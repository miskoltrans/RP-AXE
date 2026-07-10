using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Per-career persistence for one-time informational tips: a small set of "already shown" keys so a
    /// nudge fires once and never again for that save. (AXE has no RP0Settings equivalent to hang these
    /// off, so a dedicated ScenarioModule is the clean store; future one-shot tips can reuse it.)
    /// </summary>
    [KSPScenario(ScenarioCreationOptions.AddToAllGames,
        GameScenes.EDITOR, GameScenes.FLIGHT, GameScenes.SPACECENTER, GameScenes.TRACKSTATION)]
    public class AxeTipState : ScenarioModule
    {
        public static AxeTipState Instance { get; private set; }

        private readonly HashSet<string> _shown = new HashSet<string>();

        public override void OnAwake()
        {
            base.OnAwake();
            Instance = this;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        public bool WasShown(string key) => _shown.Contains(key);

        /// <summary>Records the tip as shown; returns true if it was newly added (i.e. not shown before).</summary>
        public bool MarkShown(string key) => _shown.Add(key);

        public override void OnSave(ConfigNode node)
        {
            base.OnSave(node);
            foreach (string s in _shown) node.AddValue("shown", s);
        }

        public override void OnLoad(ConfigNode node)
        {
            base.OnLoad(node);
            _shown.Clear();
            foreach (string v in node.GetValues("shown")) _shown.Add(v);
        }
    }

    /// <summary>
    /// One-time discovery nudge for AXE's airlaunch. The feature only surfaces when you press Launch after
    /// unlocking a tech-gated envelope, so a player can miss that it exists — this fires once, the first
    /// time an editor is opened with any airlaunch envelope unlocked, and never again for that career.
    /// (The AXE-appropriate replacement for RP-1's airlaunch tip, whose text/trigger were about RP-1's
    /// Space-Center-Management simulation flow, which AXE doesn't have.) Reads only the public
    /// <see cref="Airlaunch.AxeAirlaunchTechLevel.AnyUnlocked"/>; touches nothing else in the airlaunch system.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EditorAny, false)]
    public class AxeAirlaunchTip : MonoBehaviour
    {
        private const string TipKey = "airlaunchUnlocked";
        private bool _evaluated;

        private void Update()
        {
            if (_evaluated) return;

            AxeTipState state = AxeTipState.Instance;
            if (state == null) return;   // scenario module not spun up yet; retry next frame

            _evaluated = true;

            if (state.WasShown(TipKey)) return;

            bool unlocked;
            try { unlocked = Airlaunch.AxeAirlaunchTechLevel.AnyUnlocked(); }
            catch { return; }            // a tip must never break the editor
            if (!unlocked) return;

            state.MarkShown(TipKey);
            ShowTip();
        }

        private static void ShowTip()
        {
            PopupDialog.SpawnPopupDialog(new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                "AxeAirlaunchUnlockedTip", "Airlaunch unlocked",
                "You've unlocked airlaunch capability. Press Launch in the editor to release from a " +
                "carrier at altitude and speed, instead of taking off from the runway — useful for " +
                "high-and-fast first stages you'd otherwise have to fly up yourself.",
                "OK", false, HighLogic.UISkin);
        }
    }
}
