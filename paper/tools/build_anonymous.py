"""Write paper/main-anonymous.tex: main.tex with every author-identifying detail removed,
for double-anonymised review. Author details go on the separate title page."""
import pathlib
import sys

PAPER = pathlib.Path(__file__).resolve().parents[1]
text = (PAPER / "main.tex").read_text()


def sub(old, new):
    global text
    if text.count(old) != 1:
        sys.exit(f"expected one match: {old[:60]!r}")
    text = text.replace(old, new)


i = text.index("% IEEE author blocks")
j = text.index("\\maketitle")
text = text[:i] + "\\author{}\n\n" + text[j:]
sub("\\url{https://github.com/revanthreddy0906/pqc-object-store}; it has no persistent identifier.",
    "[link withheld for double-anonymised review; it is given on the title page]; it has no "
    "persistent identifier.")
for name in ("Revanth", "Lingala", "Chaitanya", "Gangadhara", "Srujan", "Saarthak", "Vainavi",
             "revanthreddy0906", "cbit.ac.in"):
    if name in text:
        sys.exit(f"identifying string left: {name}")
(PAPER / "main-anonymous.tex").write_text(text)
print("wrote paper/main-anonymous.tex")
