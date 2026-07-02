# In-game render port — ortho-late routing + Brandes–Köpf layout (handoff)

> **Follow-up to [RENDER-PORT.md](RENDER-PORT.md)** (that port is DONE). This adds the two variants the
> prototype settled on as the shipping look and makes them the in-game default:
> **routing = ortho-late** ("elbow into target", converging edges) + **layout = sugiyama-bk**
> (Brandes–Köpf coordinate assignment ⇒ straight edge runs). Both are already the prototype default
> (`tree/render/prototype/renderer.js`, `opt.routing='ortho-late'`, `opt.layout='sugiyama-bk'`).
>
> **Scope:** port these two only. Bundle/bezier/octilinear routing and the discipline-grouped layout stay
> HTML-only for now (noted at the end as optional future work).

## What "done" looks like

Open R&D in-game with the default `RenderSettings.cfg`: nodes are placed by BK (long prerequisite chains
run as **dead-straight horizontal lines**, not gentle diagonals) and edges are **converging orthogonal
elbows into the target node** (a riser just left of each target), matching the prototype's default view.
`layout = stock` still disables everything; `routing = lanes` still gives the old lane-packed look.

## Files & anchors (verified against current source)

| file | what changes |
|------|--------------|
| `Source/AXE/RnD/AxeTreeLayout.cs` | add BK coordinate assignment to `LayoutSugiyama` (new `useBK` param + `segPrev` build + 5 `Bk*` methods); add `RouteOrthoLate` |
| `Source/AXE/RnD/AxeTreeRender.cs`  | accept `sugiyama-bk` layout (guard ~line 94 + dispatch ~line 140); replace the `LaneRouting` edge block (~line 184) with a routing dispatch; loosen the `GetVectorArray_Prefix` gate (~line 259) |
| `Source/AXE/RnD/AxeTreeMeta.cs`    | add `Routing` to `Settings`; parse `routing`; accept `sugiyama-bk` |
| `GameData/RP-AXE/RenderSettings.cfg` | `layout = sugiyama-bk`, add `routing = ortho-late`, update header comments |

Everything stays inside the existing enhance-stock envelope: **one flat polyline per edge**, returned by
the existing `GetVectorArray` Harmony prefix; colour/width untouched. No new hooks.

---

## 1. `AxeTreeLayout.cs` — Brandes–Köpf coordinates

### 1a. Build `segPrev` in `LayoutSugiyama`

BK needs the *proper-layered* adjacency (adjacent-rank segments only), NOT the `prev`/`nxt` maps (which
include the non-forward `pt >= ct` edges). Add a `segPrev` map next to `prev`/`nxt`, populated **only** in
the forward-chain branch:

```csharp
// beside: var prev = ...; var nxt = ...;
var segPrev = new Dictionary<string, List<string>>();          // adjacent-rank predecessors (BK only)
void AddSeg(string a, string b) { Bucket(segPrev, b).Add(a); } // a (upper) -> b (lower)
```
In the chain loop, in the **forward** branch (the `else` where dummies are inserted), alongside
`AddAdj(chain[i], chain[i + 1])` add:
```csharp
for (int i = 0; i < chain.Count - 1; i++) { AddAdj(chain[i], chain[i + 1]); AddSeg(chain[i], chain[i + 1]); }
```
Do **not** call `AddSeg` in the `pt >= ct` (non-forward) branch — those aren't adjacent-rank segments.

### 1b. Branch the coordinate assignment

Change the signature (add `bool useBK` at the end):
```csharp
internal static void LayoutSugiyama(List<LNode> nodes, List<LEdge> edges, Dictionary<string, LNode> byId,
    Dictionary<string, int> discOrder, float colw, float spacingY, float marginX, float marginY,
    bool diffspread, bool useBK)
```
The existing coordinate block builds a `Dictionary<string,double> y` via PAV. Wrap it so BK is an
alternative producing the same `y` (the `gap` lambda is already defined just above — reuse it as BK's
separation function):
```csharp
Dictionary<string, double> y;
if (useBK)
{
    y = BkCoords(order, layers, segPrev, gap, IsD);   // block alignment ⇒ straight edges
}
else
{
    // ---- existing PAV loop, UNCHANGED ----  (var pav = ...; y = new Dictionary...; for it<30 { ... })
}
// ---- everything below (miny / Y / n.X,n.Y / waypoints) stays as-is ----
```
`IsD` and `gap` already exist in the method. Nothing downstream changes — BK writes the same `y` map the
waypoint emitter reads.

### 1c. The BK methods (paste as private static members of `AxeTreeLayout`)

Faithful port of `renderer.js` `bkType1/bkAlign/bkCompact/bkRun/bkCoords` — Brandes & Köpf 2002, 2-run
(down-left + within-layer-mirrored down-right) averaged, with a final monotone sweep guaranteeing
separation. (`string` compares by value in C#, so `align[v] != v` and `sink[v] == sink[ru]` are correct.)

```csharp
// ---- Brandes–Köpf coordinate assignment (port of renderer.js bkCoords). Aligns each vertex to its
// median predecessor into vertical BLOCKS, then compacts blocks under a min-gap -> aligned edges become
// straight runs (long dummy chains especially). 2 runs (L/R) averaged; monotone sweep guarantees sep.
private static HashSet<string> BkType1(List<List<string>> L, Dictionary<string, List<string>> predOf,
    Dictionary<string, int> ord, Func<string, bool> isd)
{
    var conf = new HashSet<string>();
    for (int k = 0; k < L.Count - 1; k++)
    {
        var upper = L[k]; var lower = L[k + 1];
        int k0 = 0, scan = 0;
        for (int l1 = 0; l1 < lower.Count; l1++)
        {
            string v = lower[l1];
            int innerPos = -1;
            if (isd(v) && predOf.TryGetValue(v, out var pv))
                foreach (var u in pv) if (isd(u) && ord[u] > innerPos) innerPos = ord[u];
            if (l1 == lower.Count - 1 || innerPos >= 0)
            {
                int k1 = innerPos >= 0 ? innerPos : upper.Count - 1;
                for (; scan <= l1; scan++)
                {
                    string w = lower[scan];
                    if (predOf.TryGetValue(w, out var pw))
                        foreach (var u in pw)
                            if ((ord[u] < k0 || ord[u] > k1) && !(isd(u) && isd(w))) conf.Add(u + " " + w);
                }
                k0 = k1;
            }
        }
    }
    return conf;
}

private static void BkAlign(List<List<string>> L, Dictionary<string, List<string>> predOf,
    Dictionary<string, int> ord, HashSet<string> conf,
    Dictionary<string, string> root, Dictionary<string, string> align)
{
    foreach (var layer in L) foreach (var v in layer) { root[v] = v; align[v] = v; }
    foreach (var layer in L)
    {
        int r = -1;
        foreach (var v in layer)
        {
            if (!predOf.TryGetValue(v, out var ws) || ws.Count == 0) continue;
            double mp = (ws.Count - 1) / 2.0;
            for (int i = (int)Math.Floor(mp); i <= (int)Math.Ceiling(mp); i++)
            {
                if (align[v] != v) break;
                string w = ws[i];
                if (r < ord[w] && !(conf.Contains(w + " " + v) || conf.Contains(v + " " + w)))
                { align[w] = v; root[v] = root[w]; align[v] = root[w]; r = ord[w]; }
            }
        }
    }
}

private static Dictionary<string, double> BkCompact(List<List<string>> L,
    Dictionary<string, string> root, Dictionary<string, string> align, Func<string, string, double> sep)
{
    var above = new Dictionary<string, string>();
    foreach (var layer in L) for (int i = 0; i < layer.Count; i++) above[layer[i]] = i > 0 ? layer[i - 1] : null;
    var X = new Dictionary<string, double>();
    var sink = new Dictionary<string, string>();
    var shift = new Dictionary<string, double>();
    foreach (var layer in L) foreach (var v in layer) { sink[v] = v; shift[v] = double.PositiveInfinity; }
    void Place(string v)
    {
        if (X.ContainsKey(v)) return;
        X[v] = 0; string w = v;
        do
        {
            string u = above[w];
            if (u != null)
            {
                string ru = root[u]; Place(ru);
                if (sink[v] == v) sink[v] = sink[ru];
                double d = sep(u, w);
                if (sink[v] == sink[ru]) X[v] = Math.Max(X[v], X[ru] + d);
                else shift[sink[ru]] = Math.Min(shift[sink[ru]], X[v] - X[ru] - d);
            }
            w = align[w];
        } while (w != v);
    }
    foreach (var layer in L) foreach (var v in layer) if (root[v] == v) Place(v);
    var xs = new Dictionary<string, double>();
    foreach (var layer in L) foreach (var v in layer)
    {
        xs[v] = X[root[v]];
        double s = shift[sink[root[v]]];
        if (!double.IsPositiveInfinity(s)) xs[v] += s;
    }
    return xs;
}

private static Dictionary<string, double> BkRun(List<List<string>> L,
    Dictionary<string, List<string>> segPrev, Func<string, string, double> sep, Func<string, bool> isd)
{
    var ord = new Dictionary<string, int>();
    foreach (var layer in L) for (int i = 0; i < layer.Count; i++) ord[layer[i]] = i;
    var predOf = new Dictionary<string, List<string>>();
    foreach (var layer in L) foreach (var v in layer)
    {
        var ps = segPrev.TryGetValue(v, out var sp) ? new List<string>(sp) : new List<string>();
        ps.Sort((a, b) => ord[a] - ord[b]);
        predOf[v] = ps;
    }
    var conf = BkType1(L, predOf, ord, isd);
    var root = new Dictionary<string, string>(); var align = new Dictionary<string, string>();
    BkAlign(L, predOf, ord, conf, root, align);
    return BkCompact(L, root, align, sep);
}

private static Dictionary<string, double> BkCoords(List<int> order, Dictionary<int, List<string>> layers,
    Dictionary<string, List<string>> segPrev, Func<string, string, double> sep, Func<string, bool> isd)
{
    var L = new List<List<string>>(); foreach (var t in order) L.Add(layers[t]);
    var cL = BkRun(L, segPrev, sep, isd);                                   // down-left
    var Lr = new List<List<string>>();
    foreach (var layer in L) { var rev = new List<string>(layer); rev.Reverse(); Lr.Add(rev); }
    var cRr = BkRun(Lr, segPrev, sep, isd);                                 // down-right (mirror)
    var cR = new Dictionary<string, double>(); foreach (var kv in cRr) cR[kv.Key] = -kv.Value;
    void Norm(Dictionary<string, double> m)
    {
        double mn = double.PositiveInfinity; foreach (var kv in m) if (kv.Value < mn) mn = kv.Value;
        var keys = new List<string>(m.Keys); foreach (var k in keys) m[k] -= mn;
    }
    Norm(cL); Norm(cR);
    var y = new Dictionary<string, double>();
    foreach (var layer in L) foreach (var v in layer) y[v] = (cL[v] + cR[v]) / 2.0;   // balance L/R bias
    foreach (var layer in L) for (int i = 1; i < layer.Count; i++)                    // guarantee separation
    {
        double need = y[layer[i - 1]] + sep(layer[i - 1], layer[i]);
        if (y[layer[i]] < need) y[layer[i]] = need;
    }
    return y;
}
```

### 1d. `RouteOrthoLate` (paste as an internal static method of `AxeTreeLayout`)

Endpoint-based (uses node anchors + fan slots, ignores waypoints — same as the prototype). Reuses the
existing `Chamfer`, `CORNER_R`, `CORNER_SEGS`. **`nodeH` is passed signed** (see §2) so the fan offset
follows the Y-flip, exactly like `BuildLaneRoutes`.

```csharp
// ---- ortho-late routing (port of renderer.js routeOrthoLate): a single riser just LEFT of the target,
// so edges converge "into the node" (stock/RP-1 look). Anchors: source RIGHT side, target LEFT side.
internal static List<Vector2> RouteOrthoLate(LNode from, LNode to, float tF, float tT, float nodeW, float nodeH)
{
    Vector2 p = new Vector2(from.X + nodeW, from.Y + tF * nodeH);   // source right anchor (fan slot tF)
    Vector2 c = new Vector2(to.X,          to.Y   + tT * nodeH);    // target left  anchor (fan slot tT)
    if (Mathf.Abs(p.y - c.y) < 0.5f) return new List<Vector2> { p, c };
    float rx = c.x - Mathf.Clamp((c.x - p.x) * 0.3f, 18f, 60f);     // riser just left of the target
    Vector2 k1 = new Vector2(rx, p.y), k2 = new Vector2(rx, c.y);
    var outp = new List<Vector2> { p };
    outp.AddRange(Chamfer(p, k1, k2, CORNER_R, CORNER_SEGS));
    outp.AddRange(Chamfer(k1, k2, c, CORNER_R, CORNER_SEGS));
    outp.Add(c);
    return outp;
}
```

---

## 2. `AxeTreeRender.cs` — wire layout + routing

**Guard (~line 94):** accept the new layout value.
```csharp
if (layoutMode != "bands" && layoutMode != "sugiyama" && layoutMode != "sugiyama-bk") return;
```

**Layout dispatch (~line 140):** pass `useBK`.
```csharp
if (layoutMode == "sugiyama" || layoutMode == "sugiyama-bk")
    AxeTreeLayout.LayoutSugiyama(lnodes, edges, byId, discOrder, AxeTreeMeta.TierWidth,
        SUG_SPACING_Y, AxeTreeMeta.MarginX, AxeTreeMeta.MarginY, false, layoutMode == "sugiyama-bk");
else
    AxeTreeLayout.LayoutBands(lnodes, edges, byId, discOrder, AxeTreeMeta.TierWidth,
        AxeTreeMeta.MarginX, AxeTreeMeta.MarginY, NODE_H, SPACING_F, false);
```

**Routing dispatch (~line 184):** replace the whole `if (AxeTreeMeta.Render.LaneRouting) { ... }` block.
Note `NODE_H * Mathf.Sign(ay)` — the signed node height so the fan follows the Y-flip (unchanged from lanes).
```csharp
string routing = AxeTreeMeta.Render.Routing;
if (routing == "lanes")
{
    AxeTreeLayout.ComputeSlots(edges, byId, AxeTreeMeta.Render.Fan);
    AxeTreeLayout.BuildLaneRoutes(lnodes, edges, NODE_W, NODE_H * Mathf.Sign(ay), AxeTreeMeta.Render.LanePitch);
    foreach (AxeTreeLayout.LEdge e in edges)
        if (e.LaneGeom != null) Routes[e.From + ">" + e.To] = e.LaneGeom;
}
else if (routing == "ortho-late")
{
    AxeTreeLayout.ComputeSlots(edges, byId, AxeTreeMeta.Render.Fan);
    float nh = NODE_H * Mathf.Sign(ay);
    foreach (AxeTreeLayout.LEdge e in edges)
    {
        if (!byId.TryGetValue(e.From, out var pf) || !byId.TryGetValue(e.To, out var pt)) continue;
        Routes[e.From + ">" + e.To] = AxeTreeLayout.RouteOrthoLate(pf, pt, e.TF, e.TT, NODE_W, nh);
    }
}
// else (routing == "stock"): leave Routes empty -> the prefix falls through to the stock elbow
```

**Prefix gate (~line 259):** was `if (!ready || !AxeTreeMeta.Render.LaneRouting) return true;`. The per-edge
`Routes` lookup already handles "no route → stock", so gate on the routing mode instead:
```csharp
if (!ready || AxeTreeMeta.Render.Routing == "stock") return true;
```

The debug log line (~205) referencing `Render.LaneRouting` can print `Render.Routing` instead (cosmetic).

---

## 3. `AxeTreeMeta.cs` — config

**`Settings` struct (~line 21):** add a `Routing` string.
```csharp
internal struct Settings { public string Layout; public string Routing; public bool LaneRouting;
    public bool Fan; public float LanePitch; public bool DiscColor; public bool Legend; public bool Hover; }
```
**Default initializer (~line 28):** `Routing = "ortho-late"`, `Layout = "sugiyama-bk"`.

**Parser (~line 89):** add, and keep `laneRouting` for back-compat (only consulted if `routing` is absent).
```csharp
string routing = r.GetValue("routing");
Render.Routing = string.IsNullOrEmpty(routing)
    ? (Render.LaneRouting ? "ortho-late" : "stock")   // no routing key: lanePitch/lane still honoured only if routing=lanes
    : routing.Trim().ToLowerInvariant();
```
(Parse `laneRouting` *before* this so the fallback sees it. `routing` present always wins.)
Accept `sugiyama-bk` wherever `Layout` is validated (the render guard in §2 is the real gate).

## 4. `GameData/RP-AXE/RenderSettings.cfg`

```
//   layout      = sugiyama-bk | sugiyama | bands | stock
//   routing     = ortho-late | lanes | stock   converging elbow into target (default) / lane-packed / stock elbow
//   lanePitch   = <px>        only when routing = lanes
RPAXE_RENDER
{
	layout      = sugiyama-bk
	routing     = ortho-late
	laneRouting = true      // legacy; ignored when `routing` is set
	fan         = true
	lanePitch   = 1
	discColor   = true
	legend      = true
	hover       = true
}
```

---

## Build & verify

```
dotnet build Source/AXE/AXE.csproj -c Release      # AXE.dll is gitignored; builds against the Instance
```
Then in-game (or via the `-axe-autotest` harness that drives the R&D scene — see [[ksp-scene-driving-api]]):
1. **Layout** — long prerequisite chains render as straight horizontal lines (BK). Compare `layout=sugiyama`
   (PAV, wavier) to confirm BK is active.
2. **Routing** — every edge makes ONE riser just left of its target and converges into the node's left side
   (not a mid-span S, not lane-packed).
3. **Fallbacks** — `routing = lanes` reproduces the old look; `routing = stock` and `layout = stock` each
   revert cleanly; no NREs in `KSP.log` (grep `[AXE]`).
4. **No overlaps** — BK's final monotone sweep guarantees separation; confirm no stacked nodes at any tier.

### Gotchas
- **Signed `nodeH`.** Pass `NODE_H * Mathf.Sign(ay)` to `RouteOrthoLate` (as lanes does) or the fan offsets
  go the wrong way under the Y-flip.
- **`segPrev`, not `prev`.** BK must use the adjacent-rank-only segments; feeding it `prev` (which includes
  non-forward edges) corrupts the type-1 conflict pass.
- **Riser clamp (18–60 px)** is in the fitted stock pos-space; fine as-is, but if targets feel cramped after
  the X-fit, widen to e.g. 24–80. Cosmetic only.
- **`string` semantics.** The BK port relies on C# `string` value-equality for `!=`/`==` on ids — correct as
  written; don't "optimize" to reference checks.

## Optional future work (HTML-only today)
- `routing = bezier | bundle | octilinear` — port `routeBezier`/`routeBundle`/`routeOctilinear` (+ a
  `bundleBeta` float) the same way; each is a pure per-edge function returning a flat point list.
- `layout = sugiyama-disc` — discipline-constrained ordering. Ground-truthed as **too cross-linked** for
  RP-AXE (long vertical cross-band edges); low priority. See `tree/render/prototype/ROUTING-VARIANTS.md`.
