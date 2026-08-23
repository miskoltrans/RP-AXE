using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace RPAxe.Bridge
{
    /// <summary>
    /// The endpoints. All read-only; nothing here mutates a vessel, a node, or the save.
    ///
    /// Every vector is in the right-handed z-up frame (Planetarium.Zup) that
    /// <c>Orbit.getRelativePositionAtUT</c> and <c>getOrbitalVelocityAtUT</c> already return —
    /// the same frame tools/mission works in — so no handedness conversion happens anywhere on
    /// this path. Angles are in the units KSP stores them: inclination/LAN/argP in DEGREES,
    /// mean anomaly in RADIANS. That mismatch is KSP's, and it is reported rather than papered
    /// over so the reader can be checked against the save format.
    /// </summary>
    public static class AxeBridgeHandlers
    {
        private static readonly PatchedConics.SolverParameters Solver = new PatchedConics.SolverParameters();

        public static string Handle(AxeBridgeServer.Request req)
        {
            switch (req.Path)
            {
                case "/": case "/ping": return Ping();
                case "/bodies": return Bodies();
                case "/predict": return Predict(req);
                default:
                    return "{\"ok\":false,\"error\":\"unknown path " + req.Path
                         + "; try /ping /bodies /predict. Live VESSEL state comes from "
                         + "KSPTOT Connect on 8282, which already serves it -- see tools/mission/ksptot.py\"}";
            }
        }

        // --- readiness -------------------------------------------------------
        /// <summary>
        /// A scene can be loaded while its data is still empty for a frame or two, which reads as
        /// "no bodies" rather than "not ready yet". Test readiness explicitly and say which it is.
        /// </summary>
        private static string NotReady(bool needGame = true)
        {
            if (FlightGlobals.Bodies == null || FlightGlobals.Bodies.Count == 0)
                return "{\"ok\":false,\"error\":\"FlightGlobals.Bodies is empty; the scene is still loading\"}";
            // Bodies exist at the main menu; vessels and the clock do not. Ask for only
            // what the endpoint actually needs, or /bodies refuses for no reason.
            if (needGame && HighLogic.CurrentGame == null)
                return "{\"ok\":false,\"error\":\"no game loaded (open a save first)\"}";
            return null;
        }

        /// <summary>
        /// Planetarium.fetch is null until the scene is up, and GetUniversalTime() derefs it
        /// without a guard -- so "what time is it" throws while KSP is still loading, which is
        /// exactly when a client is most likely to ask.
        /// </summary>
        private static double SafeUT()
        {
            return Planetarium.fetch != null ? Planetarium.GetUniversalTime() : double.NaN;
        }

        private static string Ping()
        {
            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("scene", HighLogic.LoadedScene.ToString());
            j.Val("game", HighLogic.CurrentGame != null ? HighLogic.CurrentGame.Title : null);
            j.Val("ut", SafeUT());
            // FlightGlobals.Vessels and .ActiveVessel both dereference FlightGlobals.fetch,
            // which is null until the scene is up -- so "are you there yet" throws during
            // exactly the window a client is most likely to be asking in.
            bool fg = FlightGlobals.fetch != null;
            j.Val("bodies", FlightGlobals.Bodies != null ? FlightGlobals.Bodies.Count : 0);
            j.Val("vessels", fg && FlightGlobals.Vessels != null ? FlightGlobals.Vessels.Count : 0);
            j.Val("active", fg && FlightGlobals.ActiveVessel != null
                  ? FlightGlobals.ActiveVessel.vesselName : null);
            j.Val("bridge", "1.0");
            return j.EndObj().ToString();
        }

        // --- bodies ----------------------------------------------------------
        private static string Bodies()
        {
            string bad = NotReady(needGame: false);
            if (bad != null) return bad;
            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("ut", SafeUT());
            j.Arr("bodies");
            for (int i = 0; i < FlightGlobals.Bodies.Count; i++)
            {
                CelestialBody b = FlightGlobals.Bodies[i];
                j.Obj();
                // `index` is the FlightGlobals.Bodies position -- what a save's ORBIT.REF stores.
                // `flight_globals_index` is the cfg field, which is NOT the same number.
                j.Val("index", i);
                j.Val("flight_globals_index", b.flightGlobalsIndex);
                j.Val("name", b.bodyName);
                j.Val("parent", b.referenceBody != null && b.referenceBody != b ? b.referenceBody.bodyName : null);
                j.Val("mu", b.gravParameter);
                j.Val("radius", b.Radius);
                j.Val("soi", b.sphereOfInfluence);
                j.Val("rotation_period", b.rotationPeriod);
                Orbit o = b.orbit;
                if (o != null && b.referenceBody != null && b.referenceBody != b)
                {
                    j.Val("sma", o.semiMajorAxis);
                    j.Val("ecc", o.eccentricity);
                    j.Val("inc_deg", o.inclination);
                    j.Val("lan_deg", o.LAN);
                    j.Val("argp_deg", o.argumentOfPeriapsis);
                    j.Val("mna_rad", o.meanAnomalyAtEpoch);
                    j.Val("epoch", o.epoch);
                    double ut = SafeUT();
                    if (!double.IsNaN(ut))
                    {
                        j.Vec("r", o.getRelativePositionAtUT(ut));
                        j.Vec("v", o.getOrbitalVelocityAtUT(ut));
                    }
                }
                j.EndObj();
            }
            j.EndArr();
            return j.EndObj().ToString();
        }

        // --- vessel lookup ---------------------------------------------------
        // There is deliberately no /vessels or /vessel endpoint. KSPTOT Connect ships with
        // KSPTOT, is already installed, and already answers GetVesselIDList /
        // GetVesselNameByGUID / GetVesselOrbitByGUID. Duplicating that here bought nothing.
        // What it cannot do is run KSP's own patched-conic solver over a hypothetical burn,
        // which is what /predict is for -- so FindVessel stays, purely to serve it.

        private static Vessel FindVessel(AxeBridgeServer.Request req)
        {
            string id = req.Get("id");
            string name = req.Get("vessel") ?? req.Get("name");
            var list = FlightGlobals.Vessels ?? new List<Vessel>();
            if (!string.IsNullOrEmpty(id))
            {
                // KSPTOT Connect hands out Guid.ToString("N") -- 32 hex digits, no dashes --
                // while Vessel.id.ToString() is dashed. Compare the digits only, or every
                // GUID handed over from that side silently matches nothing.
                string want = id.Replace("-", "").ToLowerInvariant();
                return list.FirstOrDefault(v => v != null
                    && v.id.ToString("N").ToLowerInvariant() == want);
            }
            if (!string.IsNullOrEmpty(name))
            {
                Vessel exact = list.FirstOrDefault(v => v != null && v.vesselName == name);
                if (exact != null) return exact;
                var hits = list.Where(v => v != null && v.vesselName != null
                                      && v.vesselName.IndexOf(name, StringComparison.OrdinalIgnoreCase) >= 0).ToList();
                return hits.Count == 1 ? hits[0] : null;
            }
            return FlightGlobals.ActiveVessel;
        }

        private static string VesselDetail(AxeBridgeServer.Request req)
        {
            string bad = NotReady();
            if (bad != null) return bad;
            Vessel v = FindVessel(req);
            if (v == null)
                return "{\"ok\":false,\"error\":\"no vessel matched (pass ?id=<guid> or ?vessel=<name>); "
                     + "an ambiguous name matches nothing on purpose\"}";
            Orbit o = v.orbit;
            if (o == null || o.referenceBody == null)
                return "{\"ok\":false,\"error\":" + AxeJson.Str(v.vesselName + " has no orbit (" + v.situation + ")") + "}";
            double ut = req.GetNum("ut", SafeUT());

            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("ut", ut);
            j.Val("id", v.id.ToString());
            j.Val("name", v.vesselName);
            j.Val("situation", v.situation.ToString());
            j.Val("body", o.referenceBody.bodyName);
            j.Val("body_index", FlightGlobals.Bodies.IndexOf(o.referenceBody));
            j.Val("mu", o.referenceBody.gravParameter);
            j.Val("sma", o.semiMajorAxis);
            j.Val("ecc", o.eccentricity);
            j.Val("inc_deg", o.inclination);
            j.Val("lan_deg", o.LAN);
            j.Val("argp_deg", o.argumentOfPeriapsis);
            j.Val("mna_rad", o.meanAnomalyAtEpoch);
            j.Val("epoch", o.epoch);
            j.Val("peR", o.PeR);
            j.Val("apR", o.ApR);
            j.Val("period", o.period);
            j.Vec("r", o.getRelativePositionAtUT(ut));
            j.Vec("v", o.getOrbitalVelocityAtUT(ut));

            j.Arr("nodes");
            // patchedConicSolver only exists for the vessel the game is actually flying; for any
            // other vessel there is nothing to report, which is not the same as "no nodes".
            if (v.patchedConicSolver != null && v.patchedConicSolver.maneuverNodes != null)
            {
                foreach (ManeuverNode n in v.patchedConicSolver.maneuverNodes)
                {
                    j.Obj();
                    j.Val("ut", n.UT);
                    j.Val("radial", n.DeltaV.x);
                    j.Val("normal", n.DeltaV.y);
                    j.Val("prograde", n.DeltaV.z);
                    j.EndObj();
                }
                j.EndArr();
                j.Val("nodes_available", true);
            }
            else
            {
                j.EndArr();
                j.Val("nodes_available", false);
            }
            return j.EndObj().ToString();
        }

        // --- the one that matters --------------------------------------------
        /// <summary>
        /// Run KSP's own patched-conic solver on a proposed burn and report every patch.
        ///
        /// Nothing is placed and nothing is modified: the burn is applied to a throwaway Orbit
        /// built from state vectors, exactly as MechJeb's PatchedConicInterceptBody does. The dV
        /// arrives in maneuver-node components (radial, normal, prograde) and is rebuilt here
        /// from the same basis definition the Python side uses, so a sign disagreement would show
        /// up as a wildly different arrival rather than hiding.
        /// </summary>
        private static string Predict(AxeBridgeServer.Request req)
        {
            string bad = NotReady();
            if (bad != null) return bad;
            Vessel v = FindVessel(req);
            if (v == null || v.orbit == null || v.orbit.referenceBody == null)
                return "{\"ok\":false,\"error\":\"no vessel with an orbit matched\"}";

            double ut = req.GetNum("ut", SafeUT());
            double horizonDays = req.GetNum("horizon", 400.0);
            int maxPatches = (int)req.GetNum("maxpatches", 8);
            double dvR = 0, dvN = 0, dvP = 0;
            string dv = req.Get("dv");
            if (!string.IsNullOrEmpty(dv))
            {
                string[] p = dv.Split(',');
                if (p.Length != 3)
                    return "{\"ok\":false,\"error\":\"dv must be three numbers: radial,normal,prograde\"}";
                if (!double.TryParse(p[0], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out dvR)
                 || !double.TryParse(p[1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out dvN)
                 || !double.TryParse(p[2], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out dvP))
                    return "{\"ok\":false,\"error\":\"dv components must parse as numbers (use '.' for the decimal point)\"}";
            }

            Orbit start = v.orbit;
            Vector3d r = start.getRelativePositionAtUT(ut);      // Zup, right-handed
            Vector3d vel = start.getOrbitalVelocityAtUT(ut);
            Vector3d prograde = vel.normalized;
            Vector3d normal = Vector3d.Cross(r, vel).normalized;
            Vector3d radial = Vector3d.Cross(prograde, normal);
            Vector3d burn = radial * dvR + normal * dvN + prograde * dvP;

            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("vessel", v.vesselName);
            j.Val("ut", ut);
            j.Val("horizon_ut", ut + horizonDays * 86400.0);
            j.Vec("burn_zup", burn);
            j.Val("burn_mag", burn.magnitude);

            double endUT = ut + horizonDays * 86400.0;
            Orbit patch = new Orbit();
            patch.UpdateFromStateVectors(r, vel + burn, start.referenceBody, ut);
            patch.StartUT = ut;
            patch.EndUT = patch.eccentricity >= 1.0 ? patch.period : ut + patch.period;

            j.Arr("patches");
            int n = 0;
            bool more = true;
            while (n++ < maxPatches)
            {
                Orbit next = new Orbit();
                more = PatchedConics.CalculatePatch(patch, next, patch.StartUT, Solver, null);
                WritePatch(j, patch);
                if (!more || patch.EndUT >= endUT) break;
                patch = next;
            }
            j.EndArr();
            j.Val("patch_count", n);
            j.Val("truncated", n >= maxPatches);
            return j.EndObj().ToString();
        }

        private static void WritePatch(AxeJson j, Orbit p)
        {
            j.Obj();
            j.Val("body", p.referenceBody != null ? p.referenceBody.bodyName : null);
            j.Val("start_ut", p.StartUT);
            j.Val("end_ut", p.EndUT);
            j.Val("transition", p.patchEndTransition.ToString());
            j.Val("sma", p.semiMajorAxis);
            j.Val("ecc", p.eccentricity);
            j.Val("inc_deg", p.inclination);
            j.Val("lan_deg", p.LAN);
            j.Val("argp_deg", p.argumentOfPeriapsis);
            j.Val("peR", p.PeR);
            j.Val("apR", p.ApR);
            j.Val("ut_soi", p.UTsoi);
            j.Val("closest_encounter", p.closestEncounterBody != null ? p.closestEncounterBody.bodyName : null);
            j.Val("closest_encounter_level", p.closestEncounterLevel.ToString());
            j.Val("cl_appr", p.ClAppr);      // closest-approach distance the solver found
            j.Val("ut_appr", p.UTappr);
            j.EndObj();
        }
    }
}
