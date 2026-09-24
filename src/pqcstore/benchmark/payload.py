"""Payload sources and sinks that never hold a whole object in memory (SoT §8.2).

Objects of any size are streamed from a pool of random bytes generated once,
before any timing starts. Each object starts at its own offset in the pool, so
consecutive objects differ. Readers and sinks hash what passes through them so
round trips can be verified without keeping the data.
"""

from __future__ import annotations

import hashlib
import io
import os

DEFAULT_POOL_BYTES = 64 * 1024 * 1024


class PayloadPool:
    def __init__(self, size: int = DEFAULT_POOL_BYTES, seed_bytes: bytes | None = None) -> None:
        # os.urandom by default; a fixed seed_bytes makes tests reproducible.
        self._pool = (seed_bytes * (size // len(seed_bytes) + 1))[:size] if seed_bytes \
            else os.urandom(size)
        self._view = memoryview(self._pool)

    def __len__(self) -> int:
        return len(self._pool)

    def reader(self, size: int, offset: int = 0) -> PoolReader:
        return PoolReader(self._view, size, offset % len(self._pool))


class PoolReader(io.RawIOBase):
    """Reads `size` bytes cycling through the pool from `offset`; hashes what it returns."""

    def __init__(self, pool: memoryview, size: int, offset: int) -> None:
        self._pool = pool
        self._remaining = size
        self._position = offset
        self._hash = hashlib.sha256()

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        want = self._remaining if size < 0 else min(size, self._remaining)
        parts = []
        while want:
            take = min(want, len(self._pool) - self._position)
            parts.append(self._pool[self._position:self._position + take])
            self._position = (self._position + take) % len(self._pool)
            want -= take
            self._remaining -= take
        data = b"".join(parts)
        self._hash.update(data)
        return data

    def sha256(self) -> bytes:
        return self._hash.digest()


class HashingSink(io.RawIOBase):
    """Discards written data but keeps its SHA-256 and length (a 'null sink' with a check)."""

    def __init__(self) -> None:
        self._hash = hashlib.sha256()
        self.bytes_written = 0

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:
        self._hash.update(data)
        self.bytes_written += len(data)
        return len(data)

    def sha256(self) -> bytes:
        return self._hash.digest()
