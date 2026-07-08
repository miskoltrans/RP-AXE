#!/usr/bin/env python3
"""
RP-AXE vs RP-1 avionics — grounded numeric comparison.

RP-AXE's ModuleAxeAvionics now adopts RP-1's Near-Earth procedural-avionics formulas directly, as the sum
of two curves:
  * HARDWARE mass  (t)  = (load^0.46172 + 0.96) * massFactor(tier) / 1000   — RP-1's MASS polynomial, fed the
    per-craft load (≈ whole-vessel mass) and FROZEN at launch. Reproduces RP-1's hardware mass at every size.
  * BATTERY        — the RealFuels EC tank the player sizes; the hardware reserves (mass / avionicsDensity)
    m^3 of the procedural part, the rest is EC.
EC DRAW (W) = (dryMass^0.57853 + 1.035) * powerFactor(tier), evaluated LIVE (steady as fuel burns, steps
down on staging). massFactor/powerFactor per tier come from the TIER nodes in AxeAvionicsCore.cfg (parsed
below, so this script and the game share one source of truth) — 13 tech-gated tiers (postWarAvionics..
modernAvionics) plus an unconditional "start" floor tier below them (matters for Science-Core only; see G).

The guided/unguided toggle is the MODEL selector (VAB-only, frozen at launch): guided = Near-Earth (above),
unguided = Science-Core (RP-1's flat per-tier scMassFactor/scPowerFactor — section G). A flight-only Hibernate
toggle deep-sleeps either model. Range is NOT gated (that's comms). Other differences are all "easier": AXE
keys hardware off the ACTUAL load (RP-1 rates controllableMass >= mass, with margin); AXE's draw is live vs
RP-1's static; guidance is gated at postWarAvionics vs RP-1's start; SAS is a flat level 3.

Sources:
  RP-1 coeffs   : RP-1/GameData/RP-1/Tree/ProceduralAvionics.cfg  (AVIONICSCONFIGS, Near-Earth)
  RP-1 formulas : RP-1/Source/RP0/Avionics/ModuleProceduralAvionics.cs (GetPolynomial / GetAvionicsMass)
  RP-AXE model  : RP-AXE/Source/AXE/Avionics/ModuleAxeAvionics.cs
  RP-AXE ladder : RP-AXE/GameData/RP-AXE/design/Tree/AxeAvionicsCore.cfg  (TIER nodes — parsed here)
  Battery tanks : Instance/GameData/RealismOverhaul/RO_RealFuels.cfg (Battery-I..IV)

Re-run after editing the cfg TIER nodes to refresh docs/AVIONICS_COMPARISON.md.
"""
import math
import os
import re

MASS_EXP, MASS_CONST = 0.46172, 0.96
PWR_EXP,  PWR_CONST  = 0.57853, 1.035
DENSITY = 0.5  # avionicsDensity, t/m^3

def poly(value, exponent, constant, factor):
    return (math.pow(value, exponent) + constant) * factor

def hw_mass_t(M, mf):  return poly(M, MASS_EXP, MASS_CONST, mf) / 1000.0   # tons
def draw_W(M, pf):     return poly(M, PWR_EXP,  PWR_CONST,  pf)            # watts
def hw_vol_L(M, mf):   return (hw_mass_t(M, mf) / DENSITY) * 1000.0        # liters (m^3 * 1000)

# ---- RP-1 Near-Earth ladder: (techLevel, name, era, massFactor, powerFactor) — full 13 tiers ----
NE = [
    (0,  "start/postWar",        "1945-51", 87.99,  56.415),
    (1,  "avionicsPrototypes",   "1952-55", 69.712, 47.851),
    (2,  "earlyAvionics",        "1956-58", 59.13,  40.587),
    (3,  "basicAvionics",        "1959-60", 50.153, 34.426),
    (4,  "interplanetaryProbes", "1961",    42.54,  29.2),
    (5,  "improvedAvionics",     "1962-63", 36.082, 24.767),
    (6,  "matureAvionics",       "1964-66", 30.605, 21.007),
    (7,  "largeScaleAvionics",   "1967-71", 25.959, 17.818),
    (8,  "advancedAvionics",     "1972-80", 22.018, 15.113),
    (9,  "nextGenAvionics",      "1981-87", 18.675, 12.819),
    (10, "longTermAvionics",     "1988-93", 15.84,  10.873),
    (11, "internationalAvionics","1994-99", 13.436,  9.222),
    (12, "modernAvionics",       "2000s",   11.396,  7.822),
]

# ---- RP-AXE ladder: parsed from the cfg TIER nodes (single source of truth) ----
# Each TIER carries factors for BOTH models: Near-Earth (massFactor/powerFactor) + Science-Core
# (scMassFactor/scPowerFactor/scDensity/scAllowAxial). Parse the whole block then pull fields by key, so
# key order / extra keys don't matter.
CFG = os.path.join(os.path.dirname(__file__), "..", "GameData", "RP-AXE", "design", "Tree", "AxeAvionicsCore.cfg")
TIER_RE = re.compile(r"TIER\s*\{([^}]*)\}")

def _field(body, key):
    m = re.search(r"\b" + key + r"\s*=\s*([^\s}]+)", body)
    return m.group(1) if m else None

def load_axe_ladder():
    """(NE list of (name, massFactor, powerFactor), SC dict name -> (scMass kg, scPower W, scDensity, axial),
    COST dict name -> (costFactor, scCostFactor), SCI dict name -> hasScienceContainer,
    KOS dict name -> (diskSpace, costFactor, massFactor, ecPerInstruction))."""
    try:
        with open(CFG, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return [], {}, {}, {}, {}
    ne, sc, cost, sci, kos = [], {}, {}, {}, {}
    for blk in TIER_RE.finditer(text):
        body = blk.group(1)
        tech, mf, pf = _field(body, "tech"), _field(body, "massFactor"), _field(body, "powerFactor")
        if not (tech and mf and pf):
            continue
        ne.append((tech, float(mf), float(pf)))
        scm, scp, scd = _field(body, "scMassFactor"), _field(body, "scPowerFactor"), _field(body, "scDensity")
        if scm and scp and scd:
            sc[tech] = (float(scm), float(scp), float(scd), (_field(body, "scAllowAxial") or "").lower() == "true")
        cf, scc = _field(body, "costFactor"), _field(body, "scCostFactor")
        if cf and scc:
            cost[tech] = (float(cf), float(scc))
        sci[tech] = (_field(body, "hasScienceContainer") or "").lower() == "true"
        kd, kcf, kmf, kec = (_field(body, "kosDiskSpace"), _field(body, "kosSpaceCostFactor"),
                             _field(body, "kosSpaceMassFactor"), _field(body, "kosECPerInstruction"))
        if kd and kcf and kmf and kec:
            kos[tech] = (float(kd), float(kcf), float(kmf), float(kec))
    return ne, sc, cost, sci, kos

AXE, AXE_SC, AXE_COST, AXE_SCI, AXE_KOS = load_axe_ladder()
AXE_BY_NAME = {name: (name, mf, pf) for name, mf, pf in AXE}  # name-anchored, not positional (tier count/order can change)

# ---- RealFuels battery chemistries: name -> (kg/1000EC, funds/1000EC, maxUtil, unlock) ----
BATT = {
    "Battery-I":   (4.5,  12, 0.50, "start"),
    "Battery-II":  (2.89,  8, 0.50, "electronicsHuman ~1961"),
    "Battery-III": (1.8,   5, 0.60, "electronicsAdvCapsules ~1964"),
    "Battery-IV":  (1.44,  4, 0.75, "electronicsLunar ~1967"),
}

def main():
    bar = "=" * 94
    print(bar); print("RP-AXE vs RP-1 avionics — AXE now = RP-1 Near-Earth formulas on the per-craft load"); print(bar)
    if not AXE:
        print("!! could not parse TIER nodes from", CFG); return
    print(f"parsed {len(AXE)} AXE TIER nodes from cfg\n")

    print(bar); print("A) TIER LADDER — AXE tech node -> (massFactor, powerFactor), matched 1:1 to RP-1 Near-Earth"); print(bar)
    print(f"{'AXE tech (TIER node)':22} {'massFactor':>10} {'powerFactor':>12}   RP-1 Near-Earth tier (era)")
    ne_by_pf = {round(t[4], 3): t for t in NE}
    for name, mf, pf in AXE:
        match = ne_by_pf.get(round(pf, 3))
        tag = f"{match[1]} ({match[2]})" if match else "—"
        print(f"{name:22} {mf:10.3f} {pf:12.3f}   {tag}")

    masses = [1, 3, 10, 30, 100, 300, 1000]
    print(); print(bar); print("B) HARDWARE MASS (kg) vs per-craft load — AXE == RP-1 at equal load"); print(bar)
    print(f"{'tier':22} | " + " ".join(f"{m:>7}t" for m in masses))
    for name, mf, pf in [AXE_BY_NAME["gnc_postWarAvionics"], AXE_BY_NAME["gnc_basicAvionics"],
                         AXE_BY_NAME["comp_multiplyRedundantFlightComputer"], AXE_BY_NAME["comp_commercialOffTheShelfAvionics"]]:
        print(f"{name:22} | " + " ".join(f"{hw_mass_t(m, mf)*1000:8.0f}" for m in masses))
    print("  (AXE is fed ACTUAL vessel load and freezes it; RP-1 uses rated controllableMass>=load, with")
    print("   margin, and AXE's load drops as stages separate -> AXE <= RP-1 in play)")

    print(); print(bar); print("C) EC DRAW (W) vs DRY mass — AXE == RP-1 per tier, live (steady on burn, steps on staging)"); print(bar)
    print(f"{'tier':22} | " + " ".join(f"{m:>7}t" for m in masses))
    for name, mf, pf in [AXE_BY_NAME["gnc_postWarAvionics"], AXE_BY_NAME["gnc_basicAvionics"],
                         AXE_BY_NAME["comp_multiplyRedundantFlightComputer"], AXE_BY_NAME["comp_commercialOffTheShelfAvionics"]]:
        print(f"{name:22} | " + " ".join(f"{draw_W(m, pf):8.0f}" for m in masses))

    print(); print(bar); print("D) GROUNDED: V-2 — RP-1 (Near-Earth, controllableMass 15 t) vs AXE (live load ~12.5 t)"); print(bar)
    mf0, pf0 = AXE_BY_NAME["start"][1], AXE_BY_NAME["start"][2]
    print(f"  RP-1 (rated 15 t):  hardware {hw_mass_t(15, mf0)*1000:6.0f} kg | draw {draw_W(15, pf0):6.0f} W | "
          f"footprint {hw_vol_L(15, mf0):5.0f} L")
    print(f"  AXE  (load 12.5 t): hardware {hw_mass_t(12.5, mf0)*1000:6.0f} kg | draw {draw_W(12.5, pf0):6.0f} W | "
          f"footprint {hw_vol_L(12.5, mf0):5.0f} L  (+ the battery you size)")
    ad = draw_W(12.5, pf0)
    for label, secs in [("5 min", 300), ("30 min", 1800), ("3 h", 10800), ("12 h", 43200)]:
        ec = (ad / 1000.0) * secs
        print(f"        + Battery-I for {label:6}: {ec:8.1f} EC -> {ec/1000*4.5:6.2f} kg  "
              f"(hardware alone is {hw_mass_t(12.5, mf0)*1000:.0f} kg)")

    print(); print(bar); print("E) VOLUME — hardware reserves (mass / 0.5) m^3 of the part; the rest is EC battery (L)"); print(bar)
    print(f"{'tier':22} | " + " ".join(f"{m:>7}t" for m in masses))
    for name, mf, pf in [AXE_BY_NAME["gnc_postWarAvionics"], AXE_BY_NAME["gnc_basicAvionics"],
                         AXE_BY_NAME["comp_multiplyRedundantFlightComputer"], AXE_BY_NAME["comp_commercialOffTheShelfAvionics"]]:
        print(f"{name:22} | " + " ".join(f"{hw_vol_L(m, mf):8.0f}" for m in masses))

    print(); print(bar); print("F) BATTERY chemistries (RO electronics line); EC per kg: I 222 II 346 III 556 IV 694"); print(bar)
    for bn, (kg, fn, mu, unl) in BATT.items():
        print(f"   {bn:11}: {1000/kg:6.0f} EC/kg, {kg:4.2f} kg/1000EC, {fn:2} funds/1000EC, maxUtil {mu:.2f}  (unlock: {unl})")

    if AXE_SC:
        print(); print(bar); print("G) SCIENCE-CORE (unguided model) — flat per tier, size-independent (RP-1 Science-Core)"); print(bar)
        print(f"{'AXE tech (TIER node)':22} {'mass(kg)':>9} {'draw(W)':>9} {'density':>9} {'axial':>7}")
        for name, _mf, _pf in AXE:
            if name not in AXE_SC: continue
            scm, scp, scd, sca = AXE_SC[name]
            print(f"{name:22} {scm:9.2f} {scp:9.3f} {scd:9.2f} {('yes' if sca else 'no'):>7}")
        print("  (mass = scMassFactor/1000 t and draw = scPowerFactor/1000 kW are FLAT — no vessel scaling;")
        print("   axial = axial-thrust spin-stabilization allowed from improvedAvionics up. vs Near-Earth at the")
        print("   same node: a fraction of the mass + near-zero power, but no steering.)")

    if AXE_COST:
        def hw_cost(M, cf): return poly(M, MASS_EXP, 3.034, cf)  # same exponent, cost's own constant, no /1000
        print(); print(bar); print("H) HARDWARE COST (funds) — RP-1's hump, not monotonic; peaks matureAvionics"); print(bar)
        print(f"{'AXE tech (TIER node)':22} {'NE @10t':>9} {'NE @100t':>9} {'SC (flat)':>10}")
        for name, _mf, _pf in AXE:
            if name not in AXE_COST: continue
            cf, scc = AXE_COST[name]
            print(f"{name:22} {hw_cost(10, cf):9.0f} {hw_cost(100, cf):9.0f} {scc:10.1f}")
        print("  (Near-Earth cost = (load^0.46172 + 3.034)*costFactor, same load/freeze basis as mass, no /1000;")
        print("   Science-Core cost = scCostFactor flat funds. Distinct from mass/power: this curve is a HUMP —")
        print("   early sophistication costs more, before mass production brings it back down.)")

    if AXE_SCI:
        print(); print(bar); print("I) SCIENCE CONTAINER gating + kOS per-tier scaling (kOS: no-op until installed)"); print(bar)
        print(f"{'AXE tech (TIER node)':22} {'sciContainer':>13} {'kosDiskSpace':>13}")
        for name, _mf, _pf in AXE:
            sci = "yes" if AXE_SCI.get(name) else "no"
            kd = f"{AXE_KOS[name][0]:.0f} B" if name in AXE_KOS else "—"
            print(f"{name:22} {sci:>13} {kd:>13}")
        print("  (sciContainer: ModuleScienceContainer checked off at flight start if the as-built tier lacks it,")
        print("   matching RP-1's own Start()-only gating. kosDiskSpace: reflected onto a kOSProcessor module if")
        print("   present — kOS isn't an AXE dependency today, so this is currently inert.)")

if __name__ == "__main__":
    main()
