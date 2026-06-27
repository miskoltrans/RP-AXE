using System.Collections.Generic;

namespace RPAxe
{
    /// <summary>
    /// Decides whether a vessel's ATTITUDE control should be locked (the "dumb rocket" state).
    ///
    /// RP-AXE rule — NO mass anywhere. Three control levels (mirrors RP-1's LockLevel):
    ///   * Unlocked — full control, when any of: a crewed command part, a bare probe core, or a Near-Earth
    ///     Avionics Core with guidance active.
    ///   * Axial    — axial-thrust only (rotation locked), when the only command source is a Science-Core Core
    ///     whose tier permits axial thrust (spin-stabilized kick stages).
    ///   * Locked   — fully dumb (throttle + staging only), otherwise.
    ///
    /// Adapted from RP-1 ControlLockerUtils.ShouldLock with all controllable-mass logic removed.
    /// </summary>
    public static class AxeControlLockerUtils
    {
        public enum LockLevel { Locked, Axial, Unlocked }

        public static LockLevel ShouldLock(List<Part> parts)
        {
            if (parts == null || parts.Count == 0) return LockLevel.Unlocked;
            if (!HighLogic.LoadedSceneIsFlight && !HighLogic.LoadedSceneIsEditor) return LockLevel.Unlocked;

            Vessel vessel = parts[0].vessel;
            if (vessel != null && vessel.isEVA) return LockLevel.Unlocked;

            bool bypass = false;      // a non-Core command source grants control outright
            bool coreGuided = false;  // a Near-Earth Avionics Core with guidance active grants full control
            bool coreAxial = false;   // a Science-Core Avionics Core grants axial-thrust-only control

            foreach (Part p in parts)
            {
                bool isCore = false;
                bool guided = false;
                bool axial = false;
                bool cmd = false;

                foreach (PartModule m in p.Modules)
                {
                    if (m is ModuleAxeAvionics axe)
                    {
                        isCore = true;
                        if (axe.GuidanceActive) guided = true;
                        if (axe.AxialActive) axial = true;
                    }
                    else if (m is ModuleCommand mc && (IsValidCommand(mc) || HighLogic.LoadedSceneIsEditor))
                    {
                        cmd = true;
                    }
                }

                if (isCore && guided) coreGuided = true;
                if (isCore && axial) coreAxial = true;
                if (cmd && !isCore) bypass = true; // crewed pod OR bare probe core (a Core's own command never bypasses)
            }

            if (bypass || coreGuided) return LockLevel.Unlocked;
            return coreAxial ? LockLevel.Axial : LockLevel.Locked;
        }

        static bool IsValidCommand(ModuleCommand mc) =>
            mc.ModuleState == ModuleCommand.ModuleControlState.Nominal ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialProbe ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialManned;
    }
}
