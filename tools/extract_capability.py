#!/usr/bin/env python3
"""extract_capability — mine per-part performance from the live cache to drive CAPABILITY spreading
(so a fuel-family fans across its ladder by how advanced each unit is, not piled on one node).
Engines: peak maxThrust (kN) + peak vacuum Isp (s). Antennas: tx power. Solar: charge rate.
Output: manifest/part-capability.tsv (part / maxThrust / ispVac / antPower / solarRate)."""
import os, re
MAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifest")
CACHE = r"C:\git\ksp\Instance\GameData\ModuleManager.ConfigCache"

def curated():
    s = set()
    with open(os.path.join(MAN, "curated-parts.tsv"), encoding="utf-8") as f:
        next(f, None)
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) > 1: s.add(c[1])
    return s

def parts_iter(lines):
    """yield (name, block_text) per top-level PART."""
    n = len(lines); i = 0
    while i < n:
        if lines[i].strip() == "PART" and i + 1 < n and lines[i + 1].strip() == "{":
            depth = 0; j = i + 1; name = None
            while j < n:
                t = lines[j].strip()
                if t == "{": depth += 1
                elif t == "}":
                    depth -= 1
                    if depth == 0: break
                elif depth == 1 and t.startswith("name =") and name is None:
                    name = t.split("=", 1)[1].strip()
                j += 1
            yield name, lines[i:j + 1]
            i = j + 1
        else:
            i += 1

def main():
    cur = curated()
    with open(CACHE, encoding="utf-8", errors="replace") as f: lines = f.readlines()
    rows = {}
    for name, blk in parts_iter(lines):
        if name not in cur: continue
        txt = "".join(blk)
        thr = [float(x) for x in re.findall(r"maxThrust\s*=\s*([\d.]+)", txt)]
        # vacuum Isp = the second number of an 'key = 0 <isp>' line inside an atmosphereCurve
        isp = []
        in_curve = False
        for ln in blk:
            s = ln.strip()
            if s == "atmosphereCurve": in_curve = True
            elif in_curve:
                m = re.match(r"key\s*=\s*0\s+([\d.]+)", s)
                if m: isp.append(float(m.group(1)))
                elif s == "}" : in_curve = False
        ant = re.findall(r"(?:antennaPower|TxPower|txPower)\s*=\s*([\d.eE+]+)", txt)
        sol = re.findall(r"chargeRate\s*=\s*([\d.]+)", txt)
        rows[name] = (
            max(thr) if thr else "",
            max(isp) if isp else "",
            max((float(a) for a in ant), default="") if ant else "",
            max((float(s) for s in sol), default="") if sol else "",
        )
    with open(os.path.join(MAN, "part-capability.tsv"), "w", encoding="utf-8") as f:
        f.write("part\tmaxThrust\tispVac\tantPower\tsolarRate\n")
        for p in sorted(rows):
            f.write(p + "\t" + "\t".join(str(x) for x in rows[p]) + "\n")
    eng = sum(1 for v in rows.values() if v[0] != "")
    print(f"parts scanned: {len(rows)} | with thrust (engines): {eng} | with Isp: {sum(1 for v in rows.values() if v[1]!='')}")
    print("-> manifest/part-capability.tsv")

if __name__ == "__main__": main()
