using HarmonyLib;

namespace RPAxe
{
    /// <summary>
    /// Gives AXE the FIRST and the LAST word on the active vessel's control state, by bracketing
    /// <c>Vessel.FeedInputFeed()</c> — the method that runs KSP's four control callbacks in order:
    ///
    ///     OnPreAutopilotUpdate -> OnAutopilotUpdate (stock SAS) -> OnPostAutopilotUpdate -> OnFlyByWire
    ///
    /// WHY THIS EXISTS. The avionics overload mechanic used to write at <c>OnPostAutopilotUpdate</c>, which
    /// is third of four. MechJeb registers on <c>OnFlyByWire</c> — fourth — and its attitude controller
    /// assigns <c>s.pitch/s.yaw/s.roll</c> outright whenever the value it finds sits within 0.1 of trim
    /// (that is its "has the pilot grabbed the stick?" test). So on any MechJeb-driven attitude the
    /// corruption was computed, written into ctrlState, and then overwritten in the same tick, before it
    /// reached a gimbal or a reaction wheel. Symptom: a scheduled node burn executed perfectly at 2x over
    /// rated capacity, with the PAW correctly reporting saturated overload the whole time. The mechanic was
    /// not weak, it was not running.
    ///
    /// Patching FeedInputFeed rather than re-registering on OnFlyByWire is deliberate: delegate invocation
    /// order there is registration order, and MechJeb re-registers on vessel switch and on scene load
    /// (Remove-then-Combine), so "add ourselves last" is a race we would lose intermittently — the worst
    /// possible failure shape for a mechanic that is already hard to attribute. A postfix is last by
    /// construction, for MechJeb and kOS and anything else, forever.
    ///
    /// THE PREFIX IS NOT AN AFTERTHOUGHT — it is the other half of the fix. Arming has to read what the
    /// PILOT asked for, never what the control loop ended up commanding, because the latter is downstream
    /// of our own corruption: perturb the vessel, SAS corrects, the correction re-arms us, and the fault
    /// sustains itself with no way for the player to stop it by stopping. That is exactly what killed the
    /// additive cell on 2026-08-24. At the prefix, ctrlState holds nothing but what FlightInputHandler just
    /// copied in from the player's stick, so the loop is open by construction.
    ///
    /// Not reentrant and not a leak risk: FlightInputHandler rebuilds the active vessel's ctrlState from raw
    /// input every frame (<c>SetControlState(state)</c> immediately before <c>FeedInputFeed()</c>), so
    /// nothing written in the postfix survives into the next frame's MechJeb override test.
    /// </summary>
    [HarmonyPatch(typeof(Vessel), "FeedInputFeed")]
    internal static class AxeFlightControlLast
    {
        [HarmonyPrefix]
        internal static void Prefix(Vessel __instance)
        {
            if (!HighLogic.LoadedSceneIsFlight) return;
            if (__instance == null || __instance != FlightGlobals.ActiveVessel) return;
            AxeControlLockerUtils.SampleStickIntent(__instance.ctrlState);
        }

        [HarmonyPostfix]
        internal static void Postfix(Vessel __instance)
        {
            if (!HighLogic.LoadedSceneIsFlight) return;
            if (__instance == null || __instance != FlightGlobals.ActiveVessel) return;
            AxeAvionicsController ctl = AxeAvionicsController.Instance;
            if (ctl == null) return;
            ctl.ApplyDegradation(__instance.ctrlState);
        }
    }
}
