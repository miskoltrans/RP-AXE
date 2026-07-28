# In-game R&D render port — plan / handoff

> **STATUS: IMPLEMENTED** (branch `restart`). Ported into `Source/AXE/RnD/`:
> `AxeTreeMeta.cs` (loads `RPAXE_TREEMETA` + `RPAXE_RENDER`), `AxeTreeLayout.cs` (KSP-free port of
> layoutBands + computeSlots + buildLaneRoutes + chamfer), `AxeTreeRender.cs` (reposition via
> `RDTechTree.OnTechTreeSpawn` + a Harmony prefix on `RDNode.GetVectorArray`). Config in
> `GameData/RP-AXE/RenderSettings.cfg` (`layout`/`laneRouting`/`fan`/`lanePitch`). In-game smoke-tested via
> `-axe-autotest`. The notes below are the original design/handoff, kept for reference.
>
> **NEXT:** [RENDER-PORT-ORTHO-BK.md](RENDER-PORT-ORTHO-BK.md) — ship the prototype's chosen look
> (routing = **ortho-late** + layout = **sugiyama-bk**). Revised approach: **bake node placement offline**
> (Brandes–Köpf into `build_tree.py`, positions already flow to `AxeTechTree.cfg`) and **DELETE the runtime
> re-layout**; the C# plugin keeps only ortho-late edge routing + cosmetics. Paste-ready Python + C#.

Port the HTML rendering prototype into the **KSP R&D scene** via the AXE Harmony plugin,
**config-toggleable**. This is the next big task (written before a context clear).

## Goal
In-game R&D tree, enhance-stock (no scene replacement), driven by a config:
- **Layout override**: `bands` (discipline lanes) · `sugiyama` (layered) · `stock` (off, keep cfg positions).
- **Lane routing**: on/off (tight lane-routed orthogonal edges vs stock elbow).
- Fan endpoints: on/off. (Square tiles already = stock; icons already stock.)
- Default (chosen in prototype): **bands + compact + lane + fan**.

## Reference implementation — PORT THESE FROM THE PROTOTYPE
`RP-AXE/tree/render/prototype/renderer.js` (JS → C#). Read its header ledger for the portability rules.
- `computeLayout()` → `layoutBands()` / `layoutSugiyama()` — node placement.
  - bands: each discipline = a horizontal band (by `disciplines.yaml` `order`); x = tier; stack within (disc,tier) cell; stack gap sized to tile height so tiles never overlap; band height grows with mean cost when cost-spread on.
  - sugiyama: dummy nodes on >1-tier edges → median-sweep crossing-min → PAV/isotonic coordinate assignment; waypoints through the dummy chain.
- `buildLaneRoutes()` — per-gutter lane assignment (interval-graph colouring) + **lane-order by barycentre** + **horizontal-track** separation + **tight fixed pitch (~13px, centred, clamped)** + rounded corners (`roundPolyline`/`chamfer`, port of stock `RDNode.chamferCorner`).
- `routeEdge()` — the stock-elbow (kspStock) alternative when lane routing is off.
- Endpoint fan: distribute incident edges along a node side (`computeSlots`).

## KSP hooks (Harmony, enhance-stock)
Model after the working `Source/AXE/RnD/AxeTreeHighlight.cs` (Harmony postfix, applied at MainMenu once).
- **Node positions**: `RDController.Instance.nodes` (`List<RDNode>`); each `RDNode` has `pos`/`transform.localPosition`. Reposition after the tree spawns (patch `RDTechTree` spawn or `RDController` Start/Setup), then trigger arrow (re)draw.
- **Arrow routing**: `RDNode.GetVectorArray(Parent)` builds each edge's flat point list; `RDNode.DrawArrow` creates the Vectrosity `VectorLine`s; endpoints via `RDNode.GetPosition(anchor,…)`. To lane-route, Harmony-replace `GetVectorArray` (or post-process in `DrawArrow`) to emit the lane-routed points. Colour = `Color32`, uniform width, build once (don't vary width → mesh rebuild).
- Re-decompile if needed: `~/.dotnet/tools/ilspycmd.exe "<KSP>/KSP_x64_Data/Managed/Assembly-CSharp.dll" -p -o <out>` then read `KSP.UI.Screens/RDNode.cs`, `RDNodePrefab.cs`, `RDController.cs`, `UIGridArea.cs`. (Vectrosity is in `Assembly-CSharp-firstpass.dll`.)

## OPEN ISSUE — discipline + tier per node in-game
The game `RDNode` has **no discipline/tier field** (only `icon` + `pos`). Bands need discipline; both need tier.
- **Recommended**: have `build_tree.py` (layout agent's file — coordinate) emit a plugin-readable mapping `nodeID → {discipline, tier}` into GameData (e.g. a `RPAXE_TREEMETA` ConfigNode), which the plugin loads via `GameDatabase.Instance.GetConfigNodes`.
- Fallback: derive tier from `pos.x` (`tier = round((x-MARGIN_X)/TIERW)`), discipline from icon (unreliable — icons are shared). Prefer the explicit mapping.

## Config design
A settings ConfigNode, e.g. `GameData/RP-AXE/RenderSettings.cfg`:
```
RPAXE_RENDER { layout = bands   // bands | sugiyama | stock
               laneRouting = true
               fan = true }
```
Plugin reads it on R&D scene load (`GameDatabase.GetConfigNodes("RPAXE_RENDER")`), MM-patchable. Also expose an in-game toggle later if wanted.

## Build & verify
- `dotnet build Source/AXE/AXE.csproj -c Release` (KSPRoot defaults to `Instance`; refs Assembly-CSharp[.firstpass], UnityEngine[.UI/.CoreModule], `GameData/000_Harmony/0Harmony.dll`). Output auto-copies to `GameData/RP-AXE/Plugins/AXE.dll` (**gitignored** — commit source only).
- In-game: launch KSP → R&D, or the `-axe-autotest` harness (`Source/AXE/AutoTest/AxeAutoTest.cs`, drives the R&D scene hands-free → look for `[AXE]` / `SUCCESS` in `KSP.log`) to confirm it loads + patches + spawns the tree without throwing. Visual pass: nodes in bands, lane-routed arrows.

## Risk note
Repositioning ALL nodes + rerouting is more invasive than the highlight patch (which only recolours). It overrides stock/RP-0 tree positions. Test carefully; keep `layout = stock` as a safe fallback.

## Status at handoff *(historical — superseded by the STATUS banner at the top of this file)*
- Prototype: complete, mainline (then branch `restart`, since renamed `main`), commits through `460f807`. Full toggle set + prototype-owned layout (bands/sugiyama) + tight lane routing.
- Plugin: `AxeTreeHighlight.cs` (lineage highlight) compiles; not yet in-game tested.
- ~~This render port is the next piece.~~ **Done** — the port shipped, and the follow-on
  [RENDER-PORT-ORTHO-BK.md](RENDER-PORT-ORTHO-BK.md) (bake layout offline, render only edges) shipped too.
