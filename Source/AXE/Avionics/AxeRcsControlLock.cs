using HarmonyLib;

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
    /// </summary>
    [HarmonyPatch(typeof(ModuleRCS), "Update")]
    internal static class AxeRcsControlLock
    {
        // ModuleRCS.Update is never reentrant, so a single shared save-slot is safe across all RCS modules.
        private static bool _saved;
        private static float _x, _y, _z, _pitch, _yaw, _roll;

        [HarmonyPrefix]
        internal static void Prefix(ModuleRCS __instance)
        {
            _saved = false;

            AxeAvionicsController ctl = AxeAvionicsController.Instance;
            if (ctl == null || !HighLogic.LoadedSceneIsFlight) return;

            Vessel v = __instance.vessel;
            if (v == null || v != FlightGlobals.ActiveVessel) return;

            AxeControlLockerUtils.LockLevel level = ctl.Level;
            if (level == AxeControlLockerUtils.LockLevel.Unlocked) return;

            FlightCtrlState st = v.ctrlState;
            _x = st.X; _y = st.Y; _z = st.Z;
            _pitch = st.pitch; _yaw = st.yaw; _roll = st.roll;
            _saved = true;

            st.yaw = st.pitch = st.roll = 0f;   // no steering
            st.X = st.Y = 0f;                    // no lateral translation
            if (level == AxeControlLockerUtils.LockLevel.Locked)
                st.Z = 0f;                       // Locked: no axial translation either (Axial keeps Z)
        }

        [HarmonyPostfix]
        internal static void Postfix(ModuleRCS __instance)
        {
            if (!_saved) return;
            _saved = false;

            FlightCtrlState st = __instance.vessel.ctrlState;
            st.X = _x; st.Y = _y; st.Z = _z;
            st.pitch = _pitch; st.yaw = _yaw; st.roll = _roll;
        }
    }
}
