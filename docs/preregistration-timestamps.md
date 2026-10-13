# Pre-registration timestamps

Each pre-registration is an entry in the versioned project specification
(`docs/build_sot.py`, built into `docs/source-of-truth.pdf`). The times below are from GitHub's
repository activity log (`gh api repos/revanthreddy0906/pqc-object-store/activity`), which
records when each commit was pushed and which the authors cannot edit. Commit author dates are
not used, because an author can set them freely.

| Version | Content | Commit | Pushed (UTC) | First run of the data it governs (UTC) |
|---|---|---|---|---|
| v1.8 | Confirmatory campaign: primary family, TOST, Holm, repetitions, stall rule, queueing split, session grid, batches E–I | `33ea9ce` | 2026-10-10 16:19:00 | Batch E, first attempt: 2026-10-11 11:53:06 (discarded); second: 2026-10-11 17:09:50 |
| v1.11 | Batch J (padded-manifest control) with its decision rule; batch K (64 KiB PUT, 50 repetitions) | `7741ece` | 2026-10-13 05:16:05 | Batch J: 2026-10-13 05:31:22 |
| v1.12 | Batch L (binding controls H1, G1) with its decision rule; predictions for the CPU decomposition | `f0c6b77` | 2026-10-13 05:36:24 | Batch L: after batches J and K |
| v1.13 | Diagnostic batches M and MT (allocator hypothesis); disclosure of overlapping transfers | `a21babe` | 2026-10-13 (see activity log) | Batches M, MT: after batch L |

## Limits of this evidence

- **The repository is private.** A reader cannot check the activity log until it is made
  public. Publishing it later does not change the recorded push times.
- **v1.12 was pushed five minutes after batch J started.** It governs batch L, which had not
  started, and it fixes a prediction for batch J's ML-KEM/X25519 ratio. No batch J data had been
  downloaded or analysed at that point; only the request counts of its first two runs had been
  seen in the run log. This is stated in the v1.12 entry itself.
- **Analyses not pre-specified** are listed in the paper (Section VI-H) and are exploratory.
- GitHub's activity log is retained by the service, not by an independent registry such as OSF.
  It is third-party evidence, but not a formal registration.
