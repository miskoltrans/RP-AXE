#!/usr/bin/env python3
"""Build the RP-AXE release archive: dist/RP-AXE-v<version>.zip

    python tools/package_release.py            # builds AXE.dll, then zips
    python tools/package_release.py --no-build # zip whatever Plugins/AXE.dll is there

What goes in (and the archive root is GameData/RP-AXE/, which is what the netkan's
`find: RP-AXE` + `install_to: GameData` expects):
  * every git-TRACKED file under GameData/RP-AXE -- so runtime droppings (@thumbs/,
    Bridge.cfg, ModuleManager caches) and anything gitignored can never leak in, and
  * Plugins/AXE.dll, which is gitignored build output and so has to be added by hand,
  * minus EXCLUDE: dev artifacts that are tracked for the tools but have no business
    on a player's disk.

Guards: refuses a git-lfs POINTER (the ~120 MB of vendored RP-1 part models/textures are
LFS; a checkout without `git lfs pull` would ship 130-byte stubs that look like files),
refuses a missing or stale DLL, and refuses to overwrite an existing archive for the
same version unless --force.

The version is read from GameData/RP-AXE/RP-AXE.version (KSP-AVC) -- bump it there,
that single file drives the archive name, the in-game version and CKAN's $vref.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
MOD_DIR = "GameData/RP-AXE"
DLL = MOD_DIR + "/Plugins/AXE.dll"
AVC = os.path.join(REPO, MOD_DIR, "RP-AXE.version")
CSPROJ = os.path.join(REPO, "Source", "AXE", "AXE.csproj")
DIST = os.path.join(REPO, "dist")

# Tracked under GameData/RP-AXE for the tooling, but not part of the mod.
EXCLUDE = {
    MOD_DIR + "/Plugins/.gitkeep",
    MOD_DIR + "/Plugins/PluginData/craft-prices.csv",   # AutoTest dev sweep output, read by tools/analyze_craft_costs.py
}
LFS_MAGIC = b"version https://git-lfs"


def version():
    with open(AVC, encoding="utf-8") as f:
        v = json.load(f)["VERSION"]
    return "%d.%d.%d" % (v["MAJOR"], v["MINOR"], v["PATCH"])


def tracked_files():
    out = subprocess.check_output(["git", "-C", REPO, "ls-files", "-z", "--", MOD_DIR])
    return [p for p in out.decode("utf-8").split("\0") if p]


def build():
    print("building AXE.dll ...")
    r = subprocess.run(["dotnet", "build", CSPROJ, "-c", "Release", "-nologo", "-v", "q"], cwd=REPO)
    if r.returncode:
        sys.exit("dotnet build failed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-build", action="store_true", help="do not run dotnet build first")
    ap.add_argument("--force", action="store_true", help="overwrite an existing archive for this version")
    args = ap.parse_args()

    ver = version()
    out = os.path.join(DIST, "RP-AXE-v%s.zip" % ver)
    if os.path.exists(out) and not args.force:
        sys.exit("%s exists -- bump RP-AXE.version or pass --force" % out)
    if not args.no_build:
        build()

    dll = os.path.join(REPO, DLL)
    if not os.path.exists(dll):
        sys.exit("no %s -- build it (drop --no-build)" % DLL)
    # A DLL older than any plugin source is a stale build that looks perfectly packaged.
    newest_src = max(os.path.getmtime(os.path.join(d, f))
                     for d, _, fs in os.walk(os.path.join(REPO, "Source", "AXE"))
                     if "\\bin" not in d and "\\obj" not in d and "/bin" not in d and "/obj" not in d
                     for f in fs if f.endswith(".cs"))
    if os.path.getmtime(dll) < newest_src:
        sys.exit("%s is older than Source/AXE/*.cs -- rebuild (drop --no-build)" % DLL)

    files = [p for p in tracked_files() if p not in EXCLUDE]
    files.append(DLL)
    files.sort()

    problems = []
    for p in files:
        full = os.path.join(REPO, p)
        if not os.path.exists(full):
            problems.append("missing on disk: " + p)
            continue
        with open(full, "rb") as f:
            if f.read(len(LFS_MAGIC)) == LFS_MAGIC:
                problems.append("git-lfs pointer, not content (run `git lfs pull`): " + p)
        if p.endswith((".pdb", ".bak", ".orig")) or "/@thumbs/" in p:
            problems.append("dev artifact: " + p)
    if problems:
        print("\n".join("  " + x for x in problems))
        sys.exit("refusing to package")

    os.makedirs(DIST, exist_ok=True)
    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            full = os.path.join(REPO, p)
            z.write(full, p)            # forward slashes, GameData/RP-AXE/... at the archive root
            total += os.path.getsize(full)

    # Re-open and prove the shape a CKAN install relies on.
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        bad = [n for n in names if not n.startswith(MOD_DIR + "/")]
        assert not bad, "entries outside %s/: %s" % (MOD_DIR, bad[:5])
        assert DLL in names, "AXE.dll missing from archive"
        assert MOD_DIR + "/RP-AXE.version" in names
    sha = hashlib.sha256(open(out, "rb").read()).hexdigest()
    with open(out + ".sha256", "w") as f:
        f.write("%s  %s\n" % (sha, os.path.basename(out)))

    print("wrote %s" % out)
    print("  %d files, %.1f MB uncompressed, %.1f MB zipped" % (len(names), total / 1e6, os.path.getsize(out) / 1e6))
    print("  sha256 %s" % sha)
    print("  excluded: %s" % ", ".join(sorted(os.path.basename(e) for e in EXCLUDE)))
    print("  built %s" % time.strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
