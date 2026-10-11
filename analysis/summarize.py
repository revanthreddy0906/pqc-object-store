"""Stream an experiment's raw records once and write one summary row per run.

Every later statistic (confidence intervals, bottlenecks, hypotheses, queueing fits,
figures) is computed from these per-run rows, so the 100M-record raw files are read
exactly once and never decompressed to disk.

    python analysis/summarize.py experiments/final-a/<stamp> [...] --out results/final
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import yaml

from pqcstore.benchmark.records import iter_lines

STAGES = ("ke_ns", "kdf_ns", "aead_ns", "ser_ns", "s3_ns")
MIB = 1024 * 1024
QUANTILES = {"p50": 0.50, "p90": 0.90, "p95": 0.95, "p99": 0.99, "p999": 0.999}


class RunAcc:
    """Measured-phase accumulator for one run; arrays are dropped once summarised."""

    def __init__(self) -> None:
        self.total = []          # service time: client-observed request latency (ms)
        self.wait = []           # open loop: time between scheduled arrival and start (ms)
        self.stage = dict.fromkeys(STAGES, 0)
        self.cpu_ns = 0
        self.first_start = 0
        self.last_end = 0
        self.bytes = 0
        self.failures = 0
        self.rotations = 0       # N1: requests that opened a new session (one ML-KEM encaps)
        self.session_reqs = 0
        self.bound_sum = 0
        # N1 exposure: objects and plaintext bytes protected by each session root, over the
        # whole run (warm-up included: a root's scope does not stop at a phase boundary).
        self.roots: dict[str, list[int]] = {}

    def protect(self, r: dict) -> None:
        root = self.roots.setdefault(r["session_id"], [0, 0])
        root[0] += 1
        root[1] += r["object_size_bytes"]

    def add(self, r: dict) -> None:
        if not r["success"]:
            self.failures += 1
            return
        self.total.append(r["total_ns"] / 1e6)
        self.wait.append(r["queue_wait_ns"] / 1e6)
        for s in STAGES:
            self.stage[s] += r[s]
        self.cpu_ns += r["cpu_thread_ns"]
        start = r["ts_start_utc_ns"]
        self.first_start = start if not self.first_start else min(self.first_start, start)
        self.last_end = max(self.last_end, start + r["total_ns"])
        self.bytes += r["object_size_bytes"]
        if r["session_id"] is not None:
            self.session_reqs += 1
            self.rotations += bool(r["session_seq"] == 0)
            self.bound_sum += r["session_bound"] or 0

    def summary(self) -> dict:
        n = len(self.total)
        if not n:
            return {"requests": 0, "failures": self.failures}
        total = np.asarray(self.total)
        wait = np.asarray(self.wait)
        sojourn = total + wait
        window = max(1e-9, (self.last_end - self.first_start) / 1e9)
        half = n // 2
        row = {"requests": n, "failures": self.failures,
               "t0_ns": self.first_start, "t1_ns": self.last_end, "window_s": window, "ops_per_s": n / window,
               "mib_per_s": self.bytes / MIB / window,
               "mean_ms": float(total.mean()),
               "cpu_ms_per_req": self.cpu_ns / n / 1e6,
               "drift": (float(np.median(total[half:]) / np.median(total[:half])) - 1
                         if half else float("nan"))}
        for name, q in QUANTILES.items():
            row[f"{name}_ms"] = float(np.quantile(total, q))
        # Open loop: response time seen by the arrival process = waiting + service.
        row["wait_mean_ms"] = float(wait.mean())
        row["wait_p99_ms"] = float(np.quantile(wait, 0.99))
        row["sojourn_mean_ms"] = float(sojourn.mean())
        row["sojourn_p50_ms"] = float(np.quantile(sojourn, 0.5))
        row["sojourn_p99_ms"] = float(np.quantile(sojourn, 0.99))
        stage_total = sum(self.stage.values())
        for s in STAGES:
            row[f"{s[:-3]}_mean_ms"] = self.stage[s] / n / 1e6
            row[f"{s[:-3]}_share"] = self.stage[s] / stage_total if stage_total else float("nan")
        row["session_requests"] = self.session_reqs
        row["kem_per_request"] = (self.rotations / self.session_reqs if self.session_reqs
                                  else float("nan"))
        row["mean_session_bound"] = (self.bound_sum / self.session_reqs if self.session_reqs
                                     else float("nan"))
        if self.roots:
            objects = np.asarray([v[0] for v in self.roots.values()])
            size = np.asarray([v[1] for v in self.roots.values()]) / MIB
            row["roots"] = len(objects)
            row["kem_per_object_observed"] = len(objects) / int(objects.sum())
            for name, values in (("root_objects", objects), ("root_mib", size)):
                row[f"{name}_median"] = float(np.median(values))
                row[f"{name}_p95"] = float(np.quantile(values, 0.95))
                row[f"{name}_max"] = float(values.max())
        return row


def scan(run_dir: Path) -> dict[str, dict]:
    """One pass over the raw records; a run's arrays are freed as soon as the next run starts."""
    done: dict[str, dict] = {}
    current, acc = None, None
    lines = 0
    for line in iter_lines(run_dir):
        lines += 1
        if lines % 10_000_000 == 0:
            print(f"  {run_dir.parent.name}: {lines:,} records", flush=True)
        measured = '"phase":"measure"' in line   # cheap filters before parsing
        in_session = '"session_id":"' in line
        if not measured and not in_session:
            continue
        r = json.loads(line)
        run_id = r["run_id"]
        if run_id != current:
            if current is not None:
                done[current] = acc.summary()
            if run_id in done:
                raise ValueError(f"{run_dir}: records of {run_id} are not contiguous")
            current, acc = run_id, RunAcc()
        if in_session and r["operation"] == "put" and r["success"]:
            acc.protect(r)
        if measured:
            acc.add(r)
    if current is not None:
        done[current] = acc.summary()
    print(f"  {run_dir.parent.name}: {lines:,} records, {len(done)} runs", flush=True)
    return done


def sampler_stats(path: Path, kind: str, windows: dict[str, tuple[int, int]]) -> dict[str, dict]:
    """Per-run sampler statistics.

    CPU and network rates cover the measured window only (warm-up and teardown dropped).
    Memory covers the whole run, because workers allocate during warm-up: the first
    sample is the footprint before any request, the peak is the run's maximum, and
    growth is their difference. In-window growth is kept separately as a leak check.
    The client RSS sums every worker process (samplers.ClientSampler)."""
    runs: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            runs[row["run_id"]].append(row)

    def col(samples, name):
        return [float(s[name]) for s in samples if s.get(name) not in (None, "")]

    out = {}
    for run_id, every in runs.items():
        t0, t1 = windows.get(run_id, (0, 0))
        window = [s for s in every if t0 <= int(s["ts_utc_ns"]) <= t1]
        cpu = col(window, "proc_cpu_pct")
        rss_all, rss_win = col(every, "proc_rss_bytes"), col(window, "proc_rss_bytes")
        stats = {f"{kind}_cpu_pct": statistics.fmean(cpu) if cpu else float("nan"),
                 f"{kind}_rss_first_mib": rss_all[0] / MIB if rss_all else float("nan"),
                 f"{kind}_rss_peak_mib": max(rss_all) / MIB if rss_all else float("nan"),
                 f"{kind}_rss_growth_mib": ((max(rss_all) - rss_all[0]) / MIB if rss_all
                                            else float("nan")),
                 f"{kind}_rss_window_drift_mib": ((rss_win[-1] - rss_win[0]) / MIB
                                                  if len(rss_win) > 1 else float("nan"))}
        if kind == "client":
            host = col(window, "host_cpu_pct")
            stats["client_host_cpu_pct"] = statistics.fmean(host) if host else float("nan")
        ts = [int(s["ts_utc_ns"]) for s in window]
        span = (ts[-1] - ts[0]) / 1e9 if len(ts) > 1 else 0.0
        for name in ("net_tx_bytes", "net_rx_bytes"):
            values = col(window, name)
            if len(values) > 1 and span > 0:
                stats[f"{kind}_{name[:-6]}_mib_s"] = (values[-1] - values[0]) / MIB / span
        if kind == "server" and span > 0:   # host kernel counters (node_exporter), if sampled
            def delta(name, samples=window):
                values = col(samples, name)
                return values[-1] - values[0] if len(values) > 1 else float("nan")

            dirty, writeback = col(window, "dirty_bytes"), col(window, "writeback_bytes")
            if dirty:
                writes = delta("disk_writes")
                stats.update({
                    "host_dirty_mean_mib": statistics.fmean(dirty) / MIB,
                    "host_dirty_max_mib": max(dirty) / MIB,
                    "host_writeback_max_mib": max(writeback) / MIB if writeback else float("nan"),
                    "host_disk_write_mib_s": delta("disk_written_bytes") / MIB / span,
                    "host_disk_writes_s": writes / span,
                    "host_disk_write_latency_ms": (delta("disk_write_time_s") / writes * 1000
                                                   if writes > 0 else float("nan")),
                    "host_disk_busy": delta("disk_io_time_s") / span,
                    "host_io_pressure": delta("io_pressure_s") / span,
                    "host_iowait_cores": delta("cpu_iowait_s") / span,
                })
        out[run_id] = stats
    return out


def summarize(run_dir: Path) -> list[dict]:
    manifest = yaml.safe_load((run_dir / "run-manifest.yaml").read_text())
    records = scan(run_dir)
    windows = {run_id: (r["t0_ns"], r["t1_ns"]) for run_id, r in records.items() if r["requests"]}
    client = sampler_stats(run_dir / "client-samples.csv", "client", windows)
    server = sampler_stats(run_dir / "server-samples.csv", "server", windows)
    rows = []
    previous, position = None, {}
    for index, run in enumerate(manifest["runs"]):
        cell, run_id = run["cell"], run["run_id"]
        group = run_id[:10]                       # repetition + block
        position[group] = position.get(group, -1) + 1
        order = {"run_index": index, "position_in_block": position[group],
                 "previous_operation": previous["cell"]["operation"] if previous else "",
                 "previous_mode": previous["cell"]["mode"] if previous else "",
                 "started_unix": run.get("started_unix", float("nan")),
                 "settle_s": run.get("settle_s", float("nan"))}
        previous = run
        processes = max(1, min(cell["concurrency"] or 0, manifest["environment"]["logical_cores"]))
        row = {"experiment": manifest["experiment_id"], "run_id": run_id,
               "repetition": int(run_id[3:5]), "block": run_id.split("-")[1],
               "mode": cell["mode"], "operation": cell["operation"], "size": cell["size"],
               "loop": cell["loop"], "concurrency": cell["concurrency"], "rate": cell["rate"],
               "session_bmax": cell["session_bmax"], "queue_aware": cell["queue_aware"],
               "session_tmax_s": cell.get("session_tmax_s", 0.0),
               "valid": run["valid"], "client_bound": run.get("client_bound", False),
               "worker_processes": processes, **order,
               **records.get(run_id, {"requests": 0}),
               **client.get(run_id, {}), **server.get(run_id, {})}
        if row.get("client_cpu_pct") == row.get("client_cpu_pct") and "client_cpu_pct" in row:
            row["client_cpu_per_process_pct"] = row["client_cpu_pct"] / processes
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("experiments", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, default=Path("results/final"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=len(args.experiments)) as pool:
        results = list(pool.map(summarize, args.experiments))
    rows = [row for result in results for row in result]
    fields = list(dict.fromkeys(key for row in rows for key in row))
    path = args.out / "runs.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    sources = {str(d): (d / "checksums.sha256").read_text() for d in args.experiments}
    (args.out / "sources.json").write_text(json.dumps(sources, indent=1))
    print(f"wrote {path} ({len(rows)} runs)")


if __name__ == "__main__":
    main()
