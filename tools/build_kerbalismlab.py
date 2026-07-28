#!/usr/bin/env python3
"""Vendor KerbalismLab (the fork) into RP-AXE, remapping every tech reference to AXE nodes.

Path A (docs/KERBALISMLAB.md): keep the mod as its creator authored it (values / situations /
bodies / crew / slots), change only what AXE's from-scratch tree forces:
  * UnlockTech / UpgradeTech / ReconfigureTech  -> AXE nodes   (the §4 remap table below)
  * a handful of marquee experiments             -> their thematic Mir/Kvant module (T11)

Sources (siblings, read-only):
  fork      = KerbalismLabExperimentsExpandedContinued/GameData/.../*.cfg   (65 experiments)
  framework = KerbalismScienceOnly/.../ScienceRework/{Tweakables/StockGroups-Lab, Groups/LabExperiments}.cfg
Output: GameData/RP-AXE/design/Science/KerbalismLab/{Framework-2-LabGroup, Framework-3-LabProcessing, Experiments/*}.cfg

The scaffold (Framework-1), Configure host (Framework-4), InstrumentTagging and _README are hand-authored
(they need judgement) and are NOT touched by this script. Re-run any time: it only rewrites generated files.
"""
import os, re, sys

G = r"C:\git\ksp"
FORK = os.path.join(G, "KerbalismLabExperimentsExpandedContinued", "GameData", "KerbalismLabExperimentsExpandedContinued")
FW   = os.path.join(G, "KerbalismScienceOnly", "GameData", "KerbalismScienceOnly", "System", "ScienceRework")
OUT  = os.path.join(G, "RP-AXE", "GameData", "RP-AXE", "design", "Science", "KerbalismLab")

# ---- §4 remap: stock/CTT tech -> AXE node (era-stepped on the Life-Support / station ladder) ----
REMAP = {
    "highAltitudeFlight":     "life_highAltCompartment",     # T3  (BIRDIE flying lab)
    "engineering101":         "life_openLoopECLSS",          # T5
    "survivability":          "life_openLoopECLSS",          # T5
    "basicScience":           "life_pressurisedCabin",       # T5
    "electrics":              "life_pressurisedCabin",       # T5
    "generalConstruction":    "life_crewedExperimentBay",    # T7
    "spaceExploration":       "life_crewedExperimentBay",    # T7
    "scienceTech":            "life_crewedExperimentBay",    # T7
    "electronics":            "life_crewedExperimentBay",    # T7
    "unmannedTech":           "life_crewedExperimentBay",    # T7
    "fieldScience":           "life_stationHabitation",      # T8
    "precisionEngineering":   "life_stationHabitation",      # T8
    "aerodynamicSystems":     "life_stationHabitation",      # T8
    "advExploration":         "life_convertedStageStation",  # T9
    "advScienceTech":         "life_convertedStageStation",  # T9  (also the +1-slot upgrade tech)
    "advConstruction":        "life_habitatModuleCatalog",   # T9
    "experimentalElectrics":  "life_habitatModuleCatalog",   # T9
    "miniaturization":        "life_mirCore",                # T10
    "advUnmanned":            "life_mirCore",                # T10
    "heavyLanding":           "life_isru",                   # T10 (TRAPPED ground base)
    "specializedScienceTech": "life_largeObservationDome",   # T11
    "hydroponics":            "life_bioregenerativeECLSS",   # T11 (greenhouse)
    "experimentalScience":    "life_largeStationModule",     # T11
    "longTermScienceTech":    "life_largeScaleHabitat",      # T12
}

# ---- Kvant/Mir marquee overrides: experiment (fork filename stem) -> thematic module node (T11) ----
MARQUEE = {
    # Kvant-1 Astrophysics Module
    "HaloSat": "int_kvant1Module", "NICER": "int_kvant1Module", "CALET": "int_kvant1Module",
    "ASTERIA": "int_kvant1Module", "AMS-02": "int_kvant1Module",  # space telescope / particle astrophysics
    # Kristall Materials-Processing Module
    "SODI-Colloid": "int_kristallModule", "Platan": "int_kristallModule", "TPSMMO": "int_kristallModule",
    # Priroda Earth-Observation Module
    "ECOSTRESS": "int_prirodaModule", "GEDI": "int_prirodaModule", "BeaverCube": "int_prirodaModule",
    # Kvant-2 EVA & Biology Module
    "Tanpopo": "int_kvant2Module",
}

# ---- near-Earth floor: single-body-locked experiments x10 (docs/KERBALISMLAB.md "Balance pass") ----
# An experiment gated to ONE body earns no body multiplier, ever. The rest of the catalogue does:
# AXE's body table runs from Earth x1 up to Pluto x30, and biome-scattered situations multiply again
# by a biome sum of up to 20. The creator priced this mod on stock Kerbin scales, where home orbit IS
# the game; under RSS home orbit is the starting line, so every home-locked experiment is structurally
# underpriced by about an order of magnitude relative to everything beside it.
#
# Scaling exactly those experiments restores parity without touching the deep-space tail -- they run
# at one body, so nothing else in the budget moves. A LEO station program goes from ~4.0k to ~28k
# against a ~300k tree; grand theoretical max moves only +1.7% (tools/lab_budget.py).
#
# Uniform x10 on purpose: it preserves the creator's RELATIVE pricing (the marquee astrophysics
# payloads are already priced 25-50x the Earth-observation cubesats precisely because they are
# single-subject) and changes only the global scale that RSS broke. Path A stays intact in spirit --
# no situations, bodies, crew, durations, slots or data sizes are re-authored, only this one scalar.
SINGLE_BODY_GATES = {"HomeBody", "Oceanic", "Suns"}   # Oceanic == Earth, Suns == the Sun
HOME_LOCKED_SCALE = 10

# design/Science/EarthScienceRemoval.cfg takes Earth's sub-40km science out of the economy on purpose
# (landed/splashed 0.00001, flyingLow 0.001) so you cannot grind the home planet. An Earth-locked
# experiment that ONLY runs in one of those situations is therefore worth ~0 no matter what we price
# it at -- scaling it would be a false signal in the config, so it is skipped and reported instead.
EARTH_ZEROED_SITUATIONS = {"srflanded", "srfsplashed", "flyinglow"}

def scale_home_locked(text, stem):
    """x10 the group `value` of an experiment whose BodyAllowed pins it to a single body.
    Returns (text, 'scaled' | 'dead' | None)."""
    mk = re.search(r'KERBALISM_EXPERIMENT', text)
    if not mk:
        return text, None
    seg = text[mk.end():mk.end() + 400]
    mba = re.search(r'(?m)^\s*BodyAllowed\s*=\s*(\S+)', seg)
    if not mba or mba.group(1) not in SINGLE_BODY_GATES:
        return text, None
    if re.search(r'(?m)^\s*BodyNotAllowed\s*=', seg):        # a second gate means it is not a clean lock
        return text, None
    sits = [s.split("@")[0].lower() for s in re.findall(r'(?m)^\s*Situation\s*=\s*(\S+)', seg)]
    if mba.group(1) in ("HomeBody", "Oceanic") and sits and all(s in EARTH_ZEROED_SITUATIONS for s in sits):
        return text, "dead"
    n = [0]
    def bump(m):
        n[0] += 1
        return f"{m.group(1)}{float(m.group(2)) * HOME_LOCKED_SCALE:g}"
    text = re.sub(r'(?m)^(\s*value\s*=\s*)([0-9.]+)', bump, text, count=1)
    return text, ("scaled" if n[0] else None)

TECH_FIELD = re.compile(r'(\b(?:UnlockTech|UpgradeTech|ReconfigureTech)\s*=\s*)([A-Za-z0-9_]+)')

# Source-mod bug: a few fork EXPERIMENT_DEFINITIONs set baseValue/scienceCap to the experiment NAME
# instead of a number (e.g. ALSEP-2.cfg: `baseValue = ALSEP-2`). Harmless in the fork's own framework,
# but AXE's GlobalExperimentPatches.cfg does `@dataScale /= #$baseValue$` at :FIRST (before the fork
# overrides baseValue) -> "1 / ALSEP-2" math error -> blocks the whole ConfigCache from being written.
# Sanitize the top-def value to the fork's standard 180 (a generous scienceCap; real baseValue is set
# later at :FOR[zzzKerbalismDefault]). Only touches bare `baseValue =`/`scienceCap =`, not `@`-patch lines.
BAD_BASEVALUE = re.compile(r'(?m)^(\s*(?:baseValue|scienceCap)\s*=\s*)([A-Za-z][\w-]*)\s*$')

def remap_text(text, marquee_node=None):
    unknown = set()
    def sub(m):
        field, tok = m.group(1), m.group(2)
        if field.strip().startswith("UnlockTech") and marquee_node:
            return f"{field}{marquee_node}"
        if tok in REMAP:
            return f"{field}{REMAP[tok]}"
        unknown.add(tok)
        return m.group(0)
    return TECH_FIELD.sub(sub, text), unknown

def main():
    os.makedirs(os.path.join(OUT, "Experiments"), exist_ok=True)
    allunknown, nmarquee = set(), 0

    # 1) framework lab group (remap its 8 techs)
    src = open(os.path.join(FW, "Tweakables", "StockGroups-Lab.cfg"), encoding="utf-8").read()
    out, unk = remap_text(src); allunknown |= unk
    header = "// GENERATED by tools/build_kerbalismlab.py from KerbalismScienceOnly StockGroups-Lab.cfg\n// techs remapped to AXE nodes (see _README.md). Do not hand-edit.\n"
    open(os.path.join(OUT, "Framework-2-LabGroup.cfg"), "w", encoding="utf-8").write(header + out)

    # 2) framework lab processing (verbatim — all techs come from the group above)
    proc = open(os.path.join(FW, "Groups", "LabExperiments.cfg"), encoding="utf-8").read()
    open(os.path.join(OUT, "Framework-3-LabProcessing.cfg"), "w", encoding="utf-8").write(
        "// VENDORED verbatim from KerbalismScienceOnly Groups/LabExperiments.cfg (reads techs from Framework-2).\n" + proc)

    # 2b) the 6 base lab experiments' EXPERIMENT_DEFINITIONs.
    # Framework-2 carries their group entry and Framework-3 wires them into every lab's Configure menu,
    # but their definitions live in ScienceDefs-Kerbalism.cfg — a file AXE does not vendor wholesale
    # (it also defines the Crew/Orbital/Unmanned groups, the conflicting alt-science system). Without
    # these 6 defs the SETUPs are dead menu entries pointing at experiments that do not exist.
    # Vendored verbatim; their scienceCap is re-equalised to baseValue by Framework-6.
    defs = open(os.path.join(FW, "ScienceDefs-Kerbalism.cfg"), encoding="utf-8").read()
    want = ("kerbalism_CHILLED", "kerbalism_RELAX", "kerbalism_JAMMED",
            "kerbalism_TRAPPED", "kerbalism_SALINE", "kerbalism_BIRDIE")
    blocks, found = [], []
    for m in re.finditer(r'(?m)^EXPERIMENT_DEFINITION[^\n]*\n', defs):
        i = defs.index("{", m.end() - 1)
        d, j = 0, i
        while j < len(defs):
            if defs[j] == "{": d += 1
            elif defs[j] == "}":
                d -= 1
                if d == 0: break
            j += 1
        body = defs[m.start():j + 1]
        mid = re.search(r'(?m)^\s*id\s*=\s*(\S+)', body)
        if mid and mid.group(1) in want:
            blocks.append(body); found.append(mid.group(1))
    missing = [w for w in want if w not in found]
    if missing:
        print("!! base experiment definitions not found upstream:", missing); sys.exit(2)
    open(os.path.join(OUT, "Framework-5-BaseExperimentDefs.cfg"), "w", encoding="utf-8").write(
        "// GENERATED by tools/build_kerbalismlab.py — the 6 base lab EXPERIMENT_DEFINITIONs, vendored\n"
        "// verbatim from KerbalismScienceOnly ScienceRework/ScienceDefs-Kerbalism.cfg. Do not hand-edit.\n"
        "// Framework-2 sets their balance (group `value`); Framework-6 makes that value the payout.\n"
        "// Only these 6 are taken: the rest of that file is the Crew/Orbital/Unmanned alt-science system.\n\n"
        + "\n".join(blocks) + "\n")
    print(f"base experiment definitions vendored: {len(blocks)}")

    # 3) the 65 fork experiments (remap UnlockTech; marquee override where applicable)
    n = 0; nsan = 0; nscaled = 0; scaled_names = []; dead_names = []
    for fn in sorted(os.listdir(FORK)):
        if not fn.endswith(".cfg") or fn == "InstrumentTagging.cfg":
            continue
        stem = fn[:-4]
        text = open(os.path.join(FORK, fn), encoding="utf-8").read()
        text, nfix = BAD_BASEVALUE.subn(r'\g<1>180', text)   # fix source-mod non-numeric baseValue/scienceCap
        nsan += nfix
        text, how = scale_home_locked(text, stem)
        if how == "scaled": nscaled += 1; scaled_names.append(stem)
        elif how == "dead": dead_names.append(stem)
        mn = MARQUEE.get(stem)
        out, unk = remap_text(text, marquee_node=mn)
        allunknown |= unk
        if mn: nmarquee += 1
        open(os.path.join(OUT, "Experiments", fn), "w", encoding="utf-8").write(out)
        n += 1

    print(f"experiments vendored: {n}  (marquee Mir/Kvant gates: {nmarquee}, baseValue/scienceCap fixes: {nsan})")
    print(f"single-body-locked value x{HOME_LOCKED_SCALE}: {nscaled} -> {chr(44).join(sorted(scaled_names))}")
    if dead_names: print(f"Earth-locked but zeroed by EarthScienceRemoval (left alone, dead content): {chr(44).join(sorted(dead_names))}")
    if allunknown:
        print("!! UNMAPPED tech tokens (add to REMAP):", sorted(allunknown)); sys.exit(2)
    print("all tech references mapped OK ->", OUT)

if __name__ == "__main__":
    main()
