"""Thin S3 adapter over the MinIO Python SDK.

Only raw byte transport lives here; encryption, manifests and the commit
protocol are layered on top so every benchmark mode shares one storage path.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import BinaryIO

from minio import Minio

from pqcstore.settings import Settings

# S3 requires multipart parts of at least 5 MiB; 8 MiB is the SoT default (§9.4).
DEFAULT_PART_SIZE = 8 * 1024 * 1024
READ_SIZE = 1024 * 1024


class MinioStore:
    def __init__(self, settings: Settings) -> None:
        self.client = Minio(
            settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=settings.s3_secure,
        )

    def ensure_bucket(self, bucket: str) -> None:
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    def put_bytes(self, bucket: str, key: str, data: bytes,
                  content_type: str = "application/octet-stream") -> None:
        self.client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)

    def put_stream(self, bucket: str, key: str, stream: BinaryIO, length: int = -1,
                   part_size: int = DEFAULT_PART_SIZE,
                   content_type: str = "application/octet-stream") -> None:
        """Upload from a file-like object; unknown length (-1) uses multipart upload."""
        self.client.put_object(bucket, key, stream, length, part_size=part_size,
                               content_type=content_type)

    def get_bytes(self, bucket: str, key: str) -> bytes:
        response = self.client.get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def iter_object(self, bucket: str, key: str, read_size: int = READ_SIZE) -> Iterator[bytes]:
        response = self.client.get_object(bucket, key)
        try:
            yield from response.stream(read_size)
        finally:
            response.close()
            response.release_conn()

    def delete(self, bucket: str, key: str) -> None:
        self.client.remove_object(bucket, key)

    def delete_prefix(self, bucket: str, prefix: str) -> int:
        count = 0
        for obj in self.client.list_objects(bucket, prefix=prefix, recursive=True):
            self.client.remove_object(bucket, obj.object_name)
            count += 1
        return count

    def server_reachable(self) -> bool:
        try:
            self.client.list_buckets()
        except Exception:  # noqa: BLE001 - any failure means "not reachable" for diagnostics
            return False
        return True
