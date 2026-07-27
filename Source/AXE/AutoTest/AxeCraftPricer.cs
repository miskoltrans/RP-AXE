using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;

namespace RPAxe.AutoTest
{
    /// <summary>
    /// Dev tool: price every .craft in the install and dump a per-part cost breakdown, so the economy
    /// pass has a real "what does a vehicle cost" number instead of a guess.
    ///
    /// WHY IN-GAME: most of an AXE vehicle is procedural (ProceduralParts, RealFuels tanks, B9 wings,
    /// AXE avionics) and its cost is computed by the part's own <c>GetModuleCosts</c> from the
    /// dimensions stored in the craft file — a static read of the part configs reports the prefab's
    /// cost, which is wrong by a wide margin. Only a loaded ShipConstruct knows the real number.
    ///
    /// WHY THE EDITOR SCENE: instantiating a ShipConstruct runs OnLoad for every part + module, and
    /// FAR (installed here) assumes that only happens in the loading screen or the editor. RP-1's
    /// VesselProject.GetShip carries the same warning. So this is [KSPAddon(EditorAny)] and the
    /// AutoTest driver hands off to the VAB to trigger it.
    ///
    /// Cost model mirrors stock ShipConstruction.GetPartCosts: partInfo.cost already includes each
    /// resource at FULL, so dry = base + modules - (maxAmount * unitCost) and fuel = amount * unitCost.
    /// The per-ship total is cross-checked against stock's own GetShipCosts and any mismatch is logged
    /// rather than hidden — if the two disagree, trust stock and fix this.
    /// </summary>
    internal static class AxeCraftPricer
    {
        public static bool EditorPhaseRequested { get; private set; }
        public static void RequestEditorPhase() => EditorPhaseRequested = true;

        private const string ReportName = "craft-prices.csv";

        private static string ReportPath => Path.Combine(
            Path.Combine(KSPUtil.ApplicationRootPath, "GameData/RP-AXE/Plugins/PluginData"), ReportName);

        /// <summary>Every .craft under saves/*/Ships/{VAB,SPH}, excluding the autotest save's own.</summary>
        private static List<string> FindCraft()
        {
            var found = new List<string>();
            string savesRoot = Path.Combine(KSPUtil.ApplicationRootPath, "saves");
            if (!Directory.Exists(savesRoot)) return found;

            foreach (string save in Directory.GetDirectories(savesRoot))
            {
                string leaf = Path.GetFileName(save);
                if (string.Equals(leaf, AutoTestConfig.SaveName, StringComparison.OrdinalIgnoreCase)) continue;

                foreach (string sub in new[] { "Ships/VAB", "Ships/SPH" })
                {
                    string dir = Path.Combine(save, sub);
                    if (!Directory.Exists(dir)) continue;
                    found.AddRange(Directory.GetFiles(dir, "*.craft", SearchOption.TopDirectoryOnly));
                }
            }
            return found;
        }

        /// <summary>Price one craft; appends a row per part. Returns null on failure (reason logged).</summary>
        private static string PriceOne(string path, StringBuilder csv)
        {
            ShipConstruct sc = null;
            try
            {
                sc = ShipConstruction.LoadShip(path);
                if (sc == null || sc.Parts == null || sc.Parts.Count == 0)
                    return "load returned no parts";

                // Qualify by save folder: "Auto-Saved Ship" / "Untitled Space Craft" exist in several
                // saves, and a bare filename key silently merges them into one bogus vehicle.
                string norm = path.Replace('\\', '/');
                string facility = norm.Contains("/SPH/") ? "SPH" : "VAB";
                string save = "";
                int savesIx = norm.IndexOf("/saves/", StringComparison.OrdinalIgnoreCase);
                if (savesIx >= 0)
                {
                    string rest = norm.Substring(savesIx + "/saves/".Length);
                    int slash = rest.IndexOf('/');
                    if (slash > 0) save = rest.Substring(0, slash);
                }
                string craft = string.IsNullOrEmpty(save)
                    ? Path.GetFileNameWithoutExtension(path)
                    : save + "/" + Path.GetFileNameWithoutExtension(path);

                double shipDry = 0d, shipFuel = 0d, shipMass = 0d;

                foreach (Part p in sc.Parts)
                {
                    if (p == null || p.partInfo == null) continue;

                    float baseCost = p.partInfo.cost;
                    float moduleCost = 0f;
                    try { moduleCost = p.GetModuleCosts(baseCost, ModifierStagingSituation.CURRENT); }
                    catch (Exception e) { Debug.LogWarning("[AXE][Price] GetModuleCosts threw for " + p.partInfo.name + ": " + e.Message); }

                    double resourceAtFull = 0d, resourceLoaded = 0d;
                    if (p.Resources != null)
                    {
                        foreach (PartResource r in p.Resources)
                        {
                            if (r?.info == null) continue;
                            resourceAtFull += r.maxAmount * r.info.unitCost;
                            resourceLoaded += r.amount * r.info.unitCost;
                        }
                    }

                    // Stock convention: partInfo.cost is the FULL-tank price, so back the resources out.
                    double dry = baseCost + moduleCost - resourceAtFull;
                    double fuel = resourceLoaded;

                    double mass = 0d;
                    try { mass = p.mass + p.GetModuleMass(p.partInfo.partPrefab != null ? p.partInfo.partPrefab.mass : p.mass, ModifierStagingSituation.CURRENT); }
                    catch { mass = p.mass; }

                    shipDry += dry; shipFuel += fuel; shipMass += mass;

                    csv.Append(Csv(craft)).Append(',')
                       .Append(Csv(facility)).Append(',')
                       .Append(Csv(p.partInfo.name)).Append(',')
                       .Append(Csv(p.partInfo.title)).Append(',')
                       .Append(Num(baseCost)).Append(',')
                       .Append(Num(moduleCost)).Append(',')
                       .Append(Num(resourceAtFull)).Append(',')
                       .Append(Num(dry)).Append(',')
                       .Append(Num(fuel)).Append(',')
                       .Append(Num(dry + fuel)).Append(',')
                       .Append(Num(mass)).Append('\n');
                }

                // Cross-check against stock's own total. Disagreement means our model drifted.
                float stockDry = 0f, stockFuel = 0f;
                bool haveStock = false;
                try { sc.GetShipCosts(out stockDry, out stockFuel); haveStock = true; }
                catch (Exception e) { Debug.LogWarning("[AXE][Price] GetShipCosts unavailable: " + e.Message); }

                string check = haveStock
                    ? string.Format(CultureInfo.InvariantCulture,
                        " | stock dry={0:N0} fuel={1:N0}{2}", stockDry, stockFuel,
                        (Math.Abs(stockDry - shipDry) > 1.0 || Math.Abs(stockFuel - shipFuel) > 1.0) ? "  <== MISMATCH" : "  (match)")
                    : " | stock cross-check unavailable";

                Debug.Log(string.Format(CultureInfo.InvariantCulture,
                    "[AXE][Price] {0} [{1}] parts={2} dry={3:N0} fuel={4:N0} total={5:N0} mass={6:N2}t{7}",
                    craft, facility, sc.Parts.Count, shipDry, shipFuel, shipDry + shipFuel, shipMass, check));

                return null;
            }
            catch (Exception e)
            {
                return e.Message;
            }
            finally
            {
                // Never leave instantiated parts behind in the editor.
                if (sc?.Parts != null)
                {
                    foreach (Part p in sc.Parts)
                        if (p != null) UnityEngine.Object.Destroy(p.gameObject);
                    sc.Parts.Clear();
                }
            }
        }

        public static void Run()
        {
            List<string> craft = FindCraft();
            if (craft.Count == 0) { Debug.LogWarning("[AXE][Price] no .craft files found under saves/*/Ships."); return; }

            Debug.Log("[AXE][Price] pricing " + craft.Count + " craft...");
            var csv = new StringBuilder();
            csv.Append("craft,facility,part,title,baseCost,moduleCost,resourceAtFull,dryCost,fuelCost,totalCost,massT\n");

            int ok = 0;
            foreach (string path in craft.OrderBy(p => p))
            {
                string err = PriceOne(path, csv);
                if (err == null) ok++;
                else Debug.LogWarning("[AXE][Price] FAILED " + Path.GetFileName(path) + ": " + err);
            }

            try
            {
                string dir = Path.GetDirectoryName(ReportPath);
                if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);
                File.WriteAllText(ReportPath, csv.ToString());
                Debug.Log("[AXE][Price] wrote " + ok + "/" + craft.Count + " craft to " + ReportPath);
            }
            catch (Exception e) { Debug.LogError("[AXE][Price] could not write report: " + e); }
        }

        private static string Num(double d) => d.ToString("0.####", CultureInfo.InvariantCulture);

        private static string Csv(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.IndexOfAny(new[] { ',', '"', '\n' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        }

        /// <summary>Editor-scene half: runs the sweep once the VAB is up, then quits if asked.</summary>
        [KSPAddon(KSPAddon.Startup.EditorAny, false)]
        public class AxeCraftPricerEditorDriver : MonoBehaviour
        {
            private void Start()
            {
                AutoTestConfig.EnsureLoaded();
                if (!AutoTestConfig.Enabled || !EditorPhaseRequested) return;
                StartCoroutine(RunRoutine());
            }

            private IEnumerator RunRoutine()
            {
                // Let the editor finish spawning before instantiating anything into it.
                yield return AutoTestUtil.Dwell(Math.Max(2f, AutoTestConfig.SettleSeconds));

                try { Run(); }
                catch (Exception e) { Debug.LogError("[AXE][Price] sweep threw: " + e); }

                if (AutoTestConfig.QuitWhenDone)
                {
                    Debug.Log("[AXE][Price] done; quitting KSP in " + AutoTestConfig.QuitDelaySeconds + "s...");
                    yield return AutoTestUtil.Dwell(AutoTestConfig.QuitDelaySeconds);
                    Application.Quit();
                }
            }
        }
    }
}
