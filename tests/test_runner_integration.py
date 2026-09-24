"""The whole pipeline (config -> worker processes -> records -> samplers -> validation) on MinIO."""

import json

import pytest
import yaml

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
        ],
    }))
    run_dir, outcomes = run_experiment(config, tmp_path / "out", progress=lambda _: None)

    assert len(outcomes) == 7 and all(o.valid for o in outcomes)
    report = validate(run_dir)
    assert report.records > 0 and report.schema_error_count == 0
    assert not report.checksum_errors and not report.invalid_runs
    assert not report.failures
    assert not any("exceed" in v for v in report.timer_violations)  # no double counting

    records = [json.loads(line) for line in (run_dir / "requests.jsonl").open()]
    closed = [r for r in records if r["loop_type"] == "closed"]
    assert {r["mode"] for r in closed} == {"B0", "R1", "P1"}
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
