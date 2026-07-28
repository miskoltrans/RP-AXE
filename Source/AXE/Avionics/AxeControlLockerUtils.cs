using System.Collections.Generic;

namespace RPAxe
{
    /// <summary>
    /// Decides whether a vessel's ATTITUDE control should be locked (the "dumb rocket" state).
    ///
    /// Three control levels (mirrors RP-1's LockLevel):
    ///   * Unlocked — full control, when any of: a crewed command part, a procedural Avionics Core with
    ///     guidance active, or a fixed-capacity unit rated for at least the vessel's mass.
    ///   * Axial    — axial-thrust only (rotation locked), when the only guidance available is axial:
    ///     a Science-Core whose tier permits axial thrust, or an over-capacity fixed unit with allowAxial
    ///     (both are the spin-stabilized kick-stage case).
    ///   * Locked   — fully dumb (throttle + staging only), otherwise.
    ///
    /// MASS RULE — applies to FIXED-capacity units only (<see cref="ModuleAxeFixedAvionics"/>), not to the
    /// procedural core. The procedural core deliberately has no mass gate: the player sizes its box, and
    /// going over its capacity costs a smooth EC-draw penalty rather than a lock, so a slightly-undersized
    /// box degrades instead of bricking the flight (docs/AVIONICS_SPEC.md). A fixed unit has no sizing
    /// decision to get wrong — its capacity is authored hardware — so it uses RP-1's original rule, which
    /// is both more faithful and far more legible than routing it through the penalty curve (a capacity-0
    /// part on the penalty path would draw exp(80) watts, flatten the battery and drop ModuleCommand
    /// altogether, losing staging and throttle too — RP-1 kept those and locked only attitude).
    ///
    /// Vessel mass is whole-vessel WET mass (part.mass + part.resourceMass), and the budget is the MAX
    /// across parts, never the sum — RP-1's own anti-cheese rule, matching the procedural core's
    /// EffectiveCapacityTons(). Bolting on a second bus does not double what you can steer.
    ///
    /// Launch clamps are excluded from vessel mass while in the editor or on the pad, and never grant the
    /// bypass, so a pad structure that happens to carry a ModuleCommand (the ModularLaunchPads stands all
    /// do) can neither make a rocket controllable nor eat its mass budget. RP-1 also zeroed parts tagged
    /// HasPadInfrastructure; AXE cut ModuleTagList entirely (design/StripAxedRP1Modules.cfg), so the clamp
    /// check is the whole of it here.
    ///
    /// Adapted from RP-1 ControlLockerUtils.ShouldLock.
    /// </summary>
    public static class AxeControlLockerUtils
    {
        public enum LockLevel { Locked, Axial, Unlocked }

        public static LockLevel ShouldLock(List<Part> parts) => ShouldLock(parts, out _, out _);

        /// <param name="maxCapacity">Steerable-mass budget: MAX across fixed-capacity units, in tons.</param>
        /// <param name="vesselMass">Whole-vessel wet mass measured against it, in tons.</param>
        public static LockLevel ShouldLock(List<Part> parts, out float maxCapacity, out float vesselMass)
        {
            maxCapacity = 0f;
            vesselMass = 0f;
            if (parts == null || parts.Count == 0) return LockLevel.Unlocked;
            if (!HighLogic.LoadedSceneIsFlight && !HighLogic.LoadedSceneIsEditor) return LockLevel.Unlocked;

            Vessel vessel = parts[0].vessel;
            if (vessel != null && vessel.isEVA) return LockLevel.Unlocked;

            // Clamps only count as clamps in the editor or on the pad; once flying they are long gone.
            bool ignoreClamps = !HighLogic.LoadedSceneIsFlight
                                || vessel == null
                                || vessel.situation == Vessel.Situations.PRELAUNCH;

            bool bypass = false;      // a non-avionics command source grants control outright
            bool coreGuided = false;  // a procedural Avionics Core with guidance active grants full control
            bool coreAxial = false;   // a Science-Core Avionics Core grants axial-thrust-only control
            bool fixedAxial = false;  // a fixed unit that keeps axial thrust when over capacity

            foreach (Part p in parts)
            {
                bool isCore = false;
                bool guided = false;
                bool axial = false;
                bool cmd = false;
                bool isClamp = false;
                bool hasFixed = false;
                float partCapacity = 0f;
                float partMass = p.mass + p.resourceMass;

                foreach (PartModule m in p.Modules)
                {
                    if (m is ModuleAxeAvionics axe)
                    {
                        isCore = true;
                        if (axe.GuidanceActive) guided = true;
                        if (axe.AxialActive) axial = true;
                    }
                    else if (m is ModuleAxeFixedAvionics fix)
                    {
                        isCore = true;
                        hasFixed = true;
                        partCapacity += fix.CapacityTons;   // summed within a part, MAX across parts
                        if (fix.allowAxial) fixedAxial = true;
                    }
                    else if (m is ModuleCommand mc && (IsValidCommand(mc) || HighLogic.LoadedSceneIsEditor))
                    {
                        cmd = true;
                    }
                    else if (m is LaunchClamp)
                    {
                        isClamp = true;
                    }
                }

                if (isClamp && ignoreClamps) partMass = 0f;
                vesselMass += partMass;

                if (isCore && guided) coreGuided = true;
                if (isCore && axial) coreAxial = true;
                if (hasFixed && partCapacity > maxCapacity) maxCapacity = partCapacity;
                // crewed pod OR a probe core with no avionics at all (an avionics unit's own command never
                // bypasses; neither does a launch clamp's, or every pad stand would unlock the rocket).
                if (cmd && !isCore && !isClamp) bypass = true;
            }

            if (bypass || coreGuided) return LockLevel.Unlocked;
            if (maxCapacity > 0f && vesselMass <= maxCapacity) return LockLevel.Unlocked;
            return (coreAxial || fixedAxial) ? LockLevel.Axial : LockLevel.Locked;
        }

        static bool IsValidCommand(ModuleCommand mc) =>
            mc.ModuleState == ModuleCommand.ModuleControlState.Nominal ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialProbe ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialManned;
    }
}
