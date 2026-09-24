"""Command-line entry point: `pqcstore <command>` or `python -m pqcstore.cli <command>`."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import sys
import uuid
from pathlib import Path

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


def _print_result(label: str, result) -> None:
    identity = result.identity
    print(f"{label} {identity.bucket}/{identity.object_key} version={identity.object_version}")
    print(f"  plaintext={result.plaintext_bytes} B  stored={result.stored_bytes} B  "
          f"manifest={result.metadata_bytes} B")
    for name, value in result.stages.as_dict().items():
        print(f"  {name:<9} {value / 1e6:10.3f} ms")


def cmd_keygen(args: argparse.Namespace) -> int:
    from pqcstore import keys
    from pqcstore.crypto import mlkem

    kid = keys.write_keypair(mlkem.generate_keypair(), Path(args.public), Path(args.private))
    print(f"wrote ML-KEM-768 key pair key_id={kid}")
    print(f"  public  {args.public}\n  private {args.private} (mode 0600, keep out of Git)")
    return 0


def cmd_put(args: argparse.Namespace) -> int:
    from pqcstore import keys
    from pqcstore.crypto import envelope
    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    from pqcstore.storage.minio_store import MinioStore

    settings = Settings.from_env()
    public_key, _ = keys.load_public_key(Path(args.recipient_public_key))
    envelope.warm_up()
    store = MinioStore(settings)
    store.ensure_bucket(args.bucket)
    path = Path(args.input)
    estore = EncryptedObjectStore(store)
    with path.open("rb") as reader:
        result = estore.put(args.bucket, args.key, reader, path.stat().st_size, public_key,
                            args.chunk_size)
    estore.verify_committed(result)
    _print_result("PUT", result)
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    from pqcstore import keys
    from pqcstore.crypto import envelope
    from pqcstore.crypto.chunked_aead import IntegrityError
    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    from pqcstore.storage.minio_store import MinioStore

    settings = Settings.from_env()
    private_key, kid = keys.load_private_key(Path(args.recipient_private_key))
    envelope.warm_up()
    output = Path(args.output)
    # Plaintext goes to a temporary file and is published only after every chunk verified.
    partial = output.with_name(output.name + ".partial")
    try:
        with partial.open("wb") as sink:
            result = EncryptedObjectStore(MinioStore(settings)).get(
                args.bucket, args.key, private_key, sink, args.version, expected_key_id=kid)
    except IntegrityError as exc:
        partial.unlink(missing_ok=True)
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 2
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(output)
    _print_result("GET", result)
    return 0


def cmd_soak(args: argparse.Namespace) -> int:
    """Phase 3 exit check: N consecutive encrypted round trips, then a clean audit."""
    import io
    import statistics

    from pqcstore.crypto import envelope, mlkem
    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    from pqcstore.storage.minio_store import MinioStore

    settings = Settings.from_env()
    store = MinioStore(settings)
    store.ensure_bucket(args.bucket)
    estore = EncryptedObjectStore(store)
    envelope.warm_up()
    pair = mlkem.generate_keypair()  # ephemeral test recipient; never written to disk
    sizes = [int(s) for s in args.sizes.split(",")]
    prefix = f"soak/{uuid.uuid4()}/"
    failures, totals = [], {"put": [], "get": []}
    written = []
    for run in range(args.runs):
        size = sizes[run % len(sizes)]
        payload = os.urandom(size)
        key = f"{prefix}obj-{run:04d}"
        try:
            put = estore.put(args.bucket, key, io.BytesIO(payload), size, pair.public_key,
                             args.chunk_size)
            written.append((key, put.identity.object_version))
            estore.verify_committed(put)
            sink = io.BytesIO()
            got = estore.get(args.bucket, key, pair.private_key, sink,
                             put.identity.object_version)
            if hashlib.sha256(sink.getvalue()).digest() != hashlib.sha256(payload).digest():
                raise AssertionError("plaintext mismatch")
            totals["put"].append(put.stages.total_ns)
            totals["get"].append(got.stages.total_ns)
        except Exception as exc:  # noqa: BLE001 - count every failure, keep going
            failures.append(f"run {run} size {size}: {exc!r}")
    audit = estore.audit(args.bucket, prefix)
    ok = not failures and audit.clean and len(audit.committed) == args.runs
    print(f"runs={args.runs} failures={len(failures)} committed={len(audit.committed)} "
          f"orphaned_data={len(audit.orphaned_data)} "
          f"dangling_manifests={len(audit.dangling_manifests)}")
    for op, values in totals.items():
        if values:
            print(f"  {op} median {statistics.median(values) / 1e6:.2f} ms "
                  f"max {max(values) / 1e6:.2f} ms (dev laptop, not a result)")
    for failure in failures[:10]:
        print("  FAIL", failure)
    if not args.keep:
        for key, version in written:
            estore.delete_version(args.bucket, key, version)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def cmd_gc(args: argparse.Namespace) -> int:
    from datetime import timedelta

    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    from pqcstore.storage.minio_store import MinioStore

    estore = EncryptedObjectStore(MinioStore(Settings.from_env()))
    audit = estore.audit(args.bucket, args.prefix)
    print(f"committed={len(audit.committed)} orphaned_data={len(audit.orphaned_data)} "
          f"dangling_manifests={len(audit.dangling_manifests)}")
    for version_dir in audit.dangling_manifests:
        print(f"  WARNING manifest without data: {version_dir}")
    if args.dry_run:
        return 0
    removed = estore.collect_garbage(args.bucket, args.prefix,
                                     timedelta(minutes=args.older_than_minutes))
    print(f"removed {len(removed)} orphaned data object(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pqcstore")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="check liboqs, libraries and the S3 endpoint").set_defaults(
        func=cmd_doctor)
    smoke = sub.add_parser("s3-smoke", help="raw S3 round trip without encryption")
    smoke.add_argument("--size", type=int, default=1024 * 1024, help="payload bytes (default 1 MiB)")
    smoke.set_defaults(func=cmd_s3_smoke)

    keygen = sub.add_parser("keygen", help="create a recipient ML-KEM-768 key pair")
    keygen.add_argument("--public", required=True)
    keygen.add_argument("--private", required=True)
    keygen.set_defaults(func=cmd_keygen)

    put = sub.add_parser("put", help="encrypt a file and upload it as a new version")
    put.add_argument("--bucket", required=True)
    put.add_argument("--key", required=True)
    put.add_argument("--input", required=True)
    put.add_argument("--recipient-public-key", required=True)
    put.add_argument("--chunk-size", type=int, default=4 * 1024 * 1024)
    put.set_defaults(func=cmd_put)

    get = sub.add_parser("get", help="download, verify and decrypt an object")
    get.add_argument("--bucket", required=True)
    get.add_argument("--key", required=True)
    get.add_argument("--output", required=True)
    get.add_argument("--recipient-private-key", required=True)
    get.add_argument("--version", help="default: latest committed version")
    get.set_defaults(func=cmd_get)

    soak = sub.add_parser("soak", help="N consecutive encrypted round trips + audit (Phase 3)")
    soak.add_argument("--bucket", default="pqc-bench")
    soak.add_argument("--runs", type=int, default=100)
    soak.add_argument("--sizes", default="0,1,1048576,4194303,4194304,4194305,9437184",
                      help="comma-separated plaintext sizes, cycled")
    soak.add_argument("--chunk-size", type=int, default=4 * 1024 * 1024)
    soak.add_argument("--keep", action="store_true", help="keep the objects afterwards")
    soak.set_defaults(func=cmd_soak)

    gc = sub.add_parser("gc", help="report and remove uncommitted (orphaned) data objects")
    gc.add_argument("--bucket", default="pqc-bench")
    gc.add_argument("--prefix", default="")
    gc.add_argument("--older-than-minutes", type=int, default=60)
    gc.add_argument("--dry-run", action="store_true")
    gc.set_defaults(func=cmd_gc)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
