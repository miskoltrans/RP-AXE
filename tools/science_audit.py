import re, os
TMP = r"C:\Users\User\.claude\jobs\5bb92631\tmp"
TREE = r"C:\git\ksp\RP-AXE\GameData\RP-AXE\seed\Tree\RP0TechTree.cfg"
SCALE = 0.8  # our science-pace trim

# ---------- 1) tree: per-node (cost, era_x) via RDNode-chunk parsing ----------
txt = open(TREE, encoding="utf-8", errors="ignore").read()
chunks = txt.split("RDNode")[1:]
nodes = []
for c in chunks:
    mc = re.search(r"\n\s*cost\s*=\s*(\d+)", c)
    mp = re.search(r"\n\s*pos\s*=\s*(-?\d+)", c)
    if mc and mp and int(mc.group(1)) < 5000:   # exclude the ORPHANS dump node (cost 99999, not progression)
        nodes.append((int(mp.group(1)), int(mc.group(1)) * SCALE))
tree_total = sum(n[1] for n in nodes)
print(f"tree: {len(nodes)} nodes, total science (x{SCALE}) = {tree_total:,.0f}")

# ---------- 2) experiments ----------
exps = []
for line in open(os.path.join(TMP, "experiments.txt")):
    p = line.strip().split("|")
    if len(p) == 4 and p[1]:
        exps.append((p[0], float(p[1]), int(p[2]), int(p[3])))
print(f"experiments: {len(exps)}")

# situation bits: 1 Landed,2 Splashed,4 FlyLow,8 FlyHigh,16 SpaceLow,32 SpaceHigh
SIT = [("landed",1),("splashed",2),("flyLow",4),("flyHigh",8),("spLow",16),("spHigh",32)]

# ---------- 3) body multipliers [landed,splashed,flyLow,flyHigh,spLow,spHigh], biomes, era reachable (x) ----------
# Earth values are POST our EarthScienceRemoval patch. era_x ~ when body first yields science in the tree timeline.
B = {
 "Earth":   ([0.00001,0.00001,0.001,0.6,1,1.25], 15, -3292),   # first orbit ~1958
 "Moon":    ([3,0,0,0,2,1.5],                     12, -3292),   # lunar probes ~1958-59
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

# ---------- 4) compute available science per body ----------
avail = {b:0.0 for b in B}
earth_orbit_only = 0.0  # Earth, spLow+spHigh+flyHigh only (what we kept)
for eid,bv,sm,bm in exps:
    tgt = body_for_exp(eid)
    if tgt == "Earth":
        avail["Earth"] += exp_science_on("Earth",bv,sm,bm)
    elif tgt == "Moon":
        avail["Moon"] += exp_science_on("Moon",bv,sm,bm)
    else:  # universal: every body
        for b in B:
            avail[b] += exp_science_on(b,bv,sm,bm)

total_avail = sum(avail.values())
print(f"\nTOTAL available science (all bodies, all experiments) = {total_avail:,.0f}")
print(f"  vs full tree {tree_total:,.0f}  ->  ratio {total_avail/tree_total:.2f}x")

print("\nper-body available science (sorted):")
for b,v in sorted(avail.items(), key=lambda x:-x[1]):
    print(f"  {b:10s} {v:12,.0f}   (reach era x={B[b][2]})")

# ---------- 5) cumulative tree cost by era vs cumulative available science reachable ----------
print("\n=== SOLVENCY BY ERA: cumulative node cost vs cumulative reachable science ===")
milestones = [(-3292,"first orbit ~1958"),(-2952,"early Moon/inner-planet probes ~1961"),
    (-2612,"crewed + early landing ~1964"),(-2272,"adv probes/stations ~1967"),
    (-2187,"crewed lunar (Apollo) ~1968"),(-1847,"stations/NF-precursor ~1972"),
    (-657,"modern ~2019"),(-62,"endgame")]
nodes_sorted = sorted(nodes)
for mx,label in milestones:
    cost_to = sum(c for x,c in nodes_sorted if x <= mx)
    reach = sum(v for b,v in avail.items() if B[b][2] <= mx)
    flag = "OK" if reach >= cost_to else "SHORT"
    print(f"  x<= {mx:6d} {label:34s} cost {cost_to:9,.0f} | reachable sci {reach:11,.0f} | {flag}")

# ---------- 6) the two specific questions ----------
print("\n=== the questions ===")
moon_capable_cost = sum(c for x,c in nodes_sorted if x <= -3122)  # through ~1960 (orbit+early probes)
apollo_cost = sum(c for x,c in nodes_sorted if x <= -2187)        # through ~1968
print(f"Q: Moon on Earth(+Moon) science?")
print(f"   Earth available           = {avail['Earth']:,.0f}")
print(f"   Earth+Moon available       = {avail['Earth']+avail['Moon']:,.0f}")
print(f"   cost to reach Moon-capable (~1960) = {moon_capable_cost:,.0f}")
print(f"Q: Apollo on lunar science?")
print(f"   cost to reach Apollo (~1968)       = {apollo_cost:,.0f}")
print(f"   Earth+Moon available               = {avail['Earth']+avail['Moon']:,.0f}")
