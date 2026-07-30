#!/usr/bin/env python3
"""gate_feasibility — cross-gate audit: does every gate the player must pass have the
money/science/hardware to pass it, AT THE MOMENT it binds?

AXE gates progression on eight independent ladders. Each one is individually sane; the
question this tool asks is whether they LINE UP:

  1. tree prereq edges           (build_tree.py already validates: forward-only + reachable)
  2. node science cost           vs the science actually collectable by that era (SCIENCE.md 3b)
  3. R&D scienceCostLimit        funds ladder laid ACROSS the science gate (ECONOMY.md 8)
  4. launchpad craftMassLimit    funds ladder laid across the HARDWARE the tree hands you
  5. launchpad craftSizeLimit    (checked: never binds before mass -- see SIZE_CHECK below)
  6. tracking-station DSN        tech gate + funds, vs how far that era's probes fly
  7. Mission Control limit       funds ladder on simultaneous active contracts
  8. Astronaut Complex           unlockedEVA = 2 -> beyond-Earth EVA

THE ORDERING IS THE POINT. A gate must be bought BEFORE the missions that pay for it can
be flown, so income is counted only from eras STRICTLY BEFORE the milestone. Summing a
whole career's income against a whole career's sinks hides every real block.

Sources, all ground truth rather than assumption:
  tree/nodes.yaml                       tiers, node costs, part placement
  manifest/engine-stats.tsv             thrust / Isp / mass per engine CONFIG
  design/Tree/AxeEngineConfigGates.cfg  CONFIG -> AXE node (the real career gate for a variant)
  design/Settings/AxeFacilities.cfg     pad / MC / R&D ladders   (upgrades[0] is never charged)
  design/Settings/AxeTrackingStation.cfg  DSN ladder
  design/Programs/AxeProgramCompletion.cfg + AxeCapstoneFunds.cfg   Channel 1 payouts
  Instance/GameData/ModuleManager.ConfigCache   reputation per contract (Channel 2)

Run: python tools/gate_feasibility.py
"""
import os, re, csv, math, collections
try:
    import yaml
except ImportError:
    raise SystemExit("needs PyYAML:  pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
GD   = os.path.join(ROOT, "GameData", "RP-AXE", "design")
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"

# ---------------------------------------------------------------- facility ladders
# upgrades[0] is the STARTING level's own cost and is NEVER charged (KSP bills
# upgradeLevels[level+1]); cum(prices, L) therefore sums prices[1:L]. See ECONOMY.md 2.
PAD_MASS = [25, 75, 200, 500, 1200, 3000, 10**9]
PAD_PRICE= [0, 40000, 90000, 400000, 900000, 1800000, 4000000]
RD_CAP   = [82, 265, 404, 600, 865, 1225, 1655, 10**9]
RD_PRICE = [0, 25000, 50000, 100000, 200000, 400000, 700000, 1200000]
TS_PRICE = [0, 50000, 50000, 100000, 175000, 100000, 150000, 1000000, 300000, 300000, 300000]
TS_RANGE = [4.2047e11, 8.4093e11, 1.3329e12, 4.2652e12, 1.3649e13, 4.0946e13,
            1.1465e14, 3.6688e14, 5.1363e14, 8.9885e14, 8.9885e14]
MC_PRICE = [0, 60000, 120000, 200000, 300000]
AC_PRICE = [0, 75000, 282000]          # Astronaut Complex, CustomBarnKit stock
START_FUNDS = 15000                    # Normal preset
FUNDS_MULT  = 1.5                      # prestige (1.25 Significant) x FundsGainMultiplier (1.2)

# Channel 2 yield at Administration L1, in funds per point of incoming reputation.
# CurrencyConverter.OnEffectQuery lerps BOTH terms off the same commitment factor f, so the yield is
# QUADRATIC in f:  Lerp(minShare, maxShare, f) x Lerp(minRate, maxRate, f).
# AXE sets minShare 0.55 (AxeStrategies.cfg) and caps f at 0.5 for Administration L1
# (AxeFacilities.cfg @ADMINISTRATION) -- docs/ECONOMY.md §11.
#   Lerp(0.55, 1, 0.5) x Lerp(125, 157, 0.5) = 0.775 x 141 = 109.3
# It was 0.25 x 133 = 33.2 on CustomBarnKit's default cap with stock's minShare of 0.
CH2_MIN_SHARE, CH2_MAX_SHARE = 0.55, 1.0
CH2_MIN_RATE,  CH2_MAX_RATE  = 125, 157
CH2_COMMIT_L1 = 0.5
def _ch2(f):
    return ((CH2_MIN_SHARE + (CH2_MAX_SHARE - CH2_MIN_SHARE) * f)
            * (CH2_MIN_RATE + (CH2_MAX_RATE - CH2_MIN_RATE) * f))
CH2_YIELD_L1 = _ch2(CH2_COMMIT_L1)
REP_MULT    = 1.2                      # RepGainMultiplier, Normal
AU = 1.496e11

def cum(prices, level):
    """Funds paid to REACH `level` (1-based). prices[0] is the never-charged slot."""
    return sum(prices[1:level])

def pad_level(mass_t):
    for i, cap in enumerate(PAD_MASS):
        if mass_t <= cap:
            return i + 1
    return len(PAD_MASS)

# ---------------------------------------------------------------- tree
def load_tree():
    d = yaml.safe_load(open(os.path.join(ROOT, "tree", "nodes.yaml"), encoding="utf-8"))
    meta = d["meta"]
    tier_cost = {int(k): v for k, v in meta["tier_cost"].items()}
    scalar = meta["scalar"]
    for n in d["nodes"]:
        n["_cost"] = n["cost"] if n.get("cost") is not None else round(tier_cost[n["tier"]] * scalar)
    return d["nodes"], tier_cost, scalar

def rd_level_for_tier(tier_cost, scalar, t):
    c = round(tier_cost[t] * scalar)
    for i, cap in enumerate(RD_CAP):
        if c < cap:
            return i + 1
    return len(RD_CAP)

# ---------------------------------------------------------------- propulsion envelope
def load_engines(nodes):
    """Every RealFuels engine CONFIG, homed on the AXE node that actually unlocks it."""
    p2n = {p: n["id"] for n in nodes for p in (n.get("parts") or [])}
    tier = {n["id"]: n["tier"] for n in nodes}
    cfg2node = {}
    pat = re.compile(r"@PART\[([^\]]+)\].*?@CONFIG\[([^\]]+)\][^{]*,\*\s*\{\s*[@%]techRequired\s*=\s*(\w+)")
    path = os.path.join(GD, "Tree", "AxeEngineConfigGates.cfg")
    for line in open(path, encoding="utf-8", errors="replace"):
        m = pat.search(line)
        if m:
            cfg2node[(m.group(1), m.group(2))] = m.group(3)
    rows = list(csv.DictReader(open(os.path.join(ROOT, "manifest", "engine-stats.tsv"),
                                    encoding="utf-8"), delimiter="\t"))
    out = collections.defaultdict(list)
    for r in rows:
        node = cfg2node.get((r["part"], r["config"])) or p2n.get(r["part"])
        t = tier.get(node)
        if t is None:
            continue
        r["_node"], r["_tier"] = node, t
        out[t].append(r)
    return out

def num(x):
    try:    return float(x)
    except: return None

def propfam(p):
    p = (p or "").lower()
    if "uranium" in p:                                  return "nuclear"
    if "lqdhydrogen" in p:                              return "hydrolox"
    if "xenon" in p or "argon" in p or "krypton" in p:  return "electric"
    if "kerosene" in p or "rp-1" in p or "syntin" in p: return "kerolox"
    if "lqdmethane" in p or "ch4" in p:                 return "methalox"
    if "ethanol" in p or "ethyl" in p:                  return "alcolox"
    if "htp" in p or "peroxide" in p:                   return "htp"
    if any(k in p for k in ("aerozine","udmh","hydrazine","mmh","nto","nitric","ak20","mon","ircfna")):
        return "storable"
    if "hydyne" in p:                                   return "hydyne"
    if "solid" in p or "htpb" in p or "nitrocellulose" in p: return "solid"
    return "other"

# ---------------------------------------------------------------- launcher sizing
DV_LEO = 9400.0     # RSS, Cape, incl. gravity + drag losses
F1, F2 = 0.09, 0.11 # stage dry structure as a fraction of that stage's propellant

def min_glow(isp1, isp2, payload_t, thrust1_kN, eng1_t, eng2_t, twr=1.25):
    """Lightest 2-stage vehicle that reaches LEO, optimising the dV split numerically.

    OPTIMISTIC BY CONSTRUCTION: perfect staging, no fairing/interstage/avionics margin,
    procedural-tank structure fractions. Real first orbital rockets come out 1.5-2.5x
    heavier. Use it as a FLOOR on required pad level, never as a build target.
    """
    best = None
    for i in range(1, 400):
        dv1 = DV_LEO * i / 400.0
        r2 = math.exp((DV_LEO - dv1) / (isp2 * 9.80665))
        den2 = 1 - (r2 - 1) * F2
        if den2 <= 0:
            continue
        prop2 = (r2 - 1) * (payload_t + eng2_t) / den2
        m2 = payload_t + eng2_t + prop2 * (1 + F2)
        r1 = math.exp(dv1 / (isp1 * 9.80665))
        den1 = 1 - (r1 - 1) * F1
        if den1 <= 0:
            continue
        n1, m1 = 1, None
        for _ in range(60):
            prop1 = (r1 - 1) * (m2 + eng1_t * n1) / den1
            m1 = m2 + eng1_t * n1 + prop1 * (1 + F1)
            need = max(1, math.ceil(m1 * twr * 9.80665 / thrust1_kN))
            if need == n1:
                break
            n1 = need
        if m1 and (best is None or m1 < best[0]):
            best = (m1, dv1, n1)
    return best

def best_pair(pool, allow_hydrolox):
    ok = lambda r: propfam(r["propellants"]) not in ("nuclear", "electric", "other") and \
                   (allow_hydrolox or propfam(r["propellants"]) != "hydrolox")
    sl  = [r for r in pool if ok(r) and (num(r["ispSL"])  or 0) > 150 and (num(r["maxThrust_kN"]) or 0) > 100]
    vac = [r for r in pool if ok(r) and (num(r["ispVac"]) or 0) > 150 and (num(r["maxThrust_kN"]) or 0) > 20]
    if not sl or not vac:
        return None
    blend = lambda r: num(r["ispSL"]) + 0.45 * (num(r["ispVac"]) - num(r["ispSL"]))
    e1 = max(sl,  key=lambda r: (round(blend(r)), num(r["maxThrust_kN"])))
    e2 = max(vac, key=lambda r: num(r["ispVac"]))
    return e1, e2, blend(e1), num(e2["ispVac"])

# ---------------------------------------------------------------- Channel 1
PROGRAM_ERA = {
    "A": ["SuborbRocketDev", "SuborbRocketResearch", "EarlyXPlanes"],
    "B": ["EarlySatellites", "EarlySatellites-Heavy", "TargetedSats", "CommNetwork",
          "EarthObservationScience1", "SkoposCommercialApplications0"],
    "C": ["CrewedOrbitEarly", "EarlyLunarProbes", "SkoposCommercialApplications1",
          "EarlyInnerPlanetProbes"],
    "D": ["UncrewedLunarSurface", "CrewedOrbitAdv", "SkoposCommercialApplications2"],
    "E": ["CrewedLunar"],
    "F": ["EarlyEarthSpaceStation", "EarlyLunarHabitation", "SkoposCommercialApplications3",
          "OuterPlanetFlyby"],
    "G": ["MarsSurfaceExp", "VenusSurfaceExp", "MercuryExploration", "SmallBodiesFlyby",
          "JupiterObservation", "AsteroidExploration"],
    "H": ["SaturnObservation", "OuterGasGiantSurvey", "JupiterMoonLandings", "SaturnMoonLandings",
          "UranusMoonLandings", "NeptuneMoonLandings", "PlutoLandings", "CrewedMarsExp"],
}
def program_budgets():
    """raw config funds per programme = completion bonus + capstone."""
    b = collections.Counter()
    txt = open(os.path.join(GD, "Programs", "AxeProgramValue.cfg"), encoding="utf-8",
               errors="replace").read()
    for m in re.finditer(r"^// (\S+) . budget ([\d,]+);", txt, re.M):
        b[m.group(1)] = int(m.group(2).replace(",", ""))
    return b

# ---------------------------------------------------------------- Channel 2
def era_reputation(names):
    """Reputation PAID (config x prestige x RepGainMultiplier) for a set of contract types."""
    if not os.path.exists(CACHE):
        return None
    prestige = {"Trivial": 1.0, "Significant": 1.25, "Exceptional": 1.5}
    rows, cur, depth, prev = {}, None, 0, ""
    for raw in open(CACHE, encoding="utf-8", errors="replace"):
        s = raw.strip()
        if s == "CONTRACT_TYPE":
            prev = s; continue
        if s == "{" and prev == "CONTRACT_TYPE":
            cur, depth, prev = [], 1, ""; continue
        prev = ""
        if cur is None:
            continue
        if s == "{":
            depth += 1
        elif s.startswith("}"):
            depth -= 1
            if depth == 0:
                t = "\n".join(cur)
                nm = re.search(r"^\s*name\s*=\s*(\S+)", t, re.M)
                if nm:
                    r = re.search(r"^\s*rewardReputation\s*=\s*([\d.]+)", t, re.M)
                    p = re.search(r"^\s*prestige\s*=\s*(\w+)", t, re.M)
                    rows[nm.group(1)] = (float(r.group(1)) if r else 0.0,
                                         prestige.get(p.group(1) if p else "Trivial", 1.0))
                cur = None
        else:
            cur.append(s)
    return sum(v * pf * REP_MULT for k, (v, pf) in rows.items() if k in names)

ERA_A_CONTRACTS = set("""KarmanLine SuborbitalReturn DownrangeEarly Downrange SoundingRocketFilm
SoundingRocketBio SoundingRocketAdvancedBio BreakSoundBarrier XPlanesSupersonicMach2
XPlanesStratosphericResearch XPlanesHighAltitude XPlanesHypersonic XPlanesKarman""".split())

# ---------------------------------------------------------------- the milestones
# tier      = the tree tier whose hardware defines the milestone
# vehicle   = the real launcher that era's king nodes model (RSS/RO masses, tonnes)
# floor     = lightest vehicle that can do the job at all (min_glow, optimistic)
# ts/mc/ac  = facility level the milestone needs
MILESTONES = [
  # key label                              tier  vehicle                       glow  floor ts mc ac
  ("A", "sounding rockets / X-planes",        3, "V-2 / Aerobee",                13,   13, 1, 1, 1),
  ("B", "first orbit + early satellites",     4, "R-7 8K71PS",                  270,   41, 1, 2, 1),
  ("C", "appsats, first crew, lunar probes",  7, "Vostok 8K72 / Titan II GLV",  305,   41, 3, 3, 1),
  ("D", "Gemini, uncrewed lunar surface",     8, "Titan II GLV / Atlas-Centaur",154,   60, 4, 3, 1),
  ("E", "crewed lunar landing",               8, "Saturn V",                   2950,  650, 4, 3, 2),
  ("F", "stations, shuttle, Grand Tour",      9, "Shuttle / Proton",           2030,  600, 5, 4, 2),
  ("G", "planetary surfaces",                10, "Titan IIIE / Proton",         640,  300, 6, 4, 2),
  ("H", "outer planets, crewed Mars",        12, "Energia / SLS-class",        2400,  900, 8, 4, 2),
]

# ---------------------------------------------------------------- launch spend
# THE TERM THIS TABLE IGNORED UNTIL 2026-07-30. Every margin above compares banked contract income
# against facility GATES and says nothing about the money spent flying the missions that earn it --
# measured at ~30% of career income in saves/default3, i.e. the single largest recurring expense.
#
# launch_spend(era) = objectives(era) x LAUNCHES_PER_OBJECTIVE x dry_t x FUNDS_PER_TONNE_DRY
#
# ALL FOUR INPUTS ARE SOFT, in increasing order of how much they can move the answer:
#   FUNDS_PER_TONNE_DRY  measured, and the firmest: 112,013 funds over 187.6 t across the 28 real craft
#                        in saves/default3, priced under AxePartFlyCost.cfg. Reproduce with
#                        tools/analyze_craft_costs.py. NB craft-prices massT is DRY (p.mass +
#                        GetModuleMass, no resources), so this must never be applied to a GLOW figure.
#   DRY_FRACTION         dry mass as a share of GLOW. This module's own F1/F2 (0.09/0.11 of propellant)
#                        imply ~0.10, and real vehicles bracket it -- R-7 9.6%, Saturn V 6.1%, but a V-2
#                        is ~32%, so the term UNDER-states the smallest vehicles.
#   LAUNCHES_PER_OBJECTIVE  calibrated from the one real career available: ~62 launches (249,257 of
#                        launch spend at 4,000/craft) against ~16 funded objectives completed. Test
#                        flights, aborts and reputation-only contracts all land in here.
#   objectives(era)      counted from the generated payout configs, so it tracks build_economy.py.
#
# THE WEAKEST ASSUMPTION IS NOT IN THAT LIST: it is that every launch in an era flies that era's
# REFERENCE vehicle. Players fly the smallest thing that will do the job far more often than the
# milestone-defining launcher, which is why the floor table below is the more realistic bracket and the
# reference table is a pessimistic ceiling. Read the pair, never either alone.
FUNDS_PER_TONNE_DRY = 597
DRY_FRACTION = 0.10
LAUNCHES_PER_OBJECTIVE = 4

def era_objectives():
    """era key -> number of funded objectives, parsed from the generated payout configs."""
    n = collections.Counter()
    for fn in (os.path.join(GD, "Programs", "AxeProgramObjectiveFunds.cfg"),
               os.path.join(GD, "Contracts", "AxeCapstoneFunds.cfg")):
        if not os.path.exists(fn):
            continue
        txt = open(fn, encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"(?:objective|capstone) of (\S+)", txt):
            n[m.group(1).rstrip(".,")] += 1
    return {k: sum(n.get(p, 0) for p in v) for k, v in PROGRAM_ERA.items()}

def launch_spend(era_key, glow_t, objectives):
    """Funds spent flying an era's missions, for a fleet of `glow_t` vehicles."""
    return objectives.get(era_key, 0) * LAUNCHES_PER_OBJECTIVE * \
           (glow_t * DRY_FRACTION) * FUNDS_PER_TONNE_DRY

def main():
    nodes, tier_cost, scalar = load_tree()
    bytier = collections.defaultdict(list)
    for n in nodes:
        bytier[n["tier"]].append(n)
    sci_cum, run = {}, 0
    for t in sorted(bytier):
        run += sum(n["_cost"] for n in bytier[t] if n["id"] != "parking")
        sci_cum[t] = run

    budgets = program_budgets()
    era_funds = {k: sum(budgets.get(p, 0) for p in v) * FUNDS_MULT for k, v in PROGRAM_ERA.items()}

    # ---- 1. the headline: cash-flow-ordered gate audit -------------------------------
    print("=" * 122)
    print("GATE FEASIBILITY -- funds banked BEFORE a milestone vs the gates that milestone demands")
    print(f"Normal preset: start {START_FUNDS:,} - Channel 1 x{FUNDS_MULT} - Channel 2 excluded "
          "(measured separately below; pre-orbit reputation is 0.4% of the career's)")
    print("=" * 122)
    hdr = (f"{'milestone':36} {'T':>2} {'treeSci':>8} {'banked':>11} | "
           f"{'reference vehicle':>28} {'t':>5} {'pad':>4} {'padCum':>9} {'RD':>3} {'other':>9} "
           f"{'GATES':>10} {'flown':>11} {'margin':>11}")
    print(hdr); print("-" * len(hdr))
    objectives = era_objectives()
    banked = float(START_FUNDS)
    flown = 0.0            # cumulative launch spend, deducted from `banked` as it accrues
    blocks = []
    for key, label, t, veh, glow, floor, ts, mc, ac in MILESTONES:
        pl  = pad_level(glow); pdc = cum(PAD_PRICE, pl)
        rl  = rd_level_for_tier(tier_cost, scalar, t); rdc = cum(RD_PRICE, rl)
        oth = cum(TS_PRICE, ts) + cum(MC_PRICE, mc) + cum(AC_PRICE, ac) + rdc
        gates = pdc + oth
        margin = banked - flown - gates
        if margin < 0:
            blocks.append((label, veh, glow, pl, gates, banked - flown, margin, floor))
        print(f"{label:36} {t:>2} {sci_cum[t]:>8,} {banked - flown:>11,.0f} | {veh:>28} {glow:>5} "
              f"L{pl:<3} {pdc:>9,} L{rl:<2} {oth-rdc:>9,} {gates:>10,} {flown:>11,.0f} {margin:>11,.0f}"
              f"{'  BLOCKED' if margin < 0 else ''}")
        banked += era_funds.get(key, 0)
        flown += launch_spend(key, glow, objectives)

    print()
    print("Same table, but the player min-maxes: lightest vehicle that can do the job at all")
    banked = float(START_FUNDS)
    flown = 0.0
    for key, label, t, veh, glow, floor, ts, mc, ac in MILESTONES:
        pl  = pad_level(floor)
        rl  = rd_level_for_tier(tier_cost, scalar, t)
        gates = cum(PAD_PRICE, pl) + cum(RD_PRICE, rl) + cum(TS_PRICE, ts) + \
                cum(MC_PRICE, mc) + cum(AC_PRICE, ac)
        m = banked - flown - gates
        print(f"   {label:36} floor {floor:>5} t -> pad L{pl}  gates {gates:>10,}  "
              f"banked {banked - flown:>11,.0f}  flown {flown:>10,.0f}  margin {m:>11,.0f}"
              f"{'  BLOCKED' if m < 0 else ''}")
        banked += era_funds.get(key, 0)
        flown += launch_spend(key, floor, objectives)

    # ---- 2. propulsion envelope: what each tier can actually lift ---------------------
    per_tier = load_engines(nodes)
    print()
    print("=" * 122)
    print("PROPULSION ENVELOPE -- lightest 2-stage LEO launcher for a 300 kg satellite, by tier")
    print("(optimistic floor: perfect staging, no margin. Real early rockets run 1.5-2.5x heavier.)")
    print("=" * 122)
    print(f"{'T':>3} | {'--- without hydrolox ---':^40} | {'--- hydrolox allowed ---':^40} | pad step saved")
    print(f"{'':>3} | {'stage 1':>14} {'stage 2':>14} {'GLOW':>8} | {'stage 1':>14} {'stage 2':>14} {'GLOW':>8} |")
    pool = []
    for t in range(0, 10):
        pool += per_tier.get(t, [])
        res = {}
        for allow in (False, True):
            c = best_pair(pool, allow)
            if not c:
                res[allow] = None; continue
            e1, e2, i1, i2 = c
            b = min_glow(i1, i2, 0.30, num(e1["maxThrust_kN"]),
                         num(e1["origMass_t"]) or 0.5, num(e2["origMass_t"]) or 0.2)
            res[allow] = (e1["config"], e2["config"], b[0] if b else None)
        if not res[True]:
            continue
        a, h = res[False], res[True]
        saved = (pad_level(a[2]) - pad_level(h[2])) if a and a[2] and h[2] else 0
        f = lambda x: f"{x[0][:14]:>14} {x[1][:14]:>14} {x[2]:>8.1f}" if x and x[2] else f"{'(none)':^40}"
        print(f"{t:>3} | {f(a)} | {f(h)} | {saved if saved else '-'}"
              f"{'  <== a whole pad tier' if saved else ''}")

    # ---- 3. DSN: is the tech gate ever behind the mission that needs it? --------------
    print()
    print("=" * 122)
    print("DSN TRACKING STATION -- tech gate tier vs the range that era's probes need")
    print("=" * 122)
    tiers = {n["id"]: n["tier"] for n in nodes}
    gates = {}
    for n in nodes:
        for g in (n.get("grants") or []):
            m = re.match(r"RP0Level(\d+)TrackingStation$", g)
            if m:
                gates[int(m.group(1)) - 1] = n["id"]
    targets = [("Moon", 0.0027), ("Venus", 1.7), ("Mars", 2.7), ("Jupiter", 6.5),
               ("Saturn", 11.0), ("Uranus", 21.0), ("Neptune", 31.0), ("Pluto", 50.0)]
    run = 0
    print(f"{'step':>4} {'gating node':>34} {'T':>3} {'price':>10} {'cumTS':>11} "
          f"{'range (Gm)':>12}  farthest target in range")
    for step in sorted(gates):
        run += TS_PRICE[step]
        rng = TS_RANGE[step]
        reach = [b for b, au in targets if au * AU <= rng]
        print(f"{step:>4} {gates[step]:>34} {tiers[gates[step]]:>3} {TS_PRICE[step]:>10,} "
              f"{run:>11,} {rng/1e9:>12,.0f}  {reach[-1] if reach else '< Moon'}")

    # ---- 4. Channel 2 in the era where it would matter -------------------------------
    rep = era_reputation(ERA_A_CONTRACTS)
    print()
    print("CHANNEL 2 (Administration) at the first-orbit gate:")
    if rep is None:
        print("   ModuleManager.ConfigCache not found -- skipped")
    else:
        print(f"   pre-orbit reputation paid : {rep:>10,.0f}   (vs 146,163 lifetime = "
              f"{rep/146163*100:.1f}% of the career)")
        print(f"   -> convertible funds      : {rep * CH2_YIELD_L1:>10,.0f}   at Administration L1 "
              f"({CH2_YIELD_L1:.1f} funds/rep; was {rep * 0.25 * 133:,.0f} at CustomBarnKit's "
              f"0.25 cap and stock minShare)")
        print(f"   banked at the first-orbit gate, both channels: "
              f"{START_FUNDS + era_funds['A'] + rep * CH2_YIELD_L1:>10,.0f}")

    # ---- 5. every route to first orbit ------------------------------------------------
    have = START_FUNDS + era_funds["A"] + (rep * CH2_YIELD_L1 if rep else 0)
    have_no_aviation = START_FUNDS + (budgets.get("SuborbRocketDev", 0) +
                                      budgets.get("SuborbRocketResearch", 0)) * FUNDS_MULT
    print()
    print("=" * 122)
    print(f"ROUTES TO FIRST ORBIT -- pad cost vs {have:,.0f} banked "
          f"({have_no_aviation:,.0f} if the player skips the aviation lane, which the design allows)")
    print("=" * 122)
    routes = [("R-7 8K71PS",              "fd_orbitalSoviet",      4, 270),
              ("Vostok 8K72",             "fd_orbitalSoviet",      6, 287),
              ("Titan II",                "fd_titanTandem",        5, 154),
              ("Atlas B",                 "fd_largeChamber",       4, 118),
              ("Juno I (solid upper)",    "pc_scoutSolids",        4,  29),
              ("Vanguard",                "fd_singleChamber",      3,  10),
              ("min-max kerolox 2-stage", "fd_singleChamber",      3,  41),
              ("min-max HYDROLOX upper",  "cryo_hydroloxPrototype",2,  17)]
    for name, node, t, mass in routes:
        pl = pad_level(mass); c = cum(PAD_PRICE, pl)
        verdict = "affordable" if c <= have else "OUT OF REACH"
        if c > have_no_aviation and c <= have:
            verdict = "affordable only with the aviation lane flown"
        print(f"   {name:26} {node:24} T{t}  {mass:>5} t -> pad L{pl} "
              f"({PAD_MASS[pl-1] if pl < 7 else 'unlimited'} t)  {c:>9,}  {verdict}")

    # ---- SIZE_CHECK: does craftSizeLimit ever bind before craftMassLimit? -------------
    print()
    print("craftSizeLimit check -- a cylinder filling each pad's box at 0.7 t/m^3 (a fuelled "
          "rocket's mean density):")
    boxes = [(12,24,12), (16,32,16), (20,45,20), (25,60,25), (30,85,30), (40,120,40)]
    for i, (x, h, z) in enumerate(boxes):
        vol = math.pi * (min(x, z) / 2) ** 2 * h
        print(f"   pad L{i+1}: box {x}x{h}x{z} m -> {vol*0.7:>9,.0f} t of rocket fits, "
              f"mass cap is {PAD_MASS[i]:>5} t  -> {'mass binds first' if vol*0.7 > PAD_MASS[i] else 'SIZE BINDS FIRST'}")

    if blocks:
        print()
        print("=" * 122)
        print("BLOCKED GATES")
        print("=" * 122)
        for label, veh, glow, pl, gates, banked, margin, floor in blocks:
            print(f"   {label}")
            print(f"      the tree hands you {veh} ({glow} t) -> pad L{pl}; all gates cost "
                  f"{gates:,}, the player has {banked:,.0f} -> short {-margin:,.0f}")
            print(f"      cheapest way out: build the {floor} t floor vehicle instead "
                  f"(pad L{pad_level(floor)}, {cum(PAD_PRICE, pad_level(floor)):,})")

if __name__ == "__main__":
    main()
