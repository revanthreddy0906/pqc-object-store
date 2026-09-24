"""Encrypted objects on S3 with a manifest-as-commit protocol (SoT D9).

Each PUT creates a new version under

    <object_key>.pqcs/<version>/data.enc       chunked ciphertext stream
    <object_key>.pqcs/<version>/manifest.json  written last = commit record

Readers only consider versions whose manifest exists, so an interrupted upload
(data without manifest) is never visible. Versions are UUIDv7, so the latest
committed version is the lexicographically largest one.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from minio.error import S3Error

from pqcstore.crypto import envelope
from pqcstore.crypto.chunked_aead import DEFAULT_CHUNK_SIZE, ciphertext_size
from pqcstore.crypto.manifest import ObjectIdentity, new_version
from pqcstore.storage.minio_store import MinioStore
from pqcstore.timing import Stages

SUFFIX = ".pqcs"
DATA = "data.enc"
MANIFEST = "manifest.json"


class ObjectNotFound(LookupError):
    pass


class CommitVerificationError(RuntimeError):
    """A committed version does not match what was written (read-after-write check)."""


@dataclass
class Audit:
    committed: list[str] = field(default_factory=list)
    orphaned_data: list[tuple[str, datetime]] = field(default_factory=list)  # data, no manifest
    dangling_manifests: list[str] = field(default_factory=list)  # manifest, no data

    @property
    def clean(self) -> bool:
        return not self.orphaned_data and not self.dangling_manifests


def version_prefix(object_key: str, version: str) -> str:
    return f"{object_key}{SUFFIX}/{version}/"


class _IterReader:
    """File-like `read(n)` over an iterator of byte strings (what minio-py uploads from)."""

    def __init__(self, pieces: Iterator[bytes]) -> None:
        self._pieces = pieces
        self._buffer = bytearray()

    def read(self, size: int = -1) -> bytes:
        while size < 0 or len(self._buffer) < size:
            piece = next(self._pieces, None)
            if piece is None:
                break
            self._buffer += piece
        if size < 0:
            size = len(self._buffer)
        out = bytes(self._buffer[:size])
        del self._buffer[:size]
        return out


@dataclass
class TransferResult:
    identity: ObjectIdentity
    stages: Stages = field(default_factory=Stages)
    plaintext_bytes: int = 0
    stored_bytes: int = 0
    metadata_bytes: int = 0


class EncryptedObjectStore:
    def __init__(self, store: MinioStore, tenant: str = "research") -> None:
        self.store = store
        self.tenant = tenant

    def put(self, bucket: str, object_key: str, reader: BinaryIO, plaintext_size: int,
            recipient_public_key: bytes, chunk_size: int = DEFAULT_CHUNK_SIZE) -> TransferResult:
        """Encrypt and upload a new version. Time spent in `reader.read` is counted in
        s3_ns, so timed runs read from the in-memory payload pool."""
        start = time.perf_counter_ns()
        identity = ObjectIdentity(self.tenant, bucket, object_key, new_version())
        result = TransferResult(identity)
        stages = result.stages
        manifest_bytes, encryptor = envelope.seal(recipient_public_key, identity, plaintext_size,
                                                  stages, chunk_size)
        prefix = version_prefix(object_key, identity.object_version)
        stored = ciphertext_size(plaintext_size, chunk_size)

        upload_start = time.perf_counter_ns()
        try:
            self.store.put_stream(bucket, prefix + DATA, _IterReader(encryptor.records(reader)),
                                  length=stored)
            self.store.put_bytes(bucket, prefix + MANIFEST, manifest_bytes, "application/json")
        except BaseException as exc:
            # minio-py already aborted any multipart upload; remove what may have landed.
            # The manifest goes first so the version can never look committed.
            self._remove_quietly(bucket, prefix, exc)
            raise
        # AEAD runs inside the upload's read() calls; subtract it to isolate transfer time.
        stages.aead_ns = encryptor.aead_ns
        stages.s3_ns = time.perf_counter_ns() - upload_start - encryptor.aead_ns
        stages.total_ns = time.perf_counter_ns() - start
        result.plaintext_bytes = plaintext_size
        result.stored_bytes = stored
        result.metadata_bytes = len(manifest_bytes)
        return result

    def verify_committed(self, result: TransferResult) -> None:
        """Read-after-write check: both objects exist with the sizes that were written.
        Not part of the timed PUT path."""
        identity = result.identity
        prefix = version_prefix(identity.object_key, identity.object_version)
        for name, expected in ((DATA, result.stored_bytes), (MANIFEST, result.metadata_bytes)):
            actual = self.store.stat_size(identity.bucket, prefix + name)
            if actual != expected:
                raise CommitVerificationError(
                    f"{identity.bucket}/{prefix}{name}: stored {actual} B, expected {expected} B")

    def delete_version(self, bucket: str, object_key: str, version: str) -> None:
        """Uncommit first (manifest), then remove the data."""
        prefix = version_prefix(object_key, version)
        self.store.delete(bucket, prefix + MANIFEST)
        self.store.delete(bucket, prefix + DATA)

    def _remove_quietly(self, bucket: str, prefix: str, cause: BaseException) -> None:
        for name in (MANIFEST, DATA):
            try:
                self.store.delete(bucket, prefix + name)
            except Exception as cleanup_error:  # noqa: BLE001 - report, never mask the cause
                cause.add_note(f"cleanup of {prefix}{name} failed: {cleanup_error!r}; "
                               "collect_garbage() will remove it")

    def audit(self, bucket: str, prefix: str = "") -> Audit:
        """Classify every version directory under `prefix` (an object-key prefix)."""
        versions: dict[str, dict[str, datetime]] = {}
        for obj in self.store.client.list_objects(bucket, prefix=prefix, recursive=True):
            head, _, name = obj.object_name.rpartition("/")  # head = <key>.pqcs/<version>
            if name not in (DATA, MANIFEST) or not head.rpartition("/")[0].endswith(SUFFIX):
                continue
            versions.setdefault(head + "/", {})[name] = obj.last_modified
        report = Audit()
        for version_dir, files in sorted(versions.items()):
            if MANIFEST in files and DATA in files:
                report.committed.append(version_dir)
            elif DATA in files:
                report.orphaned_data.append((version_dir, files[DATA]))
            else:
                report.dangling_manifests.append(version_dir)
        return report

    def collect_garbage(self, bucket: str, prefix: str = "",
                        older_than: timedelta = timedelta(hours=1)) -> list[str]:
        """Delete data objects that never got a manifest. The age threshold protects
        uploads that are still in flight."""
        cutoff = datetime.now(UTC) - older_than
        removed = []
        for version_dir, modified in self.audit(bucket, prefix).orphaned_data:
            if modified <= cutoff:
                self.store.delete(bucket, version_dir + DATA)
                removed.append(version_dir)
        return removed

    def committed_versions(self, bucket: str, object_key: str) -> list[str]:
        prefix = f"{object_key}{SUFFIX}/"
        versions = []
        for obj in self.store.client.list_objects(bucket, prefix=prefix, recursive=True):
            version, _, name = obj.object_name[len(prefix):].partition("/")
            if name == MANIFEST:
                versions.append(version)
        return sorted(versions)

    def get(self, bucket: str, object_key: str, recipient_private_key: bytes, sink: BinaryIO,
            version: str | None = None, expected_key_id: str | None = None) -> TransferResult:
        """Decrypt into `sink`. Data written to `sink` is only trustworthy if this returns;
        on IntegrityError the caller must discard it. Benchmarks should pass `version`;
        otherwise the LIST that finds the latest version is counted as S3 time.

        Time spent in `sink.write` is counted in s3_ns, so timed runs use a null sink."""
        start = time.perf_counter_ns()
        list_ns = 0
        if version is None:
            versions = self.committed_versions(bucket, object_key)
            list_ns = time.perf_counter_ns() - start
            if not versions:
                raise ObjectNotFound(f"no committed version of {bucket}/{object_key}")
            version = versions[-1]
        identity = ObjectIdentity(self.tenant, bucket, object_key, version)
        result = TransferResult(identity)
        stages = result.stages
        prefix = version_prefix(object_key, version)

        fetch_start = time.perf_counter_ns()
        try:
            manifest_bytes = self.store.get_bytes(bucket, prefix + MANIFEST)
        except S3Error as exc:
            if exc.code == "NoSuchKey":
                raise ObjectNotFound(f"{bucket}/{object_key} version {version} "
                                     "is not committed") from None
            raise
        manifest_fetch_ns = time.perf_counter_ns() - fetch_start

        decryptor = envelope.open_manifest(recipient_private_key, manifest_bytes, identity,
                                           stages, expected_key_id)
        download_start = time.perf_counter_ns()
        stored = 0

        def counted() -> Iterator[bytes]:
            nonlocal stored
            for piece in self.store.iter_object(bucket, prefix + DATA):
                stored += len(piece)
                yield piece

        for chunk in decryptor.plaintext(counted()):
            sink.write(chunk)
            result.plaintext_bytes += len(chunk)
        stages.aead_ns = decryptor.aead_ns
        stages.s3_ns = list_ns + manifest_fetch_ns + (time.perf_counter_ns() - download_start
                                                      - decryptor.aead_ns)
        stages.total_ns = time.perf_counter_ns() - start
        result.stored_bytes = stored
        result.metadata_bytes = len(manifest_bytes)
        return result
