# Response to the Revision and Literature-Gap Report

> **Superseded in part.** This letter describes the first revision. Later experiments (batches J to
> N) changed several statements below: the two under-powered cells were re-run with 50
> repetitions and are equivalent, a native reader was added, and the cause of the client-bound
> deficit was identified. Table and section numbers below refer to that earlier version. For the
> current results and open points see the addendum of `paper/audit-response.md`.

Manuscript: *Benchmarking Post-Quantum Key Encapsulation in S3-Compatible Object Storage under
Client Concurrency*.

This letter maps every issue in the report to the change made. Section numbers refer to the
revised manuscript (`paper/main.tex`) as it stands after the later audit revision (`paper/audit-response.md`), which renumbered several tables and sections. Every number below is produced by
`analysis/revision_assets.py` from the per-run summaries in `results/revision/` and
`results/revision-arm/`.

## Summary of the revision

- A second, **pre-registered confirmatory campaign** was run: 1,495 runs and 97.6 million
  requests with no failed request, on an x86 client and an ARM client. The pre-registration
  (primary cells, test, margin, multiplicity correction, repetitions, stall rule, queueing split,
  session grid) was committed as version 1.8 of the project specification before any of the new
  data existed (commit `33ea9ce`).
- The original 1,970 runs are kept as an **exploratory campaign** and are never pooled with the
  new data. They ran in another AWS region on another account.
- The headline result changed in form and in strength. It was "equivalent in 38 of 44 cells";
  it is now "equivalent in 6 of 8 pre-specified cells on each architecture, inconclusive in 2,
  non-equivalent in none", with a measured 4.0–4.9 % deficit where the client CPU is the
  bottleneck.

## Point-by-point

| # | Issue in the report | What we did | Where |
|---|---|---|---|
| 1 | Novelty not systematically established | Added a scope matrix of related work with peer-reviewed/preprint labels, a known / unknown / contribution passage, and a logged keyword search (`docs/literature-search.md`), which also surfaced one further preprint that is now cited. | Sec. I, Sec. III, Table I |
| 2 | Informal statistical equivalence | Replaced the interval rule with paired TOST on log throughput ratios, bounds [0.95, 1.05], alpha = 0.05; the 90 % interval decides and the 95 % interval is shown. Hypotheses and the smallest effect of interest are stated. | Sec. VI-F, Table X, Fig. 4 |
| 3 | Only five repetitions | Primary cells were re-run with 10 repetitions, 20 at the knee cell, sized by a power calculation from the earlier data, with no optional stopping. | Sec. VI-F |
| 4 | Limited external validity | Added a second client architecture (ARM, Graviton3) for the primary family. No native client and no distributed store were added; all general claims were narrowed instead. | Sec. VI-B, IX-D, IX-E, XI |
| 5 | MinIO bottleneck inferred indirectly | Profiled the server directly: system-call tracing, disk latency and queue depth, CPU sampling. The ceiling is attributed to lock and namespace contention in the metadata path, not the disk. | Sec. VII-C, Table IX |
| 6 | Run-to-run variability and stalls | Per-run ratios are plotted for every primary cell; a stall rule fixed in advance and blind to the mode is applied as a sensitivity analysis; an order/time regression is reported. Per-cell mean, median, SD, quartiles and range of the paired ratios are in `results/revision/robustness.csv`. | Sec. IX-A to IX-C, Fig. 4 |
| 7 | Queueing stops at "M/M/c fails" | Added a state-dependent model and a load-dependent fit, trained on alternate rates and scored on held-out rates. | Sec. VII-I, Table XIX, Fig. 5 |
| 8 | Session amortization lacks a security cost | Swept B_max x T_max and report observed KEM operations per object and objects and bytes per root (median, p95, max) beside CPU, throughput and p99; added threat scenarios and a decision rule. | Sec. VIII, Table XX |
| 9 | Hybrid mode underdeveloped | Implemented X-Wing (draft-connolly-cfrg-xwing-kem-11), verified against the draft's test vectors, and measured it across the primary cells on both architectures and an 18-workload matrix from 1 KiB to 128 MiB. The earlier hybrid is relabelled a study-specific concatenation hybrid with no security claim. | Sec. II-B, IV-B, VII-F, Tables XV and XVI |
| 10 | Security and performance claims mixed | Added a claim taxonomy table. | Sec. IV-F, Table III |
| 11 | "Handshake" terminology | Replaced throughout by "per-object key-establishment time". The old name appears once, as a loose synonym to avoid. | Sec. VI-D and throughout |
| 12 | Metadata not scaled | Added fleet totals for 1 M, 100 M and 1 B objects in decimal and binary units, shares of payload, and a discussion of replication, request billing and the second S3 object. | Sec. VII-H, Table XVIII |
| 13 | Conclusions too broad | Abstract, discussion and conclusion now name the client stack, the single-node store and the cloud provider, and state what the results must not be extended to. | Abstract, Sec. X, XI |
| 14 | Contribution hierarchy unclear | Added a one-sentence thesis and contributions in order (C1–C3 after the later audit revision, which demoted the queueing analysis to a supporting observation); research questions and results are aligned with them. The architecture is presented as support for C1, not as a cryptographic contribution. | Sec. I |

## Results the reviewer should know about

**Primary family (ML-KEM-768 / X25519 throughput, Holm-adjusted over 8 cells per client).**

| Cell | x86 ratio (90 % CI) | x86 verdict | ARM ratio (90 % CI) | ARM verdict |
|---|---|---|---|---|
| 64 KiB GET, 128 workers | 1.001 (0.998–1.004) | Equivalent | 1.000 (0.997–1.003) | Equivalent |
| 64 KiB GET, 500 workers | 0.960 (0.959–0.962) | Equivalent | 0.951 (0.950–0.953) | Inconclusive |
| 64 KiB PUT, 32 workers | 1.017 (0.987–1.048) | Inconclusive | 1.001 (0.968–1.036) | Equivalent |
| 64 KiB PUT, 128 workers | 1.000 (0.939–1.064) | Inconclusive | 1.026 (0.943–1.117) | Inconclusive |
| 1 MiB PUT, 32 workers | 1.001 (0.984–1.018) | Equivalent | 0.992 (0.979–1.004) | Equivalent |
| 1 MiB GET, 32 workers | 1.000 (0.998–1.002) | Equivalent | 0.998 (0.996–1.000) | Equivalent |
| 16 MiB PUT, 32 workers | 0.998 (0.993–1.002) | Equivalent | 0.995 (0.987–1.004) | Equivalent |
| 16 MiB GET, 32 workers | 1.000 (0.999–1.001) | Equivalent | 1.001 (1.000–1.001) | Equivalent |

We report three things that do not flatter the result:

- **A real deficit at 64 KiB GET with 500 workers.** ML-KEM is 4.0 % slower on x86 and 4.9 %
  slower on ARM, with very narrow intervals. On x86 it is inside the margin; on ARM the interval
  touches the bound. It fails the ±2 % sensitivity check on both.
- **Under-powered cells.** The two 64 KiB PUT cells have ratios near 1 but paired standard
  deviations of 8–15 %. At the observed variance, ten repetitions give the 128-worker cell a
  power of about 3 %; about 50 would be needed. Our power calculation used the earlier
  campaign's lower variance and was too optimistic for that cell.
- **One verdict depends on a stalled run.** Excluding stalled runs and re-applying the Holm
  correction leaves all 8 x86 verdicts unchanged but turns the ARM knee cell (64 KiB PUT, 32
  workers) from equivalent to inconclusive (adjusted p = 0.076).
- **X-Wing is not free.** In the client-bound cell it is 9.6 % (x86) and 10.4 % (ARM) slower than
  X25519, outside the margin. It is equivalent from 1 MiB upward.

## Two points where we differ from the report

1. **The original rule was stricter, not looser, than TOST at alpha = 0.05.** A 95 % interval
   lying inside ±5 % corresponds to TOST at alpha = 0.025. Moving to the standard presentation
   (90 % interval, alpha = 0.05) is therefore a change of presentation and of rigour in
   pre-specification and multiplicity control, not a weakening of the criterion.
2. **"Handshake overhead" is kept once.** The term appears a single time, as a loose synonym
   the paper says it avoids, so that readers who know the metric by that name can match it;
   "per-object key-establishment time" is used everywhere else.

## Deviations from the pre-registration

- The first attempt at batch E stopped after 134 of 300 runs, when a spending guard on the cloud
  account halted both instances. That partial data was never downloaded or analysed. The batch
  was restarted from its first run with the same configuration and seed.
- The profiling batch was run twice (once under system-call tracing, once under CPU sampling),
  because the first CPU profiles kept too little detail.
- The stall rule is applied to closed-loop runs only.

Analyses that the pre-registration did not fix, and that are therefore exploratory: Holm
correction on the ARM family; the knee defined as twice the light-load response time; the
functional form of the load-dependent queueing model; and the order/time regression. The paper
lists these in Sec. VI-H.

## What the revision does not do

- **No native client.** Absolute key-establishment times include the Python binding's call
  overhead. The paper says so and limits its claims accordingly.
- **No distributed or second S3 implementation.** MinIO ran as a single node.
- **Function-level attribution inside MinIO.** The CPU profiler could not resolve symbols in the
  MinIO binary, so the write ceiling is attributed to a subsystem (lock and namespace contention
  in the metadata path), not to a named function.
- **The queueing knee is not predicted.** The state-dependent model halves the held-out error of
  M/M/c below the knee but still places the knee too high; the paper reports this as a negative
  result.
- **A reverse-order schedule.** Mode order was randomized within every repetition and an
  order/time regression is reported, but no block was repeated in reversed order.
- **Intervals on the queueing-model parameters.** Only point estimates and held-out errors are
  given, and there are just 3 and 2 stable held-out rates per object size.
- **Per-upload system-call counts.** The tracing windows include the deletion of objects after
  each run, so only shares of calls and of traced time are reported.
- **Literature search of IEEE Xplore and the ACM Digital Library.** The search described in the
  paper covers arXiv and the open web only. The subscription databases still have to be searched
  by the authors before submission; the novelty statement is worded "to our knowledge" for that
  reason.
