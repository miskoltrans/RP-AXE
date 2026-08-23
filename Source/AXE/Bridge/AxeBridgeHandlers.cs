using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace RPAxe.Bridge
{
    /// <summary>
    /// The endpoints.
    ///
    /// Most are read-only. Three are not: <c>/node</c> places maneuver nodes, <c>/node/clear</c>
    /// removes them, and <c>/alarm</c> creates an alarm. They are POST-only, so a browser or a
    /// stray GET cannot trip them, and they exist only because the alternative — reading six
    /// numbers off a terminal and typing them into a node gizmo — is where the mission planning
    /// actually loses its precision.
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
                case "/sites": return Sites();
                case "/predict": return Predict(req);
                case "/nodes": return Nodes(req);
                case "/node": return RequirePost(req) ?? PlaceNodes(req);
                case "/node/clear": return RequirePost(req) ?? ClearNodes(req);
                case "/alarms": return Alarms();
                case "/alarm": return RequirePost(req) ?? CreateAlarm(req);
                case "/alarm/delete": return RequirePost(req) ?? DeleteAlarm(req);
                default:
                    return "{\"ok\":false,\"error\":\"unknown path " + req.Path
                         + "; try /ping /bodies /sites /predict /nodes /alarms, or POST "
                         + "/node /node/clear /alarm /alarm/delete. Live VESSEL state comes from "
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
                // The rotation phase, for turning "launch on this date" into "launch at this
                // TIME". KSP computes it as
                //     rotationAngle = (initialRotation + 360 * UT / rotationPeriod) % 360
                // (CelestialBody.updateRotation), and a tidally locked body has its
                // rotationPeriod overwritten with its orbital period first. Both inputs and the
                // live result are reported so the replica can be diffed against the game rather
                // than trusted -- an epoch-shaped error in this would move every launch time
                // consistently and nothing internal would notice.
                j.Val("initial_rotation", b.initialRotation);
                j.Val("rotation_angle", b.rotationAngle);
                j.Val("direct_rot_angle", b.directRotAngle);
                j.Val("tidally_locked", b.tidallyLocked);
                j.Val("rotates", b.rotates);
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
        // which is what /predict is for. FindVessel serves that and the node endpoints.

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

        // --- writes ----------------------------------------------------------
        /// <summary>
        /// Writes are POST-only. A GET that mutates state is reachable by anything that follows a
        /// link -- a browser tab left open on /ping, a shell history recall -- and "place a burn"
        /// is not something that should be one stray request away.
        /// </summary>
        private static string RequirePost(AxeBridgeServer.Request req)
        {
            if (req.IsWrite) return null;
            return "{\"ok\":false,\"error\":\"" + req.Path + " is a write; use POST\"}";
        }

        /// <summary>
        /// The maneuver-node solver, or a message saying precisely why there isn't one. There are
        /// three different causes and they need three different fixes, so collapsing them into
        /// "no solver" would send someone to check the wrong thing every time.
        /// </summary>
        private static PatchedConicSolver NodeSolver(Vessel v, out string why)
        {
            why = null;
            if (v == null) { why = "no vessel"; return null; }
            if (v.patchedConicSolver != null) return v.patchedConicSolver;

            if (HighLogic.LoadedScene != GameScenes.FLIGHT)
                why = "maneuver nodes only exist in the FLIGHT scene; KSP is in "
                    + HighLogic.LoadedScene + ". Fly the vessel first (-axe-focus=<name> does it "
                    + "from the main menu).";
            else if (FlightGlobals.ActiveVessel != v)
                why = v.vesselName + " is not the active vessel ("
                    + (FlightGlobals.ActiveVessel != null ? FlightGlobals.ActiveVessel.vesselName : "none")
                    + " is). KSP builds a patchedConicSolver for the active vessel only.";
            else
                why = "the active vessel has no patchedConicSolver. In a career this usually means "
                    + "the Tracking Station is not upgraded far enough for patched conics.";
            return null;
        }

        /// <summary>Read the current flight plan back: the nodes, and where they lead.</summary>
        private static string Nodes(AxeBridgeServer.Request req)
        {
            string bad = NotReady();
            if (bad != null) return bad;
            Vessel v = FindVessel(req);
            if (v == null)
                return "{\"ok\":false,\"error\":\"no vessel matched (pass ?id=<guid> or ?vessel=<name>)\"}";
            string why;
            PatchedConicSolver s = NodeSolver(v, out why);

            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("ut", SafeUT());
            j.Val("vessel", v.vesselName);
            j.Val("id", v.id.ToString());
            j.Val("nodes_available", s != null);
            if (s == null) j.Val("why", why);
            WriteNodes(j, s);
            WriteFlightPlan(j, s);
            return j.EndObj().ToString();
        }

        private static void WriteNodes(AxeJson j, PatchedConicSolver s)
        {
            j.Arr("nodes");
            if (s != null && s.maneuverNodes != null)
            {
                foreach (ManeuverNode n in s.maneuverNodes)
                {
                    j.Obj();
                    j.Val("ut", n.UT);
                    // DeltaV is stored (radial, normal, prograde) -- the same order and the same
                    // basis tools/mission uses. Named rather than emitted as a bare triple so a
                    // reordering on either side cannot pass silently.
                    j.Val("radial", n.DeltaV.x);
                    j.Val("normal", n.DeltaV.y);
                    j.Val("prograde", n.DeltaV.z);
                    j.Val("magnitude", n.DeltaV.magnitude);
                    j.EndObj();
                }
            }
            j.EndArr();
        }

        /// <summary>
        /// The trajectory the placed nodes actually produce, straight out of KSP's solver. This is
        /// the point of writing through the bridge rather than by hand: the same request that
        /// places the burn reports where the game thinks it goes, so a sign error shows up in the
        /// response instead of three hours into a time warp.
        /// </summary>
        private static void WriteFlightPlan(AxeJson j, PatchedConicSolver s)
        {
            j.Arr("flight_plan");
            if (s != null && s.flightPlan != null)
                foreach (Orbit o in s.flightPlan)
                    if (o != null) WritePatch(j, o);
            j.EndArr();
        }

        /// <summary>
        /// Place maneuver nodes. Body: {"vessel": "...", "replace": true, "nodes": [
        ///   {"ut": 123.0, "radial": 0, "normal": 0, "prograde": 1500.0}, ... ]}
        /// A single node may also be given inline as ut/radial/normal/prograde on the object.
        /// </summary>
        private static string PlaceNodes(AxeBridgeServer.Request req)
        {
            string bad = NotReady();
            if (bad != null) return bad;
            Vessel v = FindVessel(req);
            if (v == null)
                return "{\"ok\":false,\"error\":\"no vessel matched (pass vessel or id); "
                     + "an ambiguous name matches nothing on purpose\"}";
            string why;
            PatchedConicSolver s = NodeSolver(v, out why);
            if (s == null) return "{\"ok\":false,\"error\":" + AxeJson.Str(why) + "}";

            var body = req.Json;
            var specs = new List<double[]>();          // ut, radial, normal, prograde
            List<object> arr = body != null ? AxeJsonReader.Arr(body, "nodes") : null;
            if (arr != null)
            {
                foreach (object item in arr)
                {
                    var n = AxeJsonReader.AsObj(item);
                    if (n == null)
                        return "{\"ok\":false,\"error\":\"every entry of \\\"nodes\\\" must be an object "
                             + "with ut/radial/normal/prograde\"}";
                    specs.Add(new[]
                    {
                        AxeJsonReader.NumRequired(n, "ut"),
                        AxeJsonReader.Num(n, "radial", 0.0),
                        AxeJsonReader.Num(n, "normal", 0.0),
                        AxeJsonReader.Num(n, "prograde", 0.0),
                    });
                }
            }
            else
            {
                double utOne = req.FieldNum("ut", double.NaN);
                if (double.IsNaN(utOne))
                    return "{\"ok\":false,\"error\":\"send either \\\"nodes\\\": [ ... ] or a single "
                         + "node as ut/radial/normal/prograde\"}";
                specs.Add(new[] { utOne, req.FieldNum("radial", 0.0),
                                         req.FieldNum("normal", 0.0), req.FieldNum("prograde", 0.0) });
            }
            if (specs.Count == 0)
                return "{\"ok\":false,\"error\":\"no nodes given\"}";

            double now = SafeUT();
            bool allowPast = req.FieldBool("allow_past", false);
            if (!allowPast)
                foreach (double[] n in specs)
                    if (n[0] < now)
                        return "{\"ok\":false,\"error\":" + AxeJson.Str(
                            "node UT " + AxeJson.Num(n[0]) + " is " + AxeJson.Num(now - n[0])
                            + " s in the past (now is " + AxeJson.Num(now) + "). A node behind the "
                            + "vessel is never flown and quietly does nothing; pass allow_past to "
                            + "place it anyway.") + "}";

            // Ordering matters. AddManeuverNode inserts into a list KSP keeps sorted by UT, and a
            // caller that sends a correction before its own ejection would otherwise get a flight
            // plan solved in an order it did not ask for.
            specs.Sort(delegate (double[] a, double[] b) { return a[0].CompareTo(b[0]); });

            bool replace = req.FieldBool("replace", true);
            int removed = 0;
            if (replace && s.maneuverNodes != null)
                while (s.maneuverNodes.Count > 0) { s.maneuverNodes[0].RemoveSelf(); removed++; }

            foreach (double[] n in specs)
            {
                ManeuverNode node = s.AddManeuverNode(n[0]);
                node.DeltaV = new Vector3d(n[1], n[2], n[3]);
            }
            s.UpdateFlightPlan();

            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("ut", now);
            j.Val("vessel", v.vesselName);
            j.Val("id", v.id.ToString());
            j.Val("placed", specs.Count);
            j.Val("removed", removed);
            WriteNodes(j, s);
            WriteFlightPlan(j, s);
            return j.EndObj().ToString();
        }

        private static string ClearNodes(AxeBridgeServer.Request req)
        {
            string bad = NotReady();
            if (bad != null) return bad;
            Vessel v = FindVessel(req);
            if (v == null) return "{\"ok\":false,\"error\":\"no vessel matched\"}";
            string why;
            PatchedConicSolver s = NodeSolver(v, out why);
            if (s == null) return "{\"ok\":false,\"error\":" + AxeJson.Str(why) + "}";

            int removed = 0;
            if (s.maneuverNodes != null)
                while (s.maneuverNodes.Count > 0) { s.maneuverNodes[0].RemoveSelf(); removed++; }
            s.UpdateFlightPlan();

            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("vessel", v.vesselName);
            j.Val("removed", removed);
            WriteNodes(j, s);
            WriteFlightPlan(j, s);
            return j.EndObj().ToString();
        }

        // --- alarms ----------------------------------------------------------
        private static string Alarms()
        {
            string bad = NotReady();
            if (bad != null) return bad;
            AxeKac.Bind();
            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("ut", SafeUT());
            j.Val("backend", AxeKac.Ready ? "kac" : "stock");
            if (!AxeKac.Ready) j.Val("kac", AxeKac.Unavailable ?? "KAC is installed but not ready yet");
            WriteAlarmEnums(j);
            j.Arr("alarms");
            foreach (AxeKac.AlarmInfo a in AxeKac.List())
            {
                j.Obj();
                j.Val("id", a.Id);
                j.Val("name", a.Name);
                j.Val("notes", a.Notes);
                j.Val("type", a.Type);
                j.Val("action", a.Action);
                j.Val("ut", a.UT);
                j.Val("margin", a.Margin);
                j.Val("remaining", a.Remaining);
                j.Val("vessel_id", a.VesselId);
                j.Val("xfer_origin", a.XferOrigin);
                j.Val("xfer_target", a.XferTarget);
                j.EndObj();
            }
            j.EndArr();
            return j.EndObj().ToString();
        }

        /// <summary>
        /// Report the alarm type/action names KAC actually declares. The client needs them to
        /// validate before sending, and reading them off the live enum means the list cannot drift
        /// out of step with the installed KAC the way a hardcoded copy would.
        /// </summary>
        private static void WriteAlarmEnums(AxeJson j)
        {
            j.Arr("alarm_types");
            foreach (string n in AxeKac.AlarmTypeNames) j.Item(n);
            j.EndArr();
            j.Arr("alarm_actions");
            foreach (string n in AxeKac.AlarmActionNames) j.Item(n);
            j.EndArr();
        }

        /// <summary>
        /// Create an alarm. Body: {"ut": 123.0, "name": "...", "notes": "...", "type": "Raw",
        /// "action": "KillWarp", "margin": 0, "vessel": "...", "xfer_origin": "Earth",
        /// "xfer_target": "Jupiter"}
        /// </summary>
        private static string CreateAlarm(AxeBridgeServer.Request req)
        {
            string bad = NotReady();
            if (bad != null) return bad;
            double ut = req.FieldNum("ut", double.NaN);
            if (double.IsNaN(ut))
                return "{\"ok\":false,\"error\":\"ut is required (seconds of universal time)\"}";

            var spec = new AxeKac.AlarmSpec
            {
                UT = ut,
                Type = req.Field("type", "Raw"),
                Name = req.Field("name", "AXE"),
                Notes = req.Field("notes", req.Field("description", "")),
                Action = req.Field("action", "KillWarp"),
                Margin = req.FieldNum("margin", 0.0),
                XferOrigin = req.Field("xfer_origin"),
                XferTarget = req.Field("xfer_target"),
            };

            // Bind the alarm to a vessel by name as well as by id: the caller is working from a
            // name everywhere else in this toolchain, and KAC wants the Guid.
            string vesselRef = req.Field("vessel") ?? req.Field("vessel_id") ?? req.Field("id");
            if (!string.IsNullOrEmpty(vesselRef))
            {
                Vessel v = FindVesselByRef(vesselRef);
                if (v == null)
                    return "{\"ok\":false,\"error\":" + AxeJson.Str(
                        "no vessel matched \"" + vesselRef + "\"; omit \"vessel\" for an unbound alarm") + "}";
                spec.VesselId = v.id.ToString();
            }

            string backend;
            string id;
            try
            {
                id = AxeKac.Create(spec, out backend);
            }
            catch (Exception e)
            {
                return "{\"ok\":false,\"error\":" + AxeJson.Str(e.Message) + "}";
            }

            double nowUT = SafeUT();
            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("id", id);
            j.Val("backend", backend);
            j.Val("ut", ut);
            j.Val("now", nowUT);
            j.Val("in_seconds", ut - nowUT);
            j.Val("name", spec.Name);
            j.Val("type", spec.Type);
            j.Val("vessel_id", spec.VesselId);
            WriteAlarmEnums(j);
            return j.EndObj().ToString();
        }

        private static string DeleteAlarm(AxeBridgeServer.Request req)
        {
            string bad = NotReady();
            if (bad != null) return bad;
            string id = req.Field("id");
            if (string.IsNullOrEmpty(id))
                return "{\"ok\":false,\"error\":\"id is required (see /alarms)\"}";
            bool ok = AxeKac.Delete(id);
            var j = new AxeJson().Obj();
            j.Val("ok", ok);
            j.Val("id", id);
            if (!ok) j.Val("error", "no alarm with that id, or the backend refused to delete it");
            return j.EndObj().ToString();
        }

        private static Vessel FindVesselByRef(string reference)
        {
            var list = FlightGlobals.Vessels ?? new List<Vessel>();
            string want = reference.Replace("-", "").ToLowerInvariant();
            Vessel byId = list.FirstOrDefault(v => v != null && v.id.ToString("N").ToLowerInvariant() == want);
            if (byId != null) return byId;
            Vessel exact = list.FirstOrDefault(v => v != null && v.vesselName == reference);
            if (exact != null) return exact;
            var hits = list.Where(v => v != null && v.vesselName != null
                              && v.vesselName.IndexOf(reference, StringComparison.OrdinalIgnoreCase) >= 0).ToList();
            return hits.Count == 1 ? hits[0] : null;
        }

        // --- launch sites ----------------------------------------------------
        /// <summary>
        /// Every launch site the game will actually spawn a vessel at, with the latitude and
        /// longitude it will spawn at.
        ///
        /// This exists because a launch window is only half an answer. "Depart on 26 Sep 1966"
        /// says nothing about what time of day to launch, and that depends on where the pad is and
        /// on how far the planet has turned. KSCSwitcher RELOCATES the single KSC rather than
        /// adding sites, so the pad position reported here is the switched one, which is exactly
        /// the number the launch-time solver needs and is not recoverable from a body config.
        /// </summary>
        private static string Sites()
        {
            string bad = NotReady(needGame: false);
            if (bad != null) return bad;
            var j = new AxeJson().Obj();
            j.Val("ok", true);
            j.Val("ut", SafeUT());
            j.Arr("sites");
            PSystemSetup ps = PSystemSetup.Instance;
            if (ps != null && ps.LaunchSites != null)
            {
                foreach (LaunchSite site in ps.LaunchSites)
                {
                    if (site == null) continue;
                    j.Obj();
                    j.Val("name", site.name);
                    j.Val("display_name", site.launchSiteName);
                    j.Val("pqs", site.pqsName);
                    CelestialBody b = null;
                    try { b = site.Body; } catch (Exception) { }
                    j.Val("body", b != null ? b.bodyName : null);
                    j.Val("editor", site.editorFacility.ToString());
                    j.Arr("spawn_points");
                    if (site.spawnPoints != null)
                    {
                        foreach (LaunchSite.SpawnPoint sp in site.spawnPoints)
                        {
                            if (sp == null) continue;
                            j.Obj();
                            j.Val("name", sp.name);
                            // latlonaltSet says whether these numbers have been resolved from the
                            // PQSCity yet. Unresolved ones read as 0,0 -- a real place in the ocean
                            // off Africa -- so the flag has to travel with them or the client
                            // cannot tell an unresolved site from a genuinely equatorial one.
                            j.Val("latitude", sp.latitude);
                            j.Val("longitude", sp.longitude);
                            j.Val("altitude", sp.altitude);
                            j.Val("resolved", sp.latlonaltSet);
                            j.EndObj();
                        }
                    }
                    j.EndArr();
                    j.EndObj();
                }
            }
            j.EndArr();
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
