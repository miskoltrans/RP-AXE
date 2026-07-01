#!/usr/bin/env python3
"""cluster_parts (P2 review) — group all placed parts + upgrades into coherent review CLUSTERS
(by placement family/method), one TSV per cluster, so we can go through P2 cluster-by-cluster with
every part visible. Each row carries the signals needed to judge placement (title, mod, current node,
RP-1 era, propellants, key modules). Regenerate any time; edit placement rules in place_parts.py or
add hand-overrides, then rebuild.

Inputs : manifest/part-placement.tsv, manifest/part-capabilities.tsv, manifest/upgrade-placement.tsv,
         tree/nodes.yaml (node tiers).
Output : manifest/clusters/<cluster>.tsv  +  manifest/clusters/INDEX.tsv  + console index.
"""
import os, collections
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__)); MAN = os.path.join(ROOT, "..", "manifest")
OUT = os.path.join(MAN, "clusters")
NODES = os.path.join(ROOT, "..", "tree", "nodes.yaml")

def read_tsv(fn):
    rows = []; p = os.path.join(MAN, fn)
    with open(p, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            rows.append({h: (c[i] if i < len(c) else "") for i, h in enumerate(hdr)})
    return rows

KEY_MODS = ("Engine", "SolarPanel", "Antenna", "Command", "Parachute", "DockingNode", "Wheel",
            "Reaction", "Science", "Radiator", "Ablator", "RTG", "Reactor", "FuelTank", "RCS")
def keymods(mods):
    return ";".join(m for m in mods.split(";") if any(k in m for k in KEY_MODS))[:60]

def cluster_key(method):
    """collapse the placement method into a review-cluster label."""
    if method.startswith("engine:"):      return "engine-" + method.split(":")[1]
    if method.startswith("science:"):     return "science-" + method.split(":")[1]
    if method.startswith("clean:"):       return "clean-" + method.split(":")[1]
    return method

def main():
    os.makedirs(OUT, exist_ok=True)
    node_tier = {n["id"]: n["tier"] for n in yaml.safe_load(open(NODES, encoding="utf-8"))["nodes"]}
    cap = {r["name"]: r for r in read_tsv("part-capabilities.tsv")}
    place = read_tsv("part-placement.tsv")

    clusters = collections.defaultdict(list)
    for pl in place:
        r = cap.get(pl["part"], {})
        clusters[cluster_key(pl["method"])].append({
            "part": pl["part"], "title": r.get("title", ""), "mod": r.get("mod", ""),
            "node": pl["node"], "node_tier": node_tier.get(pl["node"], ""),
            "rp1_tech": r.get("rp1_tech", ""), "props": r.get("propellants", ""),
            "key_modules": keymods(r.get("modules", "")), "confidence": pl["confidence"],
        })
    # upgrades -> 2 clusters
    up = read_tsv("upgrade-placement.tsv")
    for u in up:
        ck = "upgrade-engineconfig" if u["method"].startswith("engine-config") else "upgrade-capability"
        clusters[ck].append({"part": u["upgrade"], "title": "", "mod": "", "node": u["node"],
                             "node_tier": node_tier.get(u["node"], ""), "rp1_tech": "", "props": "",
                             "key_modules": u["method"], "confidence": ""})

    cols = ["part","title","mod","node","node_tier","rp1_tech","props","key_modules","confidence"]
    index = []
    for ck in sorted(clusters, key=lambda k: -len(clusters[k])):
        rows = sorted(clusters[ck], key=lambda r: (str(r["node_tier"]), r["node"], r["part"]))
        with open(os.path.join(OUT, ck + ".tsv"), "w", encoding="utf-8") as f:
            f.write("\t".join(cols) + "\n")
            for r in rows: f.write("\t".join(str(r[c]) for c in cols) + "\n")
        nodes_used = sorted({r["node"] for r in rows})
        index.append((ck, len(rows), len(nodes_used), ", ".join(nodes_used[:4]) + (" …" if len(nodes_used) > 4 else "")))

    with open(os.path.join(OUT, "INDEX.tsv"), "w", encoding="utf-8") as f:
        f.write("cluster\tparts\tnodes\tnodes_sample\n")
        for ck, n, nn, s in index: f.write(f"{ck}\t{n}\t{nn}\t{s}\n")
    print(f"{len(index)} clusters -> manifest/clusters/  ({sum(n for _,n,_,_ in index)} items)\n")
    print(f"{'cluster':28} {'items':>5} {'nodes':>5}  spread")
    for ck, n, nn, s in index:
        print(f"{ck:28} {n:>5} {nn:>5}  {s}")

if __name__ == "__main__": main()
