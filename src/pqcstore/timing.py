"""Stage timers for the latency decomposition (SoT §8.2)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass


@dataclass
class Stages:
    """Nanoseconds spent per stage of one PUT or GET."""

    ke_ns: int = 0     # key establishment: encaps/decaps, RSA wrap/unwrap, ECDH
    kdf_ns: int = 0    # HKDF
    aead_ns: int = 0   # AES-GCM over all chunks
    ser_ns: int = 0    # manifest serialization / parsing and validation
    s3_ns: int = 0     # object-store transfer, excluding AEAD time interleaved with it
    total_ns: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@contextmanager
def measure(stages: Stages, field: str) -> Iterator[None]:
    start = time.perf_counter_ns()
    try:
        yield
    finally:
        setattr(stages, field, getattr(stages, field) + time.perf_counter_ns() - start)
