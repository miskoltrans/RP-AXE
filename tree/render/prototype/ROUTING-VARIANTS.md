# Tech-tree line/edge routing — variants to evaluate

**Status (2026-07-02):** **nine** routing variants are wired into the prototype behind a
**Routing** dropdown (top toolbar) + `?routing=` URL param. Pick a winner interactively,
then (if it isn't `lanes`) port it to the in-game C# renderer. This doc is the handoff.
The three ★ variants (`bezier`, `bundle`, `octilinear`) were added this session as
"new and better" candidates — see [The new variants](#the-new-variants-).

## How to try them

Open `tree/render/prototype/index.html` and use the **Routing** dropdown, or load a URL:

```
index.html?routing=lanes                 # current default (orthogonal, gutter-packed)
index.html?routing=lanes&lanePitch=13    # same, but parallel lanes spread apart (traceable)
index.html?routing=ortho-mid
index.html?routing=ortho-late
index.html?routing=polyline
index.html?routing=spline
index.html?routing=bezier                # ★ new — horizontal-tangent cubic (modern DAG flow)
index.html?routing=bundle                # ★ new — edge bundling (declutters dense fan-in/out)
index.html?routing=bundle&bundle=0.4     #   same, weaker bundling (0=bezier … 1=fully merged)
index.html?routing=octilinear            # ★ new — metro/subway 45° routing
index.html?routing=direct
```

Everything else stays live-tunable: **Layout** (sugiyama/bands/compiler), **Spacing X/Y**,
**Lane** pitch (only affects `lanes`), **Fan endpoints**, **Arrowheads**, **Highlight lineage**.
Best evaluated by zooming into the two dense regions: the T0→T1 root fan-out and the
Systems-Integration block (mid-left), where routing quality actually shows.

## The variants

Each edge is still **one flat polyline** in world space (spline is tessellated to points),
so all of these remain portable to a single KSP Vectrosity `VectorLine` per edge.

| `routing`    | family | what it does | trade-off |
|--------------|--------|--------------|-----------|
| `lanes`      | orthogonal | vertical legs packed into per-gutter lanes (interval-colour + barycentre order + track separation + rounded corners). `lanePitch` px between lanes; **1px ≈ bundled into a bus**, larger = traceable parallel tracks. | KSP-native look; but at 1px parallel edges overlap and can't be told apart; busy gutters get noisy. This is the only one already ported to C#. |
| `ortho-mid`  | orthogonal | stock KSP S-elbow: one vertical riser at the **mid-X** of the span, ignores intermediate tiers (`routeEdge`). | fewest bends of the orthogonal set; long multi-tier edges can cut across node columns. |
| `ortho-late` | orthogonal | elbow with the riser pushed **next to the target** — edges run horizontally then turn in, converging "into the node" (closest to real KSP/RP-1). | clean convergence, matches KSP convention; long horizontal runs can overlap on shared rows. |
| `polyline`   | polyline (fam. #1) | straight diagonal segments through the layout's dummy waypoints (classic Sugiyama). | each edge individually traceable, minimal ink; diagonals are un-KSP-like; sharp bends at tiers. |
| `spline`     | spline (fam. #1) | smooth Catmull-Rom curve through the same dummy waypoints (dagre / d3-dag look). | most readable per-edge, softest; least KSP-native; curve can stray from the grid. |
| `bezier` ★   | spline (endpoint) | horizontal-tangent cubic Bézier, **endpoint-based** (React-Flow "bumpX"). Leaves the source rightward, arrives the target leftward — one clean predictable S, no dummy-point wiggle. | the readability of `spline` but tidier and more uniform (never strays off-grid, always enters/leaves horizontally = reads as flow). Ignores dummies, so a very long edge can pass near a node — rare in this L→R layout. |
| `bundle` ★   | spline (bundled) | edge **bundling**: every edge is pulled toward its source's out-hub (mean-y of its targets) and its target's in-hub (mean-y of its sources) by strength β (`bundle=` / the **Bundle β** slider). Edges to nearby nodes share a curved trunk and peel off at the ends. | biggest declutter for the dense root fan-out / Systems-Integration block — a hairball becomes a few legible bundles. High β (≈0.85) is tidiest but the shared trunk is less individually-traceable (curved cousin of the `lanes` bus); β≈0.35–0.5 keeps edges separable while still calming the mess. |
| `octilinear` ★ | octilinear | metro/subway map: horizontal run → one **45° diagonal** to change rows → horizontal into the target (corners rounded via the stock chamfer). Falls back to `ortho-late` when the span is too short for a 45° leg. | a crisp, distinctive "circuit board / transit map" aesthetic that still feels engineered/KSP-adjacent; like `ortho-late`, long horizontal runs can share rows and overlap. |
| `direct`     | none (baseline) | one straight line source→target, ignores dummies. | sanity baseline only — crosses nodes/edges freely; not a real candidate. |

## The new variants ★

Added this session (2026-07-02) as genuinely-better candidates than the original six. All three are
still **one flat polyline per edge** (Bézier/bundle tessellated to ~18–20 points), so they remain
portable to a single KSP Vectrosity `VectorLine` — no change to the portability envelope.

- **`bezier`** — the standout for legibility. Horizontal-tangent cubic (P0=source-right, P3=target-left,
  control points reach `BEZ_K=0.5·dx` straight out horizontally). Reads like a modern flow-chart /
  React-Flow diagram: every edge a distinct, uniform S that *always* enters and leaves horizontally.
  It's `spline`'s readability without the Catmull-Rom wiggle and without needing dummy waypoints.
- **`bundle`** — the declutter play. Pulls each edge toward its source-out-hub and target-in-hub by β.
  At β≈0.85 the four-root fan-out visibly necks into a trunk before spreading — the busiest region of
  the tree calms right down. Trade β for traceability with the **Bundle β** slider (`bundle=`); mid β
  (~0.4) is the sweet spot where it's calmer than `bezier` but you can still follow one line.
- **`octilinear`** — the aesthetic play. Metro-map horizontal→45°→horizontal. Crisp and distinctive;
  shares `ortho-late`'s only weakness (co-row horizontal overlaps on long edges).

## Ground-truthed assessment (from headless shots, `scratchpad/shots/`)

At the full-tree zoom on the current 68-node slice:

- **`lanes` @ 1px** (current default) reads clean where gutters are sparse but **bundles into an
  untraceable bus** in the root fan-out and the Systems-Integration block. Good "tidy" look,
  bad if you want to follow one prerequisite edge.
- **`lanes` @ 13px** fixes traceability (parallel tracks separate) at the cost of width/noise.
- **`bezier` ★** is the best all-round: as readable as `spline`, tidier and more uniform, and the
  horizontal in/out tangents make it feel like an intentional flow rather than an org-chart.
- **`bundle` ★** wins specifically in the two dense regions; elsewhere it ≈ `bezier`. Best paired with
  a mid β so the trunk stays separable.
- **`spline`** is very readable — every edge a distinct smooth curve — but wigglier than `bezier` and
  can stray off-grid.
- **`polyline`** ≈ spline for legibility with less "organic" feel; sharp tier bends.
- **`octilinear` ★** and **`ortho-late`** are the best *orthogonal/engineered* options for KSP feel —
  clean, converge into nodes like stock; both can overlap on shared rows for long edges.
- **`ortho-mid`** and **`direct`** are the weakest here (mid-S cuts across columns; direct crosses).

## Recommendation (updated)

The new `bezier` reshuffles the finalists. Two honest options depending on the goal:

1. **If readability wins** → **`bezier`** (new default lean). Objectively the easiest to follow, tidy
   and uniform, and — unlike the old `spline` pick — it looks *engineered* (horizontal flow) rather
   than like an org-chart. Add **`bundle`** (mid β) as a "declutter" toggle for anyone overwhelmed by
   the dense regions; it degrades gracefully to `bezier` at β=0.
2. **If KSP-native aesthetic wins** → **`ortho-late`** (converging elbows) or **`octilinear`** (metro
   45°) for a crisper engineered look; or `lanes` with a **larger default pitch** (~8–13px, not 1px)
   so lineage stays traceable. The 1px default optimises "tidy" over "traceable" — reconsider it given
   the highlight-lineage feature.

My lean: ship **`bezier`** as the default (best readability, still one clean line per edge) with
**`ortho-late`** available for players who want the native R&D feel and **`bundle`** as a declutter
toggle. But this stays a taste call — that's why all nine are live.

## Porting the winner to KSP (C#)

Only `lanes` is ported (`AxeTreeLayout.BuildLaneRoutes`). The others are **easier** — each is a
pure per-edge function of node anchors + the fan slots (`TF`/`TT`), and (for the dummy-routed ones)
`e.Waypoints`. To port a non-lane winner:

- add the routing function to `Source/AXE/RnD/AxeTreeLayout.cs` (mirror the JS in `renderer.js`):
  - `bezier` → `routeBezier` + `cubicBezier` (endpoint-based, **needs no dummy chain** — simplest port),
  - `bundle` → `routeBundle` + `buildBundleHubs` (one pre-pass to compute per-node mean-target/source y),
  - `octilinear` → `routeOctilinear` (+ reuse `roundPolyline`/`chamfer`),
  - or the originals: `pathThroughDummies` / `catmullRom` / `routeOrthoLate` / `routeEdge`.
- select it in `AxeTreeRender.cs` where it currently calls `BuildLaneRoutes` (guard by a new
  `routing` field on `RPAXE_RENDER` in `RenderSettings.cfg`; `bundle` also reads a `bundleBeta` float),
- the draw/arrow hook already consumes a flat point list, so nothing else changes. `bezier` is the
  cleanest port of the lot (no dummy dependency, no lane-packing pass).

## Files

- `renderer.js` — `edgeGeom()` dispatcher + per-variant fns: `routeBezier`/`cubicBezier`,
  `routeBundle`/`buildBundleHubs`, `routeOctilinear`, plus the originals `pathThroughDummies` /
  `catmullRom` / `routeOrthoLate` / `routeEdge`. `opt.routing` + `opt.bundleBeta`; `buildGeometry`
  runs `buildLaneRoutes()` only for `lanes` and `buildBundleHubs()` only for `bundle`.
- `index.html` — the **Routing** `<select id="s_route">` (nine options) + the **Bundle β** slider
  (`#r_bundle`, only affects `bundle`).
- Shots: `scratchpad/shots/*.png` (session scratch, not committed): `bezier.png`, `bundle85.png`,
  `bundle40.png`, `octilinear.png` + `ref_*.png` baselines.
