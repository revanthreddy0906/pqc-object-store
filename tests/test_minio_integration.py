"""Raw S3 transport against a live MinIO (Phase 1 exit criterion)."""

import hashlib
import io
import os

import pytest

pytestmark = pytest.mark.integration

MIB = 1024 * 1024


@pytest.mark.parametrize("size", [0, 1, MIB])
def test_raw_round_trip_bytes(store, settings, test_prefix, size):
    payload = os.urandom(size)
    key = f"{test_prefix}raw-{size}"
    store.put_bytes(settings.bucket, key, payload)
    assert hashlib.sha256(store.get_bytes(settings.bucket, key)).digest() == \
        hashlib.sha256(payload).digest()


def test_multipart_stream_round_trip(store, settings, test_prefix):
    # 20 MiB with unknown length forces a multipart upload in 8 MiB parts.
    payload = os.urandom(20 * MIB)
    key = f"{test_prefix}multipart"
    store.put_stream(settings.bucket, key, io.BytesIO(payload), length=-1)
    digest = hashlib.sha256()
    for chunk in store.iter_object(settings.bucket, key):
        digest.update(chunk)
    assert digest.digest() == hashlib.sha256(payload).digest()


def test_delete_prefix_removes_everything(store, settings, test_prefix):
    for i in range(3):
        store.put_bytes(settings.bucket, f"{test_prefix}del/{i}", b"x")
    assert store.delete_prefix(settings.bucket, f"{test_prefix}del/") == 3
    assert list(store.client.list_objects(settings.bucket, prefix=f"{test_prefix}del/")) == []
