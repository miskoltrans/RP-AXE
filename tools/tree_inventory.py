#!/usr/bin/env python3
"""Tree inventory (P1) — the INVERSE rubric: derive the node set from the real part inventory.

For each curated part, pull from the live ModuleManager cache: TechRequired (RP-1's node = a "when"
hint), category, mass, the MODULE signature (the strongest discipline signal), and engine propellants
(cryo vs hypergolic vs kerolox vs solid). Then coarse-classify each part to one of the 18 AXE
disciplines (or flag it CONVERGENCE = an engine/tank/structure whose home is a signature-breakthrough
judgment, not a module lookup). The point is to VALIDATE the 18 with real part-counts and measure how
much of P2 is mechanical (clean module->discipline) vs judgment (convergence outcomes).

Inputs : Instance/GameData/ModuleManager.ConfigCache, manifest/curated-parts.tsv,
         manifest/upgrades-curated.tsv (T3, the ~490 KEEP upgrades that also need homes).
Output : manifest/part-capabilities.tsv  (name, mod, title, category, mass, rp1_tech, kind, disc,
         modules, propellants) + a console summary (per-discipline counts; clean-vs-judgment split).
"""
import os, collections

ROOT  = os.path.dirname(os.path.abspath(__file__))
REPO  = os.path.join(ROOT, "..")
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"
MAN   = os.path.join(REPO, "manifest")

# ---- the 18 disciplines (canonical slugs) ----
DISC = ["Metallurgy","CompositeMaterials","PropellantChemistry","ResourceEngineering","Cryogenics",
        "Thermodynamics","FluidDynamics","ElectricalPower","NuclearEngineering","Aerodynamics",
        "StructuresMechanisms","Robotics","Microelectronics","Computing","GuidanceControl",
        "Telecommunications","OpticsPhotonics","LifeSupport"]

CRYO_PROP   = {"LqdHydrogen","LqdMethane","LH2"}
HYPER_PROP  = {"Aerozine50","UDMH","MMH","NTO","Hydrazine","AK20","AK27","IRFNA-III","IWFNA",
               "Nitrogen2O4","HTP","MON3","MON10","Tonka250","Tonka500","UH25"}
KEROLOX_PROP= {"Kerosene","RP-1","RP1"}
SOLID_PROP  = {"HTPB","PSPC","NGNC","SolidFuel","APCP"}

def load_set(path, col=0):
    out=set()
    with open(path,encoding="utf-8",errors="replace") as f:
        next(f,None)
        for ln in f:
            p=ln.rstrip("\n").split("\t")
            if p and p[col]: out.add(p[col])
    return out

def load_map(path, kcol, vcol):
    out={}
    with open(path,encoding="utf-8",errors="replace") as f:
        next(f,None)
        for ln in f:
            p=ln.rstrip("\n").split("\t")
            if len(p)>max(kcol,vcol) and p[kcol]: out.setdefault(p[kcol], p[vcol])
    return out

def parse_parts(lines):
    """State machine over the merged cache: yield a dict per top-level PART block."""
    n=len(lines); i=0; pending=None; depth=0; stack=[]
    cur=None
    while i<n:
        s=lines[i].strip()
        if s=="PART" and i+1<n and lines[i+1].strip()=="{":
            cur={"name":None,"tech":None,"cat":None,"mass":None,"crew":"0","mods":[],"props":[]}
            depth=0; stack=[]; pending="PART"; i+=1
            # consume this PART block
            while i<n:
                t=lines[i].strip()
                if t=="{":
                    depth+=1; stack.append(pending); pending=None
                elif t=="}":
                    if stack: stack.pop()
                    depth-=1
                    if depth==0: break
                elif "=" in t:
                    k,v=t.split("=",1); k=k.strip(); v=v.strip()
                    top=stack[-1] if stack else None
                    if depth==1:
                        if   k=="name" and cur["name"] is None: cur["name"]=v
                        elif k=="TechRequired": cur["tech"]=v
                        elif k=="category": cur["cat"]=v
                        elif k=="mass" and cur["mass"] is None: cur["mass"]=v
                        elif k=="CrewCapacity": cur["crew"]=v
                    elif depth==2 and top=="MODULE" and k=="name":
                        cur["mods"].append(v)
                    elif top=="PROPELLANT" and k=="name":
                        cur["props"].append(v)
                    pending=None
                else:
                    pending=t
                i+=1
            if cur["name"]: yield cur
        i+=1

SPACECRAFT_SYS = ("ModuleScienceExperiment","ModuleOrbitalScience","ModuleRealAntenna",
                  "ModuleDataTransmitter","ModuleOrbitalScanner","ModuleResourceScanner")

def classify(cat, crew, mods, props):
    """Coarse part -> (kind, candidate discipline). kind in
       CLEAN (module->one discipline) | CONVERGENCE (engine/tank/struct = breakthrough judgment) |
       INTEGRATED (composite spacecraft = P5 checklist case) | SCIENCE | EXPERIMENTAL."""
    M=set(mods)
    has=lambda *xs: any(any(x in m for m in M) for x in xs)
    crewn=0
    try: crewn=int(float(crew))
    except: pass
    # 1) engines are engines even when they carry tanks (home = signature breakthrough, by propellant)
    if has("ModuleEngines","ModuleEnginesRF","ModuleEnginesFX"):
        p=set(props)
        fuel = ("cryo" if p&CRYO_PROP else "hypergolic" if p&HYPER_PROP
                else "kerolox" if p&KEROLOX_PROP else "solid" if p&SOLID_PROP else "other")
        return ("CONVERGENCE", "engine:"+fuel)
    # 2) command pod: integrated spacecraft (probe carrying its own science/antenna/scanner) = P5,
    #    crewed capsule -> LifeSupport, bare probe core -> Computing
    if has("ModuleCommand"):
        if crewn>0: return ("CLEAN","LifeSupport")
        if has(*SPACECRAFT_SYS): return ("INTEGRATED","probe:integrated")
        return ("CLEAN","Computing")
    # 3) clean single-discipline module signals
    if has("ModuleResourceHarvester","ModuleResourceConverter","ModuleAsteroidDrill","ModuleISRU"):
        return ("CLEAN","ResourceEngineering")
    if has("FissionReactor") or (has("Reactor") and has("ModuleActiveRadiator")):
        return ("CLEAN","NuclearEngineering")
    if has("ModuleRTG","ModuleRadioisotope"): return ("CLEAN","NuclearEngineering")
    if has("ModuleDataTransmitter","ModuleRTAntenna","ModuleDeployableAntenna","ModuleRealAntenna"):
        return ("CLEAN","Telecommunications")
    if has("ModuleDeployableSolarPanel","ModuleCurvedSolarPanel","ModuleROSolarPanel"):
        return ("CLEAN","ElectricalPower")
    if has("ModuleGenerator","ModuleFuelCell") or cat=="Electrical": return ("CLEAN","ElectricalPower")
    if has("ModuleParachute","RealChuteModule"): return ("CLEAN","Aerodynamics")
    if has("ModuleProceduralFairing","ProceduralFairingBase","ProceduralFairingSide"):
        return ("CLEAN","Aerodynamics")
    if has("ModuleControlSurface","ModuleLiftingSurface") or cat in ("Aero","Wing","ControlSurface"):
        return ("CLEAN","Aerodynamics")
    if has("ModuleDockingNode"): return ("CLEAN","StructuresMechanisms")
    if has("ModuleWheelBase","KFModuleWheel","ModuleWheelMotor","ModuleWheelSuspension",
           "ModuleRoboticServo","ModuleRoboticController","ModuleRoboticArm"):
        return ("CLEAN","Robotics")
    if has("ModuleActiveRadiator","ModuleRadiator","HeatPump"): return ("CLEAN","Thermodynamics")
    if has("ModuleAblator","ModuleHeatShield"): return ("CLEAN","CompositeMaterials")
    if has("ModuleScienceExperiment","ModuleOrbitalScience","DMModuleScienceAnimate",
           "ModuleGroundExperiment","ModuleScienceLab","ModuleOrbitalScanner"):
        return ("SCIENCE","science:scattered")
    if has("ModuleRCSFX","ModuleRCS"): return ("CONVERGENCE","rcs")
    if has("ModuleReactionWheel"): return ("CLEAN","GuidanceControl")
    # 4) raw structure / tanks = convergence
    if has("ModuleFuelTanks","ModuleProceduralTank") or cat=="FuelTank":
        return ("CONVERGENCE","tank")
    if cat in ("Structural","Construction","Coupling") or has("ModuleDecouple","ModuleAnchoredDecoupler"):
        return ("CONVERGENCE","structure")
    return ("CONVERGENCE","unclassified")

def main():
    curated = load_set(os.path.join(MAN,"curated-parts.tsv"), 1)
    titles  = load_map(os.path.join(MAN,"curated-parts.tsv"), 1, 2)
    mods    = load_map(os.path.join(MAN,"curated-parts.tsv"), 1, 0)
    print(f"curated parts: {len(curated)}")

    with open(CACHE,encoding="utf-8",errors="replace") as f: lines=f.readlines()
    parts={}
    for p in parse_parts(lines):
        if p["name"] in curated and p["name"] not in parts: parts[p["name"]]=p
    print(f"matched in cache: {len(parts)}  (unmatched: {len(curated)-len(parts)})")

    rows=[]
    for name in sorted(parts):
        p=parts[name]
        kind,disc=classify(p["cat"] or "", p["crew"], p["mods"], p["props"])
        rows.append((name, mods.get(name,"?"), titles.get(name,""), p["cat"] or "", p["mass"] or "",
                     p["tech"] or "", kind, disc, ";".join(dict.fromkeys(p["mods"])),
                     ";".join(dict.fromkeys(p["props"]))))

    with open(os.path.join(MAN,"part-capabilities.tsv"),"w",encoding="utf-8") as f:
        f.write("name\tmod\ttitle\tcategory\tmass\trp1_tech\tkind\tdisc\tmodules\tpropellants\n")
        for r in rows: f.write("\t".join(map(str,r))+"\n")

    # ---- summary ----
    print("\n=== kind split (mechanical vs judgment) ===")
    for k,n in collections.Counter(r[6] for r in rows).most_common(): print(f"  {n:>5}  {k}")
    print("\n=== clean discipline counts (module-derived; CONVERGENCE/SCIENCE excluded) ===")
    cd=collections.Counter(r[7] for r in rows if r[6]=="CLEAN")
    for d,n in cd.most_common(): print(f"  {n:>5}  {d}")
    print("  -- disciplines with ZERO clean parts (homed only via convergence/science/upgrades):")
    print("     " + ", ".join(d for d in DISC if d not in cd) or "     (none)")
    print("\n=== convergence/science buckets (need rubric judgment) ===")
    for d,n in collections.Counter(r[7] for r in rows if r[6]!="CLEAN").most_common(): print(f"  {n:>5}  {d}")
    print("\n=== top RP-1 techRequired (the 'when' spread) ===")
    for t,n in collections.Counter(r[5] for r in rows if r[5]).most_common(20): print(f"  {n:>5}  {t}")

    # upgrades that also need homes
    up=os.path.join(MAN,"upgrades-curated.tsv")
    if os.path.exists(up):
        keep=0; ut=collections.Counter()
        with open(up,encoding="utf-8",errors="replace") as f:
            hdr=f.readline().rstrip("\n").split("\t"); di=hdr.index("disposition"); ti=hdr.index("techRequired")
            for ln in f:
                p=ln.rstrip("\n").split("\t")
                if len(p)>di and p[di].startswith("KEEP"): keep+=1; ut[p[ti]]+=1
        print(f"\n=== KEEP upgrades needing homes: {keep} (across {len(ut)} distinct RP-1 techs) ===")
    print("\n-> manifest/part-capabilities.tsv")

if __name__=="__main__": main()
