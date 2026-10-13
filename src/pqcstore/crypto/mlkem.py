"""ML-KEM-768 (FIPS 203) through liboqs.

Decapsulation never fails: with a wrong key or a modified ciphertext it returns
a pseudorandom secret (implicit rejection), so tampering surfaces later as an
AES-GCM authentication failure.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from functools import cache

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


# ---------------------------------------------------------------- direct calls (SoT v1.12)
#
# liboqs-python builds a KeyEncapsulation object for every operation: OQS_KEM_new, the KEM call,
# OQS_MEM_cleanse (when a secret key is held) and OQS_KEM_free, each through ctypes.CDLL, which
# releases the interpreter lock around every foreign call. The two functions below make ONE
# foreign call per operation on a handle created once per process, either releasing the lock
# (CDLL) or holding it (PyDLL). They exist to measure what the binding costs under thread
# contention; ML-KEM itself is the same liboqs code in all three paths.

@cache
def _direct(hold_gil: bool):
    path = oqs().native()._name
    lib = (ctypes.PyDLL if hold_gil else ctypes.CDLL)(path)
    lib.OQS_KEM_new.restype = ctypes.c_void_p
    lib.OQS_KEM_new.argtypes = [ctypes.c_char_p]
    for name in ("OQS_KEM_encaps", "OQS_KEM_decaps"):
        function = getattr(lib, name)
        function.restype = ctypes.c_int
        function.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    handle = lib.OQS_KEM_new(KEM_NAME.encode())
    if not handle:
        raise RuntimeError(f"{KEM_NAME} is not available in liboqs")
    return lib, handle


def encapsulate_direct(public_key: bytes, hold_gil: bool) -> tuple[bytes, bytes]:
    _check("public key", public_key, PUBLIC_KEY_BYTES)
    lib, handle = _direct(hold_gil)
    ciphertext = ctypes.create_string_buffer(CIPHERTEXT_BYTES)
    secret = ctypes.create_string_buffer(SHARED_SECRET_BYTES)
    if lib.OQS_KEM_encaps(handle, ciphertext, secret, public_key) != 0:
        raise RuntimeError("ML-KEM-768 encapsulation failed")
    return ciphertext.raw, secret.raw


def decapsulate_direct(private_key: bytes, kem_ciphertext: bytes, hold_gil: bool) -> bytes:
    _check("private key", private_key, PRIVATE_KEY_BYTES)
    _check("KEM ciphertext", kem_ciphertext, CIPHERTEXT_BYTES)
    lib, handle = _direct(hold_gil)
    secret = ctypes.create_string_buffer(SHARED_SECRET_BYTES)
    if lib.OQS_KEM_decaps(handle, secret, kem_ciphertext, private_key) != 0:
        raise RuntimeError("ML-KEM-768 decapsulation failed")
    return secret.raw
