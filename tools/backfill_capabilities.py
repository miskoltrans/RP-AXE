#!/usr/bin/env python3
"""backfill_capabilities — give every tree-placed part a row in manifest/part-capabilities.tsv.

WHY THIS EXISTS
---------------
`part-capabilities.tsv` was built by joining the curated part list against RP-1's own tech tree, so
parts RP-1 never had a node for (SCANsat instruments, DMagic's US2 wedges, the Universal Storage 2
set, RO-MagellanRadar) simply have no row. That is invisible everywhere except pricing:
`build_tree.py`'s `costcat()` reads category/discipline/modules from this file, and a part with no
row classifies from four empty strings — it falls through every rule to `misc` (weight 1.0). Nine
SCANsat instruments and five DMagic science wedges were therefore priced as generic hardware
instead of instruments (2.5), silently, with nothing in the build output to say so.

WHAT IT WRITES
--------------
One row per missing part, mined from the live ModuleManager cache, matching the existing columns:
  name / mod / title / category / mass / rp1_tech / kind / disc / modules / propellants
  * `mod`      — first path segment of the cache's parentUrl
  * `disc`     — the discipline of the AXE node the part is placed on. Not a guess: the part is in
                 the tree, so its discipline is known exactly. (costcat reads disc for the
                 OpticsPhotonics -> science rule.)
  * `rp1_tech` — empty. Having no RP-1 tech node is the very reason the row was missing.
  * `kind`     — `AXEONLY`, distinct from the curation verdicts (CLEAN / CONVERGENCE / INTEGRATED /
                 SCIENCE) so hand-placed-only parts stay visible. Nothing reads this column.

Idempotent: existing rows are never touched, output stays sorted by name. Run after placing parts
that RP-1 did not have, then re-run `build_tree.py`.

Usage: python tools/backfill_capabilities.py [--dry-run]
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"
TSV = os.path.join(REPO, "manifest", "part-capabilities.tsv")


def cache_parts(wanted):
    """name -> dict(mod, title, category, mass, modules, propellants) for the wanted part names."""
    lines = open(CACHE, encoding="utf-8", errors="replace").read().split("\n")
    out, parent, i, n = {}, "", 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s.startswith("parentUrl ="):
            parent = s.split("=", 1)[1].strip()
        elif s == "PART" and i + 1 < n and lines[i + 1].strip() == "{":
            depth, j = 0, i + 1
            name = title = category = mass = None
            mods, props, mod_depth = [], [], None
            while j < n:
                t = lines[j].strip()
                if t == "{":
                    depth += 1
                elif t == "}":
                    depth -= 1
                    if depth == 0:
                        break
                elif depth == 1:
                    if t.startswith("name =") and name is None:
                        name = t.split("=", 1)[1].strip()
                    elif t.startswith("title ="):
                        title = t.split("=", 1)[1].strip()
                    elif t.startswith("category ="):
                        category = t.split("=", 1)[1].strip()
                    elif t.startswith("mass ="):
                        mass = t.split("=", 1)[1].strip()
                elif depth == 2 and t.startswith("name ="):
                    # depth 2 = a MODULE's own name (also PROPELLANT/RESOURCE names, filtered by parent)
                    if mod_depth == "MODULE":
                        mods.append(t.split("=", 1)[1].strip())
                    elif mod_depth == "PROPELLANT":
                        props.append(t.split("=", 1)[1].strip())
                if t in ("MODULE", "PROPELLANT", "RESOURCE"):
                    mod_depth = t
                j += 1
            if name in wanted:
                out[name] = dict(mod=parent.split("/")[0], title=title or "", category=category or "",
                                 mass=mass or "", modules=";".join(mods), propellants=";".join(props))
            i = j + 1
            continue
        i += 1
    return out


def main():
    dry = "--dry-run" in sys.argv
    import build_tree as bt
    disc, meta, nodes = bt.load()
    by = {n["id"]: n for n in nodes}
    bt.resolve(disc, meta, nodes, by)
    p2n, _ = bt.merge_placement(nodes, by)

    with open(TSV, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        rows = [ln.rstrip("\n") for ln in f if ln.strip()]
    have = {r.split("\t")[0] for r in rows}
    missing = sorted(p for p, nd in p2n.items() if nd in by and p not in have)
    if not missing:
        print("backfill: nothing missing — every placed part has a capability row")
        return

    if not os.path.exists(CACHE):
        sys.exit(f"ModuleManager cache not found at {CACHE} (needed to mine the missing rows)")
    mined = cache_parts(set(missing))
    added, absent = [], []
    for p in missing:
        m = mined.get(p)
        if not m:
            absent.append(p)
            continue
        d = by[p2n[p]]["discipline"]
        added.append("\t".join([p, m["mod"], m["title"], m["category"], m["mass"], "", "AXEONLY",
                                d, m["modules"], m["propellants"]]))
    print(f"backfill: {len(missing)} placed parts had no capability row -> {len(added)} mined")
    for ln in added:
        c = ln.split("\t")
        print(f"   + {c[0]:<34} {c[1]:<22} cat={c[3]:<10} disc={c[7]}")
    if absent:
        print(f"   !! {len(absent)} not in the live cache (not installed?): {', '.join(absent)}")
    if dry:
        print("   (dry run — nothing written)")
        return
    allrows = sorted(rows + added, key=lambda r: r.split("\t")[0])
    with open(TSV, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(hdr) + "\n")
        f.write("\n".join(allrows) + "\n")
    print(f"   -> {os.path.relpath(TSV, REPO)} ({len(allrows)} rows)")


if __name__ == "__main__":
    main()
