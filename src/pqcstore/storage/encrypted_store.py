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
        self.store.put_stream(bucket, prefix + DATA, _IterReader(encryptor.records(reader)),
                              length=stored)
        self.store.put_bytes(bucket, prefix + MANIFEST, manifest_bytes, "application/json")
        # AEAD runs inside the upload's read() calls; subtract it to isolate transfer time.
        stages.aead_ns = encryptor.aead_ns
        stages.s3_ns = time.perf_counter_ns() - upload_start - encryptor.aead_ns
        stages.total_ns = time.perf_counter_ns() - start
        result.plaintext_bytes = plaintext_size
        result.stored_bytes = stored
        result.metadata_bytes = len(manifest_bytes)
        return result

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
