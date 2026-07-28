using System;
using Upgradeables;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// AutoTest smoke check for the launchpad mass/size cap, Mission Control contract limit and the
    /// R&amp;D science-cost ladder (design/Settings/AxeFacilities.cfg → CustomBarnKit @LAUNCHPAD /
    /// @MISSION / @RESEARCH). It reads the LIVE GameVariables curve at every facility level, so it
    /// confirms the whole chain end-to-end: our config was consumed by CustomBarnKit and now shows up
    /// in GetCraftMassLimit / GetActiveContractsLimit / GetScienceCostLimit (the values stock KSP
    /// actually enforces at launch, in the contract system and in the R&amp;D screen). None of the three
    /// is tech-gated (RP-1 parity for the first two), so this only reports values — there is no gate
    /// to block.
    ///
    /// Expect on a fresh career:
    ///   launchpad      levels=7 massLimit=[25, 75, 200, 500, 1200, 3000, -1]
    ///   missionControl levels=5 contractLimit=[3, 5, 7, 10, -1]
    ///   rnd            levels=8 sciCap=[82, 265, 404, 600, 865, 1225, 1655, inf]
    ///                           price=[25000, 50000, 100000, 200000, 400000, 700000, 1200000]
    /// (-1 = unlimited, surfacing as "inf"). A "NOT FOUND" or a stock-looking curve (pad levels=3
    /// mass=[18,140,-1]; rnd levels=3 sciCap=[100,500,inf]) means the CustomBarnKit override did not
    /// apply. R&amp;D matters most here: CBK validates each per-level array against `levels` and, on a
    /// mismatch, logs "scienceCostLimit wrong size" and falls back to STOCK for that one field —
    /// restoring the 100/500 research wall with nothing visible in game. This is the check that
    /// catches it. `price` deliberately skips upgrades[0], the slot KSP never charges.
    /// </summary>
    internal static class AxeFacilitiesSelfTest
    {
        internal static string SelfTestReport()
        {
            return "launchpad " + PadReport() + " | missionControl " + McReport() + " | rnd " + RndReport();
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

        private static string RndReport()
        {
            UpgradeableFacility fac = Find("SpaceCenter/ResearchAndDevelopment");
            if (fac == null) return "NOT FOUND";
            GameVariables gv = GameVariables.Instance;
            int max = fac.MaxLevel;

            // The cap stock compares each node's scienceCost against (RDNode: RESEARCHABLE iff
            // cost < ScienceCap). CustomBarnKit maps a negative config entry to float.MaxValue.
            var caps = new string[max + 1];
            for (int i = 0; i <= max; i++)
            {
                float norm = max > 0 ? (float)i / max : 0f;
                float c = gv.GetScienceCostLimit(norm);
                caps[i] = c >= 1e12f ? "inf" : c.ToString("0.#");
            }

            // What the player is actually billed. KSP charges upgradeLevels[currentLevel + 1], so
            // index 0 is the starting level's own cost and is never paid — start at 1.
            var price = new string[max];
            var levels = fac.UpgradeLevels;
            for (int i = 1; i <= max; i++)
                price[i - 1] = (levels != null && i < levels.Length)
                    ? levels[i].levelCost.ToString("0") : "?";

            return "levels=" + (max + 1) + " curLevel=" + fac.FacilityLevel +
                   " sciCap=[" + string.Join(", ", caps) + "]" +
                   " price=[" + string.Join(", ", price) + "]";
        }
    }
}
