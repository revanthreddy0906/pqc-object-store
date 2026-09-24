"""Chunked AES-256-GCM format: boundaries, framing, nonces, size enforcement."""

import io
import os

import pytest

from pqcstore.crypto import chunked_aead as ca

KEY = os.urandom(32)
PREFIX = os.urandom(4)
CONTEXT = b'{"test":true}'
CHUNK = 1024


def encrypt(plaintext: bytes, chunk_size: int = CHUNK) -> bytes:
    enc = ca.ChunkEncryptor(KEY, PREFIX, CONTEXT, len(plaintext), chunk_size)
    return b"".join(enc.records(io.BytesIO(plaintext)))


def decrypt(ciphertext_pieces, size: int, chunk_size: int = CHUNK) -> bytes:
    dec = ca.ChunkDecryptor(KEY, PREFIX, CONTEXT, size, chunk_size)
    return b"".join(dec.plaintext(ciphertext_pieces))


@pytest.mark.parametrize("size", [0, 1, CHUNK - 1, CHUNK, CHUNK + 1, 2 * CHUNK, 5 * CHUNK + 7])
def test_boundary_round_trip(size):
    plaintext = os.urandom(size)
    ciphertext = encrypt(plaintext)
    assert len(ciphertext) == ca.ciphertext_size(size, CHUNK)
    assert decrypt([ciphertext], size) == plaintext


@pytest.mark.parametrize("piece", [1, 7, CHUNK + ca.TAG_BYTES, 10_000])
def test_arbitrary_network_framing(piece):
    plaintext = os.urandom(3 * CHUNK + 100)
    ciphertext = encrypt(plaintext)
    pieces = [ciphertext[i:i + piece] for i in range(0, len(ciphertext), piece)]
    assert decrypt(pieces, len(plaintext)) == plaintext


def test_default_chunk_size_multi_chunk():
    plaintext = os.urandom(9 * 1024 * 1024)
    ciphertext = encrypt(plaintext, ca.DEFAULT_CHUNK_SIZE)
    assert ca.chunk_count(len(plaintext), ca.DEFAULT_CHUNK_SIZE) == 3
    assert decrypt([ciphertext], len(plaintext), ca.DEFAULT_CHUNK_SIZE) == plaintext


def test_chunk_count():
    assert ca.chunk_count(0, CHUNK) == 1
    assert ca.chunk_count(CHUNK, CHUNK) == 1
    assert ca.chunk_count(CHUNK + 1, CHUNK) == 2
    with pytest.raises(ValueError):
        ca.chunk_count(1, 0)
    with pytest.raises(ValueError):
        ca.chunk_count(1, ca.MAX_CHUNK_SIZE + 1)


def test_nonces_unique_for_a_million_chunks():
    nonces = {ca.nonce(PREFIX, j) for j in range(1_000_000)}
    assert len(nonces) == 1_000_000
    assert all(len(n) == 12 for n in list(nonces)[:10])


def test_short_plaintext_is_rejected():
    enc = ca.ChunkEncryptor(KEY, PREFIX, CONTEXT, 2 * CHUNK, CHUNK)
    with pytest.raises(ValueError, match="ended early"):
        b"".join(enc.records(io.BytesIO(os.urandom(CHUNK))))


def test_long_plaintext_is_rejected():
    enc = ca.ChunkEncryptor(KEY, PREFIX, CONTEXT, CHUNK, CHUNK)
    with pytest.raises(ValueError, match="longer"):
        b"".join(enc.records(io.BytesIO(os.urandom(CHUNK + 1))))


def test_aead_time_is_accumulated():
    enc = ca.ChunkEncryptor(KEY, PREFIX, CONTEXT, 4 * CHUNK, CHUNK)
    b"".join(enc.records(io.BytesIO(os.urandom(4 * CHUNK))))
    assert enc.aead_ns > 0


class Trickle(io.RawIOBase):
    """Returns at most 100 bytes per read, like a pipe or socket."""

    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        return self._data.read(100 if size < 0 else min(size, 100))


def test_short_reads_are_tolerated():
    plaintext = os.urandom(3 * CHUNK + 5)
    enc = ca.ChunkEncryptor(KEY, PREFIX, CONTEXT, len(plaintext), CHUNK)
    ciphertext = b"".join(enc.records(Trickle(plaintext)))
    assert decrypt([ciphertext], len(plaintext)) == plaintext


def test_surplus_input_is_detected_before_final_record():
    enc = ca.ChunkEncryptor(KEY, PREFIX, CONTEXT, 2 * CHUNK, CHUNK)
    records = enc.records(io.BytesIO(os.urandom(2 * CHUNK + 1)))
    next(records)  # first record is fine
    with pytest.raises(ValueError, match="longer"):
        next(records)  # the final record is never produced
