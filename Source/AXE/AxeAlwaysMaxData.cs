using System;
using System.Collections;
using System.Linq;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Forces TestFlight's "parts always have maximum flight data" mode ON for RP-AXE careers, so
    /// engine/part reliability sits at each config's rated ceiling from unlock and the static-fire /
    /// test-flight DATA GRIND is bypassed. Everything else TestFlight does is untouched: the failure
    /// model, rated burn time / rated ignitions, and per-config reliability ceilings — so early engines
    /// still fail at their best-case rate, and reliability still improves by unlocking better engines,
    /// just never by grinding a given one.
    ///
    /// Why a plugin and not config: in TestFlight 2.2 the PluginData/settings.cfg "alwaysMaxData" field
    /// is DEAD — it is round-tripped to the file but read nowhere at runtime. The value the max-data
    /// logic actually reads is TestFlightManagerScenario.settingsAlwaysMaxData: a per-save [KSPField]
    /// that defaults to FALSE and is otherwise only ever set by the in-game "Parts always have Maximum
    /// Data" GUI toggle. It lives in the save's scenario module, not the GameDatabase, so it is not
    /// ModuleManager-reachable — a plugin setting the live property is the only reliable way for a
    /// distributable mod to guarantee the grind stays off across fresh careers and instance rebuilds.
    /// (Verified against decompiled TestFlightCore 2.2: TestFlightCore.TestFlightManagerScenario,
    /// public static Instance, public bool SettingsAlwaysMaxData.)
    ///
    /// Reflection (not a compile-time TestFlight reference) keeps TestFlight a soft dependency: if it
    /// is absent the addon simply no-ops. Runs on entering the Space Center; the flag persists in the
    /// save once set, so this is idempotent and cheap.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.SpaceCentre, false)]
    public class AxeAlwaysMaxData : MonoBehaviour
    {
        private void Start()
        {
            // Reliability / the data grind only exist in Career and Science modes; skip pure Sandbox so
            // we don't spin polling for a scenario module that isn't there.
            if (HighLogic.CurrentGame == null || HighLogic.CurrentGame.Mode == Game.Modes.SANDBOX)
                return;
            StartCoroutine(ApplyWhenReady());
        }

        private IEnumerator ApplyWhenReady()
        {
            Type scenarioType = AppDomain.CurrentDomain.GetAssemblies()
                .Select(a => a.GetType("TestFlightCore.TestFlightManagerScenario"))
                .FirstOrDefault(t => t != null);

            if (scenarioType == null)
            {
                Debug.Log("[AXE] TestFlight not present; always-max-data no-op.");
                yield break;
            }

            PropertyInfo instanceProp = scenarioType.GetProperty("Instance",
                BindingFlags.Public | BindingFlags.Static);
            PropertyInfo maxDataProp = scenarioType.GetProperty("SettingsAlwaysMaxData",
                BindingFlags.Public | BindingFlags.Instance);
            if (instanceProp == null || maxDataProp == null)
            {
                Debug.LogWarning("[AXE] TestFlight internals changed (Instance/SettingsAlwaysMaxData not "
                    + "found); reliability data grind left as-is.");
                yield break;
            }

            // The TF scenario module loads with the save; wait a few seconds of frames for it to appear.
            object scenario = null;
            for (int i = 0; i < 300 && scenario == null; i++)
            {
                scenario = instanceProp.GetValue(null, null);
                if (scenario == null)
                    yield return null;
            }
            if (scenario == null)
            {
                Debug.LogWarning("[AXE] TestFlightManagerScenario.Instance never appeared; could not force "
                    + "always-max-data this scene.");
                yield break;
            }

            if ((bool)maxDataProp.GetValue(scenario, null))
                yield break; // already on (persisted from a prior visit) — nothing to do

            maxDataProp.SetValue(scenario, true, null);
            Debug.Log("[AXE] TestFlight always-max-data forced ON — reliability data grind bypassed "
                + "(failure model / rated burn time unchanged).");
        }
    }
}
