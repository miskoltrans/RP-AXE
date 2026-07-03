#!/usr/bin/env python3
"""Classify every RP-1 science experiment as CREWED or UNCREWED. See docs/SCIENCE.md §2-§3.

Ground truth: the Kerbalism `MODULE { name = Experiment ... }` blocks that RP-1 adds to parts.
An experiment is CREWED if any such module sets `crew_operate` to a crew value
(True/CrewOnly/Pilot/Scientist/Engineer) OR the module is attached to a kerbalEVA* part
(EVA report / surface samples — collected by a Kerbal on EVA; Kerbalism doesn't tag these
with crew_operate, so the part context is the signal).

Emits manifest/experiment-crew.tsv:  experiment <TAB> crewed(1/0) <TAB> signal
Regenerate: python tools/experiment_crew.py
"""
import os, re, glob

RP1 = os.environ.get("RP1_SCIENCE",
    "C:/git/ksp/RP-1/GameData/RP-1/Science")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    "..", "manifest", "experiment-crew.tsv")

CREWVALS = {"True", "CrewOnly", "Pilot", "Scientist", "Engineer"}

# EVA/crew experiments RP-1 patches onto parts via `@PART[*]:HAS[...]` rather than a literal
# `kerbalEVA*` selector, so part-context detection alone misses them. These are collected by a
# Kerbal on EVA (no uncrewed path): stock EVA report + the base surface sample. (surfaceSample2/3
# ARE on literal kerbalEVA* parts and get detected automatically; surfaceAnalysis is the robotic
# RO-SurfaceSampleScoop and stays uncrewed.)
KNOWN_EVA = {"evaReport", "surfaceSample"}


def strip_comments(text):
    out = []
    for ln in text.splitlines():
        i = ln.find("//")
        if i >= 0:
            ln = ln[:i]
        out.append(ln)
    return "\n".join(out)


class Node:
    def __init__(self, name):
        self.name = name
        self.values = {}
        self.children = []

    def add_val(self, k, v):
        self.values.setdefault(k, []).append(v)


def parse(text):
    text = strip_comments(text)
    root = Node("ROOT")
    stack = [root]
    pending = None
    for tok in re.split(r'(\{|\})', text):
        if tok == "{":
            n = Node((pending or "").strip())
            stack[-1].children.append(n)
            stack.append(n)
            pending = None
        elif tok == "}":
            if len(stack) > 1:
                stack.pop()
            pending = None
        else:
            for ln in tok.split("\n"):
                s = ln.strip()
                if not s:
                    continue
                if "=" in s and not s.endswith("="):
                    k, v = s.split("=", 1)
                    k = k.strip().lstrip("@%+!*")
                    stack[-1].add_val(k.strip(), v.strip())
                    pending = None
                else:
                    pending = s
    return root


def getval(n, key):
    return n.values.get(key, [None])[0]


# experiment_id -> {"crew": set(crew_operate values), "eva": bool, "seen": bool}
crew = {}


def rec(eid):
    return crew.setdefault(eid, {"crew": set(), "eva": False, "seen": False})


def walk(n, part_ctx):
    nm = n.name
    # track PART context so we can detect kerbalEVA* attachment
    mpart = re.match(r'^@?PART\[([^\]]*)\]', nm)
    ctx = part_ctx
    if mpart:
        ctx = mpart.group(1)

    if re.match(r'^@?EXPERIMENT_DEFINITION', nm):
        eid = None
        hid = re.search(r'#id\[([^\]]+)\]', nm)
        if hid:
            eid = hid.group(1)
        if not eid:
            eid = getval(n, "id")
        if eid:
            rec(eid)["seen"] = True

    if re.match(r'^@?MODULE', nm):
        names = n.values.get("name", [])
        eid = getval(n, "experiment_id")
        if not eid:
            h = re.search(r'#experiment_id\[([^\]]+)\]', nm)
            if h:
                eid = h.group(1)
        if eid and (("Experiment" in names) or ("experiment_id" in n.values)
                    or "#experiment_id" in nm):
            r = rec(eid)
            r["seen"] = True
            cv = getval(n, "crew_operate")
            if cv:
                r["crew"].add(cv)
            if ctx and "kerbalEVA" in ctx:
                r["eva"] = True

    for c in n.children:
        walk(c, ctx)


def main():
    for f in glob.glob(RP1 + "/**/*.cfg", recursive=True):
        try:
            txt = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        try:
            walk(parse(txt), None)
        except Exception:
            continue

    rows = []
    for eid, r in sorted(crew.items()):
        eva = r["eva"] or (eid in KNOWN_EVA)
        crewed = bool(r["crew"] & CREWVALS) or eva
        sig = ",".join(sorted(r["crew"] & CREWVALS)) or ("EVA" if eva else "uncrewed")
        if eva and (r["crew"] & CREWVALS):
            sig += "+EVA"
        rows.append((eid, 1 if crewed else 0, sig))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("experiment\tcrewed\tsignal\n")
        for eid, c, sig in rows:
            fh.write(f"{eid}\t{c}\t{sig}\n")

    nc = sum(1 for _, c, _ in rows if c)
    print(f"wrote {OUT}  ({len(rows)} experiments, {nc} crewed / {len(rows)-nc} uncrewed)")


if __name__ == "__main__":
    main()
