"""Encrypted PUT/GET against a live MinIO, including the commit protocol (SoT D9)."""

import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from pqcstore.crypto.chunked_aead import IntegrityError
from pqcstore.storage.encrypted_store import (
    DATA,
    EncryptedObjectStore,
    ObjectNotFound,
    version_prefix,
)

pytestmark = pytest.mark.integration

MIB = 1024 * 1024


@pytest.fixture
def estore(store):
    return EncryptedObjectStore(store)


def put(estore, settings, key, plaintext, recipient, chunk_size=4 * MIB):
    return estore.put(settings.bucket, key, io.BytesIO(plaintext), len(plaintext),
                      recipient.public_key, chunk_size)


def get(estore, settings, key, recipient, version=None):
    sink = io.BytesIO()
    result = estore.get(settings.bucket, key, recipient.private_key, sink, version)
    return sink.getvalue(), result


@pytest.mark.parametrize("size", [0, MIB, 9 * MIB])
def test_round_trip(estore, settings, test_prefix, recipient, size):
    plaintext = os.urandom(size)
    key = f"{test_prefix}obj-{size}"
    put_result = put(estore, settings, key, plaintext, recipient)
    recovered, get_result = get(estore, settings, key, recipient)
    assert hashlib.sha256(recovered).digest() == hashlib.sha256(plaintext).digest()
    for result in (put_result, get_result):
        s = result.stages
        assert s.ke_ns > 0 and s.kdf_ns > 0 and s.aead_ns > 0 and s.s3_ns > 0
        assert s.total_ns >= s.ke_ns + s.kdf_ns + s.aead_ns + s.ser_ns + s.s3_ns


def test_store_only_sees_ciphertext(estore, store, settings, test_prefix, recipient):
    plaintext = b"TOP-SECRET-MARKER " * 1000
    key = f"{test_prefix}secret"
    result = put(estore, settings, key, plaintext, recipient)
    stored = store.get_bytes(settings.bucket,
                             version_prefix(key, result.identity.object_version) + DATA)
    assert b"TOP-SECRET-MARKER" not in stored
    assert len(stored) == result.stored_bytes


def test_latest_committed_version_wins(estore, settings, test_prefix, recipient):
    key = f"{test_prefix}versions"
    first = put(estore, settings, key, b"v1", recipient)
    second = put(estore, settings, key, b"v2", recipient)
    assert get(estore, settings, key, recipient)[0] == b"v2"
    assert get(estore, settings, key, recipient, first.identity.object_version)[0] == b"v1"
    assert estore.committed_versions(settings.bucket, key) == sorted(
        [first.identity.object_version, second.identity.object_version])


def test_partial_upload_is_invisible(estore, store, settings, test_prefix, recipient):
    key = f"{test_prefix}partial"
    committed = put(estore, settings, key, b"committed", recipient)
    # Simulate a crash after the data write: a newer version with data but no manifest.
    store.put_bytes(settings.bucket, version_prefix(key, "ffffffff-ffff-7fff-bfff-ffffffffffff")
                    + DATA, b"orphan")
    assert estore.committed_versions(settings.bucket, key) == [committed.identity.object_version]
    assert get(estore, settings, key, recipient)[0] == b"committed"
    with pytest.raises(ObjectNotFound):
        get(estore, settings, key, recipient, "ffffffff-ffff-7fff-bfff-ffffffffffff")


def test_missing_object(estore, settings, test_prefix, recipient):
    with pytest.raises(ObjectNotFound):
        get(estore, settings, f"{test_prefix}nothing", recipient)


def test_stored_ciphertext_tamper_is_rejected(estore, store, settings, test_prefix, recipient):
    key = f"{test_prefix}tamper"
    result = put(estore, settings, key, os.urandom(2 * MIB), recipient, chunk_size=MIB)
    data_key = version_prefix(key, result.identity.object_version) + DATA
    stored = bytearray(store.get_bytes(settings.bucket, data_key))
    stored[MIB + 100] ^= 0x01
    store.put_bytes(settings.bucket, data_key, bytes(stored))
    with pytest.raises(IntegrityError):
        get(estore, settings, key, recipient)


def test_concurrent_writers_same_key(estore, settings, test_prefix, recipient):
    key = f"{test_prefix}concurrent"
    payloads = [os.urandom(64 * 1024) for _ in range(16)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda p: put(estore, settings, key, p, recipient), payloads))
    versions = {r.identity.object_version for r in results}
    assert len(versions) == 16
    for result, payload in zip(results, payloads, strict=True):
        assert get(estore, settings, key, recipient, result.identity.object_version)[0] == payload
