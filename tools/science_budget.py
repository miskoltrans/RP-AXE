#!/usr/bin/env python3
"""Probe-science budget (RP0* suite) — available-science half of the old audit, tree-independent."""
import os
TMP = r"C:\git\ksp\RP-AXE\tools"

# situation bits: 1 Landed,2 Splashed,4 FlyLow,8 FlyHigh,16 SpaceLow,32 SpaceHigh
SIT = [("landed",1),("splashed",2),("flyLow",4),("flyHigh",8),("spLow",16),("spHigh",32)]

# body multipliers [landed,splashed,flyLow,flyHigh,spLow,spHigh], biome count, era reach (x)
B = {
 "Earth":   ([0.00001,0.00001,0.001,0.6,1,1.25], 15, -3292),
 "Moon":    ([3,0,0,0,2,1.5],                     12, -3292),
 "Venus":   ([8,0,12,7,3,3],                       5, -2952),
 "Mars":    ([7,0,7,6,3,3],                       10, -2952),
 "Mercury": ([40,0,29,21,4,4],                     5, -2612),
 "Phobos":  ([4,0,5,4.5,4,4],                      2, -2612),
 "Deimos":  ([4,0,5,4.5,4,4],                      2, -2612),
 "Vesta":   ([20,0,12,7,5,4],                      5, -2272),
 "Ceres":   ([20,0,12,7,5,4],                      5, -2272),
 "Jupiter": ([0,0,24,15,10,6],                     3, -2102),
 "Io":      ([30,0,24,15,15,8],                    5, -2102),
 "Europa":  ([30,0,24,15,15,8],                    5, -2102),
 "Ganymede":([30,0,24,15,15,8],                    5, -2102),
 "Callisto":([30,0,24,15,15,8],                    5, -2102),
 "Saturn":  ([0,0,26,17,12,8],                     3, -1847),
 "Titan":   ([35,0,26,17,15,10],                   5, -1847),
 "Enceladus":([35,0,26,17,15,10],                  5, -1847),
 "Mimas":   ([35,0,26,17,15,10],                   5, -1847),
 "Tethys":  ([35,0,26,17,15,10],                   5, -1847),
 "Dione":   ([35,0,26,17,15,10],                   5, -1847),
 "Rhea":    ([35,0,26,17,15,10],                   5, -1847),
 "Iapetus": ([35,0,26,17,15,10],                   5, -1847),
 "Uranus":  ([0,0,28,20,18,13],                    3, -1200),
 "Ariel":   ([40,0,28,20,18,13],                   5, -1200),
 "Miranda": ([40,0,28,20,18,13],                   5, -1200),
 "Titania": ([40,0,28,20,18,13],                   5, -1200),
 "Umbriel": ([40,0,28,20,18,13],                   5, -1200),
 "Oberon":  ([40,0,29,21,23,18],                   5, -1200),
 "Neptune": ([0,0,29,21,20,15],                    3, -900),
 "Triton":  ([40,0,29,21,23,18],                   5, -900),
 "Pluto":   ([50,0,29,21,30,25],                   5, -657),
 "Charon":  ([50,0,29,21,30,25],                   5, -657),
}

exps = []
for line in open(os.path.join(TMP, "science_audit_experiments.txt")):
    p = line.strip().split("|")
    if len(p) == 4 and p[1]:
        exps.append((p[0], float(p[1]), int(p[2]), int(p[3])))

def body_for_exp(eid):
    s = eid.lower()
    if "lunar" in s or "alsep" in s: return "Moon"
    earth_kw = ["earth","supersonic","weather","ocean","airglow","longdurationhabit",
        "compositecasting","galliumarsenide","gnatmice","egggrowth","bloodcells","closedloopag",
        "foodevaluation","sleepanalysis","worktolerance","visualacuity","zerogflammability",
        "vapordistillation","liquidsmicrogravity","flightcontrol","powertoolevaluation",
        "orbitalmaneuvering","ionsensing","simplenavigation","staroccultation","nuclearemulsion",
        "particlecollection","alfmed","bistaticradar","television","habit","navigation",
        "terrainphotography","nightimage","uvairglow","uvpanorama","uvstellar","uvxray",
        "ultraviolet","vhfpolar","visualtracking","zodiacal","solarxray","narrowbeam",
        "galacticxray","earthresources","photography"]
    if any(k in s for k in earth_kw): return "Earth"
    return "UNIVERSAL"

def exp_science_on(body, baseval, smask, bmask):
    mult, biomes, _ = B[body]
    tot = 0.0
    for i,(name,bit) in enumerate(SIT):
        if smask & bit:
            bf = biomes if (bmask & bit) else 1
            tot += baseval * mult[i] * bf
    return tot

avail = {b:0.0 for b in B}
crewed_earth_moon = 0.0
CREW_KW = ["habit","bloodcells","egggrowth","gnatmice","closedloopag","foodevaluation",
    "sleepanalysis","worktolerance","visualacuity","alfmed","liquidsmicrogravity",
    "compositecasting","galliumarsenide","zerogflammability","vapordistillation",
    "powertoolevaluation","nuclearemulsion","longalsep","alsep","lunarisrudemo",
    "lunarmicrobiome","lunarseismic","lunarnight"]
crewed_sum = 0.0
for eid,bv,sm,bm in exps:
    tgt = body_for_exp(eid)
    if tgt == "Earth": avail["Earth"] += exp_science_on("Earth",bv,sm,bm)
    elif tgt == "Moon": avail["Moon"] += exp_science_on("Moon",bv,sm,bm)
    else:
        for b in B: avail[b] += exp_science_on(b,bv,sm,bm)

total = sum(avail.values())
print("=== RP0* PROBE-SCIENCE BUDGET (theoretical max, all RSS bodies, post-EarthScienceRemoval) ===")
print(f"experiments: {len(exps)}")
print(f"TOTAL available probe science (all bodies) = {total:,.0f}\n")
print("per-body (sorted):")
for b,v in sorted(avail.items(), key=lambda x:-x[1]):
    print(f"  {b:10s}{v:12,.0f}   reach x={B[b][2]}")

# era-cumulative (when each body first becomes reachable)
print("\n=== cumulative reachable probe science by era milestone ===")
mil = [(-3292,"first orbit ~1958"),(-2952,"inner-planet/early Moon ~1961"),
   (-2612,"crewed+landing ~1964"),(-2272,"adv probes/stations ~1967"),
   (-2102,"Jupiter ~1970"),(-1847,"Saturn/stations ~1972"),
   (-1200,"Uranus ~1986"),(-657,"Pluto/modern ~2015"),(-62,"endgame")]
for mx,label in mil:
    reach = sum(v for b,v in avail.items() if B[b][2] <= mx)
    print(f"  x<= {mx:6d} {label:30s} {reach:12,.0f}")

# Earth+Moon only (home-system, where crewed stations realistically operate early/mid)
print(f"\nEarth-only available       = {avail['Earth']:,.0f}")
print(f"Earth+Moon available       = {avail['Earth']+avail['Moon']:,.0f}")
