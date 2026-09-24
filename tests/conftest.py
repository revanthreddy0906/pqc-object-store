import os
import uuid

import pytest

from pqcstore.settings import Settings
from pqcstore.storage.minio_store import MinioStore


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
