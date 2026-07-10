using System.Reflection;
using System.Text;
using HarmonyLib;
using KSP.UI.Screens;

namespace RPAxe
{
    /// <summary>
    /// Appends the list of parts a tech node unlocks to that node's R&amp;D tooltip — the "what does
    /// this node actually give me?" info, useful when planning a route through AXE's engineering tree.
    /// A postfix on RDNode.UpdateGraphics (which stock uses to build the tooltip): it rewrites the
    /// tooltip body as stock's caption + the assigned-part titles, so it stays idempotent across the
    /// frequent redraws (never appends to itself). Ported from the standalone slice of RP-1's RDNode
    /// patch (the rest of that patch was KCT research-queue colouring — sacked).
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
            if (parts == null || parts.Count == 0) return;

            object tooltip = TooltipField.GetValue(__instance);
            if (tooltip == null) return;

            if (!_textResolved)
            {
                _textField = AccessTools.Field(tooltip.GetType(), "textString");
                _textResolved = true;
            }
            if (_textField == null) return;

            var sb = new StringBuilder(GetCaption.Invoke(__instance, null) as string ?? "");
            sb.Append("\n\n<b>Parts:</b>");
            foreach (AvailablePart ap in parts)
                if (ap != null) sb.Append('\n').Append(ap.title);

            _textField.SetValue(tooltip, sb.ToString());
        }
    }
}
