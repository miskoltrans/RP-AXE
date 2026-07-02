#!/usr/bin/env python3
"""
extract_engine_stats.py  --  RP-AXE engine/booster stats & upgrade-path reference.

For every curated engine/booster part (part-capabilities.tsv disc == engine:*), pull
its RealFuels `ModuleEngineConfigs` CONFIG variants from the RP-1 reference cache
(ksp_rp1_expanded, which is RO engines + RP-1's TREE-Engines.cfg techRequired/cost
placement baked in). Each CONFIG is a selectable variant gated behind an RP-1 tech
node -- the ordered set of a part's CONFIGs *is* its upgrade path.

Sources (all read-only ground truth):
  RP-AXE/manifest/curated-parts.tsv        -- the 1787 curated part names (authority)
  RP-AXE/manifest/part-capabilities.tsv    -- name -> disc (engine:kerolox/solid/...)
  ksp_rp1_expanded/.../ModuleManager.ConfigCache -- compiled RO+RP-1: stats + techRequired
  ksp_rp1_expanded/.../RP-1/Tree/RP0TechTree.cfg -- node id -> title + era (pos.x)

Emits:
  RP-AXE/manifest/engine-stats.tsv         -- one row per (part, config); greppable lookup
  (docs/ENGINE-STATS.md is written by a companion pass / by hand from this TSV)

Reproduce:  python RP-AXE/tools/extract_engine_stats.py
"""
import os
import re
import sys

# ---- paths (repo-root relative to this script: RP-AXE/tools/..) --------------
HERE = os.path.dirname(os.path.abspath(__file__))
RPAXE = os.path.dirname(HERE)                 # .../RP-AXE
ROOT = os.path.dirname(RPAXE)                 # .../ksp  (repo root)

CURATED = os.path.join(RPAXE, "manifest", "curated-parts.tsv")
CAPS = os.path.join(RPAXE, "manifest", "part-capabilities.tsv")
CACHE = os.path.join(ROOT, "ksp_rp1_expanded", "GameData", "ModuleManager.ConfigCache")
# fallback for curated engines RP-1 does not ship/place (integrated probes, some verniers):
# RO stats without RP-1 tech placement.
RO_CACHE = os.path.join(ROOT, "ksp_ro_expanded", "GameData", "ModuleManager.ConfigCache")
TREE = os.path.join(ROOT, "ksp_rp1_expanded", "GameData", "RP-1", "Tree", "RP0TechTree.cfg")

OUT_TSV = os.path.join(RPAXE, "manifest", "engine-stats.tsv")
OUT_DOC = os.path.join(RPAXE, "docs", "ENGINE-STATS.md")


# ---- generic ConfigNode parser ----------------------------------------------
# The cache is a brace-delimited tree. A block is introduced by a bare identifier
# line, then `{`, contents, `}`. Key-values are `k = v` (v may contain '=').
def parse_block(lines, i):
    """Parse the contents of a block starting just after its '{'.
    Returns (node_dict, next_index). Repeated keys/subblocks -> lists."""
    node = {}
    pending = None
    n = len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        i += 1
        if s == "" or s.startswith("//"):
            continue
        if s == "{":
            child, i = parse_block(lines, i)
            key = pending if pending is not None else "_anon"
            node.setdefault(key, []).append(child)
            pending = None
            continue
        if s == "}":
            return node, i
        if "=" in s:
            k, v = s.split("=", 1)
            node.setdefault(k.strip(), []).append(v.strip())
            pending = None
        else:
            # bare identifier -> name of the next block
            pending = s
    return node, i


def get(node, key):
    """First value of a scalar key, or None."""
    v = node.get(key)
    return v[0] if v else None


# ---- RP0TechTree: node id -> (title, era_x) ----------------------------------
def load_tree(path):
    nodes = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    # RDNode blocks: id / title / pos = x,y,z
    for m in re.finditer(r"RDNode\s*\{(.*?)\n\t\}", text, re.S):
        body = m.group(1)
        idm = re.search(r"\bid\s*=\s*(\S+)", body)
        tm = re.search(r"\btitle\s*=\s*(.+)", body)
        pm = re.search(r"\bpos\s*=\s*(-?[\d.]+)", body)
        if not idm:
            continue
        nid = idm.group(1).strip()
        title = tm.group(1).strip() if tm else nid
        era = float(pm.group(1)) if pm else 0.0
        nodes[nid] = (title, era)
    return nodes


# ---- curated engine set: name -> disc ----------------------------------------
def load_engine_parts():
    curated = set()
    with open(CURATED, encoding="utf-8", errors="replace") as fh:
        next(fh)
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) >= 2:
                curated.add(c[1])
    disc = {}
    title = {}
    with open(CAPS, encoding="utf-8", errors="replace") as fh:
        header = next(fh).rstrip("\n").split("\t")
        di = header.index("disc")
        ti = header.index("title")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) > max(di, ti):
                disc[c[0]] = c[di]
                title[c[0]] = c[ti]
    engines = {name: disc[name] for name in curated
               if disc.get(name, "").startswith("engine")}
    return engines, disc, title


# ---- Isp -> (ispVac, ispSL, mode) --------------------------------------------
# Two encodings in RealFuels configs:
#   "curve"   -- explicit atmosphereCurve, values are absolute seconds (most engines)
#   "TL-frac" -- IspSL/IspV fields are fractions (0-1) of the engine TYPE's tech-level
#                Isp ceiling (small RCS/OMS/cold-gas thrusters). NOT seconds.
def isp_extract(cfg):
    curves = cfg.get("atmosphereCurve")
    if curves:
        pts = []
        for k in curves[0].get("key", []):
            parts = k.split()
            if len(parts) >= 2:
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
        if pts:
            pts.sort()
            isp_vac = pts[0][1]               # Isp at lowest pressure (~0 = vacuum)
            isp_sl = next((v for p, v in pts if abs(p - 1.0) < 1e-6), None)
            return isp_vac, isp_sl, "curve"
    v, s = get(cfg, "IspV"), get(cfg, "IspSL")
    if v is not None or s is not None:
        return v, s, "TL-frac"
    return None, None, ""


def props(cfg):
    out = []
    for p in cfg.get("PROPELLANT", []):
        name = get(p, "name")
        if not name:
            continue
        if get(p, "ignoreForIsp") in ("True", "true"):
            continue                          # pressurant, not a real propellant
        out.append(name)
    return "+".join(out)


def num(v):
    if v is None:
        return ""
    return v


# ---- main --------------------------------------------------------------------
def scan_cache(cache_path, source, want, engines, tree, rows, found):
    """Walk a ConfigCache, emitting rows for PART blocks whose name is in `want`."""
    with open(cache_path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s == "UrlConfig":
            j = i + 1
            while j < n and lines[j].strip() == "":
                j += 1
            if j < n and lines[j].strip() == "{":
                block, i = parse_block(lines, j + 1)
                process_urlconfig(block, engines, tree, rows, found, source, want)
                continue
        i += 1


def main():
    tree = load_tree(TREE)
    engines, disc_all, title_all = load_engine_parts()
    sys.stderr.write(f"curated engine/booster parts: {len(engines)}\n")

    rows = []
    found_parts = set()

    # Pass 1 -- RP-1 reference (RO engines + RP-1 TREE-Engines techRequired/cost).
    scan_cache(CACHE, "rp1_expanded", set(engines), engines, tree, rows, found_parts)
    n1 = len(found_parts)

    # Pass 2 -- RO fallback for curated engines RP-1 does not ship as PARTs (no RP-1
    # tech placement; stats only). Excludes anything already found.
    still = set(engines) - found_parts
    if os.path.exists(RO_CACHE) and still:
        scan_cache(RO_CACHE, "ro_expanded", still, engines, tree, rows, found_parts)

    missing = sorted(set(engines) - found_parts)
    write_tsv(rows, missing, engines, disc_all)
    write_doc(rows, missing, engines, n1, len(found_parts) - n1)
    sys.stderr.write(
        f"engine parts covered: {len(found_parts)} "
        f"(RP-1={n1}, RO-fallback={len(found_parts) - n1}) | "
        f"config rows: {len(rows)} | no config path: {len(missing)}\n")


CFG_MODULES = ("ModuleEngineConfigs", "ModuleBimodalEngineConfigs")
# airbreathing / integrated engine modules that carry NO RealFuels config path
FIXED_ENGINE_MODULES = ("ModuleEnginesAJEJet", "ModuleEnginesAJEPropeller",
                        "ModuleEnginesAJERamjet", "ModuleEnginesRF",
                        "ModuleEngines", "ModuleEnginesFX", "ModuleRCSFX",
                        "ModuleRCS")

# name -> reason string for engine-disc parts without a config path
NO_CFG = {}


def process_urlconfig(block, engines, tree, rows, found_parts, source, want):
    for part in block.get("PART", []):
        name = get(part, "name")
        if name is None:
            continue
        # cache mangles duplicate part names as "orig_name/dup"? name is clean here.
        base = name.split("/")[0]
        if base not in want or base in found_parts:
            continue
        modnames = [get(m, "name") for m in part.get("MODULE", [])]
        part_title = get(part, "title") or base
        part_tech = get(part, "TechRequired") or get(part, "techRequired") or ""
        mecs = [m for m in part.get("MODULE", [])
                if get(m, "name") in CFG_MODULES]
        if not mecs:
            # No RealFuels config path. Two sub-cases:
            #  (a) a plain ModuleEnginesRF with inline stats and no CONFIG switching
            #      -> emit ONE single-config row (LES solids, FFT drives, verniers).
            #  (b) airbreathing (AJE jet/prop/ramjet) or integrated/effect part
            #      -> record in the trailer with the reason.
            rf = next((m for m in part.get("MODULE", [])
                       if get(m, "name") == "ModuleEnginesRF"), None)
            aje = [m for m in ("ModuleEnginesAJEJet", "ModuleEnginesAJEPropeller",
                               "ModuleEnginesAJERamjet") if m in modnames]
            if rf is not None and not aje:
                found_parts.add(base)
                NO_CFG.pop(base, None)
                isp_vac, isp_sl, isp_mode = isp_extract(rf)
                node_title, era = tree.get(part_tech, ("", 999999.0))
                rows.append({
                    "part": base, "title": part_title, "disc": engines[base],
                    "config": get(rf, "engineID") or "(single config)",
                    "is_base": "single", "techRequired": part_tech,
                    "node_title": node_title,
                    "era_x": f"{era:.0f}" if era != 999999.0 else "",
                    "cost": "", "specLevel": "",
                    "maxThrust_kN": num(get(rf, "maxThrust")),
                    "minThrust_kN": num(get(rf, "minThrust")),
                    "ispVac": num(isp_vac), "ispSL": num(isp_sl),
                    "ispMode": isp_mode,
                    "propellants": props(rf), "massMult": "", "origMass_t": "",
                    "ullage": "", "pressureFed": "",
                    "ignitions": "", "ratedBurnTime": "",
                    "ignRelStart": "", "ignRelEnd": "",
                    "engineType": get(rf, "EngineType") or "ModuleEnginesRF",
                    "partTech": part_tech, "source": source,
                })
                continue
            present = [m for m in FIXED_ENGINE_MODULES if m in modnames]
            NO_CFG[base] = ("+".join(present) if present
                            else "no engine module (integrated/effect part)")
            continue
        found_parts.add(base)
        NO_CFG.pop(base, None)
        mec = mecs[0]
        base_cfg = get(mec, "configuration") or ""
        orig_mass = get(mec, "origMass") or ""
        etype = get(mec, "type") or ""
        for cfg in mec.get("CONFIG", []):
            cname = get(cfg, "name") or ""
            tech = get(cfg, "techRequired") or ""
            node_title, era = tree.get(tech, ("", 999999.0))
            isp_vac, isp_sl, isp_mode = isp_extract(cfg)
            rows.append({
                "part": base,
                "title": part_title,
                "disc": engines[base],
                "config": cname,
                "is_base": "base" if cname == base_cfg else "",
                "techRequired": tech,
                "node_title": node_title,
                "era_x": f"{era:.0f}" if era != 999999.0 else "",
                "cost": num(get(cfg, "cost")),
                "specLevel": num(get(cfg, "specLevel")),
                "maxThrust_kN": num(get(cfg, "maxThrust")),
                "minThrust_kN": num(get(cfg, "minThrust")),
                "ispVac": num(isp_vac),
                "ispSL": num(isp_sl),
                "ispMode": isp_mode,
                "propellants": props(cfg),
                "massMult": num(get(cfg, "massMult")),
                "origMass_t": orig_mass,
                "ullage": num(get(cfg, "ullage")),
                "pressureFed": num(get(cfg, "pressureFed")),
                "ignitions": num(get(cfg, "ignitions")),
                "ratedBurnTime": num(get(cfg, "ratedBurnTime")),
                "ignRelStart": num(get(cfg, "ignitionReliabilityStart")),
                "ignRelEnd": num(get(cfg, "ignitionReliabilityEnd")),
                "engineType": etype,
                "partTech": part_tech, "source": source,
            })


COLS = ["part", "title", "disc", "config", "is_base", "techRequired", "node_title",
        "era_x", "cost", "specLevel", "maxThrust_kN", "minThrust_kN", "ispVac",
        "ispSL", "ispMode", "propellants", "massMult", "origMass_t", "ullage",
        "pressureFed", "ignitions", "ratedBurnTime", "ignRelStart", "ignRelEnd",
        "engineType", "partTech", "source"]


def write_tsv(rows, missing, engines, disc_all):
    # sort: disc, part, then config by era (upgrade path order)
    def sortkey(r):
        try:
            e = float(r["era_x"]) if r["era_x"] else 1e9
        except ValueError:
            e = 1e9
        return (r["disc"], r["part"], e, r["config"])
    rows.sort(key=sortkey)
    with open(OUT_TSV, "w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in rows:
            fh.write("\t".join(str(r.get(c, "")) for c in COLS) + "\n")
        # trailer: engine-disc parts with no RF config path (fixed-stat / airbreathing
        # / integrated). engineType column carries the reason (which module instead).
        for m in missing:
            blank = {c: "" for c in COLS}
            blank["part"] = m
            blank["disc"] = engines[m]
            reason = NO_CFG.get(m, "absent in RP-1 cache")
            blank["config"] = "(no RealFuels config path)"
            blank["engineType"] = reason
            fh.write("\t".join(str(blank.get(c, "")) for c in COLS) + "\n")


# ---- human-readable index doc ------------------------------------------------
DISC_ORDER = [
    ("engine:solid", "Solid motors & boosters"),
    ("engine:kerolox", "Kerolox (kerosene / LOX)"),
    ("engine:hypergolic", "Hypergolic (storable)"),
    ("engine:cryo", "Cryogenic (hydrolox / methalox)"),
    ("engine:other", "Other (nuclear, electric, exotic, jets)"),
]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _rng(vals, fmt="%g"):
    vals = [v for v in vals if v is not None]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    return (fmt % lo) if lo == hi else f"{fmt % lo}-{fmt % hi}"


def write_doc(rows, missing, engines, n_rp1, n_ro):
    # group config rows by part (preserve per-part config list)
    by_part = {}
    for r in rows:
        by_part.setdefault(r["part"], []).append(r)

    n_engines = len(by_part)
    n_configs = len(rows)
    out = []
    W = out.append

    W("# RP-AXE — Engine & Booster Stats + Upgrade Paths (RP-1 reference)\n")
    W("Lookup reference for **every curated engine and booster** (part-capabilities "
      "`disc = engine:*`): each part's RealFuels config variants, the RP-1 tech node "
      "that unlocks each, and its key stats. A RealFuels engine part carries one "
      "`ModuleEngineConfigs` with many selectable **`CONFIG`s**; each better CONFIG is "
      "gated behind an RP-1 tech node via an `RFUpgrade_<config>` PARTUPGRADE — so the "
      "**ordered set of a part's CONFIGs *is* its upgrade path**. See "
      "[UPGRADES.md](UPGRADES.md) for how those PARTUPGRADEs are curated.\n")
    W(f"- **Coverage:** {n_engines} / {len(engines)} curated engine/booster parts, "
      f"{n_configs} config variants. "
      f"{n_rp1} from the RP-1 reference (with tech placement), "
      f"{n_ro} RO-only (stats but **no** RP-1 tech node — RP-1 doesn't ship them). "
      f"{len(missing)} airbreathing/hybrid parts have no RealFuels config path "
      f"(listed at the end).")
    W("- **Full detail (greppable):** [`manifest/engine-stats.tsv`]"
      "(../manifest/engine-stats.tsv) — one row per (part, config), all fields below "
      "plus reliability, ullage, pressureFed, ignitions, rated burn time, mass mult.")
    W("- **Source:** `ksp_rp1_expanded/GameData/ModuleManager.ConfigCache` (RO engines "
      "with RP-1's `Tree/TREE-Engines.cfg` `techRequired`/`cost` placement baked in); "
      "tech-node titles + era ordering from `RP-1/Tree/RP0TechTree.cfg` (`pos.x`).")
    W("- **Reproduce:** `python RP-AXE/tools/extract_engine_stats.py` "
      "(regenerates the TSV and this doc).\n")
    W("**Reading the tables.** *Variants* = number of CONFIGs. *Tech span* = tech node "
      "of the earliest CONFIG → the latest (the length of the upgrade path). *Thrust* = "
      "vacuum `maxThrust` kN across variants. *IspVac* is in **seconds** for curve-mode "
      "engines; small RCS/OMS/cold-gas thrusters use RealFuels' tech-level system where "
      "Isp is a *fraction* of a per-type ceiling (marked `†TL-frac` — see the TSV "
      "`ispMode` column), and airbreathing jets defined via `ModuleEngineConfigs` have "
      "no rocket Isp (thrust only). `‡` marks the RO-only parts.\n")

    # summary counts
    W("## Engine count by type\n")
    W("| Type | Engines | Config variants |")
    W("|---|---:|---:|")
    for disc, label in DISC_ORDER:
        parts = [p for p, rs in by_part.items() if rs[0]["disc"] == disc]
        ncfg = sum(len(by_part[p]) for p in parts)
        if parts:
            W(f"| {label} | {len(parts)} | {ncfg} |")
    W(f"| **Total** | **{n_engines}** | **{n_configs}** |\n")

    # longest upgrade paths (orientation)
    longest = sorted(by_part.items(), key=lambda kv: -len(kv[1]))[:12]
    W("## Longest upgrade paths\n")
    W("| Part | Title | Variants | Tech span |")
    W("|---|---|---:|---|")
    for p, rs in longest:
        rs_sorted = sorted(rs, key=lambda r: _f(r["era_x"]) or 1e9)
        span = _span(rs_sorted)
        W(f"| `{p}` | {rs[0]['title']} | {len(rs)} | {span} |")
    W("")

    # per-type index tables
    for disc, label in DISC_ORDER:
        parts = sorted([p for p, rs in by_part.items() if rs[0]["disc"] == disc],
                       key=lambda p: (min((_f(r["era_x"]) or 1e9) for r in by_part[p]), p))
        if not parts:
            continue
        W(f"## {label} — {len(parts)} parts\n")
        W("| Part | Title | Var | Base config | Tech span | Thrust kN (vac) | "
          "IspVac | Propellants |")
        W("|---|---|---:|---|---|---|---|---|")
        for p in parts:
            rs = sorted(by_part[p], key=lambda r: _f(r["era_x"]) or 1e9)
            title = rs[0]["title"]
            src = " ‡" if rs[0].get("source") == "ro_expanded" else ""
            base = next((r["config"] for r in rs if r["is_base"] in ("base", "single")),
                        rs[0]["config"])
            span = _span(rs)
            thrust = _rng([_f(r["maxThrust_kN"]) for r in rs])
            curve = [r for r in rs if r["ispMode"] == "curve"]
            tl = [r for r in rs if r["ispMode"] == "TL-frac"]
            if curve:
                isp = _rng([_f(r["ispVac"]) for r in curve])
                if tl:
                    isp += " †TL-frac"
            elif tl:
                isp = _rng([_f(r["ispVac"]) for r in tl]) + " †TL-frac"
            else:
                isp = "— (airbreathing)"
            props_set = []
            for r in rs:
                if r["propellants"] and r["propellants"] not in props_set:
                    props_set.append(r["propellants"])
            propcell = " · ".join(props_set[:4]) + (" …" if len(props_set) > 4 else "")
            W(f"| `{p}`{src} | {title} | {len(rs)} | `{base}` | {span} | {thrust} | "
              f"{isp} | {propcell} |")
        W("")

    # trailer: no-config parts
    if missing:
        W("## Airbreathing / hybrid — no RealFuels config path\n")
        W("These curated `engine:*` parts use jet/propeller/ramjet modules (AJE) or are "
          "integrated effect parts, so they have no CONFIG-based upgrade path. Their "
          "stats live in a different module system (thrust vs. mach/altitude curves).\n")
        W("| Part | Type | Engine module |")
        W("|---|---|---|")
        for m in missing:
            reason = NO_CFG.get(m, "absent in RP-1 cache")
            W(f"| `{m}` | {engines[m]} | {reason} |")
        W("")

    with open(OUT_DOC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


def _span(rs_sorted):
    """earliest node title -> latest node title across an era-sorted config list."""
    named = [r for r in rs_sorted if r["node_title"]]
    if not named:
        # fall back to techRequired ids
        ids = [r["techRequired"] for r in rs_sorted if r["techRequired"]]
        if not ids:
            return "—"
        return ids[0] if ids[0] == ids[-1] else f"{ids[0]} → {ids[-1]}"
    a, b = named[0]["node_title"], named[-1]["node_title"]
    return a if a == b else f"{a} → {b}"


if __name__ == "__main__":
    main()
