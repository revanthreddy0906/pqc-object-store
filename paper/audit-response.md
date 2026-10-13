# Response to the Q1 Audit (13 October 2026)

Manuscript: *Benchmarking Post-Quantum Key Encapsulation in S3-Compatible Object Storage under
Client Concurrency* (`paper/main.tex`, 18 pages in IEEE conference format).

**Read the addendum at the end first.** Sections A to E below were written before batches J to N existed and before the second audit; table and section numbers in them refer to the manuscript at commit `4c385e8`. The addendum records what the new experiments showed, what the second audit changed, and what is still open.

This document holds deliverables A, C, D and E and the change log. Deliverable B is the revised
manuscript itself. No new experiment was run for this revision: every new number comes from
re-analysing data that already existed, through `analysis/revision_assets.py`. Experiments the
audit asks for that were not run are listed in section C and in Section IX-F of the paper, and
no expected outcome is presented as a result.

## How the audit's recommendations were checked

Each major criticism was tested against the data or a primary source before acting on it.

| Audit claim | Check | Outcome |
|---|---|---|
| Six of eight primary cells cannot show an effect of the mode | Bottleneck of each cell, from client and server CPU and network use | **Confirmed, and it is seven.** Only 64 KiB GET at 500 workers saturates the client; at 128 workers the client still has spare CPU |
| The 4 % deficit is "probably not the KEM" | Stage timers at one worker (batches F, I1) | **Supported, not proven.** Decapsulation is 2–5 µs faster than X25519; manifest handling is 6 µs slower on GET and 16 µs on PUT |
| C1's isolation claim does not hold | Manifest sizes per mode | **Confirmed.** 622 to 2,085 bytes. Claim rewritten |
| Penalty ≈ extra CPU per request ÷ total | Inverse CPU ratio against observed ratio, 64 KiB GET, same runs | **Holds at saturation** (within 0.9 points at 500 workers, both architectures), but it is an accounting identity there, not a prediction; it overstates the loss by 1.8–3.0 points at 128 workers, where the client is not saturated. Presented as a decomposition, not as a model with predictive status |
| Knee range in the abstract contradicts Table XVI | Recomputed both quantities | **Confirmed.** 0.75–0.82 was the stability boundary; the knee at 64 KiB is 0.68–0.75 |
| P2 manifest 2,091 vs 2,085 bytes | Source records | **Not an error.** Recorded for a 1 MiB object in one table and a 1 KiB object in the other; the manifest embeds object-dependent fields. The exact composition of the 6 bytes was not traced |
| "No failed request" contradicts open-loop failure rule | Failure counts of the 185 open-loop runs | **Claim stands.** 0 failures; every queued request was served in the drain window. Now stated explicitly |
| Identical MAPEs may be a rounding artifact | One more decimal | **Not identical:** 7.5 vs 7.6 % and 4.4 vs 4.5 % |
| S3 user-metadata limit is about 2 KB | AWS S3 User Guide | **Confirmed:** 2 KB. Our JSON manifests are at or above it |
| HPKE draft lists ML-KEM-768 and an X25519 hybrid | draft-ietf-hpke-pq-03 | **Confirmed:** ML-KEM-768 and MLKEM768-X25519 |
| Schroeder et al. establishes the open/closed lesson | NSDI 2006 paper | **Confirmed.** Cited; queueing demoted |
| Margin justification is circular | Re-read | **Accepted.** Replaced by a provisioning argument, labelled post hoc |

Recommendations **not** followed, with reasons:

- **Citing "The Tail at Scale", COSBench, pqm4 and eBACS.** None would support a statement the
  paper makes. Adding them would pad the reference list.
- **False-discovery correction applied to Table XIII's marks.** The marks stay unadjusted, as in
  the earlier version; the caption now reports how many survive Benjamini–Hochberg at 5 %
  (50 of 66 among 162 ratios).
- **Dropping the 64 KiB PUT cells from the confirmatory family.** They were pre-registered.
  Removing them after seeing the data would be worse than reporting them as under-powered.
- **Venue quartiles and impact factors.** The audit could not verify them and neither can we
  without Journal Citation Reports access. No venue claim is made.

## A. Prioritized checklist

Status: **Done** = changed in the manuscript using existing data or sources. **Partial** = the
claim is corrected and the gap disclosed, but the experiment is outstanding. **Pending** = needs
work only the authors or new experiments can supply.

### Major

| ID | Finding | Action taken | Status | Where |
|---|---|---|---|---|
| M1 | Public-key KEM per object not motivated | Added the deployments that need it (write-only producers, multiple recipients or escrow, cross-organization hand-off) and stated that a shared symmetric key needs no KEM (baseline B1) | Done | Sec. I |
| M2 | HPKE not discussed | Added HPKE background, a subsection mapping the envelope to HPKE base mode with its three differences, a row in the claim taxonomy, and a statement that HPKE was not benchmarked | Partial | Sec. II-C, IV-E, Table III |
| M3 | Primary family dominated by cells where the KEM cannot matter | Stated as a limitation in Methods, Results, Findings, abstract and conclusion (seven of eight cells). Added client CPU per request as an exploratory second endpoint for all 8 cells | Partial | Sec. VI-F, VII-D, Table XI |
| M4 | Python client defines the only informative regime | Stated that the client is part of the instrument and that the direction of the change on a native client is unknown. Not measured | Pending | Sec. I, IX-E, IX-F |
| M5 | Deficit unexplained; isolation claim false | Isolation claim rewritten. New subsection with a CPU decomposition and a one-worker stage comparison. It rules out decapsulation and names manifest handling as the largest measured stage difference; most of the extra CPU stays unattributed. Padded-manifest control not run | Partial | Sec. IV-B, VII-E, Tables XIII, XIV |
| M6 | Queueing not novel, thin validation | Removed as contribution C4, retitled, cited Schroeder et al., knee and stability boundary reported separately, limits on the held-out points stated | Done | Sec. I, VII-I |
| M7 | No URL, DOI or external timestamp | The paper now says the repository is not yet public and that identifiers are required before submission | Pending | Artifact section |

### Moderate

| Finding | Action taken | Status |
|---|---|---|
| Knee vs stability boundary | Two named quantities, each with its own range | Done |
| P2 manifest 2,091 vs 2,085 B | Explained in the caption of Table VII | Done |
| "No failed request" | Verified (0 failures in 185 open-loop runs) and stated | Done |
| Circular margin justification | Replaced with a provisioning argument, labelled as made after the fact | Done |
| Under-powered small-PUT cells | Already reported with achieved power; now also listed as a required experiment | Partial |
| Distributional assumption | Percentile-bootstrap check: agrees in 15 of 16 cells | Done |
| Unadjusted exploratory tables | Caption of Table XVI reports the false-discovery count | Done |
| S3 metadata-size limit | Verified and stated, with its consequence for a single-object design | Done |
| Baseline set | Stated as a limitation and a required experiment | Pending |
| 20-second windows | Already a stated limitation; long runs listed as required | Pending |
| Preprint-only primitive citations | Kyber design paper (EuroS&P 2018) and FIPS 203 now lead that paragraph | Done |
| Abstracts-only reading of two preprints | Unchanged: both are still described "according to its abstract" | Pending |

### Minor

| Finding | Action taken | Status |
|---|---|---|
| Duplicated Prometheus sentence | Merged | Done |
| "Assignment" wording | Removed; the alias is kept in neutral words | Done |
| B_max undefined in abstract | Sessions removed from the abstract | Done |
| Chunk vs part size in Algorithm 1 | 4 MiB chunks and 8 MiB upload parts now on separate lines | Done |
| Fig. 3 shows exploratory data | Kept and labelled exploratory; the confirmatory campaign has no full concurrency sweep | Not changed |
| Correlation used as attribution | Demoted to a parenthesis that says it is not evidence of cause | Done |
| Abstract too dense | Cut from about 20 numbers to 9 | Done |
| Funding, conflict, contribution, AI-use statements | Not written: these are the authors' declarations | Pending |

## C. Experiments and evidence still required

Ordered by how much each would change the paper. Estimates assume the existing AWS testbed
scripts.

| # | Experiment | Why | Design | Est. effort and cost |
|---|---|---|---|---|
| 1 | **Padded-manifest control** | Separates ciphertext size from KEM computation; decides whether the paper can say "the KEM is free, its metadata is not" | New mode: X25519 with the manifest padded to 2,034 B. 64 KiB GET at 128 and 500 workers, with B2 and P1, 10 repetitions | 1 day of code, about 2 h and $6 of AWS |
| 2 | **Native client** | The only informative regime is a saturated client, and ours is interpreted; whether the deficit grows or shrinks without the interpreter is unknown | Go, Rust or C client for the client-bound cells; new pre-registered family; client CPU per request co-primary | 2–3 weeks of development |
| 3 | **64 KiB PUT with about 50 repetitions** | Those two cells had 3 % and 73 % power | Same cells, about 50 repetitions | About 3 h and $8 of AWS |
| 4 | **HPKE-conformant envelope** | Confirms that per-object costs transfer to the standard construction | Replace key schedule and nonce derivation; re-run one-worker cells | 1 week |
| 5 | **Wider baselines** | ML-KEM-1024, RSA-3072, remote key-service wrap | Add modes; one-worker cells and the client-bound cells | 1 week |
| 6 | **Second store or distributed MinIO** | Store-side results rest on one archived single-node server | One object size, closed and open loop | 2–3 weeks |
| 7 | **Long runs** | 20 s windows hide compaction and memory growth | 10–30 min in one PUT cell | 1 day |
| 8 | **Full-text reading of [23] and [24]** | Both are characterized from abstracts | Read and revise two sentences | 2 hours |

Items 1 and 3 can be run with what exists today. They were not run for this revision because
they need the AWS account's spending limit raised again and incur cost; they need the authors'
decision.

## D. Citation and reference verification report

Checked in this revision (13 October 2026). "Verified" means the bibliographic details were
confirmed against the publisher, an official repository or the document itself.

### Added

| Key | Reference | Verified against | Used for |
|---|---|---|---|
| `rfc9180` | Barnes, Bhargavan, Lipp, Wood. *Hybrid Public Key Encryption.* RFC 9180, Feb. 2022 | RFC Editor | HPKE background and mapping |
| `hpkepq` | Barnes, Connolly. *Post-Quantum and Post-Quantum/Traditional Hybrid Algorithms for HPKE.* draft-ietf-hpke-pq-03, Nov. 2025 | The draft text | ML-KEM-768 and MLKEM768-X25519 as HPKE KEMs |
| `schroeder2006` | Schroeder, Wierman, Harchol-Balter. *Open Versus Closed: A Cautionary Tale.* NSDI 2006, pp. 239–252 | USENIX | Open- vs closed-loop behaviour |
| `hoefler2015` | Hoefler, Belli. *Scientific Benchmarking of Parallel Computing Systems.* SC 2015, 73:1–73:12 | Author's publication page, DOI | Reporting rules |
| `lakens2017` | Lakens. *Equivalence Tests: A Practical Primer.* SPPS 8(4):355–362, 2017 | PubMed Central | Choosing equivalence bounds |
| `bos2018` | Bos et al. *CRYSTALS-Kyber: A CCA-Secure Module-Lattice-Based KEM.* IEEE EuroS&P 2018, pp. 353–367 | CWI repository, ePrint | Peer-reviewed primitive reference |
| `s3metadata` | AWS. *Working with object metadata.* S3 User Guide | The page | 2 KB user-metadata limit |

### Corrected

- **Rodriguez-Alvarez (arXiv:2508.01694)** is a single-author preprint. The table had
  "Rodriguez et al."; corrected in the previous revision and kept.

### Existing references: status

| Refs | Status |
|---|---|
| FIPS 203, SP 800-38D, RFC 5869, RFC 8017, RFC 7748 | Standards; details verified in earlier revisions |
| X-Wing draft-11; Barbosa et al. (IACR CiC 1(1)) | Verified earlier; the audit independently confirmed the draft's date |
| Paquin 2020, Sikeridis 2020, Sosnowski 2023, Giron 2023, Gadban 2021, Henziger 2019 | Bibliographic details verified earlier. **Their characterization in the paper was checked against abstracts and open versions, not against every full text** |
| Ozeri et al. (SYSTOR 2023) | A one-page abstract. Cited only for the claim in its title |
| Prikutse 2026, Junaid 2026 | Exist on arXiv. Described from abstracts only, and the paper says so |
| Demir 2025, Lopez 2025, Rodriguez-Alvarez 2025 | arXiv preprints, labelled as such in Table I |
| Schuirmann 1987, Holm 1979, Dixon 2018 | Verified in the previous revision |
| MinIO repository | The archive status of the community edition was not re-verified in this revision |
| Vendor documentation (S3 Encryption Client, Azure, Bucket Keys, Encryption SDK) | Appropriate for what they support; URLs not re-fetched in this revision |

### Not added, deliberately

The Tail at Scale, COSBench, pqm4, eBACS/SUPERCOP. See "Recommendations not followed".

## E. Final compliance checklist

### Unresolved weaknesses (scientific)

1. **External validity is unchanged.** One interpreted client, one single-node store, one
   provider. The regime where modes differ is the one most affected by the client implementation.
2. **The cause of ML-KEM's client-bound cost is indicated, not established.** Stage differences
   at one worker are about 10 µs; the CPU difference at 500 workers is 79 µs (x86) and 109 µs
   (ARM). The padded-manifest control is not run.
3. **The CPU decomposition is an identity on the runs it describes.** It has no predictive
   status until tested on a configuration it was not computed from.
4. **A 5 µs key-derivation difference between modes is unexplained**, as is the 1 MiB one-worker
   slowdown of the hybrids.
5. **Two primary cells are inconclusive and one ARM verdict depends on a stalled run.**
6. **Seven of eight primary cells could not have failed.** This is disclosed, not repaired.
7. **The envelope is not HPKE**, and HPKE was not benchmarked.
8. **Queueing results rest on 3 and 2 held-out points and one mode.**
9. **The literature search did not cover IEEE Xplore or the ACM Digital Library.**

### Before submission (administrative)

| Item | Owner | Status |
|---|---|---|
| Choose the target journal and read its author guidelines, page limit and template | Authors | Open. The paper is 18 pages in conference format |
| Verify the journal's quartile and Web of Science indexing through library access | Authors | Open |
| Public repository with a DOI (for example Zenodo) for code and per-run summaries | Authors | Open |
| Deposit or describe access to the raw records (about 11 GB) | Authors | Open |
| External timestamp for the pre-registration | Authors | Open. The commit history shows the order, but only inside our own repository |
| Funding statement, conflict-of-interest statement, author contributions | Authors | Open |
| **Disclosure of generative-AI use**, as the target journal requires | Authors | Open. An AI assistant was used extensively for code, analysis and drafting in this project; this must be disclosed accurately |
| Search of IEEE Xplore and the ACM Digital Library | Authors | Open |
| Plagiarism and text-overlap check | Authors | Open. None was run |
| Back up the raw data | Authors | Open |

### Reporting-standard check (Hoefler and Belli, SC 2015, as applicable)

| Rule | Met? |
|---|---|
| Report the experimental unit and the number of repetitions | Yes |
| Report intervals, not single numbers | Yes |
| State hardware, software versions and configuration | Yes |
| Do not summarize ratios with arithmetic means | Yes (geometric means of paired ratios) |
| Report all results, including unfavourable ones | Yes |
| Make the artifact available | **No** (not yet public) |

## Change log: substantial revisions

| # | Original issue | Change | How it answers the audit |
|---|---|---|---|
| 1 | Abstract carried about 20 numbers, used an undefined symbol and gave the stability boundary as the knee | Rewritten around four points: per-object time, the equivalence result with its caveat, the saturated-client deficit and its cause, scope | Sec. 8 items 1 and wording; Sec. 10 |
| 2 | Introduction did not say why a public-key KEM is needed | New paragraph on deployments that need it | M1 |
| 3 | The unknown was stated as if the result were not predictable | The introduction now concedes the back-of-envelope estimate and states what it cannot tell | Sec. 4 |
| 4 | Four contributions, the fourth not about post-quantum cryptography | Three contributions; C2 gains the CPU decomposition; queueing named as a supporting observation | M6 |
| 5 | "Differences isolate key establishment" | Replaced by "key establishment together with the handling of its ciphertext" | M5, 6.3 |
| 6 | No HPKE | Background subsection, design subsection, claim-taxonomy row, related-work paragraph | M2 |
| 7 | Margin justified by between-session drift | Provisioning argument tied to the measured stability boundary, labelled post hoc | 7.4 |
| 8 | Primary family presented without its limitation | Limitation stated where the family is defined and where it is reported | M3 |
| 9 | No sensitivity to the normality assumption | Bootstrap check | 7.5 |
| 10 | Deficit reported without mechanism | New subsection "Why the Saturated Client Is Slower": CPU decomposition, stage comparison, two tables, and an explicit statement of what is and is not established | M5, 7.2, Sec. 4 |
| 11 | Throughput the only endpoint in the primary family | Table of client CPU per request for all 8 cells | 7.1 |
| 12 | Correlation offered as attribution | Demoted and caveated | 7.8 |
| 13 | Unadjusted marks in the hybrid matrix | Caption gives the false-discovery count | 7.6 |
| 14 | Single-object alternative asserted without checking the limit | S3's 2 KB limit cited, with its consequence | 6.6 |
| 15 | Queueing presented as a contribution, with one range for two quantities | Retitled, scoped, two named thresholds, prior work cited, MAPE to one decimal | M6, 7.7, Sec. 8 item 1 |
| 16 | Limitations did not name the experiments needed | New subsection "Experiments Still Required" | Instruction 6; roadmap |
| 17 | Discussion said only that the deficit exists | New paragraphs: an operator procedure, and a hypothesis about where the cost comes from, labelled as a hypothesis | Sec. 10 |
| 18 | Conclusion ended on a list of future work | Conclusion states the scope and names the decisive open experiment | Sec. 8 |
| 19 | Artifact section implied availability | States that the repository is not public and has no identifier | M7 |
| 20 | Two analysis lists claimed more pre-specification than there was | The list of analyses that were not pre-specified now includes the new ones | Integrity |


---

# Addendum (13 October 2026, evening): second audit and batches J to N

## What was run

Five pre-registered batches on a fresh x86 testbed, plus a native client. Every
pre-registration was pushed to GitHub before the first run of the batch it governs; the push
times are in `docs/preregistration-timestamps.md`.

| Batch | Runs | Question | Result by the pre-registered rule |
|---|---|---|---|
| J | 120 | Does a manifest as large as ML-KEM's explain the Python client's deficit? | **No.** Padding costs 0.7 % (ratio 0.993, 90 % CI 0.991–0.995); ML-KEM is still 3.3 % slower than the padded control. Manifest size accounts for 17 % of the deficit (CI 14–21 %) |
| K | 200 | Are the two 64 KiB PUT cells equivalent with adequate power (50 repetitions)? | **Yes, both.** 0.994 (0.984–1.004) at 32 workers, 0.996 (0.979–1.013) at 128; unchanged without stalled runs |
| L | 120 | Does the Python library binding explain the deficit? | **Yes.** ML-KEM through one foreign call reaches 0.999 (0.997–1.002) of X25519's throughput; through the binding, in the same batch, 0.963 (0.960–0.967). Holding or releasing the interpreter lock makes no difference |
| M, MT | 40 | Is the 1 MiB one-worker anomaly an allocator effect? | **Supported.** AES-GCM stage time varies 3.2-fold between modes with the default allocator and 1.1-fold with a fixed mmap threshold |
| N | 90 | Does a native (Go) reader show a deficit when saturated? | **Yes, a larger one.** On one core: ML-KEM 0.905 (0.900–0.910), X-Wing 0.826 (0.821–0.831) of X25519's throughput |

All 570 runs completed without a failed request. The testbed was destroyed afterwards; no
instance, disk or snapshot remains.

## How the paper's thesis changed

- **Before:** ML-KEM is 4–5 % slower on a saturated client; the cause is probably its larger
  manifest; unproven.
- **Now:** on x86, the Python client's deficit is an artifact of the binding, which makes four foreign
  calls per decapsulation. The manifest is a minor part. A native client does show a cost
  (9.5 % for ML-KEM, 17.4 % for X-Wing on one core). A slower ML-KEM key recovery in Go's
  standard library accounts for about half of that (17 of 36 µs for ML-KEM, 52 of 72 µs for
  X-Wing); the rest was not measured separately. In every case the throughput ratio equals the inverse
  ratio of client CPU per request. The cost is a property of the implementation and appears only
  under client saturation; it ranged from none to 9.5 % for ML-KEM. In no saturated cell was
  ML-KEM faster than X25519. Both controls ran on x86 only.

The earlier text's leading hypothesis (the manifest) was wrong. It was labelled a hypothesis and
is now reported as refuted for the most part.

## Second audit: findings and actions

| ID | Finding | Action | Status |
|---|---|---|---|
| C1 | Mechanism 87 % unattributed | Batches J and L, with decision rules fixed in advance. The audit's binding hypothesis was confirmed in the library source (four foreign calls per decapsulation) and then by experiment | **Resolved** for the Python client |
| C2 | Only informative effect measured on an instrument that may cause it | Batch N with a Go reader. The Python effect was indeed caused by the instrument; the native client shows a different, larger effect of its own | **Partly resolved**: GET path, three modes, one object size, saturation on one core only |
| C3 | Pre-registration timing unverifiable; artifact not public | GitHub's push log shows the first pre-registration pushed 19 hours before the first run; times are recorded. The repository is still private | **Partly resolved**; making it public is the authors' step |
| J1 | Primary family mis-targeted | Stated wherever the result appears (seven of eight cells could not show an effect) | Done (disclosure) |
| J2 | 1,412 bytes conflates encoding with ciphertext | Now reported separately: 1,056 bytes intrinsic, 356 bytes of JSON/base64 encoding | Done |
| J3 | Two-object manifest design not representative | Stated, with the S3 calls per operation and the reason for the design | Done (justification); no in-metadata variant was built |
| J4 | Missing literature; outdated drafts | Added STREAM (CRYPTO 2015), KEMTLS (CCS 2020) and age v1.3.0; HPKE draft updated to version 05 | Done |
| J5 | Finding 7 contradicted Finding 5 | CPU statement scoped to one worker, with the contention figure beside it | Done |
| – | Underpowered cells | Batch K | Done |
| – | CPU identity untested out of sample | One advance prediction (0.956) for batches J and L: observed 0.960 and 0.963, both intervals exclude the prediction. Reported as a miss of 0.4 and 0.7 points | Done, with a negative nuance |
| – | 1 MiB AES-GCM anomaly | Batches M and MT | Done |
| – | 158 MiB server-memory outlier | Explained in the text: one run of five | Done |
| – | Ten finding boxes, off-thesis queueing section | Six finding boxes; queueing moved to an appendix | Done |
| – | Abstract's first sentence overstated the threat | Reworded to keys established with RSA or elliptic curves | Done |

### Where the second audit was wrong

- **X-Wing draft version 11 exists** (23 September 2026, IETF datatracker). The citation stands.
- **The pre-registration can be timestamped** from the hosting service's push log; it does not
  need to be recreated.

### Not done from the second audit

- Signal PQXDH, Apple PQ3 and vendor PQ-TLS reports were not added: they would support no
  statement the paper makes.
- No binary in-metadata manifest variant was built.
- Access dates were not added to vendor documentation entries that were not re-fetched.
- The title was kept.

## Integrity notes

- **A wrong hypothesis was in the previous version.** It said the larger manifest was the
  largest measured stage difference and the leading candidate. Batch J shows it explains 17 %.
- **One pre-registration was pushed five minutes after a batch started.** Version 1.12 (batch L
  and a prediction for batch J) was pushed at 05:36 UTC; batch J had started at 05:31. No batch J
  data had been downloaded; the request counts of its first two runs had been seen in the log.
- **A local exploratory test preceded batch L.** On the development laptop, decapsulation under
  16 threads cost 60 µs through the binding against 16–33 µs through one call. It motivated the
  batch and is recorded in the pre-registration; it is not used as evidence in the paper.
- **The native timing of single operations is exploratory**, not part of batch N.
- **Transfers overlapped earlier batches.** During the confirmatory x86 chain, completed batches
  were downloaded while parts of batches F, G and H ran. This may have added noise to those runs;
  it cannot favour a mode. It did not affect the primary-family batches or batches J to N.
- **The disk baseline of the J–N testbed did not complete.** Its network baseline did.
- **Cost.** These batches were estimated at about $15; the account's month-to-date figure rose
  further than the estimates given during the work, mainly because tax and idle time had not
  been counted.

## Still open after this revision

1. **The native client is minimal.** GET only, three modes, 64 KiB objects, different
   cryptographic libraries from the Python client, and saturated only when confined to one core.
   Library and language are not separated.
2. **One unexplained native result.** At 16 cores and 128 workers ML-KEM is 5.7 % slower although
   the client is not CPU-saturated by the pre-registered criterion.
3. **A 4 µs key-derivation difference** between ML-KEM and X25519 in the Python client is still
   unexplained, and X-Wing keeps a small residual in the allocator diagnostic.
4. **HPKE was not benchmarked**, and the envelope is not HPKE-conformant.
5. **Baselines are narrow** and the store is a single-node, archived community edition.
6. **Queueing results** rest on very few held-out points and one mode.
7. **The repository is private** and has no DOI.
8. **Declarations are missing:** funding, conflicts of interest, author contributions and
   generative-AI use. An AI assistant was used extensively for code, analysis and drafting; this
   must be disclosed accurately under the target journal's policy.
9. **Not searched:** IEEE Xplore and the ACM Digital Library. Two 2026 preprints are still
   described from their abstracts.
10. **The paper is 20 pages** in IEEE conference format; a journal will need its own template.
