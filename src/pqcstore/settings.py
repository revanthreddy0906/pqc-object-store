"""Runtime settings from environment variables, with an optional .env file.

Values already present in the environment take precedence over .env, so CI and
experiment scripts can override anything without editing files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass(frozen=True)
class Settings:
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_secure: bool
    bucket: str

    @classmethod
    def from_env(cls, dotenv: Path | None = Path(".env")) -> Settings:
        if dotenv is not None:
            load_dotenv(dotenv)
        try:
            return cls(
                s3_endpoint=os.environ.get("PQC_S3_ENDPOINT", "127.0.0.1:9000"),
                s3_access_key=os.environ["MINIO_ROOT_USER"],
                s3_secret_key=os.environ["MINIO_ROOT_PASSWORD"],
                s3_secure=os.environ.get("PQC_S3_SECURE", "false").lower() == "true",
                bucket=os.environ.get("PQC_BUCKET", "pqc-bench"),
            )
        except KeyError as missing:
            raise RuntimeError(
                f"{missing.args[0]} is not set; copy .env.example to .env"
            ) from None
