"""Per-object envelope encryption, mode P1: ML-KEM-768 -> HKDF-SHA256 -> chunked AES-256-GCM.

`seal` and `open_manifest` do the per-object key work and return a streaming
chunk encryptor/decryptor, so storage code can stream objects of any size.
"""

from __future__ import annotations

import io
import os

from pqcstore.crypto import mlkem
from pqcstore.crypto.chunked_aead import (
    DEFAULT_CHUNK_SIZE,
    NONCE_PREFIX_BYTES,
    ChunkDecryptor,
    ChunkEncryptor,
)
from pqcstore.crypto.kdf import canonical_json, derive_object_key
from pqcstore.crypto.manifest import (
    SALT_BYTES,
    ObjectIdentity,
    build_context,
    encode_manifest,
    key_id,
    parse_manifest,
)
from pqcstore.timing import Stages, measure

MODE = "P1"


def warm_up() -> None:
    """Pay one-off costs (liboqs load and self-checks, first HKDF/AES-GCM setup) outside
    any timer. Call once per process before timed operations."""
    pair = mlkem.generate_keypair()
    ke_ct, secret = mlkem.encapsulate(pair.public_key)
    mlkem.decapsulate(pair.private_key, ke_ct)
    key = derive_object_key(secret, os.urandom(SALT_BYTES), b"warm-up")
    list(ChunkDecryptor(key, bytes(NONCE_PREFIX_BYTES), b"", 1, 16).plaintext(
        ChunkEncryptor(key, bytes(NONCE_PREFIX_BYTES), b"", 1, 16).records(io.BytesIO(b"x"))))


def seal(recipient_public_key: bytes, identity: ObjectIdentity, plaintext_size: int,
         stages: Stages, chunk_size: int = DEFAULT_CHUNK_SIZE) -> tuple[bytes, ChunkEncryptor]:
    """Return (manifest_bytes, encryptor) for one new object version."""
    with measure(stages, "ke_ns"):
        ke_ct, shared_secret = mlkem.encapsulate(recipient_public_key)
    with measure(stages, "ser_ns"):
        salt = os.urandom(SALT_BYTES)
        prefix = os.urandom(NONCE_PREFIX_BYTES)
        context = build_context(identity, MODE, plaintext_size, chunk_size,
                                key_id(recipient_public_key), ke_ct)
        context_bytes = canonical_json(context)
    with measure(stages, "kdf_ns"):
        object_key = derive_object_key(shared_secret, salt, context_bytes)
    with measure(stages, "ser_ns"):
        manifest_bytes = encode_manifest(context, ke_ct, salt, prefix)
    return manifest_bytes, ChunkEncryptor(object_key, prefix, context_bytes, plaintext_size,
                                          chunk_size)


def open_manifest(recipient_private_key: bytes, manifest_bytes: bytes, identity: ObjectIdentity,
                  stages: Stages, expected_key_id: str | None = None) -> ChunkDecryptor:
    """Validate the manifest and return a decryptor for the matching data stream."""
    with measure(stages, "ser_ns"):
        manifest = parse_manifest(manifest_bytes, identity, expected_key_id)
    with measure(stages, "ke_ns"):
        shared_secret = mlkem.decapsulate(recipient_private_key, manifest.ke_ct)
    with measure(stages, "kdf_ns"):
        object_key = derive_object_key(shared_secret, manifest.salt, manifest.context_bytes)
    return ChunkDecryptor(object_key, manifest.nonce_prefix, manifest.context_bytes,
                          manifest.plaintext_size, manifest.chunk_size)


def encrypt_bytes(recipient_public_key: bytes, identity: ObjectIdentity, plaintext: bytes,
                  chunk_size: int = DEFAULT_CHUNK_SIZE) -> tuple[bytes, bytes]:
    """In-memory convenience for tests: return (manifest_bytes, ciphertext)."""
    manifest_bytes, encryptor = seal(recipient_public_key, identity, len(plaintext), Stages(),
                                     chunk_size)
    return manifest_bytes, b"".join(encryptor.records(io.BytesIO(plaintext)))


def decrypt_bytes(recipient_private_key: bytes, manifest_bytes: bytes, ciphertext: bytes,
                  identity: ObjectIdentity, expected_key_id: str | None = None) -> bytes:
    decryptor = open_manifest(recipient_private_key, manifest_bytes, identity, Stages(),
                              expected_key_id)
    return b"".join(decryptor.plaintext([ciphertext]))
