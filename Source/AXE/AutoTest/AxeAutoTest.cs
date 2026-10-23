using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;   // TerminateProcess (see AutoTestUtil.HardQuit)
using Contracts;          // ContractSystem
using KSP.UI.Screens;     // SpaceCenterBuilding + facility buildings + facility-scene despawners
using UnityEngine;

namespace RPAxe.AutoTest
{
    /// <summary>
    /// Headless-ish smoke test harness, driven by <c>Plugins/PluginData/AutoTest.cfg</c>. On launch
    /// (if enabled) it starts a fresh game, then walks the configured KSC facility screens
    /// (enter → dwell → exit each), and optionally quits KSP when done. Edit the .cfg and relaunch —
    /// no rebuild needed.
    ///
    /// The point is to exercise — hands-free — the code paths that have historically thrown in RP-AXE
    /// (new-game setup, ContractConfigurator's R&amp;D / Mission Control UI). Watch <c>KSP.log</c> for
    /// the <c>[AXE][AutoTest]</c> prefix: a clean run ends with "SUCCESS:".
    /// </summary>
    internal static class AutoTestConfig
    {
        public const string CmdFlag = "-axe-autotest";   // force-enable override (regardless of cfg)
        public const string EnvVar = "AXE_AUTOTEST";

        // Defaults; overridden by AutoTest.cfg on load. Enabled MUST default false: if the cfg is
        // missing (reinstall / CKAN drops PluginData / AV quarantine) LoadFromFile writes defaults and
        // returns without touching this, so a `true` default would make a shipped install self-create a
        // career and Application.Quit() every launch. The -axe-autotest flag force-enables for dev.
        public static bool Enabled = false;
        public static Game.Modes GameMode = Game.Modes.CAREER;
        public static string SaveName = "AXE_AutoTest";
        public static string[] Screens = { "RND", "MISSIONCONTROL" };
        public static float DwellSeconds = 5f;
        public static float SettleSeconds = 2f;
        public static float StepTimeoutSeconds = 60f;
        public static float EnterAttemptSeconds = 10f;
        public static bool QuitWhenDone = true;
        public static float QuitDelaySeconds = 3f;
        // Opt-in: after the screen walk, load the Tracking Station and verify free KSCSwitcher
        // switching (site change + comms network + LastKSC persistence). Off by default so the
        // standard R&D/MC smoke test is unchanged. See AxeKscSwitchSelfTest.
        public static bool KscSwitchTest = false;
        // Opt-in dev sweep: after the screen walk, open the VAB and price every .craft in the install
        // (per-part cost breakdown -> PluginData/craft-prices.csv). Feeds the economy pass; the editor
        // scene is required because procedural part costs only resolve on a loaded ShipConstruct.
        // See AxeCraftPricer.
        public static bool PriceCraftTest = false;
        // Opt-in: after the screen walk, launch a probe into orbit and measure the over-capacity control
        // corruption (shipped vs the 0.9.0 double application). See AxeAvionicsFlightTest.
        public static bool AvionicsTest = false;

        // Per-session state (statics persist until the assembly reloads, i.e. KSP restart).
        public static bool CareerStarted;
        public static bool SequenceDone;

        private static bool _loaded;

        public static void EnsureLoaded()
        {
            if (_loaded) return;
            _loaded = true;

            try { LoadFromFile(); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest] config load failed, using defaults: " + e); }

            // Command-line flag / env var force-enable, regardless of the cfg's 'enabled'.
            try
            {
                bool flag = Environment.GetCommandLineArgs().Any(a => string.Equals(a, CmdFlag, StringComparison.OrdinalIgnoreCase));
                string env = Environment.GetEnvironmentVariable(EnvVar);
                bool envOn = !string.IsNullOrEmpty(env) &&
                             (env == "1" || env.Equals("true", StringComparison.OrdinalIgnoreCase) || env.Equals("yes", StringComparison.OrdinalIgnoreCase));
                if (flag || envOn) { Enabled = true; Debug.Log("[AXE][AutoTest] force-enabled via " + (flag ? CmdFlag : EnvVar) + "."); }
                if (Environment.GetCommandLineArgs().Any(a => string.Equals(a, AxeAvionicsFlightTest.CmdFlag, StringComparison.OrdinalIgnoreCase)))
                {
                    Enabled = true;
                    AvionicsTest = true;
                    Debug.Log("[AXE][AutoTest] avionics flight test enabled via " + AxeAvionicsFlightTest.CmdFlag + ".");
                }
            }
            catch { /* args/env unavailable */ }

            Debug.Log("[AXE][AutoTest] config: enabled=" + Enabled + " mode=" + GameMode + " save='" + SaveName +
                      "' screens=[" + string.Join(",", Screens) + "] dwell=" + DwellSeconds + "s quitWhenDone=" + QuitWhenDone);
        }

        /// <summary>.../GameData/RP-AXE/Plugins/PluginData/AutoTest.cfg (next to AXE.dll).</summary>
        public static string ConfigPath
        {
            get
            {
                string pluginsDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                return Path.Combine(Path.Combine(pluginsDir, "PluginData"), "AutoTest.cfg");
            }
        }

        private static void LoadFromFile()
        {
            string path = ConfigPath;
            if (!File.Exists(path))
            {
                Debug.Log("[AXE][AutoTest] no config at " + path + "; writing defaults.");
                WriteDefault(path);
                return;
            }

            ConfigNode root = ConfigNode.Load(path);
            ConfigNode n = root?.GetNode("AXE_AUTOTEST");
            if (n == null) { Debug.LogWarning("[AXE][AutoTest] config has no AXE_AUTOTEST node; using defaults."); return; }

            Enabled = ParseBool(n.GetValue("enabled"), Enabled);
            GameMode = ParseMode(n.GetValue("gameMode"), GameMode);
            if (n.HasValue("saveName")) SaveName = n.GetValue("saveName").Trim();
            DwellSeconds = ParseFloat(n.GetValue("dwellSeconds"), DwellSeconds);
            SettleSeconds = ParseFloat(n.GetValue("settleSeconds"), SettleSeconds);
            StepTimeoutSeconds = ParseFloat(n.GetValue("stepTimeoutSeconds"), StepTimeoutSeconds);
            EnterAttemptSeconds = ParseFloat(n.GetValue("enterAttemptSeconds"), EnterAttemptSeconds);
            QuitWhenDone = ParseBool(n.GetValue("quitWhenDone"), QuitWhenDone);
            QuitDelaySeconds = ParseFloat(n.GetValue("quitDelaySeconds"), QuitDelaySeconds);
            KscSwitchTest = ParseBool(n.GetValue("kscSwitchTest"), KscSwitchTest);
            PriceCraftTest = ParseBool(n.GetValue("priceCraftTest"), PriceCraftTest);
            AvionicsTest = ParseBool(n.GetValue("avionicsTest"), AvionicsTest);

            if (n.HasValue("screens"))
            {
                string[] list = n.GetValue("screens")
                    .Split(new[] { ',', ';', ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries)
                    .Select(s => s.Trim().ToUpperInvariant())
                    .Where(s => s.Length > 0)
                    .ToArray();
                if (list.Length > 0) Screens = list;
            }
        }

        private static void WriteDefault(string path)
        {
            try
            {
                string dir = Path.GetDirectoryName(path);
                if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
                File.WriteAllText(path, DefaultCfgText);
                Debug.Log("[AXE][AutoTest] wrote default config to " + path);
            }
            catch (Exception e) { Debug.LogWarning("[AXE][AutoTest] could not write default config: " + e.Message); }
        }

        private static bool ParseBool(string v, bool def)
        {
            if (string.IsNullOrEmpty(v)) return def;
            v = v.Trim();
            if (v == "1" || v.Equals("true", StringComparison.OrdinalIgnoreCase) || v.Equals("yes", StringComparison.OrdinalIgnoreCase)) return true;
            if (v == "0" || v.Equals("false", StringComparison.OrdinalIgnoreCase) || v.Equals("no", StringComparison.OrdinalIgnoreCase)) return false;
            return def;
        }

        private static float ParseFloat(string v, float def)
        {
            if (string.IsNullOrEmpty(v)) return def;
            return float.TryParse(v.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out float f) ? f : def;
        }

        private static Game.Modes ParseMode(string v, Game.Modes def)
        {
            if (string.IsNullOrEmpty(v)) return def;
            try { return (Game.Modes)Enum.Parse(typeof(Game.Modes), v.Trim(), true); }
            catch { Debug.LogWarning("[AXE][AutoTest] unknown gameMode '" + v + "'; using " + def + "."); return def; }
        }

        // Kept in sync with GameData/RP-AXE/Plugins/PluginData/AutoTest.cfg (written if that file is missing).
        private const string DefaultCfgText =
@"// RP-AXE AutoTest harness settings. Edit and relaunch KSP (no rebuild needed).
AXE_AUTOTEST
{
    // Run the automated test on launch? (-axe-autotest / AXE_AUTOTEST=1 force-enable regardless.)
    enabled = false

    // New game to create: CAREER, SCIENCE_SANDBOX, or SANDBOX.
    gameMode = CAREER
    saveName = AXE_AutoTest

    // Ordered facility screens to enter -> dwell -> exit.
    // Tokens: RND, MISSIONCONTROL, ADMINISTRATION, ASTRONAUTCOMPLEX.
    screens = RND, MISSIONCONTROL

    // Timing (seconds).
    dwellSeconds = 5
    settleSeconds = 2
    stepTimeoutSeconds = 60

    // Close KSP automatically when the run finishes (success or failure)?
    quitWhenDone = true
    quitDelaySeconds = 3

    // Opt-in extra: after the screens, load the Tracking Station and verify free KSCSwitcher
    // switching (site change + comms ground-station network + LastKSC persistence to the .sfs).
    kscSwitchTest = false

    // Opt-in dev sweep: after the screens, open the VAB and price every .craft in the install,
    // writing a per-part cost breakdown to PluginData/craft-prices.csv. Procedural part costs only
    // resolve on a loaded ShipConstruct, so this has to run in the editor scene.
    priceCraftTest = false

    // Opt-in dev test: after the screens, launch a one-part probe into orbit and measure the
    // over-capacity control corruption at 2/5/10/20% over budget, as shipped and as 0.9.0 applied it
    // (twice). Results: [AXE][AutoTest][AVI-FLIGHT] lines + <KSP>/axe_autotest/avionics-flight.csv.
    // Also: -axe-autotest-avionics on the command line.
    avionicsTest = false
}
";
    }

    /// <summary>A KSC facility screen the harness can drive.</summary>
    internal class ScreenDef
    {
        public readonly string Key;
        public readonly Type Building;     // SpaceCenterBuilding subclass to find + EnterBuilding()
        public readonly Type Despawner;    // *SceneDespawner present while the screen is open; BtnExit() leaves
        public readonly bool NeedsRnD;       // career scenario prerequisites before it's safe to enter
        public readonly bool NeedsContracts;

        public ScreenDef(string key, Type building, Type despawner, bool needsRnD, bool needsContracts)
        {
            Key = key; Building = building; Despawner = despawner; NeedsRnD = needsRnD; NeedsContracts = needsContracts;
        }
    }

    internal static class ScreenRegistry
    {
        public static ScreenDef Resolve(string token)
        {
            switch (token)
            {
                case "RND": case "R&D": case "RESEARCH": case "RESEARCHANDDEVELOPMENT":
                    return new ScreenDef("R&D", typeof(RnDBuilding), typeof(RDSceneDespawner), true, false);
                case "MC": case "MISSIONCONTROL": case "MISSION":
                    return new ScreenDef("Mission Control", typeof(MissionControlBuilding), typeof(MCDespawner), false, true);
                case "ADMIN": case "ADMINISTRATION":
                    return new ScreenDef("Administration", typeof(AdministrationFacility), typeof(AdministrationSceneDespawner), false, false);
                case "AC": case "ASTRONAUT": case "ASTRONAUTCOMPLEX":
                    return new ScreenDef("Astronaut Complex", typeof(AstronautComplexFacility), typeof(ACSceneDespawner), false, false);
                default:
                    return null;
            }
        }
    }

    /// <summary>Shared helpers for the harness.</summary>
    internal static class AutoTestUtil
    {
        [DllImport("kernel32.dll")] private static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll", SetLastError = true)] private static extern bool TerminateProcess(IntPtr handle, uint exitCode);

        /// <summary>
        /// Exit the process WITHOUT running Unity/Mono teardown.
        ///
        /// <c>Application.Quit()</c> unwinds the runtime, which races with editor work still in flight
        /// (RealFuels' UpdateUsedBySets, craft-thumbnail autogen) and reliably access-violates at
        /// UnityPlayer+0x612BC4 — a dangling-pointer read on a Unity worker thread while Mono is
        /// already in mono_threads_set_shutting_down. It reproduced on 8/8 runs at that exact offset
        /// with 85 MB..3.8 GB of free RAM, so it is a shutdown race, not memory pressure.
        ///
        /// The crash is harmless (it lands after SUCCESS is logged and every artifact is flushed) but
        /// it leaves a crash dump and a nonzero exit code. Teardown buys a smoke test nothing, so skip
        /// it. Callers must keep their pre-quit dwell: TerminateProcess drops anything still sitting in
        /// KSP.log's buffer.
        /// </summary>
        public static void HardQuit()
        {
            Debug.Log("[AXE][AutoTest] hard-exit (skipping Unity teardown; see AutoTestUtil.HardQuit).");
            try
            {
                if (TerminateProcess(GetCurrentProcess(), 0)) return;   // on success this never returns
                Debug.LogWarning("[AXE][AutoTest] TerminateProcess returned false (win32 err " +
                                 Marshal.GetLastWin32Error() + "); falling back to Application.Quit().");
            }
            catch (Exception e)
            {
                // P/Invoke unavailable — fall back to the crashy-but-working path rather than hanging.
                Debug.LogWarning("[AXE][AutoTest] HardQuit threw, falling back to Application.Quit(): " + e);
            }
            Application.Quit();
        }

        /// <summary>
        /// Wait <paramref name="seconds"/> of REAL time. Unlike <c>WaitForSeconds</c> (scaled game
        /// time, which never advances while the game is paused — e.g. inside facility screens or under
        /// a modal popup), this counts unscaled time, so dwells elapse even when timeScale is 0.
        /// </summary>
        public static IEnumerator Dwell(float seconds)
        {
            float t = 0f;
            while (t < seconds)
            {
                t += Time.unscaledDeltaTime;
                yield return null;
            }
        }

        /// <summary>
        /// Dismiss any open stock popup dialogs (new-game welcome / notification boxes can be modal,
        /// pause the game, and block facility entry). Returns how many were dismissed.
        /// </summary>
        public static int DismissPopups()
        {
            int n = 0;
            try
            {
                foreach (PopupDialog d in UnityEngine.Object.FindObjectsOfType<PopupDialog>())
                {
                    if (d == null) continue;
                    try { d.Dismiss(); n++; } catch { /* already closing */ }
                }
            }
            catch (Exception e) { Debug.LogWarning("[AXE][AutoTest] DismissPopups error: " + e.Message); }
            if (n > 0) Debug.Log("[AXE][AutoTest] Dismissed " + n + " popup dialog(s).");
            return n;
        }
    }

    /// <summary>Main menu: kick off the configured new game exactly once per launch.</summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, false)]
    public class AxeAutoTestStarter : MonoBehaviour
    {
        private void Start()
        {
            AutoTestConfig.EnsureLoaded();
            if (!AutoTestConfig.Enabled || AutoTestConfig.CareerStarted) return;
            AutoTestConfig.CareerStarted = true;
            StartCoroutine(StartGameRoutine());
        }

        private IEnumerator StartGameRoutine()
        {
            Debug.Log("[AXE][AutoTest] Enabled. Starting a new " + AutoTestConfig.GameMode + " game, then exercising: " +
                      string.Join(" -> ", AutoTestConfig.Screens));

            yield return AutoTestUtil.Dwell(1.5f);

            MainMenu mm = null;
            float t = 0f;
            while (t < 15f)
            {
                mm = UnityEngine.Object.FindObjectOfType<MainMenu>();
                if (mm != null) break;
                t += Time.unscaledDeltaTime;
                yield return null;
            }
            if (mm == null) { Debug.LogError("[AXE][AutoTest] MainMenu component not found; cannot start game."); yield break; }

            EnsureCareerAllowed();   // bypasses RO's new-game dialog gate anyway, but harmless + defensive
            yield return null;

            try { CreateGame(mm); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest] Failed to create/start game: " + e); }
        }

        private static void EnsureCareerAllowed()
        {
            try
            {
                Type patch = AppDomain.CurrentDomain.GetAssemblies()
                    .Select(a => a.GetType("RealismOverhaul.Harmony.PatchMainMenu"))
                    .FirstOrDefault(x => x != null);
                patch?.GetField("_overrideCareer", BindingFlags.NonPublic | BindingFlags.Static)?.SetValue(null, true);
            }
            catch (Exception e) { Debug.LogWarning("[AXE][AutoTest] could not set RO career override: " + e.Message); }
        }

        private static void CreateGame(MainMenu mm)
        {
            GameParameters pars = GameParameters.GetDefaultParameters(AutoTestConfig.GameMode, GameParameters.Preset.Normal);

            Type t = typeof(MainMenu);
            const BindingFlags SF = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
            t.GetField("newGameParameters", SF)?.SetValue(null, pars);
            t.GetField("newGameMode", SF)?.SetValue(null, AutoTestConfig.GameMode);

            MethodInfo create = t.GetMethod("CreateAndStartGame",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                null, new[] { typeof(string), typeof(Game.Modes) }, null);
            if (create == null) { Debug.LogError("[AXE][AutoTest] MainMenu.CreateAndStartGame(string, Game.Modes) not found."); return; }

            Debug.Log("[AXE][AutoTest] Creating new " + AutoTestConfig.GameMode + " save '" + AutoTestConfig.SaveName + "' and loading the Space Center...");
            create.Invoke(mm, new object[] { AutoTestConfig.SaveName, AutoTestConfig.GameMode });
        }
    }

    /// <summary>Space Center: once the auto-started game is up, walk the configured screens, then quit.</summary>
    [KSPAddon(KSPAddon.Startup.SpaceCentre, false)]
    public class AxeAutoTestDriver : MonoBehaviour
    {
        private bool _ok;   // result of the most recent Wait()/VisitScreen()

        private void Start()
        {
            AutoTestConfig.EnsureLoaded();
            if (!AutoTestConfig.Enabled || !AutoTestConfig.CareerStarted || AutoTestConfig.SequenceDone) return;
            if (HighLogic.CurrentGame == null) return;
            AutoTestConfig.SequenceDone = true;
            StartCoroutine(RunSequence());
        }

        private IEnumerator RunSequence()
        {
            yield return RunSteps();

            // Avionics flight test: launch the probe; its flight-scene driver measures, reports and quits.
            if (AxeAvionicsFlightTest.FlightPhaseRequested)
            {
                Debug.Log("[AXE][AutoTest] Launching a probe for the avionics flight test...");
                yield return AutoTestUtil.Dwell(1f);
                if (AxeAvionicsFlightTest.Launch()) yield break;
            }

            // If the screen walk asked for the KSC-switch test, load the Tracking Station and let its
            // driver finish + quit (do NOT quit here).
            if (AxeKscSwitchSelfTest.TrackingStationPhaseRequested)
            {
                Debug.Log("[AXE][AutoTest] Loading Tracking Station for the free-KSC-switch persistence test...");
                yield return AutoTestUtil.Dwell(1f);
                HighLogic.LoadScene(GameScenes.TRACKSTATION);
                yield break;
            }

            // If the screen walk asked for the craft-pricing sweep, open the VAB and let the editor-scene
            // driver run it + quit (procedural costs need a real ShipConstruct, editor-only).
            if (AxeCraftPricer.EditorPhaseRequested)
            {
                Debug.Log("[AXE][AutoTest] Loading the VAB for the craft-pricing sweep...");
                yield return AutoTestUtil.Dwell(1f);
                EditorDriver.StartEditor(EditorFacility.VAB);
                yield break;
            }

            if (AutoTestConfig.QuitWhenDone)
            {
                Debug.Log("[AXE][AutoTest] Test finished; quitting KSP in " + AutoTestConfig.QuitDelaySeconds + "s...");
                yield return AutoTestUtil.Dwell(AutoTestConfig.QuitDelaySeconds);
                AutoTestUtil.HardQuit();
            }
        }

        /// <summary>The actual steps; logs SUCCESS or a FAILED reason. Quit handling lives in <see cref="RunSequence"/>.</summary>
        private IEnumerator RunSteps()
        {
            // Resolve configured screen tokens to drivable facilities.
            var defs = new List<ScreenDef>();
            foreach (string tok in AutoTestConfig.Screens)
            {
                ScreenDef d = ScreenRegistry.Resolve(tok);
                if (d == null) Debug.LogWarning("[AXE][AutoTest] unknown screen '" + tok + "' (skipped). Valid: RND, MISSIONCONTROL, ADMINISTRATION, ASTRONAUTCOMPLEX.");
                else defs.Add(d);
            }
            if (defs.Count == 0) { Debug.LogWarning("[AXE][AutoTest] no valid screens configured; nothing to do."); yield break; }

            bool needsRnD = defs.Any(s => s.NeedsRnD);
            bool needsContracts = defs.Any(s => s.NeedsContracts);

            Debug.Log("[AXE][AutoTest] Space Center loaded. Waiting for systems + buildings (" +
                      string.Join(" -> ", defs.Select(d => d.Key).ToArray()) + ")...");
            yield return Wait(() =>
                    HighLogic.LoadedScene == GameScenes.SPACECENTER
                    && (!needsRnD || ResearchAndDevelopment.Instance != null)
                    && (!needsContracts || ContractSystem.Instance != null)
                    && defs.All(s => UnityEngine.Object.FindObjectOfType(s.Building) != null),
                AutoTestConfig.StepTimeoutSeconds, "systems + buildings ready");
            if (!_ok) { Fail("systems/buildings did not initialize"); yield break; }

            yield return AutoTestUtil.Dwell(AutoTestConfig.SettleSeconds); // settle

            // DSN tracking-station gate smoke check (11-level ladder + tech gate).
            try { Debug.Log("[AXE][AutoTest][DSN] " + AxeTrackingStationGate.SelfTestReport()); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest][DSN] self-test threw: " + e); }

            // Launchpad mass/size cap + Mission Control contract limit (CustomBarnKit @LAUNCHPAD / @MISSION).
            try { Debug.Log("[AXE][AutoTest][FAC] " + AxeFacilitiesSelfTest.SelfTestReport()); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest][FAC] self-test threw: " + e); }

            // Avionics Shielded axis: confirm each Shielded rung gates on its shd_* node (not the guided tier).
            try { Debug.Log("[AXE][AutoTest][AVI] " + ModuleAxeAvionics.ShieldedLadderReport()); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest][AVI] self-test threw: " + e); }

            // Avionics shutdown (RP-1's Shutdown Avionics): confirm the per-axis availability gate wired
            // through from config -- Unshielded from index 9 only, Shielded from its own first rung.
            try { Debug.Log("[AXE][AutoTest][AVI] " + ModuleAxeAvionics.HibernateLadderReport()); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest][AVI] self-test threw: " + e); }

            // Editor simulation: confirm the feature flag + 2-rung body gate resolve (home open, others gated).
            try { Debug.Log("[AXE][AutoTest][SIM] " + RPAxe.Simulation.AxeSimulation.SelfTestReport()); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest][SIM] self-test threw: " + e); }

            // Funds economy: capstone patches landed, completion contracts well-formed with no
            // dangling CompleteContract deps, strategy reputation gate un-re-broken.
            try { Debug.Log("[AXE][AutoTest][ECON] " + AxeEconomySelfTest.SelfTestReport()); }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest][ECON] self-test threw: " + e); }

            foreach (ScreenDef s in defs)
            {
                yield return VisitScreen(s);
                if (!_ok) { Fail(s.Key + " step failed"); yield break; }
            }

            Debug.Log("[AXE][AutoTest] SUCCESS: visited " + defs.Count + " screen(s) [" +
                      string.Join(", ", defs.Select(d => d.Key).ToArray()) + "]. Test sequence complete.");

            // Opt-in: hand off to the Tracking Station for the free-KSC-switch downstream check (that
            // scene is where KSCSwitcher's UI + its LastKSC persistence module live). RunSequence loads it.
            if (AutoTestConfig.KscSwitchTest)
                AxeKscSwitchSelfTest.RequestTrackingStationPhase();

            // Opt-in: hand off to the VAB for the craft-pricing sweep (economy-pass ground truth).
            if (AutoTestConfig.PriceCraftTest)
                AxeCraftPricer.RequestEditorPhase();

            // Opt-in: launch a probe and measure the avionics corruption in flight. Takes precedence over
            // the two hand-offs above (one scene change per run).
            if (AutoTestConfig.AvionicsTest)
                AxeAvionicsFlightTest.RequestFlightPhase();
        }

        /// <summary>Enter a facility, dwell, then exit it. Sets <see cref="_ok"/>.</summary>
        private IEnumerator VisitScreen(ScreenDef s)
        {
            Debug.Log("[AXE][AutoTest] === " + s.Key + " ===");
            AutoTestUtil.DismissPopups();

            var building = UnityEngine.Object.FindObjectOfType(s.Building) as SpaceCenterBuilding;
            if (building == null) { _ok = false; Debug.LogError("[AXE][AutoTest] " + s.Key + " building not found; cannot enter."); yield break; }

            // Enter — primary path is public EnterBuilding(); fallback is the building's private OnClicked().
            Debug.Log("[AXE][AutoTest] Entering " + s.Key + " via EnterBuilding()...");
            TryInvoke(() => building.EnterBuilding(), s.Key + ".EnterBuilding()");
            yield return Wait(() => IsOpen(s), AutoTestConfig.EnterAttemptSeconds, s.Key + " open (EnterBuilding)");
            if (!_ok)
            {
                Debug.LogWarning("[AXE][AutoTest] " + s.Key + " not open via EnterBuilding(); trying OnClicked() fallback.");
                MethodInfo onClicked = building.GetType().GetMethod("OnClicked", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (onClicked != null)
                {
                    TryInvoke(() => onClicked.Invoke(building, null), s.Key + ".OnClicked()");
                    yield return Wait(() => IsOpen(s), AutoTestConfig.StepTimeoutSeconds, s.Key + " open (OnClicked)");
                }
            }
            if (!_ok) { Debug.LogError("[AXE][AutoTest] " + s.Key + " did not open."); yield break; }

            Debug.Log("[AXE][AutoTest] " + s.Key + " open. Dwelling " + AutoTestConfig.DwellSeconds + "s...");
            // Let nodes/arrows settle, clear any scene-triggered popups (e.g. ToolbarController first-run),
            // THEN grab a clean frame (e.g. the R&D render port) for a visual pass.
            yield return AutoTestUtil.Dwell(Mathf.Max(1f, AutoTestConfig.DwellSeconds - 1f));
            AutoTestUtil.DismissPopups();
            CaptureShot(s.Key);
            yield return AutoTestUtil.Dwell(1f);   // let the async screenshot land

            // Exit via the facility's scene despawner (same as clicking its Exit button).
            Debug.Log("[AXE][AutoTest] Exiting " + s.Key + "...");
            if (!InvokeDespawnerExit(s.Despawner)) { _ok = false; Debug.LogError("[AXE][AutoTest] could not operate " + s.Key + " despawner."); yield break; }
            yield return Wait(() => !IsOpen(s), AutoTestConfig.StepTimeoutSeconds, s.Key + " closed");
            if (!_ok) { Debug.LogError("[AXE][AutoTest] " + s.Key + " did not close."); yield break; }

            yield return AutoTestUtil.Dwell(AutoTestConfig.SettleSeconds);
        }

        private static bool IsOpen(ScreenDef s)
        {
            return UnityEngine.Object.FindObjectOfType(s.Despawner) != null;
        }

        // Request a full-frame screenshot into the Instance root (async, lands next frame during the dwell).
        // Only ever runs under the autotest, so it never affects normal play.
        private static void CaptureShot(string key)
        {
            try
            {
                string safe = new string(key.Where(char.IsLetterOrDigit).ToArray());
                string file = KSPUtil.ApplicationRootPath + "axe-shot-" + safe + ".png";
                ScreenCapture.CaptureScreenshot(file);
                Debug.Log("[AXE][AutoTest] screenshot requested -> " + file);
            }
            catch (Exception e) { Debug.LogWarning("[AXE][AutoTest] screenshot failed: " + e.Message); }
        }

        private static bool InvokeDespawnerExit(Type despawnerType)
        {
            UnityEngine.Object despawner = UnityEngine.Object.FindObjectOfType(despawnerType);
            if (despawner == null) return false;
            MethodInfo btnExit = despawnerType.GetMethod("BtnExit", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (btnExit == null) return false;
            try { btnExit.Invoke(despawner, null); return true; }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest] " + despawnerType.Name + ".BtnExit() threw: " + e); return false; }
        }

        private static bool TryInvoke(Action a, string what)
        {
            try { a(); return true; }
            catch (Exception e) { Debug.LogError("[AXE][AutoTest] " + what + " threw: " + e); return false; }
        }

        private static void Fail(string why)
        {
            Debug.LogError("[AXE][AutoTest] FAILED: " + why + ". (Test sequence aborted.)");
        }

        /// <summary>Poll <paramref name="cond"/> each frame up to <paramref name="timeout"/>s (unscaled); sets <see cref="_ok"/>.</summary>
        private IEnumerator Wait(Func<bool> cond, float timeout, string label)
        {
            _ok = false;
            float t = 0f;
            while (t < timeout)
            {
                bool c = false;
                try { c = cond(); }
                catch (Exception e) { Debug.LogWarning("[AXE][AutoTest] condition '" + label + "' threw: " + e.Message); }
                if (c) { _ok = true; yield break; }
                t += Time.unscaledDeltaTime;
                yield return null;
            }
            Debug.LogWarning("[AXE][AutoTest] timeout (" + timeout + "s) waiting for: " + label);
        }
    }
}
