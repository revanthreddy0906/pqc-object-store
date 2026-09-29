"""The whole pipeline (config -> worker processes -> records -> samplers -> validation) on MinIO."""


import pytest
import yaml

from pqcstore.benchmark.records import iter_records
from pqcstore.benchmark.runner import run_experiment
from pqcstore.benchmark.validate import validate

pytestmark = pytest.mark.integration


def test_tiny_experiment_end_to_end(store, settings, tmp_path):
    config = tmp_path / "tiny.yaml"
    config.write_text(yaml.safe_dump({
        "experiment_id": "tiny", "bucket": settings.bucket, "repetitions": 1,
        "warmup_s": 0.3, "duration_s": 0.7, "get_objects": 2, "pool_bytes": 1 << 20,
        "blocks": [
            {"sizes": [2048], "concurrency": [3], "operations": ["put", "get"],
             "modes": ["B0", "R1", "P1"]},
            {"loop": "open", "sizes": [1024], "rates": [40], "threads": 4,
             "operations": ["put"], "modes": ["P2"]},
            {"sizes": [1024], "concurrency": [4], "operations": ["put", "get"],
             "modes": ["N1"], "session_bmax": [1, 5], "queue_aware": [False, True],
             "session_tmax_s": 30},
        ],
    }))
    run_dir, outcomes = run_experiment(config, tmp_path / "out", progress=lambda _: None)

    assert len(outcomes) == 7 + 8 and all(o.valid for o in outcomes)
    report = validate(run_dir)
    assert report.records > 0 and report.schema_error_count == 0
    assert not report.checksum_errors and not report.invalid_runs
    assert not report.failures
    assert not any("exceed" in v for v in report.timer_violations)  # no double counting
    assert report.sessions_checked > 0 and not report.session_violations

    records = list(iter_records(run_dir))  # raw records are zstd-compressed at the end
    closed = [r for r in records if r["loop_type"] == "closed" and r["mode"] != "N1"]
    assert {r["mode"] for r in closed} == {"B0", "R1", "P1"}
    n1_puts = [r for r in records if r["mode"] == "N1" and r["operation"] == "put"
               and r["success"]]
    assert {r["session_bmax"] for r in n1_puts} == {1, 5}
    assert all(r["session_seq"] == 0 for r in n1_puts if r["session_bmax"] == 1)
    assert any(r["session_seq"] > 0 for r in n1_puts if r["session_bmax"] == 5)
    assert {r["concurrency"] for r in closed} == {3}
    assert {r["phase"] for r in closed} == {"warmup", "measure"}
    opened = [r for r in records if r["loop_type"] == "open"]
    assert opened and all(r["queue_wait_ns"] >= 0 for r in opened)

    manifest = yaml.safe_load((run_dir / "run-manifest.yaml").read_text())
    assert manifest["environment"]["liboqs_version"] == "0.16.0"
    assert (run_dir / "client-samples.csv").read_text().count("\n") > 1
    assert "scrape_ok" in (run_dir / "server-samples.csv").read_text()
    # Workers delete their PUT objects and the runner deletes GET fixtures.
    from pqcstore.storage.encrypted_store import EncryptedObjectStore
    assert EncryptedObjectStore(store).audit(settings.bucket, "bench/tiny/").committed == []


def test_a_failing_run_is_recorded_and_the_experiment_continues(store, settings, tmp_path,
                                                                monkeypatch):
    from pqcstore.benchmark import runner

    def broken(*args, **kwargs):
        raise ConnectionError("simulated storage failure during setup")

    monkeypatch.setattr(runner, "prepare_get_objects", broken)
    config = tmp_path / "c.yaml"
    config.write_text(yaml.safe_dump({
        "experiment_id": "broken", "bucket": settings.bucket, "warmup_s": 0.2, "duration_s": 0.4,
        "pool_bytes": 1 << 20,
        "blocks": [{"sizes": [1024], "concurrency": [1], "operations": ["get", "put"],
                    "modes": ["B1"]}],
    }))
    run_dir, outcomes = run_experiment(config, tmp_path / "out", progress=lambda _: None)
    by_op = {o.run_id.split("-")[3]: o for o in outcomes}
    assert not by_op["get"].valid and "ConnectionError" in by_op["get"].note
    assert by_op["put"].valid and by_op["put"].records > 0
    manifest = yaml.safe_load((run_dir / "run-manifest.yaml").read_text())
    assert len(manifest["runs"]) == 2 and "finished_utc" in manifest
