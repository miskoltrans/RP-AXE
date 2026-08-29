#!/usr/bin/env python3
"""How manifest/curated-parts.tsv was derived -- the RECORD, not a build step.

⚠ THIS SCRIPT DOES NOT RUN, AND THAT IS FINE. It generated the manifest once, at T1 (`926453e`,
2026-06-30). Its third input was scratch data that was never checked in and is now gone (see the
exit message below). Re-running it would rebuild all ~1,800 rows from month-old reference caches
to recreate a file the whole tree is already placed against -- risk with no upside.

WHAT IS AUTHORITATIVE: `manifest/curated-parts.tsv`. It is a BUILD INPUT -- build_tree.py reads it
directly, and every part placed in tree/nodes.yaml must appear in it or the build's membership
check complains. The five commits that touched it since T1 all edited this file in lockstep by
hand, which is the workflow, not a lapse.

TO ADD A PART:
  1. add the row to manifest/curated-parts.tsv  (mod<TAB>name<TAB>title)  <- this is the one that counts
  2. mirror it into AXE_PARTS / ADD below, so this record stays a true description of the set
  3. run tools/build_tree.py -- its membership check is what catches a part placed but not curated
NB `manifest/curated-parts.txt` (names only) was a dead twin -- nothing but this script read it, and
it had already drifted (missing the three AXE-* geochemistry parts added 2026-07-29). DELETED
2026-07-29; the write below is left in place so the derivation still reads correctly.

WHAT IS STILL LIVE IN HERE: the data literals. AXE_PARTS, ADD, US2_WEDGES, KEEP_DEPRECATED,
EXPANSION_MODS and the SCANsat cut rationale are the readable statement of *which* parts AXE ships
and why. The curation JUDGEMENT is not here at all -- that is docs/PARTLIST.md, per mod.

TO REVIVE IT AS A GENERATOR (only worth it if a part mod is added or RP-1 is bumped): re-derive the
cuts from RP-1's own configs and check the result into manifest/. Read the exit message first --
there is one specific shortcut that must not be taken.

The derivation it records:

manifest = RP-1 base (rp1_clean)
         + RP-1's expansion keeps  (ro_expanded parts of the curated expansion mods, minus RP-1's cuts)
         + RP-1-authored US2 science wedges (only exist with RP-1 active)
         + our recorded divergences (probe reinstatements, Tantares flagship, NF-Solar tier, Kerwis DFH-1,
           clean-drop reversals)
         - 2 deprecated SXT parts
DMagic + NearFutureSpacecraft are excluded (dropped).

SCANsat is treated as an expansion mod too: RP-1 loads 12 of the 16 parts RO loads (4 more --
SCANsat_Scanner/2/24 and RO-PVO-ORAD -- are stuck on stock-only tech IDs with no RP-1 tree entry and
get pruned by RP-1's tree-validity cleanup). We keep RP-1's 12; see SCANSAT_CUTS below.

Sources it used: ksp_rp1_clean cache, ksp_ro_expanded cache, scratchpad/rp1_cuts_from_packs.txt (gone).
Outputs it produced: manifest/curated-parts.tsv (mod<TAB>name<TAB>title) + curated-parts.txt (now deleted).
"""
import os, collections, sys
G=r"C:\git\ksp"
# The missing input, and the exit that explains it. See the module docstring for why this is a
# recorded state rather than a bug to fix. (Confirmed still gone 2026-07-29.)
SCRATCH=r"C:\Users\User\AppData\Local\Temp\claude\C--git-ksp\8108a075-9f8b-4a7c-89f0-2cd28a7f8a8f\scratchpad"
CUTS_INPUT=os.path.join(SCRATCH,"rp1_cuts_from_packs.txt")
OUTDIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","manifest")

if not os.path.exists(CUTS_INPUT):
    sys.exit(
        "build_manifest.py CANNOT RUN: its third input is gone.\n"
        f"  missing: {CUTS_INPUT}\n"
        "  (the two ConfigCache inputs are fine -- ksp_rp1_clean and ksp_ro_expanded are both present)\n"
        "\n"
        "rp1_cuts_from_packs.txt was a formatted dump of the parts RP-1 DELETES from the curated\n"
        "expansion part-mods, produced in an analysis session whose scratch directory no longer\n"
        "exists. Without it this script cannot tell 'RP-1 cut this' from 'RP-1 kept this', so it\n"
        "cannot reproduce manifest/curated-parts.tsv.\n"
        "\n"
        "TO REVIVE IT, re-derive the cuts from RP-1's own configs (the real source) and check the\n"
        "result into manifest/ rather than a temp dir -- it is derived data this build depends on.\n"
        "\n"
        "DO NOT reconstruct it by subtracting the current TSV from the ro_expanded cache. That makes\n"
        "the script reproduce its own output by construction, so an RP-1 bump that changes the cuts\n"
        "would silently produce no diff -- the offline-fixture trap, in the one place it would cost\n"
        "the most (docs/BUG-CLASSES.md family C).\n"
        "\n"
        "UNTIL THEN the TSV is authoritative and hand-maintained: a new AXE part needs a row there\n"
        "AND an AXE_PARTS entry below (see docs/SCIENCE.md 6). build_tree.py's membership check is\n"
        "what keeps the tree honest about it in the meantime."
    )

def parse_cache(cache):
    with open(cache,encoding="utf-8",errors="replace") as f: lines=f.readlines()
    n=len(lines);cur=None;i=0;out=[]
    while i<n:
        s=lines[i].strip()
        if s.startswith("parentUrl"): cur=s.split("=",1)[1].strip()
        elif s=="PART" or s.startswith("PART "):
            j=i+1
            while j<n and lines[j].strip()!="{": j+=1
            d=0;st=False;name=title=None;k=j
            while k<n:
                t=lines[k].strip()
                if t=="{": d+=1;st=True
                elif t=="}":
                    d-=1
                    if st and d==0: break
                elif d==1 and "=" in t:
                    key=t.split("=",1)[0].strip();val=t.split("=",1)[1].strip()
                    if key=="name" and name is None: name=val
                    elif key=="title" and title is None: title=val
                k+=1
            if name: out.append((cur.split("/")[0] if cur else "?",name,title or ""))
            i=k
        i+=1
    return out

base=parse_cache(os.path.join(G,"ksp_rp1_clean","GameData","ModuleManager.ConfigCache"))
ro_list=parse_cache(os.path.join(G,"ksp_ro_expanded","GameData","ModuleManager.ConfigCache"))
ro={n:(m,t) for m,n,t in ro_list}

# RP-1's cuts from the expansion packs. The dump truncates >34-char names (they merge with the title),
# so recover the true name via longest-prefix match against the clean ro_expanded names of that mod.
ro_names_by_mod=collections.defaultdict(set)
for m,n,t in ro_list: ro_names_by_mod[m].add(n)
cuts=set()
with open(os.path.join(SCRATCH,"rp1_cuts_from_packs.txt"),encoding="utf-8",errors="replace") as f:
    for ln in f:
        if len(ln)<27 or ln.startswith("MOD") or ln.startswith("-"): continue
        mod=ln[0:26].strip(); rest=ln[26:].split()
        if not rest: continue
        cand=rest[0]
        matches=[nm for nm in ro_names_by_mod.get(mod,()) if cand==nm or cand.startswith(nm)]
        cuts.add(max(matches,key=len) if matches else cand)

# RP-1's own cuts from SCANsat (see docstring): the 3 deprecated hidden placeholders plus the one RO
# clone (RO-PVO-ORAD) that never got a TREE-Parts.cfg tech-node remap.
cuts|={"SCANsat_Scanner","SCANsat_Scanner2","SCANsat_Scanner24","RO-PVO-ORAD"}

# OUR cut, not RP-1's (2026-08-18): the ReStockPlus parts that ReStockPlus itself deletes on any install
# with MakingHistory. ReStockPlus/Patches/MakingHistoryPartHiding.cfg puts %TechHidden=True /
# @category=none on every #MHReplacement[True] part :NEEDS[SquadExpansion/MakingHistory], and MH is a HARD
# DEP of RP-AXE -- so these can never be built here. RP-1 "keeps" them only in the sense that
# HardRemoveNonRP0 spares them; verified category=none in ksp_rp1_clean and ksp_rp1_expanded too, i.e.
# dead there as well. 52 ReStockPlus parts carry the MHReplacement flag; these are the only 3 AXE curated.
# The MH originals they stand in for (InflatableAirlock, Decoupler_1p5, Separator_1p5) are absent from
# RP-1, so we inherit RP-1's MH cut rather than substitute them.
cuts|={"restock-decoupler-1875-1","restock-separator-1875-1"}

# the curated expansion part-mods we inherit RP-1's keep from (DMagic + NF-Spacecraft excluded; KF treated as base)
EXPANSION_MODS={"CoatlAerospace","CryoEngines","FarFutureTechnologies","HullCameraVDS","KerbalAtomics",
  "KerwisChineseAerospacePack","NearFutureAeronautics","NearFutureConstruction","NearFutureElectrical",
  "NearFutureExploration","NearFutureLaunchVehicles","NearFuturePropulsion","NearFutureSolar","Tantares",
  "RN_Soviet_Probes","RN_US_Probes","RocketMotorMenagerie","StationPartsExpansionRedux","UniversalStorage2",
  "SCANsat"}

US2_WEDGES={  # RP-1-authored, not present in ro_expanded
  "USGooBayWedge":"Biological Sample Capsule","USMatBayWedge":"Crewed Experiment Bay",
  "USFluidSpectroWedge":"Mass Spectrometer Unit"}
# CUT 2026-08-27 (US2 promotion pass), both formerly here:
#   USAccelGravWedge "Orbital Science Unit" -- carried micrometeoriteDetect, RP0orbitalPurturbation1 and
#     RP0cosmicRay1/2, ALL FOUR of which proceduralAvionics already carries on `start`; the dedicated
#     instruments (RO-Micrometeorite, RO-GeigerMuller, RO-ScintillationCounter, sensorGravimeter) cover
#     them too, so nothing was orphaned. Left gnc_orbitalGravimetry with sensorGravimeter alone.
#   USThermoBaroWedge "Atmospheric Science Unit" -- already homeless: mic_atmoSounding was emptied
#     2026-07-29 because both its experiments were covered elsewhere, and it fell to the sandbox.
# Both are DELETED outright by design/Parts/AxeCutParts.cfg, not merely unplaced -- an uncurated part
# falls through emit_placement_patch to `parking`, and `parking` is meant to stay empty.

AXE_PARTS={  # authored BY AXE, so they exist in no upstream dump -- resolve them here or nowhere
  "AXE-GammaRaySpectrometer":"GR01 - Gamma-Ray Spectrometer",
  "AXE-XRayFluorescence":"XR01 - X-Ray Fluorescence Spectrometer",
  "AXE-NeutronSpectrometer":"NS01 - Neutron Spectrometer",
  # +PART clone of Squad's RelayAntenna100, stripped of every antenna module (design/Science/
  # KerbalismLab/InstrumentTagging.cfg) -- the same 4m dish pointed outward as a passive receiver.
  # It is the ONLY carrier of RadioLabExperimentPackage, so 6 lab experiments are unrunnable
  # without it; added to curated-parts + tel_antennaCatalog 2026-08-25 (it had defaulted to the
  # `parking` holding pen because nothing placed it).
  "AntennaRadioLab":"RA-100T Radio Telescope"}

ADD={  # our divergences (names; mod/title resolved from ro_expanded)
  # UniversalStorage2 service-module system (19), promoted out of the us2_serviceSandbox trial node
  # 2026-08-27. PARTLIST.md originally cut all 29 modular US2 parts as "-> procedural"; the sandbox
  # existed to judge them in the editor, and the verdict was: keep the CORES, the SKINS and the three
  # chemical plants; sack the ACDs, the bulk tank wedges, the battery and the avionics wedge (17 parts,
  # deleted by design/Parts/AxeCutParts.cfg). The US2 shrouds are service-module skins, NOT payload
  # fairings. Diameters are RO metres throughout (RO sets rescaleFactor 1.6 on every US* part).
  "USQuadcore","USPenticore","USHexcore","USOctocore",
  "USCylindricalShroud0625","USCylindricalShroud125","USCylindricalShroud1500","USCylindricalShroud250",
  "USCylindricalShroud125ResizedTo1875-1","USCylindricalShroud1500ResizedTo1875-2",
  "USAdaptorShroud0625","USAdaptorShroud1250","USAdaptorShroud1250Soyuz","USAdaptorShroud1250Vostok",
  "USAdaptorShroud1500","USAdaptorShroud1875",
  "USSabatier","USElektron","USWaterPurifier",
  # Tantares flagship (48)
  "aquarius_crew_s1p5_1","vela_landing_leg_srf_1","vela_landing_leg_srf_2","aquarius_heatshield_s1p5_1",
  "aquarius_drogue_parachute_s0_1","aquarius_parachute_s0p5_1","vela_high_gain_antenna_srf_1",
  "eridani_crew_s2_1","eridani_crew_s2_s1p5_1","eridani_crew_s1p5_1","aquila_node_s0p5_1","eridani_node_adapter_s1p5_s0p5_1",
  "acamar_adapter_s2_s0p5_1","acamar_crew_s2_1","acamar_science_processor_s2_1",
  "ro_kvant-2_adapter_s2_s0p5_1","ro_kvant-2_adapter_s2_s1p5_1","ro_kvant-2_crew_s1p5_2","aquila_crew_s1_3","aquila_lab_s1_1",
  "aquila_adapter_s2_s0p5_1","aquila_adapter_s2_s1p5_1","aquila_crew_s1p5_2","aquila_crew_s1_1","aquila_adapter_s1p5_1","aquila_node_s0p5_2","aquila_node_adapter_s1_1",
  "ro_spektr_adapter_s2_s0p5_1","ro_spektr_adapter_s2_s1p5_1","ro_spektr_crew_s1p5_2","aquila_structural_cone_s1p5_1","aquila_lab_s1p5_1",
  "ro_priroda_adapter_s2_s0p5_1","ro_priroda_adapter_s2_s1p5_1","ro_priroda_crew_s1p5_2","aquila_experiment_rack_s1p5_1","aquila_lab_s1p5_2",
  "rana_mount_srf_1","rana_truss_srf_1","rana_truss_srf_2",
  "aquila_control_s2_1","ro_TKS_adapter_s2_s0p5_1","ro_TKS_adapter_s2_s1p5_1","ro_TKS_crew_s1p5_2","alnair_les_s0_2","sargas_decoupler_s1p5_1",
  "aquila_sensor_synthetic_aperture_radar_srf_1",
  # DROPPED 2026-07-29 (tier-balance audit, docs/TIER-BALANCE.md B): aquila_sensor_visible_light_telescope_s0_1
  # ("Priroda 5 Earth Resources Camera") carried RP0visibleImaging4 (cap 6) as a BARE Experiment module, so
  # its gate was whatever node it sat on -- `experimental`, T1, 1 science. That made the gen-4 camera
  # cheaper and earlier than VI01/VI02/VI03 and killed three optics nodes outright. RO-AdvancedImager
  # already carries VI04 at its proper place in the ladder, so this part was pure duplicate.
  # (Its sibling SAR part carries no experiment at all and stays.)
  # RN-US (16)
  "rn_heliosa_b","rn_juno_spacecraft","rn_lcross_mb","rn_ladee","rn_lro","rn_mariner10","rn_mariner3-4","rn_mariner5",
  "rn_mariner6-7","rn_mariner8-9","rn_mars_observer","rn_sphinx_t3e","rn_tdrs_ag","rn_galileo_scanner","rn_ladee_scanner","rn_magellan_scanner",
  # RN-Soviet (15)
  "luna_als","luna11_als","l11_astro","luna13_als","luna3","luna_astro","luna2","luna_vernier","molniya1","polyot",
  "polyot_side_engine","rn_protonn4_1","rn_protonn6_4","rn_strela3_gonets","rn_venera1",
  # NF-Solar tier (6)
  "nfs-panel-deploying-concentrator-1x4-juno-1","nfs-panel-deploying-blanket-starship-1","nfs-panel-deploying-blanket-dsg-1",
  "nfs-panel-deploying-blanket-arm-1","nfs-panel-deploying-advanced-2x20-hub-1","nfs-panel-deploying-curved-375-1",
  # NFE nuclear fuel cycle (4) -- reprocessor + fuel drums, home the RO reactors' EnrichedUranium/DepletedFuel loop
  "nuclear-recycler-25","nuclearfuel-0625","nuclearfuel-125","nuclearfuel-25",
  # Kerwis DFH-1 + clean-drop reversals
  # (restock-airlock-1 was here as the PARTLIST.md cat-3 "keep the airlock" reversal; withdrawn
  #  2026-08-18 -- ReStockPlus hides it whenever MakingHistory is installed, see the cuts block above.)
  "DFH-1","proceduralTankOre","RO-SaturnI-IU","restock-drone-core-375-1",
  "KF-ScrewDrive","KF-Skid","KF-TrackInverting","KF-TrackLong","KF-TrackMedium","KF-TrackMole","KF-TrackSimple",
  "KF-TrackSmall","KF-TrackSurface","KF-TrackTiny","KF-WheelTruck-Dual","KF-WheelTruck-Single",
}

manifest={}
for m,n,t in base:
    if m=="SXT" and "DEPRECATED" in t.upper(): continue
    manifest[n]=(m,t)
for m,n,t in ro_list:                                  # RP-1's expansion keeps
    if m in EXPANSION_MODS and n not in cuts: manifest[n]=(m,t)
for n,t in US2_WEDGES.items(): manifest[n]=("UniversalStorage2",t)
for n,t in AXE_PARTS.items(): manifest[n]=("RP-AXE",t)
missing=[]
for n in sorted(ADD):
    if n in ro: manifest[n]=ro[n]
    elif n not in manifest: missing.append(n)

os.makedirs(OUTDIR,exist_ok=True)
# Sack every DEPRECATED-titled part from curation: RP-1/RO keep them loadable so old saves don't break,
# but each is a hidden, superseded dupe of a part we already carry — we don't need them. (User call.)
# EXCEPT parts that are deprecated-but-UNIQUE (no non-deprecated counterpart exists): the sample-return
# capsule is the only buildable film/sample-return craft (closes opt_filmReturn's Corona/Discoverer loop;
# kings cmp_ablativeTPS). Nuking it would remove a capability, not a dupe.
# SCANsat_Scanner32 (BTDT) is a false positive of this heuristic: RO's generic cleanup title-tags it
# "(DEPRECATED)" for setting %RODeprecated=True, but RP-1's own TREE-Parts.cfg explicitly re-enables and
# tech-places it (unlike its RADAR/SAR/MULTI siblings, which really are dead and stay cut).
KEEP_DEPRECATED={"RP0-SampleReturnCapsule","RP0-SampleReturnCommand","SCANsat_Scanner32"}
manifest={n:mt for n,mt in manifest.items() if n in KEEP_DEPRECATED or "DEPRECATED" not in mt[1].upper()}

# ---------------------------------------------------------------------------------------------------
# DROP -- parts that reach `manifest` above but that AXE curates OUT. This is the one place where a
# considered AXE judgement subtracts from the RP-1-derived set, so the reasoning lives here in full.
#
# STOCK-POD DUPLICATE PASS (2026-08-06, user call). PARTLIST.md rule 3 -- "from the eligible set,
# exclude REDUNDANT or LOW-VALUE parts" -- and each of these is a reskin of the ROCapsules part sitting
# on the same AXE node, measured, not assumed:
#
#   mk1pod_v2  int_mercuryCapsule  0.725 t / 1 crew / HTP+He RCS   vs ROC-MercuryCMBDB 0.565 t / 1 / HTP+He
#   mk1-3pod   int_apolloCSM       3.644 t / 3 crew / MMH+NTO RCS  vs ROC-ApolloCMBDB  3.583 t / 3 / MMH+MON1
#   kv1Pod     int_vostokCapsule   2.124 t / 1 crew / decoupler    vs ROC-VostokCapsule 0.933 t / 1
#
# The "the stock pod is one part instead of three" defence is FALSE for the first two -- both ROCapsules
# kings carry the same integral RCS (checked in manifest/part-capabilities.tsv, not inferred from the
# name). kv1Pod's integral decoupler is real but duplicates ROC-VostokDecoupler and costs 2.3x the mass
# of the capsule it stands beside, so it flies as a different vehicle rather than an alternative skin.
#
# WHY RP-1 KEEPING THEM IS NOT EVIDENCE: RP-1 is a compatibility layer, not a curation. Its
# `basicCapsules` node carries FIVE Vostok analogues at a matched cost of 1600 (ROC-VostokCapsule,
# IronVostok_Crew_A, restock-pod-sphere-1, rn_vostok_sc, and kv1Pod until 2023) and FOUR Mercury
# analogues (ROC-MercuryCM, mk1pod, mk1pod_v2 at 2468; ROC-MercuryCMBDB at 1700). Matched prices across
# brands is the signature: it prices whichever mod's build of the vehicle you happen to have installed.
# AXE hard-depends on ROCapsules (RP-AXE.netkan `depends`), so the named part is ALWAYS present and the
# fallback those parallel entries buy is worth nothing here. AXE had already dropped every other brand's
# twin on these same nodes (IronVostok, RN Soyuz, ReStock's sphere, ROC-MercuryCM, mk1pod) -- keeping the
# Squad ones was inconsistency, not policy.
#
# NOT dropped, decided separately: ROAdvCapsule (RO's own, and genuinely differs -- integral hypergolic
# RCS where ROC-GeminiCMBDB needs separate OAMS parts) and the landerCabin* / mk2LanderCabin_v2 cans on
# int_compactCrewPod (a generic 1/2/3-crew size ladder, not a reskin of one vehicle).
#
# EFFECT: AXE ships no HardRemoveNonRP0, so a dropped part is not deleted -- emit_placement_patch parks
# it on `parking`, present but unreachable. Reversing any of these is a one-line edit here plus the row
# in curated-parts.tsv.
DROP={"mk1pod_v2","mk1-3pod","kv1Pod"}
manifest={n:mt for n,mt in manifest.items() if n not in DROP}
rows=sorted(manifest.items(),key=lambda kv:(kv[1][0],kv[0]))
with open(os.path.join(OUTDIR,"curated-parts.tsv"),"w",encoding="utf-8") as f:
    f.write("mod\tname\ttitle\n")
    for n,(m,t) in rows: f.write(f"{m}\t{n}\t{t}\n")
with open(os.path.join(OUTDIR,"curated-parts.txt"),"w",encoding="utf-8") as f:
    for n,(m,t) in rows: f.write(n+"\n")

print(f"MANIFEST: {len(manifest)} parts  | cuts loaded {len(cuts)}")
print("missing ADD names:", missing or "none")
bymod=collections.Counter(m for m,_ in manifest.values())
print("\nsanity — curated keeps (expect): Coatl 74, RN_US 75, RN_Soviet 23, Tantares 48, Kerwis 19,")
print("  NF-Propulsion 20, NF-Solar 6, US2 10, SSPX 108, SCANsat 12, DMagic 0, NF-Spacecraft 0:")
for mod in ["CoatlAerospace","RN_US_Probes","RN_Soviet_Probes","Tantares","KerwisChineseAerospacePack",
            "NearFuturePropulsion","NearFutureSolar","UniversalStorage2","StationPartsExpansionRedux",
            "SCANsat","DMagicOrbitalScience","NearFutureSpacecraft","KerbalFoundries","SXT","VenStockRevamp"]:
    print(f"   {mod:<28}{bymod.get(mod,0)}")
print(f"\ntotal mods contributing: {len(bymod)}")
