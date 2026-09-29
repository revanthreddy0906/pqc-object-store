"""Streaming helpers for large experiment files."""

import hashlib
import json

import pytest

from pqcstore.benchmark import records


def write_raw(run_dir, rows):
    (run_dir / records.RAW).write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_sha256_file_streams(tmp_path):
    path = tmp_path / "big.bin"
    data = b"x" * (3 * records.BLOCK + 5)
    path.write_bytes(data)
    assert records.sha256_file(path) == hashlib.sha256(data).hexdigest()


def test_compress_then_read_back_identically(tmp_path):
    rows = [{"i": i, "text": "abc" * 20} for i in range(5000)]
    write_raw(tmp_path, rows)
    plain = list(records.iter_records(tmp_path))
    target = records.compress_raw(tmp_path)
    assert target.name == records.RAW_ZST and not (tmp_path / records.RAW).exists()
    assert target.stat().st_size < 0.2 * len(json.dumps(rows))
    assert list(records.iter_records(tmp_path)) == plain == rows


def test_missing_raw_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        records.raw_path(tmp_path)
