#!/usr/bin/env python3
"""Crewed-lab (KerbalismLab) science budget — same basis as tools/science_budget.py (theoretical max
across every body an experiment can run on). Reads the 65 fork cfgs (value, Situation, BodyAllowed,
BodyNotAllowed) + 6 base lab experiments. Body multipliers/biome weights identical to science_budget.py.

Body-type gates -> RSS bodies (Kerbalism conditions): HomeBody=Earth, HomeBodyAndMoons=Earth+Moon,
Moon=Moon, Moons=all moons, Planets=sun-orbiting bodies, Gaseous=gas giants, Atmospheric=has-atmosphere,
Oceanic=Earth, Suns=Sun. Situation maps Kerbalism virtual -> stock: Space->spLow, BodyGlobal->x1."""
import re, os, glob
FORK = os.environ.get("KLE_FORK", r"C:\git\KerbalismLabExperimentsExpandedContinued\GameData\KerbalismLabExperimentsExpandedContinued")

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
    elif bn in B: s-={bn}
    return s

SMAP={"srflanded":0,"srfsplashed":1,"flyinglow":2,"flying":2,"flyinghigh":3,
      "inspacelow":4,"space":4,"inspacehigh":5,"bodyglobal":None,"surface":0}  # index into mult; None=x1

def parse_fork():
    out=[]
    def bb(s,i):
        i=s.find('{',i);d=0;j=i
        while j<len(s):
            if s[j]=='{':d+=1
            elif s[j]=='}':
                d-=1
                if d==0:return s[i+1:j],j
            j+=1
        return "",len(s)
    for p in sorted(glob.glob(os.path.join(FORK,"*.cfg"))):
        if os.path.basename(p)=="InstrumentTagging.cfg": continue
        t=open(p,encoding="utf-8",errors="ignore").read()
        me=re.search(r'KERBALISM_EXPERIMENT',t); sit=ba=bn=""
        if me:
            kb,_=bb(t,me.end())
            for k,var in [("Situation","sit"),("BodyAllowed","ba"),("BodyNotAllowed","bn")]:
                m=re.search(r'(?m)^\s*'+k+r'\s*=\s*(\S+)',kb)
                if m:
                    if k=="Situation": sit=m.group(1)
                    elif k=="BodyAllowed": ba=m.group(1)
                    else: bn=m.group(1)
        ml=re.search(r'@LAB_EXPERIMENTS',t); val=0.0
        if ml:
            lb,_=bb(t,ml.end()); mv=re.search(r'(?m)^\s*value\s*=\s*([0-9.]+)',lb)
            if mv: val=float(mv.group(1))
        out.append((os.path.basename(p)[:-4],val,sit,ba,bn))
    return out

# 6 base lab experiments (universal, situations from StockGroups-Lab.cfg comments)
BASE=[("CHILLED",24,"Space","",""),("RELAX",28,"SrfLanded@Biomes","",""),("JAMMED",30,"InSpaceLow","",""),
      ("TRAPPED",38,"SrfLanded","",""),("SALINE",27,"SrfSplashed@Biomes","",""),("BIRDIE",14,"Flying@Biomes","","")]

rows=parse_fork()+BASE

def sci(val,sit,body):
    mult,bsum,_=B[body]; sk=sit.split("@")[0].lower()
    idx=SMAP.get(sk,4)
    base = val if idx is None else val*mult[idx]
    if "@biomes" in sit.lower() or "@virtualbiomes" in sit.lower(): base*=max(bsum,1)
    return base

avail={b:0.0 for b in B}
per_exp=[]
for name,val,sit,ba,bn in rows:
    bs=bodies_for(ba,bn); tot=0.0
    for b in bs:
        s=sci(val,sit,b); avail[b]+=s; tot+=s
    gate = (f"+{ba}" if ba else "") + (f" -{bn}" if bn else "") or "(any)"
    per_exp.append((name,val,sit,gate.strip(),len(bs),tot))

total=sum(avail.values())
print(f"crewed-lab experiments: {len(rows)} (65 fork + 6 base)")
print(f"TOTAL crewed-lab science (theoretical max, all allowed bodies) = {total:,.0f}")
print(f"  Earth = {avail['Earth']:,.0f}   Earth+Moon = {avail['Earth']+avail['Moon']:,.0f}")
print("\n=== top 12 experiments by total (across allowed bodies) ===")
for name,val,sit,gate,nb,tot in sorted(per_exp,key=lambda x:-x[5])[:12]:
    print(f"  {name:16s} val={val:>4.0f} {sit:22s} gate={gate:18s} bodies={nb:2d}  total={tot:>9,.0f}")
print("\n=== cumulative crewed-lab reachable by era (body reach) ===")
mil=[(-3292,"orbit ~1958"),(-2952,"inner planets ~1961"),(-2612,"crewed+landing ~1964"),(-2272,"adv probes ~1967"),
 (-2102,"Jupiter ~1970"),(-1847,"Saturn ~1972"),(-1200,"Uranus ~1986"),(-657,"Pluto ~2015")]
for mx,lab in mil:
    print(f"  x<= {mx:6d} {lab:22s} {sum(v for b,v in avail.items() if B[b][2]<=mx):12,.0f}")
