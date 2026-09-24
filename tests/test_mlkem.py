"""ML-KEM-768 adapter: agreement, input validation, implicit rejection, cross-implementation."""

import pytest

from pqcstore.crypto import mlkem


def test_agreement(recipient):
    ciphertext, secret = mlkem.encapsulate(recipient.public_key)
    assert len(ciphertext) == mlkem.CIPHERTEXT_BYTES
    assert len(secret) == mlkem.SHARED_SECRET_BYTES
    assert mlkem.decapsulate(recipient.private_key, ciphertext) == secret


def test_encapsulation_is_randomized(recipient):
    first = mlkem.encapsulate(recipient.public_key)
    second = mlkem.encapsulate(recipient.public_key)
    assert first[0] != second[0] and first[1] != second[1]


def test_wrong_private_key_implicitly_rejects(recipient, other_recipient):
    # FIPS 203 implicit rejection: no error, just an unrelated secret.
    ciphertext, secret = mlkem.encapsulate(recipient.public_key)
    assert mlkem.decapsulate(other_recipient.private_key, ciphertext) != secret


def test_modified_ciphertext_implicitly_rejects(recipient):
    ciphertext, secret = mlkem.encapsulate(recipient.public_key)
    tampered = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]
    assert mlkem.decapsulate(recipient.private_key, tampered) != secret


@pytest.mark.parametrize("call", [
    lambda kp: mlkem.encapsulate(kp.public_key[:-1]),
    lambda kp: mlkem.decapsulate(kp.private_key[:-1], bytes(mlkem.CIPHERTEXT_BYTES)),
    lambda kp: mlkem.decapsulate(kp.private_key, bytes(mlkem.CIPHERTEXT_BYTES - 1)),
])
def test_wrong_lengths_are_rejected(recipient, call):
    with pytest.raises(ValueError):
        call(recipient)


# Independent implementation: pyca/cryptography (OpenSSL) ML-KEM, SoT amendment A9.
try:
    from cryptography.hazmat.primitives.asymmetric import mlkem as pyca_mlkem
except ImportError:  # cryptography built without ML-KEM support
    pyca_mlkem = None
needs_pyca = pytest.mark.skipif(pyca_mlkem is None, reason="pyca/cryptography lacks ML-KEM")


@needs_pyca
def test_liboqs_to_openssl(recipient):
    """OpenSSL encapsulates to a liboqs key; liboqs decapsulates."""
    public = pyca_mlkem.MLKEM768PublicKey.from_public_bytes(recipient.public_key)
    secret, ciphertext = public.encapsulate()
    assert mlkem.decapsulate(recipient.private_key, ciphertext) == secret


@needs_pyca
def test_openssl_to_liboqs():
    """liboqs encapsulates to an OpenSSL key; OpenSSL decapsulates."""
    private = pyca_mlkem.MLKEM768PrivateKey.generate()
    ciphertext, secret = mlkem.encapsulate(private.public_key().public_bytes_raw())
    assert private.decapsulate(ciphertext) == secret
