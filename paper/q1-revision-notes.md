# Q1 restructuring: change log, claims ledger, abstracts and author to-do

Baseline: git tag `q1-baseline` (commit `ae24f71`), which is byte-identical in text to the
attached "CC Final 3.pdf". Revised files: `paper/main.tex`, `paper/supplement.tex`,
`paper/abstracts/`. No experiment was run and no result was changed for this revision.

## Read this first

1. **The audit report was not attached.** The prompt refers to findings C1, M1–M5, Mo1–Mo4 and
   Mi1–Mi2, but neither audit file available to me uses that numbering. The change log therefore
   traces each change to the finding IDs *as the prompt assigns them to tasks T1–T9*. I have not
   seen the text of those findings and do not paraphrase them. M2 and M3 are not assigned to any
   task in the prompt, so nothing is traced to them.
2. **No result files for E1–E4 were attached.** All four are treated as not run. Their sections
   are skeletons with `\TODO` placeholders and no expected outcomes.
3. **One instruction was not followed literally, on purpose.** T1 asks for the claim that the
   throughput cost appears "only" in client-CPU-saturated regimes. Three existing results
   contradict a strict "only", and the hard constraints forbid upgrading a claim:
   - the native reader at 16 cores and 128 workers is 5.7 % (ML-KEM) and 7.7 % (X-Wing) slower in
     a cell that does not meet the pre-registered saturation criterion;
   - in the Python client, X-Wing is 4.5 % (x86) and 4.9 % (ARM) slower at 128 workers, a cell
     the paper calls unsaturated;
   - the Python saturation criterion was not pre-registered and rests on a few tenths of a core.

   The thesis is therefore worded "at or near CPU saturation, with one unexplained exception in
   the native reader", and the exceptions are listed in a new "Open Anomalies" subsection.
4. **The `\CITE` template in the prompt contains an em dash**, which the prompt also forbids. I
   used semicolons: `\CITE{authors; title; venue; year; VERIFY}`.
5. **One set of derived counts is new, and you should decide whether to keep it.** To support
   the word "only" in the thesis, the pipeline now sweeps all 102 closed-loop cells in which the
   Python client ran both ML-KEM and X25519 and applies the deficit rule that was pre-registered
   for the native reader (90 % interval below 0.98 or above 1.02). Result: 7 deficits, all
   small-object GET with at least 128 workers and at least 14.2 of 16 client cores in use; 4
   equally busy cells without a deficit; 2 advantages, both PUT at one worker. These are counts
   over existing data, written by `analysis/audit_assets.py` to `results/audit/sweep.csv` and
   into macros. They are not new experiments, but they are numbers that were not in the previous
   manuscript, and applying that rule outside its own experiment is exploratory; the paper says
   so. If you read the "no new number" constraint strictly, delete the "All cells" paragraph in
   Sec. VII-D and anomaly A4, and weaken "only" in the thesis, abstract and conclusion to "in
   the cells we report". Apart from this, a script found no digit token that is not in the
   baseline, other than the years inside `\CITE` placeholders, the set k = 1, 2, 4, 8 from the
   prompt, and the bounds 0.98 and 1.02 of the pre-registered rule.
6. **Nothing was deleted from the pre-registration statements, deviations or limitations.** A
   script checked 46 distinctive phrases from those passages; all are present, some moved.

## 1. Change log

| Finding ID (as assigned in the prompt) | Location | What changed | Why |
|---|---|---|---|
| M1, M5 (T1) | Sec. I, thesis | New central claim: change in throughput only at or near client CPU saturation; size is a property of the implementation (equivalence within ±2 % through 4.0–4.9 % to 9.5 %); storage is the cost every implementation pays | Reframe the thesis; see note 3 for the qualification |
| M1, M5 (T1) | New Sec. VI-G "CPU Accounting as a Method" | The identity X_a/X_b = c_b/c_a moved from Results to Methods and presented as a method, with the saturation criterion actually used and its status as a prediction | An identity must not read as an empirical discovery |
| M1, M5 (T1) | Sec. VII-E | Section now *applies* the method; all "decomposition shows" wording removed; the missed advance prediction has its own paragraph | Same |
| M1, M5 (T1) | Abstract, Sec. I, Sec. VII-D, Finding 2 | "Equivalent in 6 of 8 cells" removed from abstract and contributions; in Results it now follows the sentence that seven of eight cells were not client-saturated | Demotion requested |
| Mo3, M4 (T3) | Sec. VII-F, Conclusion | "About half" split: about half for ML-KEM, about three quarters for X-Wing, each with its macros | Stated inconsistency |
| Mo3, M4 (T3) | Abstract, Sec. I, XI, XII, IX-E | "Absent unless saturated", "disappears" and "vanishes" removed; replaced by the supported statements (equivalent within ±2 %; at or near saturation; exception A2) | Wording stronger than the data |
| T4 | Sec. I, contributions | C1 saturation-regime result with method; C2 binding artifact and library implication; C3 storage cost with the 2 KB S3 limit; C4 placeholder for E2. Sessions named a secondary result; client, harness and pipeline named an artifact | Originality framing |
| Mo2 (T5) | Sec. III | Rewritten as six subsections that synthesize: where key establishment has been measured; per-message KEMs in messaging; storage and client-side encryption; standard constructions and KEM combiners; performance variability and benchmarking statistics; search. Eleven `\CITE` placeholders | Literature gaps |
| Mo2 (T5) | Sec. III-F | Search statement keeps what was searched and lists IEEE Xplore, ACM DL, IACR ePrint and Google Scholar as *not yet searched*, with `\TODO` for queries and hit counts | A search that was not run cannot be claimed |
| Mo1, Mi2 (T6) | Sec. IV-A, Table III | New paragraphs: writers are not authenticated, so integrity covers modification of an honest writer's object and not authenticity (this **weakens** the earlier threat-model wording, which implied more); rollback to an older valid version is not prevented, and how that differs from the replay that is detected; AES-GCM is not key-committing, the single-recipient argument, and why it does not extend to several recipients | Threat-model gaps |
| Mi1 (T7) | Whole paper, Table V | Batch letters replaced by purpose labels; one mapping table. Labels requested: Primary-x86, Primary-ARM, Control-Manifest, Control-Binding, Native-GET, Sessions, Hybrid-Matrix. Labels I had to add because those batches had none: Expl-Sweep, Expl-Size, Expl-OpenLoop, Expl-SmallPUT, OneWorker-ARM, Open-Loop, Profiling, Power-PUT, Allocator | Readability |
| Mi1 (T7) | Generated control table | Row labels changed in the generator (`analysis/audit_assets.py`), not by hand | Keep "every number generated" |
| Mi1 (T7) | New Sec. VII-J "Open Anomalies" | A1 key-derivation difference; A2 native 16-core deficit; A3 X-Wing at 128 workers in the Python client; A4 ML-KEM faster at one worker in two exploratory cells; A5 allocator effect with its table | Collect anomalies. A3 and A4 were not in the prompt's list; they are existing results that the new thesis makes relevant |
| Mi1 (T7) | Sec. VII-E, VII-F to IX-E | Caveats moved to Threats to Validity: controls not run on ARM; Power-PUT on x86 only; saturation criterion post hoc; CPU figures of the two clients not like for like. The qualifier stays on each claim ("on x86", "by construction", "exploratory") | Plain results, hedges in one place, no claim strengthened |
| Mi1 (T7) | `paper/supplement.tex`, Sec. XI | Queueing appendix moved to a supplement that compiles on its own from the same generated macros; two-sentence summary and knee result in Discussion; pre-registered queueing protocol kept in the supplement and referenced from Methods | Structure |
| C1, Mo4 (T8) | Back matter | Data and Code Availability with DOI slots; CRediT; Funding; Conflicts of Interest; Use of Generative AI, drafted factually with `\TODO`s | Missing statements |
| C1, Mo4 (T8) | Sec. VI-A | Pre-registration paragraph rewritten: what the push log shows, what it does not, `\TODO` for the archived snapshot. The push log was exported to `docs/github-activity-log.json` (57 events) | Verifiability of timing |
| T9 | New Sec. X "Planned Experiments (Not Yet Run)" | Skeletons for E1–E4 with purpose, design and `\TODO` result slots | Slots requested |
| T2 | Abstract, index terms | New abstract (balanced version, 229 words, 5 numbers). Eight index terms, none verbatim from the title | Requested |
| Hard constraint | Sec. V-C | Two em dashes replaced by parentheses | No em dashes |
| – | Finding 5 | "adds 1,056 bytes of ciphertext" corrected to "against X25519, adds 1,056 bytes" | The ciphertext is 1,088 bytes; 1,056 is the increase |

Not changed: Sections II, V (except the em dashes), VIII, and every table and figure of results.

## 2. Abstracts

Counting convention: words are whitespace-separated tokens with macros expanded and the percent
sign attached to its number; numbers are digit tokens, a range counts as two, and "X25519", "S3"
and "x86" are not counted. If the percent sign is counted as its own token, add 3 or 4 words.
Sources are in `paper/abstracts/*.tex`, where every number is a pipeline macro.

### Balanced (222 words, 5 numbers), installed in `main.tex`

> Data at rest that is encrypted under classical public-key algorithms can be recorded now and decrypted once a large quantum computer exists; public-key envelope encryption must therefore move to ML-KEM, which places a key-encapsulation operation and its ciphertext on every object. To our knowledge its cost has been measured for primitives and for connection setup, but not on a concurrent object-store data path. We measured it on an S3-compatible store with a Python client on two processor architectures and a native Go reader, comparing ML-KEM with X25519 and two hybrid modes in an exploratory campaign, a pre-registered confirmatory campaign with paired equivalence tests, and pre-registered controls. With one unexplained exception in the native reader, ML-KEM lowered throughput only where the client was at or near CPU saturation: there the Python client was 4.0 to 4.9% slower than with X25519. Two controls on the x86 client show that the deficit there is produced by the library binding, which makes four foreign calls per decapsulation; with one call, ML-KEM was equivalent to X25519 within 2%. A native reader saturated on one core was 9.5% slower, so the size of the cost depends on the implementation. The cost that every implementation pays is storage: 1,056 more bytes of ciphertext per object than X25519. The results cover two clients, a single-node store and one cloud provider.

### Most technical (227 words, 6 numbers)

> Data at rest that is encrypted under classical public-key algorithms can be recorded now and decrypted once a large quantum computer exists; public-key envelope encryption must move to ML-KEM, which places a key-encapsulation operation and its ciphertext on every object. To our knowledge its cost has been measured for primitives and connection setup, but not on a concurrent object-store data path. We measured it on an S3-compatible store with a Python client on two architectures and a native Go reader, against X25519 and two hybrid modes, with pre-registered equivalence tests and controls. With one unexplained native exception, ML-KEM lowered throughput only at or near client CPU saturation, where the loss matched the extra client CPU per request: the Python client was 4.0 to 4.9% slower than with X25519. On the x86 client, a control with an equally large manifest attributes 17% of that deficit to ciphertext handling, and a control that reaches the same library through one foreign call, where the binding makes four, was equivalent to X25519 within 2%. A native reader saturated on one core was 9.5% slower, about half of which a slower key recovery in its library accounts for. The cost thus depends on the implementation; what every implementation pays is storage: 1,056 more bytes of ciphertext per object than X25519. The results cover two clients, one single-node store and one cloud provider.

### Most practitioner-oriented (228 words, 5 numbers)

> Data at rest that is encrypted under classical public-key algorithms can be recorded now and decrypted once a large quantum computer exists, so systems that encrypt objects to a public key must move to ML-KEM, which adds a key-encapsulation operation and its ciphertext to every object. To our knowledge that cost has been measured for primitives and connection setup, but not for a storage client under concurrent load. We measured it on an S3-compatible store with a Python client on two processor architectures and a native Go reader, comparing ML-KEM with X25519 and two hybrid modes in pre-registered paired equivalence tests. With one unexplained native exception, migration lowered throughput only where the client was at or near CPU saturation, and there by the ratio of client CPU per request, which an operator can measure beforehand. The Python client was 4.0 to 4.9% slower; controls on the x86 client trace the deficit there to a library binding that makes four foreign calls per decapsulation, and with one call ML-KEM was equivalent to X25519 within 2%. A native reader saturated on one core was 9.5% slower, so the cost depends on the implementation and must be measured on the actual client. The cost that no implementation avoids is storage: 1,056 more bytes of ciphertext per object than X25519. The results cover two clients, a single-node store and one cloud provider.

### Recommendation: the balanced version

- It follows the seven-part structure most directly and carries the argument with five numbers.
- The technical version is the most complete, but its sixth number (17 %) and the CPU clause make
  the middle dense, and it sits near the upper word limit.
- The practitioner version reads best for an operator, but "by the ratio of client CPU per
  request" may be read as presenting an accounting identity as a result, which T1 asks to avoid.

Choices to know about in all three:

- The gap sentence is hedged with "to our knowledge", because four database searches are still
  outstanding.
- "RSA" is not named; "classical public-key algorithms" stands in, to respect the abbreviation
  rule. "Go" and "x86" are kept as names. The controls are stated as run "on the x86 client"
  because they did not run on ARM.
- The verb is "lowered", not "changed": by the rule now stated in Sec. VI-G, ML-KEM was faster
  than X25519 in two one-worker cells of the exploratory campaign (anomaly A4).

## 3. Claims ledger

### Abstract (balanced)

| # | Claim | Support |
|---|---|---|
| 1 | Data under RSA or elliptic-curve keys is exposed to record-now, decrypt-later; public-key envelope encryption puts a KEM operation and ciphertext on every object | Background, Sec. I and II; ref. FIPS 203. Motivation, not a result |
| 2 | To our knowledge, cost measured for primitives and connection setup, not for a concurrent object-store path | Sec. III, Table I; search statement. Hedged because four database searches are outstanding (Sec. III-F `\TODO`s) |
| 3 | Setup: Python client on two architectures, native Go reader, modes, exploratory and pre-registered confirmatory campaign, pre-registered controls | Sec. VI-A, Table V |
| 4 | With one unexplained exception in the native reader, ML-KEM lowered throughput only at or near client CPU saturation | Sweep of all cells: `\AudSweepCells`, `\AudSweepDeficits`, `\AudSweepDeficitMinCores`, `\AudSweepBusyNoDeficit` (Sec. VII-D, `results/audit/sweep.csv`); Table XVII for the native reader; exception: `\AudNMidMlkemDeficit`, anomaly A2. Exploratory rule; "near" has no pre-registered threshold |
| 5 | Python client 4.0 to 4.9 % slower there | `\RevHotDeficit`, `\ArmHotDeficit`; Table XI |
| 6 | Two controls on the first architecture show the deficit there is produced by the binding | `\AudBindVerdict`, `\AudPadVerdict`; Table XVI (`tab:control`). x86 only |
| 7 | The binding makes four foreign calls per decapsulation | Library source, described in Sec. VII-E; recorded in the pre-registration (SoT v1.12). Not a measured quantity |
| 8 | With one call, ML-KEM was equivalent to X25519 within 2 % | `\AudBindReleasedEqTwoPct`, `\AudBindReleasedRatio`, `\AudBindReleasedCI` |
| 9 | Native reader saturated on one core 9.5 % slower | `\AudNOneMlkemDeficit`, `\AudNOneMlkemThrCI`, `\AudNOneSaturated`; Table XVII |
| 10 | The size of the cost depends on the implementation | Claims 5, 8 and 9 together: same algorithm, three clients, three sizes. Shows dependence on the implementation; does not show the algorithm contributes nothing |
| 11 | Storage: 1,056 more bytes of ciphertext per object than X25519 | `\RevMetaIntrinsic`; Sec. VII-I |
| 12 | Scope: two clients, single-node store, one cloud provider | Sec. VI-B, IX-E |

### Conclusion

| # | Claim | Support |
|---|---|---|
| 1 | Configurations evaluated | Sec. VI |
| 2 | ML-KEM lowered throughput against X25519 only at or near saturation, one unexplained exception | As abstract claim 4 |
| 3 | Saturated cell: 4.0 % (x86), 4.9 % (ARM) | `\RevHotDeficit`, `\ArmHotDeficit` |
| 4 | Controls on x86 attribute the deficit to the binding and 17 % to the manifest | `\AudBindVerdict`, `\AudPadShare`, `\AudPadShareLo`–`Hi` |
| 5 | One call: equivalent within ±2 % | `\AudBindReleasedEqTwoPct` |
| 6 | Native: 9.5 % (ML-KEM), 17.4 % (X-Wing) | `\AudNOneMlkemDeficit`, `\AudNOneXwingDeficit` |
| 7 | Key recovery: about half (ML-KEM), about three quarters (X-Wing) of the extra CPU | `\AudNMicroMlkemExtra` of `\AudNOneMlkemCpuDelta`; `\AudNMicroXwingExtra` of `\AudNOneXwingCpuDelta`. From an exploratory timing |
| 8 | In the saturated cells the loss matched the extra client CPU per request | Table XIV (`\RevModelErrHot`); native by construction. An identity on the same runs; the one advance prediction missed (`\AudPredictionErrorJ`, `\AudPredictionErrorL`) |
| 9 | CPU per request is the quantity to measure before a migration | Follows from 8 as a method. Not validated on an unseen configuration |
| 10 | The size of the cost depends on the client implementation | As abstract claim 10 |
| 11 | Storage: 1,056 bytes more per object | `\RevMetaIntrinsic` |
| 12 | Limits of scope | Sec. IX-E, IX-F, X |

**UNSUPPORTED:** none outright. Three claims carry a stated weakness: abstract 2 (search
incomplete), abstract and conclusion 10 (inference from three clients), conclusion 9 (method not
validated out of sample).

## 4. What the authors must do by hand

### Verify (11 `\CITE` placeholders; none is in `references.bib`)

Each was named from memory and none was checked. Confirm authors, title, venue and year, read
the source, and confirm it supports the sentence it is attached to.

1. Signal, PQXDH specification, 2023
2. Apple, iMessage PQ3, 2024
3. Giacon, Heuer, Poettering, "KEM Combiners", PKC 2018
4. Bindel et al., "Hybrid Key Encapsulation Mechanisms and Authenticated Key Exchange", PQCrypto 2019
5. Leitner and Cito, "Patterns in the Chaos", ACM TOIT 2016
6. Uta et al., "Is Big Data Performance Reproducible in Modern Cloud Networks?", NSDI 2020
7. Maricq et al., "Taming Performance Variability", OSDI 2018
8. Kalibera and Jones, "Rigorous Benchmarking in Reasonable Time", ISMM 2013
9. Dodis et al., "Fast Message Franking", CRYPTO 2018
10. Len, Grubbs, Ristenpart, "Partitioning Oracle Attacks", USENIX Security 2021
11. Albertini et al., "How to Abuse and Fix Authenticated Encryption Without Key Commitment", USENIX Security 2022

Also still to verify from earlier revisions: read the two 2026 preprints (Prikutse et al.,
Junaid) in full; the paper says only their abstracts were read.

### Security statements to have checked by someone qualified

- The key-commitment paragraph (Sec. IV-A) gives an informal argument for the single-recipient
  case. It is labelled as not a proof. A cryptographer should confirm or correct it.
- The rollback paragraph describes the design's behaviour as I understand it from the code and
  tests; confirm against `tests/test_tampering.py`.

### Searches (4 `\TODO`s in Sec. III-F)

IEEE Xplore, ACM Digital Library, IACR ePrint, Google Scholar: run them, record queries, date
and hit counts, add to `docs/literature-search.md`, then rewrite the last sentences of Sec. III-F.

### Experiments (Sec. X; none run)

- **E1** confirmatory family of client-saturated cells, both clients, three or more object sizes,
  CPU per request co-primary.
- **E2** multi-recipient objects, k = 1, 2, 4, 8. Needs a key-committing construction first.
  Then fill or remove contribution C4.
- **E3** full native client, two ML-KEM implementations, multi-core saturation, explanation of
  anomaly A2. Then revisit the words "at or near" and "one unexplained exception".
- **E4** key-service wrap baseline and an HPKE-conformant envelope or age 1.3.0.

Each must be pre-registered and pushed before its first run. Also listed as still required in
Sec. IX-F: the two controls on the ARM client, and a manifest control in the native reader.

### Identifiers and statements (`\TODO`s in the back matter and Sec. VI-A)

- Make the repository public; Zenodo DOI for code and per-run summaries; DOI or access route for
  the 11 GB of raw records.
- Archive the pre-registration snapshot and the exported push log
  (`docs/github-activity-log.json`) with a persistent identifier, and cite it in Sec. VI-A.
- CRediT roles for all five authors.
- Funding statement, including who paid for the AWS resources on both accounts.
- Conflict-of-interest statement.
- Generative-AI statement: complete the sentence on how the authors verified the work, and adapt
  it to the target venue's policy. The drafted text says an AI assistant was used for code,
  experiments, analysis, literature search and drafting, which is accurate.

### Venue and format

- Choose the venue; verify its quartile and indexing through library access.
- Convert from the IEEE conference template to the venue's journal template; the paper is 22
  pages plus a 2-page supplement.
- Remove Sec. X or replace it with results before submission; a journal will not accept a
  section of placeholders.
- The compiled PDF shows every `\TODO` in red and every `\CITE` in blue: 31 and 11 at present.

### Remaining from earlier rounds

- Teammate and supervisor review; plagiarism check.
- Back up `experiments/`.
- Figure titles and two tables of the exploratory campaign still show batch letters A to D,
  because the pipeline generates them; the mapping table explains this. Changing them means
  editing `analysis/make_paper_assets.py`.
