using System;
using System.Reflection;
using HarmonyLib;
using KERBALISM;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Is Kerbalism actually loaded?
    ///
    /// This is NOT answerable from <c>AssemblyLoader.loadedAssemblies</c>. Kerbalism ships as
    /// <c>Kerbalism1xx.kbin</c> and is pulled in by KerbalismBootstrap via <c>Assembly.Load</c> at
    /// runtime, so KSP's own list holds only "KerbalismBootstrap" — never "Kerbalism". A check written
    /// against that list therefore answers FALSE on every install that HAS Kerbalism, which is the exact
    /// inverse of the truth, and it fails silently.
    ///
    /// That inversion is not cosmetic: the avionics modules use it to decide whether to route their EC
    /// draw through Kerbalism or through stock ModuleCommand. Answering "no Kerbalism" made them do
    /// BOTH — stock drained the full avionics wattage for real while the module also reported the same
    /// wattage to Kerbalism, so every probe paid twice and Kerbalism filed the stock half under its
    /// "Others" broker (ResourceInfo.Sync attributes any resource delta it did not itself cause).
    ///
    /// The CLR knows what is loaded, so ask the CLR. Cached: Kerbalism is loaded during KSP's loading
    /// screen, long before any editor or flight scene, so the first call always sees the final answer.
    /// </summary>
    internal static class AxeKerbalism
    {
        private static bool? _present;

        public static bool Present
        {
            get
            {
                if (_present == null)
                {
                    _present = false;
                    foreach (Assembly a in AppDomain.CurrentDomain.GetAssemblies())
                    {
                        // Name match is definitive (AXE references the assembly as "Kerbalism"); the
                        // type probe is insurance against a future repack under a different identity.
                        if (a.GetName().Name == "Kerbalism" || a.GetType("KERBALISM.Kerbalism", false) != null)
                        {
                            _present = true;
                            break;
                        }
                    }
                }
                return _present.Value;
            }
        }
    }

    /// <summary>
    /// Renders Kerbalism's ElectricCharge displays as SI power (W/kW/MW) instead of "EC/s", matching
    /// RO's convention that 1 EC = 1 kJ (so 1 EC/s = 1 kW). Adapted from RP-1's KerbalismPatcher EC
    /// block, which was hard-gated to Kerbalism <= 3.17; AXE ships Kerbalism 3.32, whose UI internals
    /// (verified) still expose the same patch points with the same signatures and public members — the
    /// only real change is dropping that version guard.
    ///
    /// These patches are applied through their OWN Harmony instance with per-patch try/catch (see
    /// <see cref="AxeKerbalismEcPatcher"/>), NOT via AxeHarmony's PatchAll — so if a future Kerbalism
    /// update moves one of these methods, the failed patch is logged and skipped without taking down
    /// the rest of AXE's Harmony patches. The bodies below are plain static methods (no [HarmonyPatch]
    /// attributes) precisely so PatchAll never picks them up.
    /// </summary>
    internal static class AxeKerbalismEc
    {
        // Shared markers set by the "signal" patches and read by the rate-formatting patches, mirroring
        // RP-1's cross-patch state (Kerbalism's rate printers are generic, so we only convert while we
        // KNOW the current resource is EC).
        internal static bool JustRanAnalyze;   // set right before the Planner builds the EC subpanel
        internal static bool PlannerIsEC;      // inside SimulatedResource.Tooltip for ElectricCharge
        internal static bool TelemetryIsEC;    // inside Telemetry.Render_supplies for ElectricCharge
        internal static bool IsRenderSupplies; // inside Telemetry.Render_supplies

        private static string _ecName;
        private static bool _needName = true;

        private static string EcName()
        {
            if (_needName)
            {
                _ecName = PartResourceLibrary.Instance.GetDefinition("ElectricCharge").displayName;
                _needName = false;
            }
            return _ecName;
        }

        // ---- Solar panel status line: "12.3 EC/s" -> "12.3 kW" ----
        internal static void SolarPanelFixer_Update_Postfix(SolarPanelFixer __instance)
        {
            int idx = __instance.panelStatus.IndexOf(__instance.EcUIUnit);
            if (idx == -1) return;

            int offset = __instance.EcUIUnit.Length;
            string si = KSPUtil.PrintSI(__instance.currentOutput * 1000d, "W", 3);
            __instance.panelStatus = __instance.panelStatus.Length > idx + offset
                ? si + __instance.panelStatus.Substring(idx + offset)
                : si;
        }

        // ---- Module-info "Specifics" rows whose value we know is an EC rate ----
        internal static void Specifics_Add_Prefix(ref string label, ref string value)
        {
            if (string.IsNullOrEmpty(value)) return;

            if (label == Local.Module_Experiment_Specifics_info9
                || label == Local.Harvester_info7
                || label == "EC/s"
                || label == Local.Laboratory_ECrate
                || label == Local.DataTransmitter_ECidle
                || label == Local.DataTransmitter_ECTX
                || label == EcName())
            {
                AxeKerbalismUnits.HumanRateToSI(ref value, "W", 1000d);
            }
        }

        // ---- Planner EC subpanel: mark that Analyze just ran, then convert the following rate rows ----
        internal static void ResourceSimulator_Analyze_Postfix() => JustRanAnalyze = true;

        internal static void Panel_AddContent_Prefix(string label, ref string value)
        {
            if (!JustRanAnalyze) return;

            if (label == Local.Planner_duration) { JustRanAnalyze = false; return; } // last row -> stop
            if (label == Local.Planner_storage) return;                              // storage is not a rate

            AxeKerbalismUnits.HumanRateToSI(ref value, "W", 1000d);
        }

        // ---- Planner resource tooltip: flag EC so the shared rate printer converts ----
        internal static void SimulatedResource_Tooltip_Prefix(KERBALISM.Planner.SimulatedResource __instance)
            => PlannerIsEC = __instance.resource_name == "ElectricCharge";
        internal static void SimulatedResource_Tooltip_Postfix() => PlannerIsEC = false;

        // ---- Telemetry supply readout: mark render window; EC is detected via SpacesOnCaps below ----
        internal static void Telemetry_RenderSupplies_Prefix() => IsRenderSupplies = true;
        internal static void Telemetry_RenderSupplies_Postfix() { IsRenderSupplies = false; TelemetryIsEC = false; }

        // ---- Shared rate printer: SI-print when we know the resource is EC ----
        internal static bool Lib_HumanReadableRate_Prefix(double rate, string precision, ref string __result)
        {
            if (!(PlannerIsEC || TelemetryIsEC)) return true;   // not EC -> run the original

            int sigfigs = 3;
            char c = precision[precision.Length - 1];
            if (char.IsDigit(c)) sigfigs = (int)char.GetNumericValue(c);

            __result = KSPUtil.PrintSI(rate * 1000d, "W", sigfigs);
            return false;   // skip original
        }

        // SpacesOnCaps is called just before a resource name is printed in Render_supplies; use it to
        // detect that the current supply row is EC (the cheap marker trick RP-1 uses).
        internal static void Lib_SpacesOnCaps_Prefix(string s)
        {
            if (IsRenderSupplies)
                TelemetryIsEC = s == EcName();
        }
    }

    /// <summary>
    /// Parses a Kerbalism human-readable rate string ("12.3 EC/s", possibly with rich-text tags) and
    /// reformats the numeric part as an SI quantity in <paramref name="unit"/> (scaled by baseMult, e.g.
    /// 1000 to turn EC into J -> W). Ported verbatim from RP-1's KerbalismUtils.HumanRateToSI; the rate
    /// suffixes come from Kerbalism's own Local strings.
    /// </summary>
    internal static class AxeKerbalismUnits
    {
        private static bool _needRateStrings = true;
        private static readonly string[] _rateStrings = new string[5];
        private static readonly bool[] _rateMatches = { true, true, true, true, true };
        private static readonly double[] _rateMults = {
            1d, 1d / 60d, 1d / (60d * 60d), 1d / 86400d, 1d / (86400d * 365d) };

        public static bool HumanRateToSI(ref string rate, string unit, double baseMult = 1d, int sigFigs = 3)
        {
            int numStart = -1, numStop = -1, rStart = -1, rEnd = -1;
            int len = rate.Length;
            if (_needRateStrings)
            {
                _needRateStrings = false;
                _rateStrings[0] = Local.Generic_perSecond;
                _rateStrings[1] = Local.Generic_perMinute;
                _rateStrings[2] = Local.Generic_perHour;
                _rateStrings[3] = Local.Generic_perDay;
                _rateStrings[4] = Local.Generic_perYear;
            }
            for (int i = 0; i < len; ++i)
            {
                if (rate[i] == '/')
                {
                    numStop = i - 1;
                    rStart = i;
                    for (int j = i + 1; j < len; ++j)
                    {
                        if (rate[j] == '<') { rEnd = j - 1; break; }
                    }
                    if (rEnd == -1) rEnd = len - 1;

                    for (int j = i; j-- > 0;)
                    {
                        if (rate[j] == '>') { numStart = j + 1; break; }
                    }
                    if (numStart == -1) numStart = 0;
                    break;
                }
            }

            if (numStop == -1) return false;

            int end = rEnd - rStart + 1;
            for (int i = 0; i < end; ++i)
            {
                char c = rate[i + rStart];
                for (int j = 0; j < 5; ++j)
                    if (_rateMatches[j] && (i >= _rateStrings[j].Length || c != _rateStrings[j][i]))
                        _rateMatches[j] = false;
            }
            int rateIdx = 0;
            for (; rateIdx < 5; ++rateIdx)
                if (_rateMatches[rateIdx]) break;
            _rateMatches[0] = _rateMatches[1] = _rateMatches[2] = _rateMatches[3] = _rateMatches[4] = true;
            if (rateIdx == 5) return false;   // no rate suffix matched

            string numStr = rate.Substring(numStart, numStop - numStart + 1);
            if (!double.TryParse(numStr, out double value)) return false;

            value *= _rateMults[rateIdx] * baseMult;

            string result = KSPUtil.PrintSI(value, unit, sigFigs);
            if (numStart > 0) result = rate.Substring(0, numStart) + result;
            if (rEnd + 1 < len) result += rate.Substring(rEnd + 1, len - rEnd - 1);

            rate = result;
            return true;
        }
    }

    /// <summary>
    /// Applies the Kerbalism EC-in-watts patches through a private Harmony instance, each guarded by
    /// its own try/catch so a moved/renamed target on a future Kerbalism is logged and skipped rather
    /// than aborting AXE's whole patch set.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.MainMenu, true)]
    public class AxeKerbalismEcPatcher : MonoBehaviour
    {
        private const BindingFlags M = BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public;

        private void Start()
        {
            var h = new Harmony("rpaxe.kerbalism.ec");
            Type P = typeof(AxeKerbalismEc);
            int n = 0;

            n += Patch(h, AccessTools.Method(typeof(SolarPanelFixer), "Update"),
                       postfix: P.GetMethod(nameof(AxeKerbalismEc.SolarPanelFixer_Update_Postfix), M));
            n += Patch(h, AccessTools.Method(typeof(Specifics), "Add", new[] { typeof(string), typeof(string) }),
                       prefix: P.GetMethod(nameof(AxeKerbalismEc.Specifics_Add_Prefix), M));
            n += Patch(h, AccessTools.Method(typeof(KERBALISM.Planner.ResourceSimulator), "Analyze"),
                       postfix: P.GetMethod(nameof(AxeKerbalismEc.ResourceSimulator_Analyze_Postfix), M));
            n += Patch(h, AccessTools.Method(typeof(Panel), "AddContent"),
                       prefix: P.GetMethod(nameof(AxeKerbalismEc.Panel_AddContent_Prefix), M));
            n += Patch(h, AccessTools.Method(typeof(KERBALISM.Planner.SimulatedResource), "Tooltip"),
                       prefix: P.GetMethod(nameof(AxeKerbalismEc.SimulatedResource_Tooltip_Prefix), M),
                       postfix: P.GetMethod(nameof(AxeKerbalismEc.SimulatedResource_Tooltip_Postfix), M));
            n += Patch(h, AccessTools.Method(typeof(Telemetry), "Render_supplies"),
                       prefix: P.GetMethod(nameof(AxeKerbalismEc.Telemetry_RenderSupplies_Prefix), M),
                       postfix: P.GetMethod(nameof(AxeKerbalismEc.Telemetry_RenderSupplies_Postfix), M));
            n += Patch(h, AccessTools.Method(typeof(Lib), "HumanReadableRate", new[] { typeof(double), typeof(string), typeof(string) }),
                       prefix: P.GetMethod(nameof(AxeKerbalismEc.Lib_HumanReadableRate_Prefix), M));
            n += Patch(h, AccessTools.Method(typeof(Lib), "SpacesOnCaps", new[] { typeof(string) }),
                       prefix: P.GetMethod(nameof(AxeKerbalismEc.Lib_SpacesOnCaps_Prefix), M));

            Debug.Log($"[AXE] Kerbalism EC-in-watts: {n}/8 patch point(s) applied.");
        }

        private static int Patch(Harmony h, MethodBase target, MethodInfo prefix = null, MethodInfo postfix = null)
        {
            if (target == null) { Debug.LogWarning("[AXE] Kerbalism EC: a target method was not found; skipping."); return 0; }
            try
            {
                h.Patch(target, prefix != null ? new HarmonyMethod(prefix) : null, postfix != null ? new HarmonyMethod(postfix) : null);
                return 1;
            }
            catch (Exception e)
            {
                Debug.LogError($"[AXE] Kerbalism EC patch failed for {target.DeclaringType?.Name}.{target.Name}: {e.Message}");
                return 0;
            }
        }
    }
}
