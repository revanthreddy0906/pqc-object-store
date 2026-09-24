"""Recipient key files (SoT §7.1).

Public key: JSON {"kem", "key_id", "public_key"}. Private key: the same plus
"private_key", created with mode 0600 and never overwritten. Loading a private
key that other users can read is an error.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from pqcstore.crypto import mlkem
from pqcstore.crypto.manifest import b64d, b64e, key_id
from pqcstore.crypto.oqs_runtime import KEM_NAME


def _write_new(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def write_keypair(pair: mlkem.KEMKeyPair, public_path: Path, private_path: Path) -> str:
    kid = key_id(pair.public_key)
    public = {"kem": KEM_NAME, "key_id": kid, "public_key": b64e(pair.public_key)}
    private = {**public, "private_key": b64e(pair.private_key)}
    _write_new(private_path, json.dumps(private, indent=2).encode(), 0o600)
    _write_new(public_path, json.dumps(public, indent=2).encode(), 0o644)
    return kid


def _read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("kem") != KEM_NAME:
        raise ValueError(f"{path} is not an {KEM_NAME} key file")
    return data


def load_public_key(path: Path) -> tuple[bytes, str]:
    data = _read(path)
    public_key = b64d(data["public_key"], "public_key")
    if key_id(public_key) != data["key_id"]:
        raise ValueError(f"{path}: key_id does not match the public key")
    return public_key, data["key_id"]


def load_private_key(path: Path) -> tuple[bytes, str]:
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError(f"{path} is readable by other users; run chmod 600 {path}")
    data = _read(path)
    public_key = b64d(data["public_key"], "public_key")
    if key_id(public_key) != data["key_id"]:
        raise ValueError(f"{path}: key_id does not match the public key")
    return b64d(data["private_key"], "private_key"), data["key_id"]
