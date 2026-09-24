"""ML-KEM-768 (FIPS 203) through liboqs.

Decapsulation never fails: with a wrong key or a modified ciphertext it returns
a pseudorandom secret (implicit rejection), so tampering surfaces later as an
AES-GCM authentication failure.
"""

from __future__ import annotations

from dataclasses import dataclass

from pqcstore.crypto.oqs_runtime import KEM_NAME, oqs

PUBLIC_KEY_BYTES = 1184
PRIVATE_KEY_BYTES = 2400
CIPHERTEXT_BYTES = 1088
SHARED_SECRET_BYTES = 32


@dataclass(frozen=True)
class KEMKeyPair:
    public_key: bytes
    private_key: bytes


def _check(name: str, value: bytes, expected: int) -> None:
    if len(value) != expected:
        raise ValueError(f"{name} must be {expected} bytes, got {len(value)}")


def generate_keypair() -> KEMKeyPair:
    with oqs().KeyEncapsulation(KEM_NAME) as kem:
        public_key = kem.generate_keypair()
        private_key = kem.export_secret_key()
    return KEMKeyPair(public_key, private_key)


def encapsulate(public_key: bytes) -> tuple[bytes, bytes]:
    """Return (kem_ciphertext, shared_secret)."""
    _check("public key", public_key, PUBLIC_KEY_BYTES)
    with oqs().KeyEncapsulation(KEM_NAME) as kem:
        return kem.encap_secret(public_key)


def decapsulate(private_key: bytes, kem_ciphertext: bytes) -> bytes:
    _check("private key", private_key, PRIVATE_KEY_BYTES)
    _check("KEM ciphertext", kem_ciphertext, CIPHERTEXT_BYTES)
    with oqs().KeyEncapsulation(KEM_NAME, private_key) as kem:
        return kem.decap_secret(kem_ciphertext)
