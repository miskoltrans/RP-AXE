#!/usr/bin/env python3
"""tier_report — the tier-by-tier view: what capability actually arrives at each tier, where the
frontier stalls, and which nodes hold a generation gap inside themselves.

Sections
  1. CAPABILITY FRONTIER   best intensive value reachable BY each tier, per family. A flat run
                           means that tier bought you nothing in that family; a big step means a
                           generation landed there.
  2. INTERNAL SPREAD       nodes where one family's intensive metric spans >1.5x inside the SAME
                           node -- the general form of "a clear upgrade sits on its own base's node".
  3. MISSION SPINE         the mission/charter nodes (int_/jpl_/okb_) by tier -- what you can fly
                           when -- against each family's first arrival, so a capability that lands
                           after the mission that needs it shows up as a negative slack.

Usage: python tools/tier_report.py [--csv]
"""
import os, sys, collections
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tier_balance as tb

# family -> (intensive axis, unit, higher-is-better)
AXIS = [
    ("engine_rocket",   "ispVac",         "s vac Isp"),
    ("engine_small",    "ispVac",         "s vac Isp (small)"),
    ("engine_electric", "ispVac",         "s vac Isp (EP)"),
    ("rcs",             "ispVac",         "s RCS Isp"),
    ("solar",           "solar_per_kg",   "EC/s per kg"),
    ("battery",         "ec_per_kg",      "EC per kg"),
    ("rtg",             "gen_per_kg",     "EC/s per kg"),
    ("reaction_wheel",  "torque_per_kg",  "kNm per kg"),
    ("radiator",        "rad_per_kg",     "kW per kg"),
    ("antenna",         "antGain",        "dBi"),
    ("crewpod",         "crew",           "seats"),
]


PROP_CLASS = [
    ("kerolox",    ("RP-1+LqdOxygen", "Kerosene+LqdOxygen", "Syntin+LqdOxygen")),
    ("alcolox",    ("Ethanol75+LqdOxygen", "Ethanol90+LqdOxygen", "Ethanol+LqdOxygen")),
    ("hydrolox",   ("LqdHydrogen+LqdOxygen",)),
    ("methalox",   ("LqdMethane+LqdOxygen",)),
    ("hypergolic", ("Aerozine50+NTO", "UDMH+NTO", "MMH+NTO", "UDMH+IRFNA-III", "Aerozine50+MON3",
                    "MMH+MON3", "UDMH+MON3", "Hydrazine+NTO")),
    ("nuclear",    ("LqdHydrogen+EnrichedUranium",)),
]


def prop_class(p):
    for name, pats in PROP_CLASS:
        if p in pats:
            return name
    if "EnrichedUranium" in p:
        return "nuclear"
    if "Xenon" in p or "Argon" in p or "Krypton" in p:
        return "electric"
    if "LqdHydrogen" in p and "LqdOxygen" in p:
        return "hydrolox"
    if "LqdOxygen" in p and ("RP-1" in p or "Kerosene" in p):
        return "kerolox"
    if "NTO" in p or "MON" in p or "IRFNA" in p or "AK20" in p or "AK27" in p:
        return "hypergolic"
    if "HTPB" in p or "PBAN" in p or "APCP" in p or "NGNC" in p:
        return "solid"
    return None


def engine_frontier(nodes, upg_node, part_node, tiers):
    """Best (thrust, Isp) per propellant class reachable BY each tier, driven off CONFIG
    placement -- so engine UPGRADES count, which is how this tree is meant to stretch a family
    across tiers. Uses engine-stats.tsv: its origMass_t/thrust/Isp are the real RO numbers
    (the PART-level mass in the cache is a RealFuels placeholder)."""
    import csv
    rows = []
    with open(os.path.join(tb.MAN, "engine-stats.tsv"), encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="	"):
            cls = prop_class(r["propellants"])
            if not cls:
                continue
            node = upg_node.get("RFUpgrade_" + r["config"])
            if node is None and r["is_base"] == "base":
                node = part_node.get(r["part"])
            tier = nodes[node]["tier"] if node in nodes else None
            if tier is None:
                continue
            try:
                rows.append((cls, tier, float(r["maxThrust_kN"]), float(r["ispVac"]), r["config"]))
            except ValueError:
                continue
    out = {}
    classes = [c for c, _ in PROP_CLASS] + ["solid", "electric"]
    for cls in classes:
        bt = bi = None
        for t in tiers:
            for c, tt, th, isp, cfg in rows:
                if c == cls and tt == t:
                    if bt is None or th > bt:
                        bt = th
                    if bi is None or isp > bi:
                        bi = isp
            out[(cls, t)] = (bt, bi)
    return classes, out


def frontier(rows, tiers):
    """cumulative best value at or below each tier."""
    out = {}
    for fam, ax, _ in AXIS:
        best = None
        for t in tiers:
            for r in rows:
                if r["family"] == fam and r["tier"] == t:
                    v = r["derived"].get(ax)
                    if v and (best is None or v > best):
                        best = v
            out[(fam, ax, t)] = best
    return out


def internal_spread(rows, nodes, thresh=1.5):
    """Within one node, how far apart are members of the same family on the intensive axis."""
    g = collections.defaultdict(list)
    for r in rows:
        if r["tier"] is None or r["node"] == "parking":
            continue
        ax = tb.FAMILY_AXES.get(r["family"], (None, None))[0]
        if not ax:
            continue
        v = r["derived"].get(ax[0])
        if v:
            g[(r["node"], r["family"], ax[0])].append((v, r["name"], r["ctitle"]))
    out = []
    for (node, fam, ax), vals in g.items():
        if len(vals) < 2:
            continue
        vals.sort()
        lo, hi = vals[0], vals[-1]
        if hi[0] >= lo[0] * thresh:
            out.append((hi[0] / lo[0], nodes[node]["tier"], node, fam, ax, len(vals), lo, hi))
    return sorted(out, reverse=True)


def main():
    rows, cache, nodes, part_node, upg_node = tb.build()
    tiers = sorted({r["tier"] for r in rows if r["tier"] is not None})
    fr = frontier(rows, tiers)

    print("=" * 116)
    print("1. CAPABILITY FRONTIER — best value reachable BY that tier ('=' = tier bought nothing in this family)")
    print("=" * 116)
    print(f"  {'family / axis':<30}" + "".join(f"T{t:<7}" for t in tiers))
    for fam, ax, unit in AXIS:
        line = f"  {fam+'/'+ax:<30}"
        prev = None
        for t in tiers:
            v = fr.get((fam, ax, t))
            if v is None:
                cell = "-"
            elif prev is not None and abs(v - prev) < 1e-12:
                cell = "="
            else:
                cell = "%.3g" % v
            prev = v
            line += f"{cell:<8}"
        print(line + f"   [{unit}]")

    classes, ef = engine_frontier(nodes, upg_node, part_node, tiers)
    print("")
    print("=" * 116)
    print("1b. ENGINE FRONTIER by propellant class - best kN / best vac Isp reachable BY that tier")
    print("    (driven off CONFIG placement, so engine upgrades count)")
    print("=" * 116)
    for cls in classes:
        for lab, ix in (("kN ", 0), ("Isp", 1)):
            line = f"  {cls+' '+lab:<20}"
            prev = None
            for t in tiers:
                v = ef.get((cls, t), (None, None))[ix]
                cell = "-" if v is None else ("=" if prev is not None and v == prev else "%.4g" % v)
                prev = v
                line += f"{cell:<8}"
            print(line)

    print("\n" + "=" * 116)
    print("2. INTERNAL SPREAD — one node holding a >=1.5x capability gap inside a single family")
    print("=" * 116)
    for ratio, tier, node, fam, ax, n, lo, hi in internal_spread(rows, nodes):
        print(f"  {ratio:5.1f}x  T{tier:<3} {node:<34} {fam:<15} n={n}  "
              f"worst `{lo[1]}` {lo[0]:.3g} … best `{hi[1]}` {hi[0]:.3g}  [{ax}]")
        print(f"{'':>16}{lo[2][:52]:<54} -> {hi[2][:52]}")

    print("\n" + "=" * 116)
    print("3. MISSION SPINE — mission/charter nodes by tier (what you can fly, when)")
    print("=" * 116)
    miss = [(n["tier"], n["id"], n["title"]) for n in nodes.values()
            if n["id"].split("_")[0] in ("int", "jpl", "okb", "us2")]
    for t, i, ti in sorted(miss):
        print(f"  T{t:<3} {i:<36} {ti}")

    print("\n" + "=" * 116)
    print("4. FIRST ARRIVAL per family (tier at which the family exists at all)")
    print("=" * 116)
    for fam, ax, unit in AXIS:
        ts = [r["tier"] for r in rows if r["family"] == fam and r["tier"] is not None
              and r["derived"].get(ax)]
        if ts:
            print(f"  {fam+'/'+ax:<30} first at T{min(ts)},  best at T{max(ts)},  {len(ts)} parts")


if __name__ == "__main__":
    main()
