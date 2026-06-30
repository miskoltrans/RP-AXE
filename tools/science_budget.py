#!/usr/bin/env python3
"""Probe-science budget (RP0* suite) — tree-independent. See docs/SCIENCE.md.

GROUND-TRUTHED inputs (not hand-guessed):
  - per-body situation multipliers: RP-1/Science/BodyScienceParams.cfg (verified), Earth row =
    post AXE GameData/RP-AXE/design/Science/EarthScienceRemoval.cfg (sub-40km zeroed).
  - per-body BIOME weight (summed biome `value`s): read from the RP-1 merged ModuleManager.ConfigCache
    via tools/extract_biomes.py. Regenerate with: python tools/extract_biomes.py
  - experiment baseValue/situationMask/biomeMask: tools/science_audit_experiments.txt (verified vs
    RP-1/Science/Experiments/*.cfg, e.g. RP0visibleImaging1 = 1.5/63/29).
  - per-experiment BODY restrictions: manifest/experiment-bodies.tsv = RP-1's actual
    KERBALISM_EXPERIMENT BodyAllowed/BodyNotAllowed (regen via tools/experiment_bodies.py). This
    replaces the old keyword heuristic — 49 exp are Earth-only (HomeBody), 5 Earth+Moon, 11 Moon-only.
Situation bits: 1 Landed 2 Splashed 4 FlyLow 8 FlyHigh 16 SpaceLow 32 SpaceHigh.
Caveats (still modeled, not read): "theoretical max" counts every experiment at every allowed
body/biome (realistic collection is a fraction); Charon biomesum=0 is a cache artifact."""
import os
TMP = os.path.dirname(os.path.abspath(__file__))
SIT = [("landed",1),("splashed",2),("flyLow",4),("flyHigh",8),("spLow",16),("spHigh",32)]

# [landed,splashed,flyLow,flyHigh,spLow,spHigh], REAL biomesum (cache), era reach (x)
B = {
 "Earth":   ([0.00001,0.00001,0.001,0.6,1,1.25], 12.0, -3292),
 "Moon":    ([3,0,0,0,2,1.5],                      8.5, -3292),
 "Venus":   ([8,0,12,7,3,3],                       8.0, -2952),
 "Mars":    ([7,0,7,6,3,3],                       19.0, -2952),
 "Mercury": ([40,0,29,21,4,4],                     8.0, -2612),
 "Phobos":  ([4,0,5,4.5,4,4],                      2.0, -2612),
 "Deimos":  ([4,0,5,4.5,4,4],                      2.0, -2612),
 "Vesta":   ([20,0,12,7,5,4],                     14.0, -2272),
 "Ceres":   ([20,0,12,7,5,4],                     11.0, -2272),
 "Jupiter": ([0,0,24,15,10,6],                     6.0, -2102),
 "Io":      ([30,0,24,15,15,8],                    7.0, -2102),
 "Europa":  ([30,0,24,15,15,8],                    6.0, -2102),
 "Ganymede":([30,0,24,15,15,8],                    8.0, -2102),
 "Callisto":([30,0,24,15,15,8],                    8.0, -2102),
 "Saturn":  ([0,0,26,17,12,8],                     7.0, -1847),
 "Titan":   ([35,0,26,17,15,10],                   7.0, -1847),
 "Enceladus":([35,0,26,17,15,10],                  4.0, -1847),
 "Mimas":   ([35,0,26,17,15,10],                   6.0, -1847),
 "Tethys":  ([35,0,26,17,15,10],                   9.5, -1847),
 "Dione":   ([35,0,26,17,15,10],                   6.0, -1847),
 "Rhea":    ([35,0,26,17,15,10],                   5.0, -1847),
 "Iapetus": ([35,0,26,17,15,10],                   6.0, -1847),
 "Uranus":  ([0,0,28,20,18,13],                    6.0, -1200),
 "Ariel":   ([40,0,28,20,18,13],                   3.0, -1200),
 "Miranda": ([40,0,28,20,18,13],                   6.0, -1200),
 "Titania": ([40,0,28,20,18,13],                   7.0, -1200),
 "Umbriel": ([40,0,28,20,18,13],                   5.0, -1200),
 "Oberon":  ([40,0,29,21,23,18],                   4.0, -1200),
 "Neptune": ([0,0,29,21,20,15],                    6.0, -900),
 "Triton":  ([40,0,29,21,23,18],                   9.0, -900),
 "Pluto":   ([50,0,29,21,30,25],                  20.0, -657),
 "Charon":  ([50,0,29,21,30,25],                   0.0, -657),
}

exps=[]
for line in open(os.path.join(TMP,"science_audit_experiments.txt")):
    p=line.strip().split("|")
    if len(p)==4 and p[1]: exps.append((p[0],float(p[1]),int(p[2]),int(p[3])))

# EXACT per-experiment body restrictions, read from manifest/experiment-bodies.tsv
# (RP-1's KERBALISM_EXPERIMENT BodyAllowed/BodyNotAllowed; regen via tools/experiment_bodies.py).
# Experiments absent from the file carry no restriction -> universal (all bodies).
RESTRICT={}
_bt=os.path.join(TMP,"..","manifest","experiment-bodies.tsv")
if os.path.exists(_bt):
    for ln in open(_bt,encoding="utf-8"):
        c=ln.rstrip("\n").split("\t")
        if len(c)>=2 and c[0]!="experiment": RESTRICT[c[0]]=(c[1], c[2] if len(c)>2 else "")
ALL=set(B)
MOONS={"Moon","Phobos","Deimos","Io","Europa","Ganymede","Callisto","Titan","Enceladus","Mimas","Tethys",
 "Dione","Rhea","Iapetus","Ariel","Miranda","Titania","Umbriel","Oberon","Triton","Charon"}
PLANETS=ALL-MOONS

def bodies_for(eid):
    ba,bn=RESTRICT.get(eid,("",""))
    if   ba=="HomeBody":          s={"Earth"}
    elif ba=="HomeBodyAndMoons":  s={"Earth","Moon"}
    elif ba=="Planets":           s=set(PLANETS)
    elif ba=="Moons":             s=set(MOONS)
    elif ba in B:                 s={ba}            # specific body (e.g. Moon)
    else:                         s=set(ALL)        # no restriction = universal
    if   bn=="HomeBody":          s-={"Earth"}
    elif bn=="HomeBodyAndMoons":  s-={"Earth","Moon"}
    elif bn in B:                 s-={bn}
    return s

def sci_on(body,bv,sm,bm):
    mult,bsum,_=B[body]; tot=0.0
    for i,(nm,bit) in enumerate(SIT):
        if sm&bit:
            bf=bsum if (bm&bit) else 1
            tot+=bv*mult[i]*bf
    return tot

avail={b:0.0 for b in B}
for eid,bv,sm,bm in exps:
    for b in bodies_for(eid): avail[b]+=sci_on(b,bv,sm,bm)

total=sum(avail.values())
print("=== PROBE-SCIENCE BUDGET (RP0*, theoretical max, real biome weights) ===")
print(f"experiments: {len(exps)}")
print(f"TOTAL available probe science = {total:,.0f}")
print(f"Earth-only = {avail['Earth']:,.0f}   Earth+Moon (early game) = {avail['Earth']+avail['Moon']:,.0f}\n")
print("per-body (sorted):")
for b,v in sorted(avail.items(),key=lambda x:-x[1]):
    print(f"  {b:10s}{v:12,.0f}   biomesum={B[b][1]:>5}  reach x={B[b][2]}")
print("\n=== cumulative reachable probe science by era ===")
mil=[(-3292,"orbit ~1958"),(-2952,"inner planets ~1961"),(-2612,"crewed+landing ~1964"),
 (-2272,"adv probes ~1967"),(-2102,"Jupiter ~1970"),(-1847,"Saturn ~1972"),(-1200,"Uranus ~1986"),
 (-657,"Pluto ~2015")]
for mx,lab in mil:
    r=sum(v for b,v in avail.items() if B[b][2]<=mx)
    print(f"  x<= {mx:6d} {lab:22s} {r:12,.0f}")
