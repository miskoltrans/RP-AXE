#!/usr/bin/env python3
"""place_parts (P2) — first-pass homing of every curated part + KEEP upgrade onto a tree node,
by the SCATTER-BY-DIFFICULTY rubric: a part homes at the discipline of its signature/bottleneck
breakthrough, at the RUNG (tier) matching its RP-1 era. Auto-routes on inventory signals (kind,
propellants, modules, mod) + the RP-1 `techRequired` tier hint; flags judgment calls for review.
Guarantees 0 orphans.

Inputs : manifest/part-capabilities.tsv, manifest/upgrades-curated.tsv, tree/nodes.yaml, RP-1 tree.
Output : manifest/part-placement.tsv (part/node/method/confidence), manifest/upgrade-placement.tsv.
Targets: NODE:<id> pinned by function | SPREAD:<disc> spread across the discipline ladder by tier
         | EXPERIMENTAL (off-tree side-node) | REVIEW (needs a human call).
"""
import os, collections, re
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__)); MAN = os.path.join(ROOT, "..", "manifest")
NODES = os.path.join(ROOT, "..", "tree", "nodes.yaml")
RP1_TREE = r"C:\git\ksp\RP-1\GameData\RP-1\Tree\RP0TechTree.cfg"

def rp1_tiers():
    """RP-1 node id -> our tier (1-10) from RP-1 node cost binned to era bands."""
    txt = open(RP1_TREE, encoding="utf-8", errors="replace").read()
    cost = {}
    for m in re.finditer(r"id\s*=\s*(\w+).*?cost\s*=\s*(\d+)", txt, re.S):
        cost.setdefault(m.group(1), int(m.group(2)))
    BANDS = [(8,1),(20,2),(45,3),(90,4),(150,5),(250,6),(350,7),(500,8),(1000,9)]
    def band(c):
        for hi,t in BANDS:
            if c < hi: return t
        return 10
    return {nid: (1 if nid in ("start","unlockParts") else band(c)) for nid,c in cost.items()}
RP1T = rp1_tiers()

DISC_SPREAD = {"Telecommunications","ElectricalPower","Robotics","CompositeMaterials","Thermodynamics",
               "GuidanceControl","Microelectronics","Computing","OpticsPhotonics"}

def has(s, *subs): return any(x.lower() in (s or "").lower() for x in subs)
def flt(x):
    try: return float(x)
    except: return 0.0

def engine_node(fam, thr, isp):
    """Home an engine on its fuel-family ladder by CAPABILITY (thrust class + vacuum Isp)."""
    if fam == "kerolox":
        if thr < 40:    return "fd_pressureFed"          # verniers / tiny
        if isp >= 345:  return "fd_stagedCombustion"     # genuinely high-perf (most staged kerolox is ox-rich->Metallurgy via override)
        if thr >= 2000: return "fd_combustionStability"  # heavy-lift big-chamber
        return "fd_gasGenerator"                          # workhorse open cycle
    if fam == "hydrolox":
        if isp >= 455:  return "cryo_stagedHydrolox"      # RS-25 class
        if thr < 150:   return "fd_expanderCycle"         # small efficient upper (RL10)
        return "cryo_lh2Insulation"                       # gas-gen workhorse (J-2)
    if fam == "hypergolic":
        return "pc_storableOxidizers" if isp >= 320 else "pc_hypergolicChemistry"
    if fam == "solid":
        return "pc_castableComposite" if thr >= 1000 else "pc_apcpGrain"
    if fam == "nuclear":
        return "nuc_nervaImproved" if isp >= 900 else "nuc_nuclearThermal"
    if fam == "electric":
        return "elec_mpdThrusters" if thr >= 5 else "elec_ionThrusters"
    if fam == "airbreather":                                # jets (no dedicated air-breathing lane; home on aero)
        return "aero_subsonicAirfoils" if thr < 30 else "aero_supersonicInlets"
    return {"methalox": "pc_methalox", "nuclearpulse": "nuc_gasCoreNTR",
            "piston": "aero_subsonicAirfoils"}.get(fam, "pc_hypergolicChemistry")

def route(p):
    """-> (target, method, confidence). target: NODE:<id> | SPREAD:<disc> | EXPERIMENTAL | REVIEW."""
    disc, mods, props, mod, name = p["disc"], p["modules"], p["propellants"], p["mod"], p["name"]
    if disc.startswith("engine:"):                                     # spread each fuel-family across its ladder by capability
        thr, isp = flt(p.get("thrust")), flt(p.get("isp"))
        if isp > 1000:                fam = "airbreather"   # rocket Isp maxes ~470s; thousands = air-breathing jet
        elif has(props, "Uranium"):   fam = "nuclear"
        elif has(props, "IntakeAir"): fam = "airbreather"
        elif disc == "engine:other":                                   # grab-bag: sub-detect by propellant
            fam = ("electric" if has(props, "Xenon", "Argon", "Krypton") else
                   "nuclearpulse" if has(props, "FissionPulse", "FissionPellet") else
                   "solid" if has(props, "PBAN", "PUPE", "PBAA", "CTPB", "HTPB", "NGNC") else
                   "methalox" if has(props, "LqdMethane") else
                   "kerolox" if has(props, "RG-1", "Kerosene", "RP-1") else
                   "piston" if has(props, "AvGas", "Gasoline") else "other")
        else:
            fam = {"cryo": "hydrolox", "hypergolic": "hypergolic", "kerolox": "kerolox", "solid": "solid"}[disc.split(":")[1]]
        return ("NODE:" + engine_node(fam, thr, isp), "engine:" + fam, "med")
    if disc == "tank":
        return ("SPREAD:Cryogenics" if has(props, "LqdHydrogen", "LqdMethane") else "SPREAD:Metallurgy", "tank", "med")
    if disc == "structure":                                            # sub-route by mechanism
        if has(mods, "DockingNode"):                       return ("NODE:str_androgynousDocking", "struct:docking", "med")
        if has(mods, "Decouple", "AnchoredDecoupler"):     return ("NODE:str_stageSeparation", "struct:decoupler", "med")
        if has(mods, "Wheel", "Leg", "Suspension"):        return ("NODE:str_landingLegs", "struct:legs", "med")
        return ("NODE:str_interstageTruss", "struct:adapter", "med")   # adapters / trusses / generic
    if disc == "rcs":        return ("NODE:gnc_reactionControl", "rcs", "low")
    if disc == "probe:integrated":
        if has(name + mods, "RTG", "Radioisotope"):        return ("NODE:int_deepSpaceProbe", "probe:deepspace", "med")
        if has(name, "comsat", "Comsat", "Molniya", "TDRS", "Relay", "Syncom", "Intelsat"):
            return ("NODE:int_comsatBus", "probe:comsat", "med")
        return ("NODE:int_satelliteBus", "probe:satellite", "med")
    if disc == "science:scattered":
        if has(mods, "Imag", "Camera", "Scope", "Optical"):     return ("SPREAD:OpticsPhotonics", "science:optical", "med")
        if has(mods, "Antenna", "Transmitter"):                 return ("SPREAD:Telecommunications", "science:comms", "low")
        if has(mods, "Seismic", "Surface", "GroundExperiment"): return ("SPREAD:Robotics", "science:surface", "low")
        return ("SPREAD:Microelectronics", "science:instrument", "low")
    if disc == "unclassified":
        return ("NODE:experimental", "ground-support", "high") if mod == "ModularLaunchPads" \
               else ("NODE:experimental", "unclassified", "low")
    # ---- CLEAN parts ----
    if disc == "Aerodynamics":
        if has(mods, "Parachute", "RealChute"):  return ("NODE:aero_parachuteRecovery", "clean:chute", "high")
        if has(mods, "Fairing"):                 return ("NODE:aero_proceduralFairings", "clean:fairing", "high")
        return ("SPREAD:Aerodynamics", "clean:aero", "high")
    if disc == "LifeSupport":                                          # split space capsules from aircraft cockpits
        if mod == "ROCapsules" or has(mods, "Ablator", "HeatShield"):
            return ("NODE:int_crewedCapsule", "clean:capsule", "high")
        return ("SPREAD:LifeSupport", "clean:cabin", "med")
    if disc == "ElectricalPower" and has(name + mods, "RTG", "Radioisotope", "SNAP"):
        return ("NODE:nuc_rtg", "clean:rtg-in-elec", "high")           # radioisotope = Nuclear, not Electrical
    if disc == "StructuresMechanisms":
        if has(mods, "DockingNode"):  return ("NODE:str_androgynousDocking", "clean:docking", "high")
        return ("SPREAD:StructuresMechanisms", "clean:struct", "med")
    if disc == "NuclearEngineering":
        return ("NODE:nuc_fissionReactor", "clean:reactor", "high") if has(name+mods, "Reactor") \
               else ("NODE:nuc_rtg", "clean:rtg", "high")
    if disc in DISC_SPREAD:  return ("SPREAD:" + disc, "clean:" + disc, "high")
    return ("REVIEW", "unrouted", "low")

def main():
    ndoc = yaml.safe_load(open(NODES, encoding="utf-8"))["nodes"]
    node_ids = {n["id"] for n in ndoc} | {"EXPERIMENTAL", "REVIEW"}
    disc_nodes = collections.defaultdict(list)                          # discipline -> [(tier, id)]
    for n in ndoc: disc_nodes[n["discipline"]].append((n["tier"], n["id"]))

    def resolve(target, rp1_tier):
        if target.startswith("NODE:"): return target[5:]
        if target.startswith("SPREAD:"):
            cands = disc_nodes.get(target[7:], [])
            return min(cands, key=lambda tn: (abs(tn[0] - rp1_tier), tn[0]))[1] if cands else "REVIEW"
        return target

    parts = []
    with open(os.path.join(MAN, "part-capabilities.tsv"), encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t"); ix = {h: i for i, h in enumerate(hdr)}
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            parts.append({h: (c[ix[h]] if ix[h] < len(c) else "") for h in hdr})

    cap = {}                                                           # per-part thrust/Isp for capability spread
    cp = os.path.join(MAN, "part-capability.tsv")
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            next(f, None)
            for ln in f:
                c = ln.rstrip("\n").split("\t")
                if c and c[0]: cap[c[0]] = (c[1] if len(c) > 1 else "", c[2] if len(c) > 2 else "")
    for p in parts:
        p["thrust"], p["isp"] = cap.get(p["name"], ("", ""))

    overrides = {}                                                      # hand-overrides win over auto-routing
    op = os.path.join(MAN, "part-overrides.tsv")
    if os.path.exists(op):
        with open(op, encoding="utf-8") as f:
            next(f, None)
            for ln in f:
                c = ln.rstrip("\n").split("\t")
                if len(c) >= 2 and c[0] and not c[0].startswith("#"): overrides[c[0]] = c[1]

    rows = []
    for p in parts:
        if p["name"] in overrides:
            node, method, conf = overrides[p["name"]], "override", "high"
        else:
            target, method, conf = route(p)
            node = resolve(target, RP1T.get(p["rp1_tech"], 3))
        if node not in node_ids: node = "REVIEW"
        rows.append((p["name"], node, method, conf))
    print(f"overrides applied: {sum(1 for r in rows if r[3]=='high' and r[2]=='override')}")
    with open(os.path.join(MAN, "part-placement.tsv"), "w", encoding="utf-8") as f:
        f.write("part\tnode\tmethod\tconfidence\n")
        for r in rows: f.write("\t".join(r) + "\n")

    place = {r[0]: r[1] for r in rows}
    def route_upgrade(name):                                            # capability upgrades -> function node
        n = name.lower()
        if any(k in n for k in ("hdd", "data", "tape", "recorder")):  return "comp_dataStorage"
        if "fairing" in n:                                            return "aero_proceduralFairings"
        if "heatshield" in n or n.endswith("hs"):                     return "cmp_ablativeTPS"
        if "cockpit" in n:                                            return "life_pressurizedCabin"
        if "avionic" in n:                                            return "comp_digitalFlightComputer"
        return "experimental"                                         # airlaunch/misc -> off-tree
    up_rows = []
    with open(os.path.join(MAN, "upgrades-curated.tsv"), encoding="utf-8") as f:
        h = f.readline().rstrip("\n").split("\t"); di, ri, ni = h.index("disposition"), h.index("reason"), h.index("name")
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if di >= len(c) or not c[di].startswith("KEEP"): continue
            reason = c[ri] if ri < len(c) else ""
            src = reason.split(":")[-1].strip() if "curated engine" in reason else ""
            node = place.get(src, "experimental") if src else route_upgrade(c[ni])
            up_rows.append((c[ni], node, ("engine-config:" + src) if src else "capability"))
    with open(os.path.join(MAN, "upgrade-placement.tsv"), "w", encoding="utf-8") as f:
        f.write("upgrade\tnode\tmethod\n")
        for r in up_rows: f.write("\t".join(r) + "\n")

    # ---- report ----
    tn = collections.Counter(r[1] for r in rows)
    real = {k: v for k, v in tn.items() if k not in ("EXPERIMENTAL", "REVIEW")}
    print(f"parts placed: {len(rows)}  |  confidence: {dict(collections.Counter(r[3] for r in rows))}")
    print(f"onto {len(real)} real nodes ({sum(real.values())} parts) | EXPERIMENTAL {tn['EXPERIMENTAL']} | REVIEW {tn['REVIEW']}")
    empty = [n['id'] for n in ndoc if n['id'] not in real and n['discipline'] != 'SystemsIntegration']
    print(f"nodes with parts: {len(real)}/{len(ndoc)}  (empty non-integration nodes: {len(empty)})")
    print("busiest 12 nodes:", ", ".join(f"{k}={v}" for k, v in tn.most_common(14) if k not in ("EXPERIMENTAL","REVIEW"))[:400])
    print(f"upgrades placed: {len(up_rows)} (REVIEW: {sum(1 for r in up_rows if r[1]=='REVIEW')})")
    print("-> manifest/part-placement.tsv , manifest/upgrade-placement.tsv")

if __name__ == "__main__": main()
