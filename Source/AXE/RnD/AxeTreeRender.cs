using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using KSP.UI.Screens;
using UnityEngine;
using UnityEngine.EventSystems;

namespace RPAxe.RnD
{
    /// <summary>
    /// In-game R&amp;D render port (enhance-stock, config-toggleable). Ports the HTML prototype's
    /// discipline-band layout + lane-routed arrows into the live R&amp;D scene via two hooks:
    ///   * RDTechTree.OnTechTreeSpawn (event, fires right after LoadTechTree fills RDController.nodes
    ///     and BEFORE the nodes' next-frame Setup): compute the bands layout from AxeTreeMeta and
    ///     overwrite each RDNode's private `pos` field, which Setup then applies (localPosition = pos)
    ///     and draws arrows against — no teardown/redraw races. Also precomputes the lane routes.
    ///   * Harmony prefix on RDNode.GetVectorArray(Parent): return the precomputed lane-routed points
    ///     (world space) instead of the stock elbow, when laneRouting is on.
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
        private const bool FLIP_Y = true;              // top-to-bottom discipline order (flip if bands look inverted)
        private const float NODE_W = 42f, NODE_H = 39f;   // real node size at scale 0.6 (measured in-game) — routing + stacking

        private const bool DEBUG_DUMP = false;         // flip on to log coordinate-space numbers 1.5s after tree spawn

        private static bool installed;
        private static bool ready;
        private static readonly Dictionary<string, List<Vector2>> Routes = new Dictionary<string, List<Vector2>>();
        private static readonly FieldInfo PosField = AccessTools.Field(typeof(RDNode), "pos");
        private static readonly FieldInfo WidthF = AccessTools.Field(typeof(RDNode), "width");
        private static readonly FieldInfo HeightF = AccessTools.Field(typeof(RDNode), "height");

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
                if (AxeTreeMeta.Render.Layout != "bands") return;   // stock -> leave the tree untouched
                RDController ctrl = RDController.Instance;
                if (ctrl == null || ctrl.nodes == null || ctrl.nodes.Count == 0) return;

                // Stock (cfg) position envelope, read BEFORE we move anything. We fit our layout INTO this
                // box so nothing lands outside the scroll content (which is sized for the stock tree).
                float sMinX = 1e9f, sMaxX = -1e9f, sMinY = 1e9f, sMaxY = -1e9f;
                foreach (RDNode rd in ctrl.nodes)
                {
                    if (rd == null || PosField == null) continue;
                    Vector3 sp = (Vector3)PosField.GetValue(rd);
                    if (sp.x < sMinX) sMinX = sp.x; if (sp.x > sMaxX) sMaxX = sp.x;
                    if (sp.y < sMinY) sMinY = sp.y; if (sp.y > sMaxY) sMaxY = sp.y;
                }

                // The in-game tree can contain DUPLICATE RDNodes per techID (e.g. a stray editor TechTree
                // in the DB). Build the layout model on UNIQUE ids only, else duplicates inflate the band
                // stacking; then apply the computed position to EVERY RDNode of that id so dups stack.
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

                var discOrder = new Dictionary<string, int>();
                foreach (var kv in AxeTreeMeta.Disciplines) discOrder[kv.Key] = kv.Value.Order;

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
                float ay = mMaxY > mMinY ? (sMaxY - sMinY) / (mMaxY - mMinY) : 1f;
                if (FLIP_Y) ay = -ay;
                float by = (FLIP_Y ? sMaxY : sMinY) - ay * mMinY;
                foreach (AxeTreeLayout.LNode ln in lnodes) { ln.X = ax * ln.X + bx; ln.Y = ay * ln.Y + by; }
                foreach (AxeTreeLayout.LEdge e in edges)
                    if (e.Waypoints != null)
                        for (int i = 0; i < e.Waypoints.Count; i++)
                            e.Waypoints[i] = new Vector2(ax * e.Waypoints[i].x + bx, ay * e.Waypoints[i].y + by);

                var posById = new Dictionary<string, Vector2>(lnodes.Count);
                foreach (AxeTreeLayout.LNode ln in lnodes) posById[ln.Id] = new Vector2(ln.X, ln.Y);
                int placed = 0;
                foreach (RDNode rd in ctrl.nodes)
                {
                    string id = rd?.tech?.techID;
                    if (id != null && posById.TryGetValue(id, out Vector2 p)) { SetPos(rd, p.x, p.y); placed++; }
                }

                if (AxeTreeMeta.Render.LaneRouting)
                {
                    AxeTreeLayout.ComputeSlots(edges, byId, AxeTreeMeta.Render.Fan);   // nodes render 42x39; the
                    // fan endpoint offset is in Y, so it must follow the Y-flip (ay<0) to stay on the node's side.
                    AxeTreeLayout.BuildLaneRoutes(lnodes, edges, NODE_W, NODE_H * Mathf.Sign(ay), AxeTreeMeta.Render.LanePitch);
                    foreach (AxeTreeLayout.LEdge e in edges)
                        if (e.LaneGeom != null) Routes[e.From + ">" + e.To] = e.LaneGeom;
                }

                ready = true;
                Debug.Log($"[AXE] render-port: {lnodes.Count} unique nodes ({placed} RDNodes placed), {Routes.Count} edges lane-routed " +
                          $"(layout={AxeTreeMeta.Render.Layout} lane={AxeTreeMeta.Render.LaneRouting} fan={AxeTreeMeta.Render.Fan})");
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
                    if (sr.content != null) Debug.Log($"[AXE] DUMP content rect={sr.content.rect} sizeDelta={sr.content.sizeDelta} anchoredPos={sr.content.anchoredPosition}");
                    if (sr.viewport != null) Debug.Log($"[AXE] DUMP viewport rect={sr.viewport.rect}");
                }
                RDNode s = ctrl.nodes[0];
                float w = WidthF != null ? (float)WidthF.GetValue(s) : -1f;
                float h = HeightF != null ? (float)HeightF.GetValue(s) : -1f;
                Vector3 gp = s.graphics != null ? s.graphics.transform.position : Vector3.zero;
                Debug.Log($"[AXE] DUMP node0 id={s.tech?.techID} w={w:F1} h={h:F1} transform.pos={s.transform.position} localPos={s.transform.localPosition} graphics.pos={gp}");
                Debug.Log($"[AXE] DUMP node0 anchorR={s.GetPosition(RDNode.Anchor.RIGHT, Vector3.zero)} anchorL={s.GetPosition(RDNode.Anchor.LEFT, Vector3.zero)}");
                Transform root = ctrl.RDNodeRoot;
                if (root != null) Debug.Log($"[AXE] DUMP RDNodeRoot pos={root.position} localScale={root.localScale} euler={root.eulerAngles}");
            }
            catch (Exception e) { Debug.LogError("[AXE] DUMP failed: " + e); }
        }

        // Replace the stock elbow with the precomputed lane route (local pos-space -> world).
        // __0 = the original's first arg (the Parent) bound positionally, so we don't depend on its name.
        private static bool GetVectorArray_Prefix(RDNode __instance, RDNode.Parent __0, ref List<Vector2> __result)
        {
            if (!ready || !AxeTreeMeta.Render.LaneRouting) return true;
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

        // Tint each node's icon + its incident (parent) edges by discipline colour, AFTER stock UpdateGraphics
        // set state colours. Runs on spawn, on state changes, and on the lineage-highlight's resets — so the
        // discipline colour is the persistent base the highlight dims relative to.
        private static void UpdateGraphics_Postfix(RDNode __instance)
        {
            if (!ready || !AxeTreeMeta.Render.DiscColor) return;
            try
            {
                string id = __instance?.tech?.techID;
                if (id == null || !AxeTreeMeta.Nodes.TryGetValue(id, out AxeTreeMeta.NodeMeta m)) return;
                if (AxeTreeMeta.Disciplines.TryGetValue(m.Discipline, out AxeTreeMeta.DiscMeta d))
                    __instance.graphics?.SetIconColor(d.Color);
                if (__instance.parents == null) return;
                foreach (RDNode.Parent par in __instance.parents)   // edge coloured by its SOURCE discipline
                {
                    string from = par?.parent?.node?.tech?.techID;
                    if (from != null && AxeTreeMeta.Nodes.TryGetValue(from, out AxeTreeMeta.NodeMeta pm)
                        && AxeTreeMeta.Disciplines.TryGetValue(pm.Discipline, out AxeTreeMeta.DiscMeta pd))
                    {
                        if (par.line != null) par.line.color = pd.Color;
                        if (par.arrowHead != null) par.arrowHead.color = pd.Color;
                    }
                }
            }
            catch (Exception e) { Debug.LogException(e); }
        }

        // Hover-trace lineage (like the HTML) + click empty background to deselect. Both key off the node
        // under the pointer (UI raycast). Stock R&D only deselects when you re-click the node.
        private Vector3 _downPos;
        private bool _dragged;
        private RDNode _hoverNode;
        private static readonly List<RaycastResult> _rayHits = new List<RaycastResult>();

        private void Update()
        {
            RDController ctrl = RDController.Instance;
            if (ctrl == null) { _hoverNode = null; return; }
            RDNode over = NodeUnderPointer();

            // Hover: highlight the hovered node's lineage; on hover-out revert to the pinned selection (or
            // stock). Only re-highlight when the hovered node changes. Click still pins via ShowNodePanel.
            if (AxeTreeMeta.Render.Hover && over != _hoverNode)
            {
                _hoverNode = over;
                try
                {
                    if (over != null) AxeHighlighter.Apply(ctrl, over);
                    else if (ctrl.node_selected != null) AxeHighlighter.Apply(ctrl, ctrl.node_selected);
                    else AxeHighlighter.Clear(ctrl);
                }
                catch (Exception e) { Debug.LogException(e); }
            }

            // Click (not drag/pan) on empty background -> deselect.
            if (Input.GetMouseButtonDown(0)) { _downPos = Input.mousePosition; _dragged = false; }
            else if (Input.GetMouseButton(0) && !_dragged && (Input.mousePosition - _downPos).sqrMagnitude > 25f) _dragged = true;
            else if (Input.GetMouseButtonUp(0) && !_dragged && over == null && ctrl.node_selected != null)
            {
                try { ctrl.ShowNothingPanel(); } catch (Exception e) { Debug.LogException(e); }
            }
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
            if (!ready || !AxeTreeMeta.Render.Legend || RDController.Instance == null || AxeTreeMeta.Disciplines.Count == 0) return;
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
            Color prev = GUI.color;
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
            GUI.color = prev;
        }
    }
}
