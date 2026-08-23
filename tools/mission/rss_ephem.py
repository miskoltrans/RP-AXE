"""The install's own solar system: Kopernicus elements plus what the game measured.

Ground truth is the running install, never a textbook table. Three facts here are
load-bearing and each one has already cost a mission:

  * RSS states its elements at B1950.0, not at UT 0. RSSKopernicusSettings.cfg
    carries `Epoch = -31542641.784` and Kopernicus propagates M(t) = M0 + n(t-Epoch).
    Drop it and every body is 365.08 days out of phase -- SELF-CONSISTENTLY, so
    Lambert still closes to 0 m/s and the departure still misses by 295 Gm.
  * A body's SOI is not always a*(mu/mu_parent)^0.4. Phobos, Deimos and Mimas carry
    an explicit `sphereOfInfluence` override, and Phobos' is twice its Hill sphere.
  * A save's `ORBIT { REF = n }` indexes FlightGlobals.Bodies. That is the body's RUNTIME
    flightGlobalsIndex -- Kopernicus renumbers them on load so the two agree -- but it is
    NOT the value in the Kopernicus .cfg, which is only a load-order hint and differs for
    25 of the 33 bodies here (Ceres: cfg 50, runtime 12). Kopernicus.log records the real
    one ("Found Body: Moon:9 -> SOI = ..."), so read it instead of deriving it.

Usage:
    from rss_ephem import System
    S = System()                       # defaults to Instance/
    r, v = S.helio("Jupiter", ut)      # metres, m/s, Sun-centred
    r, v = S.rel("Io", ut)             # about its own parent
"""
import datetime
import math
import os
import re

import cfgnode

EPOCH_YEAR = 1951  # UT 0 in RSS/RP-1
DAY = 86400.0
DEFAULT_INSTANCE = r"C:/git/ksp/Instance"


class Body:
    def __init__(self, name, props, orbit):
        self.name = name
        self.index = None
        self.parent = orbit.get("referenceBody") if orbit else None
        self.mu = props.getf("gravParameter", 0.0) if props else 0.0
        self.radius = props.getf("radius", 0.0) if props else 0.0
        self.radius_cfg = self.radius       # pre-ModuleManager, kept to show the delta
        self.rot = props.getf("rotationPeriod", 0.0) if props else 0.0
        # The rotation PHASE, which is what turns a departure date into a launch time.
        # KSP: rotationAngle = (initialRotation + 360 * UT / rotationPeriod) % 360
        # (CelestialBody.updateRotation), after a tidally locked body has had its
        # rotationPeriod overwritten with its orbital period. Earth's initialRotation is
        # 100.1833 deg in RSS; leaving it out puts every launch time 100 deg of rotation
        # -- nearly seven hours -- wrong, consistently, so nothing internal would notice.
        self.initial_rotation = props.getf("initialRotation", 0.0) if props else 0.0
        self.tidally_locked = bool(props.getb("tidallyLocked", False)) if props else False
        self.soi_cfg = props.getf("sphereOfInfluence") if props else None
        self.soi = None                       # filled by System, game-measured
        if orbit:
            self.a = orbit.getf("semiMajorAxis", 0.0)
            self.e = orbit.getf("eccentricity", 0.0)
            self.inc = math.radians(orbit.getf("inclination", 0.0))
            self.lan = math.radians(orbit.getf("longitudeOfAscendingNode", 0.0))
            self.argp = math.radians(orbit.getf("argumentOfPeriapsis", 0.0))
            if orbit.has("meanAnomalyAtEpochD"):
                self.M0 = math.radians(orbit.getf("meanAnomalyAtEpochD"))
            else:
                self.M0 = orbit.getf("meanAnomalyAtEpoch", 0.0)
        else:
            self.a = self.e = self.inc = self.lan = self.argp = self.M0 = 0.0

    def __repr__(self):
        return f"<{self.name} a={self.a:.4g} e={self.e:.4f} mu={self.mu:.4g}>"


def kepler_E(M, e, tol=1e-14):
    """Eccentric anomaly. Newton, with bisection fallback so e -> 1 still converges."""
    M = math.fmod(M, 2 * math.pi)
    if M < 0:
        M += 2 * math.pi
    E = M if e < 0.8 else math.pi
    for _ in range(120):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        d = -f / fp
        E += d
        if abs(d) < tol:
            return E
    lo, hi = 0.0, 2 * math.pi
    for _ in range(200):
        E = 0.5 * (lo + hi)
        if E - e * math.sin(E) - M > 0:
            hi = E
        else:
            lo = E
    return E


def elements_to_rv(a, e, inc, lan, argp, M, mu):
    """Classical elements -> (r, v) in the right-handed z-up frame KSP stores them in."""
    E = kepler_E(M, e)
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2), math.sqrt(1 - e) * math.cos(E / 2))
    r = a * (1 - e * math.cos(E))
    p = a * (1 - e * e)
    h = math.sqrt(mu * p)
    rp = (r * math.cos(nu), r * math.sin(nu), 0.0)
    vp = (-mu / h * math.sin(nu), mu / h * (e + math.cos(nu)), 0.0)
    cO, sO = math.cos(lan), math.sin(lan)
    ci, si = math.cos(inc), math.sin(inc)
    cw, sw = math.cos(argp), math.sin(argp)
    R = (
        (cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si),
        (sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si),
        (sw * si, cw * si, ci),
    )
    mul = lambda v: tuple(sum(R[i][j] * v[j] for j in range(3)) for i in range(3))
    return mul(rp), mul(vp)


class System:
    """Every celestial in the install, as the game itself loaded them."""

    def __init__(self, instance=DEFAULT_INSTANCE, gamedata=None):
        if gamedata is None:
            gamedata = os.path.join(instance, "GameData")
        elif instance == DEFAULT_INSTANCE:
            instance = os.path.dirname(gamedata)
        self.instance = instance
        self.gamedata = gamedata
        self.bodies = {}
        self.log_path = None
        self._load_configs(gamedata)
        self._load_cache_radii(gamedata)
        self._load_epoch(gamedata)
        self.by_index = {}
        self._load_kopernicus_log(instance)
        for b in self.bodies.values():
            if b.soi is None:
                b.soi = b.soi_cfg if b.soi_cfg else self._hill_soi(b)
        self.mu_sun = self.bodies["Sun"].mu if "Sun" in self.bodies else 1.3271244004193938e20

    # --- loading ---------------------------------------------------------
    def _load_configs(self, gamedata):
        root = os.path.join(gamedata, "RealSolarSystem", "RSSKopernicus")
        idx, alias = {}, {}
        for dirpath, _dirs, files in os.walk(root):
            if "Cache" in dirpath:
                continue
            for f in files:
                if not f.endswith(".cfg"):
                    continue
                tree = cfgnode.load(os.path.join(dirpath, f))
                for node in tree.walk():
                    if node.name != "Body":
                        continue
                    name = node.get("cbNameLater") or node.get("name")
                    if not name:
                        continue
                    props = node.node("Properties")
                    orbit = node.node("Orbit")
                    if props is None and orbit is None:
                        continue
                    b = Body(name, props, orbit)
                    if b.mu or b.a:
                        self.bodies[name] = b
                        fgi = node.get("flightGlobalsIndex")
                        if fgi is not None:
                            idx[name] = int(fgi)
                        # RSS renames stock bodies with cbNameLater, but the MOONS
                        # still point at the stock name: the Moon's referenceBody is
                        # "Kerbin". Unaliased, Earth silently has no children.
                        stock = node.get("name")
                        if stock and stock != name:
                            alias[stock] = name
        self.flight_globals_index = idx
        self.alias = alias
        for b in self.bodies.values():
            if b.parent in alias:
                b.parent = alias[b.parent]

    def _load_cache_radii(self, gamedata):
        """Radius as ModuleManager left it, not as the .cfg wrote it.

        RSS ships Jupiter_Oblate.cfg and three siblings, which do
        `@radius *= 1.0226...` to restate the EQUATORIAL radius. Read only the raw
        .cfg and the four gas giants come out small -- Jupiter by 1,569 km, Saturn
        2,000 km, Uranus 192 km, Neptune 139 km. The trajectory is untouched
        (radius never enters the propagation) but every altitude and every "Rj"
        printed against them is wrong by that much, and so is any periapsis
        compared against a contract's altitude gate. The other 28 bodies agree
        exactly, which is why this stayed invisible.

        ModuleManager.ConfigCache is the post-patch truth and is already on disk.
        """
        self.cache_path = None
        p = os.path.join(gamedata, "ModuleManager.ConfigCache")
        if not os.path.exists(p):
            return
        radii, stack, pending, cur, depth = {}, [], None, {}, None
        for raw in open(p, encoding="utf-8", errors="replace"):
            line = raw.strip()
            if not line or line.startswith("//"):
                continue
            if line.startswith("{"):
                stack.append(pending or "")
                pending = None
                if stack[-1] == "Body" and depth is None:
                    cur, depth = {}, len(stack)
                continue
            if line.startswith("}"):
                if depth is not None and len(stack) == depth:
                    nm = cur.get("cbNameLater") or cur.get("name")
                    if nm and "radius" in cur:
                        radii[nm] = cur["radius"]
                    cur, depth = {}, None
                if stack:
                    stack.pop()
                continue
            if "=" in line:
                if depth is None:
                    continue
                k, v = line.split("=", 1)          # KSP splits at the FIRST '='
                k, v = k.strip(), v.strip()
                if len(stack) == depth and k in ("name", "cbNameLater"):
                    cur[k] = v
                elif (len(stack) == depth + 1 and stack[-1] == "Properties"
                      and k == "radius"):
                    try:
                        cur["radius"] = float(v)
                    except ValueError:
                        pass
                continue
            pending = line
        self.cache_path = p
        self.cache_radii = radii
        for name, r in radii.items():
            b = self.bodies.get(name) or self.bodies.get(self.alias.get(name, name))
            if b is not None and r > 0:
                b.radius = r

    def _load_epoch(self, gamedata):
        self.epoch = 0.0
        p = os.path.join(gamedata, "RealSolarSystem", "RSSKopernicusSettings.cfg")
        if os.path.exists(p):
            for line in open(p, encoding="utf-8", errors="replace"):
                line = line.split("//")[0].strip()
                if line.startswith("Epoch") and "=" in line:
                    self.epoch = float(line.split("=", 1)[1].strip())
                    break

    def _load_kopernicus_log(self, instance):
        """`Found Body: Moon:9 -> SOI = 66167158.65` -- index and SOI as the game built them.

        The only honest source for a save's ORBIT REF: FlightGlobals.Bodies order
        comes from Kopernicus' load order, not from flightGlobalsIndex.
        """
        p = os.path.join(instance, "Logs", "Kopernicus", "Kopernicus.log")
        if not os.path.exists(p):
            return
        self.log_path = p
        pat = re.compile(r"Found Body:\s*(\S+):(\d+)\s*->\s*SOI\s*=\s*([^,\s]+)")
        for line in open(p, encoding="utf-8", errors="replace"):
            m = pat.search(line)
            if not m:
                continue
            name, index, soi = m.group(1), int(m.group(2)), m.group(3)
            b = self.bodies.get(name)
            if b is None:
                continue
            b.index = index
            b.soi = float("inf") if soi.lower().startswith("inf") else float(soi)
            self.by_index[index] = b

    def _hill_soi(self, b):
        if not b.parent or b.parent not in self.bodies:
            return float("inf")
        return b.a * (b.mu / self.bodies[b.parent].mu) ** 0.4

    # --- lookup ----------------------------------------------------------
    def body(self, name):
        if isinstance(name, Body):
            return name
        if isinstance(name, int) or (isinstance(name, str) and name.isdigit()):
            return self.by_index[int(name)]
        if name in self.bodies:
            return self.bodies[name]
        for k in self.bodies:
            if k.lower() == str(name).lower():
                return self.bodies[k]
        raise KeyError(f"no body {name!r}; known: {', '.join(sorted(self.bodies))}")

    def mu_of(self, name):
        return self.body(name).mu

    def children(self, name):
        n = self.body(name).name
        return [b for b in self.bodies.values() if b.parent == n]

    def chain(self, name):
        """[body, parent, ..., Sun]"""
        out, cur = [], self.body(name).name
        while cur:
            out.append(cur)
            cur = self.bodies[cur].parent
        return out

    def common_parent(self, a, b):
        ca, cb = self.chain(a), self.chain(b)
        for n in ca:
            if n in cb:
                return n
        return "Sun"

    # --- geometry --------------------------------------------------------
    def rotation_angle(self, name, ut):
        """Degrees the body has turned at `ut`, in the game's own convention.

        Returns None for a body that does not rotate, rather than 0.0 -- "not rotating"
        and "rotated to zero" are different answers and a launch solver must not confuse
        them. Checked against the running game by `plan.py crosscheck`.
        """
        b = self.body(name)
        period = b.rot
        if b.tidally_locked:
            # KSP overwrites rotationPeriod with the orbital period BEFORE computing the
            # angle, so a locked body's own rotationPeriod value is not what is used.
            orbital = self.period(name)
            if orbital:
                period = orbital
        if not period:
            return None
        return (b.initial_rotation + 360.0 * ut / period) % 360.0

    def period(self, name):
        """Orbital period of a body about its parent, or None for the root."""
        b = self.body(name)
        if not b.parent or b.parent == b.name:
            return None
        mu = self.body(b.parent).mu
        if not mu or b.a <= 0:
            return None
        return 2 * math.pi * math.sqrt(b.a ** 3 / mu)

    def rel(self, name, ut):
        """State of `name` about its own parent."""
        b = self.body(name)
        mu = self.bodies[b.parent].mu
        n = math.sqrt(mu / b.a ** 3)
        return elements_to_rv(b.a, b.e, b.inc, b.lan, b.argp, b.M0 + n * (ut - self.epoch), mu)

    def rel_array(self, name, ts):
        """Vectorised `rel`: positions/velocities of `name` about its parent at many times."""
        import numpy as _np
        b = self.body(name)
        mu = self.bodies[b.parent].mu
        ts = _np.atleast_1d(_np.asarray(ts, float))
        n = math.sqrt(mu / b.a ** 3)
        M = _np.mod(b.M0 + n * (ts - self.epoch), 2 * math.pi)
        E = _np.where(b.e < 0.8, M, math.pi) + _np.zeros_like(M)
        for _ in range(80):
            d = -(E - b.e * _np.sin(E) - M) / (1 - b.e * _np.cos(E))
            E = E + d
            if _np.all(_np.abs(d) < 1e-14):
                break
        nu = 2 * _np.arctan2(math.sqrt(1 + b.e) * _np.sin(E / 2), math.sqrt(1 - b.e) * _np.cos(E / 2))
        r = b.a * (1 - b.e * _np.cos(E))
        p = b.a * (1 - b.e * b.e)
        h = math.sqrt(mu * p)
        cO, sO = math.cos(b.lan), math.sin(b.lan)
        ci, si = math.cos(b.inc), math.sin(b.inc)
        cw, sw = math.cos(b.argp), math.sin(b.argp)
        R = _np.array([
            [cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
            [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
            [sw * si, cw * si, ci],
        ])
        rp = _np.stack([r * _np.cos(nu), r * _np.sin(nu), _np.zeros_like(r)], axis=1)
        vp = _np.stack([-mu / h * _np.sin(nu), mu / h * (b.e + _np.cos(nu)), _np.zeros_like(r)], axis=1)
        return rp @ R.T, vp @ R.T

    def state_array(self, name, ts, centre="Sun"):
        """Vectorised `state`: walk the parent chain, summing."""
        import numpy as _np
        ts = _np.atleast_1d(_np.asarray(ts, float))
        r = _np.zeros((len(ts), 3))
        v = _np.zeros((len(ts), 3))
        cur = self.body(name).name
        centre = self.body(centre).name
        while cur != centre:
            rr, vv = self.rel_array(cur, ts)
            r += rr
            v += vv
            cur = self.bodies[cur].parent
            if cur is None:
                raise ValueError(f"{name} is not inside {centre}")
        return r, v

    def state(self, name, ut, centre="Sun"):
        """State of `name` in the frame of `centre` (any ancestor of it)."""
        r = (0.0, 0.0, 0.0)
        v = (0.0, 0.0, 0.0)
        cur = self.body(name).name
        centre = self.body(centre).name
        while cur != centre:
            rr, vv = self.rel(cur, ut)
            r = tuple(r[i] + rr[i] for i in range(3))
            v = tuple(v[i] + vv[i] for i in range(3))
            cur = self.bodies[cur].parent
            if cur is None:
                raise ValueError(f"{name} is not inside {centre}")
        return r, v

    def helio(self, name, ut):
        return self.state(name, ut, "Sun")


def ut_of(y, mo=1, d=1, h=0, mi=0, s=0):
    dt = datetime.datetime(y, mo, d, h, mi, int(s))
    return (dt - datetime.datetime(EPOCH_YEAR, 1, 1)).total_seconds() + (s - int(s))


def date_of(ut):
    return datetime.datetime(EPOCH_YEAR, 1, 1) + datetime.timedelta(seconds=ut)


def parse_date(s):
    """'1966-09-26', '1966-09-26T13:40', or a bare UT in seconds."""
    s = str(s).strip()
    if re.fullmatch(r"[-+]?\d+(\.\d*)?([eE][-+]?\d+)?", s):
        return float(s)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
        return (dt - datetime.datetime(EPOCH_YEAR, 1, 1)).total_seconds()
    raise ValueError(f"cannot read date {s!r}")


def fmt_ut(ut):
    return f"{date_of(ut):%Y-%m-%d %H:%M} (UT {ut:,.0f})"


if __name__ == "__main__":
    S = System()
    print(f"epoch {S.epoch:,.3f} s  ({date_of(S.epoch):%Y-%m-%d %H:%M:%S})")
    print(f"kopernicus log: {S.log_path}")
    print(f"{'idx':>4s} {'body':10s} {'parent':10s} {'R km':>10s} {'mu':>12s} {'SOI km':>14s} src")
    for b in sorted(S.bodies.values(), key=lambda b: (b.index if b.index is not None else 999)):
        src = "log" if b.index is not None else ("cfg" if b.soi_cfg else "hill")
        print(f"{b.index if b.index is not None else -1:4d} {b.name:10s} {str(b.parent):10s} "
              f"{b.radius/1e3:10,.0f} {b.mu:12.5e} {b.soi/1e3:14,.0f} {src}")
