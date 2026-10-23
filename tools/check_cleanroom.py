#!/usr/bin/env python3
"""Does a CKAN install of RP-AXE match what RP-AXE.netkan promises?

    python tools/check_cleanroom.py --instance C:/git/ksp/ksp_instance_cleanroom

Reads the instance's CKAN/registry.json and GameData, and reports against the netkan:

  FAIL  a `depends` module is missing, a `conflicts` module is present, GameData/RP-1 exists,
        GameData/RP-AXE is missing or its RP-AXE.version disagrees with the repo's
  WARN  a `recommends` module is missing (CKAN installs them by default; a headless run may not)
  INFO  which `suggests` landed, and every installed module the netkan does not name
        (transitive deps -- expected, listed so a surprise stands out)

Exit 1 on any FAIL. This is the "release prove" of docs/RELEASE.md: a stranger's CKAN resolving
the metadata unattended must produce the part set the tree was balanced against.

An instance with Sol-Core installed is checked as a Sol install (docs/SOL.md): Sol's own packs and
the texture folders it reads instead of the RSS texture pack / RSSVE / Scatterer checks.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def names(rel):
    out = []
    for d in rel:
        if "name" in d:
            out.append(d["name"])
        elif "any_of" in d:
            out.append("|".join(x["name"] for x in d["any_of"]))
    return out


def check_sol(reg, inst, present, gd):
    """Sol in place of RSS (docs/SOL.md). Sol-Core's per-system packs are virtual and the ParallaxContinued
    texture packs got dropped by a headless resolver with exit 0 (2026-10-23), so check what Sol READS."""
    fail = 0
    print("  --   Sol install (Sol-Core %s)" % inst["Sol-Core"]["source_module"].get("version"))
    for d in names(inst["Sol-Core"]["source_module"].get("depends", [])):
        if not present(d):
            print("  FAIL Sol-Core dependency missing:", d); fail = 1
    # Sol's Parallax configs read these folders (~2,500 references); nothing else ships them
    for folder in ("Parallax_StockScatterTextures", "Parallax_StockTerrainTextures"):
        ok = os.path.isdir(os.path.join(gd, folder))
        print("  %s %s%s" % ("ok  " if ok else "FAIL", folder, "" if ok else " -- Sol's terrain/scatter textures; install the ParallaxContinued-*-Textures packs"))
        fail |= not ok
    # Sol-Visuals carries the EVE and Scatterer configs for Sol's bodies; RSS's would stack a second set
    for folder, want in (("Sol-Visuals", True), ("RSSVE", False), ("RealSolarSystem", False), ("RSS-Textures", False)):
        ok = os.path.isdir(os.path.join(gd, folder)) == want
        print("  %s %s %s" % ("ok  " if ok else "FAIL", folder, "present" if want else "absent"))
        fail |= not ok
    ok = os.path.isdir(os.path.join(gd, "RP-AXE", "design", "Sol"))
    print("  %s RP-AXE/design/Sol (the Sol compatibility layer, 0.9.1+)" % ("ok  " if ok else "FAIL"))
    return fail | (not ok)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", required=True, help="KSP install CKAN targeted (its CKAN/registry.json is read)")
    ap.add_argument("--netkan", default=os.path.join(REPO, "RP-AXE.netkan"))
    a = ap.parse_args()

    nk = load(a.netkan)
    reg = load(os.path.join(a.instance, "CKAN", "registry.json"))
    inst = reg["installed_modules"]
    provides = {}
    for m, v in inst.items():
        for pv in v.get("source_module", {}).get("provides", []):
            provides.setdefault(pv, set()).add(m)

    def present(name):
        return any(n in inst or n in provides for n in name.split("|"))

    fail = 0
    print("instance:", a.instance)
    print("installed modules:", len(inst))

    missing = [n for n in names(nk.get("depends", [])) if not present(n)]
    print("\n=== depends (%d) -- missing: %d ===" % (len(nk.get("depends", [])), len(missing)))
    for n in missing:
        print("  FAIL missing", n)
    fail |= bool(missing)

    miss_rec = [n for n in names(nk.get("recommends", [])) if not present(n)]
    print("\n=== recommends (%d) -- missing: %d ===" % (len(nk.get("recommends", [])), len(miss_rec)))
    for n in miss_rec:
        print("  WARN missing", n)

    sug = names(nk.get("suggests", []))
    print("\n=== suggests (%d) -- installed: %s ===" % (len(sug), [n for n in sug if present(n)] or "none"))

    bad = [n for n in names(nk.get("conflicts", [])) if present(n)]
    print("\n=== conflicts present: %s ===" % (bad or "none"))
    for n in bad:
        print("  FAIL conflicting module installed:", n)
    fail |= bool(bad)

    named = set()
    for k in ("depends", "recommends", "suggests"):
        for n in names(nk.get(k, [])):
            named.update(n.split("|"))
    extra = sorted(m for m in inst if m not in named and m != nk["identifier"]
                   and not any(m in provides.get(n, ()) for n in named))
    print("\n=== installed but not named in the netkan (transitive) (%d) ===" % len(extra))
    for m in extra:
        print("  INFO", m)

    gd = os.path.join(a.instance, "GameData")
    print("\n=== GameData ===")
    if os.path.isdir(os.path.join(gd, "RP-1")):
        print("  FAIL GameData/RP-1 exists"); fail = 1
    else:
        print("  ok   no GameData/RP-1")
    avc = os.path.join(gd, "RP-AXE", "RP-AXE.version")
    if not os.path.exists(avc):
        print("  FAIL GameData/RP-AXE/RP-AXE.version missing"); fail = 1
    else:
        got = load(avc)["VERSION"]; want = load(os.path.join(REPO, "GameData", "RP-AXE", "RP-AXE.version"))["VERSION"]
        tag = "ok  " if got == want else "FAIL"
        fail |= got != want
        print("  %s RP-AXE.version installed %s / repo %s" % (tag, got, want))
    for f in ("Plugins/AXE.dll", "design/Tree/AxeTechTree.cfg", "seed/Parts/_SYNC_PROVENANCE.txt"):
        ok = os.path.exists(os.path.join(gd, "RP-AXE", f))
        print("  %s %s" % ("ok  " if ok else "FAIL", f)); fail |= not ok
    if "Sol-Core" in inst:
        fail |= check_sol(reg, inst, present, gd)
    elif os.path.isdir(os.path.join(gd, "Scatterer")):
        # `Scatterer/config` is the plugin's own folder and is always there; the planet list the
        # resolver drops is StockScattererConfigs (run 2), and that list names STOCK bodies: only
        # RSSVE's patch retargets it to RSS, so Scatterer without RSSVE renders nothing (run 5).
        cfg = os.path.isdir(os.path.join(gd, "StockScattererConfigs"))
        rssve = os.path.isdir(os.path.join(gd, "RSSVE"))
        print("  %s Scatterer present, planet config %s" % ("ok  " if cfg else "FAIL", "present" if cfg else "MISSING -- the silent-drop symptom"))
        print("  %s Scatterer %s RSSVE%s" % ("ok  " if rssve else "FAIL", "with" if rssve else "WITHOUT", "" if rssve else " -- its planet list is stock bodies; inert on RSS"))
        fail |= not (cfg and rssve)

    print("\n" + ("FAIL" if fail else "OK -- the install matches the netkan"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
