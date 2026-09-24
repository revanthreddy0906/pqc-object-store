"""Per-object envelope: key establishment (per mode) -> HKDF-SHA256 -> chunked AES-256-GCM.

`seal` and `open_manifest` do the per-object key work and return a streaming
chunk encryptor/decryptor, so storage code can stream objects of any size.
Mode B0 returns a pass-through chunker instead, keeping the data path identical.
"""

from __future__ import annotations

import io
import os

from pqcstore.crypto.chunked_aead import (
    DEFAULT_CHUNK_SIZE,
    NONCE_PREFIX_BYTES,
    ChunkDecryptor,
    ChunkEncryptor,
    PlainChunker,
)
from pqcstore.crypto.kdf import canonical_json, derive_object_key
from pqcstore.crypto.manifest import (
    SALT_BYTES,
    ObjectIdentity,
    build_context,
    encode_manifest,
    parse_manifest,
)
from pqcstore.crypto.modes import MODES, RecipientPrivate, RecipientPublic, as_private, as_public
from pqcstore.timing import Stages, measure

DEFAULT_MODE = "P1"


def warm_up(mode: str = DEFAULT_MODE, public: RecipientPublic | bytes | None = None,
            private: RecipientPrivate | bytes | None = None) -> None:
    """Pay one-off costs outside any timer: library loading and self-checks, key parsing
    and caching, first HKDF/AES-GCM setup. Call once per process (and per mode/key)
    before timed operations."""
    from pqcstore.crypto import mlkem

    pair = mlkem.generate_keypair()
    ke_ct, secret = mlkem.encapsulate(pair.public_key)
    mlkem.decapsulate(pair.private_key, ke_ct)
    key = derive_object_key(secret, os.urandom(SALT_BYTES), b"warm-up")
    list(ChunkDecryptor(key, bytes(NONCE_PREFIX_BYTES), b"", 1, 16).plaintext(
        ChunkEncryptor(key, bytes(NONCE_PREFIX_BYTES), b"", 1, 16).records(io.BytesIO(b"x"))))
    if public is not None and private is not None:
        identity = ObjectIdentity("warm-up", "warm-up", "warm-up", "warm-up")
        manifest, ciphertext = encrypt_bytes(public, identity, b"x" * 64, 16, mode)
        decrypt_bytes(private, manifest, ciphertext, identity, mode=mode)


def seal(recipient: RecipientPublic | bytes, identity: ObjectIdentity, plaintext_size: int,
         stages: Stages, chunk_size: int = DEFAULT_CHUNK_SIZE,
         mode: str = DEFAULT_MODE) -> tuple[bytes, ChunkEncryptor | PlainChunker]:
    """Return (manifest_bytes, encryptor) for one new object version."""
    spec = MODES[mode]
    public = as_public(recipient)
    with measure(stages, "ke_ns"):
        ke_ct, ikm = spec.establish(public)
    with measure(stages, "ser_ns"):
        salt = os.urandom(SALT_BYTES)
        prefix = os.urandom(NONCE_PREFIX_BYTES)
        context = build_context(identity, mode, plaintext_size, chunk_size,
                                spec.key_id(public), ke_ct)
        context_bytes = canonical_json(context)
    if spec.encrypts:
        with measure(stages, "kdf_ns"):  # key derivation and the AES key schedule
            object_key = derive_object_key(ikm, salt, context_bytes)
            encryptor = ChunkEncryptor(object_key, prefix, context_bytes, plaintext_size,
                                       chunk_size)
    else:
        encryptor = PlainChunker(plaintext_size, chunk_size)
    with measure(stages, "ser_ns"):
        manifest_bytes = encode_manifest(context, ke_ct, salt, prefix)
    return manifest_bytes, encryptor


def open_manifest(recipient: RecipientPrivate | bytes, manifest_bytes: bytes,
                  identity: ObjectIdentity, stages: Stages, expected_key_id: str | None = None,
                  mode: str = DEFAULT_MODE) -> ChunkDecryptor | PlainChunker:
    """Validate the manifest (for the mode the caller expects) and return a decryptor."""
    spec = MODES[mode]
    with measure(stages, "ser_ns"):
        manifest = parse_manifest(manifest_bytes, identity, mode, expected_key_id)
    if not spec.encrypts:
        return PlainChunker(manifest.plaintext_size, manifest.chunk_size)
    with measure(stages, "ke_ns"):
        ikm = spec.recover(as_private(recipient), manifest.ke_ct)
    with measure(stages, "kdf_ns"):  # key derivation and the AES key schedule
        object_key = derive_object_key(ikm, manifest.salt, manifest.context_bytes)
        return ChunkDecryptor(object_key, manifest.nonce_prefix, manifest.context_bytes,
                              manifest.plaintext_size, manifest.chunk_size)


def encrypt_bytes(recipient: RecipientPublic | bytes, identity: ObjectIdentity, plaintext: bytes,
                  chunk_size: int = DEFAULT_CHUNK_SIZE,
                  mode: str = DEFAULT_MODE) -> tuple[bytes, bytes]:
    """In-memory convenience for tests: return (manifest_bytes, ciphertext)."""
    manifest_bytes, encryptor = seal(recipient, identity, len(plaintext), Stages(), chunk_size,
                                     mode)
    return manifest_bytes, b"".join(encryptor.records(io.BytesIO(plaintext)))


def decrypt_bytes(recipient: RecipientPrivate | bytes, manifest_bytes: bytes, ciphertext: bytes,
                  identity: ObjectIdentity, expected_key_id: str | None = None,
                  mode: str = DEFAULT_MODE) -> bytes:
    decryptor = open_manifest(recipient, manifest_bytes, identity, Stages(), expected_key_id,
                              mode)
    return b"".join(decryptor.plaintext([ciphertext]))
