"""Client for the AXE query bridge — ask the running game instead of the save.

This covers only what KSPTOT Connect cannot: /predict, which runs KSP's OWN
patched-conic solver over a proposed burn, and /bodies, which reports the SOI and the
FlightGlobals index that KSPTOT does not send. Live VESSEL state comes from
ksptot.py -- KSPTOT Connect is already installed and already serves it.

Needs the bridge switched on in KSP (it is off by default, and read-only):

    KSP_x64.exe -axe-bridge          or  AXE_BRIDGE=1
    or  enabled = true  in  GameData/RP-AXE/Plugins/PluginData/Bridge.cfg

Everything it returns is in the same right-handed z-up frame this toolchain uses,
because Orbit.getRelativePositionAtUT already returns that frame.
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
        rows.append({"body": name, "err_m": d, "rel": d / scale,
                     "mu_game": b["mu"], "mu_mine": system.bodies[name].mu,
                     "soi_game": b["soi"], "soi_mine": system.bodies[name].soi,
                     "index_game": b["index"], "index_mine": system.bodies[name].index})
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
