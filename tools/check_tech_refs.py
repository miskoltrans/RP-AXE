#!/usr/bin/env python3
"""
check_tech_refs.py -- find tech-gate references that point at tech-tree node IDs
which do NOT exist in RP-AXE's generated tree.

Why: RP-AXE builds its tech tree from scratch (tree/nodes.yaml -> build_tree.py ->
design/Tree/AxeTechTree.cfg). Part/upgrade *placement* is regenerated and stays
consistent, but a large amount of config and plugin code references node IDs by
*string* -- and those fail CLOSED and SILENT if the node is renamed/removed:
  - EXPERIMENT_DEFINITION `techRequired = X`   (GetTechnologyState -> Unavailable)
  - Kerbalism Configure/SETUP `tech = X`       (SETUP never selectable)
  - ModuleManager `@PART[*]:HAS[#TechRequired[X]]` filters (matches 0 parts)
  - module `UPGRADE { techRequired__ = X }`
  - Contract Configurator `tech = X` / TechResearched requirements
  - C# `ResearchAndDevelopment.GetTechnologyState("X")` in plugins
None of these warn or throw. This tool turns that silent failure into a report.

Usage:
  python tools/check_tech_refs.py                 # scan the repo (RP-AXE-owned)
  python tools/check_tech_refs.py --root <dir>    # add another config root (e.g. an instance GameData)
  python tools/check_tech_refs.py --instance C:\\git\\ksp\\Instance\\GameData   # full instance audit
Exit code is non-zero if any RP-AXE-owned dangling reference is found (build-gate use);
external-mod dangling refs are reported but do not fail (they're the orphaned-tech triage list).
"""
import argparse, os, re, sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Node IDs that are intentionally absent from the tree (a mod's deliberate catch-all
# / fallback, not a break). Kept minimal + documented.
INTENTIONAL = {
    "ORPHANS",   # ProceduralParts orphan-catcher: deprecated part variants gate here on purpose
}
DEFAULT_TREE = os.path.join(REPO, "GameData", "RP-AXE", "design", "Tree", "AxeTechTree.cfg")
DEFAULT_ROOTS = [os.path.join(REPO, "GameData", "RP-AXE")]
DEFAULT_SRC = os.path.join(REPO, "Source")

# References that are authored in seed/ but deliberately fixed at runtime by a design/
# overlay (so the seed value is a known, intentional "false positive"). Keep tiny + documented.
OVERLAY_FIXED = {
    # (node, gate, filename-substring): reason
    ("surfaceScience", "tech", "SurfaceSample.cfg"): "fixed by design/Science/AxeSurfaceSampleGate.cfg",
}

# gate-field patterns: (label, compiled regex capturing the node id)
GATE_PATTERNS = [
    ("techRequired",   re.compile(r"^\s*techRequired\s*=\s*(\S+)", re.M)),
    ("techRequired__", re.compile(r"^\s*techRequired__\s*=\s*(\S+)", re.M)),
    ("tech",           re.compile(r"^\s*tech\s*=\s*(\w+)\s*$", re.M)),        # Kerbalism SETUP / contract; node-shaped only
    ("#TechRequired",  re.compile(r"#TechRequired\[(\w+)\]")),
]
CS_PATTERN = re.compile(r'GetTechnologyState\(\s*"(\w+)"')
SKIP_DIR = re.compile(r"[\\/](Localization|Flags|Textures?|Sounds?|PluginData)[\\/]", re.I)
SKIP_EXT = (".disabled", ".disable")


def load_valid_nodes(tree_path):
    if not os.path.isfile(tree_path):
        sys.exit(f"tree not found: {tree_path} (run tools/build_tree.py first)")
    txt = open(tree_path, encoding="utf-8", errors="replace").read()
    # RDNode ids: `id = X` lines (RDNode blocks). Excludes parentID / part = / Unlocks.
    return set(re.findall(r"^\s*id\s*=\s*(\S+)", txt, re.M))


def iter_cfgs(root):
    for dirpath, _, files in os.walk(root):
        if SKIP_DIR.search(dirpath + os.sep):
            continue
        for f in files:
            low = f.lower()
            if low.endswith(".cfg") and not low.endswith(SKIP_EXT) and ".cfg." not in low:
                yield os.path.join(dirpath, f)


def scan(roots, src, valid):
    # findings[node] = list of (gate, path, is_axe, is_overlay_fixed)
    findings = defaultdict(list)
    for root in roots:
        axe = "RP-AXE" in root or root.endswith("RP-AXE")
        for path in iter_cfgs(root):
            is_axe = axe or (os.sep + "RP-AXE" + os.sep) in path
            try:
                txt = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for label, pat in GATE_PATTERNS:
                for node in pat.findall(txt):
                    if node in valid:
                        continue
                    ov = any(k[0] == node and k[1] == label and k[2] in path for k in OVERLAY_FIXED)
                    findings[node].append((label, path, is_axe, ov))
    if src and os.path.isdir(src):
        for dirpath, _, files in os.walk(src):
            for f in files:
                if f.endswith(".cs"):
                    p = os.path.join(dirpath, f)
                    for node in CS_PATTERN.findall(open(p, encoding="utf-8", errors="replace").read()):
                        if node not in valid:
                            findings[node].append(("GetTechnologyState", p, True, False))
    return findings


def scan_cache(cache_path, valid):
    """Scan a ModuleManager.ConfigCache -- the POST-patch runtime truth. This is the
    accurate mode: it sees only what actually loaded, so design/ overlays that override
    a stale seed value (e.g. AxeAvionicsCore.cfg rewriting the avionics TIER techRequired)
    do NOT produce false positives. Cache-only fields: techRequired / tech / techRequired__
    (MM :HAS[#TechRequired[X]] filters are consumed at patch time and never reach the cache)."""
    findings = defaultdict(list)
    if not os.path.isfile(cache_path):
        sys.exit(f"ConfigCache not found: {cache_path} (launch KSP once to generate it)")
    parent = "?"
    # skip inert `disabled<X>` nodes (e.g. RO's disabledPARTUPGRADE templates) -- their
    # techRequired isn't a live gate. Track brace depth from the disabled header.
    skip_depth = None
    depth = 0
    with open(cache_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if skip_depth is not None:
                depth += line.count("{") - line.count("}")
                if depth <= skip_depth:
                    skip_depth = None
                continue
            if re.match(r"\s*disabled\w+\s*$", line):
                skip_depth = depth
                depth += 0  # the opening { is on the next line(s); tracked above
                continue
            depth += line.count("{") - line.count("}")
            m = re.match(r"\s*parentUrl\s*=\s*(\S+)", line)
            if m:
                parent = m.group(1)
                continue
            for label, pat in GATE_PATTERNS:
                if label == "#TechRequired":
                    continue
                mm = pat.match(line)
                if mm and mm.group(1) not in valid:
                    is_axe = "RP-AXE" in parent
                    findings[mm.group(1)].append((label, parent, is_axe, False))
    return findings


def split_findings(findings):
    """Partition scan() output into (axe_bad, ext_bad). Each is a sorted list of
    (node, real_refs); real_refs drops the overlay-fixed (allowlisted) refs."""
    axe_bad, ext_bad = [], []
    for node, refs in sorted(findings.items()):
        real = [r for r in refs if not r[3]]      # drop overlay-fixed
        if not real:
            continue
        (axe_bad if any(r[2] for r in real) else ext_bad).append((node, real))
    return axe_bad, ext_bad


def check_design(valid, design_root, src=None):
    """Build-time gate (no ConfigCache needed): scan RP-AXE's *authored* design/ cfgs
    (+ Source/ plugins) for raw tech-gate references that don't resolve against `valid`.
    seed/ (verbatim vendor) is excluded, and @-prefixed overlay assignments/selectors are
    never matched by the patterns (they legitimately name the OLD node) -> no false
    positives. Returns a sorted [(node, refs)] list of dangling authored references."""
    findings = scan([design_root], src, valid)
    axe_bad, ext_bad = split_findings(findings)
    return axe_bad + ext_bad


def rel(p):
    return p.replace(REPO + os.sep, "").replace(os.sep, "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default=DEFAULT_TREE)
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--instance", help="an instance GameData to also scan (full-instance audit)")
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--cache", help="scan a ModuleManager.ConfigCache (POST-patch truth -- no overlay false positives). Recommended for the real audit.")
    args = ap.parse_args()

    valid = load_valid_nodes(args.tree) | INTENTIONAL
    print(f"tree: {rel(args.tree)}  ({len(valid) - len(INTENTIONAL)} nodes)")

    if args.cache:
        print(f"mode: ConfigCache (runtime truth)  {args.cache}\n")
        findings = scan_cache(args.cache, valid)
    else:
        roots = list(DEFAULT_ROOTS) + args.root
        if args.instance:
            roots.append(args.instance)
        print(f"mode: SOURCE scan (fast; may false-positive on overlay-overridden seed refs)")
        print(f"roots: {', '.join(rel(r) for r in roots)}\n")
        findings = scan(roots, args.src, valid)
    if not findings:
        print("OK - every tech-gate reference resolves to a real tree node.")
        return 0

    axe_bad, ext_bad = split_findings(findings)

    def dump(title, items):
        if not items:
            return
        print(f"=== {title} ({len(items)} dangling node(s)) ===")
        for node, refs in items:
            fields = sorted({r[0] for r in refs})
            print(f"  {node}  [{', '.join(fields)}]  x{len(refs)}")
            for f in sorted({rel(r[1]) for r in refs})[:6]:
                print(f"      {f}")
        print()

    dump("RP-AXE-OWNED  (must fix -- these are ours)", axe_bad)
    dump("EXTERNAL MODS  (orphaned-tech triage -- other mods' hardcoded IDs)", ext_bad)

    overlay = [(n, r) for n, refs in findings.items() for r in refs if r[3]]
    if overlay:
        print(f"(note: {len(overlay)} ref(s) are stale in source but fixed at runtime by a design overlay -- allowlisted)")

    return 1 if axe_bad else 0


if __name__ == "__main__":
    sys.exit(main())
