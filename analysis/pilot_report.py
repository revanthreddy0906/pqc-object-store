"""Pilot analysis (SoT §15.1, Phase 6): noise, bottlenecks and a first look at the hypotheses.

One streaming pass over the raw records (tens of millions of lines) produces per-run
statistics; the repetitions of each cell are then compared. Output, in --out:

    runs.csv     one row per run (the unit of replication)
    cells.csv    one row per cell: medians across repetitions, CVs, bottleneck
    report.md    the answers to the pilot's questions and the recommendations for Phase 8

Pilot values are never reported as results (SoT D13 / §15.1); they size the final study.

    python analysis/pilot_report.py --experiment experiments/pilot/<stamp> \
        --baselines experiments/baselines --out results/pilot
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from array import array
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pqcstore.benchmark.records import iter_lines

STAGES = ("ke_ns", "kdf_ns", "aead_ns", "ser_ns", "s3_ns")
MIB = 1024 * 1024
CV_LIMIT = 0.05            # SoT §9.3: more than 5% run-to-run CV -> 10 repetitions
CLIENT_BOUND_PCT = 85.0    # host CPU on the client
SERVER_BOUND_FRACTION = 0.85


@dataclass
class RunAcc:
    totals: array = field(default_factory=lambda: array("d"))
    stage_sums: dict = field(default_factory=lambda: dict.fromkeys(STAGES, 0))
    cpu_ns: int = 0
    first_start: int = 0
    last_end: int = 0
    bytes_moved: int = 0
    failures: int = 0


def quantile(sorted_values, q: float) -> float:
    return sorted_values[min(len(sorted_values) - 1, int(q * (len(sorted_values) - 1) + 0.5))]


def cv(values: list[float]) -> float:
    return statistics.stdev(values) / statistics.fmean(values) if len(values) > 1 and \
        statistics.fmean(values) else float("nan")


def load_samples(path: Path, fields: list[str]) -> dict[str, dict[str, float]]:
    """Per-run means of sampler columns (the first second of each run is warm-up noise)."""
    sums: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in csv.DictReader(path.open(encoding="utf-8")):
        for name in fields:
            if row.get(name):
                sums[row["run_id"]][name].append(float(row[name]))
    return {run: {k: statistics.fmean(v) for k, v in cols.items()} for run, cols in sums.items()}


def scan(run_dir: Path) -> tuple[dict[str, RunAcc], int]:
    runs: dict[str, RunAcc] = defaultdict(RunAcc)
    lines = 0
    for line in iter_lines(run_dir):
        lines += 1
        if '"phase":"measure"' not in line:  # cheap filter before parsing
            continue
        r = json.loads(line)
        acc = runs[r["run_id"]]
        if not r["success"]:
            acc.failures += 1
            continue
        acc.totals.append(r["total_ns"] / 1e6)
        for s in STAGES:
            acc.stage_sums[s] += r[s]
        acc.cpu_ns += r["cpu_thread_ns"]
        start, end = r["ts_start_utc_ns"], r["ts_start_utc_ns"] + r["total_ns"]
        acc.first_start = start if not acc.first_start else min(acc.first_start, start)
        acc.last_end = max(acc.last_end, end)
        acc.bytes_moved += r["object_size_bytes"]
        if lines % 5_000_000 == 0:
            print(f"  ... {lines:,} records scanned", flush=True)
    return runs, lines


def run_rows(run_dir: Path) -> list[dict]:
    manifest = yaml.safe_load((run_dir / "run-manifest.yaml").read_text())
    client = load_samples(run_dir / "client-samples.csv",
                          ["proc_cpu_pct", "host_cpu_pct", "proc_rss_bytes", "net_tx_bytes",
                           "net_rx_bytes"])
    server = load_samples(run_dir / "server-samples.csv", ["proc_cpu_pct", "proc_rss_bytes"])
    print(f"scanning {run_dir} ...", flush=True)
    accs, lines = scan(run_dir)
    print(f"  {lines:,} records", flush=True)
    rows = []
    for run in manifest["runs"]:
        acc, cell = accs.get(run["run_id"]), run["cell"]
        if acc is None or not acc.totals:
            continue
        totals = sorted(acc.totals)
        n = len(totals)
        window = max(1e-9, (acc.last_end - acc.first_start) / 1e9)
        # Drift check: does the median of the second half of the run differ from the first?
        half = n // 2
        first_half = statistics.median(acc.totals[:half]) if half else float("nan")
        second_half = statistics.median(acc.totals[half:]) if half else float("nan")
        total_ns = sum(acc.stage_sums.values())
        rows.append({
            "run_id": run["run_id"], "repetition": int(run["run_id"][3:5]),
            "mode": cell["mode"], "operation": cell["operation"], "size": cell["size"],
            "concurrency": cell["concurrency"], "requests": n, "failures": acc.failures,
            "median_ms": statistics.median(totals), "p95_ms": quantile(totals, 0.95),
            "p99_ms": quantile(totals, 0.99), "ops_per_s": n / window,
            "mib_per_s": acc.bytes_moved / MIB / window,
            "cpu_ms_per_req": acc.cpu_ns / n / 1e6,
            "ke_share": acc.stage_sums["ke_ns"] / total_ns if total_ns else float("nan"),
            "s3_share": acc.stage_sums["s3_ns"] / total_ns if total_ns else float("nan"),
            "drift": second_half / first_half - 1 if first_half else float("nan"),
            "client_host_cpu": client.get(run["run_id"], {}).get("host_cpu_pct", float("nan")),
            "client_proc_cpu": client.get(run["run_id"], {}).get("proc_cpu_pct", float("nan")),
            "server_cpu": server.get(run["run_id"], {}).get("proc_cpu_pct", float("nan")),
            "client_bound": run.get("client_bound", False),
        })
    return rows


def cell_rows(runs: list[dict], server_cores: int, link_mib_s: float, disk_mib_s: float,
              disk_iops: float) -> list[dict]:
    by_cell = defaultdict(list)
    for r in runs:
        by_cell[(r["mode"], r["operation"], r["size"], r["concurrency"])].append(r)
    cells = []
    for (mode, op, size, conc), reps in sorted(by_cell.items()):
        medians = [r["median_ms"] for r in reps]
        tput = [r["ops_per_s"] for r in reps]
        mib = statistics.median(r["mib_per_s"] for r in reps)
        host = statistics.median(r["client_host_cpu"] for r in reps)
        server = statistics.median(r["server_cpu"] for r in reps)
        # PUT writes the object and its manifest: ~2 disk writes per request.
        write_iops = 2 * statistics.median(tput) if op == "put" else 0.0
        if host >= CLIENT_BOUND_PCT:
            limit = "client CPU"
        elif op == "put" and mib >= 0.9 * disk_mib_s:
            limit = "disk throughput (EBS cap)"
        elif op == "put" and write_iops >= 0.75 * disk_iops:
            limit = "disk IOPS (EBS cap)"
        elif server >= SERVER_BOUND_FRACTION * 100 * server_cores:
            limit = "server CPU"
        elif mib >= 0.8 * link_mib_s:
            limit = "network"
        else:
            limit = "latency (not saturated)"
        cells.append({
            "mode": mode, "operation": op, "size": size, "concurrency": conc, "reps": len(reps),
            "median_ms": statistics.median(medians), "median_cv": cv(medians),
            "p99_ms": statistics.median(r["p99_ms"] for r in reps),
            "ops_per_s": statistics.median(tput), "throughput_cv": cv(tput), "mib_per_s": mib,
            "cpu_ms_per_req": statistics.median(r["cpu_ms_per_req"] for r in reps),
            "ke_share": statistics.median(r["ke_share"] for r in reps),
            "client_host_cpu": host, "server_cpu": server,
            "max_abs_drift": max(abs(r["drift"]) for r in reps), "limit": limit,
            "failures": sum(r["failures"] for r in reps),
        })
    return cells


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def size_label(size: int) -> str:
    return f"{size // MIB} MiB" if size >= MIB else f"{size // 1024} KiB"


def report(cells: list[dict], runs: list[dict], baselines: dict, out: Path, source: Path) -> str:
    noisy = [c for c in cells if c["median_cv"] > CV_LIMIT or c["throughput_cv"] > CV_LIMIT]
    worst = sorted(cells, key=lambda c: -max(c["median_cv"], c["throughput_cv"]))[:8]
    # Latency drift inside a run is expected when a shared resource (link, disk) is saturated.
    drifting = [c for c in cells if c["max_abs_drift"] > 0.10 and "latency" in c["limit"]]
    limits = defaultdict(int)
    for c in cells:
        limits[c["limit"]] += 1

    def cell(mode, op, size, conc):
        return next((c for c in cells if (c["mode"], c["operation"], c["size"],
                                          c["concurrency"]) == (mode, op, size, conc)), None)

    lines = [
        "# Pilot report (Phase 6)", "",
        (f"Source: `{source}`. Pilot values size the final study; they are **not results** "
        "(SoT §15.1)."), "",
        "## Data", "",
        (f"- Runs: {len(runs)} valid runs in {len(cells)} cells "
        f"({min(c['reps'] for c in cells)}–{max(c['reps'] for c in cells)} repetitions each)"),
        (f"- Measured successful requests: {sum(r['requests'] for r in runs):,}; failed: "
        f"{sum(r['failures'] for r in runs):,}"),
        (f"- Testbed baselines: network {baselines['net_gbit']:.1f} Gbit/s, RTT "
        f"{baselines['rtt_ms']:.3f} ms, disk read {baselines['disk_read']:.0f} / write "
        f"{baselines['disk_write']:.0f} MiB/s (fio, 70/30 random 1 MiB)"), "",
        "## Q1. How noisy are the measurements?", "",
        (f"Run-to-run coefficient of variation (CV) of each cell's median latency and throughput "
        f"across its repetitions. SoT rule: CV > {CV_LIMIT:.0%} means 10 repetitions instead of 5."),
        "",
        f"- Cells above {CV_LIMIT:.0%}: **{len(noisy)} of {len(cells)}**",
        (f"- Median CV across cells: latency "
        f"{statistics.median(c['median_cv'] for c in cells):.1%}, throughput "
        f"{statistics.median(c['throughput_cv'] for c in cells):.1%}"), "",
        "Noisiest cells:", "",
        "| Mode | Op | Size | Workers | Latency CV | Throughput CV |",
        "|---|---|---|---|---|---|",
        *[f"| {c['mode']} | {c['operation'].upper()} | {size_label(c['size'])} | "
          f"{c['concurrency']} | {c['median_cv']:.1%} | {c['throughput_cv']:.1%} |" for c in worst],
        "",
        "## Q2. What limits throughput?", "",
        ("Per cell, from the samplers: client host CPU ≥ 85% → client CPU; PUT MiB/s ≥ 90% of the "
        "EBS throughput cap or ≥ 75% of its IOPS cap (2 writes per PUT) → disk; MinIO CPU ≥ 85% of "
        "the server's cores → server CPU; ≥ 80% of the measured link → network; otherwise the "
        "cell is latency-bound (closed loop, not saturated)."), "",
        *[f"- {k}: {v} cells" for k, v in sorted(limits.items(), key=lambda kv: -kv[1])], "",
        ("| Size | Workers | Op | Client host CPU (P1) | MinIO CPU (P1, % of one core) | "
        "MiB/s (P1) | Limit (P1) |"),
        "|---|---|---|---|---|---|---|",
    ]
    for size in sorted({c["size"] for c in cells}):
        for conc in sorted({c["concurrency"] for c in cells}):
            for op in ("put", "get"):
                c = cell("P1", op, size, conc)
                if c:
                    lines.append(f"| {size_label(size)} | {conc} | {op.upper()} | "
                                 f"{c['client_host_cpu']:.0f}% | {c['server_cpu']:.0f}% | "
                                 f"{c['mib_per_s']:.0f} | {c['limit']} |")
    lines += [
        "", "## Q3. Anything unusual?", "",
        f"- Failed requests: {sum(c['failures'] for c in cells)}",
        (f"- Client-bound runs (flagged by the runner): "
        f"{sum(1 for r in runs if r['client_bound'])}"),
        f"- Unsaturated cells whose median latency drifts >10% between the halves of a run "
        f"(drift in saturated cells is expected queueing): "
        f"{len(drifting)}"
        + (" (" + ", ".join(f"{c['mode']} {c['operation']} {size_label(c['size'])} "
                            f"c{c['concurrency']}" for c in drifting[:6]) + ")" if drifting
           else ""),
        "", "## Q4. First look at the hypotheses (pilot values, direction only)", "",
    ]
    # H3: RSA GET slower than ML-KEM GET for small objects
    h3 = [(s, cell("R1", "get", s, 1), cell("P1", "get", s, 1)) for s in (1024, 65536, MIB)]
    lines += ["**H3** RSA-4096 GET median latency vs ML-KEM-768 (1 worker):", ""]
    lines += [f"- {size_label(s)}: R1 {r['median_ms']:.2f} ms vs P1 {p['median_ms']:.2f} ms "
              f"({100 * (r['median_ms'] / p['median_ms'] - 1):+.0f}%)" for s, r, p in h3 if r and p]
    # H2: key-establishment share falls with object size
    lines += ["", "**H2** Key-establishment share of P1 PUT time (1 worker):", ""]
    lines += [f"- {size_label(s)}: {100 * c['ke_share']:.2f}%"
              for s in sorted({c['size'] for c in cells}) if (c := cell("P1", "put", s, 1))]
    # H1: P1 vs B2 at >= 1 MiB
    lines += ["", "**H1** |P1 − B2| median latency, ≥ 1 MiB, 1 worker (hypothesis: < 5%):", ""]
    for s in (MIB, 16 * MIB):
        for op in ("put", "get"):
            p, b = cell("P1", op, s, 1), cell("B2", op, s, 1)
            if p and b:
                lines.append(f"- {op.upper()} {size_label(s)}: "
                             f"{100 * (p['median_ms'] / b['median_ms'] - 1):+.1f}%")
    # H4: CPU cost per request gap P1 - B1 vs concurrency
    lines += ["", "**H4** Client CPU per request, P1 − B1 (1 KiB PUT):", ""]
    for conc in sorted({c["concurrency"] for c in cells}):
        p, b = cell("P1", "put", 1024, conc), cell("B1", "put", 1024, conc)
        if p and b:
            lines.append(f"- {conc} workers: {p['cpu_ms_per_req'] - b['cpu_ms_per_req']:+.3f} "
                         f"ms/request (P1 {p['cpu_ms_per_req']:.3f}, B1 {b['cpu_ms_per_req']:.3f})")
    # Recommendations
    reps = 10 if len(noisy) > 0.1 * len(cells) else 5
    lines += [
        "", "## Recommendations for Phase 8", "",
        f"- **Repetitions:** {reps} per cell"
        + (f" ({len(noisy)} cells exceed the {CV_LIMIT:.0%} CV rule)" if noisy else
           " (no cell exceeds the CV rule)"),
        "- **Durations:** keep 10 s warm-up + 30 s measured"
        + (" (no cell drifts > 10% within a run)" if not drifting else
           f"; {len(drifting)} cells drift > 10% within a run, so check warm-up length there"),
        ("- **Data volume:** the pilot wrote ~31 GB of raw records (1.7 GB compressed). The final "
        "matrix is several times larger; raw records are now compressed at the end of each "
        "experiment, and the client disk (60 GB) must hold the uncompressed file until then."),
        "", "_Generated by `analysis/pilot_report.py`; tables in `cells.csv` and `runs.csv`._", "",
    ]
    return "\n".join(lines)


def read_baselines(path: Path) -> dict:
    iperf = json.loads(max(path.glob("iperf3-*.json")).read_text())
    fio = json.loads(max(path.glob("fio-*.json")).read_text())["jobs"][0]
    ping = max(path.glob("ping-*.txt")).read_text().split("=")[-1].split("/")
    return {"net_gbit": iperf["end"]["sum_received"]["bits_per_second"] / 1e9,
            "rtt_ms": float(ping[1]), "disk_read": fio["read"]["bw"] / 1024,
            "disk_write": fio["write"]["bw"] / 1024}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--baselines", type=Path, default=Path("experiments/baselines"))
    parser.add_argument("--server-cores", type=int, default=8)
    parser.add_argument("--disk-mbps", type=float, default=500, help="gp3 throughput (MB/s)")
    parser.add_argument("--disk-iops", type=float, default=6000)
    parser.add_argument("--out", type=Path, default=Path("results/pilot"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    baselines = read_baselines(args.baselines)
    runs = run_rows(args.experiment)
    cells = cell_rows(runs, args.server_cores, baselines["net_gbit"] * 1e9 / 8 / MIB,
                      args.disk_mbps * 1e6 / MIB, args.disk_iops)
    write_csv(args.out / "runs.csv", runs)
    write_csv(args.out / "cells.csv", cells)
    text = report(cells, runs, baselines, args.out, args.experiment)
    (args.out / "report.md").write_text(text, encoding="utf-8")
    print(f"wrote {args.out}/report.md, cells.csv ({len(cells)}), runs.csv ({len(runs)})")
    assert all(not math.isnan(c["median_ms"]) for c in cells)


if __name__ == "__main__":
    main()
