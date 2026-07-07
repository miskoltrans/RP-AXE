#!/usr/bin/env python3
"""Build the RP-AXE curated part manifest (the SSOT).

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

Sources: ksp_rp1_clean cache, ksp_ro_expanded cache, scratchpad/rp1_cuts_from_packs.txt.
Outputs: manifest/curated-parts.tsv (mod<TAB>name<TAB>title), curated-parts.txt (names).
"""
import os, collections
G=r"C:\git\ksp"
SCRATCH=r"C:\Users\User\AppData\Local\Temp\claude\C--git-ksp\8108a075-9f8b-4a7c-89f0-2cd28a7f8a8f\scratchpad"
OUTDIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","manifest")

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

# the curated expansion part-mods we inherit RP-1's keep from (DMagic + NF-Spacecraft excluded; KF treated as base)
EXPANSION_MODS={"CoatlAerospace","CryoEngines","FarFutureTechnologies","HullCameraVDS","KerbalAtomics",
  "KerwisChineseAerospacePack","NearFutureAeronautics","NearFutureConstruction","NearFutureElectrical",
  "NearFutureExploration","NearFutureLaunchVehicles","NearFuturePropulsion","NearFutureSolar","Tantares",
  "RN_Soviet_Probes","RN_US_Probes","RocketMotorMenagerie","StationPartsExpansionRedux","UniversalStorage2",
  "SCANsat"}

US2_WEDGES={  # RP-1-authored, not present in ro_expanded
  "USGooBayWedge":"Biological Sample Capsule","USMatBayWedge":"Crewed Experiment Bay",
  "USFluidSpectroWedge":"Mass Spectrometer Unit","USThermoBaroWedge":"Atmospheric Science Unit",
  "USAccelGravWedge":"Orbital Science Unit"}

ADD={  # our divergences (names; mod/title resolved from ro_expanded)
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
  "aquila_sensor_synthetic_aperture_radar_srf_1","aquila_sensor_visible_light_telescope_s0_1",
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
  "DFH-1","proceduralTankOre","RO-SaturnI-IU","restock-drone-core-375-1","restock-airlock-1",
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
