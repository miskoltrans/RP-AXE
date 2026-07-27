#!/usr/bin/env python3
"""Enumerate every program CAPSTONE contract -> manifest/capstone-contracts.tsv.

A capstone is a `complete_contract` entry in an RP0_PROGRAM's OBJECTIVES block: the mission that
actually discharges the program. RP-1 pays its programs as a calendar drip (Program.ProcessFunding,
a Hermite curve over nominalDurationYears) which AXE cannot port -- free unlimited timewarp turns any
calendar drip into infinite money. Moving that payout onto the capstones makes the money launch-gated
instead, which is the invariant docs/PROGRAMS.md already commits to.

Source of truth is RP-1's own Programs.cfg (reference only -- AXE does not run RP-1's program system);
each capstone is joined to the vendored contract in seed/Contracts/ so its CURRENT payout is visible
next to the program funding it would be drawing from.

Usage: python tools/extract_capstones.py [path-to-RP-1-Programs.cfg]
"""
import os
import re
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(os.path.dirname(REPO), "RP-1", "GameData", "RP-1", "Programs", "Programs.cfg")
SEED = os.path.join(REPO, "GameData", "RP-AXE", "seed", "Contracts")
OUT = os.path.join(REPO, "manifest", "capstone-contracts.tsv")


def blocks(txt, node):
    """Yield the body of each top-level `node { ... }`, brace-matched (values can contain braces)."""
    for m in re.finditer(node + r'\s*\{', txt):
        start, depth, j = m.end(), 1, m.end()
        while depth and j < len(txt):
            if txt[j] == '{':
                depth += 1
            elif txt[j] == '}':
                depth -= 1
            j += 1
        yield txt[start:j - 1]


def sub(block, node):
    return next(blocks(block, node), "")


def val(block, key):
    m = re.search(r'^\s*' + key + r'\s*=\s*(.+?)\s*$', block, re.M)
    return m.group(1).strip() if m else ""


def load_seed_contracts():
    """name -> current payout fields, from the vendored CONTRACT_TYPEs."""
    out = {}
    for root, _, files in os.walk(SEED):
        for fn in sorted(files):
            if not fn.endswith(".cfg"):
                continue
            path = os.path.join(root, fn)
            txt = open(path, encoding="utf-8", errors="replace").read()
            for b in blocks(txt, "CONTRACT_TYPE"):
                name = val(b, "name")
                if not name:
                    continue
                # Strip trailing // comments off reward values (RP-1 annotates several).
                clean = lambda k: re.sub(r'\s*//.*$', '', val(b, k)).strip()  # noqa: E731
                out[name] = dict(
                    title=val(b, "title"), advance=clean("advanceFunds"), reward=clean("rewardFunds"),
                    science=clean("rewardScience"), rep=clean("rewardReputation"),
                    prestige=val(b, "prestige"), maxc=val(b, "maxCompletions"),
                    file=os.path.relpath(path, SEED).replace("\\", "/"))
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.exists(src):
        sys.exit(f"Programs.cfg not found at {src}\nPass the path as an argument.")
    txt = open(src, encoding="utf-8", errors="replace").read()
    seed = load_seed_contracts()

    rows, nocap = [], []
    for b in blocks(txt, "RP0_PROGRAM"):
        obj = sub(b, "OBJECTIVES")
        caps = [c for c in re.findall(r'^\s*complete_contract\s*=\s*(\S+)', obj, re.M) if c != "TODO"]
        name = val(b, "name")
        if not caps:
            nocap.append(name)
            continue
        status = "un-chartered" if val(b, "isDisabled") == "true" else "chartered"
        for c in caps:
            i = seed.get(c, {})
            rows.append([name, val(b, "title"), val(b, "baseFunding"), val(b, "fundingCurve") or "-",
                         val(b, "nominalDurationYears"), status, len(caps), c,
                         i.get("title", "MISSING FROM SEED"), i.get("advance", ""), i.get("reward", ""),
                         i.get("science", ""), i.get("rep", ""), i.get("prestige", ""),
                         i.get("maxc", ""), i.get("file", "")])

    hdr = ["program", "programTitle", "baseFunding", "curve", "nominalYears", "axeStatus", "nCapstones",
           "capstone", "capstoneTitle", "advanceFunds", "rewardFunds", "rewardScience",
           "rewardReputation", "prestige", "maxCompletions", "file"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(hdr) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    def fnum(s):
        try:
            return float(s)
        except (TypeError, ValueError):
            return 0.0

    counts = Counter(r[7] for r in rows)
    shared = {k: v for k, v in counts.items() if v > 1}
    chartered = [r for r in rows if r[5] == "chartered"]
    paying = [r for r in rows if fnum(r[10]) > 0 or fnum(r[9]) > 0]
    missing = [r[7] for r in rows if r[8] == "MISSING FROM SEED"]

    print(f"wrote {os.path.relpath(OUT, REPO)}")
    print(f"  {len(rows)} capstone slots / {len(counts)} distinct contracts / "
          f"{len({r[0] for r in rows})} programs")
    print(f"  chartered: {len(chartered)} slots across {len({r[0] for r in chartered})} programs, "
          f"baseFunding {sum({r[0]: fnum(r[2]) for r in chartered}.values()):,.0f}")
    print(f"  paying funds today: {len(paying)}")
    if missing:
        print(f"  !! capstones absent from the vendored seed ({len(missing)}): {sorted(set(missing))}")
    if nocap:
        print(f"  !! programs with NO capstone objective ({len(nocap)}): {sorted(nocap)}")
    if shared:
        by = defaultdict(list)
        for r in rows:
            by[r[7]].append(r[0])
        print(f"  !! shared across programs ({len(shared)}) -- one completion, several claims:")
        for k in sorted(shared, key=lambda k: -shared[k]):
            print(f"       {k:<24} x{shared[k]}  {by[k]}")


if __name__ == "__main__":
    main()
