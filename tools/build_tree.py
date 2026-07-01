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

def sugiyama_layout(disc, nodes, by, sweeps=8):
    """Proper layered (Sugiyama) layout. Phase 1 (layer assignment) is given: tier = column.
    Adds the phases that make a layered DAG legible:
      * DUMMY NODES on every edge spanning >1 tier, so long edges get their own lane and take
        part in ordering (instead of shooting across everything);
      * CROSSING MINIMISATION by the median heuristic, alternating up/down sweeps, keeping the
        best ordering seen;
      * COORDINATE ASSIGNMENT that pulls each vertex (real + dummy) toward its neighbours' mean
        under a minimum gap, which straightens the dummy chains into clean routes.
    Sets n['_x'],n['_y'] (px, for the game cfg + render) on real nodes and RETURNS edge routes
    [(parentId, childId, [(tier, y_px), ...]), ...] tracing each edge through its dummies
    (adjacent-tier edges = 2 points = straight)."""
    tier = {n["id"]: n["tier"] for n in nodes}
    layers = collections.defaultdict(list)              # tier -> [vertex keys] (real ids + dummies)
    for n in nodes: layers[tier[n["id"]]].append(n["id"])
    prev, nxt = collections.defaultdict(list), collections.defaultdict(list)
    vtier = {n["id"]: tier[n["id"]] for n in nodes}
    seed = {n["id"]: float(disc[n["discipline"]]["order"]) for n in nodes}  # cluster by discipline
    chains, dcount = [], 0
    for n in nodes:
        cid, ct = n["id"], tier[n["id"]]
        for pid in n.get("parents") or []:
            if pid not in by: continue
            chain = [pid]
            for t in range(tier[pid] + 1, ct):          # one dummy per skipped tier
                dk = f"__d{dcount}"; dcount += 1
                vtier[dk] = t; layers[t].append(dk); seed[dk] = seed[pid]
                chain.append(dk)
            chain.append(cid)
            for a, b in zip(chain, chain[1:]): nxt[a].append(b); prev[b].append(a)
            chains.append((pid, cid, chain))
    order = sorted(layers)                               # tiers ascending
    rank = {}
    def reindex(t, key):
        layers[t].sort(key=key)
        for i, v in enumerate(layers[t]): rank[v] = i
    for t in order: reindex(t, lambda v: (seed[v], str(v)))
    def median(ids):
        vs = sorted(rank[w] for w in ids)
        if not vs: return -1.0
        m = len(vs) // 2
        return vs[m] if len(vs) % 2 else (vs[m - 1] + vs[m]) / 2.0
    def crossings():
        c = 0
        for t in order[:-1]:
            es = sorted((rank[u], rank[w]) for u in layers[t] for w in nxt[u] if vtier[w] == t + 1)
            seq = [w for _, w in es]
            for i in range(len(seq)):                    # count inversions in the lower endpoints
                for j in range(i + 1, len(seq)):
                    if seq[i] > seq[j]: c += 1
        return c
    best = None
    for s in range(sweeps):                             # median sweeps, keep the least-crossing order
        for t in (order if s % 2 == 0 else order[::-1]):
            adj = prev if s % 2 == 0 else nxt
            keep = dict(rank)
            reindex(t, lambda v: (median(adj[v]) if adj[v] else float(keep[v]), keep[v]))
        c = crossings()
        if best is None or c < best[0]:
            best = (c, {t: list(layers[t]) for t in order})
    for t in order:                                     # restore best ordering
        layers[t] = best[1][t]
        for i, v in enumerate(layers[t]): rank[v] = i
    isd = lambda v: v.startswith("__d")                 # dummies are thin waypoints, not tiles:
    def gap(a, b):                                       # only real<->real needs a full row of space
        if isd(a) and isd(b): return 0.12
        return 0.45 if (isd(a) or isd(b)) else 1.0
    def pav(a):                                          # isotonic regression (pool adjacent violators):
        vals, cnts = [], []                             # nearest non-decreasing fit to targets a (unit wt)
        for x in a:
            vals.append(float(x)); cnts.append(1)
            while len(vals) > 1 and vals[-2] >= vals[-1]:
                v2, c2 = vals.pop(), cnts.pop(); v1, c1 = vals.pop(), cnts.pop()
                vals.append((v1 * c1 + v2 * c2) / (c1 + c2)); cnts.append(c1 + c2)
        out = []
        for v, c in zip(vals, cnts): out.extend([v] * c)
        return out
    y = {v: float(rank[v]) for t in order for v in layers[t]}   # coordinate assignment
    for _ in range(30):                                 # place each layer as near neighbour-mean as the
        des = {v: (sum(y[w] for w in prev[v] + nxt[v]) / len(prev[v] + nxt[v])   # gaps allow (exact, compacts)
                   if (prev[v] or nxt[v]) else y[v]) for v in y}
        for t in order:
            row = layers[t]
            if not row: continue
            c, acc = [0.0] * len(row), 0.0              # cumulative min-gap offset along the layer
            for i in range(1, len(row)):
                acc += gap(row[i - 1], row[i]); c[i] = acc
            z = pav([des[row[i]] - c[i] for i in range(len(row))])   # y = z + offset, z non-decreasing
            for i, v in enumerate(row): y[v] = z[i] + c[i]
    miny = min(y.values())
    Y = lambda v: int(MARGIN_Y + (y[v] - miny) * SPACING_Y)
    for n in nodes:
        n["_x"] = MARGIN_X + tier[n["id"]] * TIERW
        n["_y"] = Y(n["id"])
    return [(pid, cid, [(vtier[v], Y(v)) for v in chain]) for pid, cid, chain in chains]

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
    # TRANSITIVE REDUCTION: on a convergence node, a parent that is ALSO an ancestor of another parent
    # is a redundant edge (the longer path already connects them) — clutter. (Skip anyToUnlock nodes:
    # there a "shortcut" parent is an intentional earlier/alternate entry, not redundancy.)
    def reaches(a, b):
        st, sn = list(chl[a]), set()
        while st:
            x = st.pop()
            if x == b: return True
            if x in sn: continue
            sn.add(x); st += chl[x]
        return False
    for n in nodes:
        if n.get("anyToUnlock"): continue
        ps = [p for p in (n.get("parents") or []) if p in by]
        for p in ps:
            if any(p2 != p and reaches(p, p2) for p2 in ps):
                warns.append(f"redundant (transitively-implied) edge: {p} -> {n['id']} "
                             f"(reaches it via another parent)")
    for r in roots:
        if r not in ("start", "parking"): warns.append(f"extra root (no parents besides start): {r}")
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
    a(f"{indent}\thideEmpty = {'True' if n.get('hide_empty') else 'False'}")
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

def _lum(hexcolor):
    """Rough perceived luminance 0..255 of a #rrggbb color (to pick dark/light tile text)."""
    h = hexcolor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _dotesc(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')

def _dot_exe():
    """Prefer a STANDALONE Graphviz (it ships gvplugin_core -> semantic <g class='node'> svg).
    GIMP's bundled dot is usually first on PATH but lacks that plugin, so it only emits
    cairo picture-svg (no clickable groups). Fall back to PATH `dot` if no standalone found."""
    for c in (r"C:\Program Files\Graphviz\bin\dot.exe",
              r"C:\Program Files (x86)\Graphviz\bin\dot.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\Graphviz\bin\dot.exe")):
        if os.path.exists(c):
            return c
    return "dot"

def _dot_svg(disc, nodes, by):
    """Primary interactive canvas: graphviz `dot` lays out AND orthogonally routes the DAG
    (splines=ortho — obstacle-avoiding right-angle lines) as uniform square KSP-style tiles.
    Returns the routed <svg>…</svg> with data-id wired onto each node <g>, or None if dot
    is unavailable / fails (emit_html then falls back to the pure-Python inline renderer)."""
    L = ['digraph AXE {',
         '  rankdir=LR; bgcolor="transparent"; splines=ortho; nodesep=0.22; ranksep=1.5;',
         '  node[shape=box,style=filled,fixedsize=true,width=1.55,height=1.05,'
         'fontname="Helvetica,Arial,sans-serif",fontsize=8,color="#00000000"];',
         '  edge[arrowsize=0.5];']
    for n in nodes:                                  # uniform square tiles, dark/light text by luminance
        d = disc[n["discipline"]]
        fc = "#0d0d0d" if _lum(d["color"]) > 140 else "#f0f0f0"
        lbl = "\\n".join(_dotesc(ln) for ln in _wrap(n["title"], width=13, maxlines=3))
        L.append(f'  "{n["id"]}" [label="{lbl}",fillcolor="{d["color"]}",fontcolor="{fc}"];')
    tiers = collections.defaultdict(list)            # tier = column (rank)
    for n in nodes: tiers[n["tier"]].append(n["id"])
    for t in sorted(tiers):
        L.append("  { rank=same; " + " ".join(f'"{i}"' for i in tiers[t]) + " }")
    for n in nodes:
        dashed = n.get("anyToUnlock")
        for p in n.get("parents", []) or []:
            style = f'color="{MULTI_ENTRY_COLOR}",style=dashed' if dashed else 'color="#8a8f98"'
            L.append(f'  "{p}" -> "{n["id"]}" [{style}];')
    L.append("}")
    try:
        proc = subprocess.run([_dot_exe(), "-Tsvg"], input="\n".join(L),
                              capture_output=True, text=True, encoding="utf-8", timeout=180)
    except Exception as e:
        print(f"  (html: dot ortho unavailable, using inline fallback: {e})")
        return None
    raw = proc.stdout or ""
    if "<svg" not in raw:
        print(f"  (html: dot produced no svg, inline fallback; {proc.stderr.strip()[:120]})")
        return None
    raw = raw[raw.index("<svg"):]                    # drop xml/doctype preamble
    m = re.search(r'viewBox="([\d.\- ]+)"', raw)     # rewrite <svg>: id + numeric px size so zoom JS works
    vb = m.group(1) if m else "0 0 2000 2000"
    p = vb.split(); w, h = (p[2], p[3]) if len(p) == 4 else ("2000", "2000")
    raw = re.sub(r'<svg[^>]*>',
                 f'<svg id="tree" width="{float(w):.0f}" height="{float(h):.0f}" viewBox="{vb}" '
                 f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                 f'font-family="Segoe UI,Helvetica,Arial,sans-serif">', raw, count=1)
    # wire click targets: derive data-id/tabindex from each node <g>'s <title> (the node id)
    raw, n_wired = re.subn(r'<g\b[^>]*\bclass="node"[^>]*>\s*<title>([^<]+)</title>',
                 lambda mm: f'<g class="node" data-id="{mm.group(1)}" tabindex="0"><title>{mm.group(1)}</title>',
                 raw)
    if n_wired == 0:   # picture-only cairo svg (no semantic node groups) — unusable interactively
        print("  (html: dot svg has no clickable node groups — missing gvplugin_core? inline fallback)")
        return None
    return raw

def _inline_svg(disc, nodes, by, routes):
    """Interactive canvas: the pure-Python Sugiyama result — square tiles on the tier grid, edges
    drawn as polylines through the layout's dummy waypoints (adjacent-tier edges = straight).
    Emits the <g class="node" data-id> contract the viewer's click/search/zoom JS expects."""
    PAD, COLW, YS, NW, NH = 44, 196, 1.4, 88, 88    # layout geometry (px) — square KSP-style tiles
    miny = min([n["_y"] for n in nodes] + [yv for _, _, ch in routes for _, yv in ch])
    def X(n): return PAD + n["tier"] * COLW
    def Y(n): return PAD + (n["_y"] - miny) * YS
    width = max(X(n) for n in nodes) + NW + PAD
    height = max(Y(n) for n in nodes) + NH + PAD + 20  # +20 for tier header row
    maxtier = max(n["tier"] for n in nodes)

    edges, boxes = [], []
    # --- orthogonal routing: H/V segments on the grid, vertical legs nudged into per-gutter
    #     lanes (interval-graph colouring) so parallel lines get spacing, not a pile-up ---
    yc = lambda yv: PAD + (yv - miny) * YS + NH / 2
    chains_c, seg = [], collections.defaultdict(list)     # seg: gutter g -> [ymin, ymax, key]
    for ei, (pid, cid, chain) in enumerate(routes):
        ts = [t for t, _ in chain]; ys = [yc(yv) for _, yv in chain]
        chains_c.append((ei, cid, ts, ys))
        for i in range(len(ts) - 1):                      # a vertical leg lives in the gutter right of col ts[i]
            seg[ts[i]].append([min(ys[i], ys[i + 1]), max(ys[i], ys[i + 1]), (ei, i)])
    lane, lanes_n = {}, {}                                # colour each gutter's verticals: overlapping -> distinct lane
    for g, segs in seg.items():
        segs.sort(); ends = []                            # ends[l] = last ymax placed on lane l
        for lo, hi, key in segs:
            l = next((j for j, e in enumerate(ends) if e <= lo + 1e-6), -1)
            if l < 0: l = len(ends); ends.append(hi)
            else: ends[l] = hi
            lane[key] = l
        lanes_n[g] = len(ends)
    def lane_x(g, l):                                     # spread this gutter's lanes across its width
        return PAD + g * COLW + NW + (l + 1) / (lanes_n[g] + 1) * (COLW - NW)
    for ei, cid, ts, ys in chains_c:
        dashed = by[cid].get("anyToUnlock")
        stroke = f'stroke="{MULTI_ENTRY_COLOR}" stroke-dasharray="5 4"' if dashed else 'stroke="#8a8f98"'
        pts = [(PAD + ts[0] * COLW + NW, ys[0])]          # parent right anchor
        for i in range(len(ts) - 1):
            lx = lane_x(ts[i], lane[(ei, i)])
            pts += [(lx, ys[i]), (lx, ys[i + 1])]          # H into the lane, then V to the next row
        pts.append((PAD + ts[-1] * COLW, ys[-1]))          # child left anchor
        edges.append(f'<polyline points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in pts)}" '
                     f'fill="none" {stroke} stroke-width="1.4" stroke-linejoin="round" shape-rendering="crispEdges"/>')
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
    return (f'<svg id="tree" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
            f'xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI,Helvetica,Arial,sans-serif">'
            f'<g fill="none">' + "".join(edges) + '</g>'
            + "".join(boxes) + "</svg>")

def emit_html(disc, nodes, by, routes):
    """Self-contained read-only viewer: renders the pure-Python Sugiyama layout (layered +
    dummy-routed edges) as square tiles; click a node to list the parts (and upgrades) that live
    there. (_dot_svg stays available if a full Graphviz with gvplugin_core is ever installed.)"""
    svg = _inline_svg(disc, nodes, by, routes)

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
  g.node rect,g.node polygon{transition:stroke .1s;stroke:#0000;stroke-width:0}
  g.node:hover rect,g.node:hover polygon{stroke:#ffffffcc;stroke-width:2}
  g.node.sel rect,g.node.sel polygon{stroke:#fff;stroke-width:3}
  g.node:focus{outline:none} g.node:focus rect,g.node:focus polygon{stroke:#ffd166;stroke-width:3}
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

def emit_prototype_data(disc, nodes, by, routes):
    """Emit tree/render/prototype/tree-data.js (window.TREE) for the Canvas rendering prototype.
    Non-destructive — separate from axe-tree.html. Carries node positions and per-edge waypoints
    (from the Sugiyama routes) in ONE coordinate space (the cfg px space: x = MARGIN_X + tier*TIERW,
    y = the layout's row y). `pos` + optional `waypoints` are the layout<->render contract; the layout
    owner can later produce them. The rendering prototype decides how they are drawn (anchors, arrows,
    kspStock vs laneRouted); it treats pos as the node's reference point and waypoints as interior
    routing hints (endpoints coincide with node pos.y)."""
    protod = os.path.join(REND, "prototype")
    os.makedirs(protod, exist_ok=True)
    titles = load_part_titles()
    disciplines = {k: {"title": v["title"], "order": v["order"], "color": v["color"], "icon": v["icon"]}
                   for k, v in disc.items()}
    jnodes = []
    for n in nodes:
        parts = [{"name": p, "mod": titles.get(p, ("", ""))[0], "title": titles.get(p, ("", ""))[1]}
                 for p in (n.get("parts") or [])]
        jnodes.append({
            "id": n["id"], "title": n["title"], "discipline": n["discipline"],
            "tier": n["tier"], "cost": n["cost"], "anyToUnlock": bool(n.get("anyToUnlock")),
            "flavor": (n.get("flavor") or "").strip(),
            "parts": parts, "upgrades": list(n.get("upgrades") or []),
            "pos": [n["_x"], n["_y"]],
        })
    jedges = [{"from": pid, "to": cid, "anyToUnlock": bool(by[cid].get("anyToUnlock")),
               "waypoints": [[MARGIN_X + t * TIERW, y] for t, y in chain]}
              for pid, cid, chain in routes]
    payload = {"disciplines": disciplines, "nodes": jnodes, "edges": jedges}
    with open(os.path.join(protod, "tree-data.js"), "w", encoding="utf-8") as f:
        f.write("// GENERATED by tools/build_tree.py from tree/nodes.yaml — DO NOT EDIT BY HAND\n")
        f.write("window.TREE = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n")

def load_placement():
    """part->node, upgrade->node from manifest/*-placement.tsv (skip EXPERIMENTAL/REVIEW sentinels)."""
    def read(fn):
        out = {}; p = os.path.join(REPO, "manifest", fn)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                next(f, None)
                for ln in f:
                    c = ln.rstrip("\n").split("\t")
                    if len(c) >= 2 and c[1] not in ("EXPERIMENTAL", "REVIEW"): out[c[0]] = c[1]
        return out
    return read("part-placement.tsv"), read("upgrade-placement.tsv")

def merge_placement(nodes, by, use_auto=True):
    """Fold the placement TSVs into node unlocks; inline nodes.yaml seeds win as hand overrides so each
    part/upgrade gets exactly one home. Returns merged part->node, upgrade->node (for the game patch).
    use_auto=False (meta.auto_placement) => parts come ONLY from explicit `parts:` seeds (spine rebuild)."""
    hand_p = {p: n["id"] for n in nodes for p in (n.get("parts") or [])}
    hand_u = {u: n["id"] for n in nodes for u in (n.get("upgrades") or [])}
    p2n, u2n = load_placement() if use_auto else ({}, {})
    p2n.update(hand_p); u2n.update(hand_u)          # hand seeds override the auto placement
    for n in nodes: n["parts"] = []; n["upgrades"] = []
    for part, node in sorted(p2n.items()):
        if node in by: by[node]["parts"].append(part)
    for up, node in sorted(u2n.items()):
        if node in by: by[node]["upgrades"].append(up)
    return p2n, u2n

def emit_placement_patch(p2n, u2n, parking="parking"):
    """@PART/@PARTUPGRADE TechRequired assignment. First PARK every part/upgrade on the parking node,
    then override the explicitly-placed ones onto their tree nodes. Same :FOR[RP-AXE] pass, applied in
    file order (wildcard first), so anything not homed lands in `parking` instead of piling onto `start`."""
    L = ["// GENERATED by tools/build_tree.py — DO NOT EDIT BY HAND",
         "// Line 1-2 park EVERY part/upgrade on the parking node; the lines below override the",
         "// explicitly-placed ones (same pass, applied in file order) onto their real tree nodes.",
         f"@PART[*]:FOR[RP-AXE] {{ %TechRequired = {parking} }}",
         f"@PARTUPGRADE[*]:FOR[RP-AXE] {{ %techRequired = {parking} }}"]
    for part, node in sorted(p2n.items()):
        L.append(f"@PART[{part}]:FOR[RP-AXE] {{ %TechRequired = {node} }}")
    for up, node in sorted(u2n.items()):
        L.append(f"@PARTUPGRADE[{up}]:FOR[RP-AXE] {{ %techRequired = {node} }}")
    with open(os.path.join(OUTD, "AxePartPlacement.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

PROBE_SUBTREE = {"RN_US_Probes": "hire_JPL", "RN_Soviet_Probes": "hire_OKB"}

def route_probe_mods(by, p2n):
    """Route every part from the OPTIONAL US/Soviet probe packs into its charter subtree node
    (hire_JPL / hire_OKB) instead of parking. Config-only containment; the per-probe prerequisite-tech
    checklist is the deferred requirements engine. Skips DEPRECATED parts and absent subtree nodes."""
    path = os.path.join(REPO, "manifest", "curated-parts.tsv")
    if not os.path.exists(path): return
    n = 0
    with open(path, encoding="utf-8") as f:
        next(f, None)
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < 3 or c[0] not in PROBE_SUBTREE: continue
            node = PROBE_SUBTREE[c[0]]
            if node not in by or "DEPRECATED" in c[2].upper(): continue
            p2n[c[1]] = node
            by[node].setdefault("parts", []).append(c[1]); n += 1
    if n: print(f"probe subtree: routed {n} US/Soviet probe parts -> hire_JPL / hire_OKB")

def check_probe_requirements(nodes):
    """Cross-check manifest/probe-requirements.tsv against the spine + library.yaml vocabulary: each
    required breakthrough is classified in-spine / library-only (pull-list) / MISSING (real tree gap).
    This turns each historical probe into a pull-list that grows the spine (and exposes missing techs)."""
    path = os.path.join(REPO, "manifest", "probe-requirements.tsv")
    if not os.path.exists(path): return
    spine = {n["id"] for n in nodes}
    lib = set()
    libpath = os.path.join(TREE, "library.yaml")
    if os.path.exists(libpath):
        with open(libpath, encoding="utf-8") as f:
            lib = set(re.findall(r'^\s*-\s*id:\s*(\S+)', f.read(), re.M))
    req = collections.Counter(); nprobes = 0
    with open(path, encoding="utf-8") as f:
        next(f, None)
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < 6 or not c[0].strip(): continue
            nprobes += 1
            for nid in c[5].split(";"):
                nid = nid.strip()
                if nid: req[nid] += 1
    pull = sorted((n for n in req if n not in spine and n in lib), key=lambda x: -req[x])
    gaps = sorted(n for n in req if n not in spine and n not in lib)
    in_spine = [n for n in req if n in spine]
    print(f"probe requirements: {nprobes} probes -> {len(req)} distinct breakthroughs "
          f"({len(in_spine)} in spine / {len(pull)} to pull from library / {len(gaps)} gaps)")
    if pull: print("   pull into spine: " + ", ".join(f"{n}(x{req[n]})" for n in pull))
    if gaps: print("   ! TREE GAPS (no node anywhere): " + ", ".join(gaps))

def main():
    disc, meta, nodes = load()
    by = {n["id"]: n for n in nodes}
    validate(disc, nodes, by)
    resolve(disc, meta, nodes, by)       # cost, parent defaults, lane-grid fallback positions
    routes = sugiyama_layout(disc, nodes, by)   # layered (Sugiyama) layout + dummy-routed edges
    validate_design(disc, nodes, by)
    p2n, u2n = merge_placement(nodes, by, meta.get("auto_placement", True))  # P2 auto-placement (meta-gated)
    route_probe_mods(by, p2n)            # optional US/Soviet probe packs -> their charter subtree nodes
    emit_cfg(disc, nodes)
    emit_render(disc, meta, nodes, by)
    emit_html(disc, nodes, by, routes)
    emit_prototype_data(disc, nodes, by, routes)   # tree/render/prototype/tree-data.js (Canvas prototype)
    emit_placement_patch(p2n, u2n)
    print(f"placement: {len(p2n)} parts + {len(u2n)} upgrades homed onto "
          f"{len(set(p2n.values())|set(u2n.values()))} nodes -> AxePartPlacement.cfg")
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
    check_probe_requirements(nodes)

if __name__ == "__main__": main()
