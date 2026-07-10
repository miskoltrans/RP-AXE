using System.Collections;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Flight-termination self-destruct — the "Range Safety" every real launcher carries. A PAW button
    /// and action group blow the vessel leaf-first (skipping ProceduralFairingSide children so
    /// interstages don't orphan a still-live lower stage). Ported verbatim from RP-1 (destruction
    /// algorithm originally from TAC Self Destruct). Class name kept so AXE's PartHacks.cfg patch, which
    /// already adds `MODULE { name = ModuleRangeSafety }` to avionics parts (and strips it from crewed
    /// ones), resolves — that config was dead until this class existed.
    /// </summary>
    public class ModuleRangeSafety : PartModule
    {
        [KSPEvent(guiActive = true, guiName = "Range Safety")]
        public void BoomEvent() => SpawnConfirmationDialog();

        private void SpawnConfirmationDialog()
        {
            var options = new DialogGUIBase[]
            {
                new DialogGUIButton("Yes", Boom),
                new DialogGUIButton("No", () => { })
            };
            var dialog = new MultiOptionDialog("ConfirmRangeSafety", "Destroy Vessel?", "Range Safety", HighLogic.UISkin, 300, options);
            PopupDialog.SpawnPopupDialog(dialog, true, HighLogic.UISkin);
        }

        [KSPAction("Range Safety")]
        public void BoomAction(KSPActionParam param) => Boom();

        public void Boom()
        {
            FlightLogger.fetch.LogEvent("Range Safety: Destruction initiated");
            ExecuteBoom();
        }

        public void ExecuteBoom()
        {
            if (part != vessel.rootPart)
            {
                ModuleRangeSafety mrs = vessel.rootPart.Modules.GetModule<ModuleRangeSafety>();
                if (mrs == null)
                    mrs = vessel.rootPart.AddModule("ModuleRangeSafety") as ModuleRangeSafety;
                mrs.ExecuteBoom();
            }
            else
            {
                StartCoroutine(BoomRoutine());
            }
        }

        // Destruction algorithm borrowed from TAC Self Destruct.
        private void ExplodeLeafParts(Part p)
        {
            int c = p.children.Count;
            if (c == 0)
            {
                p.explode();
            }
            else
            {
                bool passAgain = true;
                for (int i = c - 1; i >= 0; --i)
                {
                    Part cP = p.children[i];
                    // Fairing sides hold up interstages — blowing them would split off the live lower
                    // stage as a new vessel that never gets destroyed. Skip them on the first pass.
                    if (cP.Modules.Contains("ProceduralFairingSide"))
                        continue;

                    ExplodeLeafParts(cP);
                    passAgain = false;
                }
                if (passAgain)
                    for (int i = c - 1; i >= 0; --i)
                        ExplodeLeafParts(p.children[i]);
            }
        }

        private IEnumerator BoomRoutine()
        {
            yield return new WaitForFixedUpdate();
            while (vessel.Parts.Count > 1)
            {
                ExplodeLeafParts(vessel.rootPart);
                yield return new WaitForFixedUpdate();
            }
            vessel.rootPart.explode();
        }
    }
}
