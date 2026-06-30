#!/usr/bin/env python3
"""Curate the RP-1 PARTUPGRADEs absent under AXE -> a curated keep-list (T3).

Consumes manifest/upgrades-absent.tsv (from tools/upgrade_audit.py, the 626 RP-1-authored
PARTUPGRADEs that are absent under AXE) and refines each into a final disposition:

  A. Engine progression (Tree/TREE-Engines.cfg, 517 RFUpgrade_*): each RFUpgrade_X unlocks
     engine CONFIG X. ORPHAN-FILTER X against the live curated install: parse the cache's
     Module*EngineConfigs CONFIG{name=} -> host PART, cross-ref the 1820 curated parts.
       config on a curated engine        -> KEEP-engine
       config only on an uncurated engine-> EXPERIMENTAL-engine (rides its part to the side-node)
       config absent from the install    -> DROP-orphan (RP-1 authored it for an RO variant we
                                            don't ship; RP-1's own deleteme+UpgradeCleanup.cfg
                                            mechanism drops these at load too)
  B. Engine type-levels (Tree/RFTechLevels.cfg, 15 RFTech-*): RealFuels per-engine-TYPE tech
     levels (Solids/Nuclear/RCS/Cryo...) -> KEEP-engine-typelevel.
  C. Capability (27): cross-ref each upgrade's TARGET part against the curated set ->
       PFTech-Fairing*  -> KEEP-capability  (procedural mass; procedural = AXE workhorse)
       X2CockpitUpgrade -> KEEP-capability  (RO-X1Cockpit curated)
       RP-1-PayloadTech*/RFTech-{Com,Nav}Sat -> KEEP-capability (sat buses curated)
       HDD-Upgrade-*    -> REVIEW-keep-candidate (Kerbalism data-storage subsystem; scope call)
       airlaunchTL*     -> DROP-axed-career (RP-0/KCT airlaunch plugin axed)
  D. Avionics (35, Tree/ProceduralAvionics.cfg)        -> DROP-superseded-avionics (AXE rewrite)
  E. KCT/facility (32, Tree/{KCTUpgrades,TechFacilityUpgrades}.cfg) -> DROP-axed-career

Every KEEP also names the companion patch that must be vendored with the bare PARTUPGRADE
(the @CONFIG techRequired/cost block, the %UPGRADES on the target part, etc.).

Sources : manifest/upgrades-absent.tsv, manifest/curated-parts.tsv, RP-1 source clone,
          live Instance ModuleManager.ConfigCache (must be freshly built).
Output  : manifest/upgrades-curated.tsv (626 rows: name techRequired sourcefile disposition
          companion_patch reason title) — the P2 input for the techRequired -> AXE-node remap.
"""
import os, re, collections

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.normpath(os.path.join(HERE, ".."))
MAN   = os.path.join(ROOT, "manifest")
RP1   = r"C:\git\ksp\RP-1\GameData\RP-1"
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"

# ---------------------------------------------------------------- curated parts
curated = set()
with open(os.path.join(MAN, "curated-parts.tsv"), encoding="utf-8") as f:
    next(f)
    for line in f:
        c = line.rstrip("\n").split("\t")
        if len(c) >= 2: curated.add(c[1])

# ---------------------------------------------------------------- parse cache: engine CONFIG -> host parts
def parse_cache(path):
    config2parts = collections.defaultdict(set)
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    n = len(lines); stack = []
    mec_re = re.compile(r'^Module\w*EngineConfigs$')
    def nearest_part():
        for fr in reversed(stack):
            if fr[0] == "PART" and fr[1]: return fr[1]
        return None
    def any_mec(): return any(fr[2] for fr in stack)
    i = 0
    while i < n:
        s = lines[i].strip()
        if s == "" or s == "{": i += 1; continue
        if s == "}":
            if stack: stack.pop()
            i += 1; continue
        if "=" in s:
            key, _, val = s.partition("=")
            key = key.strip(); val = val.strip()
            if stack:
                top = stack[-1]
                if key == "name":
                    top[1] = val
                    if top[0] == "MODULE" and mec_re.match(val): top[2] = True
                    elif top[0] == "CONFIG" and any_mec():
                        pn = nearest_part()
                        if pn: config2parts[val].add(pn)
            i += 1; continue
        j = i + 1
        while j < n and lines[j].strip() == "": j += 1
        if j < n and lines[j].strip() == "{":
            stack.append([s.split("[")[0].split(":")[0].strip(), None, False])
            i = j + 1; continue
        i += 1
    return config2parts

config2parts = parse_cache(CACHE)

def engine_disposition(config):
    parts = config2parts.get(config)
    if not parts:
        # KEEP, vendored-but-inert: RP-1's deleteme/UpgradeCleanup deletes it at load while its
        # CONFIG is absent, then it lights up automatically if a future mod supplies that engine
        # variant. 50/53 of these reference a node the keeper remap already covers (forward-compatible).
        return "KEEP-engine-dormant", f"config '{config}' absent from current install; inert via deleteme, wakes if a mod adds it"
    cur = parts & curated
    if cur:
        return "KEEP-engine", f"config on curated engine(s): {','.join(sorted(cur)[:3])}"
    return "EXPERIMENTAL-engine", f"config only on uncurated engine(s): {','.join(sorted(parts)[:3])}"

# ---------------------------------------------------------------- per-row disposition
COMPANION = {
    "Tree/TREE-Engines.cfg":      "Tree/TREE-Engines.cfg (whole: defs + @CONFIG techRequired/cost + source PARTs) + Tree/UpgradeCleanup.cfg (deleteme self-filter)",
    "Tree/RFTechLevels.cfg":      "Tree/RFTechLevels.cfg (RFSETTINGS ENGINETYPE TLTECH map + RFTech-* defs)",
    "Tree/PFTechLevels.cfg":      "Tree/PFTechLevels.cfg @PART:AFTER[RealismOverhaul] %UPGRADES (procedural mass)",
    "Tree/CockpitUpgrades.cfg":   "Tree/CockpitUpgrades.cfg @PART[..RO-X1Cockpit..]:FOR[zRP-0] UPGRADES",
    "Tree/PayloadLevels.cfg":     "Tree/PayloadLevels.cfg + Parts/ContractSat/{Communication,Navigation}Sat.cfg UPGRADES",
    "Tree/HardDriveUpgrades.cfg": "Tree/HardDriveUpgrades.cfg + Science/HardDriveConfigs.cfg (Kerbalism KERBALISM_HDD_SIZES subsystem)",
    "Tree/ProceduralAvionics.cfg":"Tree/ProceduralAvionics.cfg AVIONICSCONFIGS (reference data, not vendored as upgrades)",
    "Tree/TechFacilityUpgrades.cfg":"Tree/TechFacilityUpgrades.cfg (DSN tracking-station tech gating; pairs w/ live RealAntennas commsTL*)",
}

def final_disposition(name, srcfile):
    if srcfile == "Tree/TREE-Engines.cfg":
        cfg = name[len("RFUpgrade_"):] if name.startswith("RFUpgrade_") else name
        return engine_disposition(cfg)
    if srcfile == "Tree/RFTechLevels.cfg":
        return "KEEP-engine-typelevel", "RealFuels per-engine-TYPE tech-level (Solids/Nuclear/RCS/Cryo... all present)"
    if srcfile == "Tree/ProceduralAvionics.cfg":
        # AXE's ModuleAxeAvionics TIER ladder already supersedes the NE+SC progression and
        # AxeAvionicsCore.cfg actively deletes these icons. Keep the source AVIONICSCONFIGS as the
        # implementation reference for capabilities AXE hasn't built: per-tier kOS integration
        # (kosDiskSpace/kosECPerInstruction/...) and hasScienceContainer gating. (costFactor and
        # interplanetary/Deep-Space are deliberately dropped per AXE design.)
        return "REFERENCE-avionics", "superseded by AXE TIER ladder; retain AVIONICSCONFIGS as ref for kOS + science-container gating not yet built"
    if srcfile == "Tree/TechFacilityUpgrades.cfg":
        return "REFERENCE-comms-dsn", "DSN tracking-station tech-level gated by comms nodes; ref for AXE comms/ground-station axis (pairs w/ live RealAntennas commsTL1-10)"
    if srcfile == "Tree/KCTUpgrades.cfg":
        return "DROP-axed-career", "KCT engineer/researcher build-&-research-rate efficiency; no AXE KCT (description=unset, no payload)"
    if srcfile == "Tree/AirlaunchTechlevels.cfg":
        return "DROP-axed-career", "RP-0/KCT airlaunch capability ('not a part you can use'); plugin axed (mass/size envelopes = minor ref)"
    if srcfile == "Tree/PFTechLevels.cfg":
        return "KEEP-capability", "procedural fairing/structure mass tech; procedural parts are AXE's workhorse"
    if srcfile == "Tree/CockpitUpgrades.cfg":
        return "KEEP-capability", "raises crewDeathAltitude on RO-X1Cockpit (curated)"
    if srcfile == "Tree/PayloadLevels.cfg":
        return "KEEP-capability", "ComSat/NavSat bus tech; RP-1-CommunicationSat & RP-1-NavigationSat curated"
    if srcfile == "Tree/HardDriveUpgrades.cfg":
        return "KEEP-capability", "Kerbalism data-storage capacity tech (proceduralAvionics/ROT-ProbeCore curated + ModuleScienceContainer/Command); KEEP the data-storage axis"
    return "REVIEW", "uncategorised"

absent = []
with open(os.path.join(MAN, "upgrades-absent.tsv"), encoding="utf-8") as f:
    next(f)
    for line in f:
        c = line.rstrip("\n").split("\t")
        if len(c) < 5: continue
        name, tech, srcfile, _old, title = c[0], c[1], c[2], c[3], c[4]
        disp, reason = final_disposition(name, srcfile)
        absent.append((name, tech, srcfile, disp, COMPANION.get(srcfile, ""), reason, title))

out = os.path.join(MAN, "upgrades-curated.tsv")
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write("name\ttechRequired\tsourcefile\tdisposition\tcompanion_patch\treason\ttitle\n")
    for r in sorted(absent, key=lambda r:(r[3], r[2], r[0])):
        f.write("\t".join(r) + "\n")

# ---------------------------------------------------------------- summary
def bucket(k):
    if k.startswith("KEEP"):      return "KEEP"
    if k.startswith("REFERENCE"): return "REFERENCE"
    if k.startswith("DROP"):      return "DROP"
    return "EXP"
cc = collections.Counter(r[3] for r in absent)
tot = collections.Counter()
print(f"curated parts {len(curated)} | live engine configs {len(config2parts)} | absent upgrades {len(absent)}\n")
for k, v in sorted(cc.items(), key=lambda kv:(-kv[1])):
    print(f"  {v:>4}  {k:<24} [{bucket(k)}]")
    tot[bucket(k)] += v
nodes = len({r[1] for r in absent if r[3].startswith("KEEP") and r[3] != "KEEP-engine-dormant"})
# orphan (dormant) node coverage vs the active-keeper remap
keepnodes = {r[1] for r in absent if r[3].startswith("KEEP") and r[3] != "KEEP-engine-dormant"}
dormant_nodes = {r[1] for r in absent if r[3] == "KEEP-engine-dormant"}
uncovered = dormant_nodes - keepnodes
print(f"  ----")
print(f"  {tot['KEEP']:>4}  KEEP        (vendor; active keepers remap {nodes} distinct RP-1 nodes -> AXE)")
print(f"  {tot['REFERENCE']:>4}  REFERENCE   (retain source as design reference, not vendored as live upgrades)")
print(f"  {tot['DROP']:>4}  DROP")
print(f"  {tot['EXP']:>4}  EXPERIMENTAL")
print(f"\n  dormant-orphan forward-compat: {len(dormant_nodes)-len(uncovered)}/{len(dormant_nodes)} nodes already covered by the keeper remap; uncovered: {sorted(uncovered)}")
print(f"\n-> {out}")
