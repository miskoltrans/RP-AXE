#!/usr/bin/env python3
"""tier_balance — tier-by-tier balance audit of the AXE tree.

THE HARD PART is estimating "part capability" without a human eye. The model here:

  capability is only comparable WITHIN a functional family, and within a family the
  thing that encodes TECH GENERATION is the INTENSIVE (specific) metric --
  W/kg, N.s/kg, Isp, torque/tonne, kW/tonne -- never the EXTENSIVE one (total EC,
  total thrust, panel area). A bigger battery is not a better battery; a 2 MN engine
  is not a more advanced engine than a 400 kN one. Extensive size is a CLASS axis
  (what mission it serves); intensive performance is the TIER axis.

So each family declares:
  axes  = intensive metrics (higher = more advanced) -> drives dominance/ladder checks
  scale = extensive metrics                          -> reported, never used for dominance

Reads the live ModuleManager.ConfigCache (ground truth, post-RO-patch), joins with
tree/nodes.yaml placement, and runs the detectors in tools/tier_defects.py.

Output: manifest/part-capability-full.tsv
"""
import os, re, sys, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
MAN = os.path.join(ROOT, "manifest")
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"


# ---------------------------------------------------------------- cache parsing
class Node:
    __slots__ = ("kind", "vals", "kids")

    def __init__(self, kind):
        self.kind = kind
        self.vals = collections.defaultdict(list)   # key -> [values]
        self.kids = []                              # [Node]

    def get(self, key, default=None, cast=None):
        v = self.vals.get(key)
        if not v:
            return default
        if cast is None:
            return v[0]
        try:
            return cast(v[0])
        except (ValueError, TypeError):
            return default

    def find(self, kind):
        return [k for k in self.kids if k.kind == kind]

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()


def parse_cache(path):
    """Stream the cache into top-level PART / PARTUPGRADE / TANK_DEFINITION / EXPERIMENT_DEFINITION
    trees. Returns dict kind -> [Node]."""
    want = {"PART", "PARTUPGRADE", "TANK_DEFINITION", "EXPERIMENT_DEFINITION", "RESOURCE_DEFINITION"}
    out = collections.defaultdict(list)
    stack = []
    pending = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("//"):
                continue
            if s == "{":
                n = Node(pending if pending else "?")
                if stack:
                    stack[-1].kids.append(n)
                stack.append(n)
                pending = None
                continue
            if s.startswith("}"):
                if stack:
                    done = stack.pop()
                    # the cache wraps every file's root in a UrlConfig, so the interesting
                    # blocks are one level down -- match by kind at any depth.
                    if done.kind in want:
                        out[done.kind].append(done)
                pending = None
                continue
            if "=" in s:
                k, v = s.split("=", 1)
                k = k.strip().lstrip("@%+-!*")
                if stack:
                    stack[-1].vals[k].append(v.strip())
                pending = None
            else:
                pending = s
    return out


def fnum(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- part metrics
def vac_isp(part):
    """Peak vacuum Isp across every engine module / engine CONFIG in the part."""
    best = None
    for n in part.walk():
        if n.kind != "atmosphereCurve":
            continue
        for k in n.vals.get("key", []):
            bits = k.split()
            if len(bits) >= 2 and fnum(bits[0]) == 0.0:
                v = fnum(bits[1])
                if v and (best is None or v > best):
                    best = v
    return best


def part_metrics(part):
    """Everything we can measure about a part, from the live (post-RO) config."""
    name = part.get("name")
    mass = part.get("mass", 0.0, float) or 0.0
    mods = [m.get("name") for m in part.find("MODULE")]
    mods = [m for m in mods if m]
    m = {"name": name, "mass": mass, "modules": mods}

    # --- resources carried (extensive)
    res = {}
    for r in part.find("RESOURCE"):
        rn = r.get("name")
        if rn:
            res[rn] = (res.get(rn, 0.0) or 0.0) + (r.get("maxAmount", 0.0, float) or 0.0)
    # RealFuels tanks declare TANK blocks instead
    for mod in part.find("MODULE"):
        for t in mod.find("TANK"):
            tn = t.get("name")
            if tn:
                res[tn] = (res.get(tn, 0.0) or 0.0) + (t.get("maxAmount", 0.0, float) or 0.0)
    m["res"] = res
    m["ec"] = res.get("ElectricCharge", 0.0)

    # --- propulsion
    thr = []
    for mod in part.find("MODULE"):
        for n in mod.walk():
            v = n.get("maxThrust", None, float)
            if v:
                thr.append(v)
    m["maxThrust"] = max(thr) if thr else None
    m["ispVac"] = vac_isp(part)
    m["minThrottle"] = None
    for mod in part.find("MODULE"):
        v = mod.get("minThrust", None, float)
        mt = mod.get("maxThrust", None, float)
        if v is not None and mt:
            m["minThrottle"] = v / mt if mt else None
    ign = []
    for n in part.walk():
        v = n.get("ignitions", None, int)
        if v is not None:
            ign.append(v)
    m["ignitions"] = max(ign) if ign else None

    # --- electrical
    sol = []
    for mod in part.find("MODULE"):
        if mod.get("name") in ("ModuleDeployableSolarPanel", "ModuleROSolarPanel", "SolarPanelFixer"):
            v = mod.get("chargeRate", None, float)
            if v:
                sol.append(v)
    m["solarRate"] = max(sol) if sol else None
    gen = []
    for mod in part.find("MODULE"):
        if mod.get("name") in ("ModuleGenerator", "ModuleRadioisotopeGenerator"):
            # OUTPUT_RESOURCE only -- INPUT_RESOURCE blocks would otherwise register habitat
            # EC *draw* as generation (and come out negative).
            for r in mod.find("OUTPUT_RESOURCE"):
                if r.get("name") == "ElectricCharge":
                    v = r.get("rate", None, float)
                    if v and v > 0:
                        gen.append(v)
    # Kerbalism replaces stock RTG generators with a ProcessController running the `_RTG`
    # process; its `capacity` is the output scale, so that -- not ModuleGenerator -- is where
    # an RTG's power actually lives in this install.
    for mod in part.find("MODULE"):
        if mod.get("name") == "ProcessController" and mod.get("resource") == "_RTG":
            v = mod.get("capacity", None, float)
            if v:
                gen.append(v)
    m["genRate"] = max(gen) if gen else None

    # --- comms  (RealAntennas: TxPower dBm + gain dBi)
    tx, gain, ant = [], [], []
    for mod in part.find("MODULE"):
        if mod.get("name") == "ModuleRealAntenna":
            v = mod.get("TxPower", None, float)
            if v is not None:
                tx.append(v)
            g = mod.get("referenceGain", None, float)
            if g is not None:
                gain.append(g)
            t = mod.get("TechLevel", None, float)
            if t is not None:
                ant.append(t)
        if mod.get("name") == "ModuleDataTransmitter":
            v = mod.get("antennaPower", None, float)
            if v is not None:
                ant.append(v)
    m["txPower"] = max(tx) if tx else None
    m["antGain"] = max(gain) if gain else None
    m["antTL"] = max(ant) if ant else None

    # --- attitude
    tq = []
    for mod in part.find("MODULE"):
        if mod.get("name") == "ModuleReactionWheel":
            for k in ("PitchTorque", "YawTorque", "RollTorque"):
                v = mod.get(k, None, float)
                if v:
                    tq.append(v)
    m["torque"] = max(tq) if tq else None

    # --- thermal / recovery
    m["maxTemp"] = part.get("maxTemp", None, float)
    abl = []
    for mod in part.find("MODULE"):
        if mod.get("name") in ("ModuleAblator", "ModuleHeatShield", "ModuleROHeatshield"):
            abl.append(1.0)
    m["isShield"] = bool(abl) or "Ablator" in res or "AblativeShielding" in res
    m["ablator"] = res.get("Ablator", res.get("AblativeShielding", None))
    chute = []
    for mod in part.find("MODULE"):
        if mod.get("name") in ("ModuleParachute", "RealChuteModule", "RealChuteFAR"):
            v = mod.get("deployedDiameter", None, float) or mod.get("chuteArea", None, float)
            chute.append(v or 1.0)
    m["chute"] = max(chute) if chute else None

    # --- radiators
    rad = []
    for mod in part.find("MODULE"):
        if mod.get("name") in ("ModuleActiveRadiator", "ModuleDeployableRadiator"):
            v = mod.get("maxEnergyTransfer", None, float)
            if v:
                rad.append(v)
    m["radiator"] = max(rad) if rad else None

    # --- crew / science
    m["crew"] = part.get("CrewCapacity", 0, int) or 0
    exps = []
    for mod in part.find("MODULE"):
        e = mod.get("experimentID")
        if e:
            exps.append(e)
        for sub in mod.walk():
            e2 = sub.get("experiment")
            if e2:
                exps.append(e2)
    m["experiments"] = sorted(set(exps))
    m["cost"] = part.get("cost", None, float)
    m["title"] = part.get("title", "")
    m["category"] = part.get("category", "")
    return m


# ---------------------------------------------------------------- families
def classify(m):
    """Functional family. Order matters -- first match wins."""
    mods = set(m["modules"])
    n = m["name"] or ""
    t = (m["title"] or "").lower()

    if mods & {"ModuleEnginesRF", "ModuleEnginesFX", "ModuleEngines", "ModuleEnginesAJE",
               "ModuleEnginesAJEJet", "ModuleEnginesAJEPropeller"}:
        # AJE jets/props report Isp in the thousands, so the air-breathing test MUST come first
        # or every turbojet lands in the electric-propulsion bucket.
        if mods & {"ModuleEnginesAJEJet", "ModuleEnginesAJEPropeller", "ModuleEnginesAJERamjet"}:
            return "engine_airbreathing"
        if m.get("ispVac") and m["ispVac"] > 1200:
            return "engine_electric"
        if m.get("maxThrust") is not None and m["maxThrust"] < 10:
            return "engine_small"
        return "engine_rocket"
    if "ModuleRCSFX" in mods or "ModuleRCS" in mods:
        return "rcs"
    # Crewed pods and probe cores are classified FIRST. A probe bus carries solar, an antenna and
    # a reaction wheel as incidental kit; letting it fall into `solar` would put an integrated
    # spacecraft into the same league table as a dedicated panel and wreck the frontier.
    if m["crew"] > 0:
        return "crewpod"
    if "ModuleCommand" in mods or "ModuleAxeAvionics" in mods or "ModuleAxeFixedAvionics" in mods             or "ModuleProceduralAvionics" in mods:
        return "avionics"
    if m.get("solarRate"):
        return "solar"
    if m.get("genRate"):
        return "rtg" if ("rtg" in n.lower() or "rtg" in t or "isotope" in t) else "generator"
    if m.get("txPower") is not None or m.get("antTL") is not None or m.get("antGain") is not None:
        return "antenna"
    if m.get("torque"):
        return "reaction_wheel"
    if m.get("radiator"):
        return "radiator"
    if m["isShield"]:
        return "heatshield"
    if m.get("chute"):
        return "parachute"
    if m["experiments"]:
        return "science"
    # a battery is EC storage and nothing else -- fuel cells, converters and anything that
    # merely carries a reserve alongside another job are not batteries.
    if (m["ec"] and m["ec"] > 0
            and not (mods & {"ModuleFuelTanks", "ModuleResourceConverter", "ModuleGenerator",
                             "ProcessController", "ModuleCommand", "ModuleDeployableSolarPanel"})):
        return "battery"
    if "ModuleFuelTanks" in mods or m["res"]:
        return "tank"
    if "ModuleDecouple" in mods or "ModuleAnchoredDecoupler" in mods:
        return "separator"
    if "ModuleDockingNode" in mods:
        return "docking"
    if mods & {"ModuleWheelBase", "ModuleWheelSuspension", "ModuleWheelMotor"}:
        return "wheel"
    if "ModuleLiftingSurface" in mods or "ModuleControlSurface" in mods:
        return "aero"
    if "ModuleProceduralFairing" in mods or "ProceduralFairingSide" in mods:
        return "fairing"
    if "ModuleLight" in mods:
        return "light"
    if "ModuleResourceConverter" in mods or "ModuleResourceHarvester" in mods:
        return "isru"
    return "structural"


# intensive axes (tech generation) vs extensive axes (mission class)
FAMILY_AXES = {
    "engine_rocket":      (["ispVac"], ["maxThrust"]),
    "engine_small":       (["ispVac"], ["maxThrust"]),
    "engine_electric":    (["ispVac"], ["maxThrust"]),
    "engine_airbreathing": (["ispVac"], ["maxThrust"]),
    "rcs":                (["ispVac"], ["maxThrust"]),
    "solar":              (["solar_per_kg"], ["solarRate"]),
    "rtg":                (["gen_per_kg"], ["genRate"]),
    "generator":          (["gen_per_kg"], ["genRate"]),
    "battery":            (["ec_per_kg"], ["ec"]),
    "antenna":            (["txPower", "antGain", "antTL"], []),
    "reaction_wheel":     (["torque_per_kg"], ["torque"]),
    "radiator":           (["rad_per_kg"], ["radiator"]),
    "heatshield":         (["maxTemp"], ["mass"]),
    "parachute":          (["chute_per_kg"], ["chute"]),
    "science":            (["sci_value"], []),
    "crewpod":            (["maxTemp"], ["crew"]),
}


def derive(m):
    """Intensive metrics. mass is in tonnes in KSP configs."""
    kg = (m["mass"] or 0.0) * 1000.0
    d = {}
    if kg > 0:
        if m.get("maxThrust"):
            d["twr"] = m["maxThrust"] * 1000.0 / (kg * 9.80665)
        if m.get("solarRate"):
            d["solar_per_kg"] = m["solarRate"] / kg
        if m.get("genRate"):
            d["gen_per_kg"] = m["genRate"] / kg
        if m.get("ec"):
            d["ec_per_kg"] = m["ec"] / kg
        if m.get("torque"):
            d["torque_per_kg"] = m["torque"] / kg
        if m.get("radiator"):
            d["rad_per_kg"] = m["radiator"] / kg
        if m.get("chute"):
            d["chute_per_kg"] = m["chute"] / kg
    for k in ("ispVac", "maxThrust", "solarRate", "genRate", "ec", "txPower", "antGain",
              "antTL", "torque", "radiator", "maxTemp", "chute", "mass", "crew"):
        if m.get(k) is not None:
            d[k] = m[k]
    return d


# ---------------------------------------------------------------- tree join
def load_tree():
    import yaml
    d = yaml.safe_load(open(os.path.join(ROOT, "tree", "nodes.yaml"), encoding="utf-8"))
    nodes = {n["id"]: n for n in d["nodes"]}
    part_node, upg_node = {}, {}
    for n in d["nodes"]:
        for p in (n.get("parts") or []):
            part_node[p] = n["id"]
        for u in (n.get("upgrades") or []):
            upg_node[u] = n["id"]
    return d, nodes, part_node, upg_node


def curated():
    s = {}
    with open(os.path.join(MAN, "curated-parts.tsv"), encoding="utf-8") as f:
        next(f, None)
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) > 2:
                s[c[1]] = (c[0], c[2])
    return s


def build():
    cur = curated()
    cache = parse_cache(CACHE)
    _, nodes, part_node, upg_node = load_tree()
    sci_value = {}
    for e in cache["EXPERIMENT_DEFINITION"]:
        eid = e.get("id")
        if eid:
            sci_value[eid] = (e.get("scienceCap", 0.0, float) or 0.0,
                              e.get("baseValue", 0.0, float) or 0.0,
                              e.get("dataScale", 1.0, float) or 1.0)

    rows = []
    seen = set()
    for p in cache["PART"]:
        nm = p.get("name")
        if nm is None or nm in seen:
            continue
        if nm not in cur:
            continue
        seen.add(nm)
        m = part_metrics(p)
        m["mod"], m["ctitle"] = cur[nm]
        fam = classify(m)
        d = derive(m)
        if fam == "science":
            best = 0.0
            for e in m["experiments"]:
                best = max(best, sci_value.get(e, (0,))[0])
            d["sci_value"] = best
        nid = part_node.get(nm)
        m["node"] = nid
        m["tier"] = nodes[nid]["tier"] if nid in nodes else None
        m["discipline"] = nodes[nid]["discipline"] if nid in nodes else None
        m["family"] = fam
        m["derived"] = d
        rows.append(m)
    return rows, cache, nodes, part_node, upg_node


def main():
    rows, cache, nodes, part_node, upg_node = build()
    cols = ["name", "family", "node", "tier", "discipline", "mass", "ctitle", "mod"]
    axes = ["ispVac", "twr", "maxThrust", "solar_per_kg", "solarRate", "gen_per_kg", "genRate",
            "ec_per_kg", "ec", "txPower", "antGain", "antTL", "torque_per_kg", "torque",
            "rad_per_kg", "radiator", "maxTemp", "chute_per_kg", "sci_value", "crew"]
    out = os.path.join(MAN, "part-capability-full.tsv")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\t".join(cols + axes) + "\n")
        for r in sorted(rows, key=lambda x: (x["family"], x["tier"] if x["tier"] is not None else 99, x["name"])):
            base = [str(r.get(c, "") if r.get(c) is not None else "") for c in cols]
            av = [("%.6g" % r["derived"][a]) if a in r["derived"] else "" for a in axes]
            f.write("\t".join(base + av) + "\n")
    fam = collections.Counter(r["family"] for r in rows)
    print(f"parts measured: {len(rows)}  -> {out}")
    for k, v in fam.most_common():
        print(f"   {k:<20} {v}")


if __name__ == "__main__":
    main()
