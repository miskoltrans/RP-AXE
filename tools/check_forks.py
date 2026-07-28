#!/usr/bin/env python3
"""Detect FALSE FORKS in tree/nodes.yaml — see docs/TREE.md §10.

A false fork is a node the tree narrates as a school-of-thought choice and then requires every
branch of, so the "choice" collapses into a purchase order. Signature: an `anyToUnlock: False`
convergence whose parents include two or more nodes sharing the SAME discipline AND the SAME tier
(parallel schools), rather than orthogonal prerequisites.

This is a REVIEW aid, not a build gate — a same-discipline same-tier pair is often a legitimate
convergence (a grapple really does need both linear and hinge actuation). Every hit needs reading:
say the two parents out loud and ask "must you really buy both?", and if you fork it, confirm each
branch owns content the other forfeits.

NOTE the schema constraint before fixing one: `anyToUnlock` is per-NODE, not per-parent, so
`A AND (B OR C)` is inexpressible. Fix shapes are (i) drop the AND-parent, (ii) insert an
OR-junction node, (iii) re-parent the AND-term upstream of both schools. See docs/TREE.md §10.

Usage:
    python tools/check_forks.py           # new candidates only (reviewed set suppressed)
    python tools/check_forks.py --all     # every hit, including the reviewed ones
"""
import collections
import os
import sys

import yaml

TREE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tree")

# Hits reviewed 2026-07-28 and deliberately kept as convergences (docs/TREE.md §10 "Dismissed").
# Each is a genuine "you need both", not two schools. Extend this when a new hit is reviewed-and-kept;
# do NOT extend it to silence something you have not actually read.
REVIEWED_OK = {
    "pc_hydrazineMonoprop",   # catalyst bed (HTP) + the amine lane that supplies the fuel — node comment defends both
    "pc_solidUpperStage",     # documented deliberate crossover: kick-motor precision x segmented-casting scale
    "av_mach2Turbojet",       # real physics — the Olympus 593 and R-13 have both afterburner and variable stators
    "rob_grappleEndEffector", # a grapple genuinely needs both linear extension and hinged joints
    # The radiation-shielded avionics ladder: shielded rung N = previous shielded rung + the unshielded
    # rung it shields. Ladder rungs, not parallel schools — a structural false positive of the heuristic.
    "shd_realTimeFlightComputer", "shd_networkedAvionics", "shd_multiplyRedundantFlightComputer",
    "shd_distributedAvionicsBus", "shd_softwareDefinedFlightControl",
    "shd_interoperableAvionicsStandard", "shd_commercialOffTheShelfAvionics",
}


def main():
    show_all = "--all" in sys.argv
    with open(os.path.join(TREE, "nodes.yaml"), encoding="utf-8") as f:
        nodes = yaml.safe_load(f)["nodes"]
    by = {n["id"]: n for n in nodes}

    kids = collections.defaultdict(list)
    for n in nodes:
        for p in n.get("parents") or []:
            kids[p].append(n["id"])

    hits, suppressed = [], 0
    for n in nodes:
        if n.get("anyToUnlock"):
            continue
        ps = [p for p in (n.get("parents") or []) if p in by]
        if len(ps) < 2:
            continue
        groups = collections.defaultdict(list)
        for p in ps:
            groups[(by[p]["discipline"], by[p]["tier"])].append(p)
        for (disc, tier), sibs in groups.items():
            if len(sibs) < 2:
                continue
            if n["id"] in REVIEWED_OK and not show_all:
                suppressed += 1
                continue
            hits.append((n, disc, tier, sibs, [p for p in ps if p not in sibs]))

    for n, disc, tier, sibs, others in sorted(hits, key=lambda h: (h[0]["tier"], h[0]["id"])):
        flag = "  [reviewed-ok]" if n["id"] in REVIEWED_OK else ""
        print(f'{n["id"]}  (T{n["tier"]} {n["discipline"]})  "{n["title"]}"{flag}')
        print(f"    parallel parents [{disc} T{tier}]:")
        for s in sibs:
            b = by[s]
            print(f'        {s}: "{b["title"]}"  parts={len(b.get("parts") or [])} '
                  f'upg={len(b.get("upgrades") or [])} dependents={len(kids[s])}')
        if others:
            print("    other parents: " + ", ".join(
                f'{p} (T{by[p]["tier"]} {by[p]["discipline"]})' for p in others))
        print()

    if hits:
        print(f"{len(hits)} candidate(s) to review"
              + (f"; {suppressed} reviewed-ok suppressed (--all to show)" if suppressed else ""))
    else:
        print(f"no new fork candidates ({suppressed} reviewed-ok suppressed; --all to show)")
    return 0  # review aid, never fails the build


if __name__ == "__main__":
    sys.exit(main())
