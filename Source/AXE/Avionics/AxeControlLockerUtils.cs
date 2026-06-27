using System.Collections.Generic;

namespace RPAxe
{
    /// <summary>
    /// Decides whether a vessel's ATTITUDE control should be locked (the "dumb rocket" state).
    ///
    /// RP-AXE rule — NO mass anywhere. Attitude is locked UNLESS one of:
    ///   * a crewed command part is present (pilot flies),           — both are "a valid ModuleCommand
    ///   * a bare probe core is present (ModuleCommand, no Core),       that is NOT an Avionics Core" → bypass
    ///   * an Avionics Core has guidance active.
    /// So only craft whose sole command source is a guidance-off / not-yet-researched Core fly dumb.
    ///
    /// Adapted from RP-1 ControlLockerUtils.ShouldLock with all controllable-mass logic removed.
    /// </summary>
    public static class AxeControlLockerUtils
    {
        public static bool ShouldLock(List<Part> parts)
        {
            if (parts == null || parts.Count == 0) return false;
            if (!HighLogic.LoadedSceneIsFlight && !HighLogic.LoadedSceneIsEditor) return false;

            Vessel vessel = parts[0].vessel;
            if (vessel != null && vessel.isEVA) return false;

            bool bypass = false;      // a non-Core command source grants control outright
            bool coreGuided = false;  // an Avionics Core with guidance active grants control

            foreach (Part p in parts)
            {
                bool isCore = false;
                bool guided = false;
                bool cmd = false;

                foreach (PartModule m in p.Modules)
                {
                    if (m is ModuleAxeAvionics axe)
                    {
                        isCore = true;
                        if (axe.GuidanceActive) guided = true;
                    }
                    else if (m is ModuleCommand mc && (IsValidCommand(mc) || HighLogic.LoadedSceneIsEditor))
                    {
                        cmd = true;
                    }
                }

                if (isCore && guided) coreGuided = true;
                if (cmd && !isCore) bypass = true; // crewed pod OR bare probe core (a Core's own command never bypasses)
            }

            return !(bypass || coreGuided);
        }

        static bool IsValidCommand(ModuleCommand mc) =>
            mc.ModuleState == ModuleCommand.ModuleControlState.Nominal ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialProbe ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialManned;
    }
}
