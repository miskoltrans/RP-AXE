#!/usr/bin/env python3
"""
check_liveness.py -- does what RP-AXE *ships* actually bind to anything in the *running* game?

Every check here covers the same failure shape, the one that keeps producing playtest bugs:
a config that is authored, reviewed and documented, references something by STRING, and the
string resolves to nothing. ModuleManager merges it, KSP loads it, no error is raised, and the
only symptom is an absence -- a node that grants no part, an experiment that never runs, a
setting that never applies. See docs/BUG-CLASSES.md for the taxonomy this implements.

Nothing here can be answered from the repo alone: the question is always "what survived the
merge and the load", so this needs a real instance that has booted at least once.

  python tools/check_liveness.py                          # defaults to ../Instance
  python tools/check_liveness.py --instance <ksp-root>

Checks
  0  staleness             -- is the boot we are judging older than the configs we are judging?
  A  empty / thinned tree nodes  -- a placed part that no longer exists in the loaded game
  B  phantom part modules       -- MODULE{name=X} we add where no assembly defines X
  C  inert config nodes         -- a top-level NODE we ship that no assembly ever reads
  T  dangling tech gates        -- check_tech_refs.py in --cache mode, folded in so one command
                                   covers the whole family
  D  dead patch targets         -- @PART[x] we patch where x matched nothing (report only)
  E  effect assertions          -- did the VALUE a generator emitted actually reach the game?
                                   Every check above asks whether a string RESOLVES; this asks
                                   whether the NUMBER LANDED, which is how a cost patch can bind
                                   to nothing and change nothing while every other gate passes.

Exit code is non-zero if 0, A, B, C, T or E found anything. D is advisory: RP-AXE deliberately
carries RP-1's patches for optional mods (FASA, SSTU, ALCOR...) that this install does not have.

Check 0 exists because every other verdict here is a lie without it. The cache and the log are
snapshots of one boot; edit a config afterwards and this tool cheerfully re-reports the old
world. That is the same shape as the family-C failures in docs/BUG-CLASSES.md -- a check that
could not have caught the thing it was pointed at.
"""
import argparse, glob, os, re, sys, time
from collections import defaultdict

import check_tech_refs

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AXE = os.path.join(REPO, "GameData", "RP-AXE")
NODES_YAML = os.path.join(REPO, "tree", "nodes.yaml")

# Top-level nodes that legitimately have no runtime reader: ModuleManager resolves them at
# PATCH time (`#$@NODE/path$` value references) or they exist only to carry a :FOR[] tag.
PATCH_TIME_ONLY = {
    "KERBALISM_GROUP_SETTINGS",   # #$@KERBALISM_GROUP_SETTINGS/LAB_EXPERIMENTS/...$
    "KERBALISM_HDD_SIZES",        # #$@KERBALISM_HDD_SIZES/<probe>/data$
    "RPAXE_REMOVAL_FLAGS",        # exists only to carry :FOR[HardRemoveNonRO]
}
# Tree nodes that are SUPPOSED to grant no parts: pure progression gates, where the shape of the
# tree is the whole contribution. Keep this list short and say why -- an empty node is normally a
# defect, and the only thing separating "deliberate" from "its part silently vanished" is this file.
INTENTIONALLY_EMPTY = {
    "mic_atmoSounding": "roots the Microelectronics science lane (mic_massSpec + mic_magnetometer); "
                        "its only part granted two experiments already available at start",
}
# Top-level config nodes AXE ships that NO assembly reads, and that we are keeping anyway. Same
# contract as INTENTIONALLY_EMPTY and as check_settings_parity's DISPOSITIONS: an inert node is
# normally a defect (bug family A1 -- a file that looks authored and does nothing), so each entry
# has to say why it stays. Anything NOT listed here fails the gate.
INERT_BY_DESIGN = {
    "AVIONICSCONFIGS": "RP-1's ModuleProceduralAvionics coefficient table, vendored with "
                       "seed/Parts/_RP-AXE-extra/ProceduralAvionics.cfg. Its reader is RP0.dll, "
                       "which AXE does not ship, and AXE's own ModuleAxeAvionics TIER ladder "
                       "(design/Tree/AxeAvionicsCore.cfg) supersedes it. KEPT as the implementation "
                       "reference the avionics port is checked against -- docs/UPGRADES.md C1, "
                       "docs/AVIONICS_COMPARISON.md. Deleting it would need a partial-file strip in "
                       "sync-seed.ps1 (the block is 893 lines inside a file whose other stanzas are "
                       "live), which is not worth building for one dead node.",
}

# Node names KSP/other mods define; we only audit the ones RP-AXE actually ships.
STOCK_NODES = {
    "PART", "PARTUPGRADE", "RESOURCE_DEFINITION", "EXPERIMENT_DEFINITION", "PARAMETER",
    "REQUIREMENT", "SUBCATEGORY", "CONTRACT_TYPE", "CONTRACT_GROUP", "TANK_DEFINITION",
}


# ---------------------------------------------------------------- ground truth from the instance

def live_parts(cache):
    """Part names that survived ModuleManager patching."""
    live, depth, part_at, pending = set(), 0, None, False
    for line in open(cache, encoding="utf-8", errors="replace"):
        s = line.strip()
        if s == "PART":
            pending = True
            continue
        if pending and s == "{":
            part_at, pending = depth + 1, False
        if s == "{":
            depth += 1
        elif s == "}":
            if part_at is not None and depth == part_at:
                part_at = None
            depth -= 1
        elif part_at is not None and depth == part_at and s.startswith("name = "):
            live.add(s[7:].strip())
            part_at = None            # the part's own name is the first one in the block
    return live


def load_failures(log):
    """(parts that failed to COMPILE, module typenames KSP could not resolve).

    Attribute failures only while inside a `Compiling Part` -- KSP interleaves
    `Compiling Internal Prop`, and props fail constantly on missing ASET/BDB assets."""
    failed, modules, cur, kind = set(), set(), None, None
    for line in open(log, encoding="utf-8", errors="replace"):
        m = re.search(r"PartLoader: Compiling (Part|Internal Prop|Internal Space|Part Upgrade) '([^']+)'", line)
        if m:
            kind, cur = m.group(1), m.group(2).split("/")[-1]
            continue
        if kind == "Part" and cur and (
                "PartCompiler: Cannot compile part" in line
                or "PartCompiler: Model was not compiled correctly" in line):
            failed.add(cur)
        m = re.search(r"Cannot find a PartModule of typename '([^']+)'", line)
        if m:
            modules.add(m.group(1))
    return failed, modules


def usable_parts(cache, log):
    live = live_parts(cache)
    failed, missing_modules = load_failures(log)
    # the log url mangles '.' to '_'
    by_url = {n.replace(".", "_"): n for n in live}
    dead = {by_url[f] for f in failed if f in by_url}
    return live, live - dead, dead, missing_modules


# ---------------------------------------------------------------- what RP-AXE ships

def axe_cfgs():
    for dirpath, _, files in os.walk(AXE):
        for fn in files:
            if fn.endswith(".cfg"):
                yield os.path.join(dirpath, fn)


def rel(p):
    return p.replace(REPO + os.sep, "").replace(os.sep, "/")


def tree_nodes():
    """[(id, title, [parts])] straight out of tree/nodes.yaml (flow-style `parts:` lists)."""
    txt = open(NODES_YAML, encoding="utf-8").read()
    out = []
    for nid, body in re.findall(r"^  - id: (\S+)(.*?)(?=^  - id: |\Z)", txt, re.S | re.M):
        pm = re.search(r"^\s*parts:\s*\[(.*?)\]", body, re.S | re.M)
        if not pm:
            continue
        tm = re.search(r'^\s*title:\s*"?([^"\n]*)', body, re.M)
        parts = [p.strip() for p in pm.group(1).replace("\n", " ").split(",") if p.strip()]
        out.append((nid, (tm.group(1).strip() if tm else ""), parts))
    return out


def added_modules():
    """{module name: [(file, line)]} for every MODULE{name=X} an RP-AXE cfg adds."""
    hits = defaultdict(list)
    for p in axe_cfgs():
        lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
        for i, line in enumerate(lines):
            if line.lstrip().startswith("//"):
                continue
            if re.match(r"\s*[-!@]?MODULE\b", line) and not line.lstrip().startswith(("@", "-", "!")):
                # name may be on this line (inline block) or the next few
                blob = " ".join(lines[i:i + 4])
                m = re.search(r"name\s*=\s*([A-Za-z_][\w.]*)", blob)
                if m:
                    hits[m.group(1)].append((rel(p), i + 1))
    return hits


def patch_targets():
    """{part name: [(file, line)]} for every literal @PART[x] target RP-AXE patches."""
    hits = defaultdict(list)
    pat = re.compile(r"[@+\-!]PART\[([^\]]+)\]")
    for p in axe_cfgs():
        for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            if line.lstrip().startswith("//"):
                continue
            for m in pat.finditer(line):
                for name in m.group(1).split("|"):
                    name = name.strip()
                    if name and "*" not in name and "?" not in name:
                        hits[name].append((rel(p), i))
    return hits


def shipped_top_nodes():
    """{NODE_NAME: [(file, line)]} for custom top-level nodes RP-AXE ships."""
    hits = defaultdict(list)
    pat = re.compile(r"^([A-Z][A-Z0-9_]{3,})\s*(?:\{|$)")
    for p in axe_cfgs():
        for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            m = pat.match(line)
            if m and m.group(1) not in STOCK_NODES:
                hits[m.group(1)].append((rel(p), i))
    return hits


def assemblies(instance):
    """Every DLL the game can load. The Instance/GameData/RP-AXE junction is NOT followed by
    os.walk on Windows, so the repo's own Plugins dir is added explicitly -- skipping it is
    what has produced false 'DEAD' verdicts before."""
    roots = [os.path.join(instance, "GameData"),
             os.path.join(instance, "KSP_x64_Data", "Managed"),
             os.path.join(AXE, "Plugins")]
    out = []
    for r in roots:
        for ext in ("dll", "kbin"):     # Kerbalism ships its assemblies as *.kbin
            out += glob.glob(os.path.join(r, "**", f"*.{ext}"), recursive=True)
    return sorted({os.path.realpath(d) for d in out})


def name_in_assemblies(names, dlls):
    """{name: [assembly, ...]}. A string literal lives in the #US heap as UTF-16, which may sit
    at an ODD byte offset -- both alignments must be checked or live names read as dead."""
    found = defaultdict(list)
    probes = {n: (n.encode("ascii", "ignore"), n.encode("utf-16-le")) for n in names}
    for d in dlls:
        try:
            b = open(d, "rb").read()
        except OSError:
            continue
        for n, (a, u) in probes.items():
            if a in b or u in b:
                found[n].append(os.path.basename(d))
    return found


def boot_started(log, fallback):
    """Wall-clock time this KSP run began, from the first timestamp KSP wrote to its log.

    KSP stamps `[LOG HH:MM:SS.mmm]` with no date, so anchor it to the log file's own date. If the
    result lands in the future relative to that date (a run that crossed midnight), step back a day.
    Falls back to the caller's value if the log has no parsable stamp."""
    import datetime
    with open(log, encoding="utf-8", errors="replace") as f:
        for _ in range(200):
            line = f.readline()
            if not line:
                break
            m = re.match(r"\[(?:LOG|WRN|ERR|EXC) (\d{2}):(\d{2}):(\d{2})", line)
            if m:
                end = datetime.datetime.fromtimestamp(os.path.getmtime(log))
                started = end.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                                      second=int(m.group(3)), microsecond=0)
                if started > end:
                    started -= datetime.timedelta(days=1)
                return started.timestamp()
    return fallback


# ---------------------------------------------------------------- checks

GEN_ONELINE = re.compile(r"@PART\[([^\]*?]+)\][^{]*\{\s*%(\w+)\s*=\s*([-\d.]+)\s*\}")

def generated_intent():
    """{generated file -> {part -> {key: value}}} — what our emitters MEANT to set."""
    out = {}
    for fn, key in (("AxePartCost.cfg", "entryCost"), ("AxePartFlyCost.cfg", "cost")):
        p = os.path.join(AXE, "design", "Tree", fn)
        if not os.path.exists(p):
            continue
        want = {}
        for ln in open(p, encoding="utf-8", errors="replace"):
            m = GEN_ONELINE.match(ln.strip())
            if m and m.group(2) == key:
                want[m.group(1)] = (key, float(m.group(3)))
        if want:
            out[fn] = want
    return out

def cache_part_fields(cache, keys):
    """part -> {key: value}, reading each PART node's OWN fields only (never its modules')."""
    out, cur, depth, part_depth, pending = {}, None, 0, None, False
    for raw in open(cache, encoding="utf-8", errors="replace"):
        s = raw.strip()
        if s == "PART":
            pending = True; continue
        if s == "{":
            depth += 1
            if pending:
                part_depth, cur, pending = depth, {}, False
            continue
        if s == "}":
            if cur is not None and depth == part_depth:
                if "name" in cur:
                    out[cur["name"]] = cur
                cur, part_depth = None, None
            depth -= 1
            continue
        if cur is not None and depth == part_depth and "=" in s:
            k, v = s.split("=", 1)
            k = k.strip()
            if k == "name" or k in keys:
                cur[k] = v.strip()
    return out

def check_effects(cache):
    """Check E — did the VALUE a generator emitted actually reach the running game?

    Every other check here asks whether a string RESOLVES. None asks whether the NUMBER LANDED, and
    that gap is how AxeProcCostScale's avionics patch shipped binding to nothing: the config was
    valid, ModuleManager applied it, and not one value changed (docs/ECONOMY.md §14).

    Judged PER FILE, because the two failure modes need opposite verdicts:
      * a few parts mismatching  = something later (:AFTER / :FINAL, another mod) legitimately won.
        Real and worth seeing -- RTG costs, ROH-AdjustableHS, the US shrouds -- but not our bug.
      * MOST of a file mismatching = the patch never applied at all. That is the bug this exists for.
    So a low match rate FAILS and scattered mismatches are advisory. Measured 2026-07-30: 3,641 of
    3,685 values land, i.e. the honest baseline is ~98.8%, not 100%.
    """
    intent = generated_intent()
    if not intent:
        print("E  effect assertions: SKIP (no generated cost files found)")
        return 0, []
    keys = {k for f in intent.values() for (k, _) in f.values()}
    live = cache_part_fields(cache, keys)
    fail, notes = 0, []
    for fn, want in sorted(intent.items()):
        ok = absent = bad = 0
        examples = []
        for part, (key, val) in want.items():
            got = live.get(part)
            if got is None or key not in got:
                absent += 1
                continue
            if abs(float(got[key]) - val) > max(0.01, abs(val) * 0.001):
                bad += 1
                if len(examples) < 5:
                    examples.append(f"{part} {key} want {val:,.0f} got {got[key]}")
            else:
                ok += 1
        seen = ok + bad
        rate = (ok / seen * 100) if seen else 0.0
        verdict = "OK" if rate >= 90 else "FAILED -- this patch is not reaching the game"
        print(f"E  {fn}: {ok:,}/{seen:,} values landed ({rate:.1f}%), {absent} part(s) not loaded  {verdict}")
        for e in examples:
            print(f"     overridden downstream: {e}")
        if rate < 90:
            fail = 1
            notes.append(fn)
    return fail, notes

FACILITY_SECTION = {              # Contract Configurator's facility name -> CustomBarnKit's section
    "AstronautComplex": "ASTRONAUTS",
    "ResearchAndDevelopment": "RESEARCH",
    "MissionControl": "MISSION",
    "TrackingStation": "TRACKING",
    "LaunchPad": "LAUNCHPAD",
    "Runway": "RUNWAY",
    "VehicleAssemblyBuilding": "VAB",
    "SpaceplaneHangar": "SPH",
    "Administration": "ADMINISTRATION",
}


def check_facility_gates(cache):
    """Check F — a contract that asks for a facility level the building cannot reach.

    RP-1's contracts are written against RP-1's CustomBarnKit ladders, and AXE re-authored only
    some of those sections. Where it did not, the building silently runs at CustomBarnKit's default
    length, and any vendored `minLevel` above that becomes unsatisfiable. It fails the same way a
    dangling tech id does -- CLOSED, and silently: the requirement is never met, so the contract is
    never OFFERED, so there is nothing in the log and nothing in the contract list to notice.

    Found 2026-08-13 on first_EVA, which asks AstronautComplex minLevel = 4. RP-1 gives that
    building `levels = 5` (and `unlockedEVA = 4`, which is what the requirement was restating);
    AXE never re-authored the section, so it runs at CustomBarnKit's default `levels = 3` and the
    contract could never appear. The same sweep clears the ten TrackingStation gates, which reach
    minLevel 7 against an 11-rung DSN ladder.

    Reads both sides from the merged cache, so it stays true if either the ladders or the contracts
    change. A facility whose section is absent from the cache is reported as UNKNOWN rather than
    assumed fine -- not knowing the cap is not the same as the cap being high enough.
    """
    text = open(cache, encoding="utf-8", errors="replace").read()
    caps = {}
    for fac, section in FACILITY_SECTION.items():
        m = re.search(r"\n\t+%s\n\t+\{" % section, text)
        if not m:
            continue
        lv = re.search(r"\n\s*levels = (\d+)", text[m.end():m.end() + 900])
        if lv:
            caps[fac] = int(lv.group(1))

    bad, unknown, checked = [], [], 0
    for blk in text.split("\nUrlConfig\n{\n"):
        m = re.match(r"\tparentUrl = (.+)\n\tCONTRACT_TYPE\n", blk)
        if not m:
            continue
        nm = re.search(r"\n\t\tname = (.+)", blk)
        name = nm.group(1).strip() if nm else "?"
        for fm in re.finditer(r"type = Facility\n((?:\s+\w+ = .*\n)+)", blk):
            fac = re.search(r"facility = (\w+)", fm.group(1))
            mn = re.search(r"minLevel = (\d+)", fm.group(1))
            if not fac or not mn:
                continue
            checked += 1
            f, want = fac.group(1), int(mn.group(1))
            if f not in caps:
                unknown.append((name, f, want))
            elif want > caps[f]:
                bad.append((name, f, want, caps[f], m.group(1)))

    print(f"=== F. contract facility gates above the building's ladder ({len(bad)} of {checked}) ===")
    for name, f, want, cap, url in bad:
        print(f"  UNREACHABLE  {name}: {f} minLevel={want} but the ladder is {cap} rung(s)")
        print(f"      {url}")
    for name, f, want in unknown:
        print(f"  UNKNOWN      {name}: {f} minLevel={want} -- no CustomBarnKit section in the cache")
    if not bad and not unknown:
        print(f"  all {checked} facility gate(s) are reachable")
    return (1 if bad else 0), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", default=os.path.join(os.path.dirname(REPO), "Instance"),
                    help="KSP install root (default: ../Instance)")
    args = ap.parse_args()

    cache = os.path.join(args.instance, "GameData", "ModuleManager.ConfigCache")
    log = os.path.join(args.instance, "KSP.log")
    for f in (cache, log):
        if not os.path.exists(f):
            print(f"FATAL: {f} not found -- boot the instance once first.")
            return 2
    print(f"instance: {args.instance}")
    fail = 0

    # ---- 0: is this boot new enough to judge the current configs? ---------------------------
    # The question is "did the run that produced this cache READ this config", and the honest
    # reference point is when the boot STARTED, not when it finished.
    #
    # Two wrong answers were tried first, both of which this check exists to prevent:
    #   - KSP.log mtime: a running KSP writes continuously, so it is always "now" and calls
    #     everything fresh.
    #   - ConfigCache mtime: MM READS every config at load and WRITES the cache minutes later, so
    #     anything edited during that window gets a false PASS. Observed 2026-07-29: a config saved
    #     at 15:20:12 was absent from a cache stamped 15:20:36, and this check said "verdict is
    #     current" while reporting a merge that predated the edit. Exactly the family-C failure in
    #     docs/BUG-CLASSES.md, produced by the tool written to catch family-C failures.
    #   - st_ctime is not usable either: NTFS file-system tunnelling hands a recreated KSP.log the
    #     ORIGINAL creation time, so it reads as hours or days stale.
    # What is left is the log's own first timestamp, which KSP writes at startup. It carries no
    # date, so pair it with the log file's date and step back a day if that lands in the future.
    booted = boot_started(log, os.path.getmtime(cache))
    newest, newest_f = 0, None
    for dirpath, _, files in os.walk(AXE):
        for fn in files:
            if not fn.endswith((".cfg", ".dll")):
                continue
            p = os.path.join(dirpath, fn)
            m = os.path.getmtime(p)
            if m > newest:
                newest, newest_f = m, p
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(booted))
    if newest > booted:
        print(f"\n*** STALE: this KSP run started {when}, but {rel(newest_f)} changed after it. ***")
        print("    Every verdict below describes the PREVIOUS boot. Delete")
        print(f"    {os.path.join(args.instance, 'GameData', 'ModuleManager.ConfigCache')}")
        print("    and relaunch KSP (`-axe-autotest` for a hands-free run), then re-run this.\n")
        fail = 1
    else:
        print(f"          boot of {when} started after every shipped cfg/dll -- verdict is current")

    live, usable, dead_compile, missing_modules = usable_parts(cache, log)
    print(f"          {len(live)} parts merged, {len(dead_compile)} failed to compile\n")

    # ---- A: tree nodes that grant nothing --------------------------------------------------
    empty, thin = [], []
    for nid, title, parts in tree_nodes():
        if nid in INTENTIONALLY_EMPTY:
            continue
        gone = [p for p in parts if p not in usable]
        if gone:
            (empty if len(gone) == len(parts) else thin).append((nid, title, parts, gone))
    print(f"=== A. tree nodes whose parts are missing from the game "
          f"({len(empty)} empty, {len(thin)} thinned; "
          f"{len(INTENTIONALLY_EMPTY)} allow-listed as deliberate gates) ===")
    for nid, title, parts, gone in empty:
        print(f"  EMPTY  {nid} -- \"{title}\"  grants nothing: {gone}")
    for nid, title, parts, gone in thin:
        print(f"  thin   {nid} -- \"{title}\"  {len(gone)}/{len(parts)} missing: {gone}")
    if empty:
        fail = 1
    print()

    # ---- B: modules we add that no assembly defines ------------------------------------------
    added = added_modules()
    phantom = {m: locs for m, locs in added.items() if m in missing_modules}
    print(f"=== B. part modules RP-AXE adds that KSP cannot resolve ({len(phantom)}) ===")
    if phantom:
        print("  (KSP drops the MODULE from the part; anything keyed on it -- a Kerbalism")
        print("   `requirements = Module:X`, a contract PartValidation -- can never match.)")
    for m in sorted(phantom):
        print(f"  {m}")
        for f, i in phantom[m][:3]:
            print(f"      {f}:{i}")
    if phantom:
        fail = 1
    print()

    # ---- C: top-level nodes nothing reads ----------------------------------------------------
    shipped = shipped_top_nodes()
    candidates = {n for n in shipped if n not in PATCH_TIME_ONLY}
    readers = name_in_assemblies(candidates, assemblies(args.instance))
    unread = sorted(n for n in candidates if n not in readers)
    inert = [n for n in unread if n not in INERT_BY_DESIGN]
    kept = [n for n in unread if n in INERT_BY_DESIGN]
    print(f"=== C. top-level config nodes no assembly reads ({len(inert)}; "
          f"{len(kept)} allow-listed as deliberate) ===")
    if inert:
        print("  (ModuleManager merges them either way -- the file looks authored and does nothing.)")
    for n in inert:
        print(f"  {n}")
        for f, i in shipped[n][:3]:
            print(f"      {f}:{i}")
    for n in kept:
        print(f"  kept   {n} -- {INERT_BY_DESIGN[n]}")
    if inert:
        fail = 1
    print()

    # ---- T: tech gates that point at no node (delegated to check_tech_refs, cache mode) -------
    valid = check_tech_refs.load_valid_nodes(check_tech_refs.DEFAULT_TREE) | check_tech_refs.INTENTIONAL
    findings = check_tech_refs.scan_cache(cache, valid)
    axe_bad, ext_bad = check_tech_refs.split_findings(findings)
    dangling = sorted(axe_bad + ext_bad)          # in cache mode nothing is external -- see that tool
    inert_tl = sum(1 for refs in findings.values() for r in refs if r[3])
    print(f"=== T. tech-gate references that resolve to no tree node ({len(dangling)}) ===")
    if inert_tl:
        print(f"  (skipped {inert_tl} RealFuels TLTECH rung(s) for engine classes no TechLevel-driven "
              f"part uses -- they gate nothing; see check_tech_refs.live_engine_types)")
    if dangling:
        print("  (GetTechnologyState(unknown) -> Unavailable: whatever they gate is locked forever.)")
    for node, refs in dangling:
        fields = sorted({r[0] for r in refs})
        print(f"  {node}  [{', '.join(fields)}]  x{len(refs)}")
        for f in sorted({r[1] for r in refs})[:3]:
            print(f"      {f}")
    if dangling:
        fail = 1
    print()

    # ---- D: patch targets that matched nothing (advisory) -------------------------------------
    targets = patch_targets()
    dead_t = {t: locs for t, locs in targets.items() if t not in live}
    ours = sorted((t, locs) for t, locs in dead_t.items()
                  if any(f.startswith("GameData/RP-AXE/design/") for f, _ in locs))
    print(f"=== D. @PART targets in design/ that matched no live part ({len(ours)}) -- advisory ===")
    print("  (RP-AXE carries RP-1's support for optional mods this install lacks -- FASA, SSTU,")
    print("   ALCOR, Raidernick -- so most of these are inert on purpose. Read them for the ones")
    print("   that name a part we DO expect to exist.)")
    for t, locs in ours:
        print(f"  {t}")
        for f, i in locs[:3]:
            print(f"      {f}:{i}")
    print(f"  ... plus {len(dead_t) - len(ours)} more in vendored seed/ support patches")

    # ---- E: did the emitted VALUES actually land? (wiring is not effect) --------------------
    print()
    efail, _ = check_effects(cache)
    fail = fail or efail

    # ---- F: contract gates on a facility rung that does not exist --------------------------
    print()
    ffail, _ = check_facility_gates(cache)
    fail = fail or ffail

    print("\n" + ("FAIL -- see 0/A/B/C/T/E/F above." if fail
                  else "OK -- everything RP-AXE ships binds to something, and its values landed."))
    return fail


if __name__ == "__main__":
    sys.exit(main())
