#!/usr/bin/env python3
"""Crewed-lab (KerbalismLab) science budget — same basis as tools/science_budget.py (theoretical max
across every body an experiment can run on).

Reads the SHIPPED AXE configs (GameData/RP-AXE/design/Science/KerbalismLab), not the upstream fork:
what AXE ships is what the budget must describe. Set KLE_SRC to point elsewhere.

⚠ The payout field is `scienceCap`, NOT `baseValue`. Kerbalism 3.x:
    ExperimentInfo:  DataSize        = baseValue * dataScale        (applyScienceScale=true)
                     ScienceCap      = scienceCap * ScienceGainMultiplier
    SubjectData:     ScienceMaxValue = ScienceCap * Situation.SituationMultiplier
                     SciencePerMB    = ScienceMaxValue / DataSize
A completed run collects DataSize MB and therefore banks exactly `scienceCap * situationMultiplier`.
`baseValue` only sizes the data stream. The fork authors its balance in the group `value` field, which
Framework-3 writes to `baseValue` — so `value` only becomes the payout once scienceCap tracks baseValue
(the framework does this globally in Patches-Global.cfg; AXE does it in Framework-6-ScienceCap.cfg).

Run with --model current|fixed|both (default both):
  current = whatever scienceCap literally is in the shipped cfgs
  fixed   = scienceCap == the authored group `value`
"""
import re, os, glob, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("KLE_SRC", os.path.join(HERE, "..", "GameData", "RP-AXE", "design", "Science", "KerbalismLab"))

# body -> ([landed,splashed,flyLow,flyHigh,spLow,spHigh], biomesum, era reach)  (same as science_budget.py)
B={
 "Earth":([0.00001,0.00001,0.001,0.6,1,1.25],12.0,-3292),"Moon":([3,0,0,0,2,1.5],8.5,-3292),
 "Venus":([8,0,12,7,3,3],8.0,-2952),"Mars":([7,0,7,6,3,3],19.0,-2952),"Mercury":([40,0,29,21,4,4],8.0,-2612),
 "Phobos":([4,0,5,4.5,4,4],2.0,-2612),"Deimos":([4,0,5,4.5,4,4],2.0,-2612),"Vesta":([20,0,12,7,5,4],14.0,-2272),
 "Ceres":([20,0,12,7,5,4],11.0,-2272),"Jupiter":([0,0,24,15,10,6],6.0,-2102),"Io":([30,0,24,15,15,8],7.0,-2102),
 "Europa":([30,0,24,15,15,8],6.0,-2102),"Ganymede":([30,0,24,15,15,8],8.0,-2102),"Callisto":([30,0,24,15,15,8],8.0,-2102),
 "Saturn":([0,0,26,17,12,8],7.0,-1847),"Titan":([35,0,26,17,15,10],7.0,-1847),"Enceladus":([35,0,26,17,15,10],4.0,-1847),
 "Mimas":([35,0,26,17,15,10],6.0,-1847),"Tethys":([35,0,26,17,15,10],9.5,-1847),"Dione":([35,0,26,17,15,10],6.0,-1847),
 "Rhea":([35,0,26,17,15,10],5.0,-1847),"Iapetus":([35,0,26,17,15,10],6.0,-1847),"Uranus":([0,0,28,20,18,13],6.0,-1200),
 "Ariel":([40,0,28,20,18,13],3.0,-1200),"Miranda":([40,0,28,20,18,13],6.0,-1200),"Titania":([40,0,28,20,18,13],7.0,-1200),
 "Umbriel":([40,0,28,20,18,13],5.0,-1200),"Oberon":([40,0,29,21,23,18],4.0,-1200),"Neptune":([0,0,29,21,20,15],6.0,-900),
 "Triton":([40,0,29,21,23,18],9.0,-900),"Pluto":([50,0,29,21,30,25],20.0,-657),"Charon":([50,0,29,21,30,25],0.0,-657),
 "Sun":([0,0,0,0,1,1],0.0,-2952),  # solar exp done in inner-system solar orbit; nominal x1, no biomes
}
ALL=set(B)-{"Sun"}
MOONS={"Moon","Phobos","Deimos","Io","Europa","Ganymede","Callisto","Titan","Enceladus","Mimas","Tethys",
 "Dione","Rhea","Iapetus","Ariel","Miranda","Titania","Umbriel","Oberon","Triton","Charon"}
PLANETS=ALL-MOONS                                   # sun-orbiting (incl dwarfs Vesta/Ceres/Pluto)
GASEOUS={"Jupiter","Saturn","Uranus","Neptune"}
ATMO={"Earth","Venus","Mars","Titan","Jupiter","Saturn","Uranus","Neptune"}
OCEANIC={"Earth"}

def bodies_for(ba,bn):
    if   ba=="HomeBody": s={"Earth"}
    elif ba=="HomeBodyAndMoons": s={"Earth","Moon"}
    elif ba=="Moon": s={"Moon"}
    elif ba=="Moons": s=set(MOONS)
    elif ba=="Planets": s=set(PLANETS)
    elif ba=="Gaseous": s=set(GASEOUS)
    elif ba=="Atmospheric": s=set(ATMO)
    elif ba=="Oceanic": s=set(OCEANIC)
    elif ba=="Suns": s={"Sun"}
    elif ba in B: s={ba}
    else: s=set(ALL)
    if   bn=="HomeBody": s-={"Earth"}
    elif bn=="HomeBodyAndMoons": s-={"Earth","Moon"}
    elif bn=="Gaseous": s-=GASEOUS
    elif bn=="Atmospheric": s-=ATMO
    elif bn=="Suns": s-={"Sun"}
    elif bn in B: s-={bn}
    return s

SMAP={"srflanded":0,"srfsplashed":1,"flyinglow":2,"flying":2,"flyinghigh":3,
      "inspacelow":4,"space":4,"inspacehigh":5,"bodyglobal":None,"surface":0}  # index into mult; None=x1

def block(s,i):
    """return the text of the {...} block starting at/after index i"""
    i=s.find('{',i); d=0; j=i
    while j<len(s):
        if s[j]=='{': d+=1
        elif s[j]=='}':
            d-=1
            if d==0: return s[i+1:j],j
        j+=1
    return "",len(s)

def parse_experiments():
    """-> list of dicts from the shipped per-experiment cfgs (65) + the 6 base exps in Framework-2."""
    out=[]
    for p in sorted(glob.glob(os.path.join(SRC,"Experiments","*.cfg"))):
        t=open(p,encoding="utf-8",errors="ignore").read()
        stem=os.path.basename(p)[:-4]
        d={"name":stem,"src":"fork","sit":[],"ba":"","bn":"","cap":0.0,"value":0.0,
           "crew":"","tech":"","req":"","duration":0.0,"size":0.0}
        # EXPERIMENT_DEFINITION (the literal cap/base as shipped)
        me=re.search(r'(?m)^\s*EXPERIMENT_DEFINITION',t)
        if me:
            eb,_=block(t,me.end())
            for k,fld in [("baseValue","base"),("scienceCap","cap")]:
                m=re.search(r'(?m)^\s*'+k+r'\s*=\s*([0-9.]+)\s*$',eb)
                if m: d[fld]=float(m.group(1))
            mk=re.search(r'KERBALISM_EXPERIMENT',eb)
            if mk:
                kb,_=block(eb,mk.end())
                d["sit"]=re.findall(r'(?m)^\s*Situation\s*=\s*(\S+)',kb)
                for k,fld in [("BodyAllowed","ba"),("BodyNotAllowed","bn")]:
                    m=re.search(r'(?m)^\s*'+k+r'\s*=\s*(\S+)',kb)
                    if m: d[fld]=m.group(1)
        # LAB_EXPERIMENTS group entry (the authored balance)
        ml=re.search(r'@?LAB_EXPERIMENTS',t)
        if ml:
            lb,_=block(t,ml.end())
            for k,fld in [("value","value"),("duration","duration"),("size","size")]:
                m=re.search(r'(?m)^\s*'+k+r'\s*=\s*([0-9.]+)',lb)
                if m: d[fld]=float(m.group(1))
            for k,fld in [("CrewRequirement","crew"),("UnlockTech","tech"),("requirements","req")]:
                m=re.search(r'(?m)^\s*'+k+r'\s*=\s*(\S.*?)\s*(?://.*)?$',lb)
                if m: d[fld]=m.group(1).strip()
        out.append(d)
    out += parse_base()
    return out

# The 6 base lab experiments: group entry lives in Framework-2, the EXPERIMENT_DEFINITION in
# Framework-5 (vendored from KerbalismScienceOnly ScienceDefs-Kerbalism.cfg).
def parse_base():
    out=[]
    f2=os.path.join(SRC,"Framework-2-LabGroup.cfg")
    f5=os.path.join(SRC,"Framework-5-BaseExperimentDefs.cfg")
    if not os.path.exists(f2): return out
    t=open(f2,encoding="utf-8",errors="ignore").read()
    ml=re.search(r'LAB_EXPERIMENTS',t)
    if not ml: return out
    lb,_=block(t,ml.end())
    defs={}
    if os.path.exists(f5):
        dt=open(f5,encoding="utf-8",errors="ignore").read()
        for m in re.finditer(r'(?m)^\s*EXPERIMENT_DEFINITION',dt):
            eb,_=block(dt,m.end())
            mid=re.search(r'(?m)^\s*id\s*=\s*(\S+)',eb)
            if not mid: continue
            e={"sit":[],"ba":"","bn":"","cap":0.0}
            mc=re.search(r'(?m)^\s*scienceCap\s*=\s*([0-9.]+)',eb)
            if mc: e["cap"]=float(mc.group(1))
            mk=re.search(r'KERBALISM_EXPERIMENT',eb)
            if mk:
                kb,_=block(eb,mk.end())
                e["sit"]=re.findall(r'(?m)^\s*Situation\s*=\s*(\S+)',kb)
                for k,fld in [("BodyAllowed","ba"),("BodyNotAllowed","bn")]:
                    mm=re.search(r'(?m)^\s*'+k+r'\s*=\s*(\S+)',kb)
                    if mm: e[fld]=mm.group(1)
            defs[mid.group(1).replace("kerbalism_","")]=e
    # each base exp is a named sub-node of LAB_EXPERIMENTS
    for name in ("CHILLED","RELAX","JAMMED","TRAPPED","SALINE","BIRDIE"):
        m=re.search(r'(?m)^\s*'+name+r'\s*(?://.*)?$',lb)
        if not m: continue
        gb,_=block(lb,m.end())
        d={"name":name,"src":"base","sit":[],"ba":"","bn":"","cap":0.0,"value":0.0,
           "crew":"","tech":"","req":"","duration":0.0,"size":0.0}
        for k,fld in [("value","value"),("duration","duration"),("size","size")]:
            mm=re.search(r'(?m)^\s*'+k+r'\s*=\s*([0-9.]+)',gb)
            if mm: d[fld]=float(mm.group(1))
        for k,fld in [("CrewRequirement","crew"),("UnlockTech","tech"),("requirements","req")]:
            mm=re.search(r'(?m)^\s*'+k+r'\s*=\s*(\S.*?)\s*(?://.*)?$',gb)
            if mm: d[fld]=mm.group(1).strip()
        d.update({k:defs.get(name,{}).get(k,d[k]) for k in ("sit","ba","bn","cap")})
        d["missing_def"]= name not in defs
        out.append(d)
    return out

def sci(payout,sit,body):
    """science banked for one completed run of `sit` at `body` (Kerbalism: cap * situationMultiplier)."""
    mult,bsum,_=B[body]; sk=sit.split("@")[0].lower()
    idx=SMAP.get(sk,4)
    base = payout if idx is None else payout*mult[idx]
    if "@biomes" in sit.lower() or "@virtualbiomes" in sit.lower(): base*=max(bsum,1)
    return base

def run(rows,model,verbose=True):
    avail={b:0.0 for b in B}; per_exp=[]
    for d in rows:
        payout = d["value"] if model=="fixed" else d["cap"]
        bs=bodies_for(d["ba"],d["bn"]); tot=0.0
        sits=d["sit"] or ["InSpaceLow"]
        for b in bs:
            for s in sits:
                v=sci(payout,s,b); avail[b]+=v; tot+=v
        gate=((f"+{d['ba']}" if d['ba'] else "")+(f" -{d['bn']}" if d['bn'] else "")).strip() or "(any)"
        per_exp.append((d["name"],payout,"/".join(sits),gate,len(bs),tot,d))
    total=sum(avail.values())
    if verbose:
        print(f"TOTAL crewed-lab science (theoretical max, all allowed bodies) = {total:,.0f}")
        print(f"  Earth = {avail['Earth']:,.0f}   Earth+Moon = {avail['Earth']+avail['Moon']:,.0f}")
        print("\n  === top 12 experiments by total ===")
        for name,pay,sit,gate,nb,tot,_ in sorted(per_exp,key=lambda x:-x[5])[:12]:
            print(f"    {name:16s} pay={pay:>5.0f} {sit:26s} gate={gate:18s} bodies={nb:2d}  total={tot:>10,.0f}")
        print("\n  === cumulative reachable by era (body reach) ===")
        for mx,lab in [(-3292,"orbit ~1958"),(-2952,"inner planets ~1961"),(-2612,"crewed+landing ~1964"),
                       (-2272,"adv probes ~1967"),(-2102,"Jupiter ~1970"),(-1847,"Saturn ~1972"),
                       (-1200,"Uranus ~1986"),(-657,"Pluto ~2015")]:
            print(f"    x<= {mx:6d} {lab:22s} {sum(v for b,v in avail.items() if B[b][2]<=mx):12,.0f}")
    return total,avail,per_exp

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--model",choices=["current","fixed","both"],default="both")
    a=ap.parse_args()
    rows=parse_experiments()
    nfork=sum(1 for d in rows if d["src"]=="fork"); nbase=len(rows)-nfork
    print(f"source: {os.path.normpath(SRC)}")
    print(f"crewed-lab experiments: {len(rows)} ({nfork} fork + {nbase} base)")
    miss=[d["name"] for d in rows if d.get("missing_def")]
    if miss: print(f"!! base experiments with NO EXPERIMENT_DEFINITION (dead menu entries): {', '.join(miss)}")
    ncapmismatch=sum(1 for d in rows if d["src"]=="fork" and abs(d["cap"]-d["value"])>1e-9)
    print(f"!! fork experiments where scienceCap != authored value (payout is inert): {ncapmismatch}/{nfork}")
    for model in (["current","fixed"] if a.model=="both" else [a.model]):
        print(f"\n{'='*78}\n== MODEL: {model}  (payout field = {'authored value' if model=='fixed' else 'scienceCap as shipped'})\n{'='*78}")
        run(rows,model)
