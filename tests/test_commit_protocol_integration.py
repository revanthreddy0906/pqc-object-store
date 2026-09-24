"""Failure handling of the manifest-as-commit protocol against a live MinIO (SoT Phase 3)."""

import io
import os
from datetime import timedelta

import pytest

from pqcstore.storage.encrypted_store import (
    DATA,
    MANIFEST,
    CommitVerificationError,
    EncryptedObjectStore,
    ObjectNotFound,
    version_prefix,
)

pytestmark = pytest.mark.integration

MIB = 1024 * 1024


class FailingReader(io.RawIOBase):
    """Delivers `fail_after` bytes of random data, then raises like a dying input source."""

    def __init__(self, fail_after: int) -> None:
        self._left = fail_after

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if self._left <= 0:
            raise OSError("simulated input failure")
        n = self._left if size < 0 else min(size, self._left)
        self._left -= n
        return os.urandom(n)


@pytest.fixture
def estore(store):
    return EncryptedObjectStore(store)


def incomplete_uploads(store, bucket, prefix):
    result = store.client._list_multipart_uploads(bucket, prefix=prefix)  # test-only private API
    return list(result.uploads)


@pytest.mark.parametrize("size,fail_after", [
    (2 * MIB, MIB),                  # single-part upload dies
    (20 * MIB, 17 * MIB),            # multipart upload dies after two 8 MiB parts
])
def test_failed_upload_leaves_nothing(estore, store, settings, test_prefix, recipient, size,
                                      fail_after):
    key = f"{test_prefix}dies"
    with pytest.raises(OSError, match="simulated"):
        estore.put(settings.bucket, key, FailingReader(fail_after), size, recipient.public_key)
    audit = estore.audit(settings.bucket, test_prefix)
    assert audit.committed == [] and audit.clean
    assert incomplete_uploads(store, settings.bucket, test_prefix) == []
    with pytest.raises(ObjectNotFound):
        estore.get(settings.bucket, key, recipient.private_key, io.BytesIO())


def test_failed_manifest_write_removes_data(estore, store, settings, test_prefix, recipient,
                                            monkeypatch):
    real_put_bytes = store.put_bytes

    def put_bytes(bucket, key, data, content_type="application/octet-stream"):
        if key.endswith(MANIFEST):
            raise ConnectionError("simulated failure while committing")
        return real_put_bytes(bucket, key, data, content_type)

    monkeypatch.setattr(store, "put_bytes", put_bytes)
    with pytest.raises(ConnectionError):
        estore.put(settings.bucket, f"{test_prefix}nocommit", io.BytesIO(b"x" * 1000), 1000,
                   recipient.public_key)
    audit = estore.audit(settings.bucket, test_prefix)
    assert audit.committed == [] and audit.clean


def test_input_longer_than_declared_is_not_committed(estore, settings, test_prefix, recipient):
    with pytest.raises(ValueError, match="longer"):
        estore.put(settings.bucket, f"{test_prefix}long", io.BytesIO(b"x" * 101), 100,
                   recipient.public_key)
    assert estore.audit(settings.bucket, test_prefix).committed == []


def test_verify_committed(estore, settings, test_prefix, recipient):
    result = estore.put(settings.bucket, f"{test_prefix}ok", io.BytesIO(b"hello"), 5,
                        recipient.public_key)
    estore.verify_committed(result)
    result.stored_bytes += 1
    with pytest.raises(CommitVerificationError):
        estore.verify_committed(result)


def test_delete_version_uncommits(estore, settings, test_prefix, recipient):
    key = f"{test_prefix}deleted"
    result = estore.put(settings.bucket, key, io.BytesIO(b"bye"), 3, recipient.public_key)
    estore.delete_version(settings.bucket, key, result.identity.object_version)
    assert estore.committed_versions(settings.bucket, key) == []
    assert estore.audit(settings.bucket, test_prefix).clean


def test_audit_classifies_and_gc_respects_age(estore, store, settings, test_prefix, recipient):
    committed = estore.put(settings.bucket, f"{test_prefix}good", io.BytesIO(b"ok"), 2,
                           recipient.public_key)
    orphan_dir = version_prefix(f"{test_prefix}crashed", "01a0d43d-0000-7000-8000-000000000000")
    dangling_dir = version_prefix(f"{test_prefix}odd", "01a0d43d-0000-7000-8000-000000000001")
    store.put_bytes(settings.bucket, orphan_dir + DATA, b"orphan")
    store.put_bytes(settings.bucket, dangling_dir + MANIFEST, b"{}")
    store.put_bytes(settings.bucket, f"{test_prefix}unrelated/{DATA}", b"not ours")

    audit = estore.audit(settings.bucket, test_prefix)
    good_dir = version_prefix(f"{test_prefix}good", committed.identity.object_version)
    assert audit.committed == [good_dir]
    assert [d for d, _ in audit.orphaned_data] == [orphan_dir]
    assert audit.dangling_manifests == [dangling_dir]

    # A fresh orphan may be an upload still in flight: keep it.
    assert estore.collect_garbage(settings.bucket, test_prefix, timedelta(hours=1)) == []
    assert estore.collect_garbage(settings.bucket, test_prefix, timedelta(0)) == [orphan_dir]
    assert estore.audit(settings.bucket, test_prefix).orphaned_data == []
    assert estore.committed_versions(settings.bucket, f"{test_prefix}good") == [
        committed.identity.object_version]
