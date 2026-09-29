# Pilot report (Phase 6)

Source: `experiments/pilot/20260928T162132Z`. Pilot values size the final study; they are **not results** (SoT §15.1).

## Data

- Runs: 800 valid runs in 160 cells (5–5 repetitions each)
- Measured successful requests: 29,998,140; failed: 0
- Testbed baselines: network 12.4 Gbit/s, RTT 0.387 ms, disk read 347 / write 154 MiB/s (fio, 70/30 random 1 MiB)

## Q1. How noisy are the measurements?

Run-to-run coefficient of variation (CV) of each cell's median latency and throughput across its repetitions. SoT rule: CV > 5% means 10 repetitions instead of 5.

- Cells above 5%: **37 of 160**
- Median CV across cells: latency 2.2%, throughput 1.8%

Noisiest cells:

| Mode | Op | Size | Workers | Latency CV | Throughput CV |
|---|---|---|---|---|---|
| P1 | PUT | 1 KiB | 32 | 58.1% | 37.4% |
| B1 | PUT | 1 KiB | 32 | 54.0% | 43.8% |
| B2 | PUT | 1 KiB | 32 | 43.3% | 51.9% |
| B0 | PUT | 1 KiB | 32 | 47.5% | 50.6% |
| R1 | PUT | 64 KiB | 32 | 39.6% | 36.9% |
| R1 | PUT | 1 KiB | 32 | 36.6% | 30.1% |
| B2 | PUT | 64 KiB | 32 | 14.8% | 26.6% |
| B0 | GET | 16 MiB | 32 | 21.1% | 0.1% |

## Q2. What limits throughput?

Per cell, from the samplers: client host CPU ≥ 85% → client CPU; PUT MiB/s ≥ 90% of the EBS throughput cap or ≥ 75% of its IOPS cap (2 writes per PUT) → disk; MinIO CPU ≥ 85% of the server's cores → server CPU; ≥ 80% of the measured link → network; otherwise the cell is latency-bound (closed loop, not saturated).

- latency (not saturated): 98 cells
- network: 25 cells
- disk throughput (EBS cap): 25 cells
- server CPU: 8 cells
- disk IOPS (EBS cap): 2 cells
- client CPU: 2 cells

| Size | Workers | Op | Client host CPU (P1) | MinIO CPU (P1, % of one core) | MiB/s (P1) | Limit (P1) |
|---|---|---|---|---|---|---|
| 1 KiB | 1 | PUT | 1% | 33% | 0 | latency (not saturated) |
| 1 KiB | 1 | GET | 3% | 39% | 0 | latency (not saturated) |
| 1 KiB | 4 | PUT | 5% | 96% | 0 | latency (not saturated) |
| 1 KiB | 4 | GET | 11% | 146% | 1 | latency (not saturated) |
| 1 KiB | 16 | PUT | 13% | 229% | 1 | latency (not saturated) |
| 1 KiB | 16 | GET | 56% | 514% | 6 | latency (not saturated) |
| 1 KiB | 32 | PUT | 26% | 469% | 2 | latency (not saturated) |
| 1 KiB | 32 | GET | 80% | 736% | 8 | server CPU |
| 64 KiB | 1 | PUT | 1% | 32% | 6 | latency (not saturated) |
| 64 KiB | 1 | GET | 2% | 41% | 20 | latency (not saturated) |
| 64 KiB | 4 | PUT | 4% | 101% | 23 | latency (not saturated) |
| 64 KiB | 4 | GET | 11% | 157% | 88 | latency (not saturated) |
| 64 KiB | 16 | PUT | 13% | 257% | 58 | latency (not saturated) |
| 64 KiB | 16 | GET | 56% | 563% | 337 | latency (not saturated) |
| 64 KiB | 32 | PUT | 24% | 492% | 121 | latency (not saturated) |
| 64 KiB | 32 | GET | 77% | 788% | 473 | server CPU |
| 1 MiB | 1 | PUT | 1% | 30% | 50 | latency (not saturated) |
| 1 MiB | 1 | GET | 4% | 44% | 205 | latency (not saturated) |
| 1 MiB | 4 | PUT | 5% | 107% | 179 | latency (not saturated) |
| 1 MiB | 4 | GET | 15% | 174% | 835 | latency (not saturated) |
| 1 MiB | 16 | PUT | 13% | 294% | 447 | disk throughput (EBS cap) |
| 1 MiB | 16 | GET | 44% | 325% | 1474 | network |
| 1 MiB | 32 | PUT | 15% | 301% | 449 | disk throughput (EBS cap) |
| 1 MiB | 32 | GET | 49% | 332% | 1474 | network |
| 16 MiB | 1 | PUT | 4% | 66% | 193 | latency (not saturated) |
| 16 MiB | 1 | GET | 6% | 43% | 620 | latency (not saturated) |
| 16 MiB | 4 | PUT | 11% | 194% | 491 | disk throughput (EBS cap) |
| 16 MiB | 4 | GET | 18% | 111% | 1477 | network |
| 16 MiB | 16 | PUT | 14% | 218% | 491 | disk throughput (EBS cap) |
| 16 MiB | 16 | GET | 28% | 128% | 1475 | network |
| 16 MiB | 32 | PUT | 14% | 217% | 483 | disk throughput (EBS cap) |
| 16 MiB | 32 | GET | 31% | 131% | 1471 | network |

## Q3. Anything unusual?

- Failed requests: 0
- Client-bound runs (flagged by the runner): 10
- Unsaturated cells whose median latency drifts >10% between the halves of a run (drift in saturated cells is expected queueing): 1 (P1 get 1 KiB c1)

## Q4. First look at the hypotheses (pilot values, direction only)

**H3** RSA-4096 GET median latency vs ML-KEM-768 (1 worker):

- 1 KiB: R1 4.85 ms vs P1 2.89 ms (+68%)
- 64 KiB: R1 4.96 ms vs P1 3.05 ms (+62%)
- 1 MiB: R1 6.89 ms vs P1 4.81 ms (+43%)

**H2** Key-establishment share of P1 PUT time (1 worker):

- 1 KiB: 0.60%
- 64 KiB: 0.52%
- 1 MiB: 0.29%
- 16 MiB: 0.11%

**H1** |P1 − B2| median latency, ≥ 1 MiB, 1 worker (hypothesis: < 5%):

- PUT 1 MiB: +0.6%
- GET 1 MiB: +1.1%
- PUT 16 MiB: -3.8%
- GET 16 MiB: -1.1%

**H4** Client CPU per request, P1 − B1 (1 KiB PUT):

- 1 workers: +0.075 ms/request (P1 1.302, B1 1.227)
- 4 workers: +0.085 ms/request (P1 1.306, B1 1.221)
- 16 workers: +0.081 ms/request (P1 1.406, B1 1.325)
- 32 workers: +0.101 ms/request (P1 1.471, B1 1.370)

## Recommendations for Phase 8

- **Repetitions:** 10 per cell (37 cells exceed the 5% CV rule)
- **Durations:** keep 10 s warm-up + 30 s measured; 1 cells drift > 10% within a run, so check warm-up length there
- **Data volume:** the pilot wrote ~31 GB of raw records (1.7 GB compressed). The final matrix is several times larger; raw records are now compressed at the end of each experiment, and the client disk (60 GB) must hold the uncompressed file until then.

_Generated by `analysis/pilot_report.py`; tables in `cells.csv` and `runs.csv`._
