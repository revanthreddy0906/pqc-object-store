"""X-Wing (draft-connolly-cfrg-xwing-kem-11) against the draft's published test vectors."""

import json
from pathlib import Path

import pytest

from pqcstore.crypto import xwing
from pqcstore.crypto.chunked_aead import IntegrityError

VECTORS = json.loads((Path(__file__).parent / "data" / "xwing-draft-11-vectors.json").read_text())
CASES = VECTORS["vectors"]


@pytest.mark.parametrize("case", CASES, ids=[c["seed"][:8] for c in CASES])
def test_key_generation_matches_vector(case):
    public_key, secret = xwing.generate_keypair(bytes.fromhex(case["seed"]))
    assert secret.hex() == case["sk"]
    assert public_key.hex() == case["pk"]


@pytest.mark.parametrize("case", CASES, ids=[c["seed"][:8] for c in CASES])
def test_derandomized_encapsulation_matches_vector(case):
    ciphertext, shared = xwing.encapsulate_derand(bytes.fromhex(case["pk"]),
                                                  bytes.fromhex(case["eseed"]))
    assert ciphertext.hex() == case["ct"]
    assert shared.hex() == case["ss"]


@pytest.mark.parametrize("case", CASES, ids=[c["seed"][:8] for c in CASES])
def test_decapsulation_matches_vector(case):
    assert xwing.decapsulate(bytes.fromhex(case["sk"]), bytes.fromhex(case["ct"])).hex() == case["ss"]


def test_randomized_round_trip_and_sizes():
    public_key, secret = xwing.generate_keypair()
    ciphertext, shared = xwing.encapsulate(public_key)
    assert len(public_key) == xwing.PUBLIC_KEY_BYTES == 1216
    assert len(ciphertext) == xwing.CIPHERTEXT_BYTES == 1120
    assert len(secret) == xwing.SEED_BYTES == 32
    assert xwing.decapsulate(secret, ciphertext) == shared
    assert xwing.encapsulate(public_key)[1] != shared  # fresh randomness


def test_modified_ml_kem_part_gives_a_different_secret():
    """Implicit rejection: no error, but the secret no longer matches."""
    public_key, secret = xwing.generate_keypair()
    ciphertext, shared = xwing.encapsulate(public_key)
    tampered = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]
    assert xwing.decapsulate(secret, tampered) != shared


def test_modified_x25519_part_gives_a_different_secret():
    public_key, secret = xwing.generate_keypair()
    ciphertext, shared = xwing.encapsulate(public_key)
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    assert xwing.decapsulate(secret, tampered) != shared


def test_low_order_x25519_point_is_rejected():
    public_key, secret = xwing.generate_keypair()
    ciphertext, _ = xwing.encapsulate(public_key)
    with pytest.raises(IntegrityError):
        xwing.decapsulate(secret, ciphertext[:-32] + bytes(32))


def test_wrong_lengths_are_rejected():
    public_key, secret = xwing.generate_keypair()
    with pytest.raises(ValueError):
        xwing.encapsulate(public_key[:-1])
    with pytest.raises(ValueError):
        xwing.decapsulate(secret, bytes(1119))
    with pytest.raises(ValueError):
        xwing.generate_keypair(bytes(31))
