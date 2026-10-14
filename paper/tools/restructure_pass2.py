"""Second restructuring pass: rebuild main.tex from the tagged baseline by moving line ranges.

Bodies are copied verbatim from `git show q1-pass2-baseline:paper/main.tex`; every textual change
is an explicit, asserted substitution below, so no number or macro is retyped.
Usage: python paper/tools/restructure_pass2.py > paper/main.tex
"""
import subprocess
import sys

BASE = subprocess.run(["git", "show", "q1-pass2-baseline:paper/main.tex"], capture_output=True,
                      text=True, check=True).stdout.split("\n")
SUPP = r"\TODO{confirm supplementary file contains queueing protocol, results and Appendix A}"


def R(a, b):
    """Lines a..b (1-indexed, inclusive) of the baseline."""
    return "\n".join(BASE[a - 1:b])


ABSTRACT = r"""\begin{abstract}
Data encrypted today with classical public-key algorithms could be decrypted once large quantum
computers exist. Cloud object stores keep data for years, so the client-side encryption that
protects it must move to post-quantum algorithms such as ML-KEM, which adds a key-encapsulation
step and a larger ciphertext to every stored object. So far, the cost of ML-KEM has been
measured for the algorithm on its own and for securing network connections, but not for
encrypting each object in a storage system that serves many clients at once. It has therefore
been unclear whether ML-KEM slows such a system, under which conditions, and why. We address
this problem by measuring per-object ML-KEM against classical key exchange on an S3-compatible
object store, with two client implementations, two processor types and up to 500 concurrent
workers, using pre-registered experiments and statistical equivalence tests. ML-KEM reduced
throughput only when the client's processor was at or near full load, with one unexplained
exception, and then by \RevHotDeficit{} to \ArmHotDeficit\,\% in our main client. Controlled
experiments on one processor type traced most of that loss to the way the software library was
called, and a second, native client showed that the size of the loss depends on the
implementation. The lasting cost is storage: \RevMetaIntrinsic{} more bytes per object than with
classical key exchange. The
results cover two clients, one single-node store and one cloud provider.
\end{abstract}"""

MEASURES = (
    "This paper measures what per-object ML-KEM-768 costs against RSA-4096, X25519 and\n"
    "symmetric-only baselines on the same data path; how that cost depends on object size,\n"
    "concurrency and a hybrid construction, and what causes it; and what bounded sessions trade\n"
    "for the key-establishment work they save.")

BACK = r"""\section*{Data and Code Availability}
Code, configurations, the pre-registration, per-run summaries, the raw-data validator, the
native reader (\texttt{native/}) and the analysis scripts that generate every figure, table and
number in this paper (\texttt{analysis/summarize.py}, \texttt{final\_analysis.py},
\texttt{make\_paper\_assets.py}, \texttt{revision\_assets.py}, \texttt{audit\_assets.py}) are in
the project repository, organized following ACM artifact guidelines~\cite{acmbadges}; the
configuration files record the random seed of every experiment, and the repository holds an
export of the hosting service's push log. The code, the configurations, the pre-registration,
the push-log export and the per-run summaries are archived at \TODO{Zenodo DOI}, and the raw
request records (about 11\,GB compressed) at \TODO{data DOI}.

\section*{Author Contributions}
Roles follow the CRediT taxonomy.
Revanth Reddy Lingala: \TODO{CRediT roles}.
Vainavi Venkat: \TODO{CRediT roles}.
Saarthak Manocha: \TODO{CRediT roles}.
Padigela Srujan: \TODO{CRediT roles}.
K. Gangadhara Rao: \TODO{CRediT roles}.

\section*{Funding}
\TODO{source of AWS costs}

\section*{Conflicts of Interest}
\TODO{confirm none}

\section*{Use of Generative AI}
\TODO{statement per target journal policy}"""

PIECES = [
    # ---------------------------------------------------------------- preamble and front matter
    R(1, 13),
    R(15, 44), ABSTRACT, R(63, 66),
    # ---------------------------------------------------------------- I
    R(68, 79), R(81, 89), R(91, 97), R(99, 105), R(107, 115), R(117, 145), R(154, 158), MEASURES,
    # ---------------------------------------------------------------- II
    "\\section{Background and Related Work}\\label{sec:background}\\label{sec:related}\n"
    "\\subsection{Post-Quantum KEMs, Hybrids and HPKE}\\label{sec:kems}\n" + R(162, 169),
    R(172, 177), R(180, 185) + "\n" + R(270, 280), R(188, 196), R(244, 250),
    "\\subsection{Related Measurements}\\label{sec:measurements}\n" + R(199, 201),
    R(203, 227), R(230, 241), R(253, 267), R(295, 302),
    "\\subsection{Benchmarking Method}\\label{sec:benchmethod}\n" + R(283, 292),
    # ---------------------------------------------------------------- III
    "\\section{Design and Threat Model}\\label{sec:design}\\label{sec:n1design}\\label{sec:hpke}\n"
    + R(306, 310),
    R(312, 317), R(319, 325), R(327, 338), R(341, 357), R(359, 379), R(382, 400), R(402, 429),
    R(432, 441), R(444, 460), R(463, 464), R(466, 482),
    # ---------------------------------------------------------------- IV
    "\\section{Implementation and Methodology}\\label{sec:method}\n"
    "\\subsection{Implementation}\\label{sec:impl}\n" + R(485, 487),
    R(489, 543), R(545, 551), R(554, 563), R(565, 569), R(572, 577), R(580, 591), R(593, 601),
    R(604, 609), R(612, 618), R(621, 628), R(631, 634),
    "\\subsection{Testbeds and Workloads}\\label{sec:campaigns}\n" + R(638, 639),
    R(641, 645), R(647, 653), R(655, 665), R(667, 696), R(698, 703), R(705, 711), R(714, 724),
    R(727, 736), "The metrics are defined as follows.\n" + R(739, 752), R(755, 759), R(761, 766),
    "\\subsection{Statistical Analysis}\\label{sec:tost}\\label{sec:cpumethod}\\label{sec:deviations}\n"
    + R(769, 778),
    R(780, 787), R(789, 803), R(805, 808), R(810, 812), R(814, 816),
    "The second tool of the analysis is a CPU accounting identity.\n" + R(819, 828),
    R(830, 836), R(838, 843), R(845, 847),
    "There were five deviations from the pre-registration.\n" + R(850, 858), R(860, 869),
    # ---------------------------------------------------------------- V
    "\\section{Results}\\label{sec:results}\n"
    "\\subsection{Per-Object Cost}\\label{sec:percost}\n" + R(873, 881),
    R(883, 888), R(890, 895), R(897, 899),
    "\\subsection{Where the Cost Appears}\\label{sec:bottleneck}\\label{sec:primary}\n"
    + R(902, 907),
    R(909, 914), R(917, 925), R(927, 932), R(934, 956), R(958, 963), R(1272, 1283),
    R(1285, 1290), R(966, 973), R(975, 983), R(985, 987), R(989, 995), R(997, 1005),
    R(1007, 1012), R(1014, 1020), R(1022, 1026), R(1028, 1035), R(1037, 1043), R(1045, 1050),
    R(1052, 1057), R(1059, 1063), R(1065, 1070), R(1072, 1075),
    "\\subsection{Why the Saturated Client Is Slower}\\label{sec:mechanism}\\label{sec:native}\n"
    + R(1078, 1079),
    R(1081, 1179), R(1182, 1224),
    "\\subsection{Hybrid Key Establishment}\\label{sec:hybrid}\n" + R(1227, 1269),
    "\\subsection{Storage Overhead}\\label{sec:metadata}\n" + R(1293, 1328),
    "\\subsection{Bounded Sessions}\\label{sec:tradeoff}\n"
    "A session changes what a compromise exposes.\n" + R(1385, 1393),
    R(1396, 1430), R(1433, 1444),
    "\\subsection{Open Anomalies}\\label{sec:anomalies}\n" + R(1331, 1381),
    # ---------------------------------------------------------------- VI
    "\\section{Threats to Validity}\\label{sec:validity}\\label{sec:pending}\n"
    "We first examine run-to-run variation.\n" + R(1448, 1452),
    R(1455, 1458), R(1461, 1464), R(1467, 1469), R(1472, 1517), R(1520, 1530),
    # ---------------------------------------------------------------- VII
    "\\section{Discussion and Conclusion}\\label{sec:discussion}\\label{sec:conclusion}\n"
    + R(1533, 1574),
    R(1577, 1596),
    R(1598, 1607), R(1609, 1612),
]

# (old, new): every textual change apart from the moves. Each `old` must occur exactly once.
SUBS = [
    # ---- author list and order as given by the authors
    ("\\cbitauthor{Revanth Reddy Lingala}{revanth252017@gmail.com}\\hfill\n"
     "\\cbitauthor{Vainavi Venkat}{vainu24@gmail.com}\\hfill\n"
     "\\cbitauthor{Saarthak Manocha}{saarthakmanocha@gmail.com}\\\\[10pt]\n"
     "\\hspace*{\\fill}\\cbitauthor{Padigela Srujan}{padigela.srujan2007@gmail.com}\\hspace{0.05\\textwidth}%\n"
     "\\cbitauthor{K. Gangadhara Rao}{kgangadhar\\_it@cbit.ac.in}\\hspace*{\\fill}}",
     "\\cbitauthor{Revanth Reddy Lingala}{revanthreddy0906@gmail.com}\\hfill\n"
     "\\cbitauthor{K. Gangadhara Rao}{kgangadhar\\_it@cbit.ac.in}\\hfill\n"
     "\\cbitauthor{Padigela Srujan}{padigela.srujan2007@gmail.com}\\\\[10pt]\n"
     "\\hspace*{\\fill}\\cbitauthor{Saarthak Manocha}{saarthakmanocha@gmail.com}\\hspace{0.05\\textwidth}%\n"
     "\\cbitauthor{Vainavi Venkat}{vainavivenkat06@gmail.com}\\hspace*{\\fill}}"),
    # ---- Task 2: run-in headings in the Introduction
    ("\\textbf{When a public-key KEM per object is needed.} If writer",
     "A public-key KEM per object is needed only in some deployments. If writer"),
    ("\\textbf{What is known.} Primitive-level",
     "What is known falls into three groups of measurements. Primitive-level"),
    ("\\textbf{What is not known.} None of these",
     "What is not known is the cost on the data path of an object store. None of these"),
    ("\\textbf{Thesis.} In the configurations",
     "The thesis of this paper is the following. In the configurations"),
    ("\\textbf{Contributions.}\n", "The contributions are the following.\n"),
    ("\\item[\\textbf{C1}] \\textbf{The saturation-regime result, with a method to apply it.} Measurements",
     "\\item[C1] The saturation-regime result, with a method to apply it: measurements"),
    ("\\item[\\textbf{C2}] \\textbf{A binding artifact, and what it implies for library authors.} Two",
     "\\item[C2] A binding artifact, and what it implies for library authors: two"),
    ("\\item[\\textbf{C3}] \\textbf{The storage cost.} The per-object",
     "\\item[C3] The storage cost: the per-object"),
    ("\\textbf{Scope.} We do not evaluate",
     "The scope of the study is limited as follows. We do not evaluate"),
    # ---- Task 4.3
    ("Per-object envelope encryption is an instance of HPKE's single-recipient\nbase mode.",
     "Per-object envelope encryption has the structure of HPKE's single-recipient\nbase mode."),
    # ---- Task 5: search hit counts
    ("the IACR ePrint archive or Google Scholar, which is a limitation of that statement.",
     "the IACR ePrint archive or Google Scholar, which is a limitation of that statement\n"
     "\\TODO{hit counts for IEEE Xplore, ACM DL, IACR ePrint, Google Scholar}."),
    # ---- Section III
    ("\\textbf{Writers are not authenticated.} The envelope encrypts to a public key and carries no\n"
     "signature, as HPKE base mode does not either.",
     "Writers are not authenticated. The envelope encrypts to a public key and carries no\n"
     "signature, and neither does HPKE base mode."),
    ("\\textbf{Rollback is not prevented.} Replay", "Rollback is not prevented. Replay"),
    ("\\textbf{Key commitment.} AES-GCM",
     "A third limit concerns key commitment. AES-GCM"),
    ("over a bounded session (Section~\\ref{sec:n1design}).",
     "over a bounded session (described below)."),
    ("distributed deployments, native clients, other regions",
     "distributed deployments, native clients other than the GET-only Go reader, other regions"),
    # ---- Section IV-A
    ("For the replication of Section~\\ref{sec:native} we wrote a second, deliberately small client in\nGo",
     "As a second client (Section~\\ref{sec:native}) we wrote a deliberately small reader in\nGo"),
    # ---- Section IV-B
    ("\\textbf{What the timestamps show, and what they do not.} The commit",
     "The timestamps of the pre-registration show one thing and leave others open. The commit"),
    ("for the queueing analysis reported in the supplementary\nmaterial,",
     "for the queueing analysis reported in the supplementary\nmaterial " + SUPP + ","),
    # ---- Section IV-C
    ("\\textbf{Margin.} Five percent is our smallest effect of interest and was fixed in advance,",
     "The margin of five percent is our smallest effect of interest and was fixed in advance,"),
    ("this store (supplementary material) and needs",
     "this store (supplementary material " + SUPP + ") and needs"),
    ("\\textbf{Primary family and multiplicity.} The confirmatory hypothesis is the ratio P1/B2",
     "The pre-registered hypothesis is the ratio P1/B2"),
    ("\\emph{A limitation of this family, recognized after the\ncampaign:} only",
     "A limitation of this family, recognized after the\ncampaign: only"),
    ("spare\nCPU, which a costlier mode simply uses (Section~\\ref{sec:cpumethod}).",
     "spare\nCPU, which a costlier mode simply uses (see the CPU accounting below)."),
    ("\\textbf{Power.} From the paired",
     "The number of repetitions follows from a power calculation. From the paired"),
    ("\\textbf{Distributional assumption.} The $t$-tests",
     "The tests rest on a distributional assumption. The $t$-tests"),
    ("\\textbf{Stall rule.} Fixed in advance and blind to the mode: a closed-loop",
     "The stall rule was fixed in advance and is blind to the mode: a closed-loop"),
    ("\\textbf{Saturation criterion.} For the native",
     "The saturation criterion differs between the two clients. For the native"),
    ("\\textbf{What counts as a throughput deficit.} To say",
     "A throughput deficit is defined by one rule. To say"),
    ("was decided afterwards and is exploratory\n(Section~\\ref{sec:deviations}).",
     "was decided afterwards and is exploratory\n(see the end of this subsection)."),
    ("\\textbf{Status as a prediction.} The identity", "The identity"),
    ("\\textbf{Not pre-specified.} The pre-registration fixed",
     "Several analyses were not pre-specified. The pre-registration fixed"),
    ("the CPU accounting of Section~\\ref{sec:cpumethod}, the saturation criterion",
     "the CPU accounting described above, the saturation criterion"),
    # ---- Section V-B
    ("\\caption{Median latency against object size, one worker (\\lab{Expl-Size}; log scales).}",
     "\\caption{Median latency against object size, one worker (\\lab{Expl-Size}; log scales). "
     "\\TODO{regenerate figure with purpose labels}}"),
    ("64\\,KiB PUT from \\lab{Expl-SmallPUT}, others from \\lab{Expl-Sweep}.}",
     "64\\,KiB PUT from \\lab{Expl-SmallPUT}, others from \\lab{Expl-Sweep}. "
     "\\TODO{regenerate figure with purpose labels}}"),
    ("\\textbf{Attribution of the small-PUT ceiling.} In the exploratory",
     "The small-PUT ceiling is attributed by profiling the server directly. In the exploratory"),
    ("\\emph{The device is not the limit:} over", "The device is not the limit: over"),
    ("\\emph{System-call time goes to locks and the namespace:} of",
     "System-call time goes to locks and the namespace: of"),
    ("\\emph{The CPU profile agrees:} \\RevProfCpuUser", "The CPU profile agrees: \\RevProfCpuUser"),
    ("\\emph{All cells.} Applying", "We first look at all cells. Applying"),
    ("\\emph{Large objects.} All four",
     "For large objects the verdict is equivalence throughout. All four"),
    ("\\emph{The saturated cell.} At 64",
     "The saturated cell is the one that shows a cost. At 64"),
    ("\\emph{Noise, not difference, in small PUT.} The two",
     "In small PUT the inconclusive verdicts reflect noise, not a difference. The two"),
    ("the server-side variation described in\nSection~\\ref{sec:bottleneck}.",
     "the server-side variation described\nabove."),
    ("\\emph{Follow-up with adequate power.} Because",
     "We followed up with adequate power. Because"),
    ("\\emph{The cost is visible in CPU even where throughput does not move.}\n",
     "The cost is visible in CPU even where throughput does not move.\n"),
    ("\\emph{Sensitivity.} A percentile",
     "The verdicts were checked for sensitivity to the test, the margin and stalled runs. "
     "A percentile"),
    ("\\textbf{Exploratory campaign.} For context,", "For context,"),
    # ---- Section V-C
    ("\\textbf{Applying the CPU accounting.} Table", "Table"),
    ("(column ``Predicted'', computed", "(column ``Implied by CPU'', computed"),
    ("\\textbf{Where the extra CPU is not.} Table",
     "The stage timers show where the extra CPU is not. Table"),
    ("\\textbf{\\lab{Control-Manifest}: manifest size.} Mode C2",
     "The first control, \\lab{Control-Manifest}, tests manifest size. Mode C2"),
    ("\\textbf{\\lab{Control-Binding}: the library binding.} Our client",
     "The second control, \\lab{Control-Binding}, tests the library binding. Our client"),
    ("\\textbf{What the controls establish.} On the x86",
     "The controls establish the following. On the x86"),
    ("\\textbf{The one advance prediction missed.} Before",
     "The one advance prediction missed. Before"),
    ("\\textbf{Result.} In the saturated cell ML-KEM reaches",
     "The result for the native reader is as follows. In the saturated cell ML-KEM reaches"),
    ("\\textbf{Where the native reader's extra CPU goes.} With liboqs",
     "Part of the native reader's extra CPU can be located. With liboqs"),
    ("\\textbf{Cells with 16 cores.} With 16 cores", "With 16 cores"),
    # ---- Section V-D
    ("\\textbf{Cost per object.} X-Wing takes",
     "We first give the cost of the hybrids per object. X-Wing takes"),
    ("\\textbf{Primary cells.} Table", "Table"),
    ("\\textbf{Matrix.} Table", "Table"),
    # ---- Section V-F
    ("\\emph{Operations per object} follow", "Operations per object follow"),
    ("\\emph{Client CPU} per request falls", "Client CPU per request falls"),
    ("\\emph{Throughput and tail latency} do not change",
     "Throughput and tail latency do not change"),
    # ---- Section V-G
    ("\\textbf{(A1) A slower key derivation with ML-KEM.} At one",
     "(A1) Key derivation on GET at one worker is slower with ML-KEM. At one"),
    ("\\textbf{(A2) A native deficit without saturation.} In",
     "(A2) The native reader shows a deficit without saturation. In"),
    ("\\textbf{(A3) X-Wing below X25519 in a Python cell we call unsaturated.} At",
     "(A3) X-Wing is below X25519 in a Python cell we call unsaturated. At"),
    ("\\textbf{(A4) ML-KEM faster than X25519 at one worker.} By",
     "(A4) In some exploratory cells ML-KEM was faster than X25519 at one worker. By"),
    ("\\textbf{(A5) An allocator effect at 1\\,MiB.} In",
     "(A5) An allocator effect appears at 1\\,MiB. In"),
    # ---- Section VI
    ("The pre-registered rule flags \\RevStalls{}", "The pre-registered stall rule flags \\RevStalls{}"),
    ("Modes are shuffled within each repetition. As a check,",
     "Order and time effects were checked as follows. Modes are shuffled within each repetition. "
     "As a check,"),
    ("\\textbf{Internal.} Stage timers",
     "Threats to internal validity are the following. Stage timers"),
    ("\\textbf{External.} These are the limits of what the data supports.",
     "Threats to external validity are the limits of what the data supports."),
    ("\\textbf{Construct.} Throughput equivalence",
     "Threats to construct validity concern what the measures mean. Throughput equivalence"),
    # ---- Section VII
    ("\\textbf{What a practitioner learns beyond the estimate.} That tens",
     "A practitioner learns more from these measurements than the back-of-envelope estimate "
     "gives. That tens"),
    ("\\textbf{Migration planning.} The CPU accounting",
     "For migration planning, the CPU accounting"),
    ("\\textbf{For library authors.} A binding",
     "For library authors the lesson concerns bindings. A binding"),
    ("\\textbf{Where the cost lies.} The cost", "The cost"),
    ("\\textbf{Capacity of the store.} The open-loop measurements are reported in the supplementary\n"
     "material because",
     "On the capacity of the store, the open-loop measurements are reported in the supplementary\n"
     "material " + SUPP + " because"),
    ("We evaluated per-object post-quantum key establishment",
     "In conclusion, we evaluated per-object post-quantum key establishment"),
    # ---- supplementary material cited in the Introduction
    ("The open-loop capacity observations in the supplementary\nmaterial describe",
     "The open-loop capacity observations in the supplementary\nmaterial " + SUPP + " describe"),
]

text = "\n\n".join(PIECES) + "\n"
for old, new in SUBS:
    n = text.count(old)
    if n != 1:
        sys.exit(f"substitution matched {n} times: {old!r}")
    text = text.replace(old, new)
# Placeholders removed at the authors' request: the paper carries no TODO.
for gone in (" " + SUPP, "\n\\TODO{hit counts for IEEE Xplore, ACM DL, IACR ePrint, Google Scholar}",
             " \\TODO{regenerate figure with purpose labels}"):
    assert gone in text, gone
    text = text.replace(gone, "")
assert "TODO" not in text
sys.stdout.write(text)
