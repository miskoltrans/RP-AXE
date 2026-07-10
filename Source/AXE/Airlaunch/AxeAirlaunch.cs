using System.Collections.Generic;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// Session carrier for the airlaunch choice. The editor hook stashes the chosen params here right
    /// before it lets the stock launch proceed; the flight-scene hook consumes them once the vessel has
    /// spawned on the runway. Editor -> flight is a single scene hop inside one session, so a static field
    /// is sufficient (no ScenarioModule / save persistence needed).
    /// </summary>
    public static class AxeAirlaunchState
    {
        private static AxeAirlaunchParams _pending;

        public static void SetPending(AxeAirlaunchParams p) => _pending = p;

        public static AxeAirlaunchParams ConsumePending()
        {
            AxeAirlaunchParams p = _pending;
            _pending = null;
            return p;
        }
    }

    /// <summary>The player-chosen release condition, validated against the unlocked envelope.</summary>
    public class AxeAirlaunchParams
    {
        public double Altitude;      // m above sea level
        public double Velocity;      // m/s surface-relative
        public double Heading = 270; // degrees; release heading (direction of travel). 270 = due west.
        public double Distance;      // m downrange from the launch site; 0 = straight above it
        public double Bearing = 90;  // degrees; compass bearing from the launch site to the drop point (90 = E)

        public bool Validate(AxeAirlaunchTechLevel lvl, out string err)
        {
            if (lvl == null) { err = "No airlaunch capability unlocked"; return false; }

            if (Altitude > lvl.MaxAltitude || Altitude < lvl.MinAltitude)
                err = $"Altitude must be {lvl.MinAltitude:0}–{lvl.MaxAltitude:0} m";
            else if (Velocity > lvl.MaxVelocity || Velocity < lvl.MinVelocity)
                err = $"Velocity must be {lvl.MinVelocity:0}–{lvl.MaxVelocity:0} m/s";
            else if (Distance < 0 || Distance > lvl.MaxKscDistance)
                err = $"Downrange must be 0–{lvl.MaxKscDistance / 1000:0} km";
            else if (Heading < 0 || Heading >= 360)
                err = "Heading must be 0–360°";
            else if (Bearing < 0 || Bearing >= 360)
                err = "Bearing must be 0–360°";
            else
                err = null;

            return err == null;
        }
    }

    /// <summary>
    /// One tech-gated airlaunch envelope, loaded from a KCTAIRLAUNCHTECHS/AIRLAUNCHTECHLEVEL config node.
    /// Ported from RP-1's <c>AirlaunchTechLevel</c>, minus the ROUtils ConfigNode persistence base (parsed
    /// by hand here) and with the vessel check taking editor mass/size directly instead of a KCT
    /// VesselProject. <c>LaunchCost</c> is an AXE addition (the per-launch funds fee).
    /// </summary>
    public class AxeAirlaunchTechLevel
    {
        public string TechRequired;
        public double MinAltitude, MaxAltitude, MaxKscDistance, MinVelocity, MaxVelocity, MaxMass, LaunchCost;
        public Vector3 MaxSize;

        private static List<AxeAirlaunchTechLevel> _levels;

        public bool IsUnlocked =>
            ResearchAndDevelopment.GetTechnologyState(TechRequired) == RDTech.State.Available;

        /// <summary>Highest unlocked envelope, or null if none. Config is ordered by progression.</summary>
        public static AxeAirlaunchTechLevel GetCurrentLevel()
        {
            EnsureLoaded();
            for (int i = _levels.Count - 1; i >= 0; i--)
                if (_levels[i].IsUnlocked) return _levels[i];
            return null;
        }

        public static bool AnyUnlocked() => GetCurrentLevel() != null;

        /// <summary>Does a ship of this mass (tonnes) and bounding size fit this envelope?</summary>
        public bool CanLaunch(double massTonnes, Vector3 size, out string reason)
        {
            // Config MaxMass is in kg (RP-1 convention: 7500 == "7.5 t").
            if (massTonnes * 1000.0 > MaxMass)
            {
                reason = $"Too heavy: {massTonnes:0.#} t exceeds the {MaxMass / 1000.0:0.#} t limit";
                return false;
            }

            // Orientation-independent fit: compare the two boxes' sorted dimensions. Avoids false rejects
            // from the craft-size axis order not matching the config's width/height/length order.
            Vector3 s = SortDesc(size);
            Vector3 m = SortDesc(MaxSize);
            if (s.x > m.x || s.y > m.y || s.z > m.z)
            {
                reason = $"Too large: {size.x:0.#} x {size.y:0.#} x {size.z:0.#} m exceeds " +
                         $"{MaxSize.x:0.#} x {MaxSize.y:0.#} x {MaxSize.z:0.#} m";
                return false;
            }

            reason = null;
            return true;
        }

        private static Vector3 SortDesc(Vector3 v)
        {
            float a = v.x, b = v.y, c = v.z, t;
            if (a < b) { t = a; a = b; b = t; }
            if (b < c) { t = b; b = c; c = t; }
            if (a < b) { t = a; a = b; b = t; }
            return new Vector3(a, b, c);
        }

        private static void EnsureLoaded()
        {
            if (_levels != null) return;
            _levels = new List<AxeAirlaunchTechLevel>();

            foreach (ConfigNode parent in GameDatabase.Instance.GetConfigNodes("KCTAIRLAUNCHTECHS"))
            {
                foreach (ConfigNode n in parent.GetNodes("AIRLAUNCHTECHLEVEL"))
                {
                    var lvl = new AxeAirlaunchTechLevel();
                    n.TryGetValue("TechRequired", ref lvl.TechRequired);
                    n.TryGetValue("MinAltitude", ref lvl.MinAltitude);
                    n.TryGetValue("MaxAltitude", ref lvl.MaxAltitude);
                    n.TryGetValue("MaxKscDistance", ref lvl.MaxKscDistance);
                    n.TryGetValue("MinVelocity", ref lvl.MinVelocity);
                    n.TryGetValue("MaxVelocity", ref lvl.MaxVelocity);
                    n.TryGetValue("MaxMass", ref lvl.MaxMass);
                    n.TryGetValue("LaunchCost", ref lvl.LaunchCost);
                    Vector3 sz = Vector3.zero;
                    if (n.TryGetValue("MaxSize", ref sz)) lvl.MaxSize = sz;
                    _levels.Add(lvl);
                }
            }
            Debug.Log($"[AXE] airlaunch: loaded {_levels.Count} envelope level(s).");
        }
    }
}
