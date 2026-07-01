#!/usr/bin/env python3
"""build_part_origin — tag every installed part's in-game description with its origin mod.

Reads the DEPLOYED instance's ModuleManager.ConfigCache (the complete, ground-truth catalogue
of what is actually installed) and emits
  GameData/RP-AXE/design/Tree/AxePartOrigin.cfg
a ModuleManager patch appending "From <origin> mod" (green) to each part's description — the RP-1
feature (see RP-1/GameData/RP-1/Tree/TREE-Parts.cfg), reproduced from the live install.

Why the cache and not manifest/curated-parts.tsv: the manifest is a frozen 1820-part CURATED
subset built from two clean reference installs that no longer exist on disk, so it misses ~500
installed parts (e.g. RN_US_Probes/KH9). The cache has all of them, with each part's full
`parentUrl` path — which is also what lets us render a mod + sub-pack origin.

Origin = the part's parentUrl folder path:
  RN_US_Probes/KH9/kh9_ds.cfg              -> RN_US_Probes/KH9
  CoatlAerospace/GroundOps/Parts/.../x.cfg -> CoatlAerospace/GroundOps
  SXT/Parts/.../x.cfg                      -> SXT           (generic 'Parts' container collapsed)
  SomeMod/x.cfg                            -> SomeMod
i.e. the root mod folder, plus the second path segment when it's a real sub-pack (not a generic
Parts/ container and not the terminal .cfg).

Two kinds of part are SKIPPED so we don't double-tag what RP-1 already tagged:
  1. parentUrl under RP-AXE/ — our vendored seed full-defs (their origin isn't "RP-AXE/seed" anyway).
  2. any part a seed .cfg already gives a green "From X mod" tag — including seed PATCHES whose target
     part lives in a base mod (e.g. @PART[USGooBayWedge] in seed/Parts/Science/US2.cfg), which rule 1
     misses. Discovered by scanning the seed tree, so it stays correct as the seed evolves.

Green (not RP-AXE's blue #7fd3ff [RP-AXE] marker): green = where the part came from,
blue = RP-AXE touched it. The `^=:$:` append is a regex-replace whose pattern is `$`
(end-of-string), so existing description content never affects matching; parts not installed in a
given instance no-op silently; `:FOR[RP-AXE]` runs after the seed's `:FOR[RP-0]` description edits.

Needs a built instance (run tools/deploy.ps1 + launch KSP once so the cache exists).
Run: `python tools/build_part_origin.py` (no args).
"""
import os, re, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(ROOT, ".."))
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"
SEED = os.path.join(REPO, "GameData", "RP-AXE", "seed")
OUTD = os.path.join(REPO, "GameData", "RP-AXE", "design", "Tree")

GENERIC = {"parts", "part"}  # sub-pack folders that carry no provenance signal -> collapse to root
TAG = re.compile(r"From .+? mod</color>")            # the RP-1 origin tag already present in a description
HDR = re.compile(r"^[@+\-$]?PART\[([^\]]+)\]")        # a @/+/-/$ PART[name|name...] patch header


def seed_tagged_names():
    """Part names a seed .cfg already gives a 'From X mod' tag — skip these so we don't re-tag them.
    Brace-tracks each cfg so a tag is attributed to its enclosing PART (header bracket name, or the
    `name =` field of a full definition)."""
    out = set()
    for droot, _, files in os.walk(SEED):
        for fn in files:
            if not fn.endswith(".cfg"):
                continue
            with open(os.path.join(droot, fn), encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            frames = []; pending = None   # frames = open nodes by depth; pending = header name awaiting '{'
            for ln in lines:
                s = ln.strip()
                if not s or s.startswith("//"):
                    continue
                m = HDR.match(s)
                if m:
                    pending = set(m.group(1).split("|"))
                for ch in s:
                    if ch == "{":
                        frames.append({"names": pending or set(), "tagged": False}); pending = None
                    elif ch == "}" and frames:
                        fr = frames.pop()
                        if fr["tagged"]:
                            out |= fr["names"]
                if frames and TAG.search(s):
                    frames[-1]["tagged"] = True
                if frames and not frames[-1]["names"] and s.lower().startswith("name") and "=" in s:
                    frames[-1]["names"] = {s.split("=", 1)[1].strip()}
    return out


def origin(parent_url):
    """root mod folder + meaningful sub-pack from the part's parentUrl (see module docstring)."""
    segs = parent_url.split("/")
    if len(segs) >= 3 and segs[1].lower() not in GENERIC:
        return f"{segs[0]}/{segs[1]}"
    return segs[0]


def parts(cache):
    """yield (name, parentUrl) for every PART node in the ConfigCache (parentUrl = the .cfg it came from)."""
    with open(cache, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    n = len(lines); cur = None; i = 0
    while i < n:
        s = lines[i].strip()
        if s.startswith("parentUrl"):
            cur = s.split("=", 1)[1].strip()
        elif s == "PART" or s.startswith("PART "):
            j = i + 1
            while j < n and lines[j].strip() != "{": j += 1
            d = 0; started = False; name = None; k = j
            while k < n:
                t = lines[k].strip()
                if t == "{": d += 1; started = True
                elif t == "}":
                    d -= 1
                    if started and d == 0: break
                elif d == 1 and t.startswith("name") and "=" in t and name is None:
                    name = t.split("=", 1)[1].strip()
                k += 1
            if name and cur: yield name, cur
            i = k
        i += 1


def main():
    if not os.path.exists(CACHE):
        raise SystemExit(f"ERROR: ConfigCache not found at {CACHE}\n"
                         "Deploy (tools/deploy.ps1) and launch KSP once so the cache is built.")
    pre_tagged = seed_tagged_names()   # parts a seed cfg already tags (incl. base-mod patch targets)
    seen = {}; skipped = 0
    for name, parent in parts(CACHE):
        if parent.startswith("RP-AXE/") or name in pre_tagged:   # already carries RP-1's own tag
            skipped += 1; continue
        seen.setdefault(name, origin(parent))   # first parentUrl wins; part names are unique in KSP

    rows = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))   # by origin, then name -> stable diffs
    L = ["// GENERATED by tools/build_part_origin.py — DO NOT EDIT BY HAND",
         "// Appends each part's source mod (parentUrl path) to its description (RP-1 parity).",
         "// Sourced from the live Instance ConfigCache; parts under RP-AXE/seed are skipped",
         "// (they already carry RP-1's own 'From X mod' tag)."]
    for name, org in rows:
        L.append(f"@PART[{name}]:FOR[RP-AXE] {{ @description ^=:$: "
                 f"<b><color=green>From {org} mod</color></b> }}")
    with open(os.path.join(OUTD, "AxePartOrigin.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    origins = collections.Counter(org for _, org in rows)
    with_pack = sum(1 for o in origins if "/" in o)
    print(f"OK  {len(rows)} parts tagged across {len(origins)} origins "
          f"({with_pack} with a sub-pack); {skipped} seed parts skipped -> AxePartOrigin.cfg")


if __name__ == "__main__":
    main()
