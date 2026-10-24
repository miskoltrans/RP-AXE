using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace RPAxe.AutoTest
{
    /// <summary>
    /// AutoTest step: do the planet pack's biome maps work? For every body with a biome map it samples
    /// <c>ScienceUtil.GetExperimentBiome</c> -- the lookup science itself uses -- on a 1-degree lat/lon grid
    /// and compares the biomes found with the ones the map defines. Written for Sol, whose biome maps ship
    /// in the per-system texture packs: a map that fails to load leaves the body with one biome (or none),
    /// and every biome-dependent experiment then pays once there instead of once per biome, with no error.
    ///
    /// FAIL: a map that throws, or one that resolves to a single biome when it defines several. Biomes the
    /// grid never lands on are listed, not failed (a 1-degree grid can miss a small one). Bodies without a
    /// map are listed. Also reports the launch site's biome.
    ///
    /// Opt in with `biomeTest = true` in AutoTest.cfg or `-axe-autotest-biomes` on the command line.
    /// </summary>
    internal static class AxeBiomeSelfTest
    {
        internal const string Tag = "[AXE][AutoTest][BIOME] ";
        internal const string CmdFlag = "-axe-autotest-biomes";
        const double StepDeg = 1.0;

        internal static IEnumerator Run()
        {
            bool ok = true;
            var unmapped = new List<string>();
            int mapped = 0;
            foreach (CelestialBody b in FlightGlobals.Bodies)
            {
                CBAttributeMapSO map = b.BiomeMap;
                int defined = map?.Attributes?.Length ?? 0;
                if (map == null || defined == 0) { unmapped.Add(b.bodyName); continue; }
                mapped++;

                var hits = new Dictionary<string, int>();
                string error = null;
                try
                {
                    for (double lat = -90.0 + StepDeg / 2.0; lat < 90.0; lat += StepDeg)
                        for (double lon = -180.0 + StepDeg / 2.0; lon < 180.0; lon += StepDeg)
                        {
                            string n = ScienceUtil.GetExperimentBiome(b, lat, lon);
                            if (string.IsNullOrEmpty(n)) n = "<empty>";
                            hits.TryGetValue(n, out int c);
                            hits[n] = c + 1;
                        }
                }
                catch (Exception e) { error = e.GetType().Name + ": " + e.Message; }

                var names = map.Attributes.Select(a => a.name).ToList();
                var missed = names.Where(n => !hits.ContainsKey(n)).ToList();
                var unknown = hits.Keys.Where(n => !names.Contains(n)).ToList();
                bool bodyOk = error == null && !(defined > 1 && hits.Count < 2) && unknown.Count == 0;
                ok &= bodyOk;
                Debug.Log(Tag + (bodyOk ? "ok   " : "FAIL ") + b.bodyName + ": " + (hits.Count - unknown.Count) + "/" + defined +
                          " biomes on the grid" +
                          (missed.Count > 0 ? "; not on the grid: " + string.Join(", ", missed.ToArray()) : "") +
                          (unknown.Count > 0 ? "; NOT DEFINED: " + string.Join(", ", unknown.ToArray()) : "") +
                          (error != null ? "; threw " + error : ""));
                yield return null;   // one body per frame, so the scene keeps rendering
            }

            SpaceCenter sc = SpaceCenter.Instance;
            if (sc != null && sc.cb != null)
                Debug.Log(Tag + "launch site on " + sc.cb.bodyName + " at " + sc.Latitude.ToString("0.00") + ", " +
                          sc.Longitude.ToString("0.00") + ": biome '" + ScienceUtil.GetExperimentBiome(sc.cb, sc.Latitude, sc.Longitude) + "'");
            Debug.Log(Tag + "bodies without a biome map: " + (unmapped.Count > 0 ? string.Join(", ", unmapped.ToArray()) : "none"));
            Debug.Log(Tag + "RESULT " + (ok ? "PASS" : "FAIL") + " (" + mapped + " of " + FlightGlobals.Bodies.Count + " bodies mapped)");
        }
    }
}
