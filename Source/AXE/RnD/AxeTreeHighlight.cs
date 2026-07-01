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
        private static readonly Color32 DimLine = new Color32(90, 95, 105, 45);
        private static readonly Color DimIcon = new Color(1f, 1f, 1f, 0.25f);
        private static bool active;

        public static void Apply(RDController ctrl, RDNode sel)
        {
            if (ctrl == null || sel == null || ctrl.nodes == null) return;
            List<RDNode> nodes = ctrl.nodes;
            // Reset to stock colours FIRST. Selecting another node calls ShowNodePanel -> Apply again
            // WITHOUT a Clear in between, so without this reset previously-dimmed in-lineage edges stay
            // dim and the highlight decays after the first click.
            for (int i = 0; i < nodes.Count; i++)
                if (nodes[i] != null) nodes[i].UpdateGraphics();
            HashSet<RDNode> lineage = Lineage(sel);
            for (int i = 0; i < nodes.Count; i++)
            {
                RDNode n = nodes[i];
                if (n == null) continue;
                bool inLineage = lineage.Contains(n);
                if (!inLineage && n.graphics != null) n.graphics.SetIconColor(DimIcon);   // lit nodes keep stock colour
                if (n.parents == null) continue;
                for (int p = 0; p < n.parents.Length; p++)
                {
                    RDNode.Parent par = n.parents[p];
                    if (par == null) continue;
                    RDNode parentNode = par.parent != null ? par.parent.node : null;
                    // an edge is "in the lineage" only if BOTH ends are (the chain to/from the selection)
                    bool edgeIn = inLineage && parentNode != null && lineage.Contains(parentNode);
                    if (edgeIn) continue;
                    if (par.line != null) par.line.color = DimLine;
                    if (par.arrowHead != null) par.arrowHead.color = DimLine;
                }
            }
            active = true;
        }

        public static void Clear(RDController ctrl)
        {
            if (!active || ctrl == null || ctrl.nodes == null) return;
            active = false;
            List<RDNode> nodes = ctrl.nodes;
            for (int i = 0; i < nodes.Count; i++)
                if (nodes[i] != null) nodes[i].UpdateGraphics();   // recompute stock colours (lines + icon tint)
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
