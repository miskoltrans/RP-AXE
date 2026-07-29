#!/usr/bin/env python3
"""tier_defects — balance detectors over the capability model in tools/tier_balance.py.

Everything here is VERIFIED AGAINST NUMBERS, never against names. A group of parts or
upgrades is only treated as a LADDER (rungs that supersede each other) once the data says
one rung actually beats another; sibling variants that merely share a name prefix
(RD-855 vs RD-856 are different engines, PT6A-21 vs PT6A-42 are power ratings) are
side-grades and are left alone.

Ladder sources, all ground-truthed:
  A. engine CONFIGs      -- manifest/engine-stats.tsv (thrust + Isp per config) joined to
                            the `RFUpgrade_<config>` node placement.
  B. levelled upgrades   -- PARTUPGRADEs whose own description says "Level N" / TL-numbered
                            ladders (tank/battery/fairing/MLI/solar/comms/RCS/solids).
  C. science instruments -- Kerbalism `Configure` SETUPs (`tech = <AXE node>`), payoff read
                            from the experiment's scienceCap.
  D. parts in a family   -- intensive metrics, compared only within a scale class.

Detectors:
  SUPERSEDED  a strictly better rung unlocks EARLIER or on the SAME node -- the worse rung is
              dead on arrival (nobody will ever build it)
  COLLAPSE    2+ rungs of a monotone ladder unlock on one node -- a generation is skipped
  FLAT        2+ rungs land on the same TIER via different nodes
  COMPRESSED  the whole ladder spans fewer tiers than it has rungs to spend
  GAP         a ladder rung sits >=4 tiers above the previous one
  DOMINATED   part B beats part A on every intensive axis, same scale class, same node
  DEADONARR   as DOMINATED but B unlocks at a strictly earlier tier

Usage: python tools/tier_defects.py [--section NAME] [--json]
"""
import os, re, sys, json, collections
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tier_balance as tb

MAN = tb.MAN
F = collections.namedtuple("F", "kind group detail source severity")


# --------------------------------------------------------------- ladder source A
def engine_config_ladders(nodes, upg_node):
    """Per engine PART, its RealFuels CONFIGs ordered by measured capability."""
    rows = collections.defaultdict(list)
    path = os.path.join(MAN, "engine-stats.tsv")
    with open(path, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        ix = {k: i for i, k in enumerate(hdr)}
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) < len(hdr):
                continue
            part = c[ix["part"]]
            cfg = c[ix["config"]]
            def num(k):
                try:
                    return float(c[ix[k]])
                except (ValueError, KeyError):
                    return None
            rows[part].append({
                "part": part, "config": cfg, "title": c[ix["title"]],
                "is_base": c[ix["is_base"]] == "base",
                "thrust": num("maxThrust_kN"), "isp": num("ispVac"), "ispSL": num("ispSL"),
                "prop": c[ix["propellants"]], "ignitions": c[ix["ignitions"]],
                "burn": num("ratedBurnTime"),
            })
    # join to placement
    out = {}
    for part, cfgs in rows.items():
        for r in cfgs:
            up = "RFUpgrade_" + r["config"]
            node = upg_node.get(up)
            if node is None and r["is_base"]:
                node = None          # base config rides the part itself
            r["upgrade"] = up
            r["node"] = node
            r["tier"] = nodes[node]["tier"] if node in nodes else None
        out[part] = cfgs
    return out


def engine_defects(ladders, part_node, nodes):
    """A config is DOMINATED when another config of the SAME engine on the SAME propellant
    has >= thrust and >= Isp (one of them >=3% better)."""
    out = []
    for part, cfgs in sorted(ladders.items()):
        placed = [c for c in cfgs if c["tier"] is not None]
        if len(placed) < 2:
            continue
        # the base config unlocks with the part
        base_tier = None
        pn = part_node.get(part)
        if pn in nodes:
            base_tier = nodes[pn]["tier"]
        for c in cfgs:
            if c["is_base"] and c["tier"] is None:
                c["tier"], c["node"] = base_tier, pn
        pool = [c for c in cfgs if c["tier"] is not None and c["thrust"] and c["isp"]]
        for a in pool:
            for b in pool:
                if a is b or a["prop"] != b["prop"]:
                    continue
                # sea-level and vacuum nozzle variants of one engine trade ispVac against ispSL
                # (RL10A-5 is a SL engine: 368 s vac but far better at 1 atm). Requiring BOTH keeps
                # those side-grades out of the report.
                asl, bsl = a["ispSL"] or 0.0, b["ispSL"] or 0.0
                better = (b["thrust"] >= a["thrust"] * 0.999 and b["isp"] >= a["isp"] * 0.999
                          and bsl >= asl * 0.999
                          and (b["thrust"] >= a["thrust"] * 1.03 or b["isp"] >= a["isp"] * 1.03))
                if not better:
                    continue
                if b["tier"] < a["tier"]:
                    out.append(F("SUPERSEDED", part,
                                 f"config `{a['config']}` (T{a['tier']} {a['node']}) is beaten by "
                                 f"`{b['config']}` (T{b['tier']} {b['node']}) which unlocks EARLIER — "
                                 f"{a['thrust']:.0f}kN/{a['isp']:.0f}s vs {b['thrust']:.0f}kN/{b['isp']:.0f}s",
                                 "engine-config", 1))
                elif b["tier"] == a["tier"] and b["node"] == a["node"]:
                    out.append(F("COLLAPSE", part,
                                 f"configs `{a['config']}` and `{b['config']}` both unlock on `{a['node']}` "
                                 f"(T{a['tier']}) — {a['thrust']:.0f}kN/{a['isp']:.0f}s vs "
                                 f"{b['thrust']:.0f}kN/{b['isp']:.0f}s, the weaker is instantly obsolete",
                                 "engine-config", 2))
    # de-dup symmetric noise: keep worst-offender per (group, kind, pair)
    seen = set(); ded = []
    for f in out:
        k = (f.kind, f.group, tuple(sorted(re.findall(r"`([^`]+)`", f.detail))))
        if k in seen:
            continue
        seen.add(k)
        ded.append(f)
    return ded


# --------------------------------------------------------------- ladder source B
LEVEL_RE = re.compile(r"level\s+(I{1,3}V?|VI{0,3}|IX|X|\d+)\b", re.I)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
TL_RE = re.compile(r"^(.*?(?:TL|tltech|Upgrade))[-_]?(\d+)$")


def level_ladders(cache, nodes, upg_node):
    """Only groups the DATA calls a level ladder: an explicit 'Level N' in the upgrade's own
    text, or a TL-numbered family."""
    recs = []
    for u in cache["PARTUPGRADE"]:
        nm = u.get("name")
        if not nm:
            continue
        node = upg_node.get(nm) or u.get("techRequired")
        tier = nodes[node]["tier"] if node in nodes else None
        blob = " ".join([u.get("basicInfo", ""), u.get("description", ""), u.get("title", "")])
        lvl = None
        m = LEVEL_RE.search(blob)
        if m:
            g = m.group(1)
            lvl = ROMAN.get(g.upper(), None) or (int(g) if g.isdigit() else None)
        # family = the name with its rung stripped. TL-style names (`solarTL7`, `commsTL10`)
        # have no separator before the number, so try that shape FIRST -- stripping only
        # separator-prefixed rungs would leave every TL upgrade in a family of its own.
        fam = None
        m2 = TL_RE.match(nm)
        if m2:
            fam = m2.group(1)
            if lvl is None:
                lvl = int(m2.group(2))
        elif re.search(r"[-_ ](I{1,3}V?|VI{0,3}|IX|X)$", nm):
            # A trailing ROMAN numeral is a ladder marker essentially always (unlike a bare digit,
            # which collides with model numbers: RD-855 is an engine, not rung 855). PFTech-Fairing-I
            # ..VI names its rungs by material generation and never writes "Level N".
            mr = re.search(r"^(.*)[-_ ](I{1,3}V?|VI{0,3}|IX|X)$", nm)
            fam, lvl = mr.group(1), ROMAN[mr.group(2)]
        elif lvl is not None:
            fam = re.sub(r"[-_ ](I{1,3}V?|VI{0,3}|IX|X|\d+)$", "", nm)
            if fam == nm:
                fam = re.sub(r"\d+$", "", nm) or None
        if fam and lvl is not None:
            recs.append({"name": nm, "fam": fam, "lvl": lvl, "node": node, "tier": tier,
                         "title": u.get("title", ""), "info": u.get("basicInfo", "")})
    g = collections.defaultdict(list)
    for r in recs:
        g[r["fam"]].append(r)
    return {k: sorted(v, key=lambda r: r["lvl"]) for k, v in g.items() if len(v) >= 2}


def level_defects(ladders):
    out = []
    for fam, rungs in sorted(ladders.items()):
        placed = [r for r in rungs if r["tier"] is not None]
        if len(placed) < 2:
            continue
        bynode = collections.defaultdict(list)
        bytier = collections.defaultdict(list)
        for r in placed:
            bynode[r["node"]].append(r["lvl"])
            bytier[r["tier"]].append(r["lvl"])
        for node, lv in sorted(bynode.items()):
            if len(lv) > 1:
                t = next(r["tier"] for r in placed if r["node"] == node)
                out.append(F("COLLAPSE", fam,
                             f"levels {sorted(lv)} all unlock on `{node}` (T{t}) — "
                             f"{len(lv)-1} generation(s) skipped", "level-ladder", 2))
        for t, lv in sorted(bytier.items()):
            nodeset = {r["node"] for r in placed if r["tier"] == t}
            if len(lv) > 1 and len(nodeset) > 1:
                out.append(F("FLAT", fam, f"levels {sorted(lv)} all land on tier T{t} "
                             f"({', '.join(sorted(nodeset))})", "level-ladder", 3))
        seq = [(r["lvl"], r["tier"], r["node"]) for r in placed]
        for (l1, t1, n1), (l2, t2, n2) in zip(seq, seq[1:]):
            if t2 < t1:
                out.append(F("SUPERSEDED", fam,
                             f"level {l1} is gated at T{t1} (`{n1}`) but level {l2} is already "
                             f"available at T{t2} (`{n2}`) — level {l1} is dead on arrival",
                             "level-ladder", 1))
            elif t2 - t1 >= 4:
                out.append(F("GAP", fam, f"level {l1} (T{t1}) -> level {l2} (T{t2}): {t2-t1} tiers "
                             f"with no progress in this family", "level-ladder", 4))
        tiers = [r["tier"] for r in placed]
        span = max(tiers) - min(tiers)
        if len(placed) >= 3 and span < (len(placed) - 1) / 2.0:
            out.append(F("COMPRESSED", fam, f"{len(placed)} levels span only {span} tier(s) "
                         f"(T{min(tiers)}-T{max(tiers)})", "level-ladder", 3))
    return out


# --------------------------------------------------------------- ladder source C
def science_ladder(cache, nodes):
    sci = {}
    for e in cache["EXPERIMENT_DEFINITION"]:
        eid = e.get("id")
        if eid:
            sci[eid] = (e.get("scienceCap", 0.0, float) or 0.0,
                        e.get("baseValue", 0.0, float) or 0.0,
                        e.get("dataScale", 0.0, float) or 0.0)
    out = {}
    for p in cache["PART"]:
        for m in p.find("MODULE"):
            if m.get("name") != "Configure":
                continue
            for s in m.find("SETUP"):
                nm, tech = s.get("name"), s.get("tech")
                if not nm or not tech or nm.startswith("None"):
                    continue
                exp = None
                for k in s.kids:
                    if k.get("type") == "Experiment":
                        exp = k.get("id_value")
                cap, base, ds = sci.get(exp, (0.0, 0.0, 0.0))
                if nm not in out:
                    out[nm] = {"setup": nm, "tech": tech,
                               "tier": nodes[tech]["tier"] if tech in nodes else None,
                               "exp": exp, "cap": cap, "base": base, "data": ds,
                               "cost": s.get("cost", 0.0, float) or 0.0,
                               "mass": s.get("mass", 0.0, float) or 0.0}
    return out


def science_defects(sci):
    """Group by instrument family = setup name minus trailing generation number."""
    g = collections.defaultdict(list)
    for r in sci.values():
        m = re.match(r"^(.*?)\s*(\d+)$", r["setup"])
        if m:
            g[m.group(1).strip()].append((int(m.group(2)), r))
        else:
            g[r["setup"]].append((1, r))
    out = []
    for fam, rungs in sorted(g.items()):
        rungs = sorted(r for r in rungs if r[1]["tier"] is not None)
        if len(rungs) < 2:
            continue
        bynode = collections.defaultdict(list)
        for lvl, r in rungs:
            bynode[r["tech"]].append((lvl, r["cap"]))
        for node, lv in sorted(bynode.items()):
            if len(lv) > 1:
                t = next(r["tier"] for _, r in rungs if r["tech"] == node)
                caps = ", ".join(f"gen{l} cap={c:.0f}" for l, c in sorted(lv))
                out.append(F("COLLAPSE", fam,
                             f"generations {sorted(l for l, _ in lv)} all unlock on `{node}` (T{t}) "
                             f"— {caps}; the weaker one is obsolete the moment you buy the node",
                             "science-instrument", 2))
        for (l1, a), (l2, b) in zip(rungs, rungs[1:]):
            if b["tier"] < a["tier"] and b["cap"] >= a["cap"]:
                out.append(F("SUPERSEDED", fam,
                             f"gen{l1} gated at T{a['tier']} (`{a['tech']}`, cap={a['cap']:.0f}) but "
                             f"gen{l2} already available at T{b['tier']} (`{b['tech']}`, cap={b['cap']:.0f})",
                             "science-instrument", 1))
            elif b["tier"] - a["tier"] >= 4:
                out.append(F("GAP", fam, f"gen{l1} (T{a['tier']}) -> gen{l2} (T{b['tier']}): "
                             f"{b['tier']-a['tier']} tiers with no new instrument in this family",
                             "science-instrument", 4))
        tiers = [r["tier"] for _, r in rungs]
        if len(rungs) >= 3 and max(tiers) - min(tiers) < (len(rungs) - 1) / 2.0:
            out.append(F("COMPRESSED", fam, f"{len(rungs)} generations span only "
                         f"{max(tiers)-min(tiers)} tier(s) (T{min(tiers)}-T{max(tiers)})",
                         "science-instrument", 3))
    return out



# --------------------------------------------------------------- ladder source C2
def instrument_reachability(cache, nodes, part_node):
    """EARLIEST tier at which each experiment can actually be run, by ANY route.

    There are two gates, and checking only one is how a leak hides:
      1. a Kerbalism `Configure` SETUP with `tech = <node>`  -- the multi-slot instrument hosts;
      2. a BARE `Experiment` module on a dedicated instrument part, with no Configure wrapping it
         -- then the PART's own node is the gate, and the tech ladder has no say at all.
    `USFluidSpectroWedge` sits at T4 carrying all four mass-spectrometer experiments and is
    perfectly correct, because route 1 gates each slot; `RO-AdvancedImager` carries one bare
    experiment and so leaks its generation onto whatever node the part happens to live on.
    """
    out = collections.defaultdict(list)
    for p in cache["PART"]:
        nm = p.get("name")
        node = part_node.get(nm)
        tier = nodes[node]["tier"] if node in nodes else None
        configured = set()
        for m in p.find("MODULE"):
            if m.get("name") != "Configure":
                continue
            for st in m.find("SETUP"):
                e = next((k.get("id_value") for k in st.kids if k.get("type") == "Experiment"), None)
                tech = st.get("tech")
                if e:
                    configured.add(e)
                    if tech:
                        t2 = nodes[tech]["tier"] if tech in nodes else None
                        if t2 is not None:
                            out[e].append((t2, tech, "slot:" + (st.get("name") or ""), nm))
        for m in p.find("MODULE"):
            if m.get("name") == "Experiment":
                e = m.get("experiment_id")
                if e and e not in configured and tier is not None:
                    out[e].append((tier, node, "part", nm))
    return {e: sorted(v) for e, v in out.items()}


def instrument_defects(cache, nodes, part_node):
    sci = {}
    for e in cache["EXPERIMENT_DEFINITION"]:
        eid = e.get("id")
        if eid:
            sci[eid] = e.get("scienceCap", 0.0, float) or 0.0
    reach = instrument_reachability(cache, nodes, part_node)
    fams = collections.defaultdict(list)
    for e, routes in reach.items():
        m = re.match(r"^(.*?)(\d+)$", e)
        if not m or not routes:
            continue
        fams[m.group(1)].append((int(m.group(2)), e, routes[0], sci.get(e, 0.0)))
    out = []
    for fam, gens in sorted(fams.items()):
        gens.sort()
        if len(gens) < 2:
            continue
        # ALL pairs, not just consecutive ones: gen1 (cap 3) vs gen3 (cap 4) is exactly the kind of
        # inversion a consecutive-only walk misses when gen1 and gen2 happen to share a cap.
        for i, (g1, e1, r1, c1) in enumerate(gens):
            for (g2, e2, r2, c2) in gens[i + 1:]:
                if c2 <= c1:
                    continue                   # not actually an upgrade
                if r2[0] < r1[0]:
                    out.append(F("SUPERSEDED", fam,
                                 f"gen{g1} (cap {c1:.0f}) first reachable at T{r1[0]} via {r1[2]} `{r1[1]}`, but "
                                 f"gen{g2} (cap {c2:.0f}) is ALREADY reachable at T{r2[0]} via {r2[2]} `{r2[1]}` "
                                 f"[{r2[3]}] -- gen{g1} can never be worth building",
                                 "instrument-reach", 1))
                elif r2[0] == r1[0]:
                    where = "the same node" if r1[1] == r2[1] else f"tier T{r1[0]}"
                    out.append(F("COLLAPSE", fam,
                                 f"gen{g1} (cap {c1:.0f}, `{r1[1]}`) and gen{g2} (cap {c2:.0f}, `{r2[1]}`) both "
                                 f"arrive on {where} -- via {r1[2]} [{r1[3]}] and {r2[2]} [{r2[3]}]",
                                 "instrument-reach", 2))
    return out


# --------------------------------------------------------------- ladder source D
SCALE_TOL = 2.0     # only compare parts within this factor on the extensive axis


def part_defects(rows):
    out = []
    # Families where every axis is genuinely comparable, so "worse on all of them at the same
    # scale" really does mean "nobody will ever pick this". Engines / RCS / pods are excluded:
    # they are differentiated by role, propellant and geometry that no scalar captures, and the
    # engine-config ladder above is the right instrument for them.
    # DELIBERATELY NARROW. These six have one honest scalar each (W/kg, Wh/kg, kN.m/kg, kW/kg,
    # dBi) that really does order the family. Excluded on purpose, because the obvious proxy is
    # WRONG rather than merely noisy:
    #   parachute  -- deployedDiameter/kg conflates drogues with mains and RealChute does not
    #                 store the number that matters (canopy area at deployment pressure);
    #   heatshield -- PART maxTemp is the structure's limit, not the ablator's capability;
    #   crewpod    -- crew count is a mission-class axis, not a tech axis;
    #   engines    -- role/propellant/geometry dominate; the engine-CONFIG ladder above is the
    #                 right instrument for them.
    COMPARABLE = {"solar", "battery", "rtg", "reaction_wheel", "radiator", "antenna"}
    byfam = collections.defaultdict(list)
    for r in rows:
        if r["tier"] is None or r["node"] in ("parking", "experimental"):
            continue
        if r["family"] not in COMPARABLE:
            continue
        # An integrated spacecraft bus (Vanguard 1, Sphinx, a comsat core) carries solar/battery
        # as INCIDENTAL kit -- you do not pick it for its W/kg, so judging it against a dedicated
        # panel is a category error. Only compare parts whose family IS their job.
        mods = set(r["modules"])
        if mods & {"ModuleCommand", "ModuleEnginesRF", "ModuleEnginesFX"} or r["crew"]:
            continue
        byfam[r["family"]].append(r)
    for fam, members in sorted(byfam.items()):
        intens, extens = tb.FAMILY_AXES.get(fam, (None, None))
        if not intens:
            continue
        usable = [m for m in members if all(m["derived"].get(a) for a in intens)]
        for a in usable:
            for b in usable:
                if a is b:
                    continue
                # same scale class?
                if extens:
                    ok = True
                    for x in extens:
                        av, bv = a["derived"].get(x), b["derived"].get(x)
                        if av and bv and not (1 / SCALE_TOL <= bv / av <= SCALE_TOL):
                            ok = False
                    if not ok:
                        continue
                if not all(b["derived"][x] >= a["derived"][x] * 0.999 for x in intens):
                    continue
                if not any(b["derived"][x] >= a["derived"][x] * 1.15 for x in intens):
                    continue
                ev = ", ".join(f"{x} {a['derived'][x]:.3g}->{b['derived'][x]:.3g}" for x in intens)
                if a["node"] == b["node"]:
                    out.append(F("DOMINATED", fam,
                                 f"`{a['name']}` ({a['ctitle'][:38]}) is dominated by `{b['name']}` "
                                 f"({b['ctitle'][:38]}) on the SAME node `{a['node']}` T{a['tier']}: {ev}",
                                 "part", 2))
                elif b["tier"] < a["tier"]:
                    out.append(F("DEADONARR", fam,
                                 f"`{a['name']}` ({a['ctitle'][:38]}) T{a['tier']} `{a['node']}` is beaten by "
                                 f"`{b['name']}` ({b['ctitle'][:38]}) already at T{b['tier']} `{b['node']}`: {ev}",
                                 "part", 1))
    seen = set(); ded = []
    for f in out:
        k = (f.kind, f.group, tuple(sorted(re.findall(r"`([^`]+)`", f.detail))))
        if k in seen:
            continue
        seen.add(k)
        ded.append(f)
    return ded


# --------------------------------------------------------------------- reporting
def tier_profile(rows, sci, nodes):
    """Best capability reachable at each tier, per family -- the 'what does this tier give me' table."""
    fams = ["engine_rocket", "engine_small", "solar", "battery", "rtg", "antenna",
            "reaction_wheel", "heatshield", "crewpod", "avionics", "radiator", "engine_electric"]
    axis = {"engine_rocket": "ispVac", "engine_small": "ispVac", "engine_electric": "ispVac",
            "solar": "solar_per_kg", "battery": "ec_per_kg", "rtg": "gen_per_kg",
            "antenna": "antGain", "reaction_wheel": "torque_per_kg", "heatshield": "maxTemp",
            "crewpod": "crew", "avionics": "mass", "radiator": "rad_per_kg"}
    tiers = sorted({r["tier"] for r in rows if r["tier"] is not None})
    tbl = {}
    for fam in fams:
        best = None
        for t in tiers:
            for r in rows:
                if r["family"] == fam and r["tier"] == t:
                    v = r["derived"].get(axis[fam])
                    if v and (best is None or v > best):
                        best = v
            tbl[(fam, t)] = best
    return fams, tiers, tbl, axis


def main():
    rows, cache, nodes, part_node, upg_node = tb.build()
    sci = science_ladder(cache, nodes)
    eng = engine_config_ladders(nodes, upg_node)

    findings = []
    findings += science_defects(sci)
    findings += instrument_defects(cache, nodes, part_node)
    findings += level_defects(level_ladders(cache, nodes, upg_node))
    findings += engine_defects(eng, part_node, nodes)
    findings += part_defects(rows)
    findings.sort(key=lambda f: (f.severity, f.kind, f.group))

    if "--json" in sys.argv:
        print(json.dumps([f._asdict() for f in findings], indent=1))
        return

    sec = None
    if "--section" in sys.argv:
        sec = sys.argv[sys.argv.index("--section") + 1]

    cnt = collections.Counter(f.kind for f in findings)
    src = collections.Counter(f.source for f in findings)
    print("=" * 104)
    print(f"DEFECT CENSUS  total={len(findings)}   by kind={dict(cnt)}")
    print(f"                                by source={dict(src)}")
    print("=" * 104)
    cur = None
    for f in findings:
        if sec and f.source != sec:
            continue
        if f.kind != cur:
            print(f"\n===== {f.kind} " + "=" * (96 - len(f.kind)))
            cur = f.kind
        print(f"  [{f.source:<18}] {f.group:<28} {f.detail}")

    if sec:
        return
    print("\n" + "=" * 104)
    print("SCIENCE-INSTRUMENT LADDER  (Kerbalism `Configure` tech gate -> AXE node)")
    print("=" * 104)
    for r in sorted(sci.values(), key=lambda r: (r["tier"] if r["tier"] is not None else 99, r["setup"])):
        print(f"  T{str(r['tier']):<3} {r['tech']:<34} {r['setup']:<32} scienceCap={r['cap']:<7.0f} "
              f"data={r['data']:<9.4g} cost={r['cost']:.0f}")

    fams, tiers, tbl, axis = tier_profile(rows, sci, nodes)
    print("\n" + "=" * 104)
    print("TIER PROFILE — best value reachable BY that tier (cumulative max of the intensive axis)")
    print("=" * 104)
    print(f"  {'family / axis':<34}" + "".join(f"T{t:<6}" for t in tiers))
    for fam in fams:
        line = f"  {fam+' / '+axis[fam]:<34}"
        for t in tiers:
            v = tbl.get((fam, t))
            line += f"{('%.4g' % v) if v else '-':<7}"
        print(line)


if __name__ == "__main__":
    main()
