# Tech-tree line/edge routing — variants to evaluate

**Status (2026-07-02):** six routing variants are wired into the prototype behind a
**Routing** dropdown (top toolbar) + `?routing=` URL param. Pick a winner interactively,
then (if it isn't `lanes`) port it to the in-game C# renderer. This doc is the handoff.

## How to try them

Open `tree/render/prototype/index.html` and use the **Routing** dropdown, or load a URL:

```
index.html?routing=lanes                 # current default (orthogonal, gutter-packed)
index.html?routing=lanes&lanePitch=13    # same, but parallel lanes spread apart (traceable)
index.html?routing=ortho-mid
index.html?routing=ortho-late
index.html?routing=polyline
index.html?routing=spline
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
| `direct`     | none (baseline) | one straight line source→target, ignores dummies. | sanity baseline only — crosses nodes/edges freely; not a real candidate. |

## Ground-truthed assessment (from headless shots, `scratchpad/shots/`)

At the full-tree zoom on the current 65-node slice:

- **`lanes` @ 1px** (current default) reads clean where gutters are sparse but **bundles into an
  untraceable bus** in the root fan-out and the Systems-Integration block. Good "tidy" look,
  bad if you want to follow one prerequisite edge.
- **`lanes` @ 13px** fixes traceability (parallel tracks separate) at the cost of width/noise.
- **`spline`** is the most readable — every edge is a distinct smooth curve, the fan-out from the
  four roots is legible at a glance. Least KSP-native, though.
- **`polyline`** ≈ spline for legibility with less "organic" feel; sharp tier bends.
- **`ortho-late`** is the best *orthogonal* option for KSP feel — converges into nodes like stock.
- **`ortho-mid`** and **`direct`** are the weakest here (mid-S cuts across columns; direct crosses).

## Recommendation

Two honest finalists depending on the goal:

1. **If KSP-native aesthetic wins** → `ortho-late` (converging elbows) or `lanes` with a **larger
   default pitch** (~8–13px, not 1px) so lineage stays traceable. The 1px default currently
   optimises "tidy" over "traceable" — reconsider it given the highlight-lineage feature.
2. **If readability wins** → `spline`. It's objectively the easiest to follow and is what
   dagre/Graphviz-dot do; the only cost is it looks like an org-chart, not a tech tree.

My lean: ship **`ortho-late`** as the KSP default (keeps the R&D scene feeling native) and keep
`spline` as a toggle for people who just want to read dependencies. But this is a taste call —
that's why they're all live now.

## Porting the winner to KSP (C#)

Only `lanes` is ported (`AxeTreeLayout.BuildLaneRoutes`). The others are **easier** — each is a
pure per-edge function of `e.Waypoints` (the dummy chain, already produced by `LayoutSugiyama`)
plus the fan slots (`TF`/`TT`) and node anchors. To port a non-lane winner:

- add the routing function to `Source/AXE/RnD/AxeTreeLayout.cs` (mirror the JS in `renderer.js`:
  `pathThroughDummies` / `catmullRom` / `routeOrthoLate` / `routeEdge`),
- select it in `AxeTreeRender.cs` where it currently calls `BuildLaneRoutes` (guard by a new
  `routing` field on `RPAXE_RENDER` in `RenderSettings.cfg`),
- the draw/arrow hook already consumes a flat point list, so nothing else changes.

## Files

- `renderer.js` — `edgeGeom()` dispatcher + `pathThroughDummies` / `catmullRom` / `routeOrthoLate`;
  `opt.routing`; buildGeometry only runs `buildLaneRoutes()` for `lanes`.
- `index.html` — the **Routing** `<select id="s_route">` (replaced the old Lane-routing checkbox).
- Shots: `scratchpad/shots/*.png` + `routing-variants-montage.png` (session scratch, not committed).
