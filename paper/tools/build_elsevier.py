"""Build the Elsevier (Computers & Security) submission from the IEEE source.

Reads paper/main.tex, swaps the IEEE front and back matter for elsarticle's, and writes a flat
folder paper/elsevier/ (Elsevier's submission system does not accept subfolders): main.tex, the
generated macro files, tables and figures it uses, references.bib and elsarticle-num.bst.
The body text is copied unchanged; every edit below is an asserted substitution.
Usage: python paper/tools/build_elsevier.py [path/to/elsarticle-num.bst]
"""
import pathlib
import re
import shutil
import sys

PAPER = pathlib.Path(__file__).resolve().parents[1]
OUT = PAPER / "elsevier"
BST = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "elsarticle-num.bst"

src = (PAPER / "main.tex").read_text()


def sub(text, old, new):
    if text.count(old) != 1:
        sys.exit(f"expected exactly one match for: {old[:70]!r}")
    return text.replace(old, new)


def between(text, start, end, new):
    """Replace text[start .. end] inclusive of both markers."""
    i, j = text.index(start), text.index(end) + len(end)
    return text[:i] + new + text[j:]


GAP = r"\authorsgap"
FRONT = r"""\begin{frontmatter}

\title{Benchmarking Post-Quantum Key Encapsulation in S3-Compatible Object Storage under Client Concurrency}

\author[cbit]{Revanth Reddy Lingala\corref{cor1}}
\ead{revanthreddy0906@gmail.com}
\author[cbit]{K. Gangadhara Rao}
\ead{kgangadhar\_it@cbit.ac.in}
\author[cbit]{Padigela Srujan}
\ead{padigela.srujan2007@gmail.com}
\author[cbit]{Saarthak Manocha}
\ead{saarthakmanocha@gmail.com}
\author[cbit]{Vainavi Venkat}
\ead{vainavivenkat06@gmail.com}

\cortext[cor1]{Corresponding author.}

\affiliation[cbit]{organization={Department of Information Technology, Chaitanya Bharathi Institute of Technology},
            city={Hyderabad},
            state={Telangana},
            country={India}}

ABSTRACT

\begin{highlights}
\item ML-KEM lowered object-store throughput only at or near client CPU saturation.
\item Python client: \RevHotDeficit{} to \ArmHotDeficit\,\% slower than X25519 when saturated.
\item Controls on x86 traced that deficit mainly to the library binding.
\item A native Go reader on one core was \AudNOneMlkemDeficit\,\% slower, so cost depends on implementation.
\item ML-KEM adds \RevMetaIntrinsic{} bytes of ciphertext per object over X25519.
\end{highlights}

\begin{keyword}
ML-KEM \sep hybrid KEM \sep envelope encryption \sep client-side encryption \sep
cloud storage security \sep equivalence testing \sep performance evaluation
\end{keyword}

\end{frontmatter}"""

BACK = r"""\section*{CRediT authorship contribution statement}
\textbf{Revanth Reddy Lingala:} \authorsgap{roles}.
\textbf{K. Gangadhara Rao:} \authorsgap{roles}.
\textbf{Padigela Srujan:} \authorsgap{roles}.
\textbf{Saarthak Manocha:} \authorsgap{roles}.
\textbf{Vainavi Venkat:} \authorsgap{roles}.

\section*{Declaration of competing interest}
\authorsgap{confirm or replace: The authors declare that they have no known competing financial
interests or personal relationships that could have appeared to influence the work reported in
this paper.}

\section*{Funding}
\authorsgap{source of the cloud (AWS) costs, or: This research did not receive any specific grant
from funding agencies in the public, commercial, or not-for-profit sectors.}

\section*{Declaration of generative AI and AI-assisted technologies in the writing process}
\authorsgap{During the preparation of this work the authors used [tool] in order to [purpose].
After using this tool, the authors reviewed and edited the content as needed and take full
responsibility for the content of the published article.}

\section*{Data availability}
DATA

"""

text = src
text = sub(text, r"\documentclass[conference]{IEEEtran}", r"\documentclass[review,12pt]{elsarticle}")
text = sub(text, r"\usepackage[hidelinks]{hyperref}",
           "\\usepackage[hidelinks]{hyperref}\n\\usepackage{xcolor}\n"
           "% Marks text the authors must supply before submission.\n"
           "\\newcommand{\\authorsgap}[1]{\\textcolor{red}{[Authors to complete: #1]}}\n\n"
           "\\journal{Computers \\& Security}\n\\emergencystretch=3em")
text = text.replace("generated/", "")

abstract = text[text.index(r"\begin{abstract}"):text.index(r"\end{abstract}") + len(r"\end{abstract}")]
text = between(text, r"\title{", r"\end{IEEEkeywords}", FRONT.replace("ABSTRACT", abstract))

data = text[text.index(r"\section*{Data and Code Availability}"):text.index(r"\bibliographystyle{IEEEtran}")]
data_body = data.split("\n", 1)[1].strip()
text = between(text, r"\section*{Data and Code Availability}", r"\bibliographystyle{IEEEtran}",
               BACK.replace("DATA", data_body) + r"\bibliographystyle{elsarticle-num}")

# Single-column review layout: shrink wide tables to the text width (never enlarge narrow ones),
# keep column-width figures at a readable size, and let long URLs break.
text = sub(text, r"\usepackage{url}", r"\usepackage{xurl}" + "\n\\usepackage{adjustbox}")
text = text.replace(r"\resizebox{\columnwidth}{!}{", r"\adjustbox{max width=\textwidth}{")
text = re.sub(r"(?m)^\\input\{(tab-[^}]+)\}$", r"\\adjustbox{max width=\\textwidth}{\\input{\1}}", text)
text = re.sub(r"(\\begin\{tabular\}.*?\\end\{tabular\})",
              r"\\adjustbox{max width=\\textwidth}{\1}", text, flags=re.S)
text = re.sub(r"\\begin\{(table|figure|algorithm)(\*?)\}\[t\]", r"\\begin{\1\2}[!htbp]", text)
text = text.replace(r"\includegraphics[width=\columnwidth]", r"\includegraphics[width=0.75\textwidth]")

assert "IEEE" not in re.sub(r"IEEE Xplore", "", text), "IEEE command left over"

# flat output folder
OUT.mkdir(exist_ok=True)
for f in OUT.iterdir():
    if f.is_file() and not f.name.startswith(".") and (f.name != BST.name or BST.parent != OUT):
        f.unlink()
(OUT / "main.tex").write_text(text)
used = set(re.findall(r"\\(?:input|includegraphics(?:\[[^]]*\])?)\{([^}]+)\}", text))
for name in sorted(used):
    shutil.copy(PAPER / "generated" / name, OUT / name)
shutil.copy(PAPER / "references.bib", OUT / "references.bib")
if BST.parent != OUT:
    shutil.copy(BST, OUT / "elsarticle-num.bst")
print(f"wrote {OUT/'main.tex'} and {len(used)} generated files")
