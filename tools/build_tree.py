#!/usr/bin/env python3
"""build_tree — compile tree/nodes.yaml (+ tree/disciplines.yaml) into:
  1. GameData/RP-AXE/design/Tree/AxeTechTree.cfg        game form (MM @TechTree patch, wipes stock)
  2. GameData/RP-AXE/design/Tree/AxeTreeMeta.cfg        id->{discipline,tier,cost} for the in-game render plugin
  3. tree/render/axe-tree.{dot,svg,png}                  review render (delta preview, colored by discipline)
  4. tree/render/axe-tree.html + prototype/tree-data.js  interactive HTML viewer / render prototype (the editor)

One source of truth (YAML) -> the game cfg, the editor-openable cfg (Q1 "open without KSP"), and a
picture. Validates: unique ids, known disciplines, parents exist, no cycles. Cost = node.cost or
meta.tier_cost[tier]*scalar. Layout pos auto-derived from (discipline order, tier).
"""
import os, sys, math, subprocess, collections, json, re, datetime
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(ROOT, ".."))
TREE = os.path.join(REPO, "tree")
OUTD = os.path.join(REPO, "GameData", "RP-AXE", "design", "Tree")
REND = os.path.join(TREE, "render")

XSPACING = 0.8                  # horizontal tier-spacing multiplier (1.0 = 380px columns; 0.8 = tighter, tree fits x<0)
X0, TIERW = 0, round(380 * XSPACING)   # x = X0 + tier*TIERW (X anchored to MARGIN_X below); matches renderer.js sugiyama COLW base
Y0, DISCH, SUBH = 300, 100, 34  # y = Y0 + (order-1)*DISCH + sub-stack (lane-grid fallback)
MARGIN_X, MARGIN_Y = -3200, 711 # MARGIN_X is RE-COMPUTED in sugiyama_layout to right-anchor the tree
                                # (rightmost tier at x=-RIGHT_PAD) so it always sits at x<0 inside the R&D
                                # scroll content (right edge pivot-pinned at x=0), for ANY tier count.
RIGHT_PAD = 400                 # px between the rightmost tier and x=0 (right scroll-past padding)
YSPACING = 0.8                  # vertical rank-spacing multiplier (1.0 = 94px per rank; 0.8 = tighter rows)
SPACING_Y = round(94 * YSPACING)  # vertical px per rank unit; matches renderer.js sugiyama SPACING_Y base (94*spacing=1.0)
COORDS_BK = True                # sugiyama_layout coordinate stage: True = Brandes-Kopf block alignment
                                # (straight edges, the in-game default); False = isotonic (PAV) neighbour-mean
KSP_CFG_FLIP_Y = True           # emit_cfg only: mirror y (compiler y-down -> KSP canvas y-up) so the tree
                                # isn't upside-down in R&D. Prototype/SVG stay y-down. Flip if it renders inverted.
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
    global MARGIN_X                                     # right-anchor: rightmost tier at -RIGHT_PAD, tree grows
    MARGIN_X = -((max(tier.values()) if tier else 0) * TIERW + RIGHT_PAD)   #  leftward as tiers are added
    layers = collections.defaultdict(list)              # tier -> [vertex keys] (real ids + dummies)
    for n in nodes: layers[tier[n["id"]]].append(n["id"])
    prev, nxt = collections.defaultdict(list), collections.defaultdict(list)
    segprev = collections.defaultdict(list)             # adjacent-rank segment predecessors only (BK proper layering)
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
            for a, b in zip(chain, chain[1:]):
                nxt[a].append(b); prev[b].append(a)
                if vtier[b] == vtier[a] + 1: segprev[b].append(a)   # BK: only adjacent-forward hops
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
    # --- Brandes-Kopf coordinate assignment (Brandes & Kopf 2002): align each vertex to its median
    #     segment-neighbour into vertical BLOCKS, then compact blocks under the min-gap, so aligned +
    #     long (dummy-chain) edges become dead-straight runs. Two runs (down-left + down-right mirror)
    #     averaged for L/R balance; a final monotone per-layer sweep guarantees separation. This is the
    #     stage the in-game render CONSUMES (positions emitted to cfg); C# only routes edges. ---
    def bk_type1(Ls, predof, ordm):                     # mark non-inner segments crossing an inner (dummy) one
        conf = set()
        for k in range(len(Ls) - 1):
            upper, lower = Ls[k], Ls[k + 1]
            k0 = scan = 0
            for l1, v in enumerate(lower):
                innerpos = -1
                if isd(v):
                    for u in predof.get(v, ()):
                        if isd(u) and ordm[u] > innerpos: innerpos = ordm[u]
                if l1 == len(lower) - 1 or innerpos >= 0:
                    k1 = innerpos if innerpos >= 0 else len(upper) - 1
                    while scan <= l1:
                        w = lower[scan]
                        for u in predof.get(w, ()):
                            if (ordm[u] < k0 or ordm[u] > k1) and not (isd(u) and isd(w)): conf.add((u, w))
                        scan += 1
                    k0 = k1
        return conf
    def bk_align(Ls, predof, ordm, conf):               # vertical alignment -> root/align blocks (median-biased)
        root = {v: v for layer in Ls for v in layer}
        align = {v: v for layer in Ls for v in layer}
        has = lambda u, w: (u, w) in conf or (w, u) in conf
        for layer in Ls:
            r = -1
            for v in layer:
                ws = predof.get(v) or []
                if not ws: continue
                mp = (len(ws) - 1) / 2.0
                for i in range(int(math.floor(mp)), int(math.ceil(mp)) + 1):
                    if align[v] != v: break
                    w = ws[i]
                    if r < ordm[w] and not has(w, v):
                        align[w] = v; root[v] = root[w]; align[v] = root[w]; r = ordm[w]
        return root, align
    def bk_compact(Ls, root, align, sep):               # horizontal compaction -> coord per vertex (one dir)
        above = {}
        for layer in Ls:
            for i, v in enumerate(layer): above[v] = layer[i - 1] if i > 0 else None
        X, sink, shift = {}, {}, {}
        for layer in Ls:
            for v in layer: sink[v] = v; shift[v] = math.inf
        def place(v):
            if v in X: return
            X[v] = 0.0; w = v
            while True:
                u = above[w]
                if u is not None:
                    ru = root[u]; place(ru)
                    if sink[v] == v: sink[v] = sink[ru]
                    d = sep(u, w)
                    if sink[v] == sink[ru]: X[v] = max(X[v], X[ru] + d)
                    else: shift[sink[ru]] = min(shift[sink[ru]], X[v] - X[ru] - d)
                w = align[w]
                if w == v: break
        for layer in Ls:
            for v in layer:
                if root[v] == v: place(v)
        xs = {}
        for layer in Ls:
            for v in layer:
                xs[v] = X[root[v]]
                s = shift[sink[root[v]]]
                if s < math.inf: xs[v] += s
        return xs
    def bk_run(Ls, sep):
        ordm = {v: i for layer in Ls for i, v in enumerate(layer)}
        predof = {v: sorted(segprev.get(v, ()), key=lambda a: ordm[a]) for layer in Ls for v in layer}
        conf = bk_type1(Ls, predof, ordm)
        root, align = bk_align(Ls, predof, ordm, conf)
        return bk_compact(Ls, root, align, sep)
    def bk_coords(sep):
        Ls = [layers[t] for t in order]
        cL = bk_run(Ls, sep)
        cRr = bk_run([layer[::-1] for layer in Ls], sep)   # within-layer mirror -> down-right
        cR = {k: -v for k, v in cRr.items()}
        for m in (cL, cR):
            mn = min(m.values())
            for k in m: m[k] -= mn
        yy = {v: (cL[v] + cR[v]) / 2.0 for layer in Ls for v in layer}
        for layer in Ls:                                 # guarantee separation after averaging
            for i in range(1, len(layer)):
                need = yy[layer[i - 1]] + sep(layer[i - 1], layer[i])
                if yy[layer[i]] < need: yy[layer[i]] = need
        return yy

    if COORDS_BK:
        nverts = sum(len(layers[t]) for t in order)     # bk_compact.place recurses along block chains
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 2000 + 4 * nverts))
        y = bk_coords(gap)                              # block-aligned coordinates (straight edges)
    else:
        y = {v: float(rank[v]) for t in order for v in layers[t]}   # isotonic (PAV) coordinate assignment
        for _ in range(30):                             # place each layer as near neighbour-mean as the
            des = {v: (sum(y[w] for w in prev[v] + nxt[v]) / len(prev[v] + nxt[v])   # gaps allow (exact, compacts)
                       if (prev[v] or nxt[v]) else y[v]) for v in y}
            for t in order:
                row = layers[t]
                if not row: continue
                c, acc = [0.0] * len(row), 0.0          # cumulative min-gap offset along the layer
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
    # Intentional off-start roots: start/parking/experimental, the charter gates (hire_*), the MLP subtree
    # (gs_soundingStands), and the US2 evaluation sandbox (us2_serviceSandbox) — each a standalone-but-
    # startable line detached from the main tree by design.
    for r in roots:
        if r not in ("start", "parking", "experimental", "gs_soundingStands", "us2_serviceSandbox", "coatl_scienceSandbox") and not r.startswith("hire_"):
            warns.append(f"extra root (no parents besides start): {r}")
    print(f"design checks: {'clean' if not warns else str(len(warns))+' warning(s)'}")
    for w in warns: print(f"   ! {w}")
    return warns

def node_block(disc, n, indent="\t", flip_y=None):
    L = []; a = L.append
    yv = (flip_y - n['_y']) if flip_y is not None else n['_y']   # KSP y-up flip (emit_cfg); None = raw (prototype)
    a(f"{indent}RDNode")
    a(f"{indent}{{")
    a(f"{indent}\tid = {n['id']}")
    a(f"{indent}\ttitle = {n['title']}")
    a(f"{indent}\tdescription = {n.get('flavor','').strip()}")
    a(f"{indent}\tcost = {n['cost']}")
    a(f"{indent}\thideEmpty = {'True' if n.get('hide_empty') else 'False'}")
    a(f"{indent}\tnodeName = node_{n['id']}")
    a(f"{indent}\tanyToUnlock = {'True' if n.get('anyToUnlock') else 'False'}")
    if n.get("impl_todo"):   # placed + researchable, but its in-game effect still needs wiring (docs/IMPL-TODO.md)
        a(f"{indent}\t// NEEDS-IMPL: {n['impl_todo']}")
    # Full GameData path (not the bare name): most discipline icons aren't stock SimpleIcons,
    # so a bare `RDicon_x` would fall back in-game. The PNGs ship in GameData/RP-AXE/design/Tree/icons/
    # (copied from tree/render/prototype/icons/), resolved by KSP like RP-1's RP-1/Tree/Icons/ nodes.
    a(f"{indent}\ticon = RP-AXE/design/Tree/icons/{disc[n['discipline']]['icon']}")
    a(f"{indent}\tpos = {n['_x']},{yv},-1")
    a(f"{indent}\tscale = 1.0")
    for p in n.get("parents", []) or []:
        a(f"{indent}\tParent")
        a(f"{indent}\t{{")
        a(f"{indent}\t\tparentID = {p}")
        a(f"{indent}\t\tlineFrom = RIGHT")
        a(f"{indent}\t\tlineTo = LEFT")
        a(f"{indent}\t}}")
    parts = n.get("parts") or []; ups = n.get("upgrades") or []
    grants = n.get("grants") or []   # provisional capability/facility unlocks (avionics tier, DSN level) — docs/PLACEHOLDERS.md
    if parts or ups or grants:
        a(f"{indent}\tUnlocks")
        a(f"{indent}\t{{")
        for p in parts: a(f"{indent}\t\tpart = {p}")
        for u in ups:   a(f"{indent}\t\tpartUpgrade = {u}")
        if grants: a(f"{indent}\t\t// GRANTs (provisional): capability/facility unlocks; emission may change once the avionics/DSN mechanism is wired")
        for g in grants: a(f"{indent}\t\tpartUpgrade = {g}")
        a(f"{indent}\t}}")
    a(f"{indent}}}")
    return "\n".join(L)

def emit_cfg(disc, nodes):
    os.makedirs(OUTD, exist_ok=True)
    # KSP's R&D canvas is y-up; the compiler lays out y-down. Mirror within the tree's own y-band
    # (minY+maxY - _y) so the tree reads top-to-bottom AND stays in the same vertical envelope.
    ys = [n["_y"] for n in nodes]
    flip_y = (min(ys) + max(ys)) if (KSP_CFG_FLIP_Y and ys) else None
    blocks = "\n".join(node_block(disc, n, flip_y=flip_y) for n in nodes)
    hdr = "// GENERATED by tools/build_tree.py from tree/nodes.yaml — DO NOT EDIT BY HAND\n"
    with open(os.path.join(OUTD, "AxeTechTree.cfg"), "w", encoding="utf-8") as f:
        f.write(hdr + "@TechTree:FOR[ZZZZZ-AXE-Tree]\n{\n\t!RDNode,* {}\n" + blocks + "\n}\n")
    # No .editor.cfg: a standalone TechTree{} in GameData is aggregated by KSP's
    # GetConfigNodes("TechTree"), duplicating every node in-game (54 -> 108). The offline HTML
    # viewer (axe-tree.html / tree/render/prototype) is the editor now; the old KSPTechtreeEditor is sacked.

def emit_treemeta(disc, nodes):
    """Emit GameData/RP-AXE/design/Tree/AxeTreeMeta.cfg — a plain RPAXE_TREEMETA ConfigNode the AXE
    render plugin reads via GameDatabase.GetConfigNodes (NOT a ModuleManager patch). The in-game
    RDNode has no discipline/tier field (and icons collide across disciplines, so discipline can't be
    recovered from the node) — this carries id->{discipline,tier,cost} plus the discipline table and
    the layout constants, so build_tree.py and the plugin share one source of truth. `discipline` is
    the KEY (e.g. FluidDynamics), matching emit_prototype_data / the plugin vocabulary. Multi-line
    blocks (KSP's ConfigNode parser is line-based; no inline `{ a = 1  b = 2 }`)."""
    os.makedirs(OUTD, exist_ok=True)
    L = []; a = L.append
    a("// GENERATED by tools/build_tree.py from tree/nodes.yaml — DO NOT EDIT BY HAND")
    a("RPAXE_TREEMETA")
    a("{")
    a(f"\tmarginX = {MARGIN_X}")
    a(f"\tmarginY = {MARGIN_Y}")
    a(f"\ttierWidth = {TIERW}")
    a("\tnodeSize = 58")
    for n in nodes:
        a("\tNode")
        a("\t{")
        a(f"\t\tid = {n['id']}")
        a(f"\t\tdiscipline = {n['discipline']}")
        a(f"\t\ttier = {n['tier']}")
        a(f"\t\tcost = {n['cost']}")
        a("\t}")
    for k, v in sorted(disc.items(), key=lambda kv: kv[1]["order"]):
        a("\tDiscipline")
        a("\t{")
        a(f"\t\tkey = {k}")
        a(f"\t\torder = {v['order']}")
        a(f"\t\tcolor = {v['color']}")
        a(f"\t\ticon = {v['icon']}")
        a(f"\t\ttitle = {v['title']}")
        a("\t}")
    a("}")
    with open(os.path.join(OUTD, "AxeTreeMeta.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

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

def _fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None

def load_engine_stats():
    """part -> era-ordered list of CONFIG-stat rows, from manifest/engine-stats.tsv
    (tools/extract_engine_stats.py). Each RealFuels CONFIG is a selectable variant of the
    part -- the ordered set of a part's CONFIGs *is* its upgrade path (see ENGINE-STATS.md).
    Keyed by part name only (unambiguous -- same lookup emit_engine_config_gates uses),
    so no config-name disambiguation is needed for display."""
    path = os.path.join(REPO, "manifest", "engine-stats.tsv")
    by_part = collections.defaultdict(list)
    if not os.path.exists(path):
        return by_part
    with open(path, encoding="utf-8", errors="replace") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        ix = {h: i for i, h in enumerate(hdr)}
        g = lambda c, k: (c[ix[k]].strip() if k in ix and ix[k] < len(c) else "")
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            part, config = g(c, "part"), g(c, "config")
            if not part or config == "(no RealFuels config path)":
                continue
            by_part[part].append({
                "config": config, "isBase": g(c, "is_base") in ("base", "single"),
                "specLevel": g(c, "specLevel"), "techTitle": g(c, "node_title"),
                "era": _fnum(g(c, "era_x")),
                "thrustKN": _fnum(g(c, "maxThrust_kN")), "minThrustKN": _fnum(g(c, "minThrust_kN")),
                "ispVac": _fnum(g(c, "ispVac")), "ispSL": _fnum(g(c, "ispSL")),
                "ispMode": g(c, "ispMode"), "propellants": g(c, "propellants"),
            })
    for rows in by_part.values():   # base config first (its own techRequired, not a CONFIG gate), then by era
        rows.sort(key=lambda r: (0 if r["isBase"] else 1, r["era"] if r["era"] is not None else 1e9))
    return by_part

def costcat(cat, disc, mods, mod):
    """Classify a part into a COST-category (drives part_cost_weight). Signal = its PartModules (mods,
    ';'-joined) + stock category + AXE discipline + source mod. Order matters: most specific first. The
    stock-category clauses (Science/Coupling/Electrical) are FALLBACKS for parts whose modules dodged the
    module check. Mirrors docs/SCIENCE.md 5; uncovered parts fall through to 'misc' (weight 1.0)."""
    has = lambda *xs: any(x in mods for x in xs)
    if mod == "ModularLaunchPads" or has("LaunchClamp", "ModuleGroundPart") or cat == "Ground": return "ground"  # launch infra + hand-placed ground kit, cheap
    if has("ModuleEnginesRF", "ModuleEngineConfigs", "ModuleEngines") and "RCS" not in cat: return "engine"
    if has("ModuleRCSFX", "ModuleRCS"):                                    return "rcs"
    if has("ModuleCommand") and (has("Habitat") or cat == "Pods"):        return "crewpod"
    if has("ModuleCommand"):                                              return "avionics"
    if has("ModuleScienceExperiment", "ModuleOrbitalScience") or disc == "OpticsPhotonics" or cat == "Science": return "science"
    if has("ModuleFuelTanks", "TankContentSwitcher") or (has("ProceduralPart") and cat == "FuelTank"): return "tank"
    if has("ModuleDeployableSolarPanel", "ModuleGenerator", "ModuleResourceConverter", "ModuleRTG") or cat == "Electrical": return "power"
    if has("ModuleRealAntenna", "ModuleDataTransmitter"):                 return "antenna"
    if has("ModuleWheelBase", "ModuleWheelMotor", "KFModuleWheel"):       return "gear"
    if has("ModuleParachute", "RealChuteModule", "ProceduralChute"):      return "chute"
    if has("WingProcedural", "WingManipulator", "ModuleLiftingSurface") or cat in ("Aero", "Wings"): return "aero"
    if has("ModuleDecouple", "ModuleAnchoredDecoupler", "ProceduralFairing", "ModuleDockingNode") or cat == "Coupling": return "separator"
    if cat in ("Structural", "Payload", "Thermal") or has("ProceduralPart"): return "structural"
    return "misc"

def load_part_categories():
    """name -> cost-category, from manifest/part-capabilities.tsv (columns: name, mod, category, disc, modules)."""
    path = os.path.join(REPO, "manifest", "part-capabilities.tsv")
    out = {}
    if not os.path.exists(path): return out
    with open(path, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        ix = {h: i for i, h in enumerate(hdr)}
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) < len(hdr): c += [""] * (len(hdr) - len(c))
            g = lambda k: c[ix[k]] if k in ix else ""
            out[g("name")] = costcat(g("category"), g("disc"), g("modules"), g("mod"))
    return out

def emit_part_cost(p2n, u2n, by, meta):
    """Emit GameData/RP-AXE/design/Tree/AxePartCost.cfg — part/upgrade funds unlock cost.
    entryCost(part)    = part_cost_base[tier] * part_cost_weight[costcat(part)]
    entryCost(upgrade) = part_cost_base[tier] * upgrade_cost_scalar   (light, no category)
    Tier = the AXE node the part/upgrade is placed on. FUNDS = texture, not a wall (docs/SCIENCE.md 5).
    No-op if the meta tables are absent (older nodes.yaml)."""
    base = meta.get("part_cost_base"); weight = meta.get("part_cost_weight")
    if not base or not weight:
        print("part cost: skipped (no part_cost_base / part_cost_weight in meta)"); return
    base = {int(k): v for k, v in base.items()}
    up_scalar = meta.get("upgrade_cost_scalar", 0.3)
    cats = load_part_categories()
    L = ["// GENERATED by tools/build_tree.py — DO NOT EDIT BY HAND",
         "// Part/upgrade funds unlock cost = part_cost_base[tier] * weight (see tree/nodes.yaml meta, docs/SCIENCE.md 5)."]
    catcount = collections.Counter()
    for part, node in sorted(p2n.items()):
        if node not in by: continue
        tier = by[node]["tier"]
        cc = cats.get(part, "misc"); catcount[cc] += 1
        ec = round(base.get(tier, 0) * weight.get(cc, 1.0))
        L.append(f"@PART[{part}]:FOR[RP-AXE] {{ %entryCost = {ec} }}")
    nup = 0
    for up, node in sorted(u2n.items()):
        if node not in by: continue
        ec = round(base.get(by[node]["tier"], 0) * up_scalar)
        L.append(f"@PARTUPGRADE[{up}]:FOR[RP-AXE] {{ %entryCost = {ec} }}"); nup += 1
    with open(os.path.join(OUTD, "AxePartCost.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"part cost: {sum(catcount.values())} parts + {nup} upgrades -> AxePartCost.cfg  "
          f"(by cat: {', '.join(f'{k}={catcount[k]}' for k in sorted(catcount, key=lambda k:-catcount[k]))})")

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
        np = len(n.get("parts") or []); nu = len(n.get("upgrades") or []); ng = len(n.get("grants") or [])
        badge = (f"{np}p" + (f"+{nu}u" if nu else "") + (f"+{ng}g" if ng else "")) if (np or nu or ng) else "—"
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
            "parts": parts, "upgrades": list(n.get("upgrades") or []), "grants": list(n.get("grants") or []),
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
    engine_stats = load_engine_stats()
    disciplines = {k: {"title": v["title"], "order": v["order"], "color": v["color"], "icon": v["icon"]}
                   for k, v in disc.items()}
    jnodes = []
    for n in nodes:
        parts = []
        for p in (n.get("parts") or []):
            pd = {"name": p, "mod": titles.get(p, ("", ""))[0], "title": titles.get(p, ("", ""))[1]}
            cfgs = engine_stats.get(p)
            if cfgs:
                thr = [c["thrustKN"] for c in cfgs if c["thrustKN"] is not None]
                # Isp is seconds in 'curve' mode but a 0-1 FRACTION of a tech-level ceiling in 'TL-frac'
                # mode (small RCS/cold-gas thrusters) -- never average the two across a part's configs.
                curve_isp = [c["ispVac"] for c in cfgs if c["ispVac"] is not None and c["ispMode"] == "curve"]
                tl_isp = [c["ispVac"] for c in cfgs if c["ispVac"] is not None and c["ispMode"] == "TL-frac"]
                isp_range = [min(curve_isp), max(curve_isp)] if curve_isp else \
                            ([min(tl_isp), max(tl_isp)] if tl_isp else None)
                props = []
                for c in cfgs:
                    if c["propellants"] and c["propellants"] not in props:
                        props.append(c["propellants"])
                pd["engine"] = {
                    "configs": cfgs,
                    "thrustRange": [min(thr), max(thr)] if thr else None,
                    "ispRange": isp_range, "ispIsFraction": bool(tl_isp and not curve_isp),
                    "propellants": props,
                }
            parts.append(pd)
        jnodes.append({
            "id": n["id"], "title": n["title"], "discipline": n["discipline"],
            "tier": n["tier"], "cost": n["cost"], "anyToUnlock": bool(n.get("anyToUnlock")),
            "flavor": (n.get("flavor") or "").strip(),
            "parts": parts, "upgrades": list(n.get("upgrades") or []), "grants": list(n.get("grants") or []),
            "pos": [n["_x"], n["_y"]],
        })
    jedges = [{"from": pid, "to": cid, "anyToUnlock": bool(by[cid].get("anyToUnlock")),
               "waypoints": [[MARGIN_X + t * TIERW, y] for t, y in chain]}
              for pid, cid, chain in routes]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                         cwd=REPO, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        commit = ""
    stamp = {                                        # freshness stamp shown in the viewer's corner — see renderer showStamp()
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "commit": commit,
        "nodes": len(jnodes),
        "parts": sum(len(n["parts"]) for n in jnodes),
        "grants": sum(len(n["grants"]) for n in jnodes),
    }
    payload = {"meta": stamp, "disciplines": disciplines, "nodes": jnodes, "edges": jedges}
    with open(os.path.join(protod, "tree-data.js"), "w", encoding="utf-8") as f:
        f.write("// GENERATED by tools/build_tree.py from tree/nodes.yaml — DO NOT EDIT BY HAND\n")
        f.write("window.TREE = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n")

def emit_standalone():
    """Re-bundle the single-file viewer (axe-tree-standalone.html) so it never lags tree-data.js.
    Runs the same bundler as `python tools/build_standalone.py`; best-effort so a bundler hiccup
    (e.g. renderer.js internals moved) can't fail the whole tree build."""
    try:
        sys.path.insert(0, ROOT)
        import build_standalone
        build_standalone.main()
    except SystemExit as e:
        print(f"WARN standalone bundle skipped: {e}")
    except Exception as e:
        print(f"WARN standalone bundle failed: {e}")

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

def emit_placement_patch(p2n, u2n, grant2n=None, parking="parking"):
    """@PART/@PARTUPGRADE TechRequired assignment. First PARK every part/upgrade on the parking node,
    then override the explicitly-placed ones onto their tree nodes. Same :FOR[RP-AXE] pass, applied in
    file order (wildcard first), so anything not homed lands in `parking` instead of piling onto `start`.
    grant2n binds the capability display-token upgrades (avionics tiers, DSN levels) to their granting
    node the same way — kept separate from u2n so emit_part_cost never assigns them a funds entry cost
    (they stay entryCost 0, defined in AxeGrantUpgrades.cfg)."""
    L = ["// GENERATED by tools/build_tree.py — DO NOT EDIT BY HAND",
         "// Line 1-2 park EVERY part/upgrade on the parking node; the lines below override the",
         "// explicitly-placed ones (same pass, applied in file order) onto their real tree nodes.",
         f"@PART[*]:FOR[RP-AXE] {{ %TechRequired = {parking} }}",
         f"@PARTUPGRADE[*]:FOR[RP-AXE] {{ %techRequired = {parking} }}"]
    for part, node in sorted(p2n.items()):
        L.append(f"@PART[{part}]:FOR[RP-AXE] {{ %TechRequired = {node} }}")
    for up, node in sorted(u2n.items()):
        L.append(f"@PARTUPGRADE[{up}]:FOR[RP-AXE] {{ %techRequired = {node} }}")
    for up, node in sorted((grant2n or {}).items()):
        L.append(f"@PARTUPGRADE[{up}]:FOR[RP-AXE] {{ %techRequired = {node} }}  // capability grant token")
    with open(os.path.join(OUTD, "AxePartPlacement.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

def emit_engine_config_gates(p2n):
    """AxeEngineConfigGates.cfg: remap each RealFuels engine CONFIG's techRequired onto its part's AXE
    node. The vendored seed/Tree/TREE-Engines.cfg walker sets every CONFIG's techRequired to an RP-1 tree
    node (absent here); RealFuels' CanConfig() (EngineConfigTechLevels.cs) gates config availability on
    exactly that field, so without this remap every engine config is permanently locked in career.

    Matched BY RP-1 NODE VALUE, not config name (the AxeExternalTechRemap idiom): dodges config-name
    escaping (RF config names carry slashes/asterisks/spaces), skips configs with no RP-1 gate, and never
    touches AXE-authored configs (they don't carry the RP-1 node). :FINAL runs after the walker
    (:BEFORE[RealismOverhaulEnginesPost]) AND after AxeExternalTechRemap's :LAST spot-fixes -- which it
    therefore leaves intact (their configs no longer carry the RP-1 node this matcher looks for).

    TWO layers, emitted (and thus applied) in this order:
      1. Per-part specifics from manifest/engine-stats.tsv: @PART[p]{ CONFIG:HAS[#techRequired[R]] -> p2n[p] }
         -- precise homing for curated engines, consistent with where AxePartPlacement puts their
         RFUpgrade_* tokens (place_parts routes engine upgrades to their part's node).
      2. Global catch-all per RP-1 node: @PART[*]{ CONFIG:HAS[#techRequired[R]] -> modal AXE node }.
         engine-stats is INCOMPLETE (misses curated engines like ROE-LR105 and all uncurated ones), but it
         covers ~123/126 of the RP-1 nodes the walker uses, so a per-node catch-all sweeps up every config
         the per-part pass left behind (they'd otherwise stay on a dead RP-1 node = permanently locked). The
         catch-all runs AFTER the specifics, so curated configs already moved to their part node are no
         longer on R and the catch-all can't touch them; only the residual (non-engine-stats parts) lands on
         the era-representative modal node. Modal is approximate (88/132 nodes span >1 AXE node) but
         era-appropriate -- refine per-part later by completing engine-stats."""
    stats = os.path.join(REPO, "manifest", "engine-stats.tsv")
    pairs = set()                                                      # (part, rp1node)
    r2a = collections.defaultdict(collections.Counter)                 # rp1node -> Counter(AXE node) for catch-all
    with open(stats, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t"); pi = hdr.index("part"); ti = hdr.index("techRequired")
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) <= max(pi, ti): continue
            part, tr = c[pi].strip(), c[ti].strip()
            if not (part and tr): continue
            pairs.add((part, tr))
            if part in p2n: r2a[tr][p2n[part]] += 1
    L = ["// GENERATED by tools/build_tree.py — DO NOT EDIT BY HAND",
         "// Remap every RealFuels engine CONFIG's techRequired -> an AXE node. The vendored",
         "// seed/Tree/TREE-Engines.cfg walker points each CONFIG at an RP-1 node; RealFuels' CanConfig()",
         "// (EngineConfigTechLevels.cs) gates config availability on CONFIG/techRequired, so THIS is what",
         "// unlocks engine configs in career. Matched by RP-1 NODE VALUE (AxeExternalTechRemap idiom):",
         "// dodges config-name escaping, skips ungated configs, never clobbers AXE-authored config gates.",
         "// :FINAL runs after the walker (:BEFORE[RealismOverhaulEnginesPost]) and after",
         "// AxeExternalTechRemap's :LAST spot-fixes (preserved -- their configs no longer carry the RP-1 node).",
         "// LAYER 1 -- per-part precise homing (curated engines, from manifest/engine-stats.tsv):"]
    missing = set()
    for part, rp1 in sorted(pairs):
        node = p2n.get(part)
        if node is None: node = "parking"; missing.add(part)
        L.append(f"@PART[{part}]:HAS[@MODULE[Module*EngineConfigs]]:FINAL "
                 f"{{ @MODULE[Module*EngineConfigs],* {{ @CONFIG:HAS[#techRequired[{rp1}]],* {{ @techRequired = {node} }} }} }}")
    L.append("// LAYER 2 -- global per-node catch-all for configs the per-part pass missed (engine-stats-absent")
    L.append("//            curated engines + uncurated parts); modal AXE node per RP-1 tech generation:")
    catchall = 0
    for rp1 in sorted(r2a):
        node = r2a[rp1].most_common(1)[0][0]
        L.append(f"@PART[*]:HAS[@MODULE[Module*EngineConfigs]]:FINAL "
                 f"{{ @MODULE[Module*EngineConfigs],* {{ @CONFIG:HAS[#techRequired[{rp1}]],* {{ @techRequired = {node} }} }} }}")
        catchall += 1
    with open(os.path.join(OUTD, "AxeEngineConfigGates.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    parts = sorted(set(p for p, _ in pairs))
    print(f"engine config gates: {len(pairs)} per-part remaps ({len(parts)} engine parts) + {catchall} "
          f"per-node catch-alls -> AxeEngineConfigGates.cfg" + (f"  (WARN {len(missing)} unplaced parts -> parking)" if missing else ""))

PROBE_SUBTREE = {"RN_US_Probes": "hire_JPL", "RN_Soviet_Probes": "hire_OKB"}

def route_probe_mods(by, p2n):
    """FALLBACK ONLY: route any OPTIONAL US/Soviet probe-pack part NOT already hand-placed in nodes.yaml
    into its charter GATE (hire_JPL / hire_OKB) so it never silently vanishes. Hand placement in the
    chronological charter chains (jpl_* / okb_*) is authoritative and WINS — this only catches new or
    unplaced pack parts. Skips DEPRECATED parts and absent gate nodes."""
    path = os.path.join(REPO, "manifest", "curated-parts.tsv")
    if not os.path.exists(path): return
    n = 0
    with open(path, encoding="utf-8") as f:
        next(f, None)
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < 3 or c[0] not in PROBE_SUBTREE: continue
            if c[1] in p2n: continue                        # already hand-placed -> respect it (no override)
            node = PROBE_SUBTREE[c[0]]
            if node not in by or "DEPRECATED" in c[2].upper(): continue
            p2n[c[1]] = node
            by[node].setdefault("parts", []).append(c[1]); n += 1
    print(f"probe subtree: {n} UNPLACED probe part(s) fell back to hire_JPL / hire_OKB"
          if n else "probe subtree: all RN probe parts hand-placed (no fallback needed)")

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

# Capability-grant families -> (heading, what game-side work the stub still needs). REFERENCE/provisional
# tree content is PLACED on purpose (docs/PLACEHOLDERS.md); this is the checklist to work through when
# actually implementing it, not a reason to drop it.
IMPL_FAMILIES = [
    (lambda g: g.startswith("RP0Level") and "TrackingStation" in g,
     "Deep Space Network / tracking-station levels",
     "SHIPPED — the 11-level ladder + DSN gain are re-provided by design/Settings/AxeTrackingStation.cfg "
     "(CustomBarnKit @TRACKING, consumed by RealAntennas) and the per-level tech gate by "
     "design/Tree/AxeFacilityGates.cfg (AXEBUILDINGTECHS), enforced in AXE.dll (AxeTrackingStationGate). "
     "The grant stubs below remain as the tree-node presentation tokens."),
    (lambda g: "avionics" in g.lower() or g.startswith("Science-Core"),   # avionics track = RP-1 "Science-Core"
     "Avionics capability tiers",
     "Needs the avionics-plugin tier gate to consume these (real emission instead of the provisional "
     "partUpgrade stub)."),
    (lambda g: True,
     "Other capability grants",
     "Provisional grant stub — emission / in-game effect still to be wired."),
]

def emit_facility_gates(nodes):
    """Emit GameData/RP-AXE/design/Tree/AxeFacilityGates.cfg — the tracking-station DSN tech gate.

    RP-1 gated each Deep Space Network tracking-station level on a comms tech node
    (`KCTBUILDINGTECHS { TrackingStation { level = node } }`, consumed by RP0.dll). AXE re-derives
    that mapping from the `RP0Level{N}TrackingStation` grants already scattered on the tel_* DSN
    nodes: facility upgrade-step = N-1 (RP0Level2 unlocks step 1, i.e. display "Level 2"), gate =
    the node carrying the grant. Emitted under our own `AXEBUILDINGTECHS` node — read + enforced by
    AXE.dll's `AxeTrackingStationGate` Harmony patch (RP0.dll/KCT are gone). Pairs with
    design/Settings/AxeTrackingStation.cfg, which supplies the 11-level ladder + DSN gain via
    CustomBarnKit.
    """
    pat = re.compile(r"^RP0Level(\d+)TrackingStation$")
    gates = {}   # facility upgrade-step (1-based) -> gating node id
    for n in nodes:
        for g in (n.get("grants") or []):
            m = pat.match(g)
            if m:
                gates[int(m.group(1)) - 1] = n["id"]
    L = ["// GENERATED by tools/build_tree.py — do not hand-edit.",
         "// Tracking-station DSN tech gate: which tech node unlocks each facility level.",
         "// Derived from the RP0Level*TrackingStation grants on the tel_* nodes. Read + enforced by",
         "// AXE.dll (AxeTrackingStationGate); the 11-level ladder + DSN gain live in",
         "// design/Settings/AxeTrackingStation.cfg (CustomBarnKit @TRACKING). RP-1 parity: its",
         "// KCTBUILDINGTECHS{TrackingStation} was consumed by the now-removed RP0.dll.",
         "AXEBUILDINGTECHS", "{", "\tTrackingStation", "\t{",
         "\t\t// facility upgrade-step (1-based) = required tech node"]
    for lvl in sorted(gates):
        L.append(f"\t\t{lvl} = {gates[lvl]}")
    L += ["\t}", "}", ""]
    with open(os.path.join(OUTD, "AxeFacilityGates.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"facility gates: {len(gates)} tracking-station levels -> AxeFacilityGates.cfg")

def emit_impl_backlog(nodes):
    """Generate docs/IMPL-TODO.md: tree content that is placed + researchable now but whose in-game EFFECT
    still needs game-side wiring. Source of truth = every `grants:` capability stub + any node carrying an
    explicit `impl_todo:` note. Fully auto-derived, so it can never drift from the actual tree."""
    fams = [(heading, desc, []) for _, heading, desc in IMPL_FAMILIES]
    for n in nodes:
        for g in (n.get("grants") or []):
            for i, (pred, _, _) in enumerate(IMPL_FAMILIES):
                if pred(g): fams[i][2].append((g, n)); break
    todo = [n for n in nodes if n.get("impl_todo")]
    ngrant = sum(len(rows) for _, _, rows in fams)
    gnodes = {n["id"] for _, _, rows in fams for _, n in rows}
    L = []; A = L.append
    A("# Implementation Backlog")
    A("")
    A("> **Generated by `tools/build_tree.py` — do not hand-edit.** Regenerated on every build.")
    A("")
    A("Tree content that is PLACED and researchable now, but whose in-game **effect** still needs")
    A("game-side wiring. These are `grants:` capability stubs (emitted provisionally as `partUpgrade`s —")
    A("see [PLACEHOLDERS.md](PLACEHOLDERS.md)) plus any node carrying an explicit `impl_todo:` note.")
    A("REFERENCE items live in the tree on purpose; **this is the list to work through when building")
    A("them**, not a reason to drop them.")
    A("")
    A(f"**{ngrant} provisional grants across {len(gnodes)} nodes; {len(todo)} nodes with an explicit "
      f"impl note.**")
    for heading, desc, rows in fams:
        if not rows: continue
        A(""); A(f"## {heading} ({len(rows)})"); A(""); A(f"_{desc}_"); A("")
        A("| grant | node | tier | title |"); A("|---|---|---|---|")
        for g, n in sorted(rows, key=lambda gn: (gn[1]["tier"], gn[0])):
            A(f"| `{g}` | `{n['id']}` | T{n['tier']} | {n['title']} |")
    if todo:
        A(""); A(f"## Nodes flagged `impl_todo` ({len(todo)})"); A("")
        A("| node | tier | note |"); A("|---|---|---|")
        for n in sorted(todo, key=lambda n: n["tier"]):
            A(f"| `{n['id']}` | T{n['tier']} | {n['impl_todo']} |")
    A("")
    with open(os.path.join(REPO, "docs", "IMPL-TODO.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"implementation backlog: {ngrant} provisional grants + {len(todo)} impl notes "
          f"-> docs/IMPL-TODO.md")

# DSN tracking-station per-level data (levels 1..11 -> index 0..10). Mirrors design/Settings/
# AxeTrackingStation.cfg @TRACKING (@DSNRange / @trackedObjectLimit). Used for the DSN display-token text.
DSN_TRACK = [0, 1, 2, 3, 4, 5, 6, 8, 10, -1, -1]

def _num(x):
    """Format a float without a trailing .0 (4.0 -> '4', 0.15 -> '0.15')."""
    if x is None: return "?"
    return str(int(x)) if float(x).is_integer() else f"{x:g}"

def _parse_avionics_tiers():
    """Parse the TIER ladder out of AxeAvionicsCore.cfg -> {rp1name -> stats}, keyed by the RP-1 tier
    name in each TIER's `// RP-1: <name>` breadcrumb (plus 'start' for the unconditional floor). Single
    source of truth for the avionics display-token stat deltas (mirrors tools/avionics_compare.py's parse)."""
    path = os.path.join(OUTD, "AxeAvionicsCore.cfg")
    if not os.path.exists(path): return {}, []
    txt = open(path, encoding="utf-8").read()
    tiers, order = {}, []
    def f(body, key):
        m = re.search(rf'\b{key}\s*=\s*(-?[\d.]+)', body); return float(m.group(1)) if m else None
    def b(body, key):
        m = re.search(rf'\b{key}\s*=\s*(true|false)', body, re.I); return bool(m) and m.group(1).lower() == 'true'
    for m in re.finditer(r'TIER\s*\{(.*?)\}', txt, re.DOTALL):
        body = m.group(1)
        tech = re.search(r'\btech\s*=\s*(\S+)', body)
        rp1 = re.search(r'//\s*RP-1:\s*(\w+)', body)
        name = rp1.group(1) if rp1 else (tech.group(1) if tech and tech.group(1) == 'start' else None)
        if not name: continue
        tiers[name] = {"massFactor": f(body, "massFactor"), "powerFactor": f(body, "powerFactor"),
                       "scMassFactor": f(body, "scMassFactor"), "scPowerFactor": f(body, "scPowerFactor"),
                       "sci": b(body, "hasScienceContainer"), "axial": b(body, "scAllowAxial")}
        order.append(name)
    return tiers, order

def _avionics_main_desc(rp1, node_title, tiers, order):
    """Player-facing token description for a main (Guided/Unguided) avionics tier — AXE language, real
    per-tier stat deltas vs. the starting core, like RP-1's own tokens. None if the tier is unknown."""
    t = tiers.get(rp1)
    if not t or "start" not in tiers: return None
    md = round((1 - t["massFactor"] / tiers["start"]["massFactor"]) * 100)
    pd = round((1 - t["powerFactor"] / tiers["start"]["powerFactor"]) * 100)
    sci_flip = next((n for n in order if tiers[n]["sci"]), None)
    axial_flip = next((n for n in order if tiers[n]["axial"]), None)
    parts = [f"<b>Avionics Core: {node_title}</b>"]
    if md > 0 or pd > 0:
        parts.append(f"Guided avionics about {md}% lighter and {pd}% lower power than the starting core.")
    parts.append(f"Unguided avionics: {_num(t['scMassFactor'])} kg fixed, {_num(t['scPowerFactor'])} W.")
    if rp1 == sci_flip: parts.append("Adds onboard science storage.")
    if rp1 == axial_flip: parts.append("Adds axial-thrust control for unguided stages.")
    parts.append("<color=#7fd3ff>Applied automatically when this node is researched.</color>")
    return " ".join(parts)

def _avionics_shd_desc(rp1, node_title):
    """Token description for a Radiation-Shielded (deep-space) avionics tier."""
    lead = ("Enables the Shielded avionics toggle" if rp1 == "basicAvionics"
            else "Advances the shielded avionics ladder")
    return (f"<b>{node_title}</b> {lead} — a dedicated deep-space tier "
            f"(its own mass and cost curve, plus deep hibernation) for operating through radiation belts "
            f"and on interplanetary cruise. <color=#7fd3ff>Applied automatically when this node is researched.</color>")

def _dsn_desc(level):
    """(title, description) for a Deep Space Network tracking-station level token."""
    idx = level - 1
    track = DSN_TRACK[idx] if 0 <= idx < len(DSN_TRACK) else None
    clause = ("" if track in (None, 0)
              else " and removes the tracked-craft limit" if track < 0
              else f" and up to {track} simultaneously-tracked craft")
    title = f"Deep Space Network — Level {level}"
    desc = (f"<b>Deep Space Network — Level {level} of 11</b> Upgrades the tracking station to level "
            f"{level}: greater ground-station downlink range for deep-space communications{clause}. "
            f"<color=#7fd3ff>Applied automatically when this node is researched.</color>")
    return title, desc

def emit_grant_upgrades(nodes):
    """Emit design/Tree/AxeGrantUpgrades.cfg — the VISIBLE R&D tokens for capability grants (avionics
    tiers + DSN levels). Avionics tokens (Science-Core-*/Deep-Space-*) already exist in the seed, so they
    are retitled/redescribed in AXE language (the seed's own RP-1-flavour text + node is wrong for AXE);
    DSN tokens (RP0Level*TrackingStation) have no seed PARTUPGRADE, so they are created fresh. All carry
    entryCost/cost 0 and no stat MODULE — the tier effect is applied by AXE.dll, and AXE.dll's
    AxeGrantUpgradeUnlock auto-marks them unlocked on research (no buy step). techRequired -> node is set
    in AxePartPlacement.cfg (via grant2n). Returns the marker list of token names."""
    tiers, order = _parse_avionics_tiers()
    av, dsn, marker = [], [], []
    for n in nodes:
        nt = n.get("title", n["id"])
        for g in (n.get("grants") or []):
            if g.startswith("Science-Core-"):
                d = _avionics_main_desc(g[len("Science-Core-"):], nt, tiers, order)
                if d is None: continue
                av.append((g, "Avionics Core Upgrade", d)); marker.append(g)
            elif g.startswith("Deep-Space-"):
                d = _avionics_shd_desc(g[len("Deep-Space-"):], nt)
                av.append((g, "Shielded Avionics Upgrade", d)); marker.append(g)
            elif g.startswith("RP0Level") and g.endswith("TrackingStation"):
                ml = re.search(r'RP0Level(\d+)TrackingStation', g)
                if not ml: continue
                title, d = _dsn_desc(int(ml.group(1)))
                dsn.append((g, title, d)); marker.append(g)
            # else: unrecognised grant family -> leave untouched (no token)
    L = ["// GENERATED by tools/build_tree.py from tree/nodes.yaml -- DO NOT EDIT BY HAND",
         "// Visible R&D tokens for capability grants (avionics tiers + DSN tracking-station levels).",
         "// They carry NO stat MODULE: the tier effect is applied by AXE.dll (ModuleAxeAvionics reads the",
         "// researched node; tracking-station level via AxeTrackingStationGate). entryCost/cost = 0 and",
         "// AXE.dll (AxeGrantUpgradeUnlock) auto-marks them unlocked on research (no buy step) -- the same",
         "// shape as RP-1's own avionics PARTUPGRADE display tokens. techRequired is assigned in",
         "// AxePartPlacement.cfg (parked on `parking`, then overridden onto the granting node).", ""]
    L.append("// --- avionics tiers: retitle/redescribe the seed's Science-Core-*/Deep-Space-* tokens (AXE language) ---")
    for name, title, desc in av:
        L += [f"@PARTUPGRADE[{name}]:FOR[RP-AXE]", "{",
              f"\t%title = {title}", "\t%basicInfo = Avionics Core capability tier.",
              f"\t%description = {desc}", "}"]
    L.append("")
    L.append("// --- DSN / tracking-station levels: created fresh (no seed PARTUPGRADE exists for these) ---")
    for name, title, desc in dsn:
        L += ["PARTUPGRADE", "{", f"\tname = {name}", "\tpartIcon = RelayAntenna50",  # RA's own comms-upgrade icon
              "\tentryCost = 0", "\tcost = 0", "\tmanufacturer = Deep Space Network", f"\ttitle = {title}",
              "\tbasicInfo = Tracking-station facility level.", f"\tdescription = {desc}", "}"]
    L.append("")
    L.append("// --- marker list consumed by AXE.dll AxeGrantUpgradeUnlock (auto-unlock on research) ---")
    L += ["AXE_GRANT_UPGRADES", "{"] + [f"\tupgrade = {g}" for g in marker] + ["}"]
    with open(os.path.join(OUTD, "AxeGrantUpgrades.cfg"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"grant tokens: {len(av)} avionics + {len(dsn)} DSN -> AxeGrantUpgrades.cfg")
    return marker

def check_tech_gates(nodes):
    """Build gate: every RP-AXE-*authored* raw tech gate (design/*.cfg + Source/*.cs) must
    resolve to a real tree node. Otherwise it fails CLOSED and SILENT in-game — renaming or
    removing a node leaves dangling techRequired / Kerbalism `tech=` / GetTechnologyState
    references (see tools/check_tech_refs.py). Non-fatal by default (matches validate_design);
    set AXE_TREE_STRICT=1 to make a dangling ref fail the build (CI / pre-commit gate)."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    try:
        import check_tech_refs as ctr
    except Exception as e:
        print(f"tech-ref gate: skipped ({e})"); return []
    valid = {n["id"] for n in nodes} | ctr.INTENTIONAL
    design = os.path.join(REPO, "GameData", "RP-AXE", "design")
    src = os.path.join(REPO, "Source")
    dangling = ctr.check_design(valid, design, src if os.path.isdir(src) else None)
    if not dangling:
        print("tech-ref gate: clean -- every authored tech gate resolves to a real node"); return []
    total = sum(len(r) for _, r in dangling)
    print(f"tech-ref gate: {total} DANGLING authored ref(s) across {len(dangling)} node(s) "
          f"-- these fail closed + silent in-game; fix design/ overlays:")
    for node, refs in dangling:
        fields = sorted({r[0] for r in refs})
        files = sorted({ctr.rel(r[1]) for r in refs})[:4]
        print(f"   ! {node}  [{', '.join(fields)}]  {', '.join(files)}")
    if os.environ.get("AXE_TREE_STRICT"):
        die(f"AXE_TREE_STRICT set: {total} dangling tech-gate reference(s) — see above")
    return dangling

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
    emit_treemeta(disc, nodes)           # AxeTreeMeta.cfg: id->{discipline,tier,cost} for the render plugin
    emit_render(disc, meta, nodes, by)
    emit_html(disc, nodes, by, routes)
    emit_prototype_data(disc, nodes, by, routes)   # tree/render/prototype/tree-data.js (Canvas viewer)
    emit_standalone()                              # re-bundle axe-tree-standalone.html so it never lags tree-data.js
    grant2n = {g: n["id"] for n in nodes for g in (n.get("grants") or [])}
    emit_placement_patch(p2n, u2n, grant2n)
    print(f"placement: {len(p2n)} parts + {len(u2n)} upgrades + {len(grant2n)} grant tokens homed onto "
          f"{len(set(p2n.values())|set(u2n.values())|set(grant2n.values()))} nodes -> AxePartPlacement.cfg")
    emit_engine_config_gates(p2n)        # AxeEngineConfigGates.cfg: RealFuels CONFIG techRequired -> AXE node
    emit_part_cost(p2n, u2n, by, meta)   # AxePartCost.cfg: funds unlock cost = base[tier] * weight[costcat]
    emit_grant_upgrades(nodes)           # AxeGrantUpgrades.cfg: visible R&D tokens for avionics tiers + DSN levels
    emit_facility_gates(nodes)           # AxeFacilityGates.cfg: tracking-station DSN tech gate (AXEBUILDINGTECHS)
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
    print("-> GameData/RP-AXE/design/Tree/AxeTechTree.cfg (+ AxeTreeMeta.cfg), tree/render/axe-tree.svg|png|html")
    check_probe_requirements(nodes)
    emit_impl_backlog(nodes)             # docs/IMPL-TODO.md: provisional grants + impl_todo -> checklist
    check_tech_gates(nodes)              # gate: authored tech-refs (design/*.cfg + Source) must resolve (fail closed+silent otherwise)

if __name__ == "__main__": main()
