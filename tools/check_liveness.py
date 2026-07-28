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
  A  empty / thinned tree nodes  -- a placed part that no longer exists in the loaded game
  B  phantom part modules       -- MODULE{name=X} we add where no assembly defines X
  C  inert config nodes         -- a top-level NODE we ship that no assembly ever reads
  D  dead patch targets         -- @PART[x] we patch where x matched nothing (report only)

Exit code is non-zero if A, B or C found anything. D is advisory: RP-AXE deliberately carries
RP-1's patches for optional mods (FASA, SSTU, ALCOR...) that this install does not have.
"""
import argparse, glob, os, re, sys
from collections import defaultdict

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


# ---------------------------------------------------------------- checks

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

    live, usable, dead_compile, missing_modules = usable_parts(cache, log)
    print(f"          {len(live)} parts merged, {len(dead_compile)} failed to compile\n")
    fail = 0

    # ---- A: tree nodes that grant nothing --------------------------------------------------
    empty, thin = [], []
    for nid, title, parts in tree_nodes():
        gone = [p for p in parts if p not in usable]
        if gone:
            (empty if len(gone) == len(parts) else thin).append((nid, title, parts, gone))
    print(f"=== A. tree nodes whose parts are missing from the game "
          f"({len(empty)} empty, {len(thin)} thinned) ===")
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
    inert = sorted(n for n in candidates if n not in readers)
    print(f"=== C. top-level config nodes no assembly reads ({len(inert)}) ===")
    if inert:
        print("  (ModuleManager merges them either way -- the file looks authored and does nothing.)")
    for n in inert:
        print(f"  {n}")
        for f, i in shipped[n][:3]:
            print(f"      {f}:{i}")
    if inert:
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

    print("\n" + ("FAIL -- see A/B/C above." if fail else "OK -- everything RP-AXE ships binds to something."))
    return fail


if __name__ == "__main__":
    sys.exit(main())
