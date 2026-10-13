"""Tables and numbers for the audit batches (SoT v1.11, v1.12, v1.14), by their pre-registered rules.

  J  padded-manifest control (C2 = X25519 with a manifest as large as ML-KEM's)
  K  64 KiB PUT at 32 and 128 workers with 50 repetitions
  L  binding controls (H1 = one foreign call per operation, lock released; G1 = lock held)
  N  native Go reader, GET path, modes B2, P1, P3

    python analysis/audit_assets.py --out paper/generated
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import final_analysis as fa
import stats
from make_paper_assets import Macros, num
from revision_assets import HEADER, pval, tex_table

SIZE = 65536
PREDICTED = 0.956          # SoT v1.12: from batch E's CPU-per-request ratio P1/B2 (1.046)
LABEL = {"B2": "X25519", "C2": "X25519, padded manifest", "P1": "ML-KEM-768 (binding)",
         "H1": "ML-KEM-768, one call, lock released", "G1": "ML-KEM-768, one call, lock held",
         "P3": "X-Wing"}


def ci90(logs: list[float]) -> tuple[float, float, float]:
    r = stats.paired_tost(logs, 0.98, 1.02)
    return r.ratio, r.ci90[0], r.ci90[1]


def fmt(logs: list[float]) -> str:
    r, lo, hi = ci90(logs)
    return f"{r:.3f} [{lo:.3f}, {hi:.3f}]"


def share(control: list[float], full: list[float], seed: int) -> tuple[float, float, float]:
    """log(control)/log(full) with a percentile-bootstrap 90% interval over repetitions."""
    c, f = np.asarray(control), np.asarray(full)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(c), size=(20000, len(c)))
    boot = c[idx].mean(axis=1) / f[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [5, 95])
    return c.mean() / f.mean(), lo, hi


def two_pct(logs: list[float]) -> float:
    return stats.paired_tost(logs, 0.98, 1.02).p


class Cells:
    def __init__(self, table: dict) -> None:
        self.table = table

    def runs(self, exp: str, op: str, conc: int, mode: str) -> list[dict]:
        return self.table[(exp, op, SIZE, "closed", conc, 0.0, mode, 0, False)]["runs"]

    def logs(self, exp: str, op: str, conc: int, a: str, b: str, metric: str) -> list[float]:
        return fa.log_ratios(self.runs(exp, op, conc, a), self.runs(exp, op, conc, b), metric)

    def mean(self, exp: str, op: str, conc: int, mode: str, metric: str) -> float:
        return statistics.fmean(r[metric] for r in self.runs(exp, op, conc, mode))

    def delta(self, exp: str, op: str, a: str, b: str, metric: str) -> float:
        by = {r["repetition"]: r for r in self.runs(exp, op, 1, b)}
        return statistics.fmean((r[metric] - by[r["repetition"]][metric]) * 1000
                                for r in self.runs(exp, op, 1, a))


def batch_j(c: Cells, m: Macros) -> list[list[str]]:
    exp, rows = "final-j", []
    thr = {pair: c.logs(exp, "get", 500, *pair, "ops_per_s")
           for pair in (("C2", "B2"), ("P1", "C2"), ("P1", "B2"))}
    for conc in (500, 128):
        for a, b in (("C2", "B2"), ("P1", "C2"), ("P1", "B2")):
            rows.append([f"J, {conc}", f"{LABEL[a]} / {LABEL[b]}",
                         fmt(c.logs(exp, "get", conc, a, b, "ops_per_s")),
                         fmt(c.logs(exp, "get", conc, a, b, "cpu_ms_per_req"))])
    pad, pad_lo, pad_hi = ci90(thr[("C2", "B2")])
    rest, rest_lo, rest_hi = ci90(thr[("P1", "C2")])
    full, full_lo, full_hi = ci90(thr[("P1", "B2")])
    e, e_lo, e_hi = share(thr[("C2", "B2")], thr[("P1", "B2")], 1)
    explains = two_pct(thr[("P1", "C2")]) < 0.05 and pad_hi < 1
    does_not = two_pct(thr[("C2", "B2")]) < 0.05 and rest_hi < 1
    m.add("AudPadRatio", f"{pad:.3f}")
    m.add("AudPadCI", f"{pad_lo:.3f}--{pad_hi:.3f}")
    m.add("AudPadCost", num((1 - pad) * 100, 1))
    m.add("AudRestRatio", f"{rest:.3f}")
    m.add("AudRestCI", f"{rest_lo:.3f}--{rest_hi:.3f}")
    m.add("AudRestCost", num((1 - rest) * 100, 1))
    m.add("AudJFullRatio", f"{full:.3f}")
    m.add("AudJFullCI", f"{full_lo:.3f}--{full_hi:.3f}")
    m.add("AudPadShare", num(100 * e, 0))
    m.add("AudPadShareLo", num(100 * e_lo, 0))
    m.add("AudPadShareHi", num(100 * e_hi, 0))
    m.add("AudPadVerdict", "explains" if explains else "does not explain" if does_not
          else "partly explains")
    m.add("AudPredicted", f"{PREDICTED:.3f}")
    m.add("AudPredictionErrorJ", num(abs(full - PREDICTED) * 100, 1))
    m.add("AudPredictionInsideJ", "inside" if full_lo <= PREDICTED <= full_hi else "outside")
    m.add("AudJCpuRatio", f"{ci90(c.logs(exp, 'get', 500, 'P1', 'B2', 'cpu_ms_per_req'))[0]:.3f}")
    m.add("AudPadStageGet", num(c.delta(exp, "get", "C2", "B2", "ser_mean_ms"), 1))
    m.add("AudMlkemStageGet", num(c.delta(exp, "get", "P1", "B2", "ser_mean_ms"), 1))
    m.add("AudKdfOverPadGet", num(c.delta(exp, "get", "P1", "C2", "kdf_mean_ms"), 1))
    m.add("AudJRuns", sum(len(v["runs"]) for k, v in c.table.items() if k[0] == exp))
    return rows


def batch_k(c: Cells, runs: list[dict], out: Path, m: Macros) -> None:
    exp, rows, results = "final-k", [], []
    for conc in (32, 128):
        a, b = c.runs(exp, "put", conc, "P1"), c.runs(exp, "put", conc, "B2")
        results.append((conc, stats.paired_tost(fa.log_ratios(a, b, "ops_per_s")),
                        stats.paired_tost(fa.log_ratios(a, b, "ops_per_s", True))))
    adjusted = stats.holm([r.p for _, r, _ in results])
    clean = stats.holm([r.p for _, _, r in results])
    for (conc, r, rc), p, pc in zip(results, adjusted, clean):
        verdict = "Eq." if p < 0.05 else "Inc."
        rows.append([f"64\\,KiB PUT, {conc}", str(r.n), f"{r.ratio:.3f}",
                     f"{r.ci90[0]:.3f}--{r.ci90[1]:.3f}", f"{r.ci95[0]:.3f}--{r.ci95[1]:.3f}",
                     num(r.sd_log * 100, 0) + "\\,\\%", pval(p), verdict,
                     f"{rc.n}: " + ("Eq." if pc < 0.05 else "Inc.")])
        tag = "Knee" if conc == 32 else "Sat"
        m.add(f"AudK{tag}Ratio", f"{r.ratio:.3f}")
        m.add(f"AudK{tag}CI", f"{r.ci90[0]:.3f}--{r.ci90[1]:.3f}")
        m.add(f"AudK{tag}Sd", num(r.sd_log * 100, 0))
        m.add(f"AudK{tag}Verdict", "equivalent" if p < 0.05 else "inconclusive")
    tex_table(out / "tab-power.tex",
              ["Cell", "$n$", "Ratio", "90\\% CI", "95\\% CI", "SD", "$p_{\\text{Holm}}$",
               "Verdict", "Without stalls"], rows, "lrccccccl")
    m.add("AudKEq", sum(p < 0.05 for p in adjusted))
    m.add("AudKEqNoStall", sum(p < 0.05 for p in clean))
    m.add("AudKRuns", sum(r["experiment"] == exp for r in runs))
    m.add("AudKStalls", sum(r["stall"] for r in runs if r["experiment"] == exp))


def batch_l(c: Cells, m: Macros) -> list[list[str]]:
    exp, rows = "final-l", []
    for conc in (500, 128):
        for a, b in (("P1", "B2"), ("H1", "B2"), ("G1", "B2"), ("H1", "P1"), ("G1", "H1")):
            rows.append([f"L, {conc}", f"{LABEL[a]} / {LABEL[b]}",
                         fmt(c.logs(exp, "get", conc, a, b, "ops_per_s")),
                         fmt(c.logs(exp, "get", conc, a, b, "cpu_ms_per_req"))])
    thr = {pair: c.logs(exp, "get", 500, *pair, "ops_per_s")
           for pair in (("P1", "B2"), ("H1", "B2"), ("G1", "B2"), ("H1", "P1"), ("G1", "P1"),
                        ("G1", "H1"))}
    full, full_lo, full_hi = ci90(thr[("P1", "B2")])
    explains = full_hi < 1 and (two_pct(thr[("H1", "B2")]) < 0.05 or two_pct(thr[("G1", "B2")]) < 0.05)
    does_not = two_pct(thr[("H1", "P1")]) < 0.05 and two_pct(thr[("G1", "P1")]) < 0.05
    m.add("AudBindVerdict", "explains" if explains else "does not explain" if does_not
          else "partly explains")
    m.add("AudLFullRatio", f"{full:.3f}")
    m.add("AudLFullCI", f"{full_lo:.3f}--{full_hi:.3f}")
    m.add("AudLFullCost", num((1 - full) * 100, 1))
    m.add("AudPredictionErrorL", num(abs(full - PREDICTED) * 100, 1))
    m.add("AudPredictionInsideL", "inside" if full_lo <= PREDICTED <= full_hi else "outside")
    for mode, name in (("H1", "Released"), ("G1", "Held")):
        r, lo, hi = ci90(thr[(mode, "B2")])
        m.add(f"AudBind{name}Ratio", f"{r:.3f}")
        m.add(f"AudBind{name}CI", f"{lo:.3f}--{hi:.3f}")
        m.add(f"AudBind{name}Cost", num((1 - r) * 100, 1))
        s, s_lo, s_hi = share(thr[(mode, "B2")], thr[("P1", "B2")], 2)
        m.add(f"AudBind{name}Removed", num(100 * (1 - s), 0))
        m.add(f"AudBind{name}RemovedLo", num(100 * (1 - s_hi), 0))
        m.add(f"AudBind{name}RemovedHi", num(100 * (1 - s_lo), 0))
        m.add(f"AudBind{name}EqTwoPct", "yes" if two_pct(thr[(mode, "B2")]) < 0.05 else "no")
        cpu = ci90(c.logs(exp, "get", 500, mode, "B2", "cpu_ms_per_req"))[0]
        m.add(f"AudBind{name}CpuRatio", f"{cpu:.3f}")
        m.add(f"AudBind{name}KeOne", f"{c.mean(exp, 'get', 1, mode, 'ke_mean_ms'):.3f}")
    r, lo, hi = ci90(thr[("G1", "H1")])
    m.add("AudBindHeldOverReleased", f"{r:.3f}")
    m.add("AudBindHeldOverReleasedCI", f"{lo:.3f}--{hi:.3f}")
    m.add("AudLCpuRatio", f"{ci90(c.logs(exp, 'get', 500, 'P1', 'B2', 'cpu_ms_per_req'))[0]:.3f}")
    m.add("AudBindBindingKeOne", f"{c.mean(exp, 'get', 1, 'P1', 'ke_mean_ms'):.3f}")
    m.add("AudBindEcdhKeOne", f"{c.mean(exp, 'get', 1, 'B2', 'ke_mean_ms'):.3f}")
    m.add("AudLRuns", sum(len(v["runs"]) for k, v in c.table.items() if k[0] == exp))
    return rows


def batch_n(path: Path, out: Path, results: Path, m: Macros) -> None:
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    cells = defaultdict(dict)
    for r in records:
        rep = int(r["label"].split(",")[0].split("=")[1])
        cells[(r["gomaxprocs"], r["workers"])].setdefault(r["mode"], {})[rep] = r
    rows, table = [], []
    m.add("AudNRuns", len(records))
    m.add("AudNFailures", num(sum(r["failures"] for r in records)))
    m.add("AudNGo", records[0]["go"].replace("go", ""))
    for (cores, workers), tag in (((1, 128), "One"), ((16, 128), "Mid"), ((16, 500), "Hot")):
        by = cells[(cores, workers)]
        base = by["B2"]
        mean = lambda mode, key: statistics.fmean(r[key] for r in by[mode].values())
        saturated = all(mean(mode, "client_cores") >= 0.95 * cores for mode in by)
        m.add(f"AudN{tag}Ops", num(mean("B2", "ops_per_s"), -1))
        m.add(f"AudN{tag}Cores", f"{mean('B2', 'client_cores'):.2f}")
        m.add(f"AudN{tag}CpuUs", num(mean("B2", "cpu_ms_per_req") * 1000, 0))
        m.add(f"AudN{tag}Saturated", "yes" if saturated else "no")
        line = [f"{cores} core{'s' if cores > 1 else ''}, {workers}", num(mean("B2", "ops_per_s"), -1),
                f"{mean('B2', 'client_cores'):.2f}", num(mean("B2", "cpu_ms_per_req") * 1000, 0)]
        for mode, name in (("P1", "Mlkem"), ("P3", "Xwing")):
            for metric, short in (("ops_per_s", "Thr"), ("cpu_ms_per_req", "Cpu")):
                logs = [math.log(by[mode][rep][metric] / base[rep][metric])
                        for rep in sorted(base) if rep in by[mode]]
                r, lo, hi = ci90(logs)
                line.append(f"{r:.3f} [{lo:.3f}, {hi:.3f}]")
                m.add(f"AudN{tag}{name}{short}", f"{r:.3f}")
                m.add(f"AudN{tag}{name}{short}CI", f"{lo:.3f}--{hi:.3f}")
                table.append({"cores": cores, "workers": workers, "mode": mode, "metric": metric,
                              "ratio": r, "ci90_lo": lo, "ci90_hi": hi, "n": len(logs),
                              "p_tost_2pct": two_pct(logs)})
                if metric == "ops_per_s":
                    verdict = ("no deficit" if two_pct(logs) < 0.05 else "deficit" if hi < 0.98
                               else "advantage" if lo > 1.02 else "inconclusive")
                    m.add(f"AudN{tag}{name}Verdict", verdict)
                    m.add(f"AudN{tag}{name}Change", num((r - 1) * 100, 1))
        rows.append(line)
    fa.write_csv(results / "native.csv", table)
    tex_table(out / "tab-native.tex",
              ["Cell", "req/s", "Cores", "CPU (\\textmu s)", "Throughput", "CPU/request",
               "Throughput", "CPU/request"], rows, "lrrr|cc|cc",
              " & \\multicolumn{3}{c|}{X25519} & \\multicolumn{2}{c|}{ML-KEM-768 / X25519} & "
              "\\multicolumn{2}{c}{X-Wing / X25519}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, default=Path("results/audit/runs.csv"))
    parser.add_argument("--native", type=Path, default=Path("experiments/native/final-n.jsonl"))
    parser.add_argument("--results", type=Path, default=Path("results/audit"))
    parser.add_argument("--out", type=Path, default=Path("paper/generated"))
    args = parser.parse_args()
    runs = fa.load_runs(args.runs)
    fa.flag_stalls(runs)
    cells = Cells(fa.cells(runs))
    experiments = {r["experiment"] for r in runs}
    m = Macros()
    m.add("AudRuns", num(len(runs)))
    m.add("AudRequests", f"{sum(r['requests'] for r in runs) / 1e6:.1f}")
    m.add("AudFailures", num(sum(r["failures"] for r in runs)))
    rows = batch_j(cells, m)
    batch_k(cells, runs, args.out, m)
    if "final-l" in experiments:
        rows += batch_l(cells, m)
    tex_table(args.out / "tab-control.tex",
              ["Batch, workers", "Comparison", "Throughput ratio", "CPU-per-request ratio"],
              rows, "llcc")
    if args.native.is_file():
        batch_n(args.native, args.out, args.results, m)
    (args.out / "audit.tex").write_text(
        HEADER.replace("revision_assets", "audit_assets") + "\n".join(m.lines) + "\n",
        encoding="utf-8")
    print(f"wrote {len(m.lines)} macros to {args.out} (batches: {sorted(experiments)}"
          f"{', native' if args.native.is_file() else ''})")


if __name__ == "__main__":
    main()
