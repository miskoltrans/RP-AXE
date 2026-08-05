using System.Collections.Generic;
using HarmonyLib;
using KSP.UI.Screens;
using UnityEngine;

namespace RPAxe.RnD
{
    /// <summary>
    /// Enhance the STOCK R&amp;D tree (no renderer replacement): when a node is selected, highlight its
    /// full prerequisite + unlock lineage and dim everything else; restore on deselect. Ported from the
    /// RP-AXE HTML rendering prototype (tree/render/prototype). Colour-only — we set VectorLine.color /
    /// Image.color and the node icon tint, never geometry/width, so there is no Vectrosity mesh rebuild
    /// (this is exactly stock's own recolour path). Restore = re-run each node's UpdateGraphics(), which
    /// recomputes the stock research-state colours.
    ///
    /// NOTE: compiles against the Instance KSP assemblies; needs an in-game smoke pass (the R&amp;D scene,
    /// e.g. via -axe-autotest) to confirm runtime behaviour — it has not been run in-game yet.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, true)]
    public class AxeTreeHighlight : MonoBehaviour
    {
        private static bool patched;
        private void Awake()
        {
            if (patched) return;
            patched = true;
            new Harmony("rpaxe.tree.highlight").PatchAll(typeof(AxeTreeHighlight).Assembly);
            Debug.Log("[AXE] R&D tree lineage-highlight patches applied.");
        }
    }

    [HarmonyPatch(typeof(RDController), "ShowNodePanel")]
    internal static class Patch_RDController_ShowNodePanel
    {
        private static void Postfix(RDController __instance, RDNode node) => AxeHighlighter.Apply(__instance, node);
    }

    [HarmonyPatch(typeof(RDController), "ShowNothingPanel")]
    internal static class Patch_RDController_ShowNothingPanel
    {
        private static void Postfix(RDController __instance) => AxeHighlighter.Clear(__instance);
    }

    internal static class AxeHighlighter
    {
        private static readonly Color32 DimLine = new Color32(96, 101, 110, 28);        // ghost off-lineage edges
        private const float GHOST_A = 0.12f;        // off-lineage alpha (discipline / neutral tiles)
        private const float GHOST_DONE_A = 0.45f;   // off-lineage RESEARCHED: receded, but green enough to still read as done
        private static bool active;

        // Ghost a node's tile: a faint hint of its discipline colour (or neutral) at low alpha.
        // EXCEPT researched nodes: green means "done" everywhere in this tree, on the highlighted lineage or
        // off it, so a ghosted researched node keeps the DONE green (just receded) instead of reverting to a
        // discipline ghost — otherwise focusing a lineage erases the one state the player scans the tree for.
        private static Color GhostTile(RDNode n)
        {
            if (n != null && n.state == RDNode.State.RESEARCHED)
                return new Color(AxeTreeRenderHost.DoneTile.r, AxeTreeRenderHost.DoneTile.g, AxeTreeRenderHost.DoneTile.b, GHOST_DONE_A);
            if (AxeTreeMeta.TryDisciplineColor(n?.tech?.techID, out Color dc)) return new Color(dc.r, dc.g, dc.b, GHOST_A);
            return new Color(0.40f, 0.42f, 0.45f, GHOST_A);
        }

        public static void Apply(RDController ctrl, RDNode sel)
        {
            if (ctrl == null || sel == null || ctrl.nodes == null) return;
            List<RDNode> nodes = ctrl.nodes;
            HashSet<RDNode> lineage = Lineage(sel);
            // Colour-only, every node set explicitly each call (no UpdateGraphics reset -> cheap for hover +
            // no decay): ghost everything OFF the lineage; the lineage nodes + edges POP at full discipline
            // colour (locked-on-path included), matching the HTML prototype. Clear() restores via UpdateGraphics.
            for (int i = 0; i < nodes.Count; i++)
            {
                RDNode n = nodes[i];
                if (n == null) continue;
                bool inLineage = lineage.Contains(n);
                if (n.graphics != null)
                {
                    // TintTile (colour only) not PaintTile — hover repaints every node, and PaintTile's
                    // per-node transform write (icon scale) forced a full canvas rebuild each hover-move.
                    if (!inLineage) AxeTreeRenderHost.TintTile(n, GhostTile(n));                           // ghost the tile
                    else if (n.state == RDNode.State.RESEARCHED) AxeTreeRenderHost.TintTile(n, AxeTreeRenderHost.DoneTile);   // researched stays green on the lineage
                    else if (AxeTreeMeta.TryDisciplineColor(n.tech?.techID, out Color dc)) AxeTreeRenderHost.TintTile(n, dc);  // pop
                    else AxeTreeRenderHost.TintTile(n, Color.white);
                    if (!inLineage && n.graphics.searchHighlight != null) n.graphics.searchHighlight.enabled = false;   // hide state ring on ghosts
                }
                if (n.parents == null) continue;
                for (int p = 0; p < n.parents.Length; p++)
                {
                    RDNode.Parent par = n.parents[p];
                    if (par == null) continue;
                    RDNode parentNode = par.parent != null ? par.parent.node : null;
                    // an edge is "on the lineage" only if BOTH ends are (the chain to/from the selection)
                    bool edgeIn = inLineage && parentNode != null && lineage.Contains(parentNode);
                    if (edgeIn && AxeTreeMeta.TryDisciplineColor(parentNode.tech?.techID, out Color dcol))
                    {
                        // Path edge pops — at the source's discipline, or done-green once that source is
                        // researched (provenance stops mattering there; matches the resting rule).
                        Color ec = parentNode.state == RDNode.State.RESEARCHED ? AxeTreeRenderHost.DoneTile : dcol;
                        if (par.line != null) par.line.color = ec;
                        if (par.arrowHead != null) par.arrowHead.color = ec;
                    }
                    else if (!edgeIn)
                    {
                        if (par.line != null) par.line.color = DimLine;             // off-path edge ghosts
                        if (par.arrowHead != null) par.arrowHead.color = DimLine;
                    }
                }
            }
            // Dim the junction-bus branch dots off the lineage too (they're separate Images the loop above
            // doesn't touch) — otherwise they stay saturated over ghosted edges.
            var lineageIds = new HashSet<string>();
            foreach (RDNode ln in lineage) { string t = ln?.tech?.techID; if (!string.IsNullOrEmpty(t)) lineageIds.Add(t); }
            AxeTreeRenderHost.HighlightDots(lineageIds);
            active = true;
        }

        public static void Clear(RDController ctrl)
        {
            if (!active || ctrl == null || ctrl.nodes == null) return;
            active = false;
            List<RDNode> nodes = ctrl.nodes;
            // Colour-only restore (mirrors Apply), NOT stock UpdateGraphics per node: hover-off fires this on
            // every node-to-empty move + on deselect, and UpdateGraphics' postfix does a transform write per
            // node -> a full canvas rebuild (measured 66ms at 455 nodes = a visible stutter). RepaintResting
            // recomputes the same resting colours without touching transforms (~1.5ms).
            for (int i = 0; i < nodes.Count; i++)
                if (nodes[i] != null) AxeTreeRenderHost.RepaintResting(nodes[i]);
            AxeTreeRenderHost.RestoreDots();   // dots aren't RDNodes -> RepaintResting won't restore them
        }

        // Selection + all ancestors (via parents) + all descendants (via children).
        private static HashSet<RDNode> Lineage(RDNode sel)
        {
            var set = new HashSet<RDNode> { sel };
            var stack = new Stack<RDNode>();
            stack.Push(sel);
            while (stack.Count > 0)   // ancestors
            {
                RDNode n = stack.Pop();
                if (n.parents == null) continue;
                for (int i = 0; i < n.parents.Length; i++)
                {
                    RDNode pn = n.parents[i] != null && n.parents[i].parent != null ? n.parents[i].parent.node : null;
                    if (pn != null && set.Add(pn)) stack.Push(pn);
                }
            }
            stack.Push(sel);
            while (stack.Count > 0)   // descendants
            {
                RDNode n = stack.Pop();
                if (n.children == null) continue;
                for (int i = 0; i < n.children.Count; i++)
                {
                    RDNode cn = n.children[i];
                    if (cn != null && set.Add(cn)) stack.Push(cn);
                }
            }
            return set;
        }
    }
}
