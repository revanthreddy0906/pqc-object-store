"""All benchmark modes share one data path and meet the same security checks (SoT §7.6, §11)."""

import dataclasses
import json
import os

import pytest

from pqcstore.benchmark.payload import HashingSink
from pqcstore.crypto import chunked_aead as ca
from pqcstore.crypto.envelope import decrypt_bytes, encrypt_bytes
from pqcstore.crypto.kdf import canonical_json
from pqcstore.crypto.modes import MODES, generate_recipient
from pqcstore.crypto.session import SenderSession, SessionPolicy

CHUNK = 1024
ALL = sorted(MODES)
ENCRYPTING = [m for m in ALL if MODES[m].encrypts]


def session_for(mode, public):
    """N1 needs a sender session; every other mode ignores it."""
    return SenderSession(public.mlkem, SessionPolicy(b_max=10, t_max_s=60)) if mode == "N1" \
        else None


@pytest.fixture(scope="module")
def keys():
    return generate_recipient()


@pytest.fixture(scope="module")
def other_keys():
    return generate_recipient()


@pytest.mark.parametrize("mode", ALL)
@pytest.mark.parametrize("size", [0, 100, 3 * CHUNK + 5])
def test_round_trip(keys, identity, mode, size):
    public, private = keys
    plaintext = os.urandom(size)
    manifest, stored = encrypt_bytes(public, identity, plaintext, CHUNK, mode,
                         session_for(mode, public))
    assert decrypt_bytes(private, manifest, stored, identity, mode=mode) == plaintext


@pytest.mark.parametrize("mode,ke_ct_bytes", [
    ("B0", 0), ("B1", 0), ("R1", 512), ("B2", 32), ("C2", 1088), ("P1", 1088), ("P2", 1120), ("P3", 1120),
])
def test_key_establishment_ciphertext_sizes(keys, identity, mode, ke_ct_bytes):
    manifest, _ = encrypt_bytes(keys[0], identity, b"x", CHUNK, mode,
                         session_for(mode, keys[0]))
    assert len(ca_b64(json.loads(manifest)["ke_ct"])) == ke_ct_bytes
    assert MODES[mode].ke_ct_bytes == ke_ct_bytes


def ca_b64(text):
    from pqcstore.crypto.manifest import b64d
    return b64d(text, "ke_ct")


def test_b0_stores_plaintext_unchanged(keys, identity):
    _, stored = encrypt_bytes(keys[0], identity, b"visible" * 10, CHUNK, "B0",
                         session_for("B0", keys[0]))
    assert stored == b"visible" * 10


@pytest.mark.parametrize("mode", ENCRYPTING)
def test_ciphertext_tamper_is_rejected(keys, identity, mode):
    public, private = keys
    manifest, stored = encrypt_bytes(public, identity, os.urandom(2 * CHUNK), CHUNK, mode,
                         session_for(mode, public))
    tampered = bytearray(stored)
    tampered[CHUNK + 20] ^= 1
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(private, manifest, bytes(tampered), identity, mode=mode)


@pytest.mark.parametrize("mode", ENCRYPTING)
def test_wrong_recipient_is_rejected(keys, other_keys, identity, mode):
    manifest, stored = encrypt_bytes(keys[0], identity, os.urandom(500), CHUNK, mode,
                         session_for(mode, keys[0]))
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(other_keys[1], manifest, stored, identity, mode=mode)


@pytest.mark.parametrize("mode", ENCRYPTING)
def test_identity_binding(keys, identity, mode):
    public, private = keys
    manifest, stored = encrypt_bytes(public, identity, b"data", CHUNK, mode,
                         session_for(mode, public))
    elsewhere = dataclasses.replace(identity, object_key="other")
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(private, manifest, stored, elsewhere, mode=mode)


@pytest.mark.parametrize("planted", ["B0", "B1", "B2", "R1", "P2", "P3"])
def test_mode_downgrade_is_rejected(keys, identity, planted):
    """A reader expecting P1 must refuse any other mode's object, above all plaintext B0."""
    public, private = keys
    manifest, stored = encrypt_bytes(public, identity, b"attacker data", CHUNK, planted,
                         session_for(planted, public))
    with pytest.raises(ca.IntegrityError, match="expected 'P1'"):
        decrypt_bytes(private, manifest, stored, identity, mode="P1")


def test_relabelled_mode_is_rejected(keys, identity):
    """Changing the mode label inside an authentic manifest fails validation."""
    public, private = keys
    manifest, stored = encrypt_bytes(public, identity, b"data", CHUNK, "B2",
                         session_for("B2", public))
    doc = json.loads(manifest)
    doc["context"]["mode"] = "P1"
    with pytest.raises(ca.IntegrityError):
        decrypt_bytes(private, canonical_json(doc), stored, identity, mode="P1")


def test_rsa_and_x25519_malformed_key_material(keys, identity):
    public, private = keys
    for mode in ("R1", "B2"):
        manifest, stored = encrypt_bytes(public, identity, b"data", CHUNK, mode,
                         session_for(mode, public))
        doc = json.loads(manifest)
        import hashlib

        from pqcstore.crypto.manifest import b64e
        bad = bytes(MODES[mode].ke_ct_bytes)  # all zeros: invalid OAEP / low-order point
        doc["ke_ct"] = b64e(bad)
        doc["context"]["ke_ct_sha256"] = b64e(hashlib.sha256(bad).digest())
        with pytest.raises(ca.IntegrityError):
            decrypt_bytes(private, canonical_json(doc), stored, identity, mode=mode)


@pytest.mark.integration
@pytest.mark.parametrize("mode", ALL)
def test_minio_round_trip_every_mode(store, settings, test_prefix, keys, mode):
    from pqcstore.benchmark.payload import PayloadPool
    from pqcstore.storage.encrypted_store import EncryptedObjectStore

    public, private = keys
    estore = EncryptedObjectStore(store)
    reader = PayloadPool(1024 * 1024).reader(5 * 1024 * 1024 + 7)
    put = estore.put(settings.bucket, f"{test_prefix}{mode}", reader, 5 * 1024 * 1024 + 7,
                     public, mode=mode, session=session_for(mode, public))
    estore.verify_committed(put)
    sink = HashingSink()
    get = estore.get(settings.bucket, f"{test_prefix}{mode}", private, sink,
                     put.identity.object_version, mode=mode)
    assert sink.sha256() == reader.sha256()
    if mode == "B0":
        # Only timer overhead is recorded for B0's no-op key establishment.
        assert put.stages.ke_ns < 100_000 and put.stages.kdf_ns == put.stages.aead_ns == 0
    else:
        assert get.stages.ke_ns > 0 and get.stages.aead_ns > 0


def test_padded_control_mode_matches_ml_kem_manifest_size(keys, identity):
    """C2 is X25519 with a manifest exactly as large as P1's (SoT v1.11 control)."""
    sizes = {}
    for mode in ("B2", "C2", "P1"):
        manifest, stored = encrypt_bytes(keys[0], identity, b"hello", CHUNK, mode, None)
        assert decrypt_bytes(keys[1], manifest, stored, identity, mode=mode) == b"hello"
        sizes[mode] = len(manifest)
    assert sizes["C2"] == sizes["P1"] > sizes["B2"]
