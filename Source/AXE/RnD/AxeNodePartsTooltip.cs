using System.Reflection;
using System.Text;
using HarmonyLib;
using KSP.UI.Screens;
using RPAxe.RnD;

namespace RPAxe
{
    /// <summary>
    /// Appends what a tech node actually gives you to its R&amp;D tooltip — the "is this node worth
    /// buying?" info, useful when planning a route through AXE's engineering tree. Two blocks:
    ///
    ///   * <b>Parts</b> — RDTech.partsAssigned, i.e. what stock already lists in the node.
    ///   * <b>Experiments</b> — science unlocks that are NOT parts, and so appear nowhere in stock
    ///     R&amp;D at all: Kerbalism serves an experiment as a <c>Configure</c> SETUP on probe cores /
    ///     labs / EVA kits gated by <c>tech = &lt;node&gt;</c>, and AXE's crewed science as a
    ///     <c>techRequired</c> EXPERIMENT_DEFINITION. A node can therefore carry real, sizeable
    ///     payload and show a completely empty tooltip — tel_minitrackInterferometry (T3) unlocks the
    ///     whole Orbital Perturbation experiment and looked like a dead node. The list comes from
    ///     AxeTreeMeta (design/Tree/AxeTreeMeta.cfg, emitted by tools/build_tree.py from the same
    ///     scan the tree viewer uses, tools/experiment_index.py).
    ///
    /// A postfix on RDNode.UpdateGraphics (which stock uses to build the tooltip): it rewrites the
    /// tooltip body as stock's caption + our blocks, so it stays idempotent across the frequent
    /// redraws (never appends to itself). Ported from the standalone slice of RP-1's RDNode patch
    /// (the rest of that patch was KCT research-queue colouring — sacked).
    ///
    /// RDNode.tooltip and RDNode.GetTooltipCaption() are non-public in stock Assembly-CSharp (RP-1
    /// builds against a publicized copy; AXE builds against the raw assembly), so they're reached by
    /// reflection here. If any member can't be resolved the postfix simply no-ops.
    /// </summary>
    [HarmonyPatch(typeof(RDNode))]
    internal static class AxeNodePartsTooltip
    {
        private static readonly FieldInfo TooltipField = AccessTools.Field(typeof(RDNode), "tooltip");
        private static readonly MethodInfo GetCaption = AccessTools.Method(typeof(RDNode), "GetTooltipCaption");
        private static FieldInfo _textField;
        private static bool _textResolved;

        [HarmonyPostfix]
        [HarmonyPatch("UpdateGraphics")]
        internal static void Postfix_UpdateGraphics(RDNode __instance)
        {
            if (TooltipField == null || GetCaption == null || __instance.tech == null) return;

            var parts = __instance.tech.partsAssigned;
            bool hasParts = parts != null && parts.Count > 0;

            AxeTreeMeta.EnsureLoaded();
            AxeTreeMeta.ExperimentMeta[] experiments = null;
            if (!string.IsNullOrEmpty(__instance.tech.techID)
                && AxeTreeMeta.Nodes.TryGetValue(__instance.tech.techID, out AxeTreeMeta.NodeMeta meta))
                experiments = meta.Experiments;

            // Nothing of ours to add -> leave stock's tooltip exactly as it was.
            if (!hasParts && experiments == null) return;

            object tooltip = TooltipField.GetValue(__instance);
            if (tooltip == null) return;

            if (!_textResolved)
            {
                _textField = AccessTools.Field(tooltip.GetType(), "textString");
                _textResolved = true;
            }
            if (_textField == null) return;

            var sb = new StringBuilder(GetCaption.Invoke(__instance, null) as string ?? "");
            if (hasParts)
            {
                sb.Append("\n\n<b>Parts:</b>");
                foreach (AvailablePart ap in parts)
                    if (ap != null) sb.Append('\n').Append(ap.title);
            }
            if (experiments != null)
            {
                sb.Append("\n\n<b>Experiments:</b>");
                foreach (AxeTreeMeta.ExperimentMeta e in experiments)
                {
                    sb.Append('\n').Append(e.Name);
                    if (e.Sci > 0) sb.Append(" — ").Append(e.Sci).Append(" science");
                }
                // The one thing the player cannot guess: these are not parts in the VAB list, they are
                // options inside a part's Configure menu. Say where, once, not once per row — and name
                // the menu only when every experiment on this node shares it (a node can mix groups).
                string where = experiments[0].Group;
                foreach (AxeTreeMeta.ExperimentMeta e in experiments)
                    if (e.Group != where) { where = ""; break; }
                sb.Append(string.IsNullOrEmpty(where)
                          ? "\n<i>Fitted from a part's Configure menu.</i>"
                          : "\n<i>Fitted from a part's Configure menu (" + where + ").</i>");
            }

            _textField.SetValue(tooltip, sb.ToString());
        }
    }
}
