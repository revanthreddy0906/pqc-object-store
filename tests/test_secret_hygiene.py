"""Secrets never reach manifests or world-readable files (SoT §7.7)."""

import base64
import io
import os
import stat

import pytest

from pqcstore import keys
from pqcstore.crypto import mlkem
from pqcstore.crypto.envelope import seal
from pqcstore.crypto.manifest import key_id
from pqcstore.timing import Stages


def encodings(secret: bytes) -> list[bytes]:
    return [secret, secret.hex().encode(), base64.b64encode(secret),
            base64.urlsafe_b64encode(secret)]


def test_manifest_contains_no_secret_material(recipient, identity, monkeypatch):
    captured = {}
    real_encapsulate = mlkem.encapsulate

    def spy(public_key):
        ciphertext, secret = real_encapsulate(public_key)
        captured["secret"] = secret
        return ciphertext, secret

    monkeypatch.setattr(mlkem, "encapsulate", spy)
    manifest, encryptor = seal(recipient.public_key, identity, 10, Stages(), 1024)
    b"".join(encryptor.records(io.BytesIO(os.urandom(10))))
    for secret in (captured["secret"], recipient.private_key):
        for encoded in encodings(secret):
            assert encoded not in manifest
    assert encryptor._aesgcm is not None  # the AES key lives only in the cipher object


def test_keygen_files_and_permissions(tmp_path):
    public_path, private_path = tmp_path / "r.pub", tmp_path / "keys" / "r.key"
    pair = mlkem.generate_keypair()
    kid = keys.write_keypair(pair, public_path, private_path)
    assert stat.S_IMODE(private_path.stat().st_mode) == 0o600
    assert kid == key_id(pair.public_key)
    assert keys.load_public_key(public_path) == (pair.public_key, kid)
    assert keys.load_private_key(private_path) == (pair.private_key, kid)
    for encoded in encodings(pair.private_key):
        assert encoded not in public_path.read_bytes()


def test_existing_key_files_are_never_overwritten(tmp_path):
    public_path, private_path = tmp_path / "r.pub", tmp_path / "r.key"
    keys.write_keypair(mlkem.generate_keypair(), public_path, private_path)
    with pytest.raises(FileExistsError):
        keys.write_keypair(mlkem.generate_keypair(), public_path, private_path)


def test_group_readable_private_key_is_refused(tmp_path):
    public_path, private_path = tmp_path / "r.pub", tmp_path / "r.key"
    keys.write_keypair(mlkem.generate_keypair(), public_path, private_path)
    private_path.chmod(0o644)
    with pytest.raises(PermissionError):
        keys.load_private_key(private_path)
