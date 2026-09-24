"""Command-line entry point: `pqcstore <command>` or `python -m pqcstore.cli <command>`."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import sys
import uuid

from pqcstore.settings import Settings


def cmd_doctor(_: argparse.Namespace) -> int:
    """Print the environment facts every run manifest records, and fail on problems."""
    import cryptography
    import minio
    from cryptography.hazmat.backends.openssl import backend

    from pqcstore.crypto import oqs_runtime
    from pqcstore.storage.minio_store import MinioStore

    ok = True
    print(f"python                 {platform.python_version()} ({sys.executable})")
    print(f"platform               {platform.platform()} / {platform.machine()}")
    print(f"cryptography           {cryptography.__version__} ({backend.openssl_version_text()})")
    print(f"minio-py               {minio.__version__}")
    try:
        for key, value in oqs_runtime.build_info().items():
            print(f"{key:<22} {value}")
    except oqs_runtime.LiboqsEnvironmentError as exc:
        ok = False
        print(f"liboqs                 ERROR: {exc}")
    try:
        settings = Settings.from_env()
        reachable = MinioStore(settings).server_reachable()
        print(f"s3 endpoint            {settings.s3_endpoint} reachable={reachable}")
        ok = ok and reachable
    except RuntimeError as exc:
        ok = False
        print(f"s3 endpoint            ERROR: {exc}")
    print("status                 " + ("OK" if ok else "PROBLEMS FOUND"))
    return 0 if ok else 1


def cmd_s3_smoke(args: argparse.Namespace) -> int:
    """Phase 1 exit check: raw (unencrypted) upload/download round trip."""
    from pqcstore.storage.minio_store import MinioStore

    settings = Settings.from_env()
    store = MinioStore(settings)
    store.ensure_bucket(settings.bucket)
    payload = os.urandom(args.size)
    key = f"smoke/raw-{uuid.uuid4()}"
    store.put_bytes(settings.bucket, key, payload)
    try:
        recovered = store.get_bytes(settings.bucket, key)
    finally:
        store.delete(settings.bucket, key)
    sent, got = hashlib.sha256(payload).hexdigest(), hashlib.sha256(recovered).hexdigest()
    print(f"uploaded   {len(payload)} bytes sha256={sent}")
    print(f"downloaded {len(recovered)} bytes sha256={got}")
    print("MATCH" if sent == got else "MISMATCH")
    return 0 if sent == got else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pqcstore")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="check liboqs, libraries and the S3 endpoint").set_defaults(
        func=cmd_doctor)
    smoke = sub.add_parser("s3-smoke", help="raw S3 round trip without encryption")
    smoke.add_argument("--size", type=int, default=1024 * 1024, help="payload bytes (default 1 MiB)")
    smoke.set_defaults(func=cmd_s3_smoke)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
