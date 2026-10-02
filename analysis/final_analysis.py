"""Final statistics over the per-run summaries (analysis/summarize.py).

Statistical rules (SoT §9.3, decided after the final runs):
  * A run is the unit of replication; every cell has 5 repetitions.
  * Means carry a Student-t 95% interval (df = 4). With n = 5 a percentile bootstrap
    under-covers, so t-intervals replace the bootstrap the plan originally named.
  * Modes are compared only within one batch and paired by repetition (they ran
    interleaved, minutes apart): the ratio of two modes is exp(mean log ratio) with a
    t-interval over the 5 paired log ratios. Absolute small-object throughput moved
    ~10% between batches, so cross-batch comparisons are never made.
  * Equivalence margin +-5%: "equivalent" if the whole CI lies inside [0.95, 1.05],
    "different" if it lies entirely outside, otherwise "inconclusive".
  * A run is flagged as a server stall when both its server CPU and its throughput are
    below 80% / 90% of the median of its own cell's five runs. Primary results keep
    every run; a sensitivity column drops pairs containing a stalled run.
  * Stage times include waiting for the GIL at concurrency > 1, so key-establishment
    cost and stage shares are reported at one worker; CPU per request (thread CPU time)
    is the concurrency-independent cost.

    python analysis/final_analysis.py --runs results/final/runs.csv --out results/final
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
MARGIN = 0.05
MIB = 1024 * 1024
MODES = ["B0", "B1", "R1", "B2", "P1", "P2", "N1"]
MODE_NAME = {"B0": "plaintext", "B1": "AES only (pre-shared key)", "R1": "RSA-OAEP-4096",
             "B2": "X25519", "P1": "ML-KEM-768", "P2": "X25519+ML-KEM-768", "N1": "ML-KEM session"}
NUMERIC = {"repetition", "size", "concurrency", "rate", "session_bmax", "requests", "failures",
           "worker_processes"}
CELL_METRICS = ["ops_per_s", "mib_per_s", "p50_ms", "p99_ms", "mean_ms", "cpu_ms_per_req",
                "ke_mean_ms", "ke_share", "s3_share", "client_cores", "client_host_cores",
                "server_cores", "client_rss_peak_mib", "client_rss_growth_mib",
                "server_rss_peak_mib", "server_rss_growth_mib", "client_rss_window_drift_mib",
                "kem_per_request", "mean_session_bound", "sojourn_mean_ms", "sojourn_p99_ms",
                "wait_mean_ms"]


# ---------------------------------------------------------------- loading and cells

def num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def load_runs(path: Path) -> list[dict]:
    runs = []
    with path.open(encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            r = dict(raw)
            for key, value in raw.items():
                if key in NUMERIC:
                    r[key] = int(float(value)) if value not in ("", None) else 0
                elif key not in {"experiment", "run_id", "block", "mode", "operation", "loop",
                                 "queue_aware", "valid", "client_bound"}:
                    r[key] = num(value)
            r["queue_aware"] = raw["queue_aware"] == "True"
            r["valid"] = raw["valid"] == "True"
            r["client_bound"] = raw["client_bound"] == "True"
            # One unit for CPU: cores in use (100% of one core = 1 core).
            r["client_cores"] = r.get("client_cpu_pct", float("nan")) / 100
            r["server_cores"] = r.get("server_cpu_pct", float("nan")) / 100
            r["client_host_cores"] = r.get("client_host_cpu_pct", float("nan")) * 16 / 100
            runs.append(r)
    return runs


def workload(r: dict) -> tuple:
    """Everything that defines a cell except the mode (and the N1 session settings)."""
    return (r["experiment"], r["operation"], r["size"], r["loop"], r["concurrency"], r["rate"])


def cell_key(r: dict) -> tuple:
    return (*workload(r), r["mode"], r["session_bmax"], r["queue_aware"])


def flag_stalls(runs: list[dict]) -> None:
    groups = defaultdict(list)
    for r in runs:
        groups[cell_key(r)].append(r)
    for group in groups.values():
        cpu = statistics.median(r["server_cores"] for r in group)
        ops = statistics.median(r["ops_per_s"] for r in group)
        for r in group:
            r["stall"] = (r["loop"] == "closed" and r["server_cores"] < 0.8 * cpu
                          and r["ops_per_s"] < 0.9 * ops)


def mean_ci(values: list[float]) -> tuple[float, float, float]:
    values = [v for v in values if not math.isnan(v)]
    if not values:
        return float("nan"), float("nan"), float("nan")
    mean = statistics.fmean(values)
    if len(values) < 2:
        return mean, float("nan"), float("nan")
    half = T95[len(values) - 1] * statistics.stdev(values) / math.sqrt(len(values))
    return mean, mean - half, mean + half


def cells(runs: list[dict]) -> dict[tuple, dict]:
    groups = defaultdict(list)
    for r in runs:
        groups[cell_key(r)].append(r)
    out = {}
    for key, group in groups.items():
        row = dict(zip(["experiment", "operation", "size", "loop", "concurrency", "rate", "mode",
                        "session_bmax", "queue_aware"], key))
        row["reps"] = len(group)
        row["stalled_runs"] = sum(r["stall"] for r in group)
        row["client_bound_runs"] = sum(r["client_bound"] for r in group)
        row["failures"] = sum(r["failures"] for r in group)
        for metric in CELL_METRICS:
            mean, lo, hi = mean_ci([r.get(metric, float("nan")) for r in group])
            row[metric], row[f"{metric}_lo"], row[f"{metric}_hi"] = mean, lo, hi
        ops = [r["ops_per_s"] for r in group]
        row["ops_cv"] = statistics.stdev(ops) / statistics.fmean(ops) if len(ops) > 1 else 0.0
        row["runs"] = group
        out[key] = row
    return out


# ---------------------------------------------------------------- paired comparisons

def paired(a: list[dict], b: list[dict], metric: str, drop_stalls: bool = False):
    """Ratio a/b over runs paired by repetition: (ratio, lo, hi, n)."""
    by_rep = {r["repetition"]: r for r in b}
    logs = []
    for r in a:
        other = by_rep.get(r["repetition"])
        if other is None or (drop_stalls and (r["stall"] or other["stall"])):
            continue
        x, y = r[metric], other[metric]
        if x > 0 and y > 0:
            logs.append(math.log(x / y))
    if len(logs) < 2:
        return float("nan"), float("nan"), float("nan"), len(logs)
    mean, lo, hi = mean_ci(logs)
    return math.exp(mean), math.exp(lo), math.exp(hi), len(logs)


def paired_diff(a: list[dict], b: list[dict], metric: str):
    by_rep = {r["repetition"]: r for r in b}
    diffs = [r[metric] - by_rep[r["repetition"]][metric] for r in a if r["repetition"] in by_rep]
    mean, lo, hi = mean_ci(diffs)
    return mean, lo, hi, len(diffs)


def verdict(lo: float, hi: float) -> str:
    if math.isnan(lo) or math.isnan(hi):
        return "n/a"
    excludes_one = " (CI excludes 1)" if lo > 1 or hi < 1 else ""
    if lo >= 1 - MARGIN and hi <= 1 + MARGIN:
        return "equivalent" + excludes_one
    if hi < 1 - MARGIN or lo > 1 + MARGIN:
        return "different"
    return "inconclusive" + excludes_one


def compare(table: dict, mode_a: str, mode_b: str, metrics: list[str], where) -> list[dict]:
    rows = []
    for key, cell in sorted(table.items(), key=lambda kv: str(kv[0])):
        if cell["mode"] != mode_a or not where(cell):
            continue
        other = table.get((*key[:6], mode_b, 0, False))
        if other is None:
            continue
        row = {k: cell[k] for k in ("experiment", "operation", "size", "loop", "concurrency",
                                     "rate")}
        row["comparison"] = f"{mode_a}/{mode_b}"
        for metric in metrics:
            ratio, lo, hi, n = paired(cell["runs"], other["runs"], metric)
            s_ratio, s_lo, s_hi, s_n = paired(cell["runs"], other["runs"], metric, True)
            row.update({f"{metric}_ratio": ratio, f"{metric}_lo": lo, f"{metric}_hi": hi,
                        f"{metric}_n": n, f"{metric}_verdict": verdict(lo, hi),
                        f"{metric}_ratio_nostall": s_ratio,
                        f"{metric}_verdict_nostall": verdict(s_lo, s_hi), f"{metric}_n_nostall": s_n})
        rows.append(row)
    return rows


def closed(cell: dict) -> bool:
    return cell["loop"] == "closed"


# ---------------------------------------------------------------- bottlenecks

def bottleneck(cell: dict, link_mib_s: float, cores: int = 16) -> str:
    """Name the resource that limits a closed-loop cell (i4i.4xlarge + c7i.4xlarge, 16 vCPU each)."""
    def rate(r: dict, key: str) -> float:
        value = r.get(key, 0.0)
        return 0.0 if value is None or math.isnan(value) else value

    net = statistics.fmean(max(rate(r, "client_net_tx_mib_s"), rate(r, "client_net_rx_mib_s"))
                           for r in cell["runs"])
    if net >= 0.85 * link_mib_s:
        return "network"
    if cell["client_host_cores"] >= 0.85 * cores:
        return "client CPU"
    if cell["server_cores"] >= 0.85 * cores:
        return "server CPU"
    return "none (latency-bound)"


def mark_saturation(table: dict) -> None:
    """A closed-loop cell is saturated when doubling+ the workers adds <5% throughput."""
    series = defaultdict(list)
    for cell in table.values():
        if cell["loop"] == "closed":
            series[(cell["experiment"], cell["operation"], cell["size"], cell["mode"],
                    cell["session_bmax"])].append(cell)
    for cells_ in series.values():
        cells_.sort(key=lambda c: c["concurrency"])
        for i, cell in enumerate(cells_):
            later = [c["ops_per_s"] for c in cells_[i + 1:]]
            cell["saturated"] = bool(later) and max(later) < 1.05 * cell["ops_per_s"] or (
                not later and i > 0 and cell["ops_per_s"] < 1.05 * cells_[i - 1]["ops_per_s"])


def limit_label(cell: dict, link_mib_s: float) -> str:
    resource = bottleneck(cell, link_mib_s)
    if resource != "none (latency-bound)":
        return resource
    if cell.get("saturated"):  # flat throughput, but no client/network/CPU cap reached
        return "server write path" if cell["operation"] == "put" else "unattributed"
    return resource


# ---------------------------------------------------------------- queueing model (RQ3)

def erlang_c(servers: int, load: float) -> float:
    """Probability that an arrival waits in M/M/c (load = lambda * S, in Erlangs)."""
    if load >= servers:
        return 1.0
    term, total = 1.0, 1.0
    for k in range(1, servers):
        term *= load / k
        total += term
    term *= load / servers
    last = term * servers / (servers - load)
    return last / (total + last)


def queueing(table: dict) -> list[dict]:
    """Sweep D: offered load vs response time, and an M/M/c fit.

    Capacity mu = mean achieved throughput of the two most overloaded rates; S0 = mean
    service time at the lightest rate; c = round(mu * S0). Predicted mean response time
    W = S0 + C(c, a) * S0 / (c - a) with a = lambda * S0. A run is stable when it
    delivers >= 97% of the offered rate and its mean wait stays under 10 ms; response
    times of unstable runs grow with run length, so they get no prediction or CI."""
    rows = []
    sweep = [c for c in table.values() if c["loop"] == "open" and c["concurrency"] == 256]
    for (size, mode) in sorted({(c["size"], c["mode"]) for c in sweep}):
        series = sorted((c for c in sweep if c["size"] == size and c["mode"] == mode),
                        key=lambda c: c["rate"])
        mu = statistics.fmean(c["ops_per_s"] for c in series[-2:])
        s0 = series[0]["mean_ms"] / 1000
        servers = max(1, round(mu * s0))
        for cell in series:
            stable_runs = [r for r in cell["runs"]
                           if r["ops_per_s"] >= 0.97 * r["rate"] and r["wait_mean_ms"] < 10]
            stable = len(stable_runs) == len(cell["runs"])
            offered = cell["rate"] * s0
            predicted = (s0 + erlang_c(servers, offered) * s0 / (servers - offered)) * 1000 \
                if offered < servers else float("inf")
            rows.append({
                "size": size, "mode": mode, "rate": cell["rate"], "capacity": mu,
                "rho": cell["rate"] / mu, "servers": servers, "s0_ms": s0 * 1000,
                "achieved": cell["ops_per_s"], "stable_runs": len(stable_runs),
                "reps": len(cell["runs"]), "stable": stable,
                "measured_mean_ms": cell["sojourn_mean_ms"] if stable else float("nan"),
                "measured_mean_all_ms": cell["sojourn_mean_ms"],
                "measured_mean_lo": cell["sojourn_mean_ms_lo"] if stable else float("nan"),
                "measured_mean_hi": cell["sojourn_mean_ms_hi"] if stable else float("nan"),
                "measured_p99_ms": cell["sojourn_p99_ms"] if stable else float("nan"),
                "service_p50_ms": cell["p50_ms"],
                "predicted_mean_ms": predicted,
            })
    return rows


# ---------------------------------------------------------------- report

def fmt(x: float, digits: int = 2) -> str:
    if math.isnan(x):
        return "–"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.{digits}f}"


def ci(cell: dict, metric: str, digits: int = 2) -> str:
    return (f"{fmt(cell[metric], digits)} [{fmt(cell[metric + '_lo'], digits)}, "
            f"{fmt(cell[metric + '_hi'], digits)}]")


def size_label(size: int) -> str:
    return f"{size // MIB} MiB" if size >= MIB else f"{size // 1024} KiB"


def md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def ratio_cell(row: dict, metric: str) -> str:
    return (f"{fmt(row[metric + '_ratio'], 3)} [{fmt(row[metric + '_lo'], 3)}, "
            f"{fmt(row[metric + '_hi'], 3)}] {row[metric + '_verdict']}")


def write_csv(path: Path, rows: list[dict]) -> None:
    rows = [{k: v for k, v in r.items() if k != "runs"} for r in rows]
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("results/final/runs.csv"))
    parser.add_argument("--baselines", type=Path, default=Path("experiments/baselines"))
    parser.add_argument("--out", type=Path, default=Path("results/final"))
    args = parser.parse_args()

    runs = load_runs(args.runs)
    flag_stalls(runs)
    table = cells(runs)
    mark_saturation(table)
    iperf = json.loads(max(args.baselines.glob("iperf3-*.json")).read_text())
    link_mib_s = iperf["end"]["sum_received"]["bits_per_second"] / 8 / MIB
    for cell in table.values():
        cell["limit"] = limit_label(cell, link_mib_s) if cell["loop"] == "closed" else "open loop"

    h1 = compare(table, "P1", "B2", ["ops_per_s", "p50_ms", "p99_ms"], closed)
    h3 = compare(table, "R1", "P1", ["ops_per_s", "p50_ms", "p99_ms"],
                 lambda c: closed(c) and c["operation"] == "get")
    hybrid = compare(table, "P2", "P1", ["ops_per_s", "p50_ms"], closed)
    vs_aes = compare(table, "P1", "B1", ["ops_per_s", "p50_ms"], closed)

    # H4: thread CPU per request, paired differences (ms).
    h4 = []
    for key, cell in sorted(table.items(), key=lambda kv: str(kv[0])):
        if cell["mode"] != "P1" or not closed(cell):
            continue
        for other_mode in ("B1", "B2", "R1"):
            other = table.get((*key[:6], other_mode, 0, False))
            if other:
                d, lo, hi, n = paired_diff(cell["runs"], other["runs"], "cpu_ms_per_req")
                h4.append({k: cell[k] for k in ("experiment", "operation", "size", "concurrency")}
                          | {"comparison": f"P1-{other_mode}", "cpu_ms_diff": d,
                             "cpu_ms_lo": lo, "cpu_ms_hi": hi, "n": n})

    q_rows = queueing(table)

    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "cells.csv", list(table.values()))
    write_csv(args.out / "h1_p1_vs_b2.csv", h1)
    write_csv(args.out / "h3_r1_vs_p1.csv", h3)
    write_csv(args.out / "h4_cpu.csv", h4)
    write_csv(args.out / "p2_vs_p1.csv", hybrid)
    write_csv(args.out / "p1_vs_b1.csv", vs_aes)
    write_csv(args.out / "queueing.csv", q_rows)
    write_csv(args.out / "stalled_runs.csv",
              [{k: r[k] for k in ("experiment", "run_id", "mode", "ops_per_s", "server_cores")}
               for r in runs if r["stall"]])
    report = build_report(table, runs, h1, h3, h4, hybrid, q_rows, link_mib_s)
    (args.out / "report.md").write_text(report)
    print(f"wrote {args.out}/report.md and CSVs ({len(table)} cells)")


def build_report(table, runs, h1, h3, h4, hybrid, q_rows, link_mib_s) -> str:
    out = ["# Final results (batches A, B, C)", ""]
    n_runs = len(runs)
    n_req = sum(r["requests"] for r in runs)
    stalls = [r for r in runs if r["stall"]]
    noisy = [c for c in table.values() if c["ops_cv"] > 0.05]
    out += [(f"{n_runs} runs, {n_req:,} measured requests, "
             f"{sum(r['failures'] for r in runs)} failed requests. Link capacity (iperf3) "
             f"{link_mib_s:,.0f} MiB/s. 95% CIs are Student-t over 5 repetitions; mode ratios "
             f"are paired by repetition within one batch."), "",
            (f"Run-to-run noise: {len(noisy)} of {len(table)} cells exceed 5% throughput CV "
             f"({sum(1 for c in noisy if c['operation'] == 'put' and c['size'] <= 65536)} of "
             f"them small-object PUT cells). {len(stalls)} runs are flagged as server stalls "
             f"(server CPU and throughput both well below their own cell's median); by mode: "
             + ", ".join(f"{m} {sum(r['mode'] == m for r in stalls)}" for m in MODES) + "."),
            ""]

    # Metric 1: handshake overhead at one worker (batch B, pooled over sizes per repetition).
    out += ["## Metric 1 — key-establishment (handshake) time per request, one worker", "",
            ("Batch B, closed loop, 1 worker; per repetition averaged over the object sizes "
             "up to 16 MiB (multipart uploads above that add thread contention to the timer)."),
            ""]
    rows = []
    for mode in ["B1", "R1", "B2", "P1"]:
        for op in ("put", "get"):
            per_rep = defaultdict(list)
            for r in runs:
                if (r["experiment"] == "final-b" and r["mode"] == mode and r["operation"] == op
                        and r["concurrency"] == 1 and r["size"] <= 16 * MIB):
                    per_rep[r["repetition"]].append(r["ke_mean_ms"])
            mean, lo, hi = mean_ci([statistics.fmean(v) for v in per_rep.values()])
            rows.append([f"{mode} {MODE_NAME[mode]}", op,
                         f"{mean * 1000:.1f} [{lo * 1000:.1f}, {hi * 1000:.1f}]"])
    out += [md_table(["Mode", "Op", "Key establishment (µs), mean [95% CI]"], rows), ""]

    # Metric 2: throughput (batch A).
    out += ["## Metric 2 — throughput (batch A, closed loop)", "",
            ("Requests/s, mean ± 95% CI half-width; MiB/s in parentheses; limiting "
             "resource from the client/server/network samples."), ""]
    for op in ("put", "get"):
        for size in (65536, 1048576, 16777216):
            rows = []
            concs = sorted({c["concurrency"] for c in table.values() if c["experiment"] == "final-a"
                            and c["size"] == size and c["operation"] == op and c["mode"] == "B1"})
            for conc in concs:
                row = [str(conc)]
                for mode in ["B0", "B1", "R1", "B2", "P1", "P2"]:
                    c = table.get(("final-a", op, size, "closed", conc, 0.0, mode, 0, False))
                    half = (c["ops_per_s_hi"] - c["ops_per_s_lo"]) / 2 if c else 0
                    row.append(f"{fmt(c['ops_per_s'], 0)} ±{fmt(half, 0)} "
                               f"({fmt(c['mib_per_s'], 0)})" if c else "–")
                b1 = table[("final-a", op, size, "closed", conc, 0.0, "B1", 0, False)]
                row.append(b1["limit"])
                rows.append(row)
            out += [f"**{op.upper()} {size_label(size)}**", "",
                    md_table(["Workers", "B0", "B1", "R1", "B2", "P1", "P2", "Limit (B1)"], rows), ""]

    # Metric 3: CPU.
    out += ["## Metric 3 — CPU (batch A)", "",
            ("Cores in use during the measured window (client: benchmark processes; "
             "server: MinIO), and client thread CPU per request (ms)."), ""]
    rows = []
    for op in ("put", "get"):
        for size in (65536, 1048576):
            for conc in (1, 32, 128):
                for mode in ["B1", "R1", "B2", "P1"]:
                    c = table.get(("final-a", op, size, "closed", conc, 0.0, mode, 0, False))
                    if c:
                        rows.append([op, size_label(size), str(conc), mode,
                                     ci(c, "client_cores", 2), ci(c, "server_cores", 2),
                                     ci(c, "cpu_ms_per_req", 3)])
    out += [md_table(["Op", "Size", "Workers", "Mode", "Client cores", "Server cores",
                      "Client CPU ms/request"], rows), ""]

    # Metric 4: memory.
    out += ["## Metric 4 — memory (client RSS summed over worker processes; MinIO RSS)", "",
            ("Peak RSS over the whole run and growth from the first sample (before "
             "warm-up). Every run starts fresh worker processes, so nothing accumulates "
             "across runs."), ""]
    rows = []
    for exp, op, size, conc in [("final-a", "put", 65536, 500), ("final-a", "get", 65536, 500),
                                ("final-a", "put", 16777216, 128), ("final-a", "get", 16777216, 128),
                                ("final-b", "put", 524288000, 1), ("final-b", "get", 524288000, 1),
                                ("final-b", "put", 524288000, 16), ("final-b", "get", 524288000, 16)]:
        for mode in ["B1", "R1", "B2", "P1"]:
            c = table.get((exp, op, size, "closed", conc, 0.0, mode, 0, False))
            if c:
                rows.append([op, size_label(size), str(conc), mode,
                             ci(c, "client_rss_peak_mib", 0), ci(c, "client_rss_growth_mib", 0),
                             ci(c, "server_rss_growth_mib", 0)])
    out += [md_table(["Op", "Size", "Workers", "Mode", "Client peak MiB", "Client growth MiB",
                      "Server growth MiB"], rows), ""]

    # Hypotheses.
    out += ["## H1 — ML-KEM-768 (P1) vs X25519 (B2): throughput and median latency", "",
            f"Paired ratio P1/B2 [95% CI] and verdict (equivalent = CI inside ±{MARGIN:.0%}).", ""]
    rows = [[r["experiment"], r["operation"], size_label(r["size"]), str(r["concurrency"]),
             ratio_cell(r, "ops_per_s"), ratio_cell(r, "p50_ms"),
             r["ops_per_s_verdict_nostall"]] for r in h1]
    out += [md_table(["Batch", "Op", "Size", "Workers", "Throughput ratio", "p50 ratio",
                      "Throughput verdict w/o stalls"], rows), ""]
    counts = defaultdict(int)
    for r in h1:
        counts[r["ops_per_s_verdict"]] += 1
    out += ["Throughput verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), ""]

    out += ["## H2 — share of request time spent in ML-KEM (P1, one worker, batch B)", ""]
    rows = []
    for op in ("put", "get"):
        for size in sorted({c["size"] for c in table.values() if c["experiment"] == "final-b"}):
            c = table.get(("final-b", op, size, "closed", 1, 0.0, "P1", 0, False))
            if c:
                share = (f"{c['ke_share'] * 100:.3f}% [{c['ke_share_lo'] * 100:.3f}, "
                         f"{c['ke_share_hi'] * 100:.3f}]")
                rows.append([op, size_label(size), f"{c['ke_mean_ms'] * 1000:.1f}", share,
                             ci(c, "p50_ms", 2)])
    out += [md_table(["Op", "Size", "ML-KEM µs", "Share of request time", "p50 ms"], rows), ""]

    out += ["## H3 — RSA-OAEP-4096 (R1) vs ML-KEM-768 (P1) on GET", "",
            "Paired ratio R1/P1 [95% CI].", ""]
    rows = [[r["experiment"], size_label(r["size"]), str(r["concurrency"]),
             ratio_cell(r, "ops_per_s"), ratio_cell(r, "p50_ms")] for r in h3]
    out += [md_table(["Batch", "Size", "Workers", "Throughput ratio", "p50 ratio"], rows), ""]

    out += ["## H4 — client CPU per request, paired difference (ms)", "",
            "Thread CPU time (excludes GIL waiting), one worker.", ""]
    rows = [[r["experiment"], r["operation"], size_label(r["size"]), r["comparison"],
             f"{r['cpu_ms_diff']:+.3f} [{r['cpu_ms_lo']:+.3f}, {r['cpu_ms_hi']:+.3f}]"]
            for r in h4 if r["concurrency"] == 1]
    out += [md_table(["Batch", "Op", "Size", "Comparison", "Δ CPU ms/request [95% CI]"], rows), ""]

    out += ["## Hybrid P2 vs P1 (batch A, 1 MiB)", ""]
    rows = [[r["operation"], str(r["concurrency"]), ratio_cell(r, "ops_per_s"),
             ratio_cell(r, "p50_ms")] for r in hybrid]
    out += [md_table(["Op", "Workers", "Throughput ratio P2/P1", "p50 ratio"], rows), ""]

    # N1.
    out += ["## N1 — bounded ML-KEM session amortisation (batch C Sweep E; batch D re-run of PUT)", "",
            ("ML-KEM operations per request, key-establishment time, and throughput/CPU "
             "paired against P1 in the same batch."), ""]
    rows = []
    for exp, op, size, conc in [(e, o, s, c) for e in ("final-c", "final-d") for o in ("put", "get")
                                for s in (1024, 65536) for c in (1, 32, 128)]:
                p1 = table.get((exp, op, size, "closed", conc, 0.0, "P1", 0, False))
                if not p1:
                    continue
                for bmax in (10, 100, 1000):
                    n1 = table.get((exp, op, size, "closed", conc, 0.0, "N1", bmax, False))
                    if not n1:
                        continue
                    ratio, lo, hi, _ = paired(n1["runs"], p1["runs"], "ops_per_s")
                    d, dlo, dhi, _ = paired_diff(n1["runs"], p1["runs"], "cpu_ms_per_req")
                    rows.append([exp[-1].upper(), op, size_label(size), str(conc), str(bmax),
                                 fmt(n1["kem_per_request"], 4) if op == "put" else "–",
                                 f"{n1['ke_mean_ms'] * 1000:.1f} vs {p1['ke_mean_ms'] * 1000:.1f}",
                                 f"{ratio:.3f} [{lo:.3f}, {hi:.3f}] {verdict(lo, hi)}",
                                 f"{d:+.3f} [{dlo:+.3f}, {dhi:+.3f}]"])
    out += [md_table(["Batch", "Op", "Size", "Workers", "B_max", "KEM/request", "KE µs N1 vs P1",
                      "Throughput N1/P1", "Δ CPU ms/request"], rows), ""]

    out += ["### Queue-aware vs fixed bound (open loop, 1 KiB PUT, 128 threads, B_max = 100)", ""]
    rows = []
    for rate in sorted({c["rate"] for c in table.values() if c["experiment"] == "final-c"
                        and c["loop"] == "open" and c["mode"] == "N1"}):
        fixed = table[("final-c", "put", 1024, "open", 128, rate, "N1", 100, False)]
        aware = table[("final-c", "put", 1024, "open", 128, rate, "N1", 100, True)]
        stable = all(r["ops_per_s"] >= 0.97 * rate and r["wait_mean_ms"] < 10
                     for r in fixed["runs"] + aware["runs"])
        if stable:
            ratio, lo, hi, _ = paired(aware["runs"], fixed["runs"], "sojourn_p99_ms")
            p99 = f"{ratio:.3f} [{lo:.3f}, {hi:.3f}] {verdict(lo, hi)}"
        else:
            p99 = "overloaded (not compared)"
        rows.append([f"{rate:,.0f}", "yes" if stable else "no",
                     f"{aware['mean_session_bound']:.1f} vs {fixed['mean_session_bound']:.0f}",
                     f"{aware['kem_per_request']:.4f} vs {fixed['kem_per_request']:.4f}", p99])
    out += [md_table(["Offered req/s", "Stable", "Mean bound (aware vs fixed)",
                      "KEM/request (aware vs fixed)", "p99 response ratio aware/fixed"], rows), ""]

    # Queueing.
    out += ["## RQ3 — offered load vs response time and the M/M/c model (batch C, Sweep D)", "",
            ("Capacity µ from the two most overloaded rates of the same batch; c = round(µ·S0); "
             "M/M/c is evaluated at every ρ < 1. Response time = queue wait + service. A run is "
             "stable when it delivers ≥ 97% of the offered rate with mean wait < 10 ms; unstable "
             "response times grow with run length, so they are shown only as a lower bound."), ""]
    rows = [[size_label(q["size"]), q["mode"], f"{q['rate']:,.0f}", f"{q['rho']:.2f}",
             f"{q['achieved']:,.0f}", f"{q['stable_runs']}/{q['reps']}",
             (fmt(q["measured_mean_ms"], 2) if q["stable"]
              else f"≥ {fmt(q['measured_mean_all_ms'], 0)} (unstable)"),
             fmt(q["predicted_mean_ms"], 2) if q["rho"] < 1 else "∞",
             fmt(q["measured_p99_ms"], 1), f"{q['servers']}"] for q in q_rows]
    out += [md_table(["Size", "Mode", "Offered", "ρ", "Achieved", "Stable runs",
                      "Mean response ms", "M/M/c ms", "p99 ms", "c"], rows), ""]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    main()
