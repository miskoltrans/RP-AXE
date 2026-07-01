#!/usr/bin/env python3
"""node_density — report parts+upgrades per node: the DENSE piles (workhorses to spread) and the
EMPTY nodes (enabler/process gates vs gaps), grouped by discipline. Reads the placement TSVs + tree."""
import os, collections
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__)); MAN = os.path.join(ROOT, "..", "manifest")
nodes = yaml.safe_load(open(os.path.join(ROOT, "..", "tree", "nodes.yaml"), encoding="utf-8"))["nodes"]
disc = yaml.safe_load(open(os.path.join(ROOT, "..", "tree", "disciplines.yaml"), encoding="utf-8"))
info = {n["id"]: (n["discipline"], n["tier"], n["title"]) for n in nodes}

def counts(fn, col=1):
    c = collections.Counter()
    for ln in open(os.path.join(MAN, fn), encoding="utf-8").read().splitlines()[1:]:
        p = ln.split("\t")
        if len(p) > col: c[p[col]] += 1
    return c
parts = counts("part-placement.tsv"); ups = counts("upgrade-placement.tsv")

print("================ DENSE NODES (workhorse piles — spread these) ================")
print(f"{'node':26} {'disc':20} {'T':>2} {'parts':>5} {'ups':>4}")
for nid, n in parts.most_common():
    if n < 15: break
    d, t, _ = info.get(nid, ("?", "?", ""))
    print(f"{nid:26} {d:20} {t!s:>2} {n:>5} {ups.get(nid,0):>4}")

print("\n================ PER-DISCIPLINE: nodes / with-parts / empty / parts ================")
by = collections.defaultdict(lambda: [0, 0, 0])   # disc -> [nodes, with_parts, total_parts]
for n in nodes:
    d = n["discipline"]; has = parts.get(n["id"], 0) + ups.get(n["id"], 0) > 0
    by[d][0] += 1; by[d][1] += 1 if has else 0; by[d][2] += parts.get(n["id"], 0)
print(f"{'discipline':22} {'nodes':>5} {'filled':>6} {'empty':>5} {'parts':>6}")
for d in sorted(by, key=lambda x: disc[x]["order"]):
    nn, wp, pc = by[d]
    print(f"{disc[d]['title']:22} {nn:>5} {wp:>6} {nn-wp:>5} {pc:>6}")

print("\n================ EMPTY NODES (0 parts, 0 upgrades) by discipline ================")
empty = collections.defaultdict(list)
for n in nodes:
    if parts.get(n["id"], 0) + ups.get(n["id"], 0) == 0:
        empty[n["discipline"]].append((n["tier"], n["title"]))
for d in sorted(empty, key=lambda x: disc[x]["order"]):
    items = ", ".join(f"T{t} {ti}" for t, ti in sorted(empty[d]))
    print(f"\n{disc[d]['title']} ({len(empty[d])}): {items}")
print(f"\nTOTAL empty: {sum(len(v) for v in empty.values())} / {len(nodes)} nodes")
