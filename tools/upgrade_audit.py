#!/usr/bin/env python3
"""Upgrade audit — the non-PART analog of the part diff (tools/build_manifest.py / the live part diff).

The part diff only compares PART nodes, so PARTUPGRADEs RP-1 authors are invisible to it. RP-AXE
replaces RP-1, so every RP-1-authored PARTUPGRADE is absent in an AXE install. This enumerates them
from the RP-1 SOURCE repo, diffs against the live ModuleManager cache, groups by source file (=
purpose), and flags a disposition (NEEDED / SUPERSEDED / DROP / REVIEW).

Headline finding (RP-1 v4.4.0.0): 626 RP-1-authored PARTUPGRADEs, ALL absent. 532 are the engine
config-unlock progression (Tree/TREE-Engines.cfg + Tree/RFTechLevels.cfg) — e.g. RFUpgrade_11D23
unlocks the RD0216 engine's 11D23 CONFIG at tech `stagedCombustion1967`. That whole engine-progression
layer is missing under AXE; it's tree-coupled (techRequired -> tech nodes) so it's a P2/P3 task (see
docs/RESTART.md T3). Sandbox is unaffected (sandbox auto-unlocks all upgrades).

Sources : C:\\git\\ksp\\RP-1 (RP-1 source clone) + the live Instance ModuleManager.ConfigCache.
Outputs : manifest/upgrades-absent.tsv (RP-1-authored, missing, w/ disposition + techRequired)
          manifest/upgrades-live.tsv  (the mod-authored PARTUPGRADEs live now, w/ techRequired -> P2 remap)
Note    : the live cache must be freshly built (run KSP once / -axe-autotest) for an accurate diff.
"""
import os, collections

SRC   = r"C:\git\ksp\RP-1\GameData\RP-1"
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"
OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifest")

def extract(lines, want_parenturl=False):
    """Yield (name, techRequired, title, parentUrl) for each top-level PARTUPGRADE definition."""
    n=len(lines); i=0; cur=None
    while i<n:
        s=lines[i].strip()
        if want_parenturl and s.startswith("parentUrl"): cur=s.split("=",1)[1].strip()
        is_hdr = s.startswith("PARTUPGRADE") and (len(s)==11 or not (s[11].isalnum() or s[11]=='['))
        if is_hdr:
            j=i+1
            while j<n and lines[j].strip()!="{" and j-i<4: j+=1
            if j<n and lines[j].strip()=="{":
                d=0; st=False; name=tech=title=None; k=j
                while k<n:
                    t=lines[k].strip()
                    if t=="{": d+=1; st=True
                    elif t=="}":
                        d-=1
                        if st and d==0: break
                    elif d==1 and "=" in t:
                        key=t.split("=",1)[0].strip(); val=t.split("=",1)[1].strip()
                        if key=="name" and name is None: name=val
                        elif key=="techRequired" and tech is None: tech=val
                        elif key=="title" and title is None: title=val
                    k+=1
                if name: yield (name, tech, title, cur)
                i=k
        i+=1

def cat(rel):
    if rel in ("Tree/TREE-Engines.cfg","Tree/RFTechLevels.cfg"): return "NEEDED-engine-progression"
    if rel=="Tree/ProceduralAvionics.cfg":                       return "SUPERSEDED-axe-avionics"
    if rel in ("Tree/KCTUpgrades.cfg","Tree/TechFacilityUpgrades.cfg"): return "DROP-axed-career"
    return "REVIEW-capability"

def main():
    rp1={}
    for dp,_,fs in os.walk(SRC):
        for fn in fs:
            if not fn.endswith(".cfg"): continue
            p=os.path.join(dp,fn); rel=os.path.relpath(p,SRC).replace("\\","/")
            with open(p,encoding="utf-8",errors="replace") as f: lines=f.readlines()
            for name,tech,title,_ in extract(lines): rp1[name]=(tech,title,rel)

    with open(CACHE,encoding="utf-8",errors="replace") as f: clines=f.readlines()
    live={name:(tech,title,(cur.split('/')[0] if cur else '?'))
          for name,tech,title,cur in extract(clines,True)}

    absent={n:v for n,v in rp1.items() if n not in live}
    os.makedirs(OUT,exist_ok=True)
    with open(os.path.join(OUT,"upgrades-absent.tsv"),"w",encoding="utf-8") as f:
        f.write("name\ttechRequired\tsourcefile\tdisposition\ttitle\n")
        for n,(tech,title,rel) in sorted(absent.items(),key=lambda kv:(kv[1][2],kv[0])):
            f.write(f"{n}\t{tech}\t{rel}\t{cat(rel)}\t{title}\n")
    with open(os.path.join(OUT,"upgrades-live.tsv"),"w",encoding="utf-8") as f:
        f.write("name\ttechRequired\tmod\ttitle\n")
        for n,(tech,title,mod) in sorted(live.items()): f.write(f"{n}\t{tech}\t{mod}\t{title}\n")

    print(f"RP-1-authored PARTUPGRADEs: {len(rp1)} | absent (no RP-1): {len(absent)} | live (mod-authored): {len(live)}")
    by=collections.Counter(cat(v[2]) for v in absent.values())
    for c,n in by.most_common(): print(f"  {n:>4}  {c}")
    print("-> manifest/upgrades-absent.tsv , manifest/upgrades-live.tsv")

if __name__=="__main__": main()
