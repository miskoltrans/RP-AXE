"""Fly trajectories with KSP's OWN patched-conic solver, outside the game.

`patched.shoot` is a replica of KSP's solver. It agrees with the game to 0.000 s on SOI
transitions, which is the good news; the bad news is that it costs about 3.4 seconds for a
four-patch flight. That single number is why the tour search in `tour_plan.py` models flybys
analytically instead of flying them -- and an analytic flyby is exactly the thing this project
has already measured as failing, because the rotation is right to 0.08 degrees while the epoch
it is evaluated at is not. So the search optimises something that does not survive being flown,
and a flyby has to actually happen before the next one can be planned.

This module removes the reason for that compromise. It drives `Assembly-CSharp.dll`'s real
`Orbit` and `PatchedConics` in a worker process -- no Unity, no running game -- at about
0.13 ms per patch. The same flight the replica takes 3.4 s to do costs roughly half a
millisecond, so a flown search over a whole moon tour is seconds rather than days.

    from oracle import Oracle
    orc = Oracle(system)
    traj = orc.shoot("Jupiter", r, v, ut0, ut0 + 400 * 86400)

`shoot` returns a real `patched.Trajectory` of real `patched.Patch` objects, so everything
downstream -- `enters`, `closest_approach`, `arrival_report` -- works unchanged.

Differences from `patched.shoot`, both deliberate:

* **`watch` is ignored.** KSP considers whatever is in `Planetarium.Orbits`; it has no
  minimum-SOI cutoff, so Phobos-class bodies are not silently skipped the way the replica skips
  them by default. Pass `watch` for signature compatibility; it does not narrow anything.
* **`ut_end` past one revolution is a departure from the game.** KSP gives patch 0 exactly one
  period and no more, which is why the map view never shows an encounter two orbits out. Asking
  for a longer horizon is allowed and is reported back in `trajectory.note`.
"""
import atexit
import json
import math
import os
import subprocess

import numpy as np

import patched

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "..", "ksp-oracle", "bin", "KspOracle.exe")


class OracleError(RuntimeError):
    pass


def _num(x):
    """The wire sends Infinity and NaN as null, exactly as the in-game bridge does."""
    return math.inf if x is None else float(x)


class Oracle:
    """A live worker. Construct once and reuse -- the system is uploaded on first use."""

    def __init__(self, system, exe=None):
        self.system = system
        self.exe = os.path.abspath(exe or EXE)
        if not os.path.exists(self.exe):
            raise OracleError(
                "%s is not built.\n    pwsh tools/ksp-oracle/build.ps1" % self.exe)
        self._proc = subprocess.Popen(
            [self.exe],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1)
        atexit.register(self.close)
        self._send({"op": "system", "bodies": self._bodies()})

    # -- protocol ---------------------------------------------------------------

    def _bodies(self):
        out = []
        for name, b in self.system.bodies.items():
            d = {"name": name, "mu": b.mu, "radius": b.radius}
            if b.soi is not None and math.isfinite(b.soi):
                d["soi"] = b.soi                      # omitted means infinite, as KSP defaults
            if b.parent:
                d.update(parent=b.parent, inc=b.inc, e=b.e, a=b.a,
                         lan=b.lan, argp=b.argp, m0=b.M0, epoch=self.system.epoch)
            out.append(d)
        return out

    def _send(self, req):
        if self._proc is None or self._proc.poll() is not None:
            raise OracleError("worker exited: %s" % self._stderr())
        self._proc.stdin.write(json.dumps(req) + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        if not line:
            raise OracleError("worker closed the pipe: %s" % self._stderr())
        rep = json.loads(line)
        if not rep.get("ok"):
            raise OracleError(rep.get("error", "unknown worker error"))
        return rep

    def _stderr(self):
        try:
            return (self._proc.stderr.read() or "").strip() or "(no stderr)"
        except Exception:
            return "(stderr unavailable)"

    def close(self):
        if getattr(self, "_proc", None) is None:
            return
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()
        finally:
            self._proc = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- flying -----------------------------------------------------------------

    def ping(self):
        return self._send({"op": "ping"})

    def _job(self, body, r0, v0, ut0, ut_end=None, max_patches=8):
        body = self.system.body(body) if isinstance(body, str) else body
        job = {"body": body.name,
               "r": [float(x) for x in np.asarray(r0, float)],
               "v": [float(x) for x in np.asarray(v0, float)],
               "ut0": float(ut0),
               "max_patches": int(max_patches)}
        if ut_end is not None and math.isfinite(ut_end):
            job["ut_end"] = float(ut_end)
        return job

    def shoot(self, body, r0, v0, ut0, ut_end=None, watch=None, max_patches=8):
        """One flight. Signature mirrors `patched.shoot`; `watch` is accepted and ignored."""
        req = {"op": "shoot"}
        req.update(self._job(body, r0, v0, ut0, ut_end, max_patches))
        return self._trajectory(self._send(req)["result"])

    def shoot_many(self, jobs, max_patches=8):
        """Fly a whole frontier in one round trip.

        `jobs` is a sequence of (body, r0, v0, ut0, ut_end) tuples. This is the call a flown
        search should use: per-request overhead, not the arithmetic, is what would otherwise
        set the runtime.
        """
        payload = [self._job(*j, max_patches=max_patches) for j in jobs]
        rep = self._send({"op": "shoot_batch", "jobs": payload})
        return [self._trajectory(r["result"]) if r.get("ok") else None
                for r in rep["results"]]

    def _trajectory(self, res):
        patches = []
        for p in res["patches"]:
            pt = patched.Patch(
                self.system.body(p["body"]),
                _num(p["start_ut"]),
                np.asarray(p["r0"], float),
                np.asarray(p["v0"], float),
                ut1=_num(p["end_ut"]),
                end=p["end"])
            # KSP's own elements for this patch, kept verbatim alongside the state vector.
            pt.elements_ksp = {k: _num(p[k]) for k in
                               ("sma", "ecc", "inc", "lan", "argp", "mna", "epoch", "peR", "apR")}
            patches.append(pt)
        traj = patched.Trajectory(patches, self.system)
        traj.truncated = bool(res.get("truncated"))
        traj.note = res.get("note")
        return traj


_cached = {}


def get(system, exe=None):
    """A process-wide worker per system. Cheap to call repeatedly."""
    key = id(system)
    if key not in _cached:
        _cached[key] = Oracle(system, exe)
    return _cached[key]


def shoot(system, body, r0, v0, ut0, ut_end, watch=None, max_patches=8, coarse=None):
    """Drop-in for `patched.shoot(system, body, ...)`, flown by KSP itself."""
    return get(system).shoot(body, r0, v0, ut0, ut_end, watch, max_patches)
