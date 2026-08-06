#!/usr/bin/env python3
"""Mirror a KSP save's research progress into the tree render prototype.

Reads the ResearchAndDevelopment scenario out of a persistent.sfs and writes a
one-click launcher next to the standalone bundle:

    tree/render/prototype/save-view.html
        -> axe-tree-standalone.html?research=<ids from the save>

renderer.js treats ?research= as authoritative (it replaces any localStorage
progress), so the launcher reproduces the save's frontier exactly rather than
unioning with whatever you last clicked in the prototype.

    python tools/save_progress.py                  # newest save under Instance/saves
    python tools/save_progress.py default3         # a save by name
    python tools/save_progress.py path/to/x.sfs    # an explicit .sfs
    python tools/save_progress.py --sel <nodeId>   # also open focused on a node

The KSP save holds no R&D camera position (nothing in the .sfs records the tech
tree's scroll/zoom), so the framing is inferred: the launcher opens parked on the
LAST node in the save's Tech list (KSP appends in research order) at roughly the
in-game tile scale, since fit-the-whole-527-node-tree is nobody's vantage point.
--center/--zoom override it, --no-center goes back to the full-tree fit.
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
PROTO = os.path.join(ROOT, "tree", "render", "prototype")
SAVES = os.path.normpath(os.path.join(ROOT, "..", "Instance", "saves"))
BUNDLE = "axe-tree-standalone.html"
OUT = os.path.join(PROTO, "save-view.html")


def newest_save():
    """The most recently written save folder that actually has a persistent.sfs."""
    if not os.path.isdir(SAVES):
        sys.exit("save_progress: no Instance/saves at %s" % SAVES)
    cand = []
    for name in os.listdir(SAVES):
        sfs = os.path.join(SAVES, name, "persistent.sfs")
        if os.path.isfile(sfs):
            cand.append((os.path.getmtime(sfs), name, sfs))
    if not cand:
        sys.exit("save_progress: no persistent.sfs under %s" % SAVES)
    return max(cand)[1:]


def resolve(arg):
    if arg is None:
        return newest_save()
    if arg.lower().endswith(".sfs"):
        if not os.path.isfile(arg):
            sys.exit("save_progress: no such save file: %s" % arg)
        return os.path.basename(os.path.dirname(os.path.abspath(arg))), arg
    sfs = os.path.join(SAVES, arg, "persistent.sfs")
    if not os.path.isfile(sfs):
        sys.exit("save_progress: no such save: %s" % sfs)
    return arg, sfs


def scenario_block(txt, want):
    """Slice out the SCENARIO node named `want`, by brace depth (no delimiter guessing)."""
    for m in re.finditer(r"^\s*name = %s\s*$" % re.escape(want), txt, re.M):
        open_brace = txt.rfind("{", 0, m.start())
        if open_brace < 0:
            continue
        depth, i = 1, open_brace + 1
        while i < len(txt) and depth:
            if txt[i] == "{":
                depth += 1
            elif txt[i] == "}":
                depth -= 1
            i += 1
        return txt[open_brace:i]
    sys.exit("save_progress: no %s scenario in the save" % want)


def read_progress(sfs):
    with open(sfs, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    blk = scenario_block(txt, "ResearchAndDevelopment")
    researched, other = [], []
    for m in re.finditer(r"\bTech\b\s*\{([^{}]*)\}", blk):
        body = m.group(1)
        tid = re.search(r"^\s*id = (\S+)", body, re.M)
        state = re.search(r"^\s*state = (\S+)", body, re.M)
        if not tid:
            continue
        (researched if state and state.group(1) == "Available" else other).append(tid.group(1))
    sci = re.search(r"^\s*sci = (\S+)", blk, re.M)
    return researched, other, float(sci.group(1)) if sci else 0.0


def tree_nodes():
    """ids -> node, from the prototype's generated tree-data.js (window.TREE = {...})."""
    path = os.path.join(PROTO, "tree-data.js")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    data = json.loads(src[src.index("{"): src.rindex("}") + 1])
    return data, {n["id"]: n for n in data["nodes"]}


def frontier(data, byid, done):
    """The RESEARCHABLE set — renderer.js stateOf(), so the counts match what you'll see."""
    parents = {i: [] for i in byid}
    for e in data["edges"]:
        if e["to"] in parents and e["from"] in byid:
            parents[e["to"]].append(e["from"])
    out = []
    for i, n in byid.items():
        if i in done:
            continue
        ps = parents[i]
        if not ps or (any(p in done for p in ps) if n.get("anyToUnlock")
                      else all(p in done for p in ps)):
            out.append(i)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("save", nargs="?", help="save name, or a path to a .sfs (default: newest)")
    ap.add_argument("--sel", metavar="NODE", help="node id to open selected + centred")
    ap.add_argument("--center", metavar="NODE", help="node id to park the camera on "
                                                     "(default: last researched)")
    ap.add_argument("--no-center", action="store_true", help="open fit to the whole tree instead")
    ap.add_argument("--zoom", type=float, default=1.0, metavar="S",
                    help="world scale, 1.0 = tiles at native size (default: %(default)s)")
    ap.add_argument("--print-url", action="store_true", help="print the URL only, write nothing")
    args = ap.parse_args()

    name, sfs = resolve(args.save)
    done, other, sci = read_progress(sfs)
    data, byid = tree_nodes()

    unknown = [t for t in done if t not in byid]
    known = [t for t in done if t in byid]
    if unknown:
        print("WARNING: %d save tech id(s) are not in tree-data.js (stale tree data or a "
              "renamed node) — skipped: %s" % (len(unknown), ", ".join(unknown)))
    if other:
        print("note: %d Tech node(s) in the save are not state=Available — skipped: %s"
              % (len(other), ", ".join(other)))
    if args.sel and args.sel not in byid:
        sys.exit("save_progress: --sel %s is not a node in tree-data.js" % args.sel)

    # KSP appends Tech nodes in the order they were researched, so the tail is where you left off.
    center = args.center or (known[-1] if known and not args.no_center else None)
    if args.center and args.center not in byid:
        sys.exit("save_progress: --center %s is not a node in tree-data.js" % args.center)
    if args.no_center:
        center = None

    query = "research=" + quote(",".join(known), safe=",")
    if args.sel:
        query += "&sel=" + quote(args.sel)
    if center:
        query += "&zoom=%g&center=%s" % (args.zoom, quote(center))
    url = "%s?%s" % (BUNDLE, query)

    tiers = [byid[t]["tier"] for t in known] or [0]
    print("save        %s  (%s)" % (name, sfs))
    print("researched  %d node(s), tiers %d-%d · %d researchable next · %.2f sci banked"
          % (len(known), min(tiers), max(tiers), len(frontier(data, byid, set(known))), sci))
    print("opens on    %s" % ("%s (%s, T%d) at %g× — last researched in the save"
                              % (byid[center]["title"], center, byid[center]["tier"], args.zoom)
                              if center else "the whole-tree fit"))

    if args.print_url:
        print(url)
        return

    if not os.path.isfile(os.path.join(PROTO, BUNDLE)):
        sys.exit("save_progress: %s missing — run tools/build_standalone.py first" % BUNDLE)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(
            "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">\n"
            "<title>RP-AXE tree — save '%s'</title>\n"
            "<!-- GENERATED by tools/save_progress.py from %s — re-run it after playing. -->\n"
            "<meta http-equiv=\"refresh\" content=\"0; url=%s\">\n"
            "</head><body style=\"background:#0b1016;color:#9aa;font-family:Segoe UI,sans-serif\">\n"
            "<p>Opening the tree at save <b>%s</b> (%d researched)&hellip; "
            "<a style=\"color:#38bdf8\" href=\"%s\">continue</a></p>\n"
            "</body></html>\n" % (name, os.path.basename(sfs), url, name, len(known), url))
    print("wrote       %s" % os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
