"""Streaming access to experiment files, which can be tens of GB (the pilot wrote 31 GB).

Nothing here loads a whole file into memory. Raw request records live in
requests.jsonl while an experiment runs and are compressed to requests.jsonl.zst
at the end; readers accept either.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterator
from pathlib import Path

import zstandard

RAW = "requests.jsonl"
RAW_ZST = "requests.jsonl.zst"
BLOCK = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(BLOCK):
            digest.update(block)
    return digest.hexdigest()


def raw_path(run_dir: Path) -> Path:
    for name in (RAW_ZST, RAW):
        if (run_dir / name).exists():
            return run_dir / name
    raise FileNotFoundError(f"no {RAW} or {RAW_ZST} in {run_dir}")


def iter_lines(run_dir: Path) -> Iterator[str]:
    path = raw_path(run_dir)
    if path.suffix == ".zst":
        with path.open("rb") as compressed:
            reader = zstandard.ZstdDecompressor().stream_reader(compressed)
            yield from io.TextIOWrapper(reader, encoding="utf-8")
    else:
        with path.open(encoding="utf-8") as handle:
            yield from handle


def iter_records(run_dir: Path) -> Iterator[dict]:
    for line in iter_lines(run_dir):
        yield json.loads(line)


def compress_raw(run_dir: Path, level: int = 3) -> Path:
    """Compress requests.jsonl to requests.jsonl.zst (verified), then remove the original."""
    source, target = run_dir / RAW, run_dir / RAW_ZST
    compressor = zstandard.ZstdCompressor(level=level, threads=-1)
    with source.open("rb") as plain, target.open("wb") as out:
        compressor.copy_stream(plain, out)
    # Verify by decompressing and comparing digests before deleting anything.
    plain_digest, check = hashlib.sha256(), hashlib.sha256()
    with source.open("rb") as plain:
        while block := plain.read(BLOCK):
            plain_digest.update(block)
    with target.open("rb") as compressed:
        reader = zstandard.ZstdDecompressor().stream_reader(compressed)
        while block := reader.read(BLOCK):
            check.update(block)
    if plain_digest.digest() != check.digest():
        target.unlink()
        raise OSError(f"compression check failed for {source}; original kept")
    source.unlink()
    return target
