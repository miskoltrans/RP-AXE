#!/usr/bin/env python3
"""build_tree — compile tree/nodes.yaml (+ tree/disciplines.yaml) into:
  1. GameData/RP-AXE/design/Tree/AxeTechTree.cfg        game form (MM @TechTree patch, wipes stock)
  2. GameData/RP-AXE/design/Tree/AxeTechTree.editor.cfg  plain TechTree{} form for ETT KSPTechtreeEditor
  3. tree/render/axe-tree.{dot,svg,png}                  review render (delta preview, colored by discipline)
  4. tree/render/axe-tree.html                           interactive viewer: click a node -> its parts (read-only)

One source of truth (YAML) -> the game cfg, the editor-openable cfg (Q1 "open without KSP"), and a
picture. Validates: unique ids, known disciplines, parents exist, no cycles. Cost = node.cost or
meta.tier_cost[tier]*scalar. Layout pos auto-derived from (discipline order, tier).
"""
import os, sys, subprocess, collections, json, re
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(ROOT, ".."))
TREE = os.path.join(REPO, "tree")
OUTD = os.path.join(REPO, "GameData", "RP-AXE", "design", "Tree")
REND = os.path.join(TREE, "render")

X0, TIERW = 0, 430              # x = X0 + tier*TIERW (X anchored to MARGIN_X below)
Y0, DISCH, SUBH = 300, 100, 34  # y = Y0 + (order-1)*DISCH + sub-stack (lane-grid fallback)
MARGIN_X, MARGIN_Y = -2568, 711 # anchor top-left to the editor's stock-tree origin
SPACING_Y = 80                  # delta layout: vertical px per within-tier row
MULTI_ENTRY_COLOR = "#f4d35e"   # dashed-edge color for anyToUnlock (shared: graphviz render + html viewer)

def die(msg):
    print("ERROR:", msg); sys.exit(1)

def load():
    with open(os.path.join(TREE, "disciplines.yaml"), encoding="utf-8") as f:
        disc = yaml.safe_load(f)
    with open(os.path.join(TREE, "nodes.yaml"), encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    return disc, doc.get("meta", {}), doc["nodes"]

def validate(disc, nodes, by):
    ids = [n["id"] for n in nodes]
    dup = [i for i, c in collections.Counter(ids).items() if c > 1]
    if dup: die(f"duplicate ids: {dup}")
    for n in nodes:
        if n["discipline"] not in disc: die(f"{n['id']}: unknown discipline {n['discipline']}")
        for p in n.get("parents", []) or []:
            if p not in by: die(f"{n['id']}: parent '{p}' does not exist")
    # cycle check (Kahn)
    indeg = {i: 0 for i in ids}
    adj = collections.defaultdict(list)
    for n in nodes:
        for p in n.get("parents", []) or []:
            adj[p].append(n["id"]); indeg[n["id"]] += 1
    q = [i for i in ids if indeg[i] == 0]; seen = 0
    while q:
        i = q.pop(); seen += 1
        for c in adj[i]:
            indeg[c] -= 1
            if indeg[c] == 0: q.append(c)
    if seen != len(ids): die("cycle detected in node graph")

def resolve(disc, meta, nodes, by):
    scalar = meta.get("scalar", 1.0); tc = meta.get("tier_cost", {})
    # default parents = previous node in same discipline (lower tier); cost; pos
    cells = collections.defaultdict(list)  # (order,tier) -> [node] for sub-stacking
    prev_in_disc = {}
    for n in sorted(nodes, key=lambda x: (disc[x["discipline"]]["order"], x["tier"])):
        d = n["discipline"]
        if "parents" not in n:
            n["parents"] = [prev_in_disc[d]] if d in prev_in_disc else []
        prev_in_disc[d] = n["id"]
    for n in nodes:
        if "cost" not in n or n["cost"] is None:
            n["cost"] = round(tc.get(n["tier"], 0) * scalar)
        cells[(disc[n["discipline"]]["order"], n["tier"])].append(n)
    for (order, tier), group in cells.items():
        for k, n in enumerate(group):
            n["_x"] = X0 + tier * TIERW
            n["_y"] = Y0 + (order - 1) * DISCH + int((k - (len(group) - 1) / 2) * SUBH)
    # anchor leftmost node's X to the editor origin; leave Y at its natural Y0-based position
    minx = min(n["_x"] for n in nodes)
    for n in nodes:
        n["_x"] += MARGIN_X - minx

def delta_layout(disc, nodes, by, sweeps=12):
    """Layered 'delta' layout: tier = column (x); within-tier order minimized for edge crossings
    (barycenter/Sugiyama), then coordinate assignment pulls each node toward its neighbours' mean.
    Overrides _x/_y. Pure-Python — graphviz text exporters (-Tplain) are dead on this box."""
    tiers = collections.defaultdict(list)
    for n in nodes: tiers[n["tier"]].append(n["id"])
    par = {n["id"]: [p for p in (n.get("parents") or []) if p in by] for n in nodes}
    chl = collections.defaultdict(list)
    for nid, ps in par.items():
        for p in ps: chl[p].append(nid)
    neigh = lambda i: par[i] + chl[i]
    y = {}
    for ids in tiers.values():                      # seed by discipline order for a sensible start
        for k, i in enumerate(sorted(ids, key=lambda i: (disc[by[i]["discipline"]]["order"], i))):
            y[i] = float(k)
    for phase in ("order", "coord"):                # phase 1 reduces crossings; phase 2 places coords
        for _ in range(sweeps):
            ny = {i: (sum(y[j] for j in neigh(i)) / len(neigh(i)) if neigh(i) else y[i]) for i in y}
            for ids in tiers.values():
                if phase == "order":                # re-rank to integers (decross)
                    for k, i in enumerate(sorted(ids, key=lambda i: ny[i])): ny[i] = float(k)
                else:                               # enforce min spacing in the settled order
                    last = -1e9
                    for i in sorted(ids, key=lambda i: ny[i]):
                        if ny[i] < last + 1: ny[i] = last + 1
                        last = ny[i]
            y = ny
    gmean = sum(y.values()) / len(y)                # center each column on the global mean
    for ids in tiers.values():
        c = sum(y[i] for i in ids) / len(ids)
        for i in ids: y[i] += gmean - c
    miny = min(y.values())
    for n in nodes:
        n["_x"] = MARGIN_X + n["tier"] * TIERW
        n["_y"] = int(MARGIN_Y + (y[n["id"]] - miny) * SPACING_Y)

def validate_design(disc, nodes, by):
    """Non-fatal structural sanity checks (warn, don't die). Hook for domain consistency rules
    (e.g. 'regen-cooled engine must have a cooling parent') once parts carry that metadata."""
    warns = []
    chl = collections.defaultdict(list)
    for n in nodes:
        for p in n.get("parents", []) or []: chl[p].append(n["id"])
    roots = [n["id"] for n in nodes if not (n.get("parents") or [])]
    seen, stack = set(), list(roots)               # reachability from the roots
    while stack:
        i = stack.pop()
        if i in seen: continue
        seen.add(i); stack += chl[i]
    for n in nodes:
        if n["id"] not in seen: warns.append(f"unreachable from any root: {n['id']}")
        for p in n.get("parents", []) or []:       # edges must go forward in tier
            if p in by and by[p]["tier"] >= n["tier"]:
                warns.append(f"non-forward edge: {p} (T{by[p]['tier']}) -> {n['id']} (T{n['tier']})")
        if n.get("anyToUnlock") and len(n.get("parents") or []) < 2:
            warns.append(f"anyToUnlock with <2 parents (no-op): {n['id']}")
    for r in roots:
        if r != "start": warns.append(f"extra root (no parents besides start): {r}")
    print(f"design checks: {'clean' if not warns else str(len(warns))+' warning(s)'}")
    for w in warns: print(f"   ! {w}")
    return warns

def node_block(disc, n, indent="\t"):
    L = []; a = L.append
    a(f"{indent}RDNode")
    a(f"{indent}{{")
    a(f"{indent}\tid = {n['id']}")
    a(f"{indent}\ttitle = {n['title']}")
    a(f"{indent}\tdescription = {n.get('flavor','').strip()}")
    a(f"{indent}\tcost = {n['cost']}")
    a(f"{indent}\thideEmpty = False")
    a(f"{indent}\tnodeName = node_{n['id']}")
    a(f"{indent}\tanyToUnlock = {'True' if n.get('anyToUnlock') else 'False'}")
    a(f"{indent}\ticon = {disc[n['discipline']]['icon']}")
    a(f"{indent}\tpos = {n['_x']},{n['_y']},-1")
    a(f"{indent}\tscale = 0.6")
    for p in n.get("parents", []) or []:
        a(f"{indent}\tParent")
        a(f"{indent}\t{{")
        a(f"{indent}\t\tparentID = {p}")
        a(f"{indent}\t\tlineFrom = RIGHT")
        a(f"{indent}\t\tlineTo = LEFT")
        a(f"{indent}\t}}")
    parts = n.get("parts") or []; ups = n.get("upgrades") or []
    if parts or ups:
        a(f"{indent}\tUnlocks")
        a(f"{indent}\t{{")
        for p in parts: a(f"{indent}\t\tpart = {p}")
        for u in ups:   a(f"{indent}\t\tpartUpgrade = {u}")
        a(f"{indent}\t}}")
    a(f"{indent}}}")
    return "\n".join(L)

def emit_cfg(disc, nodes):
    os.makedirs(OUTD, exist_ok=True)
    blocks = "\n".join(node_block(disc, n) for n in nodes)
    hdr = "// GENERATED by tools/build_tree.py from tree/nodes.yaml — DO NOT EDIT BY HAND\n"
    with open(os.path.join(OUTD, "AxeTechTree.cfg"), "w", encoding="utf-8") as f:
        f.write(hdr + "@TechTree:FOR[ZZZZZ-AXE-Tree]\n{\n\t!RDNode,* {}\n" + blocks + "\n}\n")
    with open(os.path.join(OUTD, "AxeTechTree.editor.cfg"), "w", encoding="utf-8") as f:
        f.write(hdr + "TechTree\n{\n\tid = AXETree\n\tlabel = RP-AXE Tree\n" + blocks + "\n}\n")

def emit_render(disc, meta, nodes, by):
    os.makedirs(REND, exist_ok=True)
    L = ['digraph AXE {', '  rankdir=LR; bgcolor="#1a1a1a"; nodesep=0.25; ranksep=1.1;',
         '  node[shape=box,style="filled,rounded",fontname="Helvetica",fontsize=10,color="#00000000"];',
         '  edge[color="#888888",arrowsize=0.6];']
    for n in nodes:
        d = disc[n["discipline"]]
        lbl = f"{n['title']}\\n{n['discipline']} T{n['tier']} · {n['cost']}"
        L.append(f'  "{n["id"]}" [label="{lbl}",fillcolor="{d["color"]}",fontcolor="#111111"];')
    # align tiers as columns
    tiers = collections.defaultdict(list)
    for n in nodes: tiers[n["tier"]].append(n["id"])
    for t in sorted(tiers):
        L.append("  { rank=same; " + " ".join(f'"{i}"' for i in tiers[t]) + " }")
    for n in nodes:
        dashed = n.get("anyToUnlock")
        for p in n.get("parents", []) or []:
            style = f'style=dashed,color="{MULTI_ENTRY_COLOR}"' if dashed else 'style=solid'
            L.append(f'  "{p}" -> "{n["id"]}" [{style}];')
    L.append('  labelloc="t"; fontcolor="#eeeeee"; fontsize=16;')
    L.append('  label="RP-AXE tech tree — vertical slice  (dashed = multi-entry / anyToUnlock=True)";')
    L.append("}")
    dot = os.path.join(REND, "axe-tree.dot")
    with open(dot, "w", encoding="utf-8") as f: f.write("\n".join(L))
    for fmt in ("svg", "png"):
        try:
            subprocess.run(["dot", f"-T{fmt}", dot, "-o", os.path.join(REND, f"axe-tree.{fmt}")], check=True)
        except Exception as e:
            print(f"  (render {fmt} skipped: {e})")

def load_part_titles():
    """name -> (mod, title) from manifest/curated-parts.tsv (header: mod\tname\ttitle)."""
    path = os.path.join(REPO, "manifest", "curated-parts.tsv")
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            next(f, None)  # skip header
            for line in f:
                cols = line.rstrip("\n").split("\t")
                if len(cols) >= 3:
                    out[cols[1]] = (cols[0], cols[2])  # name -> (mod, title)
    except FileNotFoundError:
        pass
    return out

def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def _trunc(s, n=27):
    s = s or ""
    return s if len(s) <= n else s[:n - 1] + "…"

def _wrap(s, width=15, maxlines=2):
    """Greedy word-wrap a title into <=maxlines lines of <=width chars, ellipsizing overflow.
    Used for the square node tiles, which are too narrow for the old single-line title."""
    words = (s or "").strip().split()
    lines, cur = [], ""
    while words:
        w = words[0]
        cand = (cur + " " + w).strip()
        if not cur or len(cand) <= width:
            cur = cand; words.pop(0)
        else:
            lines.append(cur); cur = ""
            if len(lines) == maxlines - 1:
                break                                # remainder goes on the final line
    if cur or not lines:
        lines.append(cur)
    if words:                                        # words left over -> pack onto last line + ellipsize
        combined = (lines[-1] + " " + " ".join(words)).strip()
        lines[-1] = combined
    lines = [ln if len(ln) <= width else ln[:width - 1].rstrip() + "…" for ln in lines]
    return lines[:maxlines]

def emit_html(disc, nodes, by):
    """Self-contained read-only viewer: renders its OWN inline SVG from the node
    positions resolve() already computed (no graphviz dependency), then click a
    node to list the parts (and upgrades) that live there."""
    PAD, COLW, YS, NW, NH = 44, 196, 1.4, 88, 88    # layout geometry (px) — square KSP-style tiles
    miny = min(n["_y"] for n in nodes)
    def X(n): return PAD + n["tier"] * COLW
    def Y(n): return PAD + (n["_y"] - miny) * YS
    width = max(X(n) for n in nodes) + NW + PAD
    height = max(Y(n) for n in nodes) + NH + PAD + 20  # +20 for tier header row
    maxtier = max(n["tier"] for n in nodes)

    edges, boxes = [], []
    for n in nodes:                                  # edges first (drawn under nodes)
        x2, y2 = X(n), Y(n) + NH / 2                 # child left-edge midpoint
        for pid in n.get("parents", []) or []:
            p = by.get(pid)
            if not p: continue
            x1, y1 = X(p) + NW, Y(p) + NH / 2         # parent right-edge midpoint
            dash = f' stroke-dasharray="5 4" stroke="{MULTI_ENTRY_COLOR}"' if n.get("anyToUnlock") else ' stroke="#777"'
            # KSP-style: a single straight segment anchor->anchor, no routing (crossings allowed)
            edges.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}"{dash} stroke-width="1.5"/>')
    for t in range(maxtier + 1):                     # tier column headers
        boxes.append(f'<text x="{PAD + t*COLW:.0f}" y="20" fill="#888" font-size="12" font-weight="600">T{t}</text>')
    for n in nodes:
        d = disc[n["discipline"]]; x, y = X(n), Y(n); cx = x + NW / 2
        np = len(n.get("parts") or []); nu = len(n.get("upgrades") or [])
        badge = (f"{np}p" + (f"+{nu}u" if nu else "")) if (np or nu) else "—"
        lines = _wrap(n["title"], width=13, maxlines=3)   # small title inside the square; full detail on click
        starts = {1: [40], 2: [32, 46], 3: [24, 38, 52]}[len(lines)]
        tspans = "".join(
            f'<text x="{cx:.0f}" y="{y+dy:.0f}" text-anchor="middle" fill="#15212b" '
            f'font-size="10.5" font-weight="600">{_esc(ln)}</text>'
            for dy, ln in zip(starts, lines))
        boxes.append(
            f'<g class="node" data-id="{_esc(n["id"])}" tabindex="0">'
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{NW}" height="{NH}" rx="2" fill="{d["color"]}"/>'
            f'{tspans}'
            f'<text x="{cx:.0f}" y="{y+NH-9:.0f}" text-anchor="middle" fill="#2c3e50" '
            f'font-size="9">T{n["tier"]} · {badge}</text>'
            f'</g>')
    svg = (f'<svg id="tree" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
           f'xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI,Helvetica,Arial,sans-serif">'
           f'<g fill="none">' + "".join(edges) + '</g>'
           + "".join(boxes) + "</svg>")

    titles = load_part_titles()
    data = {}
    for n in nodes:
        parts = [{"name": p, "mod": titles.get(p, ("", ""))[0], "title": titles.get(p, ("", ""))[1]}
                 for p in (n.get("parts") or [])]
        data[n["id"]] = {
            "title": n["title"], "discipline": disc[n["discipline"]]["title"],
            "color": disc[n["discipline"]]["color"], "tier": n["tier"], "cost": n["cost"],
            "anyToUnlock": bool(n.get("anyToUnlock")), "flavor": (n.get("flavor") or "").strip(),
            "parts": parts, "upgrades": list(n.get("upgrades") or []),
        }
    npart = sum(len(d["parts"]) for d in data.values())
    sub = f"{len(nodes)} nodes · {npart} parts placed · click a node"
    payload = json.dumps(data, ensure_ascii=False)
    # neutralize HTML-significant chars so the JSON can't break out of the <script> body
    bs = chr(92)  # a backslash, built at runtime (tool transport JSON-decodes typed uXXXX escapes)
    for ch in ("<", ">", "&", chr(0x2028), chr(0x2029)):
        payload = payload.replace(ch, bs + "u%04x" % ord(ch))
    # single pass: a sentinel appearing inside injected data/svg can't be re-matched and clobbered
    fills = {"__SUBTITLE__": sub, "__DATA__": payload, "__SVG__": svg}
    html = re.sub("|".join(map(re.escape, fills)), lambda m: fills[m.group(0)], HTML_TEMPLATE)
    with open(os.path.join(REND, "axe-tree.html"), "w", encoding="utf-8") as f:
        f.write(html)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>RP-AXE tech tree</title>
<style>
  :root{--bg:#1a1a1a;--panel:#222;--ink:#eee;--mut:#9aa;--line:#333}
  *{box-sizing:border-box} html,body{margin:0;height:100%}
  body{display:flex;font-family:Segoe UI,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink)}
  #canvas{flex:1;overflow:auto;position:relative}
  #canvas svg{display:block}
  g.node{cursor:pointer} g.node text{pointer-events:none;user-select:none}
  g.node rect{transition:stroke .1s;stroke:#0000;stroke-width:0}
  g.node:hover rect{stroke:#ffffffcc;stroke-width:2}
  g.node.sel rect{stroke:#fff;stroke-width:3}
  g.node:focus{outline:none} g.node:focus rect{stroke:#ffd166;stroke-width:3}
  #bar{position:fixed;top:8px;left:8px;display:flex;gap:6px;align-items:center;
       background:#000a;padding:5px 8px;border-radius:6px;font-size:12px}
  #bar input{background:#111;border:1px solid #444;color:#eee;border-radius:4px;padding:3px 6px;width:150px}
  #bar button{background:#333;border:1px solid #555;color:#eee;border-radius:4px;padding:2px 8px;cursor:pointer}
  #bar button:hover{background:#444}
  #panel{width:360px;min-width:360px;background:var(--panel);border-left:1px solid var(--line);
         overflow:auto;padding:16px}
  #panel .hint{color:var(--mut);margin-top:40px;text-align:center;font-style:italic}
  .ttl{font-size:19px;font-weight:600;line-height:1.2}
  .meta{color:var(--mut);font-size:13px;margin:6px 0 12px;display:flex;align-items:center;gap:6px}
  .dot{width:11px;height:11px;border-radius:50%;display:inline-block}
  .flav{font-style:italic;color:#cdd;font-size:13px;line-height:1.45;
        border-left:3px solid var(--line);padding-left:10px;margin-bottom:14px}
  .sec{text-transform:uppercase;letter-spacing:.06em;font-size:11px;color:var(--mut);
       border-bottom:1px solid var(--line);padding-bottom:4px;margin:16px 0 8px}
  ul.parts{list-style:none;margin:0;padding:0}
  ul.parts li{padding:6px 0;border-bottom:1px solid #2a2a2a}
  .pt{font-size:14px}
  .pn{font-size:12px;color:var(--mut);font-family:Consolas,monospace}
  .mod{color:#7aa2c4}
  .empty{color:#777;font-style:italic;padding:6px 0}
  #sub{position:fixed;bottom:8px;left:8px;color:var(--mut);font-size:11px;background:#000a;padding:3px 8px;border-radius:5px}
</style></head><body>
<div id="canvas">__SVG__</div>
<div id="bar">
  <input id="q" placeholder="find node / part…" autocomplete="off">
  <button id="zo">−</button><span id="zl">100%</span><button id="zi">+</button>
</div>
<div id="sub">__SUBTITLE__</div>
<div id="panel"><div class="hint">Click any node to see the parts that live there.</div></div>
<script>
const DATA=__DATA__;
const panel=document.getElementById('panel');
const nodeG={};let cur=null;
const esc=s=>(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function select(id,scroll){
  if(cur)cur.classList.remove('sel');
  const g=nodeG[id];if(g){g.classList.add('sel');cur=g;if(scroll)g.scrollIntoView({block:'center',inline:'center'});}
  const d=DATA[id];if(!d){return;}
  let h=`<div class="ttl">${esc(d.title)}</div>`;
  h+=`<div class="meta"><span class="dot" style="background:${d.color}"></span>${esc(d.discipline)} · T${d.tier} · ${d.cost}◈${d.anyToUnlock?' · any-parent':''}</div>`;
  if(d.flavor)h+=`<div class="flav">${esc(d.flavor)}</div>`;
  h+=`<div class="sec">Parts (${d.parts.length})</div>`;
  if(d.parts.length){h+='<ul class="parts">';
    for(const p of d.parts)h+=`<li><div class="pt">${esc(p.title||p.name)}</div><div class="pn">${esc(p.name)}${p.mod?' · <span class="mod">'+esc(p.mod)+'</span>':''}</div></li>`;
    h+='</ul>';}
  else h+='<div class="empty">— no parts assigned —</div>';
  if(d.upgrades.length){h+=`<div class="sec">Upgrades (${d.upgrades.length})</div><ul class="parts">`;
    for(const u of d.upgrades)h+=`<li><div class="pn">${esc(u)}</div></li>`;h+='</ul>';}
  panel.innerHTML=h;
}
document.querySelectorAll('#canvas g.node').forEach(g=>{
  const id=g.getAttribute('data-id');if(!id)return;nodeG[id]=g;
  g.addEventListener('click',()=>select(id,false));
  g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select(id,false);}});
});
// search: first node whose id/title or any part name/title matches
document.getElementById('q').addEventListener('keydown',e=>{
  if(e.key!=='Enter')return;
  const q=e.target.value.trim().toLowerCase();if(!q)return;
  for(const id in DATA){const d=DATA[id];
    if(id.toLowerCase().includes(q)||d.title.toLowerCase().includes(q)||
       d.parts.some(p=>p.name.toLowerCase().includes(q)||(p.title||'').toLowerCase().includes(q))){
      select(id,true);break;}}
});
// zoom (scale svg width/height; viewBox keeps it crisp, scroll container handles pan)
const svg=document.querySelector('#canvas svg');
const bw=parseFloat(svg.getAttribute('width')),bh=parseFloat(svg.getAttribute('height'));let z=1;
function zoom(nz){z=Math.max(.2,Math.min(4,nz));svg.setAttribute('width',bw*z);svg.setAttribute('height',bh*z);document.getElementById('zl').textContent=Math.round(z*100)+'%';}
document.getElementById('zi').onclick=()=>zoom(z*1.2);
document.getElementById('zo').onclick=()=>zoom(z/1.2);
</script></body></html>"""

def main():
    disc, meta, nodes = load()
    by = {n["id"]: n for n in nodes}
    validate(disc, nodes, by)
    resolve(disc, meta, nodes, by)       # cost, parent defaults, lane-grid fallback positions
    delta_layout(disc, nodes, by)        # override positions with the delta (layered) layout
    validate_design(disc, nodes, by)
    emit_cfg(disc, nodes)
    emit_render(disc, meta, nodes, by)
    emit_html(disc, nodes, by)
    # summary
    print(f"OK  {len(nodes)} nodes / {len(set(n['discipline'] for n in nodes))} disciplines")
    perd = collections.Counter(n["discipline"] for n in nodes)
    for d, c in sorted(perd.items(), key=lambda kv: disc[kv[0]]["order"]):
        print(f"   {c:>3}  {d}")
    print("cost by tier:")
    cbt = collections.defaultdict(int)
    for n in nodes: cbt[n["tier"]] += n["cost"]
    for t in sorted(cbt): print(f"   T{t}: {cbt[t]:>6}")
    print(f"   total: {sum(n['cost'] for n in nodes)}")
    print("-> GameData/RP-AXE/design/Tree/AxeTechTree.cfg (+ .editor.cfg), tree/render/axe-tree.svg|png|html")

if __name__ == "__main__": main()
