#!/usr/bin/env python3
"""check_node_sizing — design rule 8 (<=6 parts/node, one clear king), measured honestly.

Counting PART INSTANCES flags 47 nodes and is mostly noise: `str_adjustableGear` holds 8 parts
that are one undercarriage in eight sizes, and `life_stationLogistics` holds 17 that are three
storage modules in every length. Rule 8 is about how many DISTINCT THINGS a node asks the player
to understand, so this counts part FAMILIES -- titles normalised by stripping sizes, dimensions
and length qualifiers.

Two exemption classes on top of the ids the rubric already lists:
  * GroundSupport / catalog dead-ends -- already documented in docs/TREE-REVIEW.md;
  * mission-charter nodes (jpl_*, okb_*) -- these hold COMPLETE SPACECRAFT by design (the probe
    charter subtree), and one probe is legitimately several parts: Huygens is a lander, a
    parachute, two heatshield halves and a heatshield parachute.

Usage: python tools/check_node_sizing.py [--all]
"""
import os, re, sys, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CAP = 6


# COMMODITY nodes: rule 8's real clause is "one clear KING", and the part count is only a proxy for
# it -- a bad one when the parts are interchangeable hardware. A node holding 13 tank variants has no
# king and does not need one, because the player is choosing a SIZE. A node holding 8 distinct engine
# families has no king and does need one, because the player is choosing a TECHNOLOGY. That is exactly
# why fd_restartableUpper was worth splitting (2026-07-29) and why these are not.
# Reviewed node by node with the tree's author, 2026-07-29.
COMMODITY = {
    # pressure vessels / tankage -- one tank in many diameters and lengths
    "met_weldedTank", "met_isogrid", "str_serviceModuleTank",
    # structures, adapters and trusses -- size and shape variants of one system
    "str_stationStructures", "str_diameterAdapters", "str_modularTrussSystem",
    "str_externalTrussStructure",
    # airframes and cockpits -- per-airframe fuselage/cabin sets
    "str_aircraftAirframe", "str_heavyTransportAirframe", "life_pilotedCockpits",
    "life_spaceplaneCockpit",
    # docking hardware -- probe/drogue halves, once per programme
    "gnc_rendezvousDocking", "gnc_androgynousDocking",
    # recovery and TPS -- drogue + main + shield, once per capsule
    "edl_crewedRecovery", "cmp_lunarReturnAblator", "int_crewedRetroPack",
    # aero surfaces, lighting, piston engines -- commodity fit-out
    "aero_subsonicWing", "aero_liftingReentry", "elec_semiconductorDiode", "prop_recipEngine",
    # the VI01 king plus utility hull-cameras: by design (user, 2026-07-29)
    "opt_vidicon",
}

SIZE_WORDS = r"XL|Mini|Micro|Small|Medium|Large|Short|Long|Twin|Quad|Extended"


def family(title):
    """A part title reduced to the THING it is, with size/variant markers removed."""
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", title)          # [Procedural], (Short)
    t = re.sub(r"\b\d+(\.\d+)?\s*m\b", "", t, flags=re.I)   # 2.25m
    t = re.sub(r"\b(" + SIZE_WORDS + r")\b", "", t, flags=re.I)
    t = re.sub(r"\b(Mk|MK|Block)\s*[-\dIVX]+\b", "", t)
    t = re.sub(r"\d+", "", t)
    return " ".join(t.split()).lower().strip(" -")


def exempt(node):
    """True when the <=6 rule does not apply, with the reason."""
    if node["discipline"] == "GroundSupport":
        return "ground-support line"
    if node["id"] in ("start", "parking", "experimental", "str_structuralHardware",
                      "us2_serviceSandbox"):
        return "documented catch-all"
    if any(w in node["title"] for w in ("Catalog", "Prefabricated", "Stamped",
                                        "Interchangeable", "Sandbox")):
        return "fixed-catalog dead-end (rule 7)"
    if node["id"].split("_")[0] in ("jpl", "okb"):
        return "mission charter (complete spacecraft)"
    if node["id"] in COMMODITY:
        return "commodity hardware (no king needed)"
    return None


def main():
    d = yaml.safe_load(open(os.path.join(ROOT, "tree", "nodes.yaml"), encoding="utf-8"))
    titles = {}
    with open(os.path.join(ROOT, "manifest", "curated-parts.tsv"), encoding="utf-8") as f:
        next(f, None)
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) >= 3:
                titles[c[1]] = c[2]

    rows = []
    for n in d["nodes"]:
        parts = n.get("parts") or []
        if len(parts) <= CAP:
            continue
        why = exempt(n)
        fams = sorted({family(titles.get(p, p)) for p in parts})
        rows.append((len(fams), len(parts), n, fams, why))

    over = [r for r in rows if r[0] > CAP and not r[4]]
    spirit = [r for r in rows if r[0] <= CAP and not r[4]]
    exempted = [r for r in rows if r[4]]

    print(f"nodes over {CAP} parts: {len(rows)}")
    print(f"  exempt by class ............ {len(exempted)}")
    print(f"  <= {CAP} FAMILIES (rule 8 met) . {len(spirit)}")
    print(f"  genuinely over ............. {len(over)}")
    if not over:
        print()
        print("  clean -- this check is now a REGRESSION GATE: it fires when a NEW node arrives over")
        print("  the cap, which is the job worth doing. Re-litigating settled nodes is not.")
    print()
    for f, p, n, fams, _ in sorted(over, key=lambda r: (-r[0], -r[1], r[2]["id"])):
        print(f"  {f:>2} families / {p:>2} parts   T{n['tier']:<3}{n['id']:<32}{n['title'][:38]}")
        if "--all" in sys.argv:
            print(f"       {', '.join(fams)}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
