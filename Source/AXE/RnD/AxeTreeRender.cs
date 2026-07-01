using System;
using System.Collections.Generic;
using System.Reflection;
using HarmonyLib;
using KSP.UI.Screens;
using UnityEngine;

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
        private const bool FLIP_Y = true;              // prototype y-down -> KSP y-up (flip if bands look inverted)

        private static bool installed;
        private static bool ready;
        private static readonly Dictionary<string, List<Vector2>> Routes = new Dictionary<string, List<Vector2>>();
        private static readonly FieldInfo PosField = AccessTools.Field(typeof(RDNode), "pos");

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

                float nodeSz = AxeTreeMeta.NodeSize;   // runtime width isn't set until Setup; the cfg value is fine
                AxeTreeLayout.LayoutBands(lnodes, edges, byId, discOrder, AxeTreeMeta.TierWidth,
                    AxeTreeMeta.MarginX, AxeTreeMeta.MarginY, nodeSz, SPACING_F, false);

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
                    AxeTreeLayout.ComputeSlots(edges, byId, AxeTreeMeta.Render.Fan);
                    AxeTreeLayout.BuildLaneRoutes(lnodes, edges, nodeSz, nodeSz, AxeTreeMeta.Render.LanePitch);
                    foreach (AxeTreeLayout.LEdge e in edges)
                        if (e.LaneGeom != null) Routes[e.From + ">" + e.To] = e.LaneGeom;
                }

                ready = true;
                Debug.Log($"[AXE] render-port: {lnodes.Count} unique nodes ({placed} RDNodes placed), {Routes.Count} edges lane-routed " +
                          $"(layout={AxeTreeMeta.Render.Layout} lane={AxeTreeMeta.Render.LaneRouting} fan={AxeTreeMeta.Render.Fan})");
            }
            catch (Exception e) { Debug.LogError("[AXE] render-port OnTreeSpawn failed: " + e); ready = false; }
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
                    float lx = local[i].x, ly = FlipY(local[i].y);
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
            PosField.SetValue(rd, new Vector3(x, FlipY(y), cur.z));
        }

        private static float FlipY(float y) => FLIP_Y ? 2f * AxeTreeMeta.MarginY - y : y;
    }
}
