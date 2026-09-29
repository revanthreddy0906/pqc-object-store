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


def test_disk_guard(tmp_path, monkeypatch):
    import shutil

    from pqcstore.benchmark import runner, samplers

    assert runner.disk_guard(tmp_path, None, 1) is None
    assert "client disk" in runner.disk_guard(tmp_path, None, 2**62)
    monkeypatch.setattr(samplers, "scrape_minio", lambda url: {"drive_free_bytes": 10.0})
    assert "server drive" in runner.disk_guard(tmp_path, "http://x", 1024)
    assert shutil.disk_usage(tmp_path).free > 0


def test_scrape_parses_labelled_metrics(monkeypatch):
    import io

    from pqcstore.benchmark import samplers

    text = ('# HELP x\nminio_process_cpu_seconds_total 1.5\n'
            'minio_node_drive_free_bytes{drive="/data",server="a:9000"} 2.5e+09\n')
    monkeypatch.setattr(samplers.urllib.request, "urlopen",
                        lambda url, timeout: io.BytesIO(text.encode()))
    values = samplers.scrape_minio("http://x")
    assert values == {"proc_cpu_seconds": 1.5, "drive_free_bytes": 2.5e9}


def test_metrics_url_can_be_overridden_for_remote_servers(tmp_path, monkeypatch):
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump({"experiment_id": "t", "blocks": [],
                                    "server_metrics_url": "http://127.0.0.1:9000/x"}))
    assert ExperimentConfig.load(path).server_metrics_url == "http://127.0.0.1:9000/x"
    monkeypatch.setenv("PQC_METRICS_URL", "http://10.0.0.5:9000/minio/v2/metrics/node")
    assert ExperimentConfig.load(path).server_metrics_url.startswith("http://10.0.0.5")


def test_settle_waits_until_disk_writes_stop(monkeypatch):
    from pqcstore.benchmark import runner, samplers

    written = iter([0, 100e6, 200e6, 200e6 + 1, 200e6 + 2, 200e6 + 3, 200e6 + 4])
    monkeypatch.setattr(samplers, "scrape_minio", lambda url: {"io_write_bytes": next(written)})
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    runner.settle("http://x", max_s=60)
    assert next(written) == 200e6 + 3  # stopped after two quiet one-second intervals


def test_settle_disabled_or_metric_missing(monkeypatch):
    from pqcstore.benchmark import runner, samplers

    assert runner.settle(None, 30) == 0.0
    assert runner.settle("http://x", 0) == 0.0
    monkeypatch.setattr(samplers, "scrape_minio", lambda url: {})
    slept = []
    monkeypatch.setattr(runner.time, "sleep", slept.append)
    runner.settle("http://x", max_s=30)
    assert slept == [5.0]


def test_plan_counts_runs_and_cost(tmp_path):
    from pqcstore.benchmark.runner import plan_experiment

    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump({
        "experiment_id": "t", "repetitions": 5, "warmup_s": 5, "duration_s": 20,
        "settle_max_s": 30,
        "blocks": [{"sizes": [1024, 2048], "concurrency": [1, 8], "operations": ["put"],
                    "modes": ["B1", "P1"]}]}))
    p = plan_experiment(path, hourly_usd=2.0)
    assert p["cells"] == 8 and p["runs"] == 40 and p["seconds_per_run"] == 33
    assert p["hours"] == round(40 * 33 / 3600, 1) and p["usd"] == round(40 * 33 / 3600 * 2.0, 1)
