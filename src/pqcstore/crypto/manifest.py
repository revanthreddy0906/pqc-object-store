"""Sidecar manifest: authenticated object context plus public crypto parameters.

Layout (canonical JSON):

    {"context": {...authenticated fields...},
     "ke_ct": b64url, "salt": b64url, "nonce_prefix": b64url}

`context` is the exact AAD/HKDF context, so every field that controls key
derivation or interpretation is authenticated (SoT §7.2). Parsing is strict:
unknown or missing fields, wrong types and inconsistent sizes are rejected
before any decryption is attempted.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pqcstore.crypto.chunked_aead import (
    MAX_CHUNK_SIZE,
    NONCE_PREFIX_BYTES,
    IntegrityError,
    chunk_count,
)
from pqcstore.crypto.kdf import canonical_json
from pqcstore.crypto.modes import MODES

SCHEMA_VERSION = 2
FORMAT = "pqcs-chunked"
SALT_BYTES = 32

CONTEXT_FIELDS = frozenset({
    "schema_version", "format", "tenant", "bucket", "object_key", "object_version", "mode", "ke",
    "kdf", "aead", "chunk_size", "chunk_count", "plaintext_size", "recipient_key_id",
    "ke_ct_sha256",
})
MANIFEST_FIELDS = frozenset({"context", "ke_ct", "salt", "nonce_prefix"})
# Extra authenticated context fields per mode.
MODE_FIELDS: dict[str, frozenset[str]] = {
    "N1": frozenset({"session_id", "session_seq", "session_bound"}),
}


@dataclass(frozen=True)
class ObjectIdentity:
    tenant: str
    bucket: str
    object_key: str
    object_version: str


@dataclass(frozen=True)
class ParsedManifest:
    context: dict[str, Any]
    context_bytes: bytes
    ke_ct: bytes
    salt: bytes
    nonce_prefix: bytes

    @property
    def plaintext_size(self) -> int:
        return self.context["plaintext_size"]

    @property
    def chunk_size(self) -> int:
        return self.context["chunk_size"]


def b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64d(text: Any, name: str) -> bytes:
    if not isinstance(text, str):
        raise IntegrityError(f"manifest field {name} is not a string")
    try:
        return base64.b64decode(text, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError):
        raise IntegrityError(f"manifest field {name} is not valid base64url") from None


def key_id(public_key: bytes) -> str:
    return b64e(hashlib.sha256(public_key).digest())


def new_version() -> str:
    """UUIDv7 (RFC 9562): random like UUIDv4 but ordered by creation time, so the
    latest committed version of a key can be found by listing."""
    millis = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = ((millis & (2**48 - 1)) << 80) | (0x7 << 76) | (((rand >> 62) & 0xFFF) << 64) \
        | (0b10 << 62) | (rand & (2**62 - 1))
    return str(uuid.UUID(int=value))


def build_context(identity: ObjectIdentity, mode: str, plaintext_size: int, chunk_size: int,
                  recipient_key_id: str, ke_ct: bytes,
                  extra: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = MODES[mode]
    if set(extra or {}) != MODE_FIELDS.get(mode, frozenset()):
        raise ValueError(f"mode {mode} needs context fields {sorted(MODE_FIELDS.get(mode, []))}")
    return {
        **(extra or {}),
        "schema_version": SCHEMA_VERSION,
        "format": FORMAT,
        "tenant": identity.tenant,
        "bucket": identity.bucket,
        "object_key": identity.object_key,
        "object_version": identity.object_version,
        "mode": mode,
        "ke": spec.ke,
        "kdf": spec.kdf,
        "aead": spec.aead,
        "chunk_size": chunk_size,
        "chunk_count": chunk_count(plaintext_size, chunk_size),
        "plaintext_size": plaintext_size,
        "recipient_key_id": recipient_key_id,
        "ke_ct_sha256": b64e(hashlib.sha256(ke_ct).digest()),
    }


def encode_manifest(context: dict[str, Any], ke_ct: bytes, salt: bytes, nonce_prefix: bytes) -> bytes:
    return canonical_json({"context": context, "ke_ct": b64e(ke_ct), "salt": b64e(salt),
                           "nonce_prefix": b64e(nonce_prefix)})


def _require_int(context: dict[str, Any], name: str) -> int:
    value = context[name]
    if type(value) is not int:  # bool is a subclass of int and must not pass
        raise IntegrityError(f"context field {name} must be an integer")
    return value


def parse_manifest(data: bytes, expected: ObjectIdentity, expected_mode: str,
                   expected_key_id: str | None = None) -> ParsedManifest:
    """Validate a manifest for the object and mode the reader asked for. Requiring the
    mode prevents downgrades, e.g. a planted B0 (plaintext) manifest being accepted."""
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise IntegrityError("manifest is not valid UTF-8 JSON") from None
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        raise IntegrityError("manifest has missing or unexpected fields")
    context = manifest["context"]
    expected_fields = CONTEXT_FIELDS | MODE_FIELDS.get(expected_mode, frozenset())
    if not isinstance(context, dict) or context.get("mode") != expected_mode:
        mode = context.get("mode") if isinstance(context, dict) else None
        raise IntegrityError(f"object uses mode {mode!r}, expected {expected_mode!r}")
    if set(context) != expected_fields:
        raise IntegrityError("manifest context has missing or unexpected fields")

    spec = MODES[expected_mode]
    fixed = {"schema_version": SCHEMA_VERSION, "format": FORMAT, "ke": spec.ke, "kdf": spec.kdf,
             "aead": spec.aead}
    for name, value in fixed.items():
        if context[name] != value or type(context[name]) is not type(value):
            raise IntegrityError(f"unsupported {name}: {context[name]!r}")

    actual = ObjectIdentity(context["tenant"], context["bucket"], context["object_key"],
                            context["object_version"])
    if actual != expected:
        raise IntegrityError("manifest belongs to a different object or version")
    if expected_key_id is not None and context["recipient_key_id"] != expected_key_id:
        raise IntegrityError("object was not encrypted for this recipient key")

    if expected_mode == "N1":
        session_id = context["session_id"]
        seq = _require_int(context, "session_seq")
        bound = _require_int(context, "session_bound")
        if not (isinstance(session_id, str) and len(session_id) == 32) or not 0 <= seq < bound:
            raise IntegrityError("invalid session fields")

    size = _require_int(context, "plaintext_size")
    chunk_size = _require_int(context, "chunk_size")
    count = _require_int(context, "chunk_count")
    if size < 0 or not 0 < chunk_size <= MAX_CHUNK_SIZE or count != chunk_count(size, chunk_size):
        raise IntegrityError("inconsistent plaintext_size, chunk_size or chunk_count")

    ke_ct = b64d(manifest["ke_ct"], "ke_ct")
    salt = b64d(manifest["salt"], "salt")
    nonce_prefix = b64d(manifest["nonce_prefix"], "nonce_prefix")
    if len(ke_ct) != spec.ke_ct_bytes:
        raise IntegrityError("key-establishment ciphertext has the wrong length")
    if len(salt) != SALT_BYTES or len(nonce_prefix) != NONCE_PREFIX_BYTES:
        raise IntegrityError("salt or nonce prefix has the wrong length")
    if b64e(hashlib.sha256(ke_ct).digest()) != context["ke_ct_sha256"]:
        raise IntegrityError("key-establishment ciphertext does not match its hash")

    return ParsedManifest(context, canonical_json(context), ke_ct, salt, nonce_prefix)
