"""Peak-memory probe for one encrypted PUT + GET (SoT Phase 4 exit check).

Peak RSS cannot be reset inside a process, so each size runs in a fresh
process: `python -m pqcstore.benchmark.memprobe --size N` prints one JSON line
with the baseline RSS (after warm-up and payload-pool allocation) and the peak
during the round trip. The difference is the memory the transfer itself needs.
"""

from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import uuid

import psutil

MIB = 1024 * 1024


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024  # Linux reports KiB


def probe(size: int, bucket: str, chunk_size: int) -> dict:
    from pqcstore.benchmark.payload import HashingSink, PayloadPool
    from pqcstore.crypto import envelope, mlkem
    from pqcstore.settings import Settings
    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    from pqcstore.storage.minio_store import MinioStore

    store = MinioStore(Settings.from_env())
    store.ensure_bucket(bucket)
    estore = EncryptedObjectStore(store)
    envelope.warm_up()
    pair = mlkem.generate_keypair()
    pool = PayloadPool()
    # Exercise one small round trip so connection pools and buffers exist before the baseline.
    small = estore.put(bucket, f"memprobe/{uuid.uuid4()}", pool.reader(1024), 1024,
                       pair.public_key)
    estore.get(bucket, small.identity.object_key, pair.private_key, HashingSink(),
               small.identity.object_version)
    estore.delete_version(bucket, small.identity.object_key, small.identity.object_version)

    baseline = psutil.Process().memory_info().rss
    peak_before = _peak_rss_bytes()
    key = f"memprobe/{uuid.uuid4()}"
    reader = pool.reader(size, offset=12345)
    put = estore.put(bucket, key, reader, size, pair.public_key, chunk_size)
    sink = HashingSink()
    get = estore.get(bucket, key, pair.private_key, sink, put.identity.object_version)
    peak = _peak_rss_bytes()
    estore.delete_version(bucket, key, put.identity.object_version)
    return {
        "size": size,
        "chunk_size": chunk_size,
        "baseline_rss": baseline,
        "peak_rss": peak,
        "peak_before": peak_before,
        "growth": max(0, peak - max(baseline, peak_before)),
        "match": sink.sha256() == reader.sha256() and sink.bytes_written == size,
        "put_ms": put.stages.total_ns / 1e6,
        "get_ms": get.stages.total_ns / 1e6,
    }


def run_isolated(size: int, bucket: str = "pqc-bench", chunk_size: int = 4 * MIB) -> dict:
    """Run `probe` in a fresh interpreter and return its result."""
    output = subprocess.run(
        [sys.executable, "-m", "pqcstore.benchmark.memprobe", "--size", str(size),
         "--bucket", bucket, "--chunk-size", str(chunk_size)],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(output.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--bucket", default="pqc-bench")
    parser.add_argument("--chunk-size", type=int, default=4 * MIB)
    args = parser.parse_args()
    print(json.dumps(probe(args.size, args.bucket, args.chunk_size)))


if __name__ == "__main__":
    main()
