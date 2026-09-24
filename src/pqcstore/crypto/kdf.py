"""HKDF-SHA256 key derivation bound to a canonical object context (SoT §7.2–7.3)."""

from __future__ import annotations

import json
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

OBJECT_DOMAIN = b"pqc-s3-object-v2"
KEY_BYTES = 32


def canonical_json(value: dict[str, Any]) -> bytes:
    """UTF-8 JSON with sorted keys and no insignificant whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def derive_object_key(ikm: bytes, salt: bytes, context_bytes: bytes,
                      domain: bytes = OBJECT_DOMAIN) -> bytes:
    info = domain + b"\x00" + context_bytes
    return HKDF(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=salt, info=info).derive(ikm)
