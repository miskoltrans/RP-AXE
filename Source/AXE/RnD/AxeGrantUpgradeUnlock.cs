using System.Collections;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// UPGRADES ARE GRANTED, NEVER SOLD. Marks every <c>PARTUPGRADE</c> whose tech node is researched as
    /// unlocked, so R&amp;D shows it owned rather than for sale — the same thing RP-1's
    /// ProceduralAvionicsTechManager does with <c>PartUpgradeManager.Handler.SetUnlocked</c> for its avionics
    /// tiers, applied to the whole category. The funds side is <c>%entryCost = 0</c> on one wildcard in the
    /// generated design/Tree/AxePartCost.cfg; this is the other half (0 alone does not unlock in stock —
    /// <c>PartUpgradeHandler.IsUnlocked</c> reads its own dictionary and never looks at the price).
    ///
    /// Why the whole category: an upgrade is a STAT on a part you already own — a tank material, an MLI
    /// wrap, a fairing size cap, a comms/solar tech level — so a price beside the parts in R&amp;D is easy to
    /// walk past, and nothing in the VAB tells you that you did (a locked tank type is simply absent from
    /// the dropdown). Research is the gate; see docs/SCIENCE.md §5d. It also settles a split rule: the
    /// avionics tiers and the Kerbalism HDD ladder were already granted while the tank/heatshield/comms
    /// ladders were billed.
    ///
    /// Two kinds of upgrade come through here and both are intended:
    ///   * display tokens (Science-Core-*/Deep-Space-*, RP0Level*TrackingStation, RFUpgrade_*,
    ///     RFTech-*-tltech*) carry no stat MODULE — the real effect lives elsewhere (ModuleAxeAvionics
    ///     reads the researched node; the tracking-station level is enforced by AxeTrackingStationGate;
    ///     RealFuels gates engine configs on EntryCostDatabase and tech levels on RF_TECHLEVELS TLTECH&lt;n&gt;);
    ///   * real upgrades whose UPGRADE block carries the stat (RealFuels tank types, ROHeatshields presets,
    ///     PFTech fairing density, HDD sizes, commsTL/solarTL) — SetUnlocked is what applies those, free.
    ///
    /// Engine variants are NOT made free by this: RealFuels asks EntryCostDatabase.IsUnlocked(&lt;config&gt;),
    /// which only its own PurchaseConfig / OnPartUpgradePurchased path writes, so SetUnlocked on a
    /// PARTUPGRADE cannot unlock a config. They stay priced by ENTRYCOSTMODS (AxeEntryCostMods.cfg) in the
    /// VAB engine-configs GUI. Either way this only ever GRANTS: it charges nothing and never gates.
    ///
    /// Triggers — EveryScene, so an already-researched tree is caught on load and re-checked whenever the
    /// player moves scenes; plus OnTechnologyResearched for the live case and onGUIRnDComplexSpawn so the
    /// R&amp;D screen can never render a stale "for sale" row. RealFuels' own EntryCostDatabase.UpdateEntry-
    /// Costs() does the same &lt;1.1 auto-unlock, but only from EntryCostManager.OnLoad, so without this an
    /// upgrade researched mid-session stayed locked until the next load. SetUnlocked is idempotent and
    /// (unlike a purchase) charges nothing, so re-running it is harmless.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EveryScene, false)]
    public class AxeGrantUpgradeUnlock : MonoBehaviour
    {
        private bool _hooked;

        private void Start()
        {
            // Career/Science only — sandbox has every upgrade unlocked already, and the main menu has no game.
            if (HighLogic.CurrentGame == null) return;
            Game.Modes mode = HighLogic.CurrentGame.Mode;
            if (mode != Game.Modes.CAREER && mode != Game.Modes.SCIENCE_SANDBOX) return;

            StartCoroutine(SweepWhenReady());
            GameEvents.OnTechnologyResearched.Add(OnResearched);
            GameEvents.onGUIRnDComplexSpawn.Add(OnRnDSpawn);
            _hooked = true;
        }

        private void OnDestroy()
        {
            if (!_hooked) return;
            GameEvents.OnTechnologyResearched.Remove(OnResearched);
            GameEvents.onGUIRnDComplexSpawn.Remove(OnRnDSpawn);
        }

        // Instance handlers, never static: the EvtDelegate ctor dereferences evt.Target unguarded, so
        // handing GameEvents a static method NREs at boot.
        private void OnResearched(GameEvents.HostTargetAction<RDTech, RDTech.OperationResult> _) => Sweep();

        private void OnRnDSpawn() => Sweep();

        /// <summary>
        /// R&amp;D's tech list is loaded when its ScenarioModule is created, so a non-null Instance is the
        /// readiness test — but the module can appear a frame or more after this addon's Start, and a sweep
        /// before then reads every node as Unavailable and silently grants nothing. Wait for it rather than
        /// latching that no-op (a "lazily-loaded module reads live-but-empty" bug). Bounded so a scene that
        /// genuinely has no R&amp;D never spins forever; a miss would self-heal on the next scene change anyway.
        /// </summary>
        private IEnumerator SweepWhenReady()
        {
            for (int i = 0; i < 600 && ResearchAndDevelopment.Instance == null; i++)
                yield return null;
            Sweep();
        }

        private static void Sweep()
        {
            if (PartUpgradeManager.Handler == null || ResearchAndDevelopment.Instance == null) return;

            // Enumerates the handler's name->Upgrade dictionary; SetUnlocked writes a different one
            // (Upgrade->bool), so mutating while enumerating here is safe.
            foreach (PartUpgradeHandler.Upgrade upg in PartUpgradeManager.Handler)
            {
                if (upg == null || string.IsNullOrEmpty(upg.techRequired)) continue;
                if (ResearchAndDevelopment.GetTechnologyState(upg.techRequired) == RDTech.State.Available)
                    PartUpgradeManager.Handler.SetUnlocked(upg.name, true);
            }
        }
    }
}
