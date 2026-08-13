#!/usr/bin/env python3
"""check_model_anims.py -- audit every `animationName` against the .mu it is supposed to name, so a
config that animates a clip the model does not have can't reach a playtest.

Why: an animation name is one more unvalidated string (docs/BUG-CLASSES.md family A). KSP resolves
it by `GetComponentInChildren<Animation>()` + `anim[name]` at OnStart; when the clip is absent the
module logs ONE line -- "Could not find animation component 'X' - on part Y failed to load!" -- and
then *stays on the part with a null animation state*. That is the whole bite: the module is live,
so `ModuleAnimateGeneric` still publishes its PAW button and its action-group action, and the first
click NREs inside UpdateAnimSwitch(). Found 2026-08-13 on ROC-VoskhodCapsule, whose config is a
copy of Vostok's (antennae + a Deploy clip) but whose model has no animations at all.

It is NOT caught by the other detectors: the part compiles, loads, is placed, and works -- only one
button on it is a trap. And the log line is a [LOG], not an [ERR], so it does not stand out in a
64 MB boot log, and it is only emitted when the part is first instantiated in the editor or in
flight -- never at load. Nothing short of clicking every button finds it by hand.

Reads the live instance ConfigCache (post-patch truth: the models and the animationNames that
actually survived every mod's patches) and the .mu binaries they point at. Two findings:
  1. CLICKABLE (fails, exit 1): the dead name is on a module that gives the player something to
     press -- ModuleAnimateGeneric and friends. This is a live NRE on a curated part.
  2. DEAD (informational): the dead name is on a module driven by something other than a click
     (FXModuleAnimateThrottle, deploy-state modules). No NRE from the PAW, but the animation the
     config asks for does not exist, so the part is not doing what it says.

Scope limits, stated so they are not mistaken for coverage: only `animationName` /
`deployAnimationName` are scanned (the two fields that name a clip on the part's own model), and a
clip is "present" if its name appears as a string in ANY .mu the part loads. A part whose model is
generated at runtime by a plugin will read as a false positive; add it to REVIEWED_EXEMPT.

Usage:
  python tools/check_model_anims.py                      # uses the default instance below
  python tools/check_model_anims.py --cache <ConfigCache> --gamedata <GameData>
  python tools/check_model_anims.py --all                # report uncurated parts too
"""
import argparse, functools, os, re, sys

DEFAULT_CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"
DEFAULT_GAMEDATA = r"C:\git\ksp\Instance\GameData"
DEFAULT_CURATED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "manifest", "curated-parts.tsv")

# Fields that name an animation clip on the part's own model.
ANIM_FIELDS = ("animationName", "deployAnimationName")

# Modules that THROW on a missing clip *and* are reachable from the PAW / an action group. Verified
# against a decompile of this install's Assembly-CSharp (ilspycmd), not inferred from the field name
# -- the deployable family looks identical in config and behaves the opposite way:
#
#   ModuleAnimateGeneric   UpdateAnimSwitch() calls FindAnimation(), then dereferences
#                          `anim[animationName]` UNCONDITIONALLY -> NRE. This is the observed bug.
#   ModuleAnimationGroup   OnStart does `part.FindModelAnimators(deployAnimationName)[0]` on what is
#                          an EMPTY array when the clip is absent -> IndexOutOfRange.
#
# Deliberately NOT here (checked, genuinely safe):
#   ModuleDeployable{SolarPanel,Radiator,Antenna}  ModuleDeployablePart.FindAnimations() sets
#                          `useAnimation = false` when no animator has the clip, and every
#                          `anim[animationName]` in the class is behind `if (useAnimation)`. The part
#                          deploys instantly with no animation -- cosmetic, so it reports as DEAD.
#   FXModuleAnimateThrottle / ModuleAnimateHeat    not player-triggered, and empirically inert: this
#                          install logs 32 "Could not find animation" from the throttle module and
#                          zero exceptions from it.
CLICKABLE_MODULES = {
    "ModuleAnimateGeneric",
    "ModuleAnimationGroup",
}

# Parts reviewed and deliberately accepted: the model is built at runtime, or the animation is known
# to be supplied by a plugin rather than the .mu. Add with a dated reason.
REVIEWED_EXEMPT = {
    # (none yet)
}

@functools.lru_cache(maxsize=8)
def mu_bytes(path):
    """Raw .mu, or None if it does not exist. Small LRU: .mu files run to tens of MB, and the
    reference pattern is bursty (every part in a mod shares a few assets), so a handful of slots
    absorbs the re-reads without holding the whole GameData in memory."""
    try:
        return open(path, "rb").read()
    except OSError:
        return None


def mu_has(data, name):
    """Is `name` written as a string in this .mu?

    Unity's BinaryWriter.Write(string) emits a 7-bit-encoded length then the raw bytes, so the test
    is for the LENGTH-PREFIXED sequence. Scanning for printable runs instead is wrong in both
    directions: a name 32-126 chars long has a printable length byte that merges into the run (real
    case: 'aquila_..._deploy' at 51 chars reads as '3aquila_..._deploy' and is reported missing),
    and a bare substring test matches 'Deploy' inside 'DeployFoo'."""
    raw = name.encode("utf-8")
    n = len(raw)
    prefix = bytes([n]) if n < 128 else bytes([(n & 0x7F) | 0x80, n >> 7])
    return data.find(prefix + raw) >= 0


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


def rol_models(cache_text):
    """ROLib's model registry: name -> the .mu path it actually loads.

    ROLib parts (ROTank, ROHeatshields, the RP-1 contract sats) do NOT put a file path in their
    MODEL nodes -- they name an `ROL_MODEL` whose `modelName` holds the real path, and ROLib swaps
    the mesh in at runtime. Reading those names as paths is what makes ROH-AdjustableHIAD look
    broken: its `Inflate` clip is on ReStock's inflatable heatshield, which the registry points at."""
    reg = {}
    for m in re.finditer(r"\n\tROL_MODEL\n\t\{\n((?:\t\t.*\n)+)", cache_text):
        body = m.group(1)
        name = re.search(r"^\t\tname = (.+)$", body, re.M)
        path = re.search(r"^\t\tmodelName = (.+)$", body, re.M)
        if name and path:
            reg[name.group(1).strip()] = path.group(1).strip()
    return reg


def part_models(body, parent_url, gamedata, registry):
    """Every .mu the part loads: explicit MODEL nodes (resolved through ROLib's registry where they
    name one), a legacy `mesh =`, else stock's model.mu."""
    part_dir = os.path.join(gamedata, os.path.dirname(parent_url).replace("/", os.sep))
    paths = []
    for raw in re.findall(r"^\s*model = (.+)$", body, re.M):
        ref = raw.strip()
        if ref in ("Model-None", "none", "None"):
            continue                      # ROLib sentinel for "this slot is empty"
        ref = registry.get(ref, ref)
        paths.append(os.path.join(gamedata, ref.replace("/", os.sep)) + ".mu")
    if not paths:
        mesh = re.search(r"^\s*mesh = (.+)$", body, re.M)
        fn = mesh.group(1).strip() if mesh else "model.mu"
        if not fn.lower().endswith(".mu"):
            fn += ".mu"
        paths = [os.path.join(part_dir, fn)]
    return paths


def part_anims(body):
    """(module_name, field, clip) for each animation reference in the part.

    Walks the node tree rather than matching `name = Module*` lines, because the owning module has
    to be identified EXACTLY: mis-reading it only ever downgrades a finding out of CLICKABLE, which
    is a silent false negative -- the failure mode this detector exists to prevent. Prefix matching
    got that wrong twice: a `name = top` ATTACH node looks like a module name, and a module whose
    class does not start with 'Module' (SCANsat's `SCANsat`, which owns an optional `animationName`)
    was attributed to nothing at all. Module dicts are captured by reference so a `name` written
    after the animationName still resolves."""
    out, stack, pending = [], [], None
    for line in body.splitlines():
        st = line.strip()
        if st == "{":
            stack.append({"type": pending or "?", "name": None})
            pending = None
        elif st == "}":
            if stack:
                stack.pop()
        elif "=" in st:
            key, _, val = st.partition("=")
            key, val = key.strip(), val.strip()
            if key == "name" and stack and stack[-1]["name"] is None:
                stack[-1]["name"] = val
            elif key in ANIM_FIELDS and val and val.lower() not in ("none", "null"):
                owner = next((n for n in reversed(stack) if n["type"] == "MODULE"), None)
                out.append((owner, key, val))
        elif st:
            pending = st
    return [(o["name"] or "?" if o else "?", f, c) for o, f, c in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--gamedata", default=DEFAULT_GAMEDATA)
    ap.add_argument("--curated", default=DEFAULT_CURATED)
    ap.add_argument("--all", action="store_true", help="report uncurated parts too")
    args = ap.parse_args()

    curated = set()
    if os.path.exists(args.curated):
        for line in open(args.curated, encoding="utf-8"):
            col = line.rstrip("\n").split("\t")
            if len(col) > 1:
                curated.add(col[1].strip())

    cache = open(args.cache, encoding="utf-8", errors="replace").read()
    registry = rol_models(cache)

    clickable, dead, unreadable, checked, parts = [], [], [], 0, 0
    for name, url, body in parse_parts(cache):
        anims = part_anims(body)
        if not anims or name in REVIEWED_EXEMPT:
            continue
        parts += 1
        models = part_models(body, url, args.gamedata, registry)
        loaded = [(p, mu_bytes(p)) for p in models]
        readable = [(p, d) for p, d in loaded if d is not None]
        for module, field, clip in anims:
            checked += 1
            if not readable:
                # Every model path is unresolvable -- typically a plugin-built mesh (ROLib et al)
                # whose MODEL entries name registry models, not files. Cannot be judged from disk.
                unreadable.append((name, url, module, field, clip, models))
                continue
            if any(mu_has(d, clip) for _, d in readable):
                continue
            row = (name, url, module, field, clip, models)
            (clickable if module in CLICKABLE_MODULES else dead).append(row)

    def show(rows, header):
        rows = [r for r in rows if args.all or r[0] in curated]
        if not rows:
            return 0
        print(header)
        for name, url, module, field, clip, models in rows:
            tag = "" if name in curated else "   [uncurated]"
            print("  %-28s %s = %s" % (name, field, clip))
            print("      module %-28s %s%s" % (module, url, tag))
            for p in models:
                print("      model  %s" % os.path.relpath(p, args.gamedata))
        print()
        return len(rows)

    n_click = show(clickable, "CLICKABLE -- dead animation on a module the player can press (NRE):")
    n_dead = show(dead, "DEAD -- animation named but absent; module is not click-driven:")
    if unreadable:
        print("UNREADABLE -- no .mu could be read for these parts (plugin-generated model?):")
        for name, url, module, field, clip, files in unreadable:
            print("  %-28s %s = %s   (%s)" % (name, field, clip, url))
        print()

    print("checked %d animation references across %d parts" % (checked, parts))
    print("  %d clickable, %d dead%s" % (n_click, n_dead, "" if args.all else " (curated parts only; --all for the rest)"))
    return 1 if n_click else 0


if __name__ == "__main__":
    sys.exit(main())
