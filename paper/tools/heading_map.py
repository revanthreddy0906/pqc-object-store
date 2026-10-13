"""Heading map for the second restructuring pass: old heading -> new section and paragraph."""
import re, subprocess
old = subprocess.run(["git","show","q1-pass2-baseline:paper/main.tex"],capture_output=True,text=True,check=True).stdout.split("\n")
new = open("paper/main.tex").read().split("\n")
ROM = ["","I","II","III","IV","V","VI","VII","VIII","IX","X","XI"]
FLOAT = ("\\begin{table","\\begin{figure","\\begin{algorithm","\\finding")
# position of every line of the new source
pos, sec, sub, para, name, inblock, isfloat = {}, 0, 0, 0, "", False, False
for i, l in enumerate(new):
    if l.startswith("\\section{"): sec += 1; sub = 0; para = 0; name = re.findall(r"\{([^}]*)\}", l)[0]
    if l.startswith("\\section*{"): sec, sub, para, name = 99, 0, 0, re.findall(r"\{([^}]*)\}", l)[0]
    if l.startswith("\\subsection{"): sub += 1; para = 0; name = re.findall(r"\{([^}]*)\}", l)[0]
    if not l.strip(): inblock = False; continue
    if l.startswith(("\\section", "\\subsection")): continue
    if not inblock:
        inblock = True; isfloat = l.startswith(FLOAT)
        if not isfloat: para += 1
    num = "back matter" if sec == 99 else ROM[sec] + (f"-{chr(64+sub)}" if sub else "")
    pos.setdefault(l, f"{num} {name}, " + ("float" if isfloat else f"par. {para}"))
rows, s, ss = [], 0, 0
i = 0
def locate(j):
    for k in range(j, j + 12):
        if old[k].strip() and not old[k].startswith(("\\section","\\subsection","\\begin","\\caption","\\label","\\centering")) and old[k] in pos:
            return pos[old[k]]
    return "REMOVED"
for i, l in enumerate(old):
    if l.startswith("\\section{"):
        s += 1; ss = 0; rows.append((ROM[s], "section", re.findall(r"\{([^}]*)\}", l)[0], locate(i + 1)))
    elif l.startswith("\\section*{"):
        rows.append(("", "section", re.findall(r"\{([^}]*)\}", l)[0], locate(i + 1)))
    elif l.startswith("\\subsection{"):
        ss += 1; rows.append((f"{ROM[s]}-{chr(64+ss)}", "subsection", re.findall(r"\{([^}]*)\}", l)[0], locate(i + 1)))
    else:
        m = re.match(r"\\(?:textbf|emph)\{((?:[^{}]|\{[^{}]*\})*[.:])\}", l) or re.match(r"\\item\[\\textbf\{(C\d)\}\]", l)
        if m:
            num = f"{ROM[s]}" + (f"-{chr(64+ss)}" if ss else "")
            rows.append((num, "run-in", m.group(1), locate(i + 1)))
print("| Old no. | Kind | Old heading | New location |\n|---|---|---|---|")
for r in rows: print("| " + " | ".join(r) + " |")
