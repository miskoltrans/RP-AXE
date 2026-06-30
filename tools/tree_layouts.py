#!/usr/bin/env python3
"""tree_layouts — GEOMETRY BAKE-OFF. Render the slice graph under 4 layouts so we can pick one:
  1. LANES     — discipline = row, tier = column (current; cross-discipline edges cross lanes)
  2. DELTA     — graphviz `dot` layered (tier columns, crossings minimized)
  3. PINWHEEL  — radial from start (ETT geometry)
  4. FORCE     — networkx spring layout (organic)
Only graphviz `dot` + networkx are available, so positions are computed here and drawn as inline SVG
into a single self-contained page: tree/render/layouts/compare.html (open in a browser to compare)."""
import os, math, subprocess, collections, html
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(ROOT, ".."))
TREE = os.path.join(REPO, "tree")
OUT  = os.path.join(TREE, "render", "layouts")

def load():
    with open(os.path.join(TREE, "disciplines.yaml"), encoding="utf-8") as f: disc = yaml.safe_load(f)
    with open(os.path.join(TREE, "nodes.yaml"), encoding="utf-8") as f: nodes = yaml.safe_load(f)["nodes"]
    return disc, {n["id"]: n for n in nodes}, nodes

# ---------- layouts: each returns {id: (x, y)} in arbitrary units ----------
def lay_lanes(disc, nodes):
    return {n["id"]: (n["tier"], -disc[n["discipline"]]["order"]) for n in nodes}

def lay_pinwheel(disc, nodes):
    used = sorted({n["discipline"] for n in nodes}, key=lambda d: disc[d]["order"])
    ang = {d: 2 * math.pi * i / len(used) for i, d in enumerate(used)}
    sub = collections.defaultdict(int)
    pos = {}
    for n in nodes:
        d = n["discipline"]; a = ang[d] + (sub[(d, n["tier"])] * 0.13); sub[(d, n["tier"])] += 1
        r = n["tier"] + 0.6
        pos[n["id"]] = (r * math.cos(a), r * math.sin(a))
    return pos

def lay_force(disc, nodes):
    import networkx as nx
    G = nx.DiGraph()
    for n in nodes: G.add_node(n["id"])
    for n in nodes:
        for p in n.get("parents", []) or []: G.add_edge(p, n["id"])
    p = nx.spring_layout(G, seed=7, k=1.1, iterations=300)
    return {k: (float(v[0]), float(v[1])) for k, v in p.items()}

def render_delta_png(disc, nodes):
    """graphviz `dot` layered render straight to PNG (text exporters are dead, but -Tpng works)."""
    os.makedirs(OUT, exist_ok=True)
    tiers = collections.defaultdict(list)
    for n in nodes: tiers[n["tier"]].append(n["id"])
    L = ['digraph G { rankdir=LR; bgcolor="#1a1a1a"; ranksep=1.2; nodesep=0.3;',
         ' node[shape=box,style="filled,rounded",fontname="Helvetica",fontsize=11,color="#00000000",fontcolor="#111"];',
         ' edge[color="#9aa0a6",arrowsize=0.6];',
         ' labelloc="t"; fontcolor="#eee"; fontsize=20;',
         ' label="DELTA — graphviz dot layered (tier columns, crossings minimized)";']
    for n in nodes:
        d = disc[n["discipline"]]; t = n["title"].replace('"', "'")
        L.append(f'"{n["id"]}" [label="{t}",fillcolor="{d["color"]}"];')
    for v in tiers.values(): L.append("{ rank=same; " + " ".join(f'"{i}"' for i in v) + " }")
    for n in nodes:
        for pa in n.get("parents", []) or []:
            st = 'style=dashed,color="#f4d35e",penwidth=1.4' if n.get("anyToUnlock") else 'style=solid'
            L.append(f'"{pa}" -> "{n["id"]}" [{st}];')
    L.append("}")
    dotp = os.path.join(OUT, "_delta.dot")
    with open(dotp, "w", encoding="utf-8") as f: f.write("\n".join(L))
    subprocess.run(["dot", "-Tpng", dotp, "-o", os.path.join(OUT, "delta.png")], check=True, capture_output=True)
    return "delta.png"

# ---------- SVG drawing ----------
def svg(title, pos, disc, by, nodes, W=1500, H=620, m=90):
    xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    def sx(v): return m if x1 == x0 else m + (v - x0) / (x1 - x0) * (W - 2 * m)
    def sy(v): return m if y1 == y0 else m + (v - y0) / (y1 - y0) * (H - 2 * m)
    P = {k: (sx(x), sy(y)) for k, (x, y) in pos.items()}
    e = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" style="background:#1a1a1a">']
    e.append(f'<text x="20" y="30" fill="#eee" font-family="Helvetica" font-size="20" '
             f'font-weight="bold">{html.escape(title)}</text>')
    # edges (under nodes)
    for n in nodes:
        if n["id"] not in P: continue
        cx, cy = P[n["id"]]
        for pa in n.get("parents", []) or []:
            if pa not in P: continue
            px, py = P[pa]
            if n.get("anyToUnlock"):
                e.append(f'<line x1="{px:.0f}" y1="{py:.0f}" x2="{cx:.0f}" y2="{cy:.0f}" '
                         f'stroke="#f4d35e" stroke-width="2" stroke-dasharray="5,4"/>')
            else:
                e.append(f'<line x1="{px:.0f}" y1="{py:.0f}" x2="{cx:.0f}" y2="{cy:.0f}" '
                         f'stroke="#7a7f87" stroke-width="1.4"/>')
    # nodes
    bw, bh = 150, 32
    for n in nodes:
        if n["id"] not in P: continue
        cx, cy = P[n["id"]]; col = disc[n["discipline"]]["color"]
        t = n["title"]; t = t if len(t) <= 30 else t[:28] + "…"
        e.append(f'<rect x="{cx-bw/2:.0f}" y="{cy-bh/2:.0f}" width="{bw}" height="{bh}" rx="6" '
                 f'fill="{col}" stroke="#000" stroke-opacity="0.25"/>')
        e.append(f'<text x="{cx:.0f}" y="{cy+3:.0f}" text-anchor="middle" fill="#111" '
                 f'font-family="Helvetica" font-size="9">{html.escape(t)}</text>')
    e.append("</svg>")
    return "\n".join(e)

def main():
    disc, by, nodes = load()
    os.makedirs(OUT, exist_ok=True)
    delta_png = render_delta_png(disc, nodes)
    svg_variants = [
        ("LANES — discipline = row, tier = column", lay_lanes(disc, nodes), 1500, 560),
        ("PINWHEEL — radial from start (ETT geometry)", lay_pinwheel(disc, nodes), 900, 900),
        ("FORCE-DIRECTED — networkx spring (organic)", lay_force(disc, nodes), 1100, 760),
    ]
    # legend
    sw = "".join(f'<span style="display:inline-block;margin:2px 8px"><span style="display:inline-block;'
                 f'width:12px;height:12px;background:{disc[d]["color"]};border-radius:2px"></span> '
                 f'{disc[d]["title"]}</span>' for d in sorted({n["discipline"] for n in nodes},
                 key=lambda d: disc[d]["order"]))
    parts = ['<!doctype html><meta charset="utf-8"><title>RP-AXE layout bake-off</title>',
             '<body style="background:#111;color:#ddd;font-family:Helvetica;margin:0;padding:20px">',
             '<h1>RP-AXE tech tree — autolayout bake-off (vertical slice)</h1>',
             f'<p>Disciplines: {sw} &nbsp;|&nbsp; '
             '<b style="color:#f4d35e">— —</b> dashed gold = multi-entry (anyToUnlock=True); '
             'grey solid = convergence/normal.</p>']
    def box(inner): return f'<div style="margin:18px 0;border:1px solid #333;border-radius:8px;overflow:auto">{inner}</div>'
    # LANES first, then the DELTA dot-render (image), then PINWHEEL + FORCE
    t0, p0, W0, H0 = svg_variants[0]
    parts.append(box(svg(t0, p0, disc, by, nodes, W=W0, H=H0)))
    parts.append(box(f'<img src="{delta_png}" style="display:block;max-width:100%">'))
    for title, pos, W, Hh in svg_variants[1:]:
        s = svg(title, pos, disc, by, nodes, W=W, H=Hh)
        parts.append(box(s))
        with open(os.path.join(OUT, f"{title.split(' ')[0].lower().rstrip('-')}.svg"), "w", encoding="utf-8") as f:
            f.write(s)
    parts.append("</body>")
    page = os.path.join(OUT, "compare.html")
    with open(page, "w", encoding="utf-8") as f: f.write("\n".join(parts))
    print("wrote", page)
    print("individual svgs:", ", ".join(sorted(os.listdir(OUT))))

if __name__ == "__main__": main()
