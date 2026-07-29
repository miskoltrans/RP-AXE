#!/usr/bin/env python3
"""Extract REAL per-body biome counts + summed biome values from the RP-1 merged cache."""
import re
import os

# Reference instances live NEXT TO this repo, i.e. <ksp root>/ksp_rp1_*. Derive that root from
# __file__ rather than hardcoding it: seven tools had "C:\git\ksp_rp1_*" (one directory too
# high), which made them die on FileNotFoundError while the data sat there intact. 2026-07-29.
_KSPROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.environ.get("RP1_CACHE",
                       os.path.join(_KSPROOT, "ksp_rp1_clean", "GameData", "ModuleManager.ConfigCache"))
txt = open(CACHE, encoding="utf-8", errors="ignore").read()

def brace_block(s, start):
    i = s.find('{', start); depth=0; j=i
    while j < len(s):
        if s[j]=='{': depth+=1
        elif s[j]=='}':
            depth-=1
            if depth==0: return s[i+1:j], j
        j+=1
    return "", len(s)

# find each Body node: a line "Body" then "{"
bodies = {}
for m in re.finditer(r'(?m)^\t+Body\s*$', txt):
    blk, end = brace_block(txt, m.end())
    nm = re.search(r'(?m)^\s*name\s*=\s*(\S+)', blk)
    later = re.search(r'(?m)^\s*cbNameLater\s*=\s*(\S+)', blk)
    if not nm: continue
    name = (later.group(1) if later else nm.group(1))
    # find Properties -> Biomes within this body
    mp = re.search(r'(?m)^\s*Properties\s*$', blk)
    if not mp: continue
    pblk,_ = brace_block(blk, mp.end())
    mb = re.search(r'(?m)^\s*Biomes\s*$', pblk)
    biome_vals = []
    if mb:
        bblk,_ = brace_block(pblk, mb.end())
        for bm in re.finditer(r'(?m)^\s*Biome\s*$', bblk):
            sub,_ = brace_block(bblk, bm.end())
            v = re.search(r'(?m)^\s*value\s*=\s*([0-9.]+)', sub)
            nm2 = re.search(r'(?m)^\s*name\s*=\s*(\S+)', sub)
            if v: biome_vals.append((nm2.group(1) if nm2 else "?", float(v.group(1))))
    # science values
    sv = {}
    ms = re.search(r'(?m)^\s*ScienceValues\s*$', pblk)
    if ms:
        sblk,_ = brace_block(pblk, ms.end())
        for k in ["landedDataValue","splashedDataValue","flyingLowDataValue","flyingHighDataValue",
                  "inSpaceLowDataValue","inSpaceHighDataValue","recoveryValue","flyingAltitudeThreshold","spaceAltitudeThreshold"]:
            mm = re.search(r'(?m)^\s*'+k+r'\s*=\s*([0-9.eE+-]+)', sblk)
            if mm: sv[k]=float(mm.group(1))
    bodies[name] = dict(nbiomes=len(biome_vals), biomesum=sum(v for _,v in biome_vals),
                        biomes=biome_vals, sv=sv)

# my hand-table biome counts for comparison
HAND = {"Earth":15,"Moon":12,"Venus":5,"Mars":10,"Mercury":5,"Phobos":2,"Deimos":2,"Vesta":5,"Ceres":5,
 "Jupiter":3,"Io":5,"Europa":5,"Ganymede":5,"Callisto":5,"Saturn":3,"Titan":5,"Enceladus":5,"Mimas":5,
 "Tethys":5,"Dione":5,"Rhea":5,"Iapetus":5,"Uranus":3,"Ariel":5,"Miranda":5,"Titania":5,"Umbriel":5,
 "Oberon":5,"Neptune":3,"Triton":5,"Pluto":5,"Charon":5}

print(f"{'body':10s} {'realN':>5} {'realSum':>8} {'handN':>5}  {'biomeValHint'}")
print("-"*60)
order=["Earth","Moon","Venus","Mars","Mercury","Phobos","Deimos","Vesta","Ceres","Jupiter","Io",
 "Europa","Ganymede","Callisto","Saturn","Titan","Enceladus","Mimas","Tethys","Dione","Rhea","Iapetus",
 "Uranus","Ariel","Miranda","Titania","Umbriel","Oberon","Neptune","Triton","Pluto","Charon"]
for b in order:
    if b in bodies:
        d=bodies[b]; vals=set(round(v,3) for _,v in d['biomes'])
        print(f"{b:10s} {d['nbiomes']:>5} {d['biomesum']:>8.1f} {HAND.get(b,'-'):>5}  vals={sorted(vals)[:5]}")
    else:
        print(f"{b:10s}  (not found in cache as a Body name)")

# also dump any bodies found but not in my order list
extra=[b for b in bodies if b not in order]
print("\nother bodies in cache:", ", ".join(sorted(extra)))
