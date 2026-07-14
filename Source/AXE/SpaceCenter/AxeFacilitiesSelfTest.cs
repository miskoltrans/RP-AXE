using System;
using Upgradeables;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// AutoTest smoke check for the launchpad mass/size cap + Mission Control contract limit
    /// (design/Settings/AxeFacilities.cfg → CustomBarnKit @LAUNCHPAD / @MISSION). It reads the LIVE
    /// GameVariables curve at every facility level, so it confirms the whole chain end-to-end: our
    /// config was consumed by CustomBarnKit and now shows up in GetCraftMassLimit /
    /// GetActiveContractsLimit (the values stock KSP actually enforces at launch and in the contract
    /// system). Unlike the tracking station, neither facility is tech-gated (RP-1 parity), so this
    /// only reports values — there is no gate to block.
    ///
    /// Expect on a fresh career:
    ///   launchpad      levels=7 massLimit=[25, 75, 200, 500, 1200, 3000, -1]
    ///   missionControl levels=5 contractLimit=[3, 5, 7, 10, -1]
    /// (-1 = unlimited). A "NOT FOUND" or a stock-looking curve (pad levels=3 mass=[18,140,-1])
    /// means the CustomBarnKit override did not apply.
    /// </summary>
    internal static class AxeFacilitiesSelfTest
    {
        internal static string SelfTestReport()
        {
            return "launchpad " + PadReport() + " | missionControl " + McReport();
        }

        private static UpgradeableFacility Find(string id)
        {
            foreach (var f in UnityEngine.Object.FindObjectsOfType<UpgradeableFacility>())
                if (f != null && f.id == id) return f;
            return null;
        }

        private static string PadReport()
        {
            UpgradeableFacility fac = Find("SpaceCenter/LaunchPad");
            if (fac == null) return "NOT FOUND";
            GameVariables gv = GameVariables.Instance;
            int max = fac.MaxLevel;
            var mass = new string[max + 1];
            for (int i = 0; i <= max; i++)
            {
                float norm = max > 0 ? (float)i / max : 0f;
                float m = gv.GetCraftMassLimit(norm, true);
                mass[i] = m >= 1e12f ? "inf" : m.ToString("0.#");   // -1/unlimited surfaces as float.MaxValue
            }
            return "levels=" + (max + 1) + " curLevel=" + fac.FacilityLevel +
                   " massLimit=[" + string.Join(", ", mass) + "]";
        }

        private static string McReport()
        {
            UpgradeableFacility fac = Find("SpaceCenter/MissionControl");
            if (fac == null) return "NOT FOUND";
            GameVariables gv = GameVariables.Instance;
            int max = fac.MaxLevel;
            var caps = new string[max + 1];
            for (int i = 0; i <= max; i++)
            {
                float norm = max > 0 ? (float)i / max : 0f;
                int c = gv.GetActiveContractsLimit(norm);
                caps[i] = c >= int.MaxValue ? "inf" : c.ToString();   // -1/unlimited surfaces as int.MaxValue
            }
            return "levels=" + (max + 1) + " curLevel=" + fac.FacilityLevel +
                   " contractLimit=[" + string.Join(", ", caps) + "]";
        }
    }
}
