"""In-process micro-benchmarks of each mode's key establishment (SoT table T2, Python level).

Measures, after warm-up and with the garbage collector off, the per-operation
wall time of the sender side (establish) and receiver side (recover) of every
mode, plus HKDF-SHA256 and AES-256-GCM over one 4 MiB chunk. These isolate the
cryptographic cost from storage and network.
"""

from __future__ import annotations

import gc
import os
import platform
import statistics
import time

from pqcstore.crypto import mlkem
from pqcstore.crypto.chunked_aead import DEFAULT_CHUNK_SIZE
from pqcstore.crypto.kdf import derive_object_key
from pqcstore.crypto.modes import MODES, generate_recipient
from pqcstore.crypto.session import SenderSession, SessionPolicy


def _time(fn, iterations: int) -> dict[str, float]:
    for _ in range(min(50, iterations)):  # warm-up
        fn()
    samples = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - start)
    samples.sort()
    return {
        "n": iterations,
        "median_us": statistics.median(samples) / 1e3,
        "p95_us": samples[int(0.95 * (len(samples) - 1))] / 1e3,
        "mean_us": statistics.fmean(samples) / 1e3,
    }


def run(iterations: int = 2000) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    from pqcstore.crypto.oqs_runtime import build_info

    public, private = generate_recipient()
    results: dict[str, dict] = {}
    gc.collect()
    gc.disable()
    try:
        for name, mode in MODES.items():
            if name in ("B0", "N1"):
                continue
            ke_ct, _ = mode.establish(public)
            slow = name == "R1"  # RSA-4096 private operations take milliseconds
            results[f"{name}.establish"] = _time(lambda m=mode: m.establish(public),
                                                 iterations)
            results[f"{name}.recover"] = _time(lambda m=mode, c=ke_ct: m.recover(private, c),
                                               iterations // 10 if slow else iterations)
        for bound in (10, 100):
            session = SenderSession(public.mlkem, SessionPolicy(bound, 3600))
            results[f"N1-B{bound}.establish"] = _time(session.grant, iterations)
        pair = mlkem.generate_keypair()
        results["ML-KEM-768.keygen"] = _time(mlkem.generate_keypair, iterations // 4)
        salt, secret, context = os.urandom(32), os.urandom(32), os.urandom(400)
        results["HKDF-SHA256.derive"] = _time(lambda: derive_object_key(secret, salt, context),
                                              iterations)
        aes, nonce, chunk = AESGCM(os.urandom(32)), os.urandom(12), os.urandom(DEFAULT_CHUNK_SIZE)
        results["AES-256-GCM.encrypt-4MiB"] = _time(lambda: aes.encrypt(nonce, chunk, b""), 200)
        del pair
    finally:
        gc.enable()
    return {"platform": platform.platform(), "machine": platform.machine(),
            "python": platform.python_version(), **build_info(), "results": results}
