#!/usr/bin/env python3
"""check_solar_wear.py -- every solar panel AXE ships must actually wear out.

Why: solar degradation is the one property of a panel that no playtest surfaces. Power and mass
are visible in the editor the moment you attach the part; life is invisible until a station has
been up for a year, by which point the save is built on the wrong number. And it fails in the
direction nobody notices -- a panel that never degrades just quietly keeps working.

The mechanism, end to end, because the check only makes sense against it:

  * RO's whole solar model is keyed on a `SolarConfig` node. RO_SolarConfig.cfg selects
    `@PART[*]:HAS[...,@SolarConfig]`; the node's era `level` expands into kwm2/kgm2 and four
    `key*` lines, and those keys are written onto the panel module as its `timeEfficCurve`.
    That curve IS degradation. No SolarConfig node -> no curve -> no wear, ever.
  * Stock ModuleDeployableSolarPanel:136-148 substitutes a flat `{0,1}` curve when the field is
    null and evaluates it in DAYS, so the part runs at 100% forever with no error.
  * Kerbalism's SolarPanelFixer.StockPanel.GetTimeCurve() reads the same MDSP curve and rescales
    it to HOURS; with no curve it falls through to a single-key curve, its `Curve.length > 1`
    test fails, and `wearFactor` pins at 1.0. The PAW's Wear row is only made guiActive when
    wearFactor < 1, so the missing mechanic looks exactly like "no wear yet".
  * RO appends "Solar Panels degrade, affecting the power output over time. Check this effect in
    the PAW." to EVERY part with an MDSP, SolarConfig or not -- so the description of an affected
    part actively asserts the mechanic it does not have.

Nothing in that chain logs anything. This is docs/BUG-CLASSES.md family A with an extra twist:
the string that resolves to nothing is a whole NODE, and its absence is indistinguishable from a
young panel. Found 2026-08-28 on ROC-OrionSolar (16 on a flying station, 44 kW, no wear in 484
days); the sweep behind that one part found 41 of 131 MDSP parts in the cache with no curve, 12
of them curated. The fixes are stanza 7 of design/Parts/AxeUpstreamPartFixes.cfg, and this gate
exists because that stanza depends on a narrow ModuleManager pass window (:AFTER[RealismOverhaul],
between the mod-family `!SolarConfig` deletions and RO's solar pass) which upstream can move at
any time -- silently.

Reads the merged ConfigCache, which is the only place the answer exists: whether a curve survived
every mod's patches is not a question the repo can answer about itself.

Scope limits, stated so they are not mistaken for coverage:
  * Only TOP-LEVEL MODULE nodes are read. B9PartSwitch SUBTYPEs carry `IDENTIFIER { name =
    ModuleDeployableSolarPanel }` blocks that look like panel modules and are not.
  * `ModuleROSolar` is exempt and verified, not assumed: it subclasses MDSP and rebuilds
    `base.timeEfficCurve` from its rung's key1/key20/key80/key99 in ReloadTimeCurve()
    (ROLib.dll, decompiled). Its curve is therefore never in the config and cannot be checked
    here; what CAN be checked is that the rung exists, which tools/check_tech_refs.py covers.
  * Kerbalism's SolarPanelFixer has its own `timeEfficCurve` KSPField (in HOURS, not days) which
    a config could set directly. This gate does NOT accept that as a fix, because Kerbalism only
    honours it when a private, non-serialized `prefabDefinesTimeEfficCurve` is true -- set solely
    in the LOADING scene, so whether it survives cloning to a part instance is not something a
    config can guarantee. If that route is ever proven in flight, accept it here.
  * A curve is judged present, not correct. The reported "-20% at N d" is printed so the rung can
    be eyeballed against the part's node; nothing here asserts the rung is the right one.

Usage:
  python tools/check_solar_wear.py                       # uses the default instance below
  python tools/check_solar_wear.py --cache <ConfigCache>
  python tools/check_solar_wear.py --all                 # report uncurated parts too
"""
import argparse, os, re, sys, time

DEFAULT_CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"
DEFAULT_CURATED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "manifest", "curated-parts.tsv")
AXE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "GameData", "RP-AXE")

# Modules that produce EC from sunlight and are expected to carry a config-visible time curve.
SOLAR_MODULES = ("ModuleDeployableSolarPanel", "ModuleCurvedSolarPanel")

# Modules that build their curve at runtime, with the code path that does it. Verified by
# decompile, not inferred from the name -- an exemption taken on faith is the family-C failure
# this file is meant to be an instance of catching, not committing.
RUNTIME_CURVE = {
    "ModuleROSolar": "ROLib ModuleROSolar.ReloadTimeCurve() rebuilds base.timeEfficCurve from the "
                     "selected ROS_TECH rung's key1/key20/key80/key99",
}

# Parts reviewed and deliberately accepted as un-fixable from config. Add with a dated reason and
# what would change the verdict.
REVIEWED_EXEMPT = {
    "nfs-panel-deploying-curved-375-1":
        "2026-08-28: power comes from NearFutureSolar's ModuleCurvedSolarPanel, not an MDSP, so "
        "there is no timeEfficCurve field for RO's pass to write; Kerbalism binds it to "
        "SolarPanelFixer.NFSCurvedPanel, which does not override GetTimeCurve(). Needs a "
        "Kerbalism-side fix or a different part -- not a config gap.",
}


def parse_parts(cache_text):
    """Yield (part_name, parent_url, part_body) for every PART in the ConfigCache."""
    for block in cache_text.split("\nUrlConfig\n{\n"):
        m = re.match(r"\tparentUrl = (.+)\n\tPART\n\t\{\n", block)
        if not m:
            continue
        body = block[m.end():]
        name = re.search(r"^\t\tname = (.+)$", body, re.M)
        if name:
            yield name.group(1).strip(), m.group(1).strip(), body


def modules(body):
    """(module_name, module_body) for each TOP-LEVEL MODULE node of a part.

    Depth-walked rather than matched by indentation or by `name = Module*` lines: the cache nests
    module templates inside ModuleB9PartSwitch SUBTYPEs, and those carry a real module name in an
    IDENTIFIER node. Counting those as panels would report a part as having four solar modules
    when it has one, and -- worse -- would let a SUBTYPE's curve stand in for the real module's."""
    out, depth, pending, cur, name = [], 0, None, None, None
    for line in body.splitlines():
        st = line.strip()
        if st == "{":
            depth += 1
            if depth == 1 and pending == "MODULE":
                cur, name = [], None      # the module's own brace: opens the body, not part of it
            elif cur is not None:
                cur.append(line)          # a brace INSIDE the module -- timeEfficCurve lives here
            pending = None
        elif st == "}":
            if depth == 1 and cur is not None:
                out.append((name or "?", "\n".join(cur)))
                cur = None
            elif cur is not None:
                cur.append(line)
            depth -= 1
            pending = None
        else:
            if cur is not None:
                cur.append(line)
                if name is None and depth == 1 and st.startswith("name = "):
                    name = st[7:].strip()
            pending = st if st and "=" not in st else None
    return out


def curve_life(module_body):
    """'-20% at N d' for a module's timeEfficCurve, or None if it has none.

    Keys arrive space-separated OR comma-separated -- RO writes levels 0-4 with spaces and 5-7
    with commas in RO_SolarConfig.cfg, and ConfigNode accepts both, so a parser that assumed one
    would silently read half the ladder as unparsable."""
    m = re.search(r"^\s*timeEfficCurve\s*$\n\s*\{\n(.*?)^\s*\}", module_body, re.M | re.S)
    if not m:
        return None
    keys = []
    for raw in re.findall(r"^\s*key = (.+)$", m.group(1), re.M):
        f = [p for p in re.split(r"[,\s]+", raw.strip()) if p]
        try:
            keys.append((float(f[0]), float(f[1])))
        except (IndexError, ValueError):
            continue
    if not keys:
        return "curve present, unparsable keys"
    for t, v in keys:
        if v <= 0.8:
            return "-20%% at %s d" % ("%.0f" % t)
    return "min %.2f at %.0f d" % (min(v for _, v in keys), keys[-1][0])


def stale(cache):
    """Warn if this cache predates the configs it is being asked about. Same reasoning as check 0
    of check_liveness.py: a cache-derived verdict about an edit the cache never saw is worse than
    no verdict. Advisory here (returns a string) -- the findings are still worth printing."""
    instance = os.path.dirname(os.path.dirname(cache))
    log = os.path.join(instance, "KSP.log")
    if not os.path.exists(log):
        return None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from check_liveness import boot_started
        booted = boot_started(log, os.path.getmtime(cache))
    except Exception:
        return None
    newest, newest_f = 0, None
    for dirpath, _, files in os.walk(AXE):
        for fn in files:
            if fn.endswith((".cfg", ".dll")):
                p = os.path.join(dirpath, fn)
                if os.path.getmtime(p) > newest:
                    newest, newest_f = os.path.getmtime(p), p
    if newest > booted:
        return ("STALE: this KSP run started %s, but %s changed after it -- reboot the instance "
                "before believing anything below."
                % (time.strftime("%Y-%m-%d %H:%M", time.localtime(booted)),
                   os.path.relpath(newest_f, AXE)))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--curated", default=DEFAULT_CURATED)
    ap.add_argument("--all", action="store_true", help="report uncurated parts too")
    args = ap.parse_args()

    if not os.path.exists(args.cache):
        print("FATAL: %s not found -- boot the instance once first." % args.cache)
        return 2

    curated = set()
    if os.path.exists(args.curated):
        for line in open(args.curated, encoding="utf-8"):
            col = line.rstrip("\n").split("\t")
            if len(col) > 1:
                curated.add(col[1].strip())

    warn = stale(args.cache)
    cache = open(args.cache, encoding="utf-8", errors="replace").read()

    bad, ok, exempt, runtime, panels = [], [], [], [], 0
    for name, url, body in parse_parts(cache):
        for mod, mbody in modules(body):
            if mod in RUNTIME_CURVE:
                runtime.append((name, mod))
                continue
            if mod not in SOLAR_MODULES:
                continue
            panels += 1
            life = curve_life(mbody)
            row = (name, mod, url, life)
            if name in REVIEWED_EXEMPT:
                exempt.append(row)
            elif life:
                ok.append(row)
            else:
                bad.append(row)

    if warn:
        print("*** %s ***\n" % warn)

    fail = [r for r in bad if r[0] in curated]
    other = [r for r in bad if r[0] not in curated]

    def group(rows):
        """One line per PART, not per module: a part with four panel modules is one defect with
        four instances of it, and listing it four times reads as four parts."""
        seen = {}
        for name, mod, url, _ in rows:
            seen.setdefault(name, [url, mod, 0])[2] += 1
        return sorted(seen.items())

    if fail:
        print("NO WEAR -- curated panel with no degradation curve (runs at 100% forever):")
        for name, (url, mod, n) in group(fail):
            print("  %-32s %s%s" % (name, mod, "  x%d" % n if n > 1 else ""))
            print("      %s" % url)
        print()
    if other and args.all:
        print("NO WEAR -- uncurated (parked / not in the tree), informational:")
        for name, (url, mod, n) in group(other):
            print("  %-32s %s%s" % (name, mod, "  x%d" % n if n > 1 else ""))
        print()
    if exempt:
        print("EXEMPT -- reviewed, cannot be fixed from config:")
        for name, mod, url, _ in exempt:
            print("  %-32s %s" % (name, mod))
            print("      %s" % REVIEWED_EXEMPT[name])
        print()

    if args.all:
        print("WEARS -- curve present (rung shown for eyeballing, not asserted):")
        for name, mod, url, life in sorted(ok):
            tag = "" if name in curated else "   [uncurated]"
            print("  %-32s %-28s %s%s" % (name, life, mod, tag))
        print()

    print("checked %d solar modules across the cache" % panels)
    print("  %d with a curve, %d without (%d curated on %d parts, %d parked), %d exempt, "
          "%d runtime-curved"
          % (len(ok), len(bad), len(fail), len(group(fail)), len(other), len(exempt), len(runtime)))
    if not args.all:
        print("  (curated parts only for the no-wear failure; --all for the rest)")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
