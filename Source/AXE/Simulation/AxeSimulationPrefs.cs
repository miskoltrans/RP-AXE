using System;
using System.IO;
using UnityEngine;

namespace RPAxe.Simulation
{
    /// <summary>
    /// Last-used simulation setup, so the window reopens on the scenario the player ran last instead of
    /// resetting to "home, 200x200" every time they walk back into the VAB.
    ///
    /// Stored per-career at <c>saves/&lt;save&gt;/AXE_sim_prefs.cfg</c> — a plain file *beside*
    /// persistent.sfs rather than inside it, because the sim's whole backbone is swapping persistent.sfs
    /// back (<see cref="AxeSimulationSave"/>); anything written into the save would be rolled back by the
    /// very simulation that set it. Values are kept as the raw field text so the box reads back exactly
    /// what was typed.
    /// </summary>
    internal static class AxeSimulationPrefs
    {
        private const string NodeName = "AXE_SIM_PREFS";
        private const string FileName = "AXE_sim_prefs.cfg";

        public static string BodyName = "";
        public static bool InOrbit;
        public static string Pe = "200", Ap = "200", Inc = "0", Delay = "0", Warp = "0";

        private static string _loadedFor;    // save folder the in-memory values came from ("" = none yet)
        private static bool _dirty;

        private static string FilePath
        {
            get
            {
                string save = HighLogic.SaveFolder;
                if (string.IsNullOrEmpty(save)) return null;
                return Path.Combine($"{KSPUtil.ApplicationRootPath}saves/{save}", FileName);
            }
        }

        /// <summary>Read the prefs file once per career. Cheap no-op on repeat calls.</summary>
        public static void Load()
        {
            string save = HighLogic.SaveFolder ?? "";
            if (_loadedFor == save) return;
            _loadedFor = save;
            _dirty = false;

            try
            {
                string path = FilePath;
                if (path == null || !File.Exists(path)) return;

                ConfigNode n = ConfigNode.Load(path)?.GetNode(NodeName);
                if (n == null) return;

                n.TryGetValue("body", ref BodyName);
                n.TryGetValue("inOrbit", ref InOrbit);
                n.TryGetValue("periapsisKm", ref Pe);
                n.TryGetValue("apoapsisKm", ref Ap);
                n.TryGetValue("inclinationDeg", ref Inc);
                n.TryGetValue("padDelaySec", ref Delay);
                n.TryGetValue("warpDays", ref Warp);
            }
            catch (Exception e)
            {
                Debug.LogWarning("[AXE][Sim] could not read remembered settings, using defaults: " + e.Message);
            }
        }

        /// <summary>Stash what's currently in the window. Only flags a write if something actually changed.</summary>
        public static void Capture(CelestialBody body, bool inOrbit,
                                   string pe, string ap, string inc, string delay, string warp)
        {
            string name = body != null ? body.bodyName : "";
            if (name != BodyName || inOrbit != InOrbit || pe != Pe || ap != Ap ||
                inc != Inc || delay != Delay || warp != Warp)
                _dirty = true;

            BodyName = name;
            InOrbit = inOrbit;
            Pe = pe; Ap = ap; Inc = inc; Delay = delay; Warp = warp;
        }

        public static void Save()
        {
            if (!_dirty) return;
            try
            {
                string path = FilePath;
                if (path == null) return;

                var root = new ConfigNode();
                ConfigNode n = root.AddNode(NodeName);
                n.AddValue("body", BodyName ?? "");
                n.AddValue("inOrbit", InOrbit);
                n.AddValue("periapsisKm", Pe ?? "");
                n.AddValue("apoapsisKm", Ap ?? "");
                n.AddValue("inclinationDeg", Inc ?? "");
                n.AddValue("padDelaySec", Delay ?? "");
                n.AddValue("warpDays", Warp ?? "");

                Directory.CreateDirectory(Path.GetDirectoryName(path));
                root.Save(path);
                _dirty = false;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[AXE][Sim] could not write remembered settings: " + e.Message);
            }
        }

        /// <summary>The remembered world, or home if it's gone (different install) or not unlocked in this
        /// career yet — a remembered target must never hand the player a target they can't launch at.</summary>
        public static CelestialBody ResolveBody()
        {
            CelestialBody home = Planetarium.fetch != null ? Planetarium.fetch.Home : null;
            if (string.IsNullOrEmpty(BodyName) || FlightGlobals.Bodies == null) return home;

            foreach (CelestialBody b in FlightGlobals.Bodies)
                if (b.bodyName == BodyName)
                    return AxeSimulationGate.CanSimulate(b) ? b : home;

            return home;
        }
    }
}
