using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Marks AXE's capability display-tokens (avionics tiers, DSN tracking-station levels) as unlocked the
    /// moment their tech node is researched, so they read as <i>granted</i> in R&amp;D rather than a 0-cost
    /// purchase prompt — the same thing RP-1's ProceduralAvionicsTechManager does with
    /// <c>PartUpgradeManager.Handler.SetUnlocked</c>. These tokens carry no stat MODULE: the real tier effect
    /// is applied elsewhere (ModuleAxeAvionics reads the researched node directly; the tracking-station level
    /// is enforced by AxeTrackingStationGate). Token names come from the generated AXE_GRANT_UPGRADES config
    /// node (design/Tree/AxeGrantUpgrades.cfg).
    ///
    /// EveryScene so a sweep runs whenever the player is somewhere R&amp;D state exists (it also catches an
    /// already-researched tree on load), plus a live hook on OnTechnologyResearched. SetUnlocked is idempotent,
    /// applies no stats and (unlike a purchase) charges nothing, so re-running it is harmless.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EveryScene, false)]
    public class AxeGrantUpgradeUnlock : MonoBehaviour
    {
        private static string[] _names;

        private void Start()
        {
            if (_names == null) LoadNames();
            Sweep();
            GameEvents.OnTechnologyResearched.Add(OnResearched);
        }

        private void OnDestroy()
        {
            GameEvents.OnTechnologyResearched.Remove(OnResearched);
        }

        private void OnResearched(GameEvents.HostTargetAction<RDTech, RDTech.OperationResult> _)
        {
            Sweep();
        }

        private static void LoadNames()
        {
            var list = new List<string>();
            foreach (ConfigNode n in GameDatabase.Instance.GetConfigNodes("AXE_GRANT_UPGRADES"))
                list.AddRange(n.GetValues("upgrade"));
            _names = list.ToArray();
        }

        private static void Sweep()
        {
            if (_names == null || _names.Length == 0) return;
            if (PartUpgradeManager.Handler == null || HighLogic.CurrentGame == null) return;
            // Career/Science only — sandbox has every upgrade unlocked already.
            Game.Modes mode = HighLogic.CurrentGame.Mode;
            if (mode != Game.Modes.CAREER && mode != Game.Modes.SCIENCE_SANDBOX) return;

            foreach (string name in _names)
            {
                PartUpgradeHandler.Upgrade upg = PartUpgradeManager.Handler.GetUpgrade(name);
                if (upg == null || string.IsNullOrEmpty(upg.techRequired)) continue;
                if (ResearchAndDevelopment.GetTechnologyState(upg.techRequired) == RDTech.State.Available)
                    PartUpgradeManager.Handler.SetUnlocked(name, true);
            }
        }
    }
}
