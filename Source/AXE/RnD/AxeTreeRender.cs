using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using KSP.UI;
using KSP.UI.Screens;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace RPAxe.RnD
{
    /// <summary>
    /// In-game R&amp;D render port (enhance-stock, config-toggleable). Ports the HTML prototype's
    /// discipline-band layout + lane-routed arrows into the live R&amp;D scene via two hooks:
    ///   * RDTechTree.OnTechTreeSpawn (event, fires right after LoadTechTree fills RDController.nodes
    ///     and BEFORE the nodes' next-frame Setup): compute the bands layout from AxeTreeMeta and
    ///     overwrite each RDNode's private `pos` field, which Setup then applies (localPosition = pos)
    ///     and draws arrows against — no teardown/redraw races. Also precomputes the lane routes.
    ///   * Harmony prefix on RDNode.GetVectorArray(Parent): return the precomputed routed points
    ///     (world space) instead of the stock elbow, when a routing override (lanes / ortho-late) is on.
    /// Colour/width are left to stock (per the prototype ledger: never vary width -> Vectrosity rebuild).
    /// Everything is guarded + try/catch'd; layout=stock (or any failure) falls back to the stock tree.
    ///
    /// KSP's EventData does `evt.Target.GetType()` on subscribe and drops subscribers whose originator
    /// is null, so the handler MUST be an instance method on an object that survives the session — hence
    /// the DontDestroyOnLoad host below (a static handler NREs in EvtDelegate's ctor).
    ///
    /// Vertical convention: stock puts RDNode.pos.y at the node TOP with the body toward smaller y
    /// (Unity UI y-up); the prototype is y-down. FlipY() mirrors the prototype coords into KSP space,
    /// applied consistently to node positions AND route points so geometry stays connected.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, true)]
    public class AxeTreeRenderBootstrap : MonoBehaviour
    {
        private static bool created;
        private void Awake()
        {
            if (created) return;
            created = true;
            var go = new GameObject("RPAxe.AxeTreeRenderHost");
            DontDestroyOnLoad(go);
            go.AddComponent<AxeTreeRenderHost>();
        }
    }

    public class AxeTreeRenderHost : MonoBehaviour
    {
        private const float SPACING_F = 0.7f;          // compact (prototype default)
        private const float SUG_SPACING_Y = 122f;       // sugiyama px per rank unit (prototype 94 * 1.3 default) — clears the 65px tile
        private const bool FLIP_Y = true;              // top-to-bottom discipline order (flip if bands look inverted)
        private const float NODE_W = 70f, NODE_H = 65f;   // real node size at scale 1.0 (prefab ~70x65) — routing + stacking

        private const bool DEBUG_DUMP = false;         // flip on to log coordinate-space numbers 1.5s after tree spawn

        private static bool installed;
        private static bool ready;
        private static readonly Dictionary<string, List<Vector2>> Routes = new Dictionary<string, List<Vector2>>();
        private static readonly List<AxeTreeLayout.JunctionDot> Dots = new List<AxeTreeLayout.JunctionDot>();   // junction-bus branch dots
        private static readonly List<GameObject> DotPool = new List<GameObject>();   // pooled dot Images (children of RDNodeRoot)
        private static Sprite DotSprite;
        internal static readonly Color RND_BG = new Color(0.078f, 0.086f, 0.110f, 1f);   // #14161c — matches the prototype backdrop (renderer.js RND_BG)
        private static readonly FieldInfo PosField = AccessTools.Field(typeof(RDNode), "pos");
        private static readonly FieldInfo WidthF = AccessTools.Field(typeof(RDNode), "width");
        private static readonly FieldInfo HeightF = AccessTools.Field(typeof(RDNode), "height");
        private static readonly FieldInfo TechIconF = AccessTools.Field(typeof(RDNodePrefab), "techIcon");   // the node glyph (Image 'ImageIcon')
        private const float ICON_SCALE = 0.78f;   // shrink the glyph a bit for easier navigation (prototype icon ~0.72 of tile)

        private void Awake()
        {
            if (installed) return;
            installed = true;
            try
            {
                RDTechTree.OnTechTreeSpawn.Add(OnTreeSpawn);   // INSTANCE method -> non-null delegate Target
                var h = new Harmony("rpaxe.tree.render");
                // Manual patch (no [HarmonyPatch] attr) so AxeTreeHighlight's assembly-wide PatchAll
                // can't also grab it -> applied exactly once.
                MethodInfo orig = AccessTools.Method(typeof(RDNode), "GetVectorArray", new[] { typeof(RDNode.Parent) });
                if (orig == null)
                    Debug.LogError("[AXE] render-port: RDNode.GetVectorArray(Parent) not found; lane routing disabled (reposition still active).");
                else
                    h.Patch(orig, prefix: new HarmonyMethod(typeof(AxeTreeRenderHost), nameof(GetVectorArray_Prefix)));
                MethodInfo ug = AccessTools.Method(typeof(RDNode), "UpdateGraphics");
                if (ug != null)
                    h.Patch(ug, postfix: new HarmonyMethod(typeof(AxeTreeRenderHost), nameof(UpdateGraphics_Postfix)));
                Debug.Log("[AXE] R&D render-port patches applied.");
            }
            catch (Exception e) { Debug.LogError("[AXE] render-port apply failed: " + e); }
        }

        // Compute layout + reposition + precompute routes, once per tree spawn (before the nodes' Setup).
        private void OnTreeSpawn(RDTechTree tree)
        {
            ready = false;
            Routes.Clear();
            try
            {
                AxeTreeMeta.EnsureLoaded();
                string layoutMode = AxeTreeMeta.Render.Layout;
                // reposition = C# computes + applies node positions (legacy sugiyama/bands). Otherwise
                // (layout=stock) we CONSUME the emitter's positions (build_tree.py's Brandes-Kopf pass) and
                // only re-route edges — the intended split: emitter owns positions, this port owns edges.
                bool reposition = layoutMode == "bands" || layoutMode == "sugiyama";
                if (!reposition && !AxeTreeMeta.Render.RouteOverride) return;   // fully stock -> nothing to do
                RDController ctrl = RDController.Instance;
                if (ctrl == null || ctrl.nodes == null || ctrl.nodes.Count == 0) return;

                // The in-game tree can contain DUPLICATE RDNodes per techID (e.g. a stray editor TechTree
                // in the DB). Build the layout model on UNIQUE ids only; a computed position is applied to
                // EVERY RDNode of that id (repositon path) so dups stack.
                var lnodes = new List<AxeTreeLayout.LNode>();
                var byId = new Dictionary<string, AxeTreeLayout.LNode>();
                foreach (RDNode rd in ctrl.nodes)
                {
                    string id = rd?.tech?.techID;
                    if (string.IsNullOrEmpty(id) || byId.ContainsKey(id) || !AxeTreeMeta.Nodes.TryGetValue(id, out AxeTreeMeta.NodeMeta m)) continue;
                    var ln = new AxeTreeLayout.LNode { Id = id, Discipline = m.Discipline, Tier = m.Tier, Cost = m.Cost };
                    lnodes.Add(ln); byId[id] = ln;
                }
                if (lnodes.Count == 0) { Debug.LogWarning("[AXE] render-port: no RDNodes matched the metadata; skipping."); return; }

                var edges = new List<AxeTreeLayout.LEdge>();
                var seenEdge = new HashSet<string>();
                foreach (RDNode rd in ctrl.nodes)
                {
                    string to = rd?.tech?.techID;
                    if (string.IsNullOrEmpty(to) || !byId.ContainsKey(to) || rd.parents == null) continue;
                    foreach (RDNode.Parent par in rd.parents)
                    {
                        string from = par?.parent?.node?.tech?.techID;
                        if (!string.IsNullOrEmpty(from) && byId.ContainsKey(from) && seenEdge.Add(from + ">" + to))
                            edges.Add(new AxeTreeLayout.LEdge { From = from, To = to });
                    }
                }

                int placed = 0;
                float ay;   // sign of the vertical axis in the final pos-space (drives the fan-side offset)
                if (reposition)
                {
                    // Stock (cfg) position envelope, read BEFORE we move anything, so our layout fits INTO the
                    // box the scroll content is sized for.
                    float sMinX = 1e9f, sMaxX = -1e9f, sMinY = 1e9f, sMaxY = -1e9f;
                    foreach (RDNode rd in ctrl.nodes)
                    {
                        if (rd == null || PosField == null) continue;
                        Vector3 sp = (Vector3)PosField.GetValue(rd);
                        if (sp.x < sMinX) sMinX = sp.x; if (sp.x > sMaxX) sMaxX = sp.x;
                        if (sp.y < sMinY) sMinY = sp.y; if (sp.y > sMaxY) sMaxY = sp.y;
                    }

                    var discOrder = new Dictionary<string, int>();
                    foreach (var kv in AxeTreeMeta.Disciplines) discOrder[kv.Key] = kv.Value.Order;

                    if (layoutMode == "sugiyama")
                        AxeTreeLayout.LayoutSugiyama(lnodes, edges, byId, discOrder, AxeTreeMeta.TierWidth,
                            SUG_SPACING_Y, AxeTreeMeta.MarginX, AxeTreeMeta.MarginY, false);
                    else
                        AxeTreeLayout.LayoutBands(lnodes, edges, byId, discOrder, AxeTreeMeta.TierWidth,
                            AxeTreeMeta.MarginX, AxeTreeMeta.MarginY, NODE_H, SPACING_F, false);

                    // Fit our layout's bbox onto the stock envelope: X is ~identity (tiers already match), Y is
                    // scaled to fit + optionally flipped so discipline order reads top-to-bottom. Applied to node
                    // positions AND edge waypoints so routing (below) works entirely in the final coordinate space.
                    float mMinX = 1e9f, mMaxX = -1e9f, mMinY = 1e9f, mMaxY = -1e9f;
                    foreach (AxeTreeLayout.LNode ln in lnodes)
                    {
                        if (ln.X < mMinX) mMinX = ln.X; if (ln.X > mMaxX) mMaxX = ln.X;
                        if (ln.Y < mMinY) mMinY = ln.Y; if (ln.Y > mMaxY) mMaxY = ln.Y;
                    }
                    float ax = mMaxX > mMinX ? (sMaxX - sMinX) / (mMaxX - mMinX) : 1f;
                    float bx = sMinX - ax * mMinX;
                    // Y fit: STRETCH a short tree to fill the envelope, but NEVER compress a tall one below its
                    // natural spacing (compression overlaps stacks). When taller than the envelope we keep
                    // ayMag=1 and grow scrollRect.content so the extra height scrolls. Anchor bottom at ENV_BOT.
                    const float ENV_BOT = 80f, ENV_TOP = 2255f;
                    float envH = ENV_TOP - ENV_BOT, naturalH = Mathf.Max(1f, mMaxY - mMinY);
                    float ayMag = naturalH <= envH ? envH / naturalH : 1f;
                    ay = FLIP_Y ? -ayMag : ayMag;
                    float by = FLIP_Y ? ENV_BOT + ayMag * mMaxY : ENV_BOT - ayMag * mMinY;
                    float layoutTopY = ENV_BOT + ayMag * naturalH;   // highest node centre (drives the content-height grow)
                    Debug.Log($"[AXE] FIT naturalH={naturalH:F0} ayMag={ayMag:F3} env={envH:F0} topY={layoutTopY:F0}");
                    foreach (AxeTreeLayout.LNode ln in lnodes) { ln.X = ax * ln.X + bx; ln.Y = ay * ln.Y + by; }
                    foreach (AxeTreeLayout.LEdge e in edges)
                        if (e.Waypoints != null)
                            for (int i = 0; i < e.Waypoints.Count; i++)
                                e.Waypoints[i] = new Vector2(ax * e.Waypoints[i].x + bx, ay * e.Waypoints[i].y + by);

                    var posById = new Dictionary<string, Vector2>(lnodes.Count);
                    foreach (AxeTreeLayout.LNode ln in lnodes) posById[ln.Id] = new Vector2(ln.X, ln.Y);
                    foreach (RDNode rd in ctrl.nodes)
                    {
                        string id = rd?.tech?.techID;
                        if (id != null && posById.TryGetValue(id, out Vector2 p)) { SetPos(rd, p.x, p.y); placed++; }
                    }

                    // RDNodeRoot IS scrollRect.content (verified) -> node localPos is content-local. When the
                    // layout is taller than the stock scroll rect, grow the content height so the top row stays
                    // reachable by scrolling instead of clipping.
                    RectTransform content = ctrl.gridArea != null && ctrl.gridArea.scrollRect != null ? ctrl.gridArea.scrollRect.content : null;
                    if (content != null)
                    {
                        float need = layoutTopY + ENV_BOT;
                        if (content.sizeDelta.y < need)
                            content.sizeDelta = new Vector2(content.sizeDelta.x, need);
                    }
                }
                else
                {
                    // STOCK POSITIONS: consume the emitter's (Brandes-Kopf) RDNode.pos as-is — no reposition,
                    // no fit — and route edges against them. The fan-side sign is a config switch (flipY) so a
                    // wrong-side result is a one-line cfg toggle + restart, not a rebuild.
                    foreach (RDNode rd in ctrl.nodes)
                    {
                        string id = rd?.tech?.techID;
                        if (id != null && PosField != null && byId.TryGetValue(id, out AxeTreeLayout.LNode ln))
                        {
                            Vector3 sp = (Vector3)PosField.GetValue(rd);
                            ln.X = sp.x; ln.Y = sp.y;
                        }
                    }
                    ay = AxeTreeMeta.Render.FlipY ? -1f : 1f;
                }

                if (AxeTreeMeta.Render.RouteOverride)
                {
                    AxeTreeLayout.ComputeSlots(edges, byId, AxeTreeMeta.Render.Fan);
                    // The fan endpoint offset is in Y, so nodeH must follow the vertical-axis sign to stay on the node's side.
                    float signedH = NODE_H * Mathf.Sign(ay);
                    bool xf = AxeTreeMeta.Render.Xfan; float xp = AxeTreeMeta.Render.XfanPitch;
                    Dots.Clear();
                    switch (AxeTreeMeta.Render.Routing)
                    {
                        case "ortho-late":  AxeTreeLayout.RouteOrthoLate(edges, byId, NODE_W, signedH, xf, xp); break;
                        case "ortho-early": AxeTreeLayout.RouteOrthoEarly(edges, byId, NODE_W, signedH, xf, xp); break;
                        case "junction":    AxeTreeLayout.RouteJunctionBus(edges, byId, NODE_W, signedH, Dots); break;
                        default:            AxeTreeLayout.BuildLaneRoutes(lnodes, edges, NODE_W, signedH, AxeTreeMeta.Render.LanePitch); break;
                    }
                    if (AxeTreeMeta.Render.Avoid)   // detour edge runs around the node boxes they'd cross
                        foreach (AxeTreeLayout.LEdge e in edges)
                            if (e.Geom != null) e.Geom = AxeTreeLayout.AvoidNodes(e.Geom, lnodes, NODE_W, signedH);
                    foreach (AxeTreeLayout.LEdge e in edges)
                        if (e.Geom != null) Routes[e.From + ">" + e.To] = e.Geom;
                    BuildJunctionDots(ctrl);   // instantiate/refresh bus branch dots (no-op unless routing=junction)
                }

                ready = true;
                Debug.Log($"[AXE] render-port: {lnodes.Count} unique nodes ({(reposition ? placed + " placed" : "stock pos")}), {Routes.Count} edges routed " +
                          $"(layout={AxeTreeMeta.Render.Layout} routing={AxeTreeMeta.Render.Routing} fan={AxeTreeMeta.Render.Fan})");
                StartCoroutine(FitContentToNodes());   // grow the scroll content to bound a tall/wide tree (else it clips)
                OverrideBackground(ctrl);               // replace the stock grid with a solid backdrop (matches the prototype)
                if (DEBUG_DUMP) StartCoroutine(DebugDump());
            }
            catch (Exception e) { Debug.LogError("[AXE] render-port OnTreeSpawn failed: " + e); ready = false; }
        }

        // TEMP instrumentation: dump the live coordinate space once, after Setup + scroll settle.
        private System.Collections.IEnumerator DebugDump()
        {
            yield return new WaitForSecondsRealtime(1.5f);
            DumpNow();
        }

        // Grow the R&D scroll content to bound the whole tree. KSP ships a fixed-size content canvas
        // (~4000x2300); the emitter's `stock` layout can place nodes far past it (dump: nodes reach y~6000
        // but content is ~2300 tall -> the top clips with no way to scroll to it, and nodes right of x=0
        // fall outside the pivot=(1,0) content). The reposition path grows content itself; the stock path
        // never did. Read the ACTUAL post-Setup node localPositions (RDNodeRoot IS content, scale 1) and
        // UNION the content rect to cover them + a margin, choosing the pivot so the rect brackets the node
        // cloud while the tree stays visually put (preserve world position). Monotonic (grow-only), so a
        // tree that already fits is left untouched. Re-run once after a beat to survive late stock re-sizes.
        private System.Collections.IEnumerator FitContentToNodes()
        {
            yield return null; yield return null; yield return null;   // let the nodes' Setup apply localPositions
            FitContentNow();
            CenterOnStart(RDController.Instance);   // land the initial view on the start node
            yield return new WaitForSecondsRealtime(1.25f);
            FitContentNow();
        }

        // Scroll the initial view to the start node: vertically centred, ~25% from the left (the tree only
        // extends rightward from start, so the left is empty). Runs once at open; setting content.position
        // is a scroll offset only (not a pivot change), so it doesn't affect zoom.
        private static void CenterOnStart(RDController ctrl)
        {
            try
            {
                UnityEngine.UI.ScrollRect sr = ctrl != null && ctrl.gridArea != null ? ctrl.gridArea.scrollRect : null;
                RectTransform content = sr != null ? sr.content : null;
                RectTransform vp = sr != null ? (sr.viewport != null ? sr.viewport : sr.transform as RectTransform) : null;
                if (content == null || vp == null || ctrl.nodes == null) return;

                RDNode start = null;
                foreach (RDNode n in ctrl.nodes) if (n != null && n.tech != null && n.tech.techID == "start") { start = n; break; }
                if (start == null)   // fallback: the leftmost node (tier 0)
                {
                    float mnx = 1e9f;
                    foreach (RDNode n in ctrl.nodes) if (n != null && n.transform.localPosition.x < mnx) { mnx = n.transform.localPosition.x; start = n; }
                }
                if (start == null) return;

                Rect vr = vp.rect;
                Vector2 targetLocal = new Vector2(vr.xMin + vr.width * 0.25f, vr.center.y);   // 25% from left, vertical centre
                Vector3 delta = vp.TransformPoint(targetLocal) - start.transform.position;
                content.position += new Vector3(delta.x, delta.y, 0f);
                if (sr != null) sr.velocity = Vector2.zero;
            }
            catch (Exception e) { Debug.LogError("[AXE] center-on-start failed: " + e); }
        }

        private static void FitContentNow()
        {
            try
            {
                RDController ctrl = RDController.Instance;
                if (ctrl == null || ctrl.nodes == null || ctrl.nodes.Count == 0) return;
                OverrideBackground(ctrl);   // re-assert the solid backdrop after Setup/scroll settle
                RectTransform content = ctrl.gridArea != null && ctrl.gridArea.scrollRect != null ? ctrl.gridArea.scrollRect.content : null;
                if (content == null) return;

                float mnx = 1e9f, mxx = -1e9f, mny = 1e9f, mxy = -1e9f;
                foreach (RDNode rd in ctrl.nodes)
                {
                    if (rd == null) continue;
                    Vector3 p = rd.transform.localPosition;
                    if (p.x < mnx) mnx = p.x; if (p.x + NODE_W > mxx) mxx = p.x + NODE_W;   // include the tile's right extent
                    if (p.y < mny) mny = p.y; if (p.y > mxy) mxy = p.y;
                }
                if (mxx < mnx) return;

                const float PAD = 400f;   // scroll a bit past the tree on the grown sides (left/top)
                Rect r = content.rect;
                Vector2 pv = content.pivot;
                // Grow ONLY sizeDelta — never pivot or position — so KSP's zoom-to-cursor and scroll math stay
                // intact (changing the pivot reset the view on zoom and shifted the junction dots). sizeDelta
                // growth moves each rect edge by a pivot-weighted share, so cover each overflowing side where the
                // pivot allows; the emitter's tighter x-spacing keeps the tree left of the (pivot-pinned) right edge.
                float overTop = Mathf.Max(0f, (mxy + PAD) - r.yMax), overBot = Mathf.Max(0f, r.yMin - (mny - PAD));
                float overRight = Mathf.Max(0f, (mxx + PAD) - r.xMax), overLeft = Mathf.Max(0f, r.xMin - (mnx - PAD));
                float dH = 0f, dW = 0f;
                if (overTop > 0f && pv.y < 0.999f) dH = Mathf.Max(dH, overTop / (1f - pv.y));
                if (overBot > 0f && pv.y > 0.001f) dH = Mathf.Max(dH, overBot / pv.y);
                if (overRight > 0f && pv.x < 0.999f) dW = Mathf.Max(dW, overRight / (1f - pv.x));
                if (overLeft > 0f && pv.x > 0.001f) dW = Mathf.Max(dW, overLeft / pv.x);
                if (dW <= 1f && dH <= 1f) return;   // already contains everything

                content.sizeDelta = new Vector2(content.sizeDelta.x + dW, content.sizeDelta.y + dH);
                Debug.Log($"[AXE] content-fit: nodes x[{mnx:F0}..{mxx:F0}] y[{mny:F0}..{mxy:F0}] grow=({dW:F0},{dH:F0}) -> sizeDelta={content.sizeDelta} (pivot {pv} unchanged)");
            }
            catch (Exception e) { Debug.LogError("[AXE] content-fit failed: " + e); }
        }

        // Replace the stock R&D blueprint grid with a solid backdrop that matches the prototype. BGDUMP showed
        // the grid IS the scroll-content node's own Image (RDNodeRoot == "Grid", sprite=R&D_grid), with every
        // RDNode rendered as its child on top. So we recolour THAT Image: drop the grid sprite + set the solid
        // colour -> a plain fill behind all nodes, panning/scaling with them. Per-scene + reset from the prefab
        // on the next R&D open, so it's non-destructive. Re-asserted from FitContentNow to survive rebuilds.
        internal static void OverrideBackground(RDController ctrl)
        {
            if (!AxeTreeMeta.Render.SolidBg) return;
            try
            {
                RectTransform content = ctrl != null && ctrl.gridArea != null && ctrl.gridArea.scrollRect != null ? ctrl.gridArea.scrollRect.content : null;
                Image grid = content != null ? content.GetComponent<Image>() : null;
                if (grid == null) return;
                grid.sprite = null;                    // drop the R&D_grid texture
                grid.overrideSprite = null;
                grid.type = Image.Type.Simple;         // a null-sprite Simple Image renders a solid quad
                grid.color = RND_BG;                   // -> solid backdrop behind all nodes
            }
            catch (Exception e) { Debug.LogError("[AXE] backdrop override failed: " + e); }
        }

        private static void DumpNow()
        {
            try
            {
                RDController ctrl = RDController.Instance;
                if (ctrl == null || ctrl.nodes == null || ctrl.nodes.Count == 0) return;
                float mnx = 1e9f, mxx = -1e9f, mny = 1e9f, mxy = -1e9f;
                foreach (RDNode rd in ctrl.nodes)
                {
                    Vector3 p = rd.transform.localPosition;
                    if (p.x < mnx) mnx = p.x; if (p.x > mxx) mxx = p.x;
                    if (p.y < mny) mny = p.y; if (p.y > mxy) mxy = p.y;
                }
                Debug.Log($"[AXE] DUMP localPos bbox x[{mnx:F0}..{mxx:F0}] y[{mny:F0}..{mxy:F0}] n={ctrl.nodes.Count}");
                RDGridArea ga = ctrl.gridArea;
                if (ga != null && ga.scrollRect != null)
                {
                    var sr = ga.scrollRect;
                    if (sr.content != null) Debug.Log($"[AXE] DUMP content rect={sr.content.rect} sizeDelta={sr.content.sizeDelta} anchoredPos={sr.content.anchoredPosition} pivot={sr.content.pivot} anchorMin={sr.content.anchorMin} anchorMax={sr.content.anchorMax}");
                    if (sr.viewport != null) Debug.Log($"[AXE] DUMP viewport rect={sr.viewport.rect}");
                }
                RDNode s = ctrl.nodes[0];
                float w = WidthF != null ? (float)WidthF.GetValue(s) : -1f;
                float h = HeightF != null ? (float)HeightF.GetValue(s) : -1f;
                Vector3 gp = s.graphics != null ? s.graphics.transform.position : Vector3.zero;
                Debug.Log($"[AXE] DUMP node0 id={s.tech?.techID} w={w:F1} h={h:F1} transform.pos={s.transform.position} localPos={s.transform.localPosition} graphics.pos={gp}");
                Debug.Log($"[AXE] DUMP node0 anchorR={s.GetPosition(RDNode.Anchor.RIGHT, Vector3.zero)} anchorL={s.GetPosition(RDNode.Anchor.LEFT, Vector3.zero)}");
                RectTransform s0 = s.transform as RectTransform;
                if (s0 != null) Debug.Log($"[AXE] ANCHDUMP node0 anchorMin={s0.anchorMin} anchorMax={s0.anchorMax} pivot={s0.pivot} anchoredPos={s0.anchoredPosition} sizeDelta={s0.sizeDelta}");
                RDNodePrefab g0 = s.graphics;
                if (g0 != null && g0.searchHighlight != null)   // halo (researchable ring) offset diagnosis
                {
                    RectTransform hr = g0.searchHighlight.rectTransform;
                    Debug.Log($"[AXE] HALODUMP searchHighlight anchorMin={hr.anchorMin} anchorMax={hr.anchorMax} pivot={hr.pivot} anchoredPos={hr.anchoredPosition} sizeDelta={hr.sizeDelta} parent={(hr.parent != null ? hr.parent.name : "null")}");
                }
                if (g0 != null)   // RDNodePrefab's Graphic-typed fields -> find the icon field to shrink it
                    foreach (System.Reflection.FieldInfo fi in g0.GetType().GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance))
                    {
                        object val = fi.GetValue(g0);
                        if (val is Graphic gr)
                            Debug.Log($"[AXE] FIELDDUMP RDNodePrefab.{fi.Name} = {gr.GetType().Name} '{gr.name}' size={gr.rectTransform.sizeDelta} scale={gr.transform.localScale}");
                    }
                if (DotPool.Count > 0 && DotPool[0] != null)   // a junction dot's anchor (vs node's)
                {
                    RectTransform dr = DotPool[0].GetComponent<RectTransform>();
                    Debug.Log($"[AXE] DOTDUMP dot0 anchorMin={dr.anchorMin} anchorMax={dr.anchorMax} pivot={dr.pivot} anchoredPos={dr.anchoredPosition} localPos={dr.localPosition} active={DotPool[0].activeSelf}");
                }
                Transform root = ctrl.RDNodeRoot;
                if (root != null) Debug.Log($"[AXE] DUMP RDNodeRoot pos={root.position} localScale={root.localScale} euler={root.eulerAngles}");
                // BACKGROUND diagnosis: ancestor chain + the host's children, to locate the stock grid.
                RectTransform contentRT = ctrl.gridArea != null && ctrl.gridArea.scrollRect != null ? ctrl.gridArea.scrollRect.content : null;
                Transform tw = contentRT;
                for (int up = 0; up < 6 && tw != null; up++)
                {
                    Image im = tw.GetComponent<Image>(); RawImage raw = tw.GetComponent<RawImage>();
                    Debug.Log($"[AXE] BGDUMP anc[{up}] '{tw.name}' img={(im != null ? im.color.ToString("F2") + (im.sprite != null ? "/spr:" + im.sprite.name : "") : "-")} raw={(raw != null ? (raw.texture != null ? raw.texture.name : "yes") : "-")} kids={tw.childCount}");
                    tw = tw.parent;
                }
                Transform host = contentRT != null ? contentRT.parent : null;
                if (host != null)
                    for (int i = 0; i < host.childCount; i++)
                    {
                        Transform c = host.GetChild(i);
                        Debug.Log($"[AXE] BGDUMP host.kid[{i}] '{c.name}' img={(c.GetComponent<Image>() != null)} raw={(c.GetComponent<RawImage>() != null)} active={c.gameObject.activeSelf}");
                    }
                RectTransform content = ga != null && ga.scrollRect != null ? ga.scrollRect.content : null;
                if (root != null && content != null)
                    Debug.Log($"[AXE] DUMP root==content? {ReferenceEquals(root, content)} rootLocalY={root.localPosition.y:F0} rootParent={(root.parent != null ? root.parent.name : "null")} contentWorldY={content.position.y:F0} contentParent={(content.parent != null ? content.parent.name : "null")}");
            }
            catch (Exception e) { Debug.LogError("[AXE] DUMP failed: " + e); }
        }

        // Replace the stock elbow with the precomputed lane route (local pos-space -> world).
        // __0 = the original's first arg (the Parent) bound positionally, so we don't depend on its name.
        private static bool GetVectorArray_Prefix(RDNode __instance, RDNode.Parent __0, ref List<Vector2> __result)
        {
            if (!ready || !AxeTreeMeta.Render.RouteOverride) return true;
            try
            {
                string from = __0?.parent?.node?.tech?.techID;
                string to = __instance?.tech?.techID;
                if (from == null || to == null) return true;
                if (!Routes.TryGetValue(from + ">" + to, out List<Vector2> local) || local == null || local.Count < 2) return true;

                Transform root = RDController.Instance != null ? RDController.Instance.RDNodeRoot : null;
                var pts = new List<Vector2>(local.Count);
                for (int i = 0; i < local.Count; i++)
                {
                    float lx = local[i].x, ly = local[i].y;   // route points are already in final pos-space
                    if (root != null) { Vector3 w = root.TransformPoint(new Vector3(lx, ly, 0f)); pts.Add(new Vector2(w.x, w.y)); }
                    else pts.Add(new Vector2(lx, ly));
                }
                __result = pts;
                return false;   // skip stock routing
            }
            catch (Exception e) { Debug.LogException(e); return true; }
        }

        private static void SetPos(RDNode rd, float x, float y)
        {
            if (rd == null || PosField == null) return;
            Vector3 cur = (Vector3)PosField.GetValue(rd);   // keep the cfg z (layer)
            PosField.SetValue(rd, new Vector3(x, y, cur.z));
        }

        // Junction-bus branch dots: small Image children of RDNodeRoot (= scroll content), placed by
        // localPosition in the SAME pos-space as the routed points (and the nodes), so they pan/zoom with the
        // tree. Pooled + reused across respawns; coloured by the bus source's discipline. No-op / all hidden
        // unless routing = junction. Placed at OnTreeSpawn (before Setup); localPosition is absolute so it holds.
        private static void BuildJunctionDots(RDController ctrl)
        {
            foreach (GameObject g in DotPool) if (g != null) g.SetActive(false);
            if (AxeTreeMeta.Render.Routing != "junction" || Dots.Count == 0) return;
            Transform root = ctrl != null ? ctrl.RDNodeRoot : null;
            if (root == null) return;
            if (DotSprite == null) DotSprite = MakeCircleSprite(20);
            // Anchor the dots at the content's PIVOT: a child anchored at its parent's pivot keeps
            // localPosition == anchoredPosition no matter how the parent's sizeDelta grows (the content-fit).
            // RDNodes are plain Transforms (immune already); the dots are RectTransforms, so without this a
            // content-fit grow drifts them ~half a tree (center-anchored -> the anchor reference moves).
            RectTransform contentRT = ctrl.gridArea != null && ctrl.gridArea.scrollRect != null ? ctrl.gridArea.scrollRect.content : root as RectTransform;
            Vector2 dotAnchor = contentRT != null ? contentRT.pivot : new Vector2(1f, 0f);
            for (int i = 0; i < Dots.Count; i++)
            {
                GameObject go = i < DotPool.Count ? DotPool[i] : null;
                if (go == null)
                {
                    go = new GameObject("AxeJunctionDot", typeof(RectTransform), typeof(Image));   // Image RequireComponent adds CanvasRenderer
                    Image im0 = go.GetComponent<Image>();
                    im0.raycastTarget = false; im0.sprite = DotSprite;
                    if (i < DotPool.Count) DotPool[i] = go; else DotPool.Add(go);
                }
                RectTransform rt = go.GetComponent<RectTransform>();
                rt.SetParent(root, false);
                rt.anchorMin = dotAnchor; rt.anchorMax = dotAnchor;   // = content pivot -> immune to the content-fit resize
                rt.pivot = new Vector2(0.5f, 0.5f);            // centre the 9x9 dot on its point
                rt.sizeDelta = new Vector2(9f, 9f);
                rt.localPosition = new Vector3(Dots[i].Pos.x, Dots[i].Pos.y, 0f);   // same space as the routed points
                go.GetComponent<Image>().color = DotBaseColor(i);
                go.SetActive(true);
            }
        }

        // A junction dot's resting colour = its bus source's discipline colour (neutral grey fallback).
        private static Color DotBaseColor(int i)
        {
            if (i >= 0 && i < Dots.Count
                && AxeTreeMeta.Nodes.TryGetValue(Dots[i].From, out AxeTreeMeta.NodeMeta m)
                && AxeTreeMeta.Disciplines.TryGetValue(m.Discipline, out AxeTreeMeta.DiscMeta d)) return d.Color;
            return new Color(0.54f, 0.56f, 0.59f, 1f);
        }

        // Lineage-dim the junction-bus dots the same way the prototype does: a dot's edge is "lit" only if
        // BOTH its ends are on the highlighted lineage; off-lineage dots ghost to a low alpha. Restore =
        // resting discipline colour. Called by AxeHighlighter (Apply/Clear) so dots track hover + selection.
        internal static void HighlightDots(HashSet<string> lineageIds)
        {
            for (int i = 0; i < Dots.Count && i < DotPool.Count; i++)
            {
                GameObject g = DotPool[i];
                if (g == null || !g.activeSelf) continue;
                Image im = g.GetComponent<Image>();
                if (im == null) continue;
                bool lit = lineageIds != null && lineageIds.Contains(Dots[i].From) && lineageIds.Contains(Dots[i].To);
                Color b = DotBaseColor(i);
                im.color = lit ? b : new Color(b.r, b.g, b.b, 0.10f);   // off-lineage -> ghost (prototype DIM_EDGE)
            }
        }

        internal static void RestoreDots()
        {
            for (int i = 0; i < Dots.Count && i < DotPool.Count; i++)
            {
                GameObject g = DotPool[i];
                if (g == null || !g.activeSelf) continue;
                Image im = g.GetComponent<Image>();
                if (im != null) im.color = DotBaseColor(i);
            }
        }

        // A soft-edged white circle sprite (1px AA), tinted per-dot via Image.color.
        private static Sprite MakeCircleSprite(int size)
        {
            var tex = new Texture2D(size, size, TextureFormat.ARGB32, false) { wrapMode = TextureWrapMode.Clamp };
            float r = size / 2f;
            var px = new Color32[size * size];
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float dx = x + 0.5f - r, dy = y + 0.5f - r;
                    float a = Mathf.Clamp01(r - Mathf.Sqrt(dx * dx + dy * dy));   // 1px anti-aliased edge
                    px[y * size + x] = new Color32(255, 255, 255, (byte)(a * 255f));
                }
            tex.SetPixels32(px); tex.Apply();
            return Sprite.Create(tex, new Rect(0, 0, size, size), new Vector2(0.5f, 0.5f), 100f);
        }

        // Tint each node's icon + its incident (parent) edges by discipline colour, AFTER stock UpdateGraphics
        // set state colours. Runs on spawn, on state changes, and on the lineage-highlight's resets — so the
        // discipline colour is the persistent base the highlight dims relative to.
        private static void UpdateGraphics_Postfix(RDNode __instance)
        {
            if (!ready) return;
            try
            {
                string id = __instance?.tech?.techID;
                if (id == null || !AxeTreeMeta.Nodes.TryGetValue(id, out AxeTreeMeta.NodeMeta m)) return;
                StateRing(__instance);   // per-node state halo (researchable = cyan; researched/locked = off)
                if (!AxeTreeMeta.Render.DiscColor) return;
                // Tile colour by state: RESEARCHED -> the whole tile turns green (matches the prototype
                // doneStyle='tile'); RESEARCHABLE -> discipline colour; locked (FADED) -> desaturated + dim.
                if (AxeTreeMeta.Disciplines.TryGetValue(m.Discipline, out AxeTreeMeta.DiscMeta d))
                    PaintTile(__instance, __instance.state == RDNode.State.RESEARCHED
                        ? DoneTile
                        : StateTint(d.Color, __instance.state == RDNode.State.FADED));
                if (__instance.parents == null) return;
                foreach (RDNode.Parent par in __instance.parents)   // edge coloured by its SOURCE discipline
                {
                    RDNode src = par?.parent?.node;
                    string from = src?.tech?.techID;
                    if (from != null && AxeTreeMeta.Nodes.TryGetValue(from, out AxeTreeMeta.NodeMeta pm)
                        && AxeTreeMeta.Disciplines.TryGetValue(pm.Discipline, out AxeTreeMeta.DiscMeta pd))
                    {
                        Color ec = StateTint(pd.Color, src.state != RDNode.State.RESEARCHED);   // lit once source researched
                        if (par.line != null) par.line.color = ec;
                        if (par.arrowHead != null) par.arrowHead.color = ec;
                    }
                }
            }
            catch (Exception e) { Debug.LogException(e); }
        }

        // Recede = desaturate the colour toward its own grey + dim the alpha (locked nodes / un-researched edges).
        private static Color StateTint(Color c, bool recede)
        {
            if (!recede) return c;
            float l = 0.3f * c.r + 0.59f * c.g + 0.11f * c.b;
            return new Color(c.r + (l - c.r) * 0.8f, c.g + (l - c.g) * 0.8f, c.b + (l - c.b) * 0.8f, 0.5f);
        }

        // Paint the whole node TILE (the UIStateButton frame) the given colour + a contrast-ink icon on top,
        // so a node reads like the prototype's coloured tiles instead of stock's grey frame + tinted icon.
        // Runs after stock SetButtonState (in the postfix / the highlight), overriding the state frame colour.
        internal static void PaintTile(RDNode rd, Color tile)
        {
            if (rd == null || rd.graphics == null) return;
            UIStateButton btn = rd.graphics.button;
            if (btn != null && btn.Image != null)
            {
                // Flatten the tile: the stock node-frame sprite averages ~0.5 luminance and KSP multiplies it
                // by our colour, so tiles rendered ~half as bright as the prototype's flat fill (verified: a
                // #c2a0e0 tile came out #604f6f). Drop the sprite -> a flat quad shows the colour at full value.
                btn.Image.sprite = null;
                btn.Image.overrideSprite = null;
                btn.Image.type = Image.Type.Simple;
                btn.Image.color = tile;
            }
            // Draw the discipline glyph in its NATIVE colours — the prototype draws the icon untinted, and
            // the shipped RDicon_* PNGs (GameData/RP-AXE/design/Tree/icons, wired via each node's cfg `icon`)
            // are dark line-art that reads on every (bright) discipline tile. White = no multiply; carry the
            // tile's alpha so faded / ghosted nodes dim the icon in step with the tile.
            rd.graphics.SetIconColor(new Color(1f, 1f, 1f, tile.a));
            if (TechIconF != null && TechIconF.GetValue(rd.graphics) is Graphic ic)   // shrink the glyph for easier navigation
                ic.transform.localScale = new Vector3(ICON_SCALE, ICON_SCALE, 1f);
        }

        // Lightweight recolour for the hover highlight: sets ONLY the tile + icon COLOUR. Graphic.color
        // equality-checks, so unchanged nodes cost nothing (no dirty, no canvas rebuild) — unlike PaintTile,
        // which also writes the icon localScale (a transform write per node, ×223 per hover-move = the lag).
        // The sprite/scale setup stays from the last PaintTile (spawn / state change).
        internal static void TintTile(RDNode rd, Color tile)
        {
            if (rd == null || rd.graphics == null) return;
            UIStateButton btn = rd.graphics.button;
            if (btn != null && btn.Image != null) btn.Image.color = tile;
            rd.graphics.SetIconColor(new Color(1f, 1f, 1f, tile.a));
        }

        private static readonly Color RingAvailable = new Color(0.32f, 0.78f, 0.97f, 1f);   // researchable = cyan frontier
        internal static readonly Color DoneTile = new Color(0.184f, 0.635f, 0.373f, 1f);    // #2fa25f — researched tile (prototype doneStyle='tile')

        // Per-node research-state halo. Only the RESEARCHABLE frontier gets a ring (cyan) — the actionable
        // "what to research next". Researched needs no ring now that its whole tile is green; locked = off.
        internal static void StateRing(RDNode rd)
        {
            RDNodePrefab g = rd != null ? rd.graphics : null;
            if (g == null || g.searchHighlight == null) return;
            g.searchHighlight.raycastTarget = false;   // the ring must never intercept the node's click
            // Centre the ring on the TILE exactly (the prefab offsets the ring, and the tile itself may sit a
            // hair off the button origin) — align to the tile's own centre rather than the button's origin.
            UIStateButton btn = g.button;
            if (btn != null && btn.Image != null) g.searchHighlight.rectTransform.position = btn.Image.rectTransform.position;
            else g.searchHighlight.rectTransform.anchoredPosition = Vector2.zero;
            if (rd.state == RDNode.State.RESEARCHABLE) { g.searchHighlight.color = RingAvailable; g.searchHighlight.enabled = true; }
            else g.searchHighlight.enabled = false;     // researched (green tile signals it) + locked = no ring
        }

        // Hover-trace lineage (like the HTML) + click empty background to deselect. Both key off the node
        // under the pointer (UI raycast). Stock R&D only deselects when you re-click the node.
        private Vector3 _downPos;
        private bool _dragged;
        private RDNode _lastHilite;      // last node the lineage highlight was applied for (change detection)
        private static readonly List<RaycastResult> _rayHits = new List<RaycastResult>();

        private void Update()
        {
            RDController ctrl = RDController.Instance;
            if (ctrl == null) return;
            RDNode over = NodeUnderPointer();

            // Hover: highlight the hovered node's lineage; on hover-out revert to the pinned selection (or
            // stock). Only re-highlight when the hovered node changes. Click still pins via ShowNodePanel.
            if (AxeTreeMeta.Render.Hover && over != _lastHilite)
            {
                _lastHilite = over;
                try
                {
                    if (over != null) AxeHighlighter.Apply(ctrl, over);
                    else if (ctrl.node_selected != null) AxeHighlighter.Apply(ctrl, ctrl.node_selected);
                    else AxeHighlighter.Clear(ctrl);
                }
                catch (Exception e) { Debug.LogException(e); }
            }

            // Click (not drag/pan) on empty background -> deselect. Stock only deselects when you re-click
            // the node; it tracks selection in TWO places -- ctrl.node_selected AND node.selected/graphics.
            // ShowNothingPanel() alone only swaps the side panel to "nothing" (+ our AxeHighlighter.Clear);
            // it leaves node.selected==true and the node's selection glow lit, so the node's own click handler
            // (RDNode.NodeInput) still sees itself as selected and TOGGLES OFF on the next click instead of
            // re-selecting. Replicate stock's full deselect: clear the node's flag+glow via UnselectNode() and
            // drop ctrl.node_selected so both re-click and hover-restore read "nothing pinned".
            if (Input.GetMouseButtonDown(0)) { _downPos = Input.mousePosition; _dragged = false; }
            else if (Input.GetMouseButton(0) && !_dragged && (Input.mousePosition - _downPos).sqrMagnitude > 25f) _dragged = true;
            else if (Input.GetMouseButtonUp(0) && !_dragged && over == null && ctrl.node_selected != null)
            {
                try
                {
                    RDNode sel = ctrl.node_selected;
                    ctrl.ShowNothingPanel();   // side panel -> nothing (+ AxeHighlighter.Clear via postfix)
                    sel.UnselectNode();         // clear node.selected + the selection glow (the missing half)
                    ctrl.node_selected = null;  // controller no longer holds a pinned node
                }
                catch (Exception e) { Debug.LogException(e); }
            }
        }

        // Zoom-to-cursor: KSP zooms by scaling the content around its bottom-right pivot, which on our huge
        // tree swings the view wildly (the aPos jump). After KSP applies the scale (its Update), nudge the
        // content so the point that was under the cursor stays under it — LateUpdate runs after Update.
        private float _zoomLastScale = -1f;
        private Vector3 _zoomLastLocal, _zoomStablePos;
        private bool _zoomHaveRef, _zoomHaveStable;
        private void LateUpdate()
        {
            RDController ctrl = RDController.Instance;
            RectTransform content = ctrl != null && ctrl.gridArea != null && ctrl.gridArea.scrollRect != null ? ctrl.gridArea.scrollRect.content : null;
            if (content == null) { _zoomHaveRef = false; _zoomHaveStable = false; return; }
            try
            {
                Canvas canvas = content.GetComponentInParent<Canvas>();
                Camera cam = canvas != null ? canvas.worldCamera : null;
                bool haveCursor = RectTransformUtility.ScreenPointToWorldPointInRectangle(content, Input.mousePosition, cam, out Vector3 cursorWorld);
                float scale = content.localScale.x;
                bool scaleChanged = _zoomHaveRef && Mathf.Abs(scale - _zoomLastScale) > 1e-5f;

                if (scaleChanged && haveCursor)
                    content.position += cursorWorld - content.TransformPoint(_zoomLastLocal);   // zoom: keep the cursor point fixed
                else if (!scaleChanged && _zoomHaveStable && Mathf.Abs(Input.mouseScrollDelta.y) > 0.001f)
                    content.position = _zoomStablePos;   // wheel at the zoom LIMIT (scale clamped): KSP yanks aPos -> hold still

                if (haveCursor) _zoomLastLocal = content.InverseTransformPoint(cursorWorld);
                _zoomLastScale = scale;
                _zoomHaveRef = haveCursor;
                _zoomStablePos = content.position;   // authoritative position after correction
                _zoomHaveStable = true;
            }
            catch (Exception e) { Debug.LogException(e); _zoomHaveRef = false; _zoomHaveStable = false; }
        }

        private static RDNode NodeUnderPointer()
        {
            if (EventSystem.current == null) return null;
            var ped = new PointerEventData(EventSystem.current) { position = Input.mousePosition };
            _rayHits.Clear();
            EventSystem.current.RaycastAll(ped, _rayHits);
            for (int i = 0; i < _rayHits.Count; i++)
            {
                if (_rayHits[i].gameObject == null) continue;
                RDNode n = _rayHits[i].gameObject.GetComponentInParent<RDNode>();
                if (n != null) return n;
            }
            return null;
        }

        // Discipline colour legend, shown while R&D is open (RDController.Instance != null).
        private static GUIStyle _legendTitle, _legendRow;
        private void OnGUI()
        {
            if (!ready || RDController.Instance == null) return;
            // No hover name label — stock R&D already shows the node title on hover.
            if (AxeTreeMeta.Render.Legend && AxeTreeMeta.Disciplines.Count > 0) DrawLegend();
        }

        private static void DrawLegend()
        {
            if (_legendRow == null)
            {
                _legendRow = new GUIStyle(GUI.skin.label) { fontSize = 15, alignment = TextAnchor.MiddleLeft };
                _legendTitle = new GUIStyle(GUI.skin.label) { fontSize = 18, fontStyle = FontStyle.Bold };
            }
            var list = new List<KeyValuePair<string, AxeTreeMeta.DiscMeta>>(AxeTreeMeta.Disciplines);
            list.Sort((a, b) => a.Value.Order.CompareTo(b.Value.Order));
            const float w = 280f, rowH = 24f, sw = 18f, pad = 10f;
            float h = list.Count * rowH + pad * 2f + 30f;
            var box = new Rect(10f, 48f, w, h);
            GUI.color = new Color(0f, 0f, 0f, 0.78f);
            GUI.DrawTexture(box, Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUI.Label(new Rect(box.x + pad, box.y + 6f, w, 24f), "Disciplines", _legendTitle);
            float yy = box.y + 34f;
            foreach (KeyValuePair<string, AxeTreeMeta.DiscMeta> kv in list)
            {
                GUI.color = kv.Value.Color;
                GUI.DrawTexture(new Rect(box.x + pad, yy + (rowH - sw) / 2f, sw, sw), Texture2D.whiteTexture);
                GUI.color = Color.white;
                GUI.Label(new Rect(box.x + pad + sw + 9f, yy, w - pad - sw - 14f, rowH), kv.Value.Title, _legendRow);
                yy += rowH;
            }
        }
    }
}
