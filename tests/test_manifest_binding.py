"""A manifest only decrypts the object, version and recipient it was made for (SoT §4.3)."""

import dataclasses
import json
import os

import pytest

from pqcstore.crypto import chunked_aead as ca
from pqcstore.crypto.envelope import decrypt_bytes, encrypt_bytes
from pqcstore.crypto.kdf import canonical_json
from pqcstore.crypto.manifest import ObjectIdentity, key_id, new_version, parse_manifest

CHUNK = 1024


@pytest.fixture
def sealed(recipient, identity):
    plaintext = os.urandom(2 * CHUNK + 3)
    manifest, ciphertext = encrypt_bytes(recipient.public_key, identity, plaintext, CHUNK)
    return plaintext, manifest, ciphertext


@pytest.mark.parametrize("field,value", [
    ("tenant", "other-tenant"),
    ("bucket", "other-bucket"),
    ("object_key", "dataset/item-002"),
    ("object_version", "00000000-0000-7000-8000-000000000000"),
])
def test_identity_mismatch_is_rejected(recipient, identity, sealed, field, value):
    _, manifest, ciphertext = sealed
    elsewhere = dataclasses.replace(identity, **{field: value})
    with pytest.raises(ca.IntegrityError, match="different object"):
        decrypt_bytes(recipient.private_key, manifest, ciphertext, elsewhere)


@pytest.mark.parametrize("field,value", [
    ("tenant", "x"), ("bucket", "x"), ("object_key", "x"), ("object_version", "x"),
    ("plaintext_size", 2 * CHUNK + 2), ("chunk_size", 512), ("chunk_count", 4),
    ("mode", "B1"), ("ke", "ML-KEM-1024"), ("kdf", "HKDF-SHA512"), ("aead", "AES-128-GCM"),
    ("schema_version", 1), ("schema_version", True), ("format", "one-shot"),
    ("recipient_key_id", "AAAA"), ("ke_ct_sha256", "AAAA"),
])
def test_context_field_tamper_is_rejected(recipient, identity, sealed, field, value):
    """Change one authenticated field; whichever check fires, decryption must fail."""
    _, manifest, ciphertext = sealed
    doc = json.loads(manifest)
    doc["context"][field] = value
    tampered_identity = identity
    if field in {"tenant", "bucket", "object_key", "object_version"}:
        # Also present the matching identity, so only cryptographic binding can catch it.
        tampered_identity = dataclasses.replace(identity, **{field: value})
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(recipient.private_key, canonical_json(doc), ciphertext, tampered_identity)


def test_manifest_swap_between_versions(recipient, identity):
    other = dataclasses.replace(identity, object_version=new_version())
    manifest_a, ciphertext_a = encrypt_bytes(recipient.public_key, identity, b"A" * 100, CHUNK)
    manifest_b, ciphertext_b = encrypt_bytes(recipient.public_key, other, b"B" * 100, CHUNK)
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(recipient.private_key, manifest_b, ciphertext_a, identity)
    with pytest.raises(ca.IntegrityError):  # B's manifest with A's data under B's identity
        decrypt_bytes(recipient.private_key, manifest_b, ciphertext_a, other)
    assert decrypt_bytes(recipient.private_key, manifest_a, ciphertext_a, identity) == b"A" * 100
    assert decrypt_bytes(recipient.private_key, manifest_b, ciphertext_b, other) == b"B" * 100


def test_replayed_old_version_is_rejected(recipient, identity):
    newer = dataclasses.replace(identity, object_version=new_version())
    old_manifest, old_ciphertext = encrypt_bytes(recipient.public_key, identity, b"old", CHUNK)
    with pytest.raises(ca.IntegrityError, match="different object"):
        decrypt_bytes(recipient.private_key, old_manifest, old_ciphertext, newer)


def test_recipient_key_id_check(recipient, other_recipient, identity, sealed):
    plaintext, manifest, ciphertext = sealed
    assert decrypt_bytes(recipient.private_key, manifest, ciphertext, identity,
                         expected_key_id=key_id(recipient.public_key)) == plaintext
    with pytest.raises(ca.IntegrityError, match="recipient"):
        decrypt_bytes(other_recipient.private_key, manifest, ciphertext, identity,
                      expected_key_id=key_id(other_recipient.public_key))


@pytest.mark.parametrize("mutate", [
    pytest.param(lambda d: d.update(extra=1), id="unknown-top-level-field"),
    pytest.param(lambda d: d["context"].update(extra=1), id="unknown-context-field"),
    pytest.param(lambda d: d.pop("salt"), id="missing-salt"),
    pytest.param(lambda d: d.update(salt="!!notbase64"), id="bad-base64"),
    pytest.param(lambda d: d.update(nonce_prefix="AAAAAAAA"), id="wrong-prefix-length"),
])
def test_malformed_manifest_is_rejected(identity, sealed, mutate):
    _, manifest, _ = sealed
    doc = json.loads(manifest)
    mutate(doc)
    with pytest.raises(ca.IntegrityError):
        parse_manifest(json.dumps(doc).encode(), identity)


def test_non_json_manifest_is_rejected(identity):
    with pytest.raises(ca.IntegrityError):
        parse_manifest(b"\xff\xfe not json", identity)


def test_versions_are_time_ordered_uuid7():
    versions = [new_version() for _ in range(5)]
    assert all(v[14] == "7" for v in versions)
    first, later = new_version(), None
    import time
    time.sleep(0.002)
    later = new_version()
    assert later > first


def test_object_identity_is_hashable():
    assert ObjectIdentity("t", "b", "k", "v") == ObjectIdentity("t", "b", "k", "v")
