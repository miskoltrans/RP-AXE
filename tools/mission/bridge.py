"""Client for the AXE bridge — ask the running game instead of the save, and tell it things.

This covers only what KSPTOT Connect cannot: /predict, which runs KSP's OWN
patched-conic solver over a proposed burn, /bodies, which reports the SOI, the
FlightGlobals index and the rotation phase that KSPTOT does not send, /sites, and the
write endpoints. Live VESSEL state comes from ksptot.py -- KSPTOT Connect is already
installed and already serves it.

The writes exist because reading six numbers off a terminal and typing them into a node
gizmo is where the precision was being lost. place_nodes() returns KSP's resulting
flight plan in the same call that placed the burn, so a sign error is visible
immediately rather than three hours into a time warp.

Needs the bridge switched on in KSP (it is off by default):

    KSP_x64.exe -axe-bridge          or  AXE_BRIDGE=1
    or  enabled = true  in  GameData/RP-AXE/Plugins/PluginData/Bridge.cfg

FRAMES. Every vector on this wire is the ELEMENT frame -- the one KSP's own inclination,
LAN and argumentOfPeriapsis use, and the one rss_ephem necessarily works in.

That is NOT what Orbit.getRelativePositionAtUT returns. It ends in
Zup.WorldToLocal(...), a rotation by -Planetarium.InverseRotAngle about z, so a body's
state vector comes out rotated relative to its own elements by a runtime angle. Bridge
1.0 emitted both untouched, which put two frames on one wire and made `crosscheck` report
that rotation as an EPOCH error -- crying wolf on the one check you reach for after an
ephemeris scare. Bridge 1.1 converts state vectors back before they leave; `ping` reports
the version and the angle so a client can tell which it is talking to.
"""
import json
import math
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

DEFAULT_PORT = 8284


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self, host="127.0.0.1", port=DEFAULT_PORT, timeout=30.0):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def get(self, path, **params):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as fh:
                data = json.loads(fh.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # The bridge answers errors with a JSON body saying what went wrong.
            # HTTPError subclasses URLError, so it MUST be caught first or a
            # perfectly clear "the handler threw X" turns into "is KSP running?".
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
                msg = json.loads(body).get("error")
            except Exception:                                       # noqa: BLE001
                msg = None
            raise BridgeError(f"{path}: HTTP {exc.code}: {msg or body[:300] or exc.reason}") from None
        except urllib.error.URLError as exc:
            raise BridgeError(
                f"cannot reach the AXE bridge at {self.base} ({exc.reason}).\n"
                f"  Is KSP running, and was it started with -axe-bridge?\n"
                f"  Alternatives: set AXE_BRIDGE=1, or put `enabled = true` in\n"
                f"  GameData/RP-AXE/Plugins/PluginData/Bridge.cfg and restart KSP."
            ) from None
        except json.JSONDecodeError as exc:
            raise BridgeError(f"{url} did not return JSON: {exc}") from None
        if not data.get("ok", False):
            raise BridgeError(f"{path}: {data.get('error', 'refused, with no reason given')}")
        return data

    def post(self, path, **body):
        """POST a JSON body. Writes are POST-only on the bridge side.

        None-valued keys are dropped rather than sent as null: "vessel": null would
        read as an explicit request to match a vessel named nothing, and the bridge
        would rightly refuse it.
        """
        payload = json.dumps({k: v for k, v in body.items() if v is not None}).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=payload, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as fh:
                data = json.loads(fh.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # HTTPError subclasses URLError and MUST be caught first, or "the handler
            # threw X" turns into "is KSP running?". See get().
            raw = ""
            try:
                raw = exc.read().decode("utf-8", "replace")
                msg = json.loads(raw).get("error")
            except Exception:                                       # noqa: BLE001
                msg = None
            raise BridgeError(f"{path}: HTTP {exc.code}: {msg or raw[:300] or exc.reason}") from None
        except urllib.error.URLError as exc:
            raise BridgeError(
                f"cannot reach the AXE bridge at {self.base} ({exc.reason}).\n"
                f"  Is KSP running, and was it started with -axe-bridge?"
            ) from None
        except json.JSONDecodeError as exc:
            raise BridgeError(f"{path} did not return JSON: {exc}") from None
        if not data.get("ok", False):
            raise BridgeError(f"{path}: {data.get('error', 'refused, with no reason given')}")
        return data

    # --- endpoints -------------------------------------------------------
    def ping(self):
        return self.get("/ping")

    def bodies(self):
        return self.get("/bodies")

    def predict(self, name=None, vid=None, ut=None, dv=(0.0, 0.0, 0.0), horizon=400.0,
                maxpatches=8):
        """KSP's own patched-conic answer for a burn, in maneuver-node components.

        `dv` is (radial, normal, prograde) -- the same triple plan.py prints.
        """
        dv = tuple(float(x) for x in dv)
        return self.get("/predict", vessel=name, id=vid, ut=_fmt(ut),
                        dv=",".join(_fmt(x) for x in dv),
                        horizon=_fmt(horizon), maxpatches=str(int(maxpatches)))

    def vessel(self, name=None, vid=None, ut=None):
        """Live vessel state: elements, state vector, and any nodes already placed.

        This is what /predict cannot give you. /predict reports patch SHAPES -- sma, ecc,
        inc, lan, argp -- with no mean anomaly and no state vector, so a trajectory can be
        EVALUATED from it but not propagated, and solving a burn needs propagation.

        KSPTOT Connect serves the same thing and ksptot.py speaks it, but it is
        [KSPAddon(Flight)] and a separate process: "the bridge is up" and "live state is
        available" are two different facts. This makes them one.
        """
        return self.get("/vessel", vessel=name, id=vid, ut=_fmt(ut))

    def state(self, system, name=None, vid=None, ut=None):
        """(body, r, v, ut) in the element frame -- the same shape ksptot.state returns."""
        d = self.vessel(name=name, vid=vid, ut=ut)
        body = system.body(d["body"])
        return body, np.array(d["r"], float), np.array(d["v"], float), d["ut"]

    def sites(self):
        """Launch sites and the lat/lon the game will actually spawn at.

        KSCSwitcher RELOCATES the single KSC rather than adding sites, so this is the
        switched position -- which is the only place it can be read from.
        """
        return self.get("/sites")

    # --- writes ----------------------------------------------------------
    def nodes(self, name=None, vid=None):
        """The vessel's current maneuver nodes and the flight plan they produce."""
        return self.get("/nodes", vessel=name, id=vid)

    def place_nodes(self, nodes, name=None, vid=None, replace=True, allow_past=False):
        """Place maneuver nodes and return KSP's resulting flight plan.

        `nodes` is a sequence of (ut, radial, normal, prograde) or of dicts with those
        keys -- the same triple, in the same order, that plan.py prints and that
        astro.to_node produces.
        """
        payload = []
        for n in nodes:
            if isinstance(n, dict):
                payload.append({"ut": float(n["ut"]), "radial": float(n.get("radial", 0.0)),
                                "normal": float(n.get("normal", 0.0)),
                                "prograde": float(n.get("prograde", 0.0))})
            else:
                ut, r, nn, pg = n
                payload.append({"ut": float(ut), "radial": float(r),
                                "normal": float(nn), "prograde": float(pg)})
        if not payload:
            raise BridgeError("place_nodes: no nodes given")
        return self.post("/node", vessel=name, id=vid, nodes=payload,
                         replace=bool(replace), allow_past=bool(allow_past))

    def clear_nodes(self, name=None, vid=None):
        return self.post("/node/clear", vessel=name, id=vid)

    def alarms(self):
        return self.get("/alarms")

    def alarm(self, ut, name="AXE", notes="", type="Raw", action="KillWarp",
              margin=0.0, vessel=None, xfer_origin=None, xfer_target=None):
        """Create an alarm. Returns the response, including its id and which backend took it.

        `type` and `action` are validated against the LIVE KAC enums on the bridge side,
        and an unknown name comes back with the full list of valid ones -- so there is no
        copy of KAC's enum here to drift out of date.
        """
        return self.post("/alarm", ut=float(ut), name=name, notes=notes, type=type,
                         action=action, margin=float(margin), vessel=vessel,
                         xfer_origin=xfer_origin, xfer_target=xfer_target)

    def delete_alarm(self, alarm_id):
        return self.post("/alarm/delete", id=alarm_id)


def _fmt(x):
    if x is None:
        return None
    return repr(float(x))


# ---------------------------------------------------------------------------
# cross-checks: where does the replica disagree with the game?
# ---------------------------------------------------------------------------
def check_bodies(system, br):
    """Compare every body's position against the game's, at the game's own UT.

    This is the check that would have caught the B1950 epoch bug in one command.
    A wrong epoch moves every body consistently, so nothing internal notices --
    but the game is not in on it.
    """
    data = br.bodies()
    ut = data["ut"]
    rows = []
    for b in data["bodies"]:
        name = b.get("name")
        if name not in system.bodies or b.get("r") is None:
            continue
        game_r = np.array(b["r"], float)
        mine_r = np.asarray(system.rel(name, ut)[0], float)
        d = float(np.linalg.norm(game_r - mine_r))
        scale = max(float(np.linalg.norm(game_r)), 1.0)
        row = {"body": name, "err_m": d, "rel": d / scale,
               "mu_game": b["mu"], "mu_mine": system.bodies[name].mu,
               "soi_game": b["soi"], "soi_mine": system.bodies[name].soi,
               "index_game": b["index"], "index_mine": system.bodies[name].index}
        # Rotation phase, when the game reports it. This is what turns a departure DATE
        # into a launch TIME, and an error in it would move every launch time
        # consistently -- exactly the shape of bug that survives an internal check.
        if b.get("rotation_angle") is not None:
            row["rot_game"] = b["rotation_angle"]
            row["rot_mine"] = system.rotation_angle(name, ut)
            if row["rot_mine"] is not None:
                d_rot = (row["rot_mine"] - row["rot_game"] + 180.0) % 360.0 - 180.0
                row["rot_err_deg"] = d_rot
        rows.append(row)
    return ut, rows


def compare_patches(system, game_patches, traj, target=None):
    """Line up KSP's patch list against the shooter's and report where they part."""
    mine = [{"body": p.body.name, "start_ut": p.ut0, "end_ut": p.ut1,
             "peR": p.elements().peR, "ecc": p.elements().ecc} for p in traj.patches]
    out = []
    for i in range(max(len(mine), len(game_patches))):
        g = game_patches[i] if i < len(game_patches) else None
        m = mine[i] if i < len(mine) else None
        row = {"i": i,
               "game_body": g["body"] if g else None,
               "mine_body": m["body"] if m else None,
               "game_start": g["start_ut"] if g else None,
               "mine_start": m["start_ut"] if m else None,
               "game_peR": g["peR"] if g else None,
               "mine_peR": m["peR"] if m else None}
        if g and m:
            row["dt_start"] = m["start_ut"] - g["start_ut"]
            row["dpeR"] = m["peR"] - g["peR"]
            row["same_body"] = g["body"] == m["body"]
        out.append(row)
    return out
