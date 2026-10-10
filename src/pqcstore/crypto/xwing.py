"""X-Wing hybrid KEM (X25519 + ML-KEM-768), draft-connolly-cfrg-xwing-kem-11.

Follows the draft's machine-readable specification (Appendix B):

    expandDecapsulationKey(seed): SHAKE256(seed, 96 bytes) -> ML-KEM-768 KeyGen(expanded[0:64]),
                                  X25519 private key = expanded[64:96]
    public key  = pk_M (1184) || pk_X (32)                      = 1216 bytes
    ciphertext  = ct_M (1088) || ct_X (32)                      = 1120 bytes
    shared key  = SHA3-256(ss_M || ss_X || ct_X || pk_X || XWingLabel)

The decapsulation key is the 32-byte seed. Expanding it costs one ML-KEM key generation, so
the expansion is cached per process, which the draft explicitly allows; P1 likewise holds
its expanded ML-KEM key. ML-KEM runs through the same liboqs build as mode P1 and X25519
through pyca/cryptography as in mode B2, so the comparison isolates the construction.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from functools import lru_cache

from cryptography.hazmat.primitives.asymmetric import x25519

from pqcstore.crypto import mlkem
from pqcstore.crypto.chunked_aead import IntegrityError
from pqcstore.crypto.oqs_runtime import KEM_NAME, oqs

XWING_LABEL = bytes.fromhex("5c2e2f2f5e5c")  # "\./" "/^\"
SEED_BYTES = 32
ESEED_BYTES = 64
PUBLIC_KEY_BYTES = mlkem.PUBLIC_KEY_BYTES + 32
CIPHERTEXT_BYTES = mlkem.CIPHERTEXT_BYTES + 32
SHARED_SECRET_BYTES = 32


def _check(name: str, value: bytes, expected: int) -> None:
    if len(value) != expected:
        raise ValueError(f"X-Wing {name} must be {expected} bytes, got {len(value)}")


@lru_cache(maxsize=16)
def expand_decapsulation_key(seed: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """Return (sk_M expanded, sk_X, pk_M, pk_X) for a 32-byte seed."""
    _check("seed", seed, SEED_BYTES)
    expanded = hashlib.shake_256(seed).digest(96)
    with oqs().KeyEncapsulation(KEM_NAME) as kem:
        pk_m = kem.generate_keypair_seed(expanded[0:64])
        sk_m = kem.export_secret_key()
    sk_x = expanded[64:96]
    pk_x = x25519.X25519PrivateKey.from_private_bytes(sk_x).public_key().public_bytes_raw()
    return sk_m, sk_x, pk_m, pk_x


def generate_keypair(seed: bytes | None = None) -> tuple[bytes, bytes]:
    """Return (public key, decapsulation key); the decapsulation key is the seed."""
    seed = os.urandom(SEED_BYTES) if seed is None else seed
    _, _, pk_m, pk_x = expand_decapsulation_key(seed)
    return pk_m + pk_x, seed


def combiner(ss_m: bytes, ss_x: bytes, ct_x: bytes, pk_x: bytes) -> bytes:
    return hashlib.sha3_256(ss_m + ss_x + ct_x + pk_x + XWING_LABEL).digest()


def _x25519(private: bytes, public: bytes) -> bytes:
    try:
        return x25519.X25519PrivateKey.from_private_bytes(private).exchange(
            x25519.X25519PublicKey.from_public_bytes(public))
    except ValueError:  # low-order point: the shared secret would be all zeros
        raise IntegrityError("invalid X25519 point in X-Wing ciphertext") from None


def _mlkem_encaps_derand(pk_m: bytes, m: bytes) -> tuple[bytes, bytes]:
    """Deterministic ML-KEM-768 encapsulation (liboqs OQS_KEM_encaps_derand)."""
    lib = oqs()
    with lib.KeyEncapsulation(KEM_NAME) as kem:
        ct = ctypes.create_string_buffer(mlkem.CIPHERTEXT_BYTES)
        ss = ctypes.create_string_buffer(mlkem.SHARED_SECRET_BYTES)
        rv = lib.native().OQS_KEM_encaps_derand(
            kem._kem, ctypes.byref(ct), ctypes.byref(ss),
            ctypes.create_string_buffer(pk_m, len(pk_m)), ctypes.create_string_buffer(m, len(m)))
        if rv != 0:  # OQS_SUCCESS
            raise RuntimeError("ML-KEM-768 derandomized encapsulation failed")
        return bytes(ct), bytes(ss)


def encapsulate_derand(public_key: bytes, eseed: bytes) -> tuple[bytes, bytes]:
    """Return (ciphertext, shared secret) for given randomness (used by the test vectors)."""
    _check("public key", public_key, PUBLIC_KEY_BYTES)
    _check("eseed", eseed, ESEED_BYTES)
    pk_m, pk_x = public_key[:mlkem.PUBLIC_KEY_BYTES], public_key[mlkem.PUBLIC_KEY_BYTES:]
    ek_x = eseed[32:64]
    ct_x = x25519.X25519PrivateKey.from_private_bytes(ek_x).public_key().public_bytes_raw()
    ss_x = _x25519(ek_x, pk_x)
    ct_m, ss_m = _mlkem_encaps_derand(pk_m, eseed[0:32])
    return ct_m + ct_x, combiner(ss_m, ss_x, ct_x, pk_x)


def encapsulate(public_key: bytes) -> tuple[bytes, bytes]:
    """Return (ciphertext, shared secret) with fresh randomness."""
    _check("public key", public_key, PUBLIC_KEY_BYTES)
    pk_m, pk_x = public_key[:mlkem.PUBLIC_KEY_BYTES], public_key[mlkem.PUBLIC_KEY_BYTES:]
    ephemeral = x25519.X25519PrivateKey.generate()
    ct_x = ephemeral.public_key().public_bytes_raw()
    ss_x = ephemeral.exchange(x25519.X25519PublicKey.from_public_bytes(pk_x))
    ct_m, ss_m = mlkem.encapsulate(pk_m)
    return ct_m + ct_x, combiner(ss_m, ss_x, ct_x, pk_x)


def decapsulate(seed: bytes, ciphertext: bytes) -> bytes:
    """Recover the shared secret. Like ML-KEM, never fails on a modified ciphertext."""
    _check("ciphertext", ciphertext, CIPHERTEXT_BYTES)
    sk_m, sk_x, _, pk_x = expand_decapsulation_key(seed)
    ct_m, ct_x = ciphertext[:mlkem.CIPHERTEXT_BYTES], ciphertext[mlkem.CIPHERTEXT_BYTES:]
    ss_m = mlkem.decapsulate(sk_m, ct_m)
    ss_x = _x25519(sk_x, ct_x)
    return combiner(ss_m, ss_x, ct_x, pk_x)
