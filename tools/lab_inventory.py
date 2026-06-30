#!/usr/bin/env python3
"""Parse KerbalismLab (fork) + base ScienceRework lab experiments into one inventory.

Canonical output is checked in at manifest/lab-experiments.tsv. To regenerate, clone
the two REFERENCE repos as siblings and point FORK/BASE at them:
  git clone https://github.com/johnabsher/KerbalismLabExperimentsExpandedContinued.git
  git clone https://github.com/Kerbalism/KerbalismScienceOnly.git
FORK = the 65 expansion experiments; BASE = the 6 base lab experiments + LAB_EXPERIMENTS
group settings (LabDataRateMultiplier etc.) that the fork *requires but omits* (see docs/SCIENCE.md).
"""
import re, os, glob, json

FORK = os.environ.get("KLE_FORK", r"C:\git\ksp\KerbalismLabExperimentsExpandedContinued\GameData\KerbalismLabExperimentsExpandedContinued")
BASE = os.environ.get("KLE_BASE", r"C:\git\ksp\KerbalismScienceOnly\GameData\KerbalismScienceOnly\System\ScienceRework\Tweakables\StockGroups-Lab.cfg")

def field(block, key):
    m = re.search(r'(?m)^\s*'+re.escape(key)+r'\s*=\s*(.*?)\s*(?://.*)?$', block)
    return m.group(1).strip() if m else ""

def all_fields(block, key):
    return [m.strip() for m in re.findall(r'(?m)^\s*'+re.escape(key)+r'\s*=\s*(.*?)\s*(?://.*)?$', block)]

def brace_block(text, start):
    """Return substring of balanced {...} beginning at first { after start index."""
    i = text.find('{', start)
    depth, j = 0, i
    while j < len(text):
        if text[j] == '{': depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0: return text[i+1:j], j
        j += 1
    return "", len(text)

rows = []

# ---- fork experiments: one file each ----
for path in sorted(glob.glob(os.path.join(FORK, "*.cfg"))):
    name = os.path.basename(path)
    if name == "InstrumentTagging.cfg": continue
    txt = open(path, encoding="utf-8", errors="ignore").read()
    # KERBALISM_EXPERIMENT block (situation/body scope)
    sit, body_allow, body_not = "", "", ""
    me = re.search(r'KERBALISM_EXPERIMENT', txt)
    if me:
        kb, _ = brace_block(txt, me.end())
        sit = ";".join(all_fields(kb, "Situation"))
        body_allow = field(kb, "BodyAllowed")
        body_not = field(kb, "BodyNotAllowed")
    # LAB_EXPERIMENTS -> the single experiment subnode
    expid = field(txt, "id").replace("kerbalism_", "")
    ml = re.search(r'@LAB_EXPERIMENTS', txt)
    val = unlock = crew = req = dur = ec = size = ""
    if ml:
        lb, _ = brace_block(txt, ml.end())
        # first subnode in lab block
        sm = re.search(r'(\w[\w\-]*)\s*\{', lb)
        if sm:
            sub, _ = brace_block(lb, sm.start())
            val = field(sub, "value"); unlock = field(sub, "UnlockTech")
            crew = field(sub, "CrewRequirement"); req = field(sub, "requirements")
            dur = field(sub, "duration"); ec = field(sub, "ECCost"); size = field(sub, "size")
            subname = sm.group(1)
    rows.append(dict(src="fork", file=name, exp=expid or subname, value=val,
                     situation=sit, body_allowed=body_allow, body_not=body_not,
                     crew=crew, unlock=unlock, req=req, duration=dur, ec=ec, size=size))

# ---- base lab experiments from StockGroups-Lab.cfg (hardcoded scope from comments) ----
BASE_EXP = [
 # name, value, situation-scope (from author comments), crew, unlock, req
 ("CHILLED", 24, "Space+Srf, no biomes",   "Scientist",   "advExploration",   "Greenhouse"),
 ("RELAX",   28, "SrfLanded@Biomes (+Kerbin)","Scientist:2","fieldScience",    ""),
 ("JAMMED",  30, "InSpaceLow, no biomes",  "True",        "scienceTech",      "Shadow"),
 ("TRAPPED", 38, "SrfLanded, no biomes",   "True",        "heavyLanding",     ""),
 ("SALINE",  27, "SrfSplashed@Biomes",     "Scientist:4", "fieldScience",     "AltitudeMax:-50"),
 ("BIRDIE",  14, "Flying@Biomes",          "Scientist:1", "highAltitudeFlight",""),
]
for nm,val,sit,crew,unlock,req in BASE_EXP:
    rows.append(dict(src="base", file="StockGroups-Lab.cfg", exp=nm, value=str(val),
                     situation=sit, body_allowed="", body_not="", crew=crew,
                     unlock=unlock, req=req, duration="", ec="", size=""))

# ---- output ----
def num(x):
    try: return float(x)
    except: return 0.0

print(f"{'EXP':<22}{'src':<5}{'value':>6}  {'situation':<26}{'crew':<14}{'unlock':<20}{'req'}")
print("-"*120)
for r in sorted(rows, key=lambda r:(-num(r['value']))):
    print(f"{r['exp']:<22}{r['src']:<5}{r['value']:>6}  {r['situation'][:25]:<26}{r['crew'][:13]:<14}{r['unlock'][:19]:<20}{r['req']}")

vals = [num(r['value']) for r in rows if num(r['value'])>0]
print("\n=== TOTALS ===")
print(f"experiments with a value: {len(vals)}  (fork={sum(1 for r in rows if r['src']=='fork')}, base={sum(1 for r in rows if r['src']=='base')})")
print(f"raw value sum            : {sum(vals):,.0f}")
print(f"min / median / max value : {min(vals):.0f} / {sorted(vals)[len(vals)//2]:.0f} / {max(vals):.0f}")

# situation scope buckets
from collections import Counter
def scope(s):
    s=s.lower()
    if "bodyglobal" in s: return "BodyGlobal (1/body)"
    if "@biomes" in s: return "situational+biomes"
    if s.startswith("space") or s=="space": return "Space (1/body/sit)"
    if "surface" in s: return "Surface"
    if "flying" in s: return "Flying"
    if "inspace" in s: return "InSpace specific"
    if "srf" in s: return "Srf specific"
    if "stock" in s: return "stock/base"
    return s[:24] or "(none)"
sc = Counter(scope(r['situation']) for r in rows if num(r['value'])>0)
scv = Counter()
for r in rows:
    if num(r['value'])>0: scv[scope(r['situation'])] += num(r['value'])
print("\nsituation-scope buckets (count | sum-of-values):")
for k,v in sc.most_common(): print(f"  {k:<26}{v:>3}  | {scv[k]:>6,.0f}")

# crewed-lab cross-body budget estimate (FIXED-VALUE model, no body science multiplier)
RSS_BODIES = 32            # bodies in the audit model
REALISTIC_BODIES = 8       # bodies a player realistically crews (Earth/Moon/Mars/Venus/4 moons)
AVG_BIOMES = 6             # avg biomes actually sampled where biome experiments apply
biome_sum  = sum(num(r['value']) for r in rows if "biome" in r['situation'].lower())
flat_sum   = sum(num(r['value']) for r in rows if num(r['value'])>0 and "biome" not in r['situation'].lower())
print(f"\n=== crewed-lab CROSS-BODY budget (fixed-value model, no body multiplier) ===")
print(f"flat (non-biome) value sum : {flat_sum:,.0f}   biome value sum: {biome_sum:,.0f}")
print(f"per-body run-set (face)    : {flat_sum+biome_sum:,.0f}  (one station/base, 1 biome)")
print(f"realistic ~{REALISTIC_BODIES} bodies        : {REALISTIC_BODIES*flat_sum + REALISTIC_BODIES*AVG_BIOMES*biome_sum:,.0f}  (flat x{REALISTIC_BODIES} + biome x{REALISTIC_BODIES}x{AVG_BIOMES})")
print(f"theoretical {RSS_BODIES} bodies       : {RSS_BODIES*flat_sum + RSS_BODIES*AVG_BIOMES*biome_sum:,.0f}")

# unlock tech histogram
ut = Counter(r['unlock'] for r in rows if r['unlock'])
print("\nUnlockTech distribution (stock node names -> must remap to AXE):")
for k,v in ut.most_common(): print(f"  {k:<24}{v}")

print("\n[canonical artifact: manifest/lab-experiments.tsv]")
