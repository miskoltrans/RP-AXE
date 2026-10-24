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

Also writes dist/RP-AXE-<version>.ckan: the netkan "inflated" against the GitHub release
asset the zip will be uploaded as (download URL from the tag convention, size and hashes
from the zip). The CKAN client cannot read a netkan; until RP-AXE is on the CKAN registry
this .ckan is what a player feeds to "File -> Install from .ckan file" (or `ckan install -c`),
so it ships as a release asset next to the zip.

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


def write_ckan(ver, zip_path, data, sha256):
    """Inflate RP-AXE.netkan the way the NetKAN bot would, against the release asset for this version."""
    with open(os.path.join(REPO, "RP-AXE.netkan"), encoding="utf-8") as f:
        nk = json.load(f)
    with open(AVC, encoding="utf-8") as f:
        avc = json.load(f)
    ck = {k: v for k, v in nk.items() if k not in ("$kref", "$vref", "x_netkan_github", "comment")}
    mn, mx = avc["KSP_VERSION_MIN"], avc["KSP_VERSION_MAX"]
    ck["version"] = "v" + ver   # what the registry shows: netkan prefers the GitHub tag's "v0.9.0"
    ck["ksp_version_min"] = "%d.%d.%d" % (mn["MAJOR"], mn["MINOR"], mn["PATCH"])
    ck["ksp_version_max"] = "%d.%d.%d" % (mx["MAJOR"], mx["MINOR"], mx["PATCH"])
    ck["release_status"] = "testing" if ver.startswith("0.") else "stable"
    ck["download"] = "https://github.com/miskoltrans/RP-AXE/releases/download/v%s/%s" % (ver, os.path.basename(zip_path))
    ck["download_size"] = len(data)
    ck["download_hash"] = {"sha1": hashlib.sha1(data).hexdigest().upper(), "sha256": sha256.upper()}
    ck["download_content_type"] = "application/zip"
    path = os.path.join(DIST, "RP-AXE-%s.ckan" % ver)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ck, f, indent=4, ensure_ascii=False)
        f.write("\n")
    return path


EXPRESS = ("RP-AXE-Express-RSS-High", "RP-AXE-Express-RSS-Low")   # = gen_netkan.EXPRESS_HIGH / EXPRESS_LOW


def write_express_zips(ver):
    """dist/RP-AXE-Express-RSS-{High,Low}.zip: a marker folder with an AVC file, so the registry presets have
    a download (NetKAN refuses to index a metapackage) and a version that tracks the mod's. Mirrors
    RP-1-ExpressInstall-Graphics (install_size 776 bytes). Uploaded to the same release as the mod."""
    with open(AVC, encoding="utf-8") as f:
        avc = json.load(f)
    paths = []
    for ident in EXPRESS:
        tier = ident.rsplit("-", 1)[1]
        marker = {
            "NAME": "RP-AXE Express (RSS, %s graphics)" % tier,
            "VERSION": avc["VERSION"],
            "KSP_VERSION": avc.get("KSP_VERSION", avc["KSP_VERSION_MAX"]),
            "KSP_VERSION_MIN": avc["KSP_VERSION_MIN"],
            "KSP_VERSION_MAX": avc["KSP_VERSION_MAX"],
        }
        readme = (
            "%s %s\n\nThis folder is a marker left by the CKAN preset '%s'. It installs nothing itself: the preset is a\n"
            "list of dependencies (RP-AXE, its stack, the recommended tools and the RSS %s graphics set). Safe to\n"
            "delete; CKAN removes it with the preset.\n" % (ident, ver, ident, tier))
        out = os.path.join(DIST, ident + ".zip")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("GameData/%s/%s.version" % (ident, ident), json.dumps(marker, indent=4) + "\n")
            z.writestr("GameData/%s/README.txt" % ident, readme)
        paths.append(out)
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-build", action="store_true", help="do not run dotnet build first")
    ap.add_argument("--force", action="store_true", help="overwrite an existing archive for this version")
    ap.add_argument("--express-only", action="store_true",
                    help="only (re)write dist/RP-AXE-Express-RSS-{High,Low}.zip for the current version")
    args = ap.parse_args()

    ver = version()
    if args.express_only:
        os.makedirs(DIST, exist_ok=True)
        for p in write_express_zips(ver):
            print("wrote %s (%d bytes)" % (p, os.path.getsize(p)))
        return
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
    data = open(out, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    with open(out + ".sha256", "w") as f:
        f.write("%s  %s\n" % (sha, os.path.basename(out)))
    ckan_path = write_ckan(ver, out, data, sha)
    express = write_express_zips(ver)

    print("wrote %s" % out)
    print("wrote %s  (CKAN -> File -> Install from .ckan file)" % ckan_path)
    print("wrote %s  (release assets for the registry presets)" % ", ".join(os.path.basename(e) for e in express))
    print("release assets: the zip, its .sha256, the .ckan, the two Express RSS .zip and the three Express .ckan "
          "files (RSS-High, RSS-Low, Sol)")
    print("  %d files, %.1f MB uncompressed, %.1f MB zipped" % (len(names), total / 1e6, os.path.getsize(out) / 1e6))
    print("  sha256 %s" % sha)
    print("  excluded: %s" % ", ".join(sorted(os.path.basename(e) for e in EXCLUDE)))
    print("  built %s" % time.strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
