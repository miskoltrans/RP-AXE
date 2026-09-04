using System;
using System.Reflection;
using HarmonyLib;

namespace RPAxe
{
    /// <summary>
    /// Stops an AJE propeller from producing a ~100x thrust spike on the first frame it is throttled
    /// up from a standstill.
    ///
    /// AJE integrates prop speed from excess torque in <c>AJEPropJSB.Calculate</c>:
    /// <code>
    ///   double num6 = num * 2.0 * Math.PI;        // omega, from the CURRENT RPM
    ///   if (num6 > 0.0)
    ///       ExcessTorque = num4 / num6;           // tau = P / omega  -- correct
    ///   else
    ///       ExcessTorque = num4;                  // RPM == 0: assigns POWER into a TORQUE variable
    ///   RPM = (num + ExcessTorque / (Ixx * 2.0 * Math.PI) * deltaT) * 60.0;
    /// </code>
    /// The <c>else</c> is a divide-by-zero guard, but it is not a physical fallback: it puts watts into
    /// a newton-metre variable with no conversion. Measured on the DS-215 Electric Ducted Fan
    /// (16.3 hp = 12,155 W; <c>Ixx 0.013558179491</c>, straight out of the KSP.log line
    /// "*AJE* Constructed prop of type DS215 ... Ixx 0.013558179491J"), one 0.02 s tick takes the prop
    /// from 0 to ~171,000 RPM against a 14,000 ceiling. Thrust goes as n-squared, so that frame is on the
    /// order of 150x rated. SolverPropeller.CalculatePerformance then bleeds the overspeed off
    /// cubically, RPM hits its own <c>if (RPM &lt; 0) RPM = 0</c> clamp, and with throttle still applied
    /// the next frame re-enters the same branch -- so it reads in-game as a repeating jolt, not one bump.
    ///
    /// The real divergence is not the <c>else</c> branch specifically, it is that tau = P/omega blows up
    /// as omega approaches zero -- seeding RPM with some epsilon makes it WORSE, not better. Solving
    ///     dRPM = 900*P*dt / (pi^2 * Ixx * RPM)
    /// for dRPM &lt;= RPM (do not more than double in one tick) gives the floor this patch enforces:
    ///     RPM_min = sqrt(900/pi^2 * P * dt / Ixx)
    /// which is 1,279 RPM for the DS-215 -- just under its declared <c>minRPM</c> of 1400. That is not a
    /// coincidence: minRPM is idle, and idle is roughly where a prop's power-to-inertia ratio stops
    /// being pathological. We take max() of the two anyway, because it is not guaranteed for every prop
    /// in the pack and a part whose minRPM sits below its own stability floor would still spike.
    ///
    /// P is taken as the raw EnginePower argument rather than (EnginePower - PowerRequired), which is
    /// what the solver actually uses. At the RPM this fires at, PowerRequired (proportional to n^3) is
    /// negligible, and over-estimating P only raises the floor -- the conservative direction.
    ///
    /// This does hand the prop angular momentum it did not earn. Worth being explicit about: at 1400 RPM
    /// with Ixx = 0.0136, that is 1/2*I*omega^2 = 146 J, which a 12 kW motor covers in 12 ms. The engine-off
    /// case is untouched (EnginePower &lt;= 0 returns early), so a prop still spins down normally.
    ///
    /// UPSTREAM: the one-line fix belongs in AJE -- divide by a small omega floor instead of assigning
    /// raw power to a torque variable. DROP THIS PATCH if AJE fixes that branch. AJE is reached by
    /// reflection so AXE keeps no compile-time dependency on it; if AJE is absent, or if any of the
    /// three private fields is renamed, Prepare() returns false and the patch is simply not applied.
    /// </summary>
    [HarmonyPatch]
    internal static class AxeAjePropZeroRpmFix
    {
        private const string PropTypeName = "AJE.AJEPropJSB";

        // 900 / pi^2, the constant in the stability floor derived above.
        private const double FloorK = 91.18906528;

        private static MethodBase _calculate;
        private static AccessTools.FieldRef<object, double> _rpm;      // all three are PRIVATE on
        private static AccessTools.FieldRef<object, double> _minRpm;   // AJEPropJSB -- this KSP is not
        private static AccessTools.FieldRef<object, double> _ixx;      // publicized, so no cast works

        /// <summary>
        /// Harmony calls Prepare() before TargetMethod(); returning false drops the whole patch class.
        /// That keeps AJE a soft dependency, and makes a future AJE release that renames or fixes these
        /// members degrade to "patch not applied" rather than a PatchAll failure that would take every
        /// other AXE patch down with it.
        /// </summary>
        private static bool Prepare()
        {
            Type prop = AccessTools.TypeByName(PropTypeName);
            if (prop == null) return false;                 // AJE not installed

            _calculate = AccessTools.Method(prop, "Calculate");
            if (_calculate == null) return false;

            try
            {
                _rpm    = AccessTools.FieldRefAccess<double>(prop, "RPM");
                _minRpm = AccessTools.FieldRefAccess<double>(prop, "MinRPM");
                _ixx    = AccessTools.FieldRefAccess<double>(prop, "Ixx");
            }
            catch (Exception e)
            {
                UnityEngine.Debug.Log("[AXE] AJE prop zero-RPM fix not applied: " + e.Message);
                return false;
            }

            return _rpm != null && _minRpm != null && _ixx != null;
        }

        private static MethodBase TargetMethod()
        {
            return _calculate;
        }

        private static void Prefix(object __instance, double EnginePower, double deltaTime)
        {
            if (EnginePower <= 0.0) return;                 // not making power: let it spin down

            double rpm = _rpm(__instance);
            double floor = _minRpm(__instance);

            double ixx = _ixx(__instance);
            if (ixx > 0.0 && deltaTime > 0.0)
            {
                double stable = Math.Sqrt(FloorK * EnginePower * deltaTime / ixx);
                if (stable > floor) floor = stable;
            }

            if (rpm < floor) _rpm(__instance) = floor;
        }
    }
}
