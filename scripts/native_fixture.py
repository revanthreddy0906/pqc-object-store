"""Key material and objects for the native (Go) reader, written by the Python client.

    native_fixture.py --vectors native/testdata/vectors.json      offline test vectors
    native_fixture.py --objects fixture.json --count 32 --size 65536
                                                                   objects in the store

The ML-KEM-768 key is generated from a 64-byte seed and the X-Wing key from its 32-byte seed,
so that Go's crypto/mlkem, which takes seeds only, holds the same keys. Seeds and the X25519
private key are written to the output file: these are benchmark keys, never real ones.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import x25519

from pqcstore.crypto import xwing
from pqcstore.crypto.envelope import encrypt_bytes
from pqcstore.crypto.manifest import ObjectIdentity, new_version
from pqcstore.crypto.modes import RecipientPrivate, RecipientPublic
from pqcstore.crypto.oqs_runtime import KEM_NAME, oqs

MODES = ("B2", "P1", "P3")


def recipient() -> tuple[RecipientPublic, RecipientPrivate, dict[str, str]]:
    x_sk, mlkem_seed, xwing_seed = os.urandom(32), os.urandom(64), os.urandom(32)
    with oqs().KeyEncapsulation(KEM_NAME) as kem:
        mlkem_pk = kem.generate_keypair_seed(mlkem_seed)
        mlkem_sk = kem.export_secret_key()
    xwing_pk, _ = xwing.generate_keypair(xwing_seed)
    x_pk = x25519.X25519PrivateKey.from_private_bytes(x_sk).public_key().public_bytes_raw()
    public = RecipientPublic(mlkem=mlkem_pk, x25519=x_pk, xwing=xwing_pk)
    private = RecipientPrivate(mlkem=mlkem_sk, x25519=x_sk, xwing=xwing_seed)
    return public, private, {"x25519_sk": x_sk.hex(), "mlkem_seed": mlkem_seed.hex(),
                             "xwing_seed": xwing_seed.hex()}


def vectors(path: Path) -> None:
    public, _, keys = recipient()
    out = []
    for mode in MODES:
        for size, chunk in ((0, 1024), (5, 1024), (3000, 1024), (65536, 4 * 1024 * 1024)):
            plaintext = os.urandom(size)
            identity = ObjectIdentity("research", "pqc-bench", f"vec-{mode}-{size}", new_version())
            manifest, stored = encrypt_bytes(public, identity, plaintext, chunk, mode, None)
            out.append({"mode": mode, "size": size, "manifest": manifest.hex(),
                        "ciphertext": stored.hex(),
                        "sha256": hashlib.sha256(plaintext).hexdigest()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**keys, "vectors": out}), encoding="utf-8")
    print(f"wrote {len(out)} vectors to {path}")


def objects(path: Path, count: int, size: int) -> None:
    from pqcstore.benchmark.payload import PayloadPool
    from pqcstore.settings import Settings
    from pqcstore.storage.encrypted_store import DATA, MANIFEST, EncryptedObjectStore, version_prefix
    from pqcstore.storage.minio_store import MinioStore

    settings = Settings.from_env()
    store = MinioStore(settings)
    store.ensure_bucket(settings.bucket)
    estore = EncryptedObjectStore(store)
    public, _, keys = recipient()
    pool = PayloadPool(size + 1)
    listing = {}
    for mode in MODES:
        entries = []
        for i in range(count):
            result = estore.put(settings.bucket, f"native/{mode}/get-{i}",
                                pool.reader(size, i * 7919), size, public, 4 * 1024 * 1024, mode)
            prefix = version_prefix(result.identity.object_key, result.identity.object_version)
            entries.append({"manifest": prefix + MANIFEST, "data": prefix + DATA})
        listing[mode] = entries
    path.write_text(json.dumps({**keys, "endpoint": settings.s3_endpoint, "bucket": settings.bucket,
                                "size": size, "objects": listing}), encoding="utf-8")
    os.chmod(path, 0o600)
    print(f"wrote {count} objects per mode ({size} bytes) and {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--objects", type=Path)
    parser.add_argument("--count", type=int, default=32)
    parser.add_argument("--size", type=int, default=65536)
    args = parser.parse_args()
    if args.vectors:
        vectors(args.vectors)
    if args.objects:
        objects(args.objects, args.count, args.size)


if __name__ == "__main__":
    main()
