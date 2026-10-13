"""Guards for the second restructuring pass: compares paper/main.tex with the baseline tag."""
import re, subprocess, collections, sys
old = subprocess.run(["git","show","q1-pass2-baseline:paper/main.tex"],capture_output=True,text=True,check=True).stdout
new = open("paper/main.tex").read()
C = collections.Counter
def body(t): return t[t.index("\\end{abstract}"):]
def macros(t): return C(re.findall(r"\\(?:Rev|Arm|Aud|Hs|Hone|Hthree|Hfour|None|Qa|Ke|Mem|Server|Put|Get|Net|Rone|Stall|Total|Loc|Test|Liboqs|Minio|Python|Cryptography|Client|Link|RTT|Fio|Region|Pone)[A-Za-z]*", t))
def digits(t):
    t = re.sub(r"\\(?:ref|label|cite|input|includegraphics)\{[^}]*\}", "", t)
    return C(re.findall(r"\d[\d{},.]*\d|\d", t))
def diff(a, b, name):
    d = {k:(a[k],b[k]) for k in set(a)|set(b) if a[k]!=b[k]}
    print(f"{name}: {'IDENTICAL' if not d else d}")
print("== body (after abstract) ==")
diff(macros(body(old)), macros(body(new)), "macro multiset")
diff(digits(body(old)), digits(body(new)), "digit-token multiset")
print("== abstract ==")
ab = lambda t: t[t.index("\\begin{abstract}"):t.index("\\end{abstract}")]
diff(macros(ab(old)), macros(ab(new)), "macro multiset")
diff(digits(ab(old)), digits(ab(new)), "digit-token multiset")
f = lambda t: re.findall(r"\\finding\{(\d)\}\{(.*?)\}\n\n", t, re.S)
fo, fn = f(old), f(new)
print("finding boxes:", len(fo), len(fn), "byte-identical and in order" if fo==fn else "DIFFER")
fl = lambda t: C(re.findall(r"\\begin\{(?:table\*?|figure\*?|algorithm)\}.*?\\end\{(?:table\*?|figure\*?|algorithm)\}", t, re.S))
d = {k[:60]:v for k,v in (fl(old)-fl(new)).items()}; d2 = {k[:60]:v for k,v in (fl(new)-fl(old)).items()}
print("floats changed (old side):", list(d)); print("floats changed (new side):", list(d2))
print("RQ:", len(re.findall(r"RQ", new)), " em dashes:", new.count("—")+len(re.findall(r"(?<!-)---(?!-)", re.sub(r"(?m)^%.*$","",new))),
      " subsubsection:", new.count("\\subsubsection"), " bold/italic run-ins:", len(re.findall(r"(?m)^\\(?:textbf|emph)\{[^}]*[.:]\}", new)))
print("headings:"); [print("  ", h) for h in re.findall(r"\\(?:sub)?section\*?\{[^}]*\}", new)]
print("bibliography keys identical:", C(re.findall(r"\\cite\{([^}]*)\}", old))==C(re.findall(r"\\cite\{([^}]*)\}", new)))
# conservation of sentences: every baseline sentence-ish line should still exist verbatim unless listed
ol = [l for l in old.split("\n") if l.strip()]; nl = set(new.split("\n"))
missing = [l for l in ol if l not in nl]
print("baseline lines not present verbatim:", len(missing))
if "-v" in sys.argv: [print("   -", l[:150]) for l in missing]
print("TODOs:"); [print("  ", m) for m in re.findall(r"\\TODO\{[^}]*\}", new[new.index("\\begin{document}"):])]
