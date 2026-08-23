#!/usr/bin/env python3
"""Port RP-1's hand-authored per-part avionics mass limits into RP-AXE's fixed-capacity module.

RP-1 states a named part's guidance capability as `ModuleAvionics.massLimit` -- the vessel mass that
unit can steer -- and hand-authors one number per spacecraft in GameData/RP-1/Avionics.cfg (~1283 lines,
each with its reasoning: "Cassini 5712 kg Launch mass" -> 6.0 t). It is not derivable from part data, so
this ports the table rather than recomputing it. Values are read from RP-1's RESOLVED ModuleManager
config cache, not from Avionics.cfg directly, so MM's own patch ordering (and every RO/mod config that
also sets massLimit) is already applied for us.

Field mapping RP-1 -> AXE (see Source/AXE/Avionics/ModuleAxeFixedAvionics.cs):
    massLimit       -> capacityTons     (verbatim)
    allowAxial      -> allowAxial       (RP0.ModuleAvionics defaults it to TRUE when the key is absent --
                                         several parts rely on that, e.g. an over-limit Vostok keeps its
                                         axial retro burn -- so absence must be read as true, not false)
    interplanetary  -> shielded         (RP-1's near-Earth lockout marked exactly the units rated to work
                                         beyond near-Earth; AXE moved range gating to comms, so the flag
                                         is reused as the radiation-hardening marker it always implied.
                                         Also defaults TRUE when absent.)
    techRequired    -> DROPPED          (its values are RP-1 tech IDs; none exist in AXE's from-scratch
                                         tree, and GetTechnologyState() returns Unavailable rather than
                                         erroring on an unknown ID, so porting it would silently zero
                                         those parts' capacity forever. The AXE tree node is the gate.)

Parts whose ModuleAvionics came from RP-1's own blanket fallback (Avionics.cfg:11 -- every uncrewed
ModuleCommand part with no avionics gets massLimit 0 / allowAxial false) are NOT emitted individually;
AXE's equivalent blanket rule at the bottom of the generated file covers them, and covers parts RP-1
never saw. They are distinguishable because only the blanket sets canPermaDisable = false.

Usage:  python tools/build_fixed_avionics.py [--check]
        --check  exit 1 if the generated file would change (CI guard)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RP1_CACHE = REPO.parent / "ksp_rp1_expanded" / "GameData" / "ModuleManager.ConfigCache"
RP1_TABLE = REPO.parent / "ksp_rp1_expanded" / "GameData" / "RP-1" / "Avionics.cfg"

# AXE-authored capacities -- parts RP-1's own table never names, so the port alone leaves them in the
# blanket zero and they ship permanently dumb. Applied last, after both RP-1 passes, so they win.
# Every entry states its derivation, the same way RP-1 annotates its table ("Cassini 5712 kg Launch
# mass" -> 6.0 t). Keep this SMALL: it is an addendum for real gaps, not a second balance table.
AXE_AUTHORED: dict[str, dict] = {
    # Saturn I Instrument Unit [3.9 m]. RP-1 rates its three identical twins at 1500 t
    # (bluedog_Saturn_S4_InstrumentUnit|SXT375mProbe|RSBprobeSaturn2, Avionics.cfg:669) and declares
    # THIS part identical to them (identicalParts.cfg:605) -- but never lists it in the avionics table,
    # so RP-1 ships it dumb too. The gap only bites here because all three twins are unreachable in
    # both installs (BDB and RSB not installed; SXT375mProbe absent from both config caches), which
    # leaves this ring and the IB/V one below as the only Saturn IUs anyone can actually fly.
    # 500 t: the Saturn I's own launch mass, user call 2026-08-24.
    "RO-SaturnI-IU": {"capacity": 500.0, "allowAxial": True, "interplanetary": False},
    # Saturn IB/V Instrument Unit [6.6 m]. Same gap, same reasoning. 3000 t = the Saturn V's launch
    # mass; the Saturn I's 500 would leave the BIGGER ring unable to steer its own rocket.
    "restock-drone-core-375-1": {"capacity": 3000.0, "allowAxial": True, "interplanetary": False},
}
AXE_CACHE = REPO.parent / "Instance" / "GameData" / "ModuleManager.ConfigCache"
OUT = REPO / "GameData" / "RP-AXE" / "design" / "Parts" / "AxeFixedAvionics.cfg"

# The shd_* node that gates a hardened unit's hibernation. First real Shielded rung in AXE's ladder
# (design/Tree/AxeAvionicsCore.cfg TIER gnc_basicAvionics -> shTech = shd_basicAvionics).
SHIELD_TECH = "shd_basicAvionics"


def iter_parts(cache_text: str):
    """Yield (part_name, node_text) for every PART node in a ModuleManager config cache."""
    for match in re.finditer(r"\tPART\n\t\{\n", cache_text):
        start = match.start()
        name = re.search(r"^\t\tname = (\S+)\s*$", cache_text[start : start + 400], re.M)
        if not name:
            continue
        idx = cache_text.index("{", start)
        depth = 0
        end = idx
        while True:
            if cache_text[end] == "{":
                depth += 1
            elif cache_text[end] == "}":
                depth -= 1
            if depth == 0:
                break
            end += 1
        yield name.group(1), cache_text[start : end + 1]


def avionics_block(node: str) -> str | None:
    """The ModuleAvionics MODULE body from a resolved PART node, if it has one."""
    at = node.find("name = ModuleAvionics")
    if at < 0:
        return None
    # far enough to cover every key the module writes, short enough not to run into the next module
    return node[at : at + 400]


def parse_bool(block: str, key: str, default: bool) -> bool:
    m = re.search(rf"{key} = (\S+)", block)
    return default if not m else m.group(1).strip().lower() in ("true", "1")


def parse_table() -> dict[str, dict]:
    """Read RP-1's authored massLimit table straight out of Avionics.cfg.

    The resolved cache is authoritative, but it only contains parts INSTALLED in the RP-1 instance. AXE
    ships mods RP-1's install didn't have, and several of those parts are authored in this table anyway
    (GuidanceStart1m, the V-2/early guidance ring, is authored at 20 t but absent from the RP-1 cache).
    Without this pass those parts fall through to the blanket zero and are silently, permanently dumb --
    which for a guidance ring is exactly backwards. Later blocks win, matching ModuleManager's own
    top-to-bottom ordering within a file.
    """
    if not RP1_TABLE.exists():
        return {}
    text = RP1_TABLE.read_text(encoding="utf-8", errors="replace")
    out: dict[str, dict] = {}
    for m in re.finditer(r"^@PART\[([^\]]+)\][^\n{]*\n\{", text, re.M):
        idx = text.index("{", m.start())
        depth = 0
        end = idx
        while end < len(text):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        block = text[idx : end + 1]
        limit = re.search(r"%?massLimit = (\S+)", block)
        if not limit:
            continue
        entry = {
            "capacity": float(limit.group(1)),
            "allowAxial": parse_bool(block, r"%?allowAxial", True),
            "interplanetary": parse_bool(block, r"%?interplanetary", True),
        }
        for name in m.group(1).split("|"):
            out[name.strip()] = entry
    return out


def collect() -> tuple[list[dict], list[str], list[str], list[str]]:
    rp1 = RP1_CACHE.read_text(encoding="utf-8", errors="replace")
    axe_names = {name for name, _ in iter_parts(AXE_CACHE.read_text(encoding="utf-8", errors="replace"))}
    table = parse_table()

    entries, blanket, seen = [], [], set()
    for name, node in iter_parts(rp1):
        block = avionics_block(node)
        if block is None:
            continue
        limit = re.search(r"massLimit = (\S+)", block)
        if not limit:
            continue
        cap = float(limit.group(1))
        allow_axial = parse_bool(block, "allowAxial", True)
        interplanetary = parse_bool(block, "interplanetary", True)
        can_perma = parse_bool(block, "canPermaDisable", True)

        # RP-1's blanket fallback is the only thing that writes canPermaDisable = false at massLimit 0.
        if cap == 0.0 and not allow_axial and not can_perma:
            blanket.append(name)
            continue

        seen.add(name)
        entries.append(
            {
                "name": name,
                "capacity": cap,
                "allowAxial": allow_axial,
                # A unit that cannot steer has nothing to harden; leaving it unshielded also reproduces
                # RP-1's blanket "disable hibernation on every ModuleCommand part" (Avionics.cfg:2).
                "shielded": interplanetary and cap > 0.0,
                "installed": name in axe_names,
                "axe": False,
            }
        )

    # Table-only parts: authored by RP-1 but absent from its install, so the cache never saw them.
    # Emit any that AXE actually ships (a wildcard pattern can't be checked against the part list, so
    # it is always emitted -- ModuleManager no-ops it if nothing matches).
    table_only = []
    for name, entry in sorted(table.items()):
        if name in seen or name in blanket:
            continue
        wildcard = "*" in name
        if not wildcard and name not in axe_names:
            continue
        table_only.append(name)
        entries.append(
            {
                "name": name,
                "capacity": entry["capacity"],
                "allowAxial": entry["allowAxial"],
                "shielded": entry["interplanetary"] and entry["capacity"] > 0.0,
                "installed": True,
                "axe": False,
            }
        )

    # AXE-authored addendum. These override whatever the two RP-1 passes concluded -- in practice a
    # blanket-zero -- so a part RP-1 forgot is not silently dumb forever. Dropped from `blanket` too,
    # so the run report keeps counting the fallback honestly.
    axe_authored = []
    for name, entry in sorted(AXE_AUTHORED.items()):
        if name not in axe_names:
            continue
        entries = [e for e in entries if e["name"] != name]
        if name in blanket:
            blanket.remove(name)
        axe_authored.append(name)
        entries.append(
            {
                "name": name,
                "capacity": entry["capacity"],
                "allowAxial": entry["allowAxial"],
                "shielded": entry["interplanetary"] and entry["capacity"] > 0.0,
                "installed": True,
                "axe": True,
            }
        )

    entries.sort(key=lambda e: (-e["capacity"], e["name"]))
    return entries, sorted(blanket), table_only, axe_authored


def render(entries: list[dict]) -> str:
    groups: dict[tuple, list[str]] = defaultdict(list)
    for e in entries:
        groups[(e["capacity"], e["allowAxial"], e["shielded"], e["axe"])].append(e["name"])

    lines = [
        "// RP-AXE fixed-capacity avionics -- GENERATED by tools/build_fixed_avionics.py, do not hand-edit.",
        "// ------------------------------------------------------------------------------------------------",
        "// Named parts (capsules, probe buses, guidance rings) carry authored hardware in a fixed model, so",
        "// they get one authored number -- the vessel mass they can steer -- instead of the procedural core's",
        "// player-sized box. Values are RP-1's own hand-authored ModuleAvionics.massLimit table, ported as-is",
        "// (plus a short AXE-authored addendum for parts that table never named -- flagged inline below):",
        "// it encodes per-spacecraft judgement that no part field contains (a part's mass is mostly structure",
        "// and tankage, so deriving capacity from it yields nonsense -- a 150 t launch stand would 'derive'",
        "// ~10 million tonnes). See Source/AXE/Avionics/ModuleAxeFixedAvionics.cs for the full field mapping",
        "// and for why RP-1's techRequired is deliberately NOT ported.",
        "//",
        "// Over capacity LOCKS ATTITUDE (RP-1's rule) rather than applying the procedural core's smooth power",
        "// penalty -- a fixed part has no sizing decision to get wrong, and command/staging/throttle keep",
        "// working. `shielded` is baked per part (from RP-1's `interplanetary`) and still gated on researching",
        f"// {SHIELD_TECH}; its effect is whether the unit may hibernate.",
        "//",
        "// :LAST[RP-AXE] so this lands after the kept :FOR[RP-0] pass and BEFORE the :FINAL blanket rule at the",
        "// bottom of this file, which then only catches what is left over.",
        "",
    ]

    for (cap, axial, shielded, axe), names in sorted(groups.items(), key=lambda kv: (-kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        tag = f"{cap:g} t" if cap > 0 else "payload only (no steering)"
        note = []
        if axial:
            note.append("axial thrust retained over capacity")
        if shielded:
            note.append("radiation-hardened")
        suffix = f" -- {', '.join(note)}" if note else ""
        lines.append(f"// {tag}{suffix}")
        if axe:
            lines.append("// AXE-authored: RP-1's table never rated this part. See AXE_AUTHORED in the generator.")
        lines.append(f"@PART[{'|'.join(sorted(names))}]:LAST[RP-AXE]")
        lines.append("{")
        lines.append("\tMODULE")
        lines.append("\t{")
        lines.append("\t\tname = ModuleAxeFixedAvionics")
        lines.append(f"\t\tcapacityTons = {cap:g}")
        lines.append(f"\t\tallowAxial = {'true' if axial else 'false'}")
        lines.append(f"\t\tshielded = {'true' if shielded else 'false'}")
        if shielded:
            lines.append(f"\t\tshieldedTech = {SHIELD_TECH}")
        lines.append("\t}")
        lines.append("}")
        lines.append("")

    lines += [
        "// --- blanket fallback (ports RP-1 Avionics.cfg:11) ---",
        "// Any uncrewed command part that still has no avionics unit steers nothing. Without this, a bare",
        "// stock ModuleCommand is an unconditional full-control bypass in AxeControlLockerUtils -- which is",
        "// exactly what made every named probe core, and every ModularLaunchPads launch stand, silently grant",
        "// unlimited guided control. RP-1 never hit that because this rule covered everything its table",
        "// missed. allowAxial = false: a part nobody authored gets no axial escape hatch either.",
        "//",
        "// :FINAL so it runs after every :LAST[RP-AXE] assignment above and can see what they added. The",
        "// !MODULE checks make it strictly a fallback -- it never overwrites an authored value.",
        "@PART[*]:HAS[@MODULE[ModuleCommand]:HAS[~minimumCrew[>0]],!MODULE[ModuleAxeAvionics],!MODULE[ModuleAxeFixedAvionics]]:FINAL",
        "{",
        "\tMODULE",
        "\t{",
        "\t\tname = ModuleAxeFixedAvionics",
        "\t\tcapacityTons = 0",
        "\t\tallowAxial = false",
        "\t\tshielded = false",
        "\t}",
        "}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if the generated file would change")
    args = ap.parse_args()

    entries, blanket, table_only, axe_authored = collect()
    text = render(entries)

    installed = sum(1 for e in entries if e["installed"])
    zero = sum(1 for e in entries if e["capacity"] == 0)
    print(f"authored entries : {len(entries)} ({installed} installed in the AXE instance)")
    print(f"  from RP-1 cache: {len(entries) - len(table_only) - len(axe_authored)}")
    print(f"  from Avionics.cfg only (absent from RP-1's install): {len(table_only)}")
    if table_only:
        print(f"    {', '.join(table_only[:10])}{' ...' if len(table_only) > 10 else ''}")
    print(f"  of which 0 t   : {zero} (explicitly authored as payload-only by RP-1)")
    print(f"  AXE-authored   : {len(axe_authored)} (gaps RP-1's table never named)")
    if axe_authored:
        print(f"    {', '.join(axe_authored)}")
    print(f"blanket-covered  : {len(blanket)} parts left to the :FINAL fallback")
    print(f"distinct groups  : {len({(e['capacity'], e['allowAxial'], e['shielded'], e['axe']) for e in entries})}")

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"OUT OF DATE: {OUT.relative_to(REPO)} -- re-run tools/build_fixed_avionics.py", file=sys.stderr)
            return 1
        print("up to date")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
