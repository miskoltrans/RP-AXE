using System;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe.Airlaunch
{
    /// <summary>
    /// Session carrier for the airlaunch choice. The editor hook stashes the chosen params here right
    /// before it lets the stock launch proceed; the flight-scene hook consumes them once the vessel has
    /// spawned on the runway. Editor -> flight is a single scene hop inside one session, so a static field
    /// is sufficient (no ScenarioModule / save persistence needed).
    ///
    /// The applied record is the same idea one step further on. "Revert to Launch" does not re-run the
    /// editor, it reloads FlightDriver.PostInitState — the vessel as it spawned, on the runway — so a
    /// one-shot pending value leaves the player reverting onto the runway instead of back into the air.
    /// The restored vessel keeps KSP's own Guid, so that id identifies the launch across any number of
    /// reverts; RP-1 uses the same trick (SpaceCenterManagement keeps AirlaunchParams.KSPVesselId alive
    /// past the first run for exactly this case). Session-scoped as well: stock can't revert across a
    /// save/quit/reload anyway (PostInitState is a static that a fresh process starts empty), so
    /// persisting this would buy nothing.
    /// </summary>
    public static class AxeAirlaunchState
    {
        private static AxeAirlaunchParams _pending;

        private static AxeAirlaunchParams _applied;
        private static Guid _appliedVesselId;
        private static AxeAirlaunchSite _appliedSite;

        /// <summary>True if some vessel this session has been airlaunched and could still be reverted.</summary>
        public static bool HasApplied => _applied != null;

        public static void SetPending(AxeAirlaunchParams p) => _pending = p;

        public static AxeAirlaunchParams ConsumePending()
        {
            AxeAirlaunchParams p = _pending;
            _pending = null;
            return p;
        }

        /// <summary>Record an airlaunch we just carried out, so a revert-to-launch can repeat it.</summary>
        public static void SetApplied(AxeAirlaunchParams p, Guid vesselId, AxeAirlaunchSite site)
        {
            _applied = p;
            _appliedVesselId = vesselId;
            _appliedSite = site;
        }

        /// <summary>The airlaunch to repeat for a vessel that just respawned, or false if it isn't ours.</summary>
        public static bool TryGetApplied(Guid vesselId, out AxeAirlaunchParams p, out AxeAirlaunchSite site)
        {
            p = null;
            site = null;
            if (_applied == null || vesselId != _appliedVesselId) return false;
            p = _applied;
            site = _appliedSite;
            return true;
        }

        /// <summary>Drop everything — the launch session is over (the player is back in the editor).</summary>
        public static void Clear()
        {
            _pending = null;
            _applied = null;
            _appliedVesselId = Guid.Empty;
            _appliedSite = null;
        }
    }

    /// <summary>
    /// The launch site an airlaunch was measured from, kept in geodetic terms so it can be rebuilt at any
    /// planet rotation. Recorded when the airlaunch first runs and reused if it runs again, so a revert
    /// releases exactly where the original launch did no matter where the restored vessel sits: stock
    /// snapshots the revert state 15 frames into the scene (FlightDriver.framesBeforeInitialSave), which
    /// is a frame race against our own teleport, so the vessel can come back either on the runway or
    /// already moved. Anchoring on the site takes that race out of the answer.
    /// </summary>
    public class AxeAirlaunchSite
    {
        public string BodyName;
        public double Latitude, Longitude, Altitude;

        public static AxeAirlaunchSite FromVessel(Vessel v)
        {
            CelestialBody b = v.mainBody;
            Vector3d wp = v.GetWorldPos3D();
            return new AxeAirlaunchSite
            {
                BodyName = b.bodyName,
                Latitude = b.GetLatitude(wp),
                Longitude = b.GetLongitude(wp),
                Altitude = b.GetAltitude(wp),
            };
        }

        /// <summary>Body-relative position (Unity XYZ) of the site, or null if it isn't on this body.</summary>
        public Vector3d? RelativePosition(CelestialBody body)
        {
            if (body == null || body.bodyName != BodyName) return null;
            return body.GetWorldSurfacePosition(Latitude, Longitude, Altitude) - body.position;
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

            int roots = GameDatabase.Instance.GetConfigNodes("KCTAIRLAUNCHTECHS").Length;
            if (roots == 0)
                Debug.LogWarning("[AXE][Airlaunch] no KCTAIRLAUNCHTECHS found -- airlaunch has no envelopes and "
                    + "will never offer itself. Expected design/Tree/AxeAirlaunch.cfg to supply them.");
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
