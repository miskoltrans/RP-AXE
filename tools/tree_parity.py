#!/usr/bin/env python3
"""Tech-tree parity audit (RP-AXE vs RP-1).

RP-AXE's tech tree must be 1:1 with RP-1 -- the ONLY deliberate deltas are the start node and the
orphan/debug browser nodes. Tree placement is 100% config-driven (RP0.dll never moves parts between
nodes at runtime), so RP-AXE can reproduce RP-1's tree entirely in config; this tool checks that it does.

Reference (where RP-1 INTENDS each part): RP-1's tree source data
  RP-1/Source/Tech Tree/Parts Browser/data/*.json   (name -> technology; the authoritative per-mod map)
  cross-checked against original_sheet_data/PartsSheet.csv (the generator's master sheet).
Actual (where the part ENDS UP in RP-AXE): the fully MM-merged ModuleManager.ConfigCache
  (name -> TechRequired) from the deployed Instance.

We bucket every part present in both maps:
  match        actual == reference (parity OK)
  start        reference is start-tier (start/unlockParts) and actual is start -- the deliberate merge
  axe-debug    actual is an RP-AXE orphan/debug/sack node (orphanParts / axeBrowse* / axeNonRO / pads)
  rp1-hidden   actual == ORPHANS (RP-1's own hide; matches RP-1 shipped intent)
  STRANDED     actual == start but RP-1 wants a REAL gated node -> generator-gap victim, PATCH THESE
  DIVERGENT    actual and reference are different real nodes -> investigate (design move or data drift)
  added        in the cache but not in RP-1's data (RP-AXE-added mod part) -- not a divergence

STRANDED is the actionable bucket (proceduralSRBRealFuels is the known one): fix each in
design/Tree/AxeTreeParity.cfg with `@PART[x]:FINAL { %TechRequired = <reference> }`.

Usage:
  python tools/tree_parity.py [path-to-ConfigCache] [--rp1 PATH] [--all] [--dump out.txt]

Default cache: ../Instance/GameData/ModuleManager.ConfigCache ; default RP-1: ../../RP-1
"""
import sys, os, json, csv, glob, collections

# start-tier nodes RP-AXE merges (StartParts.cfg: unlockParts -> start)
START = {"start", "unlockParts"}
# RP-AXE custom orphan/debug/sack + recreated launch-pad nodes (AxeLaunchPads.cfg)
AXE_PAD = {"generalLaunchPad", "launchStands", "launchPlates",
           "soyuzLaunchBase", "saturnLaunchPad", "shuttleLaunchPad"}

def repo_root():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

def default_cache():
    return os.path.normpath(os.path.join(repo_root(), "..", "Instance",
                                         "GameData", "ModuleManager.ConfigCache"))

def default_rp1():
    return os.path.normpath(os.path.join(repo_root(), "..", "RP-1"))

# ---- reference: RP-1 intended node per part ------------------------------------

def _walk_json(obj, out):
    """Collect name->technology from any nested dict carrying both keys."""
    if isinstance(obj, dict):
        if "name" in obj and "technology" in obj:
            n = (obj["name"] or "").strip()
            t = (obj["technology"] or "").strip()
            if n and t:
                out[n] = t
        for v in obj.values():
            _walk_json(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_json(v, out)

def load_reference(rp1):
    base = os.path.join(rp1, "Source", "Tech Tree", "Parts Browser")
    ref = {}
    files = glob.glob(os.path.join(base, "data", "*.json"))
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                _walk_json(json.load(f), ref)
        except Exception as e:
            print(f"  warn: failed to parse {os.path.basename(fp)}: {e}", file=sys.stderr)
    # cross-check / supplement from the master CSV (csv handles the quoted-comma desc field)
    csv_path = os.path.join(base, "original_sheet_data", "PartsSheet.csv")
    disagree = 0
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.reader(f):
                if len(row) < 10:
                    continue
                n, tech = row[0].strip(), row[9].strip()
                if not n or not tech or n == "name":
                    continue
                if n in ref and ref[n] != tech:
                    disagree += 1
                elif n not in ref:
                    ref[n] = tech
    return ref, len(files), disagree

# ---- actual: part -> TechRequired from the merged cache ------------------------

def load_actual(cache):
    with open(cache, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    n = len(lines); out = {}; i = 0
    while i < n:
        s = lines[i].strip()
        if s == "PART" or s.startswith("PART "):
            j = i + 1
            while j < n and lines[j].strip() != "{":
                j += 1
            depth = 0; started = False; pname = None; tech = None; k = j
            while k < n:
                t = lines[k].strip()
                if t == "{":
                    depth += 1; started = True
                elif t == "}":
                    depth -= 1
                    if started and depth == 0:
                        break
                elif depth == 1:  # only the PART's own fields, not nested MODULE{}
                    if pname is None and t.startswith("name") and "=" in t:
                        pname = t.split("=", 1)[1].strip()
                    elif t.startswith("TechRequired") and "=" in t:
                        tech = t.split("=", 1)[1].strip()
                k += 1
            if pname:
                out[pname] = tech or "start"   # KSP default when unset is 'start'
            i = k
        i += 1
    return out

# ---- classify -----------------------------------------------------------------

def classify(ref, act):
    if act == ref:
        return "match"
    if ref in START and act in START:
        return "start"
    if ref in START and act == "start":
        return "start"
    if act.startswith("axeBrowse") or act in ("orphanParts", "axeNonRO", "axeBrowseHub") or act in AXE_PAD:
        return "axe-debug"
    if act == "ORPHANS":
        return "rp1-hidden"
    if act in START and ref not in START:
        return "STRANDED"   # fell to native start but RP-1 wants a real/hidden node
    return "DIVERGENT"

def main(argv):
    cache = default_cache(); rp1 = default_rp1(); show_all = False; dump = None
    a = argv[1:]
    while a:
        x = a.pop(0)
        if x == "--rp1": rp1 = a.pop(0)
        elif x == "--all": show_all = True
        elif x == "--dump": dump = a.pop(0)
        else: cache = x
    if not os.path.exists(cache):
        sys.exit(f"ConfigCache not found: {cache}\n(deploy RP-AXE + run KSP once to regenerate)")

    ref, nfiles, disagree = load_reference(rp1)
    act = load_actual(cache)
    print(f"# tree parity   cache={cache}")
    print(f"#               reference: {len(ref)} parts from {nfiles} RP-1 json (+csv); "
          f"{disagree} json/csv disagreements (json wins)")
    print(f"#               actual:    {len(act)} parts in merged cache\n")

    buckets = collections.defaultdict(list)
    for name, a_node in act.items():
        if name not in ref:
            buckets["added"].append((name, None, a_node)); continue
        buckets[classify(ref[name], a_node)].append((name, ref[name], a_node))

    order = ["match", "start", "axe-debug", "rp1-hidden", "added", "STRANDED", "DIVERGENT"]
    print(f"{'bucket':<12}{'count':>7}")
    print("-" * 19)
    for b in order:
        print(f"{b:<12}{len(buckets[b]):>7}")
    print()

    def show(b, title):
        rows = sorted(buckets[b])
        if not rows: return
        print(f"== {title} ({len(rows)}) ==")
        for name, r, a_node in rows:
            print(f"  {name:<40} rp1={r!s:<22} axe={a_node}")
        print()

    show("STRANDED", "STRANDED -> add to design/Tree/AxeTreeParity.cfg (patch to rp1 node)")
    show("DIVERGENT", "DIVERGENT -> investigate (RP-AXE design move, or json/cache mismatch)")
    if show_all:
        show("axe-debug", "axe-debug (orphan/sack/pad routing)")
        show("rp1-hidden", "rp1-hidden (ORPHANS)")

    if dump:
        with open(dump, "w", encoding="utf-8") as f:
            for b in ("STRANDED", "DIVERGENT"):
                for name, r, a_node in sorted(buckets[b]):
                    f.write(f"{b}\t{name}\t{r}\t{a_node}\n")
        print(f"wrote STRANDED+DIVERGENT -> {dump}")

if __name__ == "__main__":
    main(sys.argv)
