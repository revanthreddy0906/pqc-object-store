import os
import uuid

import pytest

from pqcstore.crypto import mlkem
from pqcstore.crypto.manifest import ObjectIdentity, new_version
from pqcstore.settings import Settings
from pqcstore.storage.minio_store import MinioStore


@pytest.fixture(scope="session")
def recipient() -> mlkem.KEMKeyPair:
    return mlkem.generate_keypair()


@pytest.fixture(scope="session")
def other_recipient() -> mlkem.KEMKeyPair:
    return mlkem.generate_keypair()


@pytest.fixture
def identity() -> ObjectIdentity:
    return ObjectIdentity("research", "pqc-bench", "dataset/item-001", new_version())


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture(scope="session")
def store(settings: Settings) -> MinioStore:
    """A live MinIO store. Skips locally when MinIO is down; fails when PQC_REQUIRE_MINIO=1 (CI)."""
    store = MinioStore(settings)
    if not store.server_reachable():
        message = f"MinIO not reachable at {settings.s3_endpoint}; run `make services-up`"
        if os.environ.get("PQC_REQUIRE_MINIO") == "1":
            pytest.fail(message)
        pytest.skip(message)
    store.ensure_bucket(settings.bucket)
    return store


@pytest.fixture
def test_prefix(store: MinioStore, settings: Settings):
    prefix = f"tests/{uuid.uuid4()}/"
    yield prefix
    store.delete_prefix(settings.bucket, prefix)
