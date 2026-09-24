"""Attacks on the stored ciphertext and KEM material must never yield plaintext (SoT §11)."""

import json
import os

import pytest

from pqcstore.crypto import chunked_aead as ca
from pqcstore.crypto.envelope import decrypt_bytes, encrypt_bytes
from pqcstore.crypto.manifest import b64d, b64e

CHUNK = 1024
RECORD = CHUNK + ca.TAG_BYTES


@pytest.fixture
def sealed(recipient, identity):
    plaintext = os.urandom(3 * CHUNK + 100)  # 4 chunks, the last one short
    manifest, ciphertext = encrypt_bytes(recipient.public_key, identity, plaintext, CHUNK)
    return plaintext, manifest, ciphertext


def test_round_trip(recipient, identity, sealed):
    plaintext, manifest, ciphertext = sealed
    assert decrypt_bytes(recipient.private_key, manifest, ciphertext, identity) == plaintext


def test_empty_object(recipient, identity):
    manifest, ciphertext = encrypt_bytes(recipient.public_key, identity, b"", CHUNK)
    assert len(ciphertext) == ca.TAG_BYTES
    assert decrypt_bytes(recipient.private_key, manifest, ciphertext, identity) == b""


@pytest.mark.parametrize("position", [0, RECORD - 1, RECORD + 5, -1])
def test_ciphertext_bit_flip(recipient, identity, sealed, position):
    _, manifest, ciphertext = sealed
    tampered = bytearray(ciphertext)
    tampered[position] ^= 0x01
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(recipient.private_key, manifest, bytes(tampered), identity)


def records(ciphertext: bytes) -> list[bytes]:
    return [ciphertext[i:i + RECORD] for i in range(0, len(ciphertext), RECORD)]


@pytest.mark.parametrize("edit", [
    pytest.param(lambda r: r[:1] + r[2:], id="delete-middle-chunk"),
    pytest.param(lambda r: r[:-1], id="truncate-final-chunk"),
    pytest.param(lambda r: [r[1], r[0]] + r[2:], id="reorder"),
    pytest.param(lambda r: r + [r[-1]], id="duplicate-final-chunk"),
    pytest.param(lambda r: r + [b"x"], id="append-byte"),
    pytest.param(lambda r: r[:-1] + [r[-1][:-1]], id="cut-one-byte"),
])
def test_chunk_level_edits(recipient, identity, sealed, edit):
    _, manifest, ciphertext = sealed
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(recipient.private_key, manifest, b"".join(edit(records(ciphertext))),
                      identity)


def test_wrong_private_key_fails_at_aead(recipient, other_recipient, identity, sealed):
    # Without the key-id check, implicit rejection must surface as a tag failure.
    _, manifest, ciphertext = sealed
    with pytest.raises(ca.IntegrityError, match="authentication failed"):
        decrypt_bytes(other_recipient.private_key, manifest, ciphertext, identity)


def test_kem_ciphertext_tamper_with_consistent_hash_fails_at_aead(recipient, identity, sealed):
    """Replace ke_ct and its hash together: only AES-GCM can catch it, and must."""
    _, manifest, ciphertext = sealed
    doc = json.loads(manifest)
    ke_ct = bytearray(b64d(doc["ke_ct"], "ke_ct"))
    ke_ct[10] ^= 0x01
    doc["ke_ct"] = b64e(bytes(ke_ct))
    import hashlib
    doc["context"]["ke_ct_sha256"] = b64e(hashlib.sha256(bytes(ke_ct)).digest())
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(recipient.private_key, json.dumps(doc).encode(), ciphertext, identity)


def test_kem_ciphertext_tamper_is_caught_by_hash(recipient, identity, sealed):
    _, manifest, ciphertext = sealed
    doc = json.loads(manifest)
    ke_ct = bytearray(b64d(doc["ke_ct"], "ke_ct"))
    ke_ct[0] ^= 0x01
    doc["ke_ct"] = b64e(bytes(ke_ct))
    with pytest.raises(ca.IntegrityError, match="hash"):
        decrypt_bytes(recipient.private_key, json.dumps(doc).encode(), ciphertext, identity)


@pytest.mark.parametrize("field", ["salt", "nonce_prefix"])
def test_salt_or_nonce_prefix_tamper(recipient, identity, sealed, field):
    _, manifest, ciphertext = sealed
    doc = json.loads(manifest)
    value = bytearray(b64d(doc[field], field))
    value[0] ^= 0x01
    doc[field] = b64e(bytes(value))
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(recipient.private_key, json.dumps(doc).encode(), ciphertext, identity)
