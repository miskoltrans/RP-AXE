#!/usr/bin/env python3
"""check_experiment_gates.py -- does each experiment unlock WHERE its instrument unlocks?

The failure shape this catches is not "a string resolved to nothing" (check_liveness's family) but
"a string resolved to the WRONG node". An experiment reaches the player by two independent routes:

  1. a DEDICATED INSTRUMENT PART -- one part, one bare `Experiment` module, gated by the part's own
     TechRequired (which AxePartPlacement.cfg sets from tree/nodes.yaml). RO-RPWS carries RP0RPWS3
     and unlocks at mic_dipoleWaveSpectrometry; that IS the ladder.
  2. a Kerbalism `Configure` SETUP -- the US2 science wedges and probe cores offer the same
     experiment from a menu, gated by the SETUP's own `tech = <node>`.

Nothing ties the two together. Move the instrument to a new node and route 1 follows automatically;
route 2 keeps whatever node it was authored with, silently. Both routes work, neither errors, and the
tree renders fine -- the only symptom is that the wedge hands you a rung you have not bought yet
(EARLY: the later nodes stop being worth researching) or withholds one you have (LATE: the node you
just bought unlocks no new science). RP-AXE shipped both directions at once:

  RP0RPWS2/3   gated mic_plasmaWave T8, instruments at T9/T10  -- EARLY, two rungs skippable
  RP0magScan2  gated mic_boomMagnetometryII T8, instrument at T5 -- LATE, T5 node unlocked no science

Both were remap collateral: RP-1 gated those SETUPs on three DIFFERENT nodes (scienceLunar /
scienceAdvCapsules / deepSpaceScience), and the port to AXE node ids flattened them onto one.

The check: for every experiment with a sole-carrier part (exactly one distinct experiment_id, no
Configure module, placed on a real AXE node), every SETUP gate for that experiment must name that
same node. Deliberate splits go in ALLOW with a reason -- an experiment MAY legitimately home away
from its hardware (see the entry below), but it has to be argued, not defaulted into.

Needs a booted instance: route 1 is only knowable after the merge (which part ended up carrying
what). Route 2 comes from tools/experiment_index.py over the shipped configs.

  python tools/check_experiment_gates.py                   # defaults to ../Instance
  python tools/check_experiment_gates.py --instance <root>
"""
import argparse, collections, os, re, sys

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(ROOT, ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import experiment_index

# Experiments deliberately gated away from their instrument's node. Reason is mandatory: this file is
# the record of which mismatches were argued rather than overlooked.
ALLOW = {
    "RP0orbitalPurturbation1":
        "Scatter-by-difficulty, deliberate (design/Science/Configure.cfg): the experiment needs NO "
        "instrument -- it is read off the tracked orbit -- so it homes at precision ground tracking "
        "(tel_minitrackInterferometry T3, Vanguard 1 / 1958), while the gravimeter HARDWARE homes at "
        "its own bottleneck (gnc_orbitalGravimetry T8). Also the largest science supply in the T3-T5 "
        "trough; see docs/SCIENCE.md.",
}


def tiers():
    """node id -> tier, from tree/nodes.yaml."""
    d = yaml.safe_load(open(os.path.join(REPO, "tree", "nodes.yaml"), encoding="utf-8"))
    nodes = d["nodes"] if isinstance(d, dict) else d
    return {n["id"]: n.get("tier") for n in nodes}


def sole_carriers(cache, valid):
    """experiment id -> {(part, node)} for parts that carry exactly ONE experiment, bare.

    "Bare" = no Configure module, so the part's own TechRequired is the whole gate. That pair of
    conditions is what separates a ladder instrument from a probe bus: rn_cassini carries a dozen
    experiments, a US2 wedge serves its through a Configure, and neither is the rung we mean."""
    txt = open(cache, encoding="utf-8", errors="replace").read()
    out = collections.defaultdict(set)
    for m in re.finditer(r"\n\tPART\n\t\{\n\t\tname = (\S+)\n", txt):
        i = txt.index("{", m.start())
        depth, end = 0, i
        while end < len(txt):
            if txt[end] == "{":
                depth += 1
            elif txt[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        body = txt[m.start():end + 1]
        exps = set(re.findall(r"^\s*experiment_id = (\S+)", body, re.M))
        if len(exps) != 1:
            continue
        if re.search(r"^\t\t\tname = Configure$", body, re.M):
            continue
        tech = re.search(r"^\t\tTechRequired = (\S+)", body, re.M)
        if not tech or tech.group(1) not in valid:
            continue
        out[exps.pop()].add((m.group(1), tech.group(1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", default=os.path.join(os.path.dirname(REPO), "Instance"))
    args = ap.parse_args()
    cache = os.path.join(args.instance, "GameData", "ModuleManager.ConfigCache")
    if not os.path.exists(cache):
        print(f"FATAL: {cache} not found -- boot the instance once first.")
        return 2

    tier = tiers()
    idx, _ = experiment_index.build(valid=set(tier))
    gates = collections.defaultdict(set)
    for nid, unlocks in idx.items():
        for e in unlocks:
            gates[e["id"]].add(nid)

    carriers = sole_carriers(cache, set(tier))
    bad, allowed = [], []
    for eid, gnodes in sorted(gates.items()):
        carried = carriers.get(eid)
        if not carried:
            continue
        homes = {n for _, n in carried}
        stray = sorted(g for g in gnodes if g not in homes)
        if not stray:
            continue
        (allowed if eid in ALLOW else bad).append((eid, stray, sorted(carried)))

    print(f"{len(carriers)} sole-carrier experiment(s) cross-checked against "
          f"{sum(len(v) for v in gates.values())} SETUP gate(s)")
    print(f"\n=== experiments gated away from their instrument's node ({len(bad)}) ===")
    for eid, stray, carried in bad:
        gt = min(tier[g] for g in stray)
        ct = min(tier[n] for _, n in carried)
        way = f"EARLY by {ct - gt} tier(s)" if gt < ct else f"LATE by {gt - ct} tier(s)"
        print(f"  {eid}  --  {way}")
        print(f"      gated at   {', '.join(f'{g} (T{tier[g]})' for g in stray)}")
        print(f"      instrument {', '.join(f'{p} @ {n} (T{tier[n]})' for p, n in carried)}")
    if not bad:
        print("  every sole-carrier experiment unlocks on its own instrument's node")
    for eid, stray, carried in allowed:
        print(f"  allowed  {eid}: {ALLOW[eid].splitlines()[0]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
