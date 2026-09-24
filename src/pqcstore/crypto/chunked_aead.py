"""Chunked AES-256-GCM stream format "pqcs-chunked" (SoT §7.3, decision D7).

The plaintext is split into chunks of `chunk_size` bytes (the last may be
shorter; an empty object is one empty chunk). Chunk j is sealed with

    nonce_j = prefix(4 bytes) || uint64_be(j)
    AAD_j   = context || uint64_be(j) || uint32_be(len_j) || uint8(is_final)

and stored as ciphertext_j || tag_j. The context (which includes plaintext_size,
chunk_size and chunk_count) is authenticated in every chunk, so deletion,
reordering, truncation, appending and cross-object splicing all fail
authentication.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TAG_BYTES = 16
NONCE_PREFIX_BYTES = 4
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
MAX_CHUNK_SIZE = 64 * 1024 * 1024


class IntegrityError(Exception):
    """The stored object or manifest failed authentication or validation."""


def chunk_count(plaintext_size: int, chunk_size: int) -> int:
    if plaintext_size < 0 or not 0 < chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError("invalid plaintext_size or chunk_size")
    return max(1, -(-plaintext_size // chunk_size))


def chunk_length(index: int, plaintext_size: int, chunk_size: int) -> int:
    count = chunk_count(plaintext_size, chunk_size)
    return chunk_size if index < count - 1 else plaintext_size - chunk_size * (count - 1)


def ciphertext_size(plaintext_size: int, chunk_size: int) -> int:
    return plaintext_size + TAG_BYTES * chunk_count(plaintext_size, chunk_size)


def nonce(prefix: bytes, index: int) -> bytes:
    return prefix + index.to_bytes(8, "big")


def aad(context_bytes: bytes, index: int, length: int, final: bool) -> bytes:
    return context_bytes + index.to_bytes(8, "big") + length.to_bytes(4, "big") + bytes([final])


def _read_exact(reader: BinaryIO, length: int) -> bytes:
    """Read `length` bytes, tolerating short reads; fewer only at end of input."""
    if length == 0:
        return b""
    first = reader.read(length)
    if len(first) == length or not first:
        return first
    parts = [first]
    remaining = length - len(first)
    while remaining:
        piece = reader.read(remaining)
        if not piece:
            break
        parts.append(piece)
        remaining -= len(piece)
    return b"".join(parts)


class ChunkEncryptor:
    """Yields encrypted records for a plaintext stream; accumulates AEAD time in `aead_ns`."""

    def __init__(self, key: bytes, prefix: bytes, context_bytes: bytes, plaintext_size: int,
                 chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        if len(prefix) != NONCE_PREFIX_BYTES:
            raise ValueError("nonce prefix must be 4 bytes")
        self._aesgcm = AESGCM(key)
        self._prefix = prefix
        self._context = context_bytes
        self._size = plaintext_size
        self._chunk_size = chunk_size
        self.chunk_count = chunk_count(plaintext_size, chunk_size)
        self.aead_ns = 0

    def records(self, reader: BinaryIO) -> Iterator[bytes]:
        for index in range(self.chunk_count):
            length = chunk_length(index, self._size, self._chunk_size)
            plaintext = _read_exact(reader, length)
            if len(plaintext) != length:
                raise ValueError(f"plaintext ended early at chunk {index}")
            final = index == self.chunk_count - 1
            # Check for surplus input before sealing the final chunk: consumers such as an
            # S3 upload stop pulling records once they have the declared length.
            if final and _read_exact(reader, 1):
                raise ValueError("plaintext is longer than plaintext_size")
            start = time.perf_counter_ns()
            record = self._aesgcm.encrypt(nonce(self._prefix, index), plaintext,
                                          aad(self._context, index, length, final))
            self.aead_ns += time.perf_counter_ns() - start
            yield record


class ChunkDecryptor:
    """Re-frames an arbitrary byte stream into records and yields verified plaintext chunks.

    Callers must treat yielded chunks as provisional until iteration finishes
    without an exception: only then is the object complete and authentic.
    """

    def __init__(self, key: bytes, prefix: bytes, context_bytes: bytes, plaintext_size: int,
                 chunk_size: int) -> None:
        self._aesgcm = AESGCM(key)
        self._prefix = prefix
        self._context = context_bytes
        self._size = plaintext_size
        self._chunk_size = chunk_size
        self.chunk_count = chunk_count(plaintext_size, chunk_size)
        self.aead_ns = 0

    def plaintext(self, stream: Iterable[bytes]) -> Iterator[bytes]:
        buffer = bytearray()
        index = 0
        for piece in stream:
            buffer += piece
            while index < self.chunk_count:
                length = chunk_length(index, self._size, self._chunk_size)
                if len(buffer) < length + TAG_BYTES:
                    break
                # Decrypt straight from the buffer (no copy); the view must be released
                # before the buffer can shrink.
                with memoryview(buffer) as view:
                    chunk = self._open(index, length, view[:length + TAG_BYTES])
                del buffer[:length + TAG_BYTES]
                yield chunk
                index += 1
            if index == self.chunk_count and buffer:
                raise IntegrityError("unexpected data after the final chunk")
        if index < self.chunk_count:
            raise IntegrityError(f"stream truncated: {index} of {self.chunk_count} chunks")

    def _open(self, index: int, length: int, record: bytes | memoryview) -> bytes:
        final = index == self.chunk_count - 1
        start = time.perf_counter_ns()
        try:
            chunk = self._aesgcm.decrypt(nonce(self._prefix, index), record,
                                         aad(self._context, index, length, final))
        except InvalidTag:
            raise IntegrityError(f"authentication failed at chunk {index}") from None
        finally:
            self.aead_ns += time.perf_counter_ns() - start
        return chunk
