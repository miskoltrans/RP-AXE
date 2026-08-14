using HarmonyLib;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Applies the avionics attitude lock to RCS thrusters. <see cref="AxeAvionicsController"/> zeroes the
    /// vessel's flight control state via <c>OnPostAutopilotUpdate</c>, which covers reaction wheels and engine
    /// gimbal — but NOT RCS: <c>ModuleRCS.Update</c> reads <c>vessel.ctrlState</c> on its own Unity update,
    /// before that post-autopilot hook re-zeroes it, so an avionics-locked vessel could still translate/rotate
    /// on RCS. RP-1's ControlLocker hit the same wall and shipped a dedicated <c>ModuleRCS</c> patch (RP-0's
    /// <c>Harmony/ModuleRCS.cs</c>); AXE replaces RP-1's plugin, so we re-provide it here.
    ///
    /// Semantics match AXE's <c>FlightInputModifier</c> (attitude-only — RP-1 additionally clamps throttle;
    /// AXE deliberately leaves throttle &amp; staging free): zero rotation and lateral (X/Y) translation while
    /// locked; the Axial level still permits axial-thrust (Z) translation for spin-stabilized kick stages. We
    /// save the real ctrlState, zero it for the duration of ModuleRCS.Update, and restore it in the postfix so
    /// no other consumer (or the control display) sees the temporarily-zeroed values.
    ///
    /// IT IS ALSO THE TRANSLATION DEGRADATION PATH. The post-autopilot hook corrupts rotation only, so
    /// X/Y/Z reached the thrusters clean at any overload — docking and station-keeping were the one place
    /// an autopilot could absorb the entire mechanic by making small inputs. The same save/restore window
    /// used for the lock is where translation gets misdirected, because that window is already scoped to
    /// ModuleRCS: nothing written here escapes into the gimbal path or into any stateful buffer.
    /// </summary>
    [HarmonyPatch(typeof(ModuleRCS), "Update")]
    internal static class AxeRcsControlLock
    {
        // ModuleRCS.Update is never reentrant, so a single shared save-slot is safe across all RCS modules.
        private static bool _saved;
        private static float _x, _y, _z, _pitch, _yaw, _roll, _throttle;

        [HarmonyPrefix]
        internal static void Prefix(ModuleRCS __instance)
        {
            _saved = false;

            AxeAvionicsController ctl = AxeAvionicsController.Instance;
            if (ctl == null || !HighLogic.LoadedSceneIsFlight) return;

            Vessel v = __instance.vessel;
            if (v == null || v != FlightGlobals.ActiveVessel) return;

            AxeControlLockerUtils.LockLevel level = ctl.Level;

            // ROTATION is not re-applied here, and must not be: the post-autopilot hook mutates
            // vessel.ctrlState IN PLACE and ModuleRCS reads that same object, so thrusters already fly the
            // corrupted pitch/yaw/roll. The policy is stateful in every cell (a delay buffer, a washout EMA,
            // a regime on a dwell timer) and this prefix runs once PER THRUSTER MODULE, so re-applying it
            // would advance that state several times a frame -- a switching artefact indistinguishable from
            // the mechanic working.
            //
            // TRANSLATION is a different story and needs its own path, which is what this is. X/Y/Z never
            // pass through the post-autopilot hook's corruption at all (it is rotation-only, deliberately:
            // translation noise on a launch vehicle just burns RCS unfelt), so docking and station-keeping
            // were flying CLEAN at any overload -- the one place where an autopilot could simply absorb the
            // whole mechanic. Misdirection is what goes here, and only misdirection:
            //   * it is MAGNITUDE-INDEPENDENT, so the "nudge it in small pulses" escape that works against
            //     the three proportional cells does not work against it;
            //   * it is STATELESS and a pure function of Time.time, which is the only kind of corruption
            //     that is safe to run per-thruster on Unity's Update phase;
            //   * it rotates the WHOLE translation vector, so an axial approach bleeds into lateral and a
            //     lateral correction bleeds into axial -- which is exactly the docking failure a drifting
            //     IMU produces, and it is the same rotation the gimbals got this frame.
            float sigma = AxeControlLockerUtils.Armed ? ctl.ControlNoise : 0f;
            bool misdirectTranslation = sigma > 0f && AxeControlLockerUtils.MisdirectMaxDeg > 0f;
            if (level == AxeControlLockerUtils.LockLevel.Unlocked && !misdirectTranslation) return;

            FlightCtrlState st = v.ctrlState;
            _x = st.X; _y = st.Y; _z = st.Z;
            _pitch = st.pitch; _yaw = st.yaw; _roll = st.roll;
            _throttle = st.mainThrottle;
            _saved = true;

            if (level == AxeControlLockerUtils.LockLevel.Unlocked)
            {
                AxeControlLockerUtils.ApplyMisdirect(ref st.X, ref st.Y, ref st.Z, sigma);
                return;   // the postfix restores, so nothing outside ModuleRCS sees the rotated command
            }

            st.yaw = st.pitch = st.roll = 0f;   // no steering
            st.X = st.Y = 0f;                    // no lateral translation
            if (level == AxeControlLockerUtils.LockLevel.Locked)
                st.Z = 0f;                       // Locked: no axial translation either (Axial keeps Z)

            // A5. Stock ModuleRCS does, in effect, `if (Z ~= 0 && useThrottle) num2 -= mainThrottle`, so with
            // no translation input THE THROTTLE BECOMES THE AXIAL COMMAND. Zeroing Z without handling
            // mainThrottle leaves an avionics-locked vessel able to translate axially on RCS via the
            // throttle. RP-1 patched this as an exploit in 2023 (816d8656); AXE never ported it until now.
            // Zero at Locked, snap to full at Axial (where axial thrust is meant to be available anyway),
            // and restore in the postfix so nothing else sees it.
            st.mainThrottle = level == AxeControlLockerUtils.LockLevel.Locked ? 0f : 1f;
        }

        [HarmonyPostfix]
        internal static void Postfix(ModuleRCS __instance)
        {
            if (!_saved) return;
            _saved = false;

            FlightCtrlState st = __instance.vessel.ctrlState;
            st.X = _x; st.Y = _y; st.Z = _z;
            st.pitch = _pitch; st.yaw = _yaw; st.roll = _roll;
            st.mainThrottle = _throttle;
        }
    }
}
