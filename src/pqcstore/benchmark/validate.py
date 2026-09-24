"""Validate an experiment directory before any analysis (SoT §12.1, Phase 5 exit check).

Checks: checksums match; every run in the manifest is valid; every request
record has the full schema with the right types; and the stage timers add up.
For timers, T_other = total - sum(stages) must never be negative (that would
mean double counting), and per run the p99 of T_other/total must stay below 2%
and the aggregate unaccounted time below 1%. Individual requests above 2% are
counted as outliers: a thread descheduled by the OS between two timers is
scheduling noise, not a missing stage.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SCHEMA: dict[str, type | tuple[type, ...]] = {
    "experiment_id": str, "run_id": str, "block_id": str, "repetition": int, "request_id": str,
    "worker_id": int, "thread_id": int, "pid": int, "ts_start_utc_ns": int, "git_commit": str,
    "config_hash": str, "machine_id": str, "mode": str, "operation": str,
    "object_size_bytes": int, "concurrency": int, "loop_type": str,
    "target_rate": (int, float), "queue_wait_ns": int, "phase": str, "chunk_size": int,
    "ke_ns": int, "kdf_ns": int, "aead_ns": int, "ser_ns": int, "s3_ns": int, "total_ns": int,
    "cpu_thread_ns": int, "bytes_sent": int, "bytes_received": int, "metadata_bytes": int,
    "success": bool, "error_class": str,
}
STAGES = ("ke_ns", "kdf_ns", "aead_ns", "ser_ns", "s3_ns")
RUN_P99_LIMIT = 0.02
RUN_AGGREGATE_LIMIT = 0.01
OTHER_FLOOR_NS = 50_000  # below this, timer overhead dominates tiny requests


@dataclass
class Report:
    records: int = 0
    measured: int = 0
    failures: Counter = field(default_factory=Counter)
    schema_errors: list[str] = field(default_factory=list)
    timer_violations: list[str] = field(default_factory=list)  # failing runs / negative gaps
    timer_violation_count: int = 0
    outlier_requests: int = 0
    schema_error_count: int = 0
    checksum_errors: list[str] = field(default_factory=list)
    invalid_runs: list[str] = field(default_factory=list)
    max_other_fraction: float = 0.0

    @property
    def ok(self) -> bool:
        return not (self.schema_errors or self.timer_violations or self.checksum_errors
                    or self.invalid_runs) and self.records > 0


def validate(run_dir: Path) -> Report:
    report = Report()
    for line in (run_dir / "checksums.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if hashlib.sha256((run_dir / name).read_bytes()).hexdigest() != digest:
            report.checksum_errors.append(name)
    manifest = yaml.safe_load((run_dir / "run-manifest.yaml").read_text())
    report.invalid_runs = [run["run_id"] for run in manifest["runs"] if not run["valid"]]

    per_run: dict[str, list[tuple[float, int, int]]] = defaultdict(list)
    with (run_dir / "requests.jsonl").open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            record = json.loads(line)
            report.records += 1
            problems = [name for name, kind in SCHEMA.items()
                        if name not in record or not isinstance(record[name], kind)
                        or (kind is int and isinstance(record[name], bool))]
            if problems:
                report.schema_error_count += 1
                if len(report.schema_errors) < 20:
                    report.schema_errors.append(f"line {number}: bad or missing {problems}")
                continue
            if not record["success"]:
                report.failures[record["error_class"]] += 1
                continue
            report.measured += record["phase"] == "measure"
            total = record["total_ns"]
            other = total - sum(record[s] for s in STAGES)
            if other < 0:
                report.timer_violation_count += 1
                if len(report.timer_violations) < 20:
                    report.timer_violations.append(
                        f"line {number} ({record['run_id']}): stages exceed total by {-other} ns")
                continue
            excess = max(0, other - OTHER_FLOOR_NS)
            fraction = excess / total if total else 0.0
            report.outlier_requests += fraction > RUN_P99_LIMIT
            per_run[record["run_id"]].append((fraction, excess, total))

    for run_id, rows in sorted(per_run.items()):
        fractions = sorted(f for f, _, _ in rows)
        p99 = fractions[min(len(fractions) - 1, int(0.99 * len(fractions)))]
        aggregate = sum(e for _, e, _ in rows) / max(1, sum(t for _, _, t in rows))
        report.max_other_fraction = max(report.max_other_fraction, p99)
        if p99 > RUN_P99_LIMIT or aggregate > RUN_AGGREGATE_LIMIT:
            report.timer_violation_count += 1
            report.timer_violations.append(
                f"{run_id}: p99 unaccounted {p99:.2%}, aggregate {aggregate:.2%}")
    return report
