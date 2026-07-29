#!/usr/bin/env python3
"""Extract exact per-experiment body restrictions (KERBALISM_EXPERIMENT BodyAllowed/BodyNotAllowed)
from the RP-1 merged ModuleManager.ConfigCache → manifest/experiment-bodies.tsv.
This replaces science_budget.py's old keyword heuristic with ground truth.
Regenerate: python tools/experiment_bodies.py   (needs a built RP-1 cache; path via RP1_CACHE env)."""
import re, os

# Reference instances live NEXT TO this repo, i.e. <ksp root>/ksp_rp1_*. Derive that root from
# __file__ rather than hardcoding it: seven tools had "C:\git\ksp_rp1_*" (one directory too
# high), which made them die on FileNotFoundError while the data sat there intact. 2026-07-29.
_KSPROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.environ.get("RP1_CACHE",
                       os.path.join(_KSPROOT, "ksp_rp1_clean", "GameData", "ModuleManager.ConfigCache"))
OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifest", "experiment-bodies.tsv")

def brace_block(s, start):
    i=s.find('{',start); depth=0; j=i
    while j<len(s):
        if s[j]=='{': depth+=1
        elif s[j]=='}':
            depth-=1
            if depth==0: return s[i+1:j], j
        j+=1
    return "", len(s)

txt = open(CACHE, encoding="utf-8", errors="ignore").read()
rows={}
for m in re.finditer(r'(?m)^\s*EXPERIMENT_DEFINITION\s*$', txt):
    blk,_ = brace_block(txt, m.end())
    mid = re.search(r'(?m)^\s*id\s*=\s*(\S+)', blk)
    if not mid: continue
    eid = mid.group(1)
    ba = re.search(r'(?m)^\s*BodyAllowed\s*=\s*(\S+)', blk)
    bn = re.search(r'(?m)^\s*BodyNotAllowed\s*=\s*(\S+)', blk)
    cur = rows.get(eid, ("",""))
    rows[eid] = (cur[0] or (ba.group(1) if ba else ""), cur[1] or (bn.group(1) if bn else ""))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("experiment\tbodyAllowed\tbodyNotAllowed\n")
    for eid in sorted(rows):
        ba,bn = rows[eid]
        if ba or bn:                       # only emit experiments that carry a restriction
            f.write(f"{eid}\t{ba}\t{bn}\n")
n = sum(1 for v in rows.values() if v[0] or v[1])
print(f"parsed {len(rows)} EXPERIMENT_DEFINITIONs; wrote {n} with body restrictions -> {os.path.normpath(OUT)}")
