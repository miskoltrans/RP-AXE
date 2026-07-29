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
        if r not in ("start", "parking", "experimental", "gs_soundingStands", "us2_serviceSandbox") and not r.startswith("hire_"):
            warns.append(f"extra root (no parents besides start): {r}")
    # MEMBERSHIP: a placed part must be in manifest/curated-parts.tsv. The manifest is the single
    # source of truth for what AXE ships (docs/PARTLIST.md); a part name that reaches nodes.yaml by
    # any other route -- read off an RP-1 config, copied from a partlist extraction -- may belong to
    # a mod that is not installed, in which case the node silently grants nothing. That is exactly
    # how five DMagic Orbital Science parts (dmUS2*) left three nodes empty and two thinned until
    # 2026-07-29. Placement was validated in every other respect; nobody asked if the part was ours.
    # us2_serviceSandbox is the documented exception: it exists to hold uncurated parts on trial.
    curated = set(load_part_titles())
    if curated:
        for n in nodes:
            if n["id"] == "us2_serviceSandbox":
                continue
            for p in n.get("parts") or []:
                if p not in curated:
                    warns.append(f"placed part not in curated-parts.tsv: {p} on {n['id']}")
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
    stock-category clauses (Science/Coupling/Electrical/Ground) are FALLBACKS for parts whose modules
    dodged the module check, and each one belongs to the LAST rule that could want it — a category
    clause placed early silently outranks every module rule below it (see 'ground' vs 'gear').
    Mirrors docs/SCIENCE.md 5; uncovered parts fall through to 'misc' (weight 1.0).

    A part with no row in manifest/part-capabilities.tsv arrives here as four empty strings and
    classifies as 'misc' with nothing to flag it — run tools/backfill_capabilities.py after placing
    parts RP-1 never had."""
    has = lambda *xs: any(x in mods for x in xs)
    # 'ground' is LAUNCH INFRASTRUCTURE ONLY (weight 0.2). It must NOT claim `cat == "Ground"`: that
    # is KSP's part category for landing legs, gear, wheels and tracks, so the old clause swallowed
    # all 54 of them at the launch-clamp weight and left `gear` (2.0) matching nothing at all.
    if mod == "ModularLaunchPads" or has("LaunchClamp", "ModuleGroundPart"): return "ground"
    if has("ModuleEnginesRF", "ModuleEngineConfigs", "ModuleEngines") and "RCS" not in cat: return "engine"
    if has("ModuleRCSFX", "ModuleRCS"):                                    return "rcs"
    if has("ModuleCommand") and (has("Habitat") or cat == "Pods"):        return "crewpod"
    if has("ModuleCommand"):                                              return "avionics"
    if has("ModuleScienceExperiment", "ModuleOrbitalScience") or disc == "OpticsPhotonics" or cat == "Science":
        # ...but crew VOLUME is not an instrument. Cabins, hab modules, greenhouses and centrifuges all
        # ship ModuleScienceExperiment as a station-module convention, which used to price 41 of them at
        # the instrument weight (2.5) — mk2CrewCabin included. A real lab keeps it: ModuleScienceLab is
        # the thing being paid for there. Scoped INSIDE this clause on purpose: `Habitat` is added to any
        # pressurisable volume, crew capacity 0 included, so as a standalone rule it also swallows the
        # SSPX adapters and hubs, which are connectors and priced as such.
        if has("Habitat", "Comfort", "ModuleExperienceManagement") and not has("ModuleScienceLab"): return "crewpod"
        return "science"
    if has("ModuleFuelTanks", "TankContentSwitcher") or (has("ProceduralPart") and cat == "FuelTank"): return "tank"
    if has("ModuleDeployableSolarPanel", "ModuleGenerator", "ModuleResourceConverter", "ModuleRTG",
           "ModuleSystemHeatFissionReactor", "FissionReactor") or cat == "Electrical": return "power"
    if has("ModuleRealAntenna", "ModuleDataTransmitter"):                 return "antenna"
    # KSPWheelBase is the RO-wide wheel/leg module (RO replaces the stock wheel modules); cat ==
    # "Ground" is the fallback for legs whose only other signal is an animation (vela_landing_leg_*).
    if has("KSPWheelBase", "ModuleWheelBase", "ModuleWheelMotor", "KFModuleWheel",
           "ModuleAdjustableLeg") or cat == "Ground":                     return "gear"
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

# Capability ladders AXE GRANTS on research instead of selling. Two halves, both required:
#   entryCost 0 here, and the token listed in AXE_GRANT_UPGRADES (emit_grant_upgrades) so AXE.dll's
#   AxeGrantUpgradeUnlock marks it unlocked the moment its node is researched.
# Why: AXE already grants the avionics tier tokens (Science-Core-*/Deep-Space-*) this way, because
# ModuleAxeAvionics replaced RP-1's ModuleProceduralAvionics and with it RP-1's per-tier funds purchase
# (EntryCostManager.PurchaseConfig). RP-1 SELLS both ladders and is consistent; AXE granting avionics but
# billing data storage taught the player two different rules for the same kind of thing. Unlike
# RFUpgrade_* (zeroed because buying them unlocked nothing) these DO carry a stat -- the module's
# UPGRADE block -- and SetUnlocked applies it for free, which is the intent.
GRANTED_UPGRADE_PREFIXES = (
    "HDD-Upgrade-",
)

def emit_part_cost(p2n, u2n, by, meta):
    """Emit GameData/RP-AXE/design/Tree/AxePartCost.cfg — part/upgrade funds unlock cost.
    entryCost(part)    = part_cost_base[tier] * part_cost_weight[costcat(part)]
    entryCost(upgrade) = part_cost_base[tier] * upgrade_cost_scalar   (light, no category)
    Tier = the AXE node the part/upgrade is placed on. FUNDS = texture, not a wall (docs/SCIENCE.md 5).
    No-op if the meta tables are absent (older nodes.yaml).

    RFUpgrade_* is the ONE exception, forced to 0. Those PARTUPGRADEs are RP-1's tree ICONS for engine
    configs, nothing more: RealFuels never consults PartUpgradeManager when deciding whether a config is
    available (UnlockedConfig -> EntryCostDatabase.IsUnlocked), and OnPartUpgradePurchased marks
    'RFUpgrade-<cfg>' unlocked rather than '<cfg>', so buying one charged funds and unlocked nothing.
    RP-1 defines them at entryCost 0 on purpose -- EntryCostDatabase.UpdateEntryCosts() auto-unlocks any
    upgrade under 1.1 whose tech is researched, so the icon never presents as a purchase. Engine variants
    are priced where RealFuels actually charges for them: ENTRYCOSTMODS, see emit_entry_cost_mods()."""
    base = meta.get("part_cost_base"); weight = meta.get("part_cost_weight")
    if not base or not weight:
        print("part cost: skipped (no part_cost_base / part_cost_weight in meta)"); return
    base = {int(k): v for k, v in base.items()}
    up_scalar = meta.get("upgrade_cost_scalar", 0.3)
    cats = load_part_categories()
    L = ["// GENERATED by tools/build_tree.py — DO NOT EDIT BY HAND",
         "// Part/upgrade funds unlock cost = part_cost_base[tier] * weight (see tree/nodes.yaml meta, docs/SCIENCE.md 5).",
         "// RFUpgrade_* forced to 0: they are tree icons, not the engine-config purchase (that is",
         "// AxeEntryCostMods.cfg). 0 lets RealFuels auto-unlock them once their tech is researched, as in RP-1.",
         "@PARTUPGRADE[RFUpgrade_*]:FOR[RP-AXE] { %entryCost = 0 }",
         "// Granted capability ladders (see GRANTED_UPGRADE_PREFIXES): free on research, same as the avionics",
         "// tier tokens. AXE.dll's AxeGrantUpgradeUnlock marks them unlocked; entryCost 0 so R&D never shows",
         "// a price that is never charged. RP-1 sells these; AXE grants them, to match its own avionics."]
    catcount = collections.Counter()
    for part, node in sorted(p2n.items()):
        if node not in by: continue
        tier = by[node]["tier"]
        cc = cats.get(part, "misc"); catcount[cc] += 1
        ec = round(base.get(tier, 0) * weight.get(cc, 1.0))
        L.append(f"@PART[{part}]:FOR[RP-AXE] {{ %entryCost = {ec} }}")
    nup, ngranted = 0, 0
    for up, node in sorted(u2n.items()):
        if node not in by or up.startswith("RFUpgrade_"): continue      # engine icons: zeroed above
        if up.startswith(GRANTED_UPGRADE_PREFIXES):                     # granted, not sold
            L.append(f"@PARTUPGRADE[{up}]:FOR[RP-AXE] {{ %entryCost = 0 }}"); ngranted += 1
            continue
        ec = round(base.get(by[node]["tier"], 0) * up_scalar)
        L.append(f"@PARTUPGRADE[{up}]:FOR[RP-AXE] {{ %entryCost = {ec} }}"); nup += 1
    with open(os.path.join(OUTD, "AxePartCost.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"part cost: {sum(catcount.values())} parts + {nup} upgrades + {ngranted} granted(0) -> AxePartCost.cfg  "
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

CFG_NAME_SAFE = re.compile(r"^[A-Za-z0-9_.+/-]+$")   # MM-safe inside @CONFIG[...]: no space/comma/pipe/wildcard
CFG_NAME_REAL = re.compile(r"^[^(,=]+$")             # a real RF config, not an engine-stats placeholder
                                                     # ("(single config)", "(no RealFuels config path)")

def ecm_name(s):
    """RealFuels' Utilities.SanitizeName: '.' and '_' -> '-'. EntryCostDatabase stores ENTRYCOSTMODS keys
    VERBATIM but looks them up sanitized, so a key that isn't already sanitized is simply never found
    (RP-1's EntryCostModifiers.cfg opens with the same note)."""
    return s.replace(".", "-").replace("_", "-")

def engine_config_ladders(p2n, u2n, by):
    """Where each RealFuels engine CONFIG lands in the AXE tree -- the single source of truth shared by the
    tech gates (AxeEngineConfigGates.cfg) and the funds prices (AxeEntryCostMods.cfg).

    A part's CONFIGs are its upgrade path (ENGINE-STATS.md); tree/nodes.yaml homes each one's
    `RFUpgrade_<config>` token on the breakthrough node that earns it, and the CONFIG follows its token.
    Two guards keep every engine flyable the moment its part unlocks:
      - a `base` CONFIG never leaves the part's node (it is the part's default -- moving it would unlock an
        engine with no available config), and
      - if a part's every CONFIG would otherwise leave, its first one is pinned to the part's node.
    Config names that aren't MM-safe inside `@CONFIG[...]` stay on the part's node too (the gate emitter
    cannot address them individually).

    Returns (ladders, pinned, missing) where ladders is part -> list of rungs ordered by tree progression
    (node tier, then era), each rung a dict {config, rp1, base, node, moved}."""
    rows = collections.defaultdict(list)
    with open(os.path.join(REPO, "manifest", "engine-stats.tsv"), encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        pi, ci, ti, bi, ei = (hdr.index(k) for k in ("part", "config", "techRequired", "is_base", "era_x"))
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) <= max(pi, ci, ti, bi, ei): continue
            part, cfg, tr, isb = c[pi].strip(), c[ci].strip(), c[ti].strip(), c[bi].strip()
            if not (part and cfg): continue
            try: era = float(c[ei].strip())
            except ValueError: era = 0.0
            rows[part].append({"config": cfg, "rp1": tr, "base": isb == "base", "era": era})
    ladders, pinned, missing = {}, [], set()
    for part in sorted(rows):
        pnode = p2n.get(part)
        if pnode is None: pnode = "parking"; missing.add(part)
        for r in rows[part]:
            unode = u2n.get("RFUpgrade_" + r["config"])
            # A config with NO RP-1 techRequired can still be re-homed -- it just needs a different
            # patch form, because the usual matcher keys off the RP-1 value it does not have. Without
            # this, every AXE- or mod-authored config (Raptor, the NTR working fluids, the NK-12 marks:
            # 18 of them) is permanently stuck on its part's node no matter where its token is placed.
            r["ungated"] = not r["rp1"]
            r["moved"] = bool(not r["base"] and unode and unode != pnode and unode in by
                              and CFG_NAME_SAFE.match(r["config"]))
            r["node"] = unode if r["moved"] else pnode
        if rows[part] and all(r["moved"] for r in rows[part]):     # guard: leave one config on the part
            keep = rows[part][0]
            keep["moved"] = False; keep["node"] = pnode
            pinned.append((part, keep["config"]))
        # base first (it is the part's default -- the rung you get with the part), then tree progression
        ladders[part] = sorted(rows[part], key=lambda r: (not r["base"],
                                                          by[r["node"]]["tier"] if r["node"] in by else 99,
                                                          r["era"], r["config"]))
    return ladders, pinned, missing

def emit_entry_cost_mods(ladders, by, meta):
    """AxeEntryCostMods.cfg: ENTRYCOSTMODS -- what an engine variant costs in funds.

    RealFuels gates a CONFIG on TWO things: CanConfig() (techRequired, see emit_engine_config_gates) and
    UnlockedConfig() -> EntryCostDatabase.IsUnlocked(). The latter is priced from ENTRYCOSTMODS nodes, and
    a config with NO holder costs 0 -- at which point EngineConfigGUI silently auto-purchases it the moment
    the row renders (`if (num <= 0.0 && !flag2 && flag) PurchaseConfig(...)`). AXE shipped zero
    ENTRYCOSTMODS, so until now every tech-available variant was free and instantly owned.

    RP-1's graph (Tree/ECM-Engines.cfg) is `config = cost, child...`, scored recursively as
    cost + sum(GetCost(child)) with an ALREADY-UNLOCKED name contributing 0. We reproduce the shape, not
    the numbers: each non-base config chains to the previous rung of its own part's ladder, so the first
    variant you buy in a family carries the lineage and each sibling after it costs only its own step --
    RP-1's self-discounting property, keyed to AXE's tier table instead of RP-1's hand-tuned figures.

    PRICED SET == TECH-GATED SET. A config is charged for exactly when the ladder moved it past its part's
    own node -- you pay for a variant when a breakthrough unlocked it. Anything reachable the moment you
    buy the part (its base config, propellant variants like the NTRs' Ammonia/Methane, the RCS Helium, and
    the names too MM-hostile to gate individually) is included in the part's entryCost and stays free;
    pricing those would be a funds-only toll with no tech story behind it, which is not what
    'funds are texture, not a wall' means. Flip the `not r["moved"]` test below to charge for them.

    Deliberately CONFIGS ONLY -- no PART or shared-technology entries:
      - Base configs get no entry, so they cost 0 and come free with the part (RP-1 instead lists the part
        in ECM-Parts.cfg pointing at its base config, which is what unlocks the base config on purchase;
        omitting both gets the same result without a second pricing system).
      - Leaving parts out keeps AxePartCost.cfg the sole owner of part entryCost. An ECM holder for a part
        would OVERRIDE it -- EntryCostDatabase.UpdateEntryCost(AvailablePart) calls ap.SetEntryCost(holder).
    Engines absent from engine-stats.tsv get no entry either, so their variants stay free (same coverage
    gap as the gate emitter's layer-2 catch-all).

    ECM keys are GLOBAL, but 134 config names are shared by more than one part (`ASCENT` rides six), so a
    naive per-part emit writes the same key repeatedly and `holders[name] = ...` keeps whichever part
    happened to sort last. Each name is therefore priced ONCE, from its earliest home (lowest node tier) --
    it unlocks globally when bought, so the earliest place you can reach it is the honest price. A name
    that is any part's `base` is never priced at all. Chains are only kept when the child sorts strictly
    earlier than its parent in that same global order, which makes the graph acyclic by construction --
    without that, two parts laddering the same pair in opposite orders would produce X->Y and Y->X."""
    base = meta.get("part_cost_base")
    if not base:
        print("entry cost mods: skipped (no part_cost_base in meta)"); return
    base = {int(k): v for k, v in base.items()}
    scalar = meta.get("engine_config_cost_scalar", meta.get("upgrade_cost_scalar", 0.3))

    def rank(r, part):                                   # strict total order: tree progression, then name
        return (by[r["node"]]["tier"] if r["node"] in by else 99, r["era"], ecm_name(r["config"]), part)
    home, free = {}, set()                               # key -> (rank, part, rung) | keys that are some base
    for part in sorted(ladders):
        for r in ladders[part]:
            key = ecm_name(r["config"])
            if not CFG_NAME_REAL.match(r["config"]):     # engine-stats placeholders, not real configs
                continue
            if r["base"] or not r["moved"] or r["node"] not in by:
                free.add(key); continue                  # arrives with the part => no step to charge for
            cand = (rank(r, part), part, r)
            if key not in home or cand[0] < home[key][0]: home[key] = cand
    entries, dropped = [], 0
    for key, (rk, part, r) in home.items():
        if key in free: continue                         # someone's default => free, never priced
        prev = None                                      # previous rung of the ladder we priced it from
        for q in ladders[part]:
            if q is r: break
            k2 = ecm_name(q["config"])
            if not CFG_NAME_REAL.match(q["config"]): continue
            if k2 in free or (k2 in home and home[k2][0] < rk): prev = k2
        if prev is not None and prev not in free and home[prev][0] >= rk: prev = None; dropped += 1
        entries.append((rk, key, round(base.get(by[r["node"]]["tier"], 0) * scalar), prev))
    L = ["// GENERATED by tools/build_tree.py — DO NOT EDIT BY HAND",
         "// ENTRYCOSTMODS = RealFuels' funds price for unlocking an engine CONFIG, charged in the VAB engine-",
         "// configs GUI (EntryCostDatabase.GetCost: own cost + sum of children, an unlocked name counting 0).",
         "// Each non-base config chains to the previous rung of its own part's ladder, so buying the family's",
         "// first variant carries the lineage and later siblings cost only their own step. Base configs are",
         "// omitted on purpose => cost 0 => free with the part. No PART entries: an ECM holder for a part would",
         "// override AxePartCost.cfg's entryCost. Keys are pre-sanitized ('.'/'_' -> '-') or lookup misses.",
         "// Price = part_cost_base[tier of the config's node] * engine_config_cost_scalar (tree/nodes.yaml meta).",
         "// One entry per config NAME (keys are global; 134 names are shared across parts), priced from its",
         "// earliest home; chains point strictly backwards in that order, so the graph cannot cycle.",
         "ENTRYCOSTMODS", "{"]
    for _, key, cost, prev in sorted(entries):
        L.append(f"\t{key} = {cost}" + (f", {prev}" if prev else ""))
    L += ["}"]
    with open(os.path.join(OUTD, "AxeEntryCostMods.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    chained = sum(1 for e in entries if e[3])
    print(f"entry cost mods: {len(entries)} engine configs priced ({chained} chained to a predecessor, "
          f"{len(free)} base/anchor configs left free) -> AxeEntryCostMods.cfg"
          + (f"  (dropped {dropped} forward chain refs)" if dropped else ""))

def emit_engine_config_gates(ladders, pinned, missing, p2n, by):
    """AxeEngineConfigGates.cfg: remap each RealFuels engine CONFIG's techRequired onto an AXE node. The
    vendored seed/Tree/TREE-Engines.cfg walker sets every CONFIG's techRequired to an RP-1 tree node
    (absent here); RealFuels' CanConfig() (EngineConfigTechLevels.cs) gates config availability on exactly
    that field, so without this remap every engine config is permanently locked in career.

    THE CONFIG'S OWN GATE IS THE SCATTER. A part's CONFIGs are its upgrade path (ENGINE-STATS.md), and
    tree/nodes.yaml homes each one's `RFUpgrade_<config>` token on the breakthrough node that earns it --
    RL10A-1 at cryo_expanderCycle, the A-3/A-4 family at cryo_refinedExpander, the CECE/RL10C/E family at
    cryo_deployableNozzleExpander. That token is only an R&D *icon*; techRequired on the CONFIG is the real
    lever, so it has to follow the token or unlocking the part hands the player every variant at once
    (the pre-2026-07-27 behaviour: layer 1 pointed every CONFIG at p2n[part], collapsing the whole ladder).

    Matched BY RP-1 NODE VALUE (the AxeExternalTechRemap idiom): skips configs with no RP-1 gate and never
    touches AXE-authored configs (they don't carry the RP-1 node). Layer 0 adds a config-name filter on top
    of that same match. :FINAL runs after the walker (:BEFORE[RealismOverhaulEnginesPost]) AND after
    AxeExternalTechRemap's :LAST spot-fixes -- which it therefore leaves intact (their configs no longer
    carry the RP-1 node this matcher looks for).

    THREE layers, emitted (and thus applied) in this order -- each one consumes the RP-1 value it matches,
    so a later layer can never re-home what an earlier one already moved:
      0. Per-CONFIG homing: @PART[p]{ CONFIG[c]:HAS[#techRequired[R]] -> the config's ladder node }. The
         upgrade ladder proper; see engine_config_ladders() for the homing rules and their guards.
      1. Per-part fallback from manifest/engine-stats.tsv: @PART[p]{ CONFIG:HAS[#techRequired[R]] -> p2n[p] }
         -- catches what layer 0 left: base configs, the guards above, and configs with no placed token.
      2a. Global catch-all per (RP-1 node, CONFIG name), for RP-1 nodes layer 2b cannot see. Config names
         are global identities in RealFuels, so the curated homing of `MMH+NTO` is the right answer for
         `MMH+NTO` on any part -- this reproduces the ladder on parts engine-stats never heard of.
      2b. Global catch-all per RP-1 node: @PART[*]{ CONFIG:HAS[#techRequired[R]] -> modal AXE node }.
         engine-stats is INCOMPLETE (misses curated engines like ROE-LR105 and all uncurated ones), so a
         per-node catch-all sweeps up every config the per-part pass left behind (they'd otherwise stay on
         a dead RP-1 node = permanently locked). The catch-all runs AFTER the specifics, so curated configs
         already moved are no longer on R and the catch-all can't touch them; only the residual
         (non-engine-stats parts) lands on the era-representative modal node. Modal is approximate
         (88/132 nodes span >1 AXE node) but era-appropriate -- refine per-part later by completing
         engine-stats.

    COVERAGE IS ASSERTED, NOT ASSUMED. This pass used to derive the layer-2 key set from the *residual*
    rungs only, so an RP-1 node carried exclusively by curated parts -- all of which layer 0 had already
    re-homed -- got no catch-all row at all, and every uncurated part keeping that value stayed locked
    forever. That silently cost 702 RCS engine configs (`earlyDocking`, `reusableControl`): every
    hypergolic RCS propellant in the game, unreachable, on 66 placed parts. The key set is now every RP-1
    node the walker touches, and an uncovered one raises."""
    scattered = []                                                     # (part, config, rp1node, axenode)
    pairs = set()                                                      # (part, rp1node) left to layer 1
    r2a = collections.defaultdict(collections.Counter)                 # rp1node -> Counter(AXE node), residual rungs
    r2a_moved = collections.defaultdict(collections.Counter)           # ...same, from rungs layer 0 already homed
    c2a = collections.defaultdict(collections.Counter)                 # (rp1node, config) -> Counter(AXE node)
    all_rp1 = set()                                                    # every RP-1 node the walker uses
    for part in sorted(ladders):
        for r in ladders[part]:
            if r["rp1"]: all_rp1.add(r["rp1"])
            if r["moved"]:
                scattered.append((part, r["config"], r["rp1"], r["node"], r.get("ungated")))
                if r["rp1"]:
                    c2a[(r["rp1"], r["config"])][r["node"]] += 1
                    r2a_moved[r["rp1"]][r["node"]] += 1
            elif r["rp1"]:
                pairs.add((part, r["rp1"]))
                if part in p2n: r2a[r["rp1"]][p2n[part]] += 1

    L = ["// GENERATED by tools/build_tree.py — DO NOT EDIT BY HAND",
         "// Remap every RealFuels engine CONFIG's techRequired -> an AXE node. The vendored",
         "// seed/Tree/TREE-Engines.cfg walker points each CONFIG at an RP-1 node; RealFuels' CanConfig()",
         "// (EngineConfigTechLevels.cs) gates config availability on CONFIG/techRequired, so THIS is what",
         "// unlocks engine configs in career -- the CONFIG gate, not the RFUpgrade_* R&D icon, is what makes",
         "// an engine's variant ladder a ladder. Matched by RP-1 NODE VALUE (AxeExternalTechRemap idiom):",
         "// dodges config-name escaping, skips ungated configs, never clobbers AXE-authored config gates.",
         "// :FINAL runs after the walker (:BEFORE[RealismOverhaulEnginesPost]) and after",
         "// AxeExternalTechRemap's :LAST spot-fixes (preserved -- their configs no longer carry the RP-1 node).",
         "// LAYER 0 -- per-CONFIG homing: each variant follows its own RFUpgrade_* token's node (the ladder):"]
    for part, cfg, rp1, node, ungated in scattered:
        # gated: match on the RP-1 value so the patch consumes it and later layers cannot re-home it.
        # ungated: no RP-1 value to match, so address the CONFIG by name and %-set the field (create it
        # if absent). RealFuels treats a CONFIG with no techRequired as always available, so this is
        # what actually puts an AXE-authored variant behind a node at all.
        sel = f"@CONFIG[{cfg}]:HAS[#techRequired[{rp1}]],*" if not ungated else f"@CONFIG[{cfg}],*"
        setter = f"@techRequired = {node}" if not ungated else f"%techRequired = {node}"
        L.append(f"@PART[{part}]:HAS[@MODULE[Module*EngineConfigs]]:FINAL "
                 f"{{ @MODULE[Module*EngineConfigs],* {{ {sel} {{ {setter} }} }} }}")
    L.append("// LAYER 1 -- per-part fallback: base configs + variants with no placed token stay on the part's node:")
    for part, rp1 in sorted(pairs):
        node = p2n.get(part, "parking")
        L.append(f"@PART[{part}]:HAS[@MODULE[Module*EngineConfigs]]:FINAL "
                 f"{{ @MODULE[Module*EngineConfigs],* {{ @CONFIG:HAS[#techRequired[{rp1}]],* {{ @techRequired = {node} }} }} }}")
    # 2a runs before 2b so a config name we curated keeps its own node instead of the era modal.
    uncovered = sorted(all_rp1 - set(r2a))
    L.append("// LAYER 2a -- global per-CONFIG catch-all for RP-1 nodes carried ONLY by curated parts (no")
    L.append("//             residual rung to build a modal from). Config names are global in RealFuels, so")
    L.append("//             the curated homing is the right answer for that name on any part:")
    bycfg = 0
    for rp1 in uncovered:
        for (r, cfg), tally in sorted(c2a.items()):
            if r != rp1: continue
            node = tally.most_common(1)[0][0]
            L.append(f"@PART[*]:HAS[@MODULE[Module*EngineConfigs]]:FINAL "
                     f"{{ @MODULE[Module*EngineConfigs],* {{ @CONFIG[{cfg}]:HAS[#techRequired[{rp1}]],* {{ @techRequired = {node} }} }} }}")
            bycfg += 1
    L.append("// LAYER 2b -- global per-node catch-all for configs the per-part pass missed (engine-stats-absent")
    L.append("//             curated engines + uncurated parts); modal AXE node per RP-1 tech generation:")
    catchall, orphans = 0, []
    for rp1 in sorted(all_rp1):
        tally = r2a.get(rp1) or r2a_moved.get(rp1)
        if not tally:
            orphans.append(rp1); continue
        node = tally.most_common(1)[0][0]
        L.append(f"@PART[*]:HAS[@MODULE[Module*EngineConfigs]]:FINAL "
                 f"{{ @MODULE[Module*EngineConfigs],* {{ @CONFIG:HAS[#techRequired[{rp1}]],* {{ @techRequired = {node} }} }} }}")
        catchall += 1
    if orphans:
        raise SystemExit("engine config gates: no AXE node to catch-all these RP-1 nodes onto -- every "
                         "config still carrying one would be permanently locked: " + ", ".join(orphans))
    with open(os.path.join(OUTD, "AxeEngineConfigGates.cfg"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    nparts = len(set(x[0] for x in scattered) | set(p for p, _ in pairs))
    print(f"engine config gates: {len(scattered)} per-config ladder gates + {len(pairs)} per-part fallbacks "
          f"({nparts} engine parts) + {bycfg} per-config catch-alls for {len(uncovered)} curated-only RP-1 "
          f"node(s) ({', '.join(uncovered) or 'none'}) + {catchall} per-node catch-alls "
          f"-> AxeEngineConfigGates.cfg"
          + (f"  (pinned {len(pinned)}: {', '.join(p for p, _ in pinned)})" if pinned else "")
          + (f"  (WARN {len(missing)} unplaced parts -> parking)" if missing else ""))

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

# Capability-grant families -> (predicate, heading, mechanism note, wired?). REFERENCE/provisional tree
# content is PLACED on purpose (docs/PLACEHOLDERS.md); an UNWIRED family is the checklist to work through
# when actually implementing it, not a reason to drop it. A WIRED family stays listed as an inventory of
# what exists and what implements it, but it is not backlog and does not count toward the headline.
IMPL_FAMILIES = [
    (lambda g: g.startswith("RP0Level") and "TrackingStation" in g,
     "Deep Space Network / tracking-station levels",
     "SHIPPED — the 11-level ladder + DSN gain are re-provided by design/Settings/AxeTrackingStation.cfg "
     "(CustomBarnKit @TRACKING, consumed by RealAntennas) and the per-level tech gate by "
     "design/Tree/AxeFacilityGates.cfg (AXEBUILDINGTECHS), enforced in AXE.dll (AxeTrackingStationGate). "
     "The grant stubs below remain as the tree-node presentation tokens.",
     True),
    # Avionics track = RP-1 "Science-Core" (Guided) + "Deep-Space" (the Shielded axis). Match the
    # Deep-Space prefix explicitly: `Deep-Space-interplanetaryProbes` is the one shielded rung whose name
    # carries no "avionics" substring, and it used to fall through to the catch-all below.
    (lambda g: g.startswith("Science-Core") or g.startswith("Deep-Space") or "avionics" in g.lower(),
     "Avionics capability tiers",
     "SHIPPED — the tier effect is applied by AXE.dll's ModuleAxeAvionics, which reads the researched "
     "tech node DIRECTLY off the TIER ladder in design/Tree/AxeAvionicsCore.cfg: `tech =` for the 13 "
     "Guided rungs (ApplyTier) and `shTech =` for the 10 Radiation-Shielded rungs (ApplyShieldedTier). "
     "The plugin never consults the grant tokens — they carry no stat MODULE and exist only so the "
     "capability is visible in R&D (AxeGrantUpgradeUnlock marks them unlocked on research).",
     True),
    (lambda g: True,
     "Other capability grants",
     "UNCLASSIFIED — no family above matched this grant, so nothing is known to implement it. Either add "
     "a family entry (if a mechanism exists) or build one. This table should normally be empty.",
     False),
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
    still needs game-side wiring. Source of truth = every `grants:` capability token + any node carrying an
    explicit `impl_todo:` note. Fully auto-derived, so it can never drift from the actual tree — but the
    per-family `wired` flag in IMPL_FAMILIES is hand-maintained: flip it when the mechanism lands, or the
    doc keeps reporting shipped work as backlog (which is exactly what happened to the avionics family)."""
    fams = [(heading, desc, wired, []) for _, heading, desc, wired in IMPL_FAMILIES]
    for n in nodes:
        for g in (n.get("grants") or []):
            for i, (pred, _, _, _) in enumerate(IMPL_FAMILIES):
                if pred(g): fams[i][3].append((g, n)); break
    todo = [n for n in nodes if n.get("impl_todo")]
    nwired = sum(len(rows) for _, _, wired, rows in fams if wired)
    nunwired = sum(len(rows) for _, _, wired, rows in fams if not wired)
    gnodes = {n["id"] for _, _, _, rows in fams for _, n in rows}
    L = []; A = L.append
    A("# Implementation Backlog")
    A("")
    A("> **Generated by `tools/build_tree.py` — do not hand-edit.** Regenerated on every build.")
    A("")
    A("Tree content that is PLACED and researchable now, but whose in-game **effect** still needs")
    A("game-side wiring: `grants:` capability tokens whose family has no mechanism behind it yet, plus any")
    A("node carrying an explicit `impl_todo:` note. **WIRED** families are listed too — as an inventory of")
    A("what exists and what implements it — but they are finished work, not backlog. REFERENCE items live")
    A("in the tree on purpose; an unwired family is **the list to work through when building it**, not a")
    A("reason to drop it.")
    A("")
    A(f"**{nunwired} grants awaiting wiring; {nwired} wired, across {len(gnodes)} nodes; {len(todo)} "
      f"nodes with an explicit impl note.**")
    for heading, desc, wired, rows in fams:
        if not rows: continue
        A(""); A(f"## {heading} ({len(rows)}) — {'WIRED' if wired else 'AWAITING WIRING'}")
        A(""); A(f"_{desc}_"); A("")
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
    print(f"implementation backlog: {nunwired} grants awaiting wiring ({nwired} wired) + {len(todo)} "
          f"impl notes -> docs/IMPL-TODO.md")

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
        # Granted capability ladders live in `upgrades:`, not `grants:` — they are real PARTUPGRADEs with
        # their own definitions and stat-bearing UPGRADE blocks (HardDriveConfigs.cfg), so nothing is
        # emitted for them here. They only need to appear in the marker list so the sweep unlocks them.
        for u in (n.get("upgrades") or []):
            if u.startswith(GRANTED_UPGRADE_PREFIXES): marker.append(u)
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
    L.append("// Includes the GRANTED capability ladders (GRANTED_UPGRADE_PREFIXES) as well as the display")
    L.append("// tokens above. Those DO carry a stat MODULE (the HardDrive UPGRADE block) -- SetUnlocked")
    L.append("// applies it for free, which is the point: AXE grants these ladders, RP-1 sells them.")
    L += ["AXE_GRANT_UPGRADES", "{"] + [f"\tupgrade = {g}" for g in marker] + ["}"]
    with open(os.path.join(OUTD, "AxeGrantUpgrades.cfg"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"grant tokens: {len(av)} avionics + {len(dsn)} DSN + {len(marker) - len(av) - len(dsn)} granted "
          f"ladder rung(s) = {len(marker)} auto-unlocked on research -> AxeGrantUpgrades.cfg")
    return marker

LADDER_TOL = 0.03      # +/- band on the axes a player designs around (thrust, Isp, ignition count)
# Rated burn time gets a much wider band. It is a reliability/qualification detail, not something a
# player optimises a vehicle around, and RO uses it to distinguish marks that are otherwise the same
# engine: Titan's LR87-AJ-5/-7/-9 are identical at 1053.9 kN / 285.2 s and differ ONLY by 150/156/150 s
# of rated burn. At a 3% band those read as three separate decisions and demand three tree events.
LADDER_TOL_BURN = 0.25
# Sea-level Isp deliberately stays STRICT. It tracks nozzle area ratio, and a nozzle change is a real
# mechanism with a real home to scatter to -- so a difference there should split into its own node
# rather than be tolerated away. (Tried at 0.15 on 2026-07-27 and reverted: merging those classes
# pushed the tree toward fewer, fatter nodes, which is exactly backwards.)

def _ladder_perf():
    """config -> perf/propellant row from engine-stats.tsv, for the ladder-collapse classifier."""
    out = {}
    path = os.path.join(REPO, "manifest", "engine-stats.tsv")
    if not os.path.exists(path): return out
    with open(path, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        idx = {k: hdr.index(k) for k in ("config", "propellants", "maxThrust_kN", "ispVac", "ispSL",
                                         "ignitions", "ratedBurnTime") if k in hdr}
        if "config" not in idx: return out
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) <= max(idx.values()): continue
            out[c[idx["config"]].strip()] = {k: c[i].strip() for k, i in idx.items()}
    return out

def _is_electric(p):
    """True for an ELECTRIC-propulsion config (ion, Hall, MPD, pulsed-inductive, VASIMR).

    These are a different CLASS of propulsion and the ladder classifier's chemical-engine semantics do
    not describe them. For a chemical engine, a big Isp jump is a generational step -- the whole premise
    of _ladder_near. For an electric thruster Isp is a DIAL, not a generation: at fixed input power
    P = 1/2 T v_e, so thrust and Isp trade against each other continuously, and one piece of hardware
    spans a wide Isp range depending purely on how it is run. VASIMR is literally named for it, and the
    tree already recognised this once by hand -- ep_kilowattClassPPU carries `catalog: true` because
    "the DS4G marks are OPERATING POINTS of one experimental thruster".

    So two electric configs of one part sitting on one node is a CHOICE (working fluid, operating
    point), not a collapsed generational ladder, and R1 must not read it as one. Detected off the
    propellant list rather than a name pattern: every electric config draws ElectricCharge, and no
    chemical one does (electric-pump-fed engines like Rutherford draw it too, but their EC is pump power
    on a chemical engine -- they are excluded by requiring an electric-propulsion working fluid as the
    other propellant)."""
    prop = (p or {}).get("propellants") or ""
    if "ElectricCharge" not in prop: return False
    return any(w in prop for w in ("XenonGas", "KryptonGas", "ArgonGas", "Ammonia", "Hydrazine",
                                   "LqdAmmonia", "Lithium", "Iodine", "Bismuth"))

def _propfam(s):
    """Normalise a propellant string to a chemistry family; densification tracked separately.
    RealFuels spells the same chemistry several ways (LqdOxygen/Oxygen, LqdHydrogen/Hydrogen) and
    prefixes Cooled* for subcooled/densified loads -- both would otherwise read as a new fork."""
    s = s or ""
    cooled = "Cooled" in s
    s = s.replace("Cooled", "")
    for a, b in (("LqdOxygen", "O2"), ("Oxygen", "O2"), ("LqdHydrogen", "H2"), ("Hydrogen", "H2"),
                 ("LqdMethane", "CH4"), ("Methane", "CH4")):
        s = s.replace(a, b)
    return s.strip(), cooled

def _ladder_near(a, b, tol=LADDER_TOL):
    """True when two configs are the same performance point on every axis a player can feel."""
    for k in ("maxThrust_kN", "ispVac", "ispSL", "ignitions", "ratedBurnTime"):
        t = LADDER_TOL_BURN if k == "ratedBurnTime" else tol
        try: x, y = float(a.get(k) or 0), float(b.get(k) or 0)
        except ValueError: return False
        if abs(x - y) > t * max(abs(x), abs(y), 1e-9): return False
    return True

def check_ladder_collapse(ladders, by, p2n, u2n):
    """Build gate: engine config upgrades must not collapse a family's whole progression onto one node.

    See docs/UPGRADE-LADDERS.md. A part's CONFIGs are four different relationships, not one -- a RUNG
    (next generation, same propellant), a FORK (first config on a new chemistry / nozzle / densified
    load), or PADDING (functionally identical to a sibling). Homing them per-FAMILY instead of
    per-CONFIG turns an enabler node into a bucket: met_stainlessSteel handed over the entire RD-100
    ladder (+63% thrust) in one T2 purchase, and 53 of 107 families were fully collapsed onto one node.

    Reports, non-fatal by default (matches check_tech_gates):
      R1 ERROR  two config upgrades for the same part on the same node
      R5 WARN   an RFUpgrade_* token on the node that holds its own base part (doctrine #4)
      R2 WARN   rungs of a family not at strictly increasing tiers
      R4 WARN   a placed config that is a padding duplicate of an already-placed sibling
    AXE_TREE_STRICT=1 makes R1 fail the build (CI / pre-commit gate)."""
    perf = _ladder_perf()
    r1, r2, r4, r5 = [], [], [], []
    r2same = [0]
    for part, rungs in sorted(ladders.items()):
        # only configs the gate emitter can address individually are policeable; engine-stats.tsv
        # sentinels like "(single config)" / "(no RealFuels config path)" are not real CONFIG names
        placed = [r for r in rungs
                  if not r["base"] and r["node"] in by and CFG_NAME_SAFE.match(r["config"])]
        if not placed: continue
        pnode = p2n.get(part)
        # Padding-equivalence classes: configs at the same performance point are ONE decision, however
        # many names RealFuels gives it. They may share a node (cosmetic variants of one tree event);
        # what they must not do is occupy separate events. So R1 counts CLASSES, not configs.
        # Assign classes from the part's FULL config list in a STABLE order (ascending thrust, then name)
        # rather than in placement order. `placed` is sorted by node tier, so classifying from it made
        # class membership depend on where configs currently sit -- move one and the classification
        # changes under you. Ascending thrust also makes each representative the weakest of its class,
        # so members are bounded above rather than straddling it.
        fam = sorted((r["config"] for r in rungs if r["config"] in perf),
                     key=lambda c: (float(perf[c].get("maxThrust_kN") or 0), c))
        klass, order = {}, []
        for c in fam:
            p = perf[c]
            hit = next((k for k in order if _ladder_near(p, perf[k])), None)
            klass[c] = hit or c
            if not hit: order.append(c)
        for r in placed: klass.setdefault(r["config"], r["config"])
        # R1 -- one node granting two genuinely distinct configs for the same part.
        # EXEMPT: nodes flagged `catalog: true`. Some real engine families are a fixed CATALOG, not a
        # progression -- the PT6 turboprop has eleven marks whose thrust wanders 8.4-13.0 kN with no
        # ordering at all. Forcing one-class-per-node would demand six tree events for a family that
        # contains no six decisions. This matches the tree's existing idiom of opt-in dead-end catalog
        # nodes hanging off a procedural king. Use it only for a genuinely unordered family.
        pernode = collections.defaultdict(list)
        for r in placed: pernode[r["node"]].append(r["config"])
        for node, cfgs in pernode.items():
            if by[node].get("catalog"): continue
            # EXEMPT: electric propulsion is a different CLASS -- Isp is an operating point there, not a
            # generation, so two of its configs on one node is a choice, not a collapsed ladder
            # (see _is_electric). User call, 2026-07-28.
            if all(_is_electric(perf.get(c)) for c in cfgs): continue
            if len({klass[c] for c in cfgs}) > 1:
                r1.append((part, node, by[node]["tier"], sorted(cfgs)))
        # R4 -- one padding class spread over several nodes: spurious tree events for a single decision.
        # A class whose members burn DIFFERENT propellants is exempt: two configs can land on the same
        # performance point by different chemistry (RD-107-11D512P is CooledSyntin, its twin 14D22 is
        # plain Kerosene), and each still belongs at the node that unlocks its own propellant. Matching
        # numbers do not make them one decision when the thing that produced them differs.
        perclass, perfam = collections.defaultdict(set), collections.defaultdict(set)
        for r in placed:
            perclass[klass[r["config"]]].add(r["node"])
            perfam[klass[r["config"]]].add(_propfam(perf.get(r["config"], {}).get("propellants"))[0])
        for k, ns in perclass.items():
            # EXEMPT when one of the nodes is the part's own: engine_config_ladders PINS a config there
            # so a freshly-bought engine is always flyable, and doctrine #4 forbids its class-mates from
            # joining it. That split is structural, not a placement mistake -- nothing can fix it, so
            # reporting it forever only trains you to ignore the rule.
            if len(ns) > 1 and len(perfam[k]) == 1 and pnode not in ns:
                r4.append((part, k, sorted(ns)))
        # R5 -- token homed on the part's own node (the pin guard in engine_config_ladders is exempt:
        # it deliberately keeps one config there so a freshly-bought engine is always flyable)
        for r in placed:
            if pnode and u2n.get("RFUpgrade_" + r["config"]) == pnode:
                r5.append((part, r["config"], pnode))
        # walk the family in tree order, classifying against what is already reachable
        seen, bfam = [], None
        basecfg = next((r for r in rungs if r["base"]), None)
        if basecfg and basecfg["config"] in perf:
            bfam = _propfam(perf[basecfg["config"]].get("propellants"))[0]
            seen.append(basecfg)
        lasttier, lastnode = None, None
        for r in sorted(placed, key=lambda x: (by[x["node"]]["tier"], x["era"])):
            p = perf.get(r["config"])
            if not p: continue
            fam, cooled = _propfam(p.get("propellants"))
            isfork = cooled or (bfam is not None and fam != bfam
                                and not any(_propfam(perf[s["config"]].get("propellants"))[0] == fam
                                            for s in seen if s["config"] in perf))
            # R2 -- rungs (not forks) must ascend; forks legitimately branch off sideways.
            # Same-node pairs are already an R1, so only report a genuine tier regression here.
            t = by[r["node"]]["tier"]
            # A rung landing at the SAME tier on a different node is benign -- two lanes can legitimately
            # reach the same depth. Only a genuine DESCENT (a later rung gated earlier than the one it
            # supersedes) is a real ordering fault, so keep the two apart rather than burying one in the
            # other: 19 same-tier notes would otherwise hide the single descent that actually matters.
            if not isfork and lasttier is not None and r["node"] != lastnode:
                if t < lasttier: r2.append((part, r["config"], r["node"], t, lasttier))
                elif t == lasttier: r2same[0] += 1
            if not isfork: lasttier, lastnode = t, r["node"]
            seen.append(r)

    if not (r1 or r2 or r4 or r5 or r2same[0]):
        print("ladder gate: clean -- no collapsed engine-config ladders"); return []
    print(f"ladder gate: {len(r1)} collapsed node(s), {len(r5)} base-node token(s), "
          f"{len(r2)} DESCENDING rung(s) (+{r2same[0]} benign same-tier), {len(r4)} split padding class(es)"
          f"  [docs/UPGRADE-LADDERS.md]")
    for part, node, tier, cfgs in sorted(r1, key=lambda x: -len(x[3]))[:12]:
        print(f"   R1 ! {part} -> {node} T{tier} grants {len(cfgs)}: {', '.join(cfgs[:6])}"
              f"{' ...' if len(cfgs) > 6 else ''}")
    if len(r1) > 12: print(f"   R1 ... and {len(r1) - 12} more collapsed node(s)")
    for part, cfg, node in r5[:5]:
        print(f"   R5 ~ {part}: {cfg} sits on its own base part's node {node}")
    if len(r5) > 5: print(f"   R5 ... and {len(r5) - 5} more")
    for part, cfg, node, t, lt in r2[:5]:
        print(f"   R2 ! {part}: {cfg} @ {node} T{t} is gated EARLIER than the rung it supersedes (T{lt})")
    if len(r2) > 5: print(f"   R2 ... and {len(r2) - 5} more")
    for part, cfg, ns in r4[:5]:
        print(f"   R4 ~ {part}: '{cfg}' performance point split across {len(ns)} nodes: {', '.join(ns)}")
    if len(r4) > 5: print(f"   R4 ... and {len(r4) - 5} more")
    # R1 and R5 are now at zero and FAIL THE BUILD if they regress (reached 2026-07-27; the pass that got
    # there is docs/UPGRADE-LADDERS.md). R2 descents likewise. R4 stays advisory: a split performance class
    # is usually a real placement choice, and some are forced by the base-config pin guard.
    hard = len(r1) + len(r5) + len(r2)
    if hard:
        die(f"{len(r1)} collapsed ladder(s), {len(r5)} base-node token(s), {len(r2)} descending rung(s) "
            f"— see above. These are invariants, not warnings; set AXE_LADDER_SOFT=1 to downgrade while "
            f"mid-edit.") if not os.environ.get("AXE_LADDER_SOFT") else None
    return r1

def check_unplaced_upgrades(u2n, grant2n):
    """Inventory of the PARTUPGRADEs that fell through to `parking` — the upgrade-side twin of the
    "N unplaced parts -> parking" line emitted next to the placement patch.

    emit_placement_patch parks EVERY part and upgrade on `parking`, then overrides the placed ones. For
    parts that lands you a count; for upgrades nothing counted them at all, so an unplaced upgrade was
    indistinguishable from a placed one without reading the ConfigCache. That is how solarTL5/8/9/10 sat
    parked unnoticed while docs/UPGRADES.md recorded them as gated on dangling RP-1 node IDs (they never
    were — this patch overwrites ROSolar's techRequired long before the game sees it).

    Parking is a legitimate holding pen for undecided placements, so this REPORTS, never fails. Three
    buckets, because they mean different things:
      LIVE      mod-authored, present in-game right now (manifest/upgrades-live.tsv) -- the real gap
      KEEP      AXE-vendored RP-1 upgrade whose host part is curated -- a hole in an engine ladder
      dormant   KEEP-engine-dormant: the config's engine is absent from our RO, so the upgrade is inert
                until a mod adds it (RESTART.md T3). Expected; counted, not listed."""
    placed = set(u2n) | set(grant2n or {})
    def read(fn):
        path = os.path.join(REPO, "manifest", fn)
        if not os.path.exists(path): return []
        with open(path, encoding="utf-8") as f:
            hdr = f.readline().rstrip("\n").split("\t")
            return [dict(zip(hdr, l.rstrip("\n").split("\t"))) for l in f if l.strip()]
    live = [r for r in read("upgrades-live.tsv") if r.get("name") and r["name"] not in placed]
    cur = [r for r in read("upgrades-curated.tsv")
           if r.get("name") and r["name"] not in placed and r.get("disposition", "").startswith("KEEP")]
    dormant = [r for r in cur if r["disposition"] == "KEEP-engine-dormant"]
    keep = [r for r in cur if r["disposition"] != "KEEP-engine-dormant"]
    if not (live or keep):
        print(f"unplaced upgrades: clean -- every live + curated-KEEP upgrade is homed"
              f"{f' ({len(dormant)} dormant, engine absent from our RO)' if dormant else ''}")
        return []
    print(f"unplaced upgrades: {len(live)} LIVE + {len(keep)} curated-KEEP fell through to `parking`"
          f"{f' (+{len(dormant)} dormant, expected)' if dormant else ''}  [docs/UPGRADES.md]")
    for r in sorted(live, key=lambda r: (r.get("mod", ""), r["name"]))[:20]:
        print(f"   LIVE ~ {r['name']:<26} {r.get('mod', '?'):<18} {r.get('title', '')[:46]}")
    if len(live) > 20: print(f"   LIVE ... and {len(live) - 20} more")
    for r in sorted(keep, key=lambda r: r["name"])[:10]:
        print(f"   KEEP ~ {r['name']:<26} {r.get('disposition', ''):<18} {r.get('title', '')[:46]}")
    if len(keep) > 10: print(f"   KEEP ... and {len(keep) - 10} more")
    return live + keep

EP_SPREAD_MAX = 5.0          # a node may grant electric configs spanning at most this ratio in input power
EP_CHARTER_PREFIXES = ("jpl_", "okb_", "hire_")   # integrated probe craft: chronological by design, exempt

def _ep_input_kw(cfg, perf):
    """Input electrical power (kW) of an electric config, from its own thrust and Isp.

    Jet power is exact: P_jet = 1/2 * T * v_e = 1/2 * T * g0 * Isp. Input power is that over the
    thruster's total efficiency; 1/1.6 (~63%) reproduces published figures closely across the range --
    NEXT computes 7.8 kW against a real 6.9, HERMeS/AEPS 13.4 against a real 12.5, SPT-100 1.0 against
    a real 1.35. Good to well inside the band widths this gate cares about."""
    p = perf.get(cfg)
    if not p or not _is_electric(p): return None
    try:
        T, isp = float(p.get("maxThrust_kN") or 0) * 1000.0, float(p.get("ispVac") or 0)
    except ValueError: return None
    if T <= 0 or isp <= 0: return None
    return 0.5 * T * 9.80665 * isp * 1.6 / 1000.0

def check_ep_power_spread(u2n, by, hard=False):
    """Gate: one node must not grant electric configs from wildly different power classes.

    For electric propulsion the enabling breakthrough is not the thruster, it is the power chain --
    array -> PPU -> radiator. A 0.2 kW SPT-50 and a 74 kW 457M are the same physics and completely
    different engineering, and the whole difference is in what feeds them. So a node granting both is
    the EP equivalent of a collapsed ladder: one purchase spanning several generations of power
    handling. (This is a different failure from R1, which asks whether two configs of ONE PART are
    distinct decisions; this asks whether one NODE spans power classes, across parts.)

    Measures UPGRADE-granted configs only. A node's base configs arrive with its parts, and parts are
    placed by mechanism on purpose -- policing those would be a parts-placement pass, not this one.
    Charter nodes are exempt: integrated probe craft (Dawn, DS1) are homed chronologically by design.

    WARN by default; `hard` makes it fail the build once the lane is clean."""
    perf = _ladder_perf()
    pernode = collections.defaultdict(list)
    for up, node in u2n.items():
        if not up.startswith("RFUpgrade_"): continue
        if node.startswith(EP_CHARTER_PREFIXES): continue
        kw = _ep_input_kw(up[len("RFUpgrade_"):], perf)
        if kw: pernode[node].append((kw, up[len("RFUpgrade_"):]))
    bad = []
    for node, v in pernode.items():
        if len(v) < 2: continue
        lo, hi = min(v), max(v)
        if hi[0] / lo[0] > EP_SPREAD_MAX:
            bad.append((hi[0] / lo[0], node, by.get(node, {}).get("tier"), lo, hi, len(v)))
    bad.sort(reverse=True)
    if not bad:
        print(f"EP power gate: clean -- no node grants electric configs spanning >{EP_SPREAD_MAX:g}x in input power")
        return []
    print(f"EP power gate: {len(bad)} node(s) span >{EP_SPREAD_MAX:g}x in electric input power  [docs/UPGRADE-LADDERS.md]")
    for ratio, node, tier, lo, hi, n in bad:
        print(f"   EP ~ {node} T{tier} spans {ratio:>5.0f}x: {lo[1]} {lo[0]:.1f} kW .. {hi[1]} {hi[0]:.1f} kW ({n} configs)")
    if hard and not os.environ.get("AXE_LADDER_SOFT"):
        die(f"{len(bad)} node(s) span >{EP_SPREAD_MAX:g}x in electric input power — see above.")
    return bad

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

# AXE's own 8-level R&D ladder -- design/Settings/AxeFacilities.cfg @RESEARCH scienceCostLimit.
# (cap, highest tier it must ALLOW, lowest tier it must REFUSE). Keep in step with that file: the
# .cfg is what the game reads, this is only the assertion that the cost table still lines up with it.
SCIENCE_CAPS = [(82, 5, 6), (265, 7, 8), (404, 8, 9), (600, 9, 10),
                (865, 10, 11), (1225, 11, 12), (1655, 12, 13)]

def check_science_caps(meta):
    """The R&D building gates research by NODE COST, not by tier: a level whose scienceCostLimit is
    82 simply refuses any node costing more. So the tier at which each cap bites is economy design
    (docs/ECONOMY.md 8) that lives, invisibly, in the cost table -- nudge `scalar` a few percent and a
    whole tier silently changes which R&D level it needs. Assert the intended boundaries instead."""
    tc, scalar = meta.get("tier_cost", {}), meta.get("scalar", 1.0)
    if not tc: return
    rate = {int(t): round(v * scalar) for t, v in tc.items()}
    bad = []
    for cap, under, over in SCIENCE_CAPS:
        if rate.get(under, 0) > cap:
            bad.append(f"T{under} = {rate[under]} exceeds the {cap} cap (should be researchable under it)")
        if rate.get(over, 0) <= cap:
            bad.append(f"T{over} = {rate[over]} fits under the {cap} cap (should require the next R&D level)")
    # Each cap brackets `scalar`: it must stay high enough to keep T{over} ABOVE the cap and low
    # enough to keep T{under} at or below it. Report the binding pair and which boundary sets each,
    # so a retune knows how much room it has and which cap to move first.
    lo = max(((cap / tc[over], cap) for cap, _, over in SCIENCE_CAPS if tc.get(over)), default=(0, 0))
    hi = min(((cap / tc[under], cap) for cap, under, _ in SCIENCE_CAPS if tc.get(under)),
             default=(float("inf"), 0))
    if bad:
        print(f"science cap gate: {len(bad)} BROKEN boundary(ies) -- scalar {scalar} [docs/ECONOMY.md 8]")
        for b in bad: print("   !", b)
    else:
        print(f"science cap gate: clean -- {len(SCIENCE_CAPS)} boundaries hold "
              f"({'/'.join(f'T{u}|T{o}' for _, u, o in SCIENCE_CAPS)}); scalar {scalar} may range "
              f"{lo[0]:.3f} (cap {lo[1]}) .. {hi[0]:.3f} (cap {hi[1]})")

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
    check_unplaced_upgrades(u2n, grant2n)   # inventory: which upgrades fell through to `parking`
    ladders, pinned, missing = engine_config_ladders(p2n, u2n, by)   # where each RealFuels CONFIG lands
    emit_engine_config_gates(ladders, pinned, missing, p2n, by)  # AxeEngineConfigGates.cfg: CONFIG techRequired -> AXE node
    emit_entry_cost_mods(ladders, by, meta)  # AxeEntryCostMods.cfg: ENTRYCOSTMODS funds price per engine config
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
    check_science_caps(meta)             # gate: node costs must straddle the R&D scienceCostLimit boundaries
    print("-> GameData/RP-AXE/design/Tree/AxeTechTree.cfg (+ AxeTreeMeta.cfg), tree/render/axe-tree.svg|png|html")
    check_probe_requirements(nodes)
    emit_impl_backlog(nodes)             # docs/IMPL-TODO.md: provisional grants + impl_todo -> checklist
    check_tech_gates(nodes)              # gate: authored tech-refs (design/*.cfg + Source) must resolve (fail closed+silent otherwise)
    check_ladder_collapse(ladders, by, p2n, u2n)   # gate: engine-config ladders must not collapse onto one node
    check_ep_power_spread(u2n, by, hard=True)   # gate: one node must not span electric power classes (0 since 2026-07-28)

if __name__ == "__main__": main()
