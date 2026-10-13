# Second restructuring pass (Tasks 1 to 5): notes

Baseline: git tag `q1-pass2-baseline` (commit d0723f0, the PDF "CC Final 4"). The new `paper/main.tex`
is produced by `paper/tools/restructure_pass2.py`, which copies line ranges of the baseline and
applies a fixed list of asserted substitutions; `paper/tools/check_pass2.py` and
`paper/tools/heading_map.py` produce sections 2 and 5 below. Paragraph numbers count text
paragraphs inside the new section or subsection; floats and finding boxes are not counted.

## 0. Points the authors must know

- **This pass re-adds what the previous instruction removed.** The last commit removed the
  Author Contributions, Funding, Conflicts of Interest and Generative AI sections and every TODO
  "for submission". Task 5 asks for them again as placeholders, so the paper is not submittable
  until the 17 TODOs in section 4 are resolved.
- **Abstract (Task 3) installed verbatim; mismatches with the body, not edited:**
  1. "comparing ML-KEM-768 with X25519": the body also compares RSA-4096, a symmetric-only
     baseline, two hybrids and bounded sessions. An omission, not a contradiction.
  2. "ML-KEM lowered throughput only where the client was at or near CPU saturation": in the body
     this rests on a sweep of 102 cells with a deficit rule that was not pre-specified for the
     Python client (IV-C, par. 9 and 12), and it is qualified by "in the configurations we
     measured". The abstract drops both qualifiers.
  3. "There the Python client was 4.0 to 4.9 % slower": 4.0 and 4.9 % are the one saturated cell
     of the pre-registered family (64 KiB GET, 500 workers; x86 and ARM). The sweep's seven
     deficit cells range from 2.7 to 4.9 % (`results/audit/sweep.csv`); the body does not print
     the 2.7 % end.
  4. "Two controls on x86 trace this deficit to the library binding": "this deficit" includes the
     ARM value, but the controls ran on x86 only and the body says the attribution is untested
     on ARM (VI, par. 5). Also, only Control-Binding traces the deficit to the binding;
     Control-Manifest attributes 17 % of it to the larger manifest, which the abstract omits.
  5. "must move to ML-KEM": the body limits the need to deployments that require a public-key
     mechanism (I, par. 3) and treats hybrids as an alternative.
  The remaining sentences (9.5 %, 1,056 bytes, "two clients, a single-node store and one cloud
  provider") match the body. The numbers in the abstract are pipeline macros, as before.
- **Supplement TODO.** `paper/supplement.tex` already contains the queueing models, the
  pre-registered protocol, the results, the figure and the table. It has no "Appendix A"; the
  former appendix is its Section I. The four TODOs can be cleared once the authors agree.
- **Figures 2 and 3** carry "(batch A/B/D)" inside the generated PDFs. They were not edited; the
  captions carry a TODO. The titles are set in `analysis/make_paper_assets.py`
  (`fig_throughput`, `fig_size`).
- **Generated tables.** Three header strings were changed in the generators and, identically, in
  the generated `.tex` files (the generators were not re-run, to avoid touching anything else):
  `tab-sources.tex` "open loop (RQ3)" to "open loop"; `tab-tost.tex` group headers to the purpose
  labels; `tab-model.tex` "Predicted" to "Implied by CPU".
- **Not touched:** `docs/build_sot.py` (the project specification and pre-registration) still
  uses RQ1 to RQ4; changing a pre-registration text after the fact would be wrong.
  `paper/q1-revision-notes.md`, `paper/audit-response.md` and `paper/response-to-review.md`
  cite the old section and table numbers.
- **Placement choices.** Old VII-H (CPU and Memory) sits before the pre-registered family inside
  V-B, so that Finding 2 still closes the subsection. Table I and its introductory sentence open
  II-B. No paragraphs were merged; every former run-in paragraph keeps its full body.

## 1. Revised source

`paper/main.tex` (builds to 21 pages, no undefined or multiply defined references).

## 2. Heading map

| Old no. | Kind | Old heading | New location |
|---|---|---|---|
| I | section | Introduction | I Introduction, par. 1 |
| I | run-in | When a public-key KEM per object is needed. | I Introduction, par. 3 |
| I | run-in | What is known. | I Introduction, par. 4 |
| I | run-in | What is not known. | I Introduction, par. 5 |
| I | run-in | Thesis. | I Introduction, par. 6 |
| I | run-in | Contributions. | I Introduction, par. 7 |
| I | list item | C1 | I Introduction, par. 7 |
| I | list item | C2 | I Introduction, par. 7 |
| I | list item | C3 | I Introduction, par. 7 |
| I | run-in | Research questions. | REMOVED (Task 1); content folded into the one sentence of I Introduction, par. 9 |
| I | run-in | Scope. | I Introduction, par. 8 |
| II | section | Background | II-A Post-Quantum KEMs, Hybrids and HPKE, par. 1 |
| II-A | subsection | Key-Encapsulation Mechanisms and ML-KEM | II-A Post-Quantum KEMs, Hybrids and HPKE, par. 1 |
| II-B | subsection | Hybrid KEMs | II-A Post-Quantum KEMs, Hybrids and HPKE, par. 2 |
| II-C | subsection | HPKE | II-A Post-Quantum KEMs, Hybrids and HPKE, par. 3 |
| II-D | subsection | Envelope Encryption and Object Storage | II-A Post-Quantum KEMs, Hybrids and HPKE, par. 5 |
| III | section | Related Work | II-B Related Measurements, par. 1 |
| III-A | subsection | Where Key Establishment Has Been Measured | II-B Related Measurements, par. 2 |
| III-B | subsection | Per-Message Key Establishment in Messaging | II-A Post-Quantum KEMs, Hybrids and HPKE, par. 6 |
| III-C | subsection | Storage and Client-Side Encryption | II-B Related Measurements, par. 3 |
| III-D | subsection | Standard Constructions and KEM Combiners | II-A Post-Quantum KEMs, Hybrids and HPKE, par. 4 |
| III-E | subsection | Performance Variability and Benchmarking Statistics | II-C Benchmarking Method, par. 1 |
| III-F | subsection | Search | II-B Related Measurements, par. 4 |
| IV | section | System and Threat Model | III Design and Threat Model, par. 1 |
| IV-A | subsection | Threat Model | III Design and Threat Model, par. 1 |
| IV-A | run-in | Writers are not authenticated. | III Design and Threat Model, par. 2 |
| IV-A | run-in | Rollback is not prevented. | III Design and Threat Model, par. 3 |
| IV-A | run-in | Key commitment. | III Design and Threat Model, par. 4 |
| IV-B | subsection | Key-Establishment Modes | III Design and Threat Model, par. 5 |
| IV-C | subsection | Per-Object Envelope and Commit Protocol | III Design and Threat Model, par. 6 |
| IV-D | subsection | Bounded Sessions (Mode N1) | III Design and Threat Model, par. 7 |
| IV-E | subsection | Relation to HPKE | III Design and Threat Model, par. 8 |
| IV-F | subsection | What Is and Is Not Claimed | III Design and Threat Model, par. 9 |
| V | section | Implementation | IV-A Implementation, par. 1 |
| V-A | subsection | Cryptographic Core | IV-A Implementation, par. 2 |
| V-B | subsection | Storage Layer | IV-A Implementation, par. 4 |
| V-C | subsection | Measurement Harness | IV-A Implementation, par. 5 |
| V-D | subsection | Validation | IV-A Implementation, par. 7 |
| V-E | subsection | Testbed Automation | IV-A Implementation, par. 8 |
| V-F | subsection | Native Reader | IV-A Implementation, par. 9 |
| V-G | subsection | Analysis Pipeline | IV-A Implementation, par. 10 |
| VI | section | Experimental Methodology | IV-B Testbeds and Workloads, par. 1 |
| VI-A | subsection | Campaigns | IV-B Testbeds and Workloads, par. 1 |
| VI-A | run-in | What the timestamps show, and what they do not. | IV-B Testbeds and Workloads, par. 4 |
| VI-B | subsection | Testbeds | IV-B Testbeds and Workloads, par. 6 |
| VI-C | subsection | Workload | IV-B Testbeds and Workloads, par. 7 |
| VI-D | subsection | Metrics | IV-B Testbeds and Workloads, par. 8 |
| VI-E | subsection | Experimental Unit and Replication | IV-B Testbeds and Workloads, par. 9 |
| VI-F | subsection | Equivalence Testing | IV-C Statistical Analysis, par. 1 |
| VI-F | run-in | Margin. | IV-C Statistical Analysis, par. 2 |
| VI-F | run-in | Primary family and multiplicity. | IV-C Statistical Analysis, par. 3 |
| VI-F | run-in | Power. | IV-C Statistical Analysis, par. 4 |
| VI-F | run-in | Distributional assumption. | IV-C Statistical Analysis, par. 5 |
| VI-F | run-in | Stall rule. | IV-C Statistical Analysis, par. 6 |
| VI-G | subsection | CPU Accounting as a Method | IV-C Statistical Analysis, par. 7 |
| VI-G | run-in | Saturation criterion. | IV-C Statistical Analysis, par. 8 |
| VI-G | run-in | What counts as a throughput deficit. | IV-C Statistical Analysis, par. 9 |
| VI-G | run-in | Status as a prediction. | IV-C Statistical Analysis, par. 10 |
| VI-H | subsection | Deviations from the Pre-Registration | IV-C Statistical Analysis, par. 11 |
| VI-H | run-in | Not pre-specified. | IV-C Statistical Analysis, par. 12 |
| VII | section | Results | V-A Per-Object Cost, par. 1 |
| VII-A | subsection | Per-Object Key-Establishment Time (RQ1) | V-A Per-Object Cost, par. 1 |
| VII-B | subsection | Effect of Object Size (RQ2) | V-B Where the Cost Appears, par. 1 |
| VII-C | subsection | Concurrency and Bottlenecks (RQ2) | V-B Where the Cost Appears, par. 2 |
| VII-C | run-in | Attribution of the small-PUT ceiling. | V-B Where the Cost Appears, par. 3 |
| VII-D | subsection | ML-KEM against X25519: the Pre-Registered Family | V-B Where the Cost Appears, par. 5 |
| VII-D | run-in | All cells. | V-B Where the Cost Appears, par. 6 |
| VII-D | run-in | Large objects. | V-B Where the Cost Appears, par. 7 |
| VII-D | run-in | The saturated cell. | V-B Where the Cost Appears, par. 8 |
| VII-D | run-in | Noise, not difference, in small PUT. | V-B Where the Cost Appears, par. 9 |
| VII-D | run-in | Follow-up with adequate power. | V-B Where the Cost Appears, par. 10 |
| VII-D | run-in | The cost is visible in CPU even where throughput does not move. | V-B Where the Cost Appears, par. 11 |
| VII-D | run-in | Sensitivity. | V-B Where the Cost Appears, par. 12 |
| VII-D | run-in | Exploratory campaign. | V-B Where the Cost Appears, par. 13 |
| VII-E | subsection | Why the Saturated Python Client Is Slower (RQ2) | V-C Why the Saturated Client Is Slower, par. 1 |
| VII-E | run-in | Applying the CPU accounting. | V-C Why the Saturated Client Is Slower, par. 2 |
| VII-E | run-in | Where the extra CPU is not. | V-C Why the Saturated Client Is Slower, par. 3 |
| VII-E | run-in | \lab{Control-Manifest}: manifest size. | V-C Why the Saturated Client Is Slower, par. 5 |
| VII-E | run-in | \lab{Control-Binding}: the library binding. | V-C Why the Saturated Client Is Slower, par. 6 |
| VII-E | run-in | What the controls establish. | V-C Why the Saturated Client Is Slower, par. 7 |
| VII-E | run-in | The one advance prediction missed. | V-C Why the Saturated Client Is Slower, par. 8 |
| VII-F | subsection | A Native Client (RQ2) | V-C Why the Saturated Client Is Slower, par. 9 |
| VII-F | run-in | Result. | V-C Why the Saturated Client Is Slower, par. 10 |
| VII-F | run-in | Where the native reader's extra CPU goes. | V-C Why the Saturated Client Is Slower, par. 11 |
| VII-F | run-in | Cells with 16 cores. | V-C Why the Saturated Client Is Slower, par. 12 |
| VII-G | subsection | Hybrid Key Establishment (RQ2) | V-D Hybrid Key Establishment, par. 1 |
| VII-G | run-in | Cost per object. | V-D Hybrid Key Establishment, par. 1 |
| VII-G | run-in | Primary cells. | V-D Hybrid Key Establishment, par. 2 |
| VII-G | run-in | Matrix. | V-D Hybrid Key Establishment, par. 3 |
| VII-H | subsection | CPU and Memory (RQ1) | V-B Where the Cost Appears, par. 4 |
| VII-I | subsection | Metadata at Scale (RQ1) | V-E Storage Overhead, par. 1 |
| VII-J | subsection | Open Anomalies | V-G Open Anomalies, par. 1 |
| VII-J | run-in | (A1) A slower key derivation with ML-KEM. | V-G Open Anomalies, par. 2 |
| VII-J | run-in | (A2) A native deficit without saturation. | V-G Open Anomalies, par. 3 |
| VII-J | run-in | (A3) X-Wing below X25519 in a Python cell we call unsaturated. | V-G Open Anomalies, par. 4 |
| VII-J | run-in | (A4) ML-KEM faster than X25519 at one worker. | V-G Open Anomalies, par. 5 |
| VII-J | run-in | (A5) An allocator effect at 1\,MiB. | V-G Open Anomalies, par. 6 |
| VIII | section | Security--Performance Trade-off | V-F Bounded Sessions, par. 1 |
| VIII-A | subsection | What a Session Exposes | V-F Bounded Sessions, par. 1 |
| VIII-B | subsection | Measured Trade-off | V-F Bounded Sessions, par. 2 |
| VIII-C | subsection | Decision Rule | V-F Bounded Sessions, par. 6 |
| IX | section | Robustness and Validity | VI Threats to Validity, par. 1 |
| IX-A | subsection | Run-to-Run Variation | VI Threats to Validity, par. 1 |
| IX-B | subsection | Stalls | VI Threats to Validity, par. 2 |
| IX-C | subsection | Order and Time Effects | VI Threats to Validity, par. 3 |
| IX-D | subsection | Second Architecture | VI Threats to Validity, par. 4 |
| IX-E | subsection | Threats to Validity | VI Threats to Validity, par. 5 |
| IX-E | run-in | Internal. | VI Threats to Validity, par. 5 |
| IX-E | run-in | External. | VI Threats to Validity, par. 6 |
| IX-E | run-in | Construct. | VI Threats to Validity, par. 7 |
| IX-F | subsection | Experiments Still Required | VI Threats to Validity, par. 8 |
| X | section | Discussion | VII Discussion and Conclusion, par. 1 |
| X | run-in | What a practitioner learns beyond the estimate. | VII Discussion and Conclusion, par. 1 |
| X | run-in | Migration planning. | VII Discussion and Conclusion, par. 2 |
| X | run-in | For library authors. | VII Discussion and Conclusion, par. 3 |
| X | run-in | Where the cost lies. | VII Discussion and Conclusion, par. 4 |
| X | run-in | Capacity of the store. | VII Discussion and Conclusion, par. 5 |
| XI | section | Conclusion | VII Discussion and Conclusion, par. 6 |
|  | section | Data and Code Availability | back matter Data and Code Availability, par. 1 |

New text with no predecessor: I par. 9 (the one sentence that replaces the research questions),
and the back-matter sections Author Contributions, Funding, Conflicts of Interest, Use of
Generative AI.

## 3. Change log

| Task | Location (new) | Change |
|---|---|---|
| 1 | I | Deleted the "Research questions." paragraph; added one closing sentence stating what the paper measures |
| 1 | V-A to V-E | Removed "(RQ1)" and "(RQ2)" from eight subsection titles (the titles themselves are replaced by the Task 2 outline) |
| 1 | Table VI (`tab-sources`) | "open loop (RQ3)" to "open loop" (generator and generated file) |
| 1 | IV-C par. 3 | "The confirmatory hypothesis is the ratio P1/B2" to "The pre-registered hypothesis is the ratio P1/B2"; cells, TOST, margin and Holm correction unchanged |
| 1 | `analysis/*.py` | Three code comments and one report heading no longer say "RQ3" |
| 2 | whole paper | 11 sections and 43 subsections reduced to 7 sections and 13 subsections as specified; no sub-subsections |
| 2 | whole paper | 60 bold or italic run-in headings replaced by topic sentences or, where the first sentence already carried the information, removed; see section 2. Italic lead-ins inside paragraphs (profiling, sessions, "A limitation of this family") set upright, wording unchanged |
| 2 | I par. 7 | C1 to C3 kept as a list; bold titles turned into plain lead-ins |
| 2 | V-G | A1 to A5 kept as an enumerated sequence; bold titles turned into plain sentences |
| 2 | IV-B, IV-C, V-F, VI | Six short topic sentences added where a subsection title disappeared ("The metrics are defined as follows.", "The second tool of the analysis is a CPU accounting identity.", "There were five deviations from the pre-registration.", "A session changes what a compromise exposes.", "We first examine run-to-run variation.", "Order and time effects were checked as follows.") and "rule" to "stall rule" in VI par. 2 |
| 2 | VII par. 6 | "We evaluated" to "In conclusion, we evaluated" |
| 3 | Abstract | Replaced with the supplied text; numbers kept as macros; mismatches listed in section 0 |
| 4.1 | Table III (`tab:claims`) | "native clients" to "native clients other than the GET-only Go reader" |
| 4.2 | Table XI (`tab-tost`) | Group headers "batches E, EK" / "batches I, IK" to the labels Primary-x86 / Primary-ARM |
| 4.2 | Fig. 2, Fig. 3 captions | TODO to regenerate the figures with purpose labels |
| 4.3 | II-A par. 3 | "is an instance of" to "has the structure of" |
| 4.4 | Table XIV (`tab-model`) and its caption | Column "Predicted" to "Implied by CPU" |
| 4.5 | III par. 2 | "as HPKE base mode does not either" to "and neither does HPKE base mode" |
| 4.6 | IV-A par. 9 | "For the replication of Section ... we wrote a second, deliberately small client in Go" to "As a second client (Section ...) we wrote a deliberately small reader in Go" |
| 4.7 | whole paper | Every old section label is attached to the heading that absorbed it, so all references resolve to new numbers; five references that would have pointed at their own section reworded ("described below", "see the CPU accounting below", "see the end of this subsection", "described above" twice) |
| 5 | Data and Code Availability | "available from the corresponding author on request" and the "not public / no persistent identifier" sentence replaced by the archive statement with two DOI TODOs |
| 5 | back matter | Added Author Contributions, Funding, Conflicts of Interest, Use of Generative AI |
| 5 | II-B par. 4 | Hit-count TODO next to the limitation sentence, which is kept |
| 5 | I par. 7, IV-B par. 7, IV-C par. 2, VII par. 5 | Supplement TODO at each of the four mentions of the supplementary material |
| 5 | preamble | `xcolor` and the `\TODO` macro restored |

## 4. TODOs left in the source (17)

| No. | Location | TODO |
|---|---|---|
| 1 | I par. 7 | confirm supplementary file contains queueing protocol, results and Appendix A |
| 2 | II-B par. 4 | hit counts for IEEE Xplore, ACM DL, IACR ePrint, Google Scholar |
| 3 | IV-B par. 7 | confirm supplementary file (as 1) |
| 4 | IV-C par. 2 | confirm supplementary file (as 1) |
| 5 | Fig. 2 caption | regenerate figure with purpose labels |
| 6 | Fig. 3 caption | regenerate figure with purpose labels |
| 7 | VII par. 5 | confirm supplementary file (as 1) |
| 8 | Data and Code Availability | Zenodo DOI |
| 9 | Data and Code Availability | data DOI |
| 10 to 14 | Author Contributions | CRediT roles, one per author |
| 15 | Funding | source of AWS costs |
| 16 | Conflicts of Interest | confirm none |
| 17 | Use of Generative AI | statement per target journal policy |

## 5. Diff summary (output of `paper/tools/check_pass2.py`)

```
== body (after abstract) ==
macro multiset: IDENTICAL
digit-token multiset: {'2': (61, 55), '3': (62, 61), '1': (127, 121), '25519': (79, 78), '16': (17, 16), '500': (25, 24)}
== abstract ==
macro multiset: IDENTICAL
digit-token multiset: {'86': (1, 2), '768': (0, 1)}
finding boxes: 6 6 byte-identical and in order
floats changed (old side): ['\\begin{table*}[t]\n\\caption{Claim taxonomy}\n\\label{tab:claims', '\\begin{figure}[t]\n\\centering\n\\includegraphics[width=\\columnw', '\\begin{figure*}[t]\n\\centering\n\\includegraphics[width=\\textwi', '\\begin{table}[t]\n\\caption{CPU accounting on 64\\,KiB GET: the']
floats changed (new side): ['\\begin{table*}[t]\n\\caption{Claim taxonomy}\n\\label{tab:claims', '\\begin{figure}[t]\n\\centering\n\\includegraphics[width=\\columnw', '\\begin{figure*}[t]\n\\centering\n\\includegraphics[width=\\textwi', '\\begin{table}[t]\n\\caption{CPU accounting on 64\\,KiB GET: the']
RQ: 0  em dashes: 0  subsubsection: 0  bold/italic run-ins: 0
headings:
   \section{Introduction}
   \section{Background and Related Work}
   \subsection{Post-Quantum KEMs, Hybrids and HPKE}
   \subsection{Related Measurements}
   \subsection{Benchmarking Method}
   \section{Design and Threat Model}
   \section{Implementation and Methodology}
   \subsection{Implementation}
   \subsection{Testbeds and Workloads}
   \subsection{Statistical Analysis}
   \section{Results}
   \subsection{Per-Object Cost}
   \subsection{Where the Cost Appears}
   \subsection{Why the Saturated Client Is Slower}
   \subsection{Hybrid Key Establishment}
   \subsection{Storage Overhead}
   \subsection{Bounded Sessions}
   \subsection{Open Anomalies}
   \section{Threats to Validity}
   \section{Discussion and Conclusion}
   \section*{Data and Code Availability}
   \section*{Author Contributions}
   \section*{Funding}
   \section*{Conflicts of Interest}
   \section*{Use of Generative AI}
bibliography keys identical: True
baseline lines not present verbatim: 166
TODOs:
   \TODO{confirm supplementary file contains queueing protocol, results and Appendix A}
   \TODO{hit counts for IEEE Xplore, ACM DL, IACR ePrint, Google Scholar}
   \TODO{confirm supplementary file contains queueing protocol, results and Appendix A}
   \TODO{confirm supplementary file contains queueing protocol, results and Appendix A}
   \TODO{regenerate figure with purpose labels}
   \TODO{regenerate figure with purpose labels}
   \TODO{confirm supplementary file contains queueing protocol, results and Appendix A}
   \TODO{Zenodo DOI}
   \TODO{data DOI}
   \TODO{CRediT roles}
   \TODO{CRediT roles}
   \TODO{CRediT roles}
   \TODO{CRediT roles}
   \TODO{CRediT roles}
   \TODO{source of AWS costs}
   \TODO{confirm none}
   \TODO{statement per target journal policy}
```

Reading of that output:

- Pipeline macros: the multiset is identical in the body and in the abstract. No macro was added,
  dropped or moved out of its sentence.
- Digit tokens in the body: the only differences are removed heading text. "RQ1" three times and
  "RQ2" five times in titles, "RQ1/RQ2/RQ3" and "1--500" in the deleted paragraph, "N1" in the
  title "Bounded Sessions (Mode N1)", "X25519" in the title "ML-KEM against X25519: ..." and "16"
  in the run-in heading "Cells with 16 cores." account for every count. Nothing was added.
- Digit tokens in the abstract: "768" (ML-KEM-768) and a second "x86", both from the Task 3 text.
- Finding boxes 1 to 6: byte-identical and in the same order.
- Floats: four differ, all required: `tab:claims` (4.1), the captions of Fig. 2 and Fig. 3 (4.2)
  and the caption of `tab:model` (4.4). All other tables, figures and the algorithm are
  byte-identical.
- Citations: the same keys the same number of times; none added.
- The 166 baseline lines that no longer appear verbatim are the old abstract, the old headings,
  the research-questions paragraph, the first line of each former run-in paragraph, and the lines
  touched by Tasks 4 and 5. Deviations (1) to (5), anomalies A1 to A5, the "did not fix the
  following" list, the experiments (1) to (7) and every limitation sentence are among the lines
  that are present verbatim, apart from the opening words of A1 to A5.
