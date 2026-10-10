"""Key-establishment modes compared by the benchmark (SoT §7.6, decisions D4/D5).

Every mode except B0 feeds its input keying material into the same HKDF +
chunked AES-256-GCM path, so differences in measured cost come from key
establishment alone.

    B0  none                  plaintext stored as-is (raw S3 + harness cost)
    B1  none                  pre-shared 32-byte master key -> HKDF per object
    R1  RSA-OAEP-4096-SHA256  random 32-byte secret wrapped per object
    B2  X25519                ephemeral-static ECDH per object
    P1  ML-KEM-768            encapsulation per object
    P2  X25519 + ML-KEM-768   study-specific hybrid: IKM = S_kem || S_ecdh, combined by HKDF
    P3  X-Wing                standards-track hybrid (draft-connolly-cfrg-xwing-kem, xwing.py)
    N1  ML-KEM-768 session    one encapsulation per bounded session root (session.py)

Keys are carried as bytes so they can be passed to worker processes; parsed
key objects are cached per process.
"""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, x25519

from pqcstore.crypto import mlkem, xwing
from pqcstore.crypto.chunked_aead import IntegrityError

MASTER_KEY_BYTES = 32
RSA_BITS = 4096
X25519_BYTES = 32
_OAEP = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(),
                     label=None)


@dataclass(frozen=True)
class RecipientPublic:
    mlkem: bytes | None = None       # ML-KEM-768 encapsulation key
    rsa: bytes | None = None         # RSA-4096 SubjectPublicKeyInfo (DER)
    x25519: bytes | None = None      # raw 32-byte public key
    master_key: bytes | None = None  # B1 is symmetric: the sender holds the key too
    xwing: bytes | None = None       # X-Wing encapsulation key (ML-KEM-768 ek || X25519 pk)


@dataclass(frozen=True)
class RecipientPrivate:
    mlkem: bytes | None = None       # ML-KEM-768 decapsulation key
    rsa: bytes | None = None         # PKCS#8 (DER)
    x25519: bytes | None = None      # raw 32-byte private key
    master_key: bytes | None = None
    xwing: bytes | None = None       # X-Wing decapsulation key: the 32-byte seed


def generate_recipient() -> tuple[RecipientPublic, RecipientPrivate]:
    """Key material for every mode. RSA-4096 generation takes ~0.3 s: never time it."""
    kem = mlkem.generate_keypair()
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=RSA_BITS)
    x_key = x25519.X25519PrivateKey.generate()
    master = os.urandom(MASTER_KEY_BYTES)
    xwing_public, xwing_seed = xwing.generate_keypair()
    public = RecipientPublic(
        mlkem=kem.public_key,
        rsa=rsa_key.public_key().public_bytes(serialization.Encoding.DER,
                                              serialization.PublicFormat.SubjectPublicKeyInfo),
        x25519=x_key.public_key().public_bytes_raw(),
        master_key=master,
        xwing=xwing_public,
    )
    private = RecipientPrivate(
        mlkem=kem.private_key,
        rsa=rsa_key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()),
        x25519=x_key.private_bytes_raw(),
        master_key=master,
        xwing=xwing_seed,
    )
    return public, private


def _require(value: bytes | None, what: str) -> bytes:
    if value is None:
        raise ValueError(f"recipient has no {what} key")
    return value


def _id(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii")


@lru_cache(maxsize=8)
def _rsa_public(der: bytes) -> rsa.RSAPublicKey:
    return serialization.load_der_public_key(der)


@lru_cache(maxsize=8)
def _rsa_private(der: bytes) -> rsa.RSAPrivateKey:
    return serialization.load_der_private_key(der, password=None)


@lru_cache(maxsize=8)
def _x_public(raw: bytes) -> x25519.X25519PublicKey:
    return x25519.X25519PublicKey.from_public_bytes(raw)


@lru_cache(maxsize=8)
def _x_private(raw: bytes) -> x25519.X25519PrivateKey:
    return x25519.X25519PrivateKey.from_private_bytes(raw)


def _ecdh_send(recipient_raw: bytes) -> tuple[bytes, bytes]:
    ephemeral = x25519.X25519PrivateKey.generate()
    secret = ephemeral.exchange(_x_public(recipient_raw))
    return ephemeral.public_key().public_bytes_raw(), secret


def _ecdh_receive(private_raw: bytes, ephemeral_raw: bytes) -> bytes:
    try:
        return _x_private(private_raw).exchange(x25519.X25519PublicKey.from_public_bytes(
            ephemeral_raw))
    except ValueError:  # malformed or low-order point
        raise IntegrityError("invalid X25519 ephemeral public key") from None


def _rsa_send(der: bytes) -> tuple[bytes, bytes]:
    secret = os.urandom(32)
    return _rsa_public(der).encrypt(secret, _OAEP), secret


def _rsa_receive(der: bytes, wrapped: bytes) -> bytes:
    try:
        return _rsa_private(der).decrypt(wrapped, _OAEP)
    except ValueError:  # OAEP decoding failure is explicit, unlike ML-KEM
        raise IntegrityError("RSA-OAEP unwrap failed") from None


def _hybrid_send(pub: RecipientPublic) -> tuple[bytes, bytes]:
    kem_ct, kem_secret = mlkem.encapsulate(_require(pub.mlkem, "ML-KEM"))
    epk, ecdh_secret = _ecdh_send(_require(pub.x25519, "X25519"))
    return kem_ct + epk, kem_secret + ecdh_secret


def _hybrid_receive(priv: RecipientPrivate, ke_ct: bytes) -> bytes:
    kem_ct, epk = ke_ct[:mlkem.CIPHERTEXT_BYTES], ke_ct[mlkem.CIPHERTEXT_BYTES:]
    return (mlkem.decapsulate(_require(priv.mlkem, "ML-KEM"), kem_ct)
            + _ecdh_receive(_require(priv.x25519, "X25519"), epk))


def _needs_session(pub: RecipientPublic) -> tuple[bytes, bytes]:
    raise ValueError("mode N1 needs a SenderSession (pass session= to seal/put)")


@dataclass(frozen=True)
class Mode:
    name: str
    ke: str
    ke_ct_bytes: int
    kdf: str
    aead: str
    key_id: Callable[[RecipientPublic], str]
    establish: Callable[[RecipientPublic], tuple[bytes, bytes]]  # -> (ke_ct, ikm)
    recover: Callable[[RecipientPrivate, bytes], bytes]           # -> ikm

    @property
    def encrypts(self) -> bool:
        return self.aead != "none"


HKDF, AEAD = "HKDF-SHA256", "AES-256-GCM"

MODES: dict[str, Mode] = {m.name: m for m in [
    Mode("B0", "none", 0, "none", "none",
         key_id=lambda pub: "none",
         establish=lambda pub: (b"", b""),
         recover=lambda priv, ct: b""),
    Mode("B1", "none", 0, HKDF, AEAD,
         key_id=lambda pub: _id(b"pqcs-b1-key-id\x00" + _require(pub.master_key, "master")),
         establish=lambda pub: (b"", _require(pub.master_key, "master")),
         recover=lambda priv, ct: _require(priv.master_key, "master")),
    Mode("R1", "RSA-OAEP-4096-SHA256", RSA_BITS // 8, HKDF, AEAD,
         key_id=lambda pub: _id(_require(pub.rsa, "RSA")),
         establish=lambda pub: _rsa_send(_require(pub.rsa, "RSA")),
         recover=lambda priv, ct: _rsa_receive(_require(priv.rsa, "RSA"), ct)),
    Mode("B2", "X25519", X25519_BYTES, HKDF, AEAD,
         key_id=lambda pub: _id(_require(pub.x25519, "X25519")),
         establish=lambda pub: _ecdh_send(_require(pub.x25519, "X25519")),
         recover=lambda priv, ct: _ecdh_receive(_require(priv.x25519, "X25519"), ct)),
    Mode("P1", "ML-KEM-768", mlkem.CIPHERTEXT_BYTES, HKDF, AEAD,
         key_id=lambda pub: _id(_require(pub.mlkem, "ML-KEM")),
         establish=lambda pub: mlkem.encapsulate(_require(pub.mlkem, "ML-KEM")),
         recover=lambda priv, ct: mlkem.decapsulate(_require(priv.mlkem, "ML-KEM"), ct)),
    Mode("P2", "X25519+ML-KEM-768", mlkem.CIPHERTEXT_BYTES + X25519_BYTES, HKDF, AEAD,
         key_id=lambda pub: _id(_require(pub.mlkem, "ML-KEM") + _require(pub.x25519, "X25519")),
         establish=_hybrid_send,
         recover=_hybrid_receive),
    Mode("P3", "X-Wing", xwing.CIPHERTEXT_BYTES, HKDF, AEAD,
         key_id=lambda pub: _id(_require(pub.xwing, "X-Wing")),
         establish=lambda pub: xwing.encapsulate(_require(pub.xwing, "X-Wing")),
         recover=lambda priv, ct: xwing.decapsulate(_require(priv.xwing, "X-Wing"), ct)),
    # N1: one ML-KEM-768 root per bounded session (crypto/session.py); the envelope
    # obtains keys from a SenderSession / ReceiverSessionCache instead.
    Mode("N1", "ML-KEM-768-session", mlkem.CIPHERTEXT_BYTES, HKDF, AEAD,
         key_id=lambda pub: _id(_require(pub.mlkem, "ML-KEM")),
         establish=_needs_session,
         recover=lambda priv, ct: mlkem.decapsulate(_require(priv.mlkem, "ML-KEM"), ct)),
]}


def as_public(value: RecipientPublic | bytes) -> RecipientPublic:
    """Bare bytes mean an ML-KEM-768 public key (the P1-only API used before Phase 5)."""
    return value if isinstance(value, RecipientPublic) else RecipientPublic(mlkem=value)


def as_private(value: RecipientPrivate | bytes) -> RecipientPrivate:
    return value if isinstance(value, RecipientPrivate) else RecipientPrivate(mlkem=value)
