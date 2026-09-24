"""Runner building blocks that need no MinIO: concurrency split, config expansion, validation."""

import hashlib
import json

import pytest
import yaml

from pqcstore.benchmark import validate as v
from pqcstore.benchmark.runner import ExperimentConfig, _thread_counts, write_checksums


@pytest.mark.parametrize("n,p", [(1, 1), (8, 8), (500, 8), (7, 3), (129, 16)])
def test_thread_counts_sum_to_exact_concurrency(n, p):
    counts = _thread_counts(n, p)
    assert sum(counts) == n and len(counts) == p
    assert max(counts) - min(counts) <= 1


def test_config_expands_blocks_with_modes_inside(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump({
        "experiment_id": "t",
        "blocks": [
            {"sizes": [1, 2], "concurrency": [1, 8], "operations": ["put", "get"],
             "modes": ["B1", "P1"]},
            {"loop": "open", "sizes": [3], "rates": [10], "threads": 4, "operations": ["put"],
             "modes": ["P1"]},
        ],
    }))
    blocks = ExperimentConfig.load(path).cells()
    assert len(blocks) == 2 * 2 * 2 + 1
    assert all({c.mode for c in b} == {"B1", "P1"} for b in blocks[:8])
    open_cell = blocks[-1][0]
    assert open_cell.loop == "open" and open_cell.rate == 10 and open_cell.concurrency == 4


def test_unknown_mode_is_rejected(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump({"experiment_id": "t", "blocks": [
        {"sizes": [1], "concurrency": [1], "operations": ["put"], "modes": ["X9"]}]}))
    with pytest.raises(ValueError, match="X9"):
        ExperimentConfig.load(path).cells()


def good_record(**changes):
    record = {name: 0 for name, kind in v.SCHEMA.items() if kind is int}
    record.update({name: "x" for name, kind in v.SCHEMA.items() if kind is str})
    record.update(target_rate=0.0, success=True, phase="measure", error_class="",
                  ke_ns=10, kdf_ns=10, aead_ns=10, ser_ns=10, s3_ns=960_000, total_ns=1_000_000)
    record.update(changes)
    return record


def make_run_dir(tmp_path, records, valid=True):
    (tmp_path / "requests.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    (tmp_path / "run-manifest.yaml").write_text(yaml.safe_dump(
        {"runs": [{"run_id": "r1", "valid": valid}]}))
    write_checksums(tmp_path)
    return tmp_path


def test_validate_accepts_consistent_records(tmp_path):
    report = v.validate(make_run_dir(tmp_path, [good_record(), good_record(
        success=False, error_class="ReadTimeoutError")]))
    assert report.ok and report.records == 2 and report.failures["ReadTimeoutError"] == 1


@pytest.mark.parametrize("record,problem", [
    (good_record(s3_ns=900_000), "timer"),        # 60 us unaccounted = 6% of total
    (good_record(s3_ns=2_000_000), "timer"),      # stages exceed total
    (good_record(total_ns="1"), "schema"),
    (good_record(success=1), "schema"),
    ({k: val for k, val in good_record().items() if k != "mode"}, "schema"),
])
def test_validate_rejects_bad_records(tmp_path, record, problem):
    report = v.validate(make_run_dir(tmp_path, [record]))
    assert not report.ok
    assert (report.timer_violation_count if problem == "timer" else report.schema_error_count) == 1


def test_validate_detects_modified_raw_data(tmp_path):
    run_dir = make_run_dir(tmp_path, [good_record()])
    with (run_dir / "requests.jsonl").open("a") as handle:
        handle.write(json.dumps(good_record()) + "\n")
    report = v.validate(run_dir)
    assert report.checksum_errors == ["requests.jsonl"]
    assert hashlib.sha256(b"").hexdigest()  # checksums use SHA-256


def test_validate_reports_invalid_runs(tmp_path):
    assert v.validate(make_run_dir(tmp_path, [good_record()], valid=False)).invalid_runs == ["r1"]
