#!/usr/bin/env python3
"""RO-coverage audit (D10).

Parses the fully MM-merged ModuleManager.ConfigCache and reports, per source mod,
how many parts RealismOverhaul actually configured vs. left untagged.

RO flags every part it supports with `RSSROConfig = True`; any part lacking that flag
is rewritten by RealismOverhaul_Global_Config.cfg to:
  - title   : "non RO - <title>"
  - desc    : "... (PART NOT SUPPORTED BY RO)"
  - category: 97  (FilterExtensions junk drawer)
WIP parts get "(PART IN PROGRESS, MAY NOT WORK)" instead.

We key off the merged description tag (ground truth), not the RO config-file line count
(which does NOT map 1:1 to parts — variant parts inflate it). See docs/DECISIONS.md D10.

Usage:
  python tools/ro_coverage.py [path-to-ConfigCache] [--dump-unsupported out.txt]

Default cache path: ../Instance/GameData/ModuleManager.ConfigCache relative to repo.
"""
import sys, os, collections

NOT_SUP = "(PART NOT SUPPORTED BY RO)"
WIP     = "(PART IN PROGRESS, MAY NOT WORK)"

def default_cache():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "Instance",
                                         "GameData", "ModuleManager.ConfigCache"))

def modname(url):
    return url.split("/")[0] if url else "<none>"

def parse(cache):
    """Yield (mod, part_name, status) for every PART node. status in sup|nosup|wip."""
    with open(cache, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    n = len(lines)
    cur_parent = None
    i = 0
    while i < n:
        s = lines[i].strip()
        if s.startswith("parentUrl"):
            cur_parent = s.split("=", 1)[1].strip()
        elif s == "PART" or s.startswith("PART "):
            j = i + 1
            while j < n and lines[j].strip() != "{":
                j += 1
            depth = 0; started = False; pname = None; status = "sup"; k = j
            while k < n:
                t = lines[k].strip()
                if t == "{":
                    depth += 1; started = True
                elif t == "}":
                    depth -= 1
                    if started and depth == 0:
                        break
                else:
                    if pname is None and t.startswith("name") and "=" in t:
                        pname = t.split("=", 1)[1].strip()
                    if NOT_SUP in t:
                        status = "nosup"
                    elif WIP in t and status != "nosup":
                        status = "wip"
                k += 1
            yield (modname(cur_parent), pname, status)
            i = k
        i += 1

def main(argv):
    cache = default_cache()
    dump = None
    a = argv[1:]
    while a:
        x = a.pop(0)
        if x == "--dump-unsupported":
            dump = a.pop(0)
        else:
            cache = x
    if not os.path.exists(cache):
        sys.exit(f"ConfigCache not found: {cache}\n(run KSP once with the mod set deployed)")

    mods = collections.defaultdict(collections.Counter)
    unsup = collections.defaultdict(list)
    for mod, name, status in parse(cache):
        mods[mod][status] += 1
        if status == "nosup":
            unsup[mod].append(name)

    print(f"# RO coverage  ({cache})\n")
    print(f"{'MOD':<32}{'total':>7}{'sup':>7}{'NOSUP':>7}{'wip':>6}")
    print("-" * 59)
    for mod in sorted(mods, key=lambda m: -mods[m]['nosup']):
        c = mods[mod]
        print(f"{mod:<32}{sum(c.values()):>7}{c['sup']:>7}{c['nosup']:>7}{c['wip']:>6}")
    g = collections.Counter()
    for c in mods.values():
        g.update(c)
    print("-" * 59)
    print(f"{'TOTAL':<32}{sum(g.values()):>7}{g['sup']:>7}{g['nosup']:>7}{g['wip']:>6}")

    if dump:
        with open(dump, "w", encoding="utf-8") as f:
            for mod in sorted(unsup):
                for name in sorted(x for x in unsup[mod] if x):
                    f.write(f"{mod}\t{name}\n")
        print(f"\nwrote unsupported part list -> {dump}")

if __name__ == "__main__":
    main(sys.argv)
