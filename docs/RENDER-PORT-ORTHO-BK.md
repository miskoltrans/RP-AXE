# In-game render: bake layout offline (BK), render only edges in KSP

> **✅ STATUS: SHIPPED — this plan is built, not pending.** Both halves are live: `build_tree.py` bakes the
> layout offline (`COORDS_BK = True` in `sugiyama_layout`, positions emitted into `AxeTechTree.cfg`), and
> `RenderSettings.cfg` ships `layout = stock`, which per its own header comment means *"use the emitter's
> positions (build_tree.py Brandes-Köpf), route edges only"* — i.e. the runtime re-layout is off exactly as
> this document proposed. The legacy in-C# `sugiyama`/`bands` layouts remain as fallbacks. The notes below
> are the original design rationale, kept for reference.

> **Supersedes the earlier "port BK into C#" plan.** Decision (2026-07-02): node placement is **static
> data** → compute it **offline in the compiler** and delete the runtime re-layout. KSP does only what it
> genuinely must at runtime: draw the **ortho-late** edges (there's no cfg field for a custom edge polyline).
> Shipping look = **ortho-late routing + Brandes–Köpf (`sugiyama-bk`) layout**, already the prototype default.

## Why this is the right split (ground truth)

`tools/build_tree.py` `main()` already bakes positions:
```
resolve(...)                 # discipline-grid fallback _x,_y
routes = sugiyama_layout(...) # OVERWRITES _x,_y with the layered layout (+ returns dummy-routed edges)
emit_cfg(...)                # AxeTechTree.cfg: pos = _x,_y,-1   -> THE GAME TREE (line ~235)
emit_prototype_data(...)     # tree-data.js: pos = [_x,_y] + waypoints -> THE PROTOTYPE (line ~656)
```
So the game cfg **already** carries the compiler's node positions. `AxeTreeRender.OnTreeSpawn` then
*overwrites* them at runtime with its own `LayoutSugiyama`/`LayoutBands` — that was a decoupling
convenience while layout was being iterated in the prototype; now that BK is decided, consolidate.

**Consequences of moving BK into the compiler:**
- `AxeTechTree.cfg` **and** `tree-data.js` both get BK positions from one change — so the prototype's
  **"compiler" layout mode previews exactly what ships** (and equals its own `sugiyama-bk` mode).
- The C# plugin **sheds** its entire layout body (~400 lines), the `RDNode.pos` reflection, the
  `OnTreeSpawn` reposition, and the runtime fit/flip. One layout implementation instead of three.
- Only **edges** stay at runtime (KSP draws them via Vectrosity → `RDNode.GetVectorArray`), computed from
  the now-baked positions. That's the small, unavoidable piece.

---

# Part A — `build_tree.py`: Brandes–Köpf coordinates (Python)

> This is the **layout agent's file** (`sugiyama_layout` is theirs). The change lives squarely in that
> function; give them this section, or land it path-scoped and flag them. Everything else follows for free.

### A1. Build `seg_prev` (adjacent-rank segments only) in `sugiyama_layout`

BK needs the *proper-layered* adjacency, not `prev`/`nxt` (which include non-forward edges). In the chain
loop (~line 111) where `nxt`/`prev` are filled, also record adjacent-rank predecessors:
```python
seg_prev = collections.defaultdict(list)     # declare beside prev, nxt (~line 97)
...
for a, b in zip(chain, chain[1:]):
    nxt[a].append(b); prev[b].append(a)
    if vtier[b] == vtier[a] + 1: seg_prev[b].append(a)   # <-- add: BK proper-layering only
```

### A2. Branch the coordinate assignment (BK default, keep PAV)

Add a `coords="bk"` param to the signature:
```python
def sugiyama_layout(disc, nodes, by, sweeps=8, coords="bk"):
```
After the best ordering is restored and `isd`/`gap` are defined (~line 148), replace the PAV coordinate
block (the `pav` def + the `y = {...}` seed + the `for _ in range(30)` loop, ~lines 149–170) with:
```python
    if coords == "bk":
        y = _bk_coords(order, layers, seg_prev, gap, isd)
    else:
        # ---- existing PAV/isotonic block, UNCHANGED (def pav; y = {...}; for _ in range(30): ...) ----
        ...
    # ---- miny / Y / n['_x'],n['_y'] / return chains stay exactly as-is ----
```
`gap` and `isd` already exist in the function; nothing downstream changes — BK writes the same `y` dict.

### A3. `_bk_coords` (paste-ready; module-level, no new imports)

Faithful port of `renderer.js` `bkCoords/bkType1/bkAlign/bkCompact/bkRun` — Brandes & Köpf 2002, 2 runs
(down-left + within-layer-mirrored down-right) averaged, with a final monotone sweep guaranteeing separation.
```python
def _bk_coords(order, layers, seg_prev, gap, isd):
    """Brandes–Köpf: align each vertex to its median predecessor into vertical BLOCKS, then compact
    blocks under a min gap -> aligned edges become straight runs. 2 runs (L/R) averaged + sep sweep."""
    INF = float("inf")
    L = [layers[t] for t in order]

    def bk_run(LL):
        ordv = {}
        for layer in LL:
            for i, v in enumerate(layer): ordv[v] = i
        pred = {v: sorted(seg_prev.get(v, ()), key=lambda u: ordv[u]) for layer in LL for v in layer}
        # type-1 conflicts: segments crossing an inner (dummy–dummy) segment
        conf = set()
        for k in range(len(LL) - 1):
            upper, lower = LL[k], LL[k + 1]
            k0 = scan = 0
            for l1, v in enumerate(lower):
                inner = -1
                if isd(v):
                    for u in pred[v]:
                        if isd(u) and ordv[u] > inner: inner = ordv[u]
                if l1 == len(lower) - 1 or inner >= 0:
                    k1 = inner if inner >= 0 else len(upper) - 1
                    while scan <= l1:
                        w = lower[scan]
                        for u in pred[w]:
                            if (ordv[u] < k0 or ordv[u] > k1) and not (isd(u) and isd(w)):
                                conf.add((u, w))
                        scan += 1
                    k0 = k1
        # vertical alignment -> blocks (root, align)
        root = {v: v for layer in LL for v in layer}
        align = {v: v for layer in LL for v in layer}
        for layer in LL:
            r = -1
            for v in layer:
                ws = pred[v]
                if not ws: continue
                n = len(ws)
                for i in range((n - 1) // 2, n // 2 + 1):     # median predecessor(s)
                    if align[v] != v: break
                    w = ws[i]
                    if r < ordv[w] and (w, v) not in conf and (v, w) not in conf:
                        align[w] = v; root[v] = root[w]; align[v] = root[w]; r = ordv[w]
        # horizontal compaction (one direction)
        above = {}
        for layer in LL:
            for i, v in enumerate(layer): above[v] = layer[i - 1] if i else None
        X, sink, shift = {}, {v: v for layer in LL for v in layer}, {v: INF for layer in LL for v in layer}
        def place(v):
            if v in X: return
            X[v] = 0.0; w = v
            while True:
                u = above[w]
                if u is not None:
                    ru = root[u]; place(ru)
                    if sink[v] == v: sink[v] = sink[ru]
                    d = gap(u, w)
                    if sink[v] == sink[ru]: X[v] = max(X[v], X[ru] + d)
                    else: shift[sink[ru]] = min(shift[sink[ru]], X[v] - X[ru] - d)
                w = align[w]
                if w == v: break
        for layer in LL:
            for v in layer:
                if root[v] == v: place(v)
        xs = {}
        for layer in LL:
            for v in layer:
                xs[v] = X[root[v]]
                s = shift[sink[root[v]]]
                if s < INF: xs[v] += s
        return xs

    cL = bk_run(L)
    cR = {k: -val for k, val in bk_run([list(reversed(layer)) for layer in L]).items()}
    def norm(m):
        mn = min(m.values())
        for k in m: m[k] -= mn
    norm(cL); norm(cR)
    y = {v: (cL[v] + cR[v]) / 2.0 for layer in L for v in layer}    # balance L/R bias
    for layer in L:                                                 # guarantee separation
        for i in range(1, len(layer)):
            need = y[layer[i - 1]] + gap(layer[i - 1], layer[i])
            if y[layer[i]] < need: y[layer[i]] = need
    return y
```
> `place()` recurses over block-above chains (normally shallow). If a big tree ever hits `RecursionError`,
> add `sys.setrecursionlimit(10000)` in `main()` or convert `place` to an explicit stack.

### A4. `emit_cfg`: flip Y into KSP's convention  ← **verify #1**

`emit_cfg` writes `_y` straight (~line 235). The runtime port used `FLIP_Y=true` to make discipline order
read **top-to-bottom** (i.e. KSP's tree canvas is y-up vs. the prototype/compiler y-down). With positions
now baked, do that flip here so the tree isn't upside-down without runtime help:
```python
maxY = max(n["_y"] for n in nodes)
... pos = {n['_x']},{maxY - n['_y']},-1     # flip: y-down (compiler) -> y-up (KSP)
```
Leave `emit_prototype_data` on raw `_y` (Canvas is y-down — the prototype stays correct). This is the one
coordinate thing to confirm in-game; if it renders inverted, drop/re-add the flip.

**Result of Part A:** `AxeTechTree.cfg` (game) + `tree-data.js` (prototype) both carry BK positions from one
compiler run. Prototype **Layout = Compiler** now equals the shipped layout.

---

# Part B — C# plugin: delete the layout, keep the edges

### B1. `AxeTreeLayout.cs`
- **DELETE** `LayoutSugiyama`, `LayoutBands`, and their helpers (`SChain`, the PAV/median/dummy machinery,
  `MedianCost`, `Ord` if now unused). These move to the compiler.
- **KEEP** `Chamfer`, `RoundPolyline`, `ComputeSlots`, the `LNode`/`LEdge` types, `Bucket`.
  - `LNode` now only needs `Id, X, Y` for geometry (Discipline/Tier/Cost no longer used here).
- **KEEP** `BuildLaneRoutes` only if you still want a `routing=lanes` option; otherwise delete it too.
- **ADD** `RouteOrthoLate` (endpoint-based; reuses `Chamfer`/`CORNER_R`/`CORNER_SEGS`):
```csharp
// ortho-late: a single riser just LEFT of the target, so edges converge "into the node" (RP-1 look).
internal static List<Vector2> RouteOrthoLate(LNode from, LNode to, float tF, float tT, float nodeW, float nodeH)
{
    Vector2 p = new Vector2(from.X + nodeW, from.Y + tF * nodeH);   // source RIGHT anchor (fan slot tF)
    Vector2 c = new Vector2(to.X,          to.Y   + tT * nodeH);    // target LEFT  anchor (fan slot tT)
    if (Mathf.Abs(p.y - c.y) < 0.5f) return new List<Vector2> { p, c };
    float rx = c.x - Mathf.Clamp((c.x - p.x) * 0.3f, 18f, 60f);
    Vector2 k1 = new Vector2(rx, p.y), k2 = new Vector2(rx, c.y);
    var outp = new List<Vector2> { p };
    outp.AddRange(Chamfer(p, k1, k2, CORNER_R, CORNER_SEGS));
    outp.AddRange(Chamfer(k1, k2, c, CORNER_R, CORNER_SEGS));
    outp.Add(c);
    return outp;
}
```

### B2. `AxeTreeRender.cs` — `OnTreeSpawn` becomes routing-only

**DELETE** from `OnTreeSpawn`: the stock-envelope read, the `LayoutSugiyama`/`LayoutBands` call, the whole
fit/flip block (`ax/bx/ay/by`, the waypoint transform), and the `SetPos` loop (+ the `PosField.SetValue`
path — positions now come from cfg). The content-height grow (`content.sizeDelta`) was compensating for the
re-layout exceeding the stock scroll area; with positions baked, KSP sizes its scroll content to the cfg
tree — **remove it, but verify the top row is reachable** (if clipped, keep a minimal grow).

**KEEP**: the two Harmony patches (`GetVectorArray` prefix, `UpdateGraphics` postfix), all cosmetics
(`PaintTile`/`StateRing`/`StateTint`/discipline colours/legend/hover). The body reduces to:
```csharp
private void OnTreeSpawn(RDTechTree tree)
{
    ready = false; Routes.Clear();
    try
    {
        AxeTreeMeta.EnsureLoaded();
        string routing = AxeTreeMeta.Render.Routing;
        if (routing == "stock") return;                       // edges = stock; positions already from cfg
        RDController ctrl = RDController.Instance;
        if (ctrl == null || ctrl.nodes == null || ctrl.nodes.Count == 0 || PosField == null) return;

        // model from LIVE (cfg-baked) positions — NO layout, NO reposition
        var byId = new Dictionary<string, AxeTreeLayout.LNode>();
        foreach (RDNode rd in ctrl.nodes)
        {
            string id = rd?.tech?.techID;
            if (string.IsNullOrEmpty(id) || byId.ContainsKey(id)) continue;
            Vector3 sp = (Vector3)PosField.GetValue(rd);
            byId[id] = new AxeTreeLayout.LNode { Id = id, X = sp.x, Y = sp.y };
        }
        var edges = new List<AxeTreeLayout.LEdge>();
        var seen = new HashSet<string>();
        foreach (RDNode rd in ctrl.nodes)
        {
            string to = rd?.tech?.techID;
            if (string.IsNullOrEmpty(to) || !byId.ContainsKey(to) || rd.parents == null) continue;
            foreach (RDNode.Parent par in rd.parents)
            {
                string from = par?.parent?.node?.tech?.techID;
                if (!string.IsNullOrEmpty(from) && byId.ContainsKey(from) && seen.Add(from + ">" + to))
                    edges.Add(new AxeTreeLayout.LEdge { From = from, To = to });
            }
        }

        AxeTreeLayout.ComputeSlots(edges, byId, AxeTreeMeta.Render.Fan);
        float nh = -NODE_H;   // fan spreads toward smaller y (KSP y-up); matches the old ay<0 sign — verify
        foreach (AxeTreeLayout.LEdge e in edges)
        {
            if (!byId.TryGetValue(e.From, out var pf) || !byId.TryGetValue(e.To, out var pt)) continue;
            if (routing == "ortho-late")
                Routes[e.From + ">" + e.To] = AxeTreeLayout.RouteOrthoLate(pf, pt, e.TF, e.TT, NODE_W, nh);
            // else if (routing == "lanes") -> BuildLaneRoutes path, if kept
        }
        ready = true;
        Debug.Log($"[AXE] render-port: {byId.Count} nodes, {Routes.Count} edges routed (routing={routing})");
    }
    catch (Exception e) { Debug.LogError("[AXE] render-port OnTreeSpawn failed: " + e); ready = false; }
}
```
`GetVectorArray_Prefix` is unchanged except the gate: `if (!ready || AxeTreeMeta.Render.Routing == "stock") return true;`
(the per-edge `Routes` lookup already falls back to the stock elbow when an edge has no route). The
`RDNodeRoot.TransformPoint(local→world)` step stays — cfg `pos` **is** RDNodeRoot-local space (verified:
`RDNodeRoot` is `scrollRect.content`, and `pos` → `localPosition`).

### B3. Config (`AxeTreeMeta.cs` + `RenderSettings.cfg`)
The `layout` key no longer drives the plugin (positions come from cfg). Add `routing`, drop the layout
role:
```csharp
// Settings: add   public string Routing;   default "ortho-late"
Render.Routing = (r.GetValue("routing") ?? "ortho-late").Trim().ToLowerInvariant();
```
`RenderSettings.cfg`:
```
//   routing = ortho-late | lanes | stock     converging elbow (default) / lane-packed (if kept) / stock elbow
//   (node LAYOUT is baked into AxeTechTree.cfg by tools/build_tree.py — not a runtime setting)
RPAXE_RENDER
{
	routing   = ortho-late
	fan       = true
	lanePitch = 1        // only if routing = lanes is kept
	discColor = true
	legend    = true
	hover     = true
}
```
(`layout`/`laneRouting` keys become inert; leave the parse for back-compat or remove.)

---

## Build & verify
```
python tools/build_tree.py         # re-emit AxeTechTree.cfg (BK pos) + tree-data.js
dotnet build Source/AXE/AXE.csproj -c Release
```
1. **Prototype** — open `tree/render/prototype/index.html`, set **Layout = Compiler**: it should now match
   **Sugiyama + BK** (straight horizontal runs). That confirms Part A before touching the game.
2. **In-game** (or `-axe-autotest`): tree is right-side-up (discipline order top→bottom — **verify #1**, the
   `emit_cfg` flip); long chains are straight; every edge risers just left of its target and converges in.
3. **Fan sign** — if endpoints spread the wrong way off the node side, flip `nh` to `+NODE_H`.
4. **Fallbacks** — `routing = stock` reverts edges to stock elbows (positions still BK from cfg); no
   `[AXE]` NREs in `KSP.log`. Top row reachable by scrolling (no clip).

## Net
- ~400 lines of C# layout deleted; BK lives **once**, in the compiler.
- Positions baked into cfg (their native home); runtime does only the edge draw it can't avoid.
- Prototype **Compiler** mode = shipped layout, so the HTML sandbox is now a faithful preview.

## Optional future (HTML-only today)
`routing = bezier | bundle | octilinear` — port `routeBezier`/`routeBundle`/`routeOctilinear` the same way
(pure per-edge fns returning a flat point list). `layout = sugiyama-disc` — ground-truthed as too
cross-linked for RP-AXE; skip. See `tree/render/prototype/ROUTING-VARIANTS.md`.
