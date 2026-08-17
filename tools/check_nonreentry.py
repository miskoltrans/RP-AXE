#!/usr/bin/env python3
"""check_nonreentry.py -- audit ModuleNonReentryRated coverage so a newly-added part can't slip
through untagged.

Why: design/Parts/AxeNonReentryRated.cfg tags atmospheric cockpits + off-world landers so they
burn up on reentry (RP-1's mechanic + rule). It is a STATIC per-part list, so a cockpit/lander
pulled into the curated set later is SILENTLY untagged until someone remembers. This turns that
silent omission into a report -- the same idea as tools/check_tech_refs.py for dangling tech gates.
(The tagging is keyed to PART NAMES, not tree nodes, so it is immune to tree/node edits; this audit
is only about parts being added.)

Reads the live instance ConfigCache (post-patch truth: what actually loaded + what is actually
tagged). Two findings:
  1. REGRESSION (fails, exit 1): a part we SHOULD tag -- RP-1's list, plus AXE's own additions --
     that IS present in the install but is NOT tagged. A straight miss: a selector typo, a renamed
     part, or a shared part newly pulled in. RP-1's list is authoritative here, so this is mechanical.
  2. REVIEW (informational): a crewed part (CrewCapacity>0) that is present + untagged + NOT already
     accounted for (not RP-1's, not an AXE addition, not on the reviewed-exempt list below). These
     are genuinely NEW parts a human must classify: cockpit/lander -> add to AxeNonReentryRated.cfg;
     reentry capsule or station module -> add to REVIEWED_EXEMPT here (RP-1's rule leaves those alone).

Usage:
  python tools/check_nonreentry.py                       # uses the default instance cache below
  python tools/check_nonreentry.py --cache <ConfigCache>
  python tools/check_nonreentry.py --rp1 <TREE-Parts.cfg>  # refresh SHOULD_TAG from RP-1 directly
"""
import argparse, os, re, sys

DEFAULT_CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"
DEFAULT_RP1 = r"C:\git\ksp\RP-1\GameData\RP-1\Tree\TREE-Parts.cfg"

# RP-1's authoritative ModuleNonReentryRated set (RP-1/GameData/RP-1/Tree/TREE-Parts.cfg, ? -> space):
# atmospheric/spaceplane cockpits + off-world landers. `?` in RP-1's selectors is a space in the real
# part name. Refresh with --rp1 if RP-1 ever changes the list.
RP1_TAGGED = {
    "25mKossak", "625mBonny", "ALCOR_LanderCapsule", "F-104 Cockpit", "F8f Bearcat Cockpit",
    "fightercockpit", "fighterinlinecockpit", "Focke-Wulf Bearcat Cockpit", "FS_BiplaneCockpit",
    "FSfighterCockpit", "Interceptor Cockpit", "landerCabinMedium", "landerCabinSmall",
    "LEM_ASCENT_STAGE", "Mark1Cockpit", "Mark2Cockpit", "MEMLander", "MEMLanderSXT", "Mk1 S39 Cockpit",
    "Mk1 Su30 Cockpit", "mk2Cockpit_Standard", "mk2CrewCabin", "mk2LanderCabin", "mk2LanderCabin_v2",
    "oldfightercockpit", "rn_lk_lander", "ROC-LEMAscent", "ROC-LEMAscentBDB", "ROC-LEMAscentTaxiBDB",
    "ROC-LEMShelterBDB", "RO-FighterInlineCockpit", "RO-OldFighterCockpit", "RO-X1Cockpit",
    "RP0Nose-Cockpit", "SXTBuzzard", "SXTClyde", "SXTEntenteCordiale", "SXTke111", "SXTmk3Cockpit52",
    "SXTOsaulNoseCockpitAn225", "SXTOsualRadCockpit", "Trainer Cockpit", "Typhoon Cockpit", "X1_Crew",
    "zerocockpit",
}
# AXE-only parts we deliberately tag beyond RP-1's list (design/Parts/AxeNonReentryRated.cfg).
AXE_EXTRA = {"SXTLander"}   # PPD-8 Lander Can

# AXE crewed parts reviewed 2026-07-14 and deliberately LEFT untagged (RP-1's rule exempts them):
# orbital station / lab modules (never reenter), ModularLaunchPads crew arms/elevators/towers (ground
# support, never fly), reentry-rated capsules (KV reentry vehicles, Mk2 pod).
# (restock-airlock-1 -- "a docking airlock" -- was exempt here until 2026-08-18; uncurated now, see
#  tools/build_manifest.py's cuts block.)
# When the audit flags a NEW part that belongs here, add it. Regenerate wholesale if the mod set changes.
REVIEWED_EXEMPT = {
    "acamar_crew_s2_1", "acamar_science_processor_s2_1", "AM_MLP_GeneralCrewArm",
    "AM_MLP_GeneralCrewArmSmallMount", "AM_MLP_GeneralCrewElevator", "AM_MLP_GeneralCrewElevator2",
    "AM_MLP_GeneralCrewElevatorMini", "AM_MLP_GeneralCrewElevatorSmall",
    "AM_MLP_LaunchStandCrewElevatorAtlas", "AM_MLP_LaunchStandCrewElevatorGemini",
    "AM_MLP_LaunchStandCrewElevatorMercury", "AM_MLP_SaturnTowerBase", "AM_MLP_SaturnTowerBaseSquare",
    "AM_MLP_ShuttleLauncherFSSBase", "AM_MLP_ShuttleSLC6TowerCore", "AM_MLP_ShuttleSLC6TowerCrew",
    "AM_MLP_ShuttleSLC6TowerIntertank", "AM_MLP_ShuttleSLC6TowerTop", "AM_MLP_SoyuzLaunchBaseElevator",
    "AM_MLP_SoyuzLaunchBaseGantry", "aquarius_crew_s1p5_1", "aquila_crew_s1_1", "aquila_crew_s1_3",
    "aquila_crew_s1p5_2", "aquila_lab_s1_1", "aquila_lab_s1p5_1", "aquila_lab_s1p5_2",
    "aquila_node_s0p5_2", "eridani_crew_s1p5_1", "eridani_crew_s2_1", "eridani_crew_s2_s1p5_1",
    "eridani_node_adapter_s1p5_s0p5_1", "hadar_crew_s1_1", "hadar_crew_s1_2", "kv1Pod", "kv2Pod",
    "kv3Pod", "mira_crew_s1p2_1", "Mk2Pod", "ro_kvant-2_crew_s1p5_2",
    "ro_Nauka_crew_s1p5_2", "ro_Nauka_node_s0p5_2", "ro_priroda_crew_s1p5_2", "ro_spektr_crew_s1p5_2",
    "ro_TKS_crew_s1p5_2", "ro_Zarya_crew_s1p5_2", "ro_Zvezda_crew_s1p5_1", "ro_Zvezda_crew_s2_1",
    "ro_Zvezda_crew_s2_s1p5_1", "ro_Zvezda_node_adapter_s1p5_s0p5_1",
}


def parse_cache(path):
    """From a ModuleManager.ConfigCache return (crewed, tagged, present) sets of part names. A part is
    'tagged' if its OWN block contains a MODULE named ModuleNonReentryRated; 'crewed' if CrewCapacity>0."""
    crewed, tagged, present = set(), set(), set()
    pname = None
    crew = 0
    has = False
    in_part = False

    def flush():
        if pname:
            present.add(pname)
            if crew > 0:
                crewed.add(pname)
            if has:
                tagged.add(pname)

    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if line == "\tPART":
                flush()
                pname, crew, has, in_part = None, 0, False, True
                continue
            if not in_part:
                continue
            if pname is None:
                m = re.match(r"\t\tname = (.+)$", line)
                if m:
                    pname = m.group(1)
                continue
            m = re.match(r"\t\tCrewCapacity = (\d+)", line)
            if m:
                crew = int(m.group(1))
                continue
            if "name = ModuleNonReentryRated" in line:
                has = True
    flush()
    return crewed, tagged, present


def rp1_from_file(path):
    """From a TREE-Parts.cfg return (tagged, known): the parts RP-1 adds ModuleNonReentryRated to, and
    EVERY part RP-1 patches (its full known set). `known` lets us suppress parts RP-1 deliberately left
    untagged (reentry capsules, stations) from REVIEW -- for those we follow RP-1's decision, not review."""
    tagged, known = set(), set()
    cur = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*@PART\[([^\]]+)\]", line)
        if m:
            cur = [p.replace("?", " ") for p in m.group(1).split("|")]
            known.update(cur)
        elif "name = ModuleNonReentryRated" in line and cur:
            tagged.update(cur)
    return tagged, known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--rp1", help="RP-1 TREE-Parts.cfg to refresh the authoritative tagged list from")
    args = ap.parse_args()

    if not os.path.isfile(args.cache):
        sys.exit(f"ConfigCache not found: {args.cache} (launch KSP once to generate it, or pass --cache)")

    should_tag = set(RP1_TAGGED)
    rp1_known = None
    rp1_path = args.rp1 or (DEFAULT_RP1 if os.path.isfile(DEFAULT_RP1) else None)
    if rp1_path and os.path.isfile(rp1_path):
        refreshed, rp1_known = rp1_from_file(rp1_path)
        if refreshed:
            should_tag = refreshed
        print(f"(read RP-1 from {rp1_path}: {len(should_tag)} tagged, {len(rp1_known)} known parts)")
    should_tag |= AXE_EXTRA

    crewed, tagged, present = parse_cache(args.cache)
    print(f"cache: {args.cache}")
    print(f"tagged in AXE: {len(tagged)}   crewed parts: {len(crewed)}   should-tag list: {len(should_tag)}\n")

    regression = sorted((should_tag & present) - tagged)
    # REVIEW = crewed, untagged, minus: should-tag, our reviewed-exempt list, and everything RP-1 knows
    # (for RP-1-known parts we follow RP-1's own tag/don't-tag decision -- only AXE-only parts need review).
    accounted = should_tag | REVIEWED_EXEMPT | (rp1_known or set())
    review = sorted(crewed - tagged - accounted)

    if regression:
        print(f"REGRESSION ({len(regression)}) -- present in AXE + should be tagged, but ISN'T "
              f"(fix design/Parts/AxeNonReentryRated.cfg):")
        for p in regression:
            print(f"  ! {p}")
        print()
    else:
        print("OK: every should-tag part present in AXE is tagged.")

    if review:
        print(f"\nREVIEW ({len(review)}) -- new untagged crewed part(s), unclassified. Cockpit/lander -> "
              f"tag it in AxeNonReentryRated.cfg; reentry capsule / station -> add to REVIEWED_EXEMPT here:")
        for p in review:
            print(f"  ? {p}")
    else:
        print("REVIEW: none -- every crewed part is tagged, a should-tag, or reviewed-exempt.")

    return 1 if regression else 0


if __name__ == "__main__":
    sys.exit(main())
