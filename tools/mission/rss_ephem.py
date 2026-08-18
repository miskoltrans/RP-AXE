"""RSS ephemeris: read the install's own Kopernicus elements and propagate two-body.

Ground truth is the running install, never a textbook table: RSS's elements are Horizons
osculating elements at the game epoch (UT 0 = 1951-01-01), and a mission plan computed from
anything else silently disagrees with the game by degrees of phase.

Usage:
    from rss_ephem import System
    sys_ = System(r"C:/git/ksp/Instance/GameData")
    r, v = sys_.helio("Jupiter", ut)        # metres, m/s, Sun-centred
    r, v = sys_.rel("Io", ut)               # about its own parent
"""
import math
import os
import re

EPOCH_YEAR = 1951  # UT 0 in RSS/RP-1
DAY = 86400.0
YEAR = 365.25 * DAY


def _parse_cfg_bodies(path):
    """Yield (name, dict-of-flat-keys) for every Body{} in a Kopernicus cfg."""
    txt = open(path, encoding="utf-8", errors="replace").read()
    txt = re.sub(r"//.*", "", txt)
    # Body name
    m = re.search(r"Body\s*\{", txt)
    if not m:
        return
    name = re.search(r"\n\s*name\s*=\s*(\S+)", txt[m.end():])
    if not name:
        return
    body = {"name": name.group(1)}
    if "cbNameLater" in txt:
        body["name"] = txt.split("cbNameLater")[1].split("=")[1].split()[0]
    # Orbit block (the one whose body is the *nested* Orbit{...} with referenceBody)
    om = re.search(r"Orbit\s*\{(.*?)\n\t\t\}", txt, re.S)
    if om:
        for k, v in re.findall(r"(\w+)\s*=\s*([^\s]+)", om.group(1)):
            body[k] = v
    pm = re.search(r"Properties\s*\{(.*?)\n\t\t\}", txt, re.S)
    if pm:
        for k, v in re.findall(r"(\w+)\s*=\s*([^\s]+)", pm.group(1)):
            body.setdefault("prop_" + k, v)
    yield body


class Body:
    def __init__(self, d):
        self.name = d["name"]
        self.parent = d.get("referenceBody")
        g = lambda k, dflt=0.0: float(d[k]) if k in d else dflt
        self.a = g("semiMajorAxis")
        self.e = g("eccentricity")
        self.inc = math.radians(g("inclination"))
        self.lan = math.radians(g("longitudeOfAscendingNode"))
        self.argp = math.radians(g("argumentOfPeriapsis"))
        if "meanAnomalyAtEpochD" in d:
            self.M0 = math.radians(float(d["meanAnomalyAtEpochD"]))
        else:
            self.M0 = g("meanAnomalyAtEpoch")
        self.mu = g("prop_gravParameter")
        self.radius = g("prop_radius")
        self.rot = g("prop_rotationPeriod")

    def __repr__(self):
        return f"<{self.name} a={self.a:.4g} e={self.e:.4f} mu={self.mu:.4g}>"


def kepler_E(M, e, tol=1e-13):
    M = math.fmod(M, 2 * math.pi)
    E = M if e < 0.8 else math.pi
    for _ in range(80):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        d = -f / fp
        E += d
        if abs(d) < tol:
            break
    return E


def elements_to_rv(a, e, inc, lan, argp, M, mu):
    E = kepler_E(M, e)
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2), math.sqrt(1 - e) * math.cos(E / 2))
    r = a * (1 - e * math.cos(E))
    p = a * (1 - e * e)
    h = math.sqrt(mu * p)
    # perifocal
    rp = (r * math.cos(nu), r * math.sin(nu), 0.0)
    vp = (-mu / h * math.sin(nu), mu / h * (e + math.cos(nu)), 0.0)
    cO, sO = math.cos(lan), math.sin(lan)
    ci, si = math.cos(inc), math.sin(inc)
    cw, sw = math.cos(argp), math.sin(argp)
    R = [
        [cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
        [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
        [sw * si, cw * si, ci],
    ]
    mul = lambda v: tuple(sum(R[i][j] * v[j] for j in range(3)) for i in range(3))
    return mul(rp), mul(vp)


class System:
    def __init__(self, gamedata):
        root = os.path.join(gamedata, "RealSolarSystem", "RSSKopernicus")
        self.bodies = {}
        for dirpath, _dirs, files in os.walk(root):
            if "Cache" in dirpath:
                continue
            for f in files:
                if not f.endswith(".cfg"):
                    continue
                for d in _parse_cfg_bodies(os.path.join(dirpath, f)):
                    b = Body(d)
                    if b.mu or b.a:
                        self.bodies[b.name] = b
        sun = self.bodies.get("Sun")
        self.mu_sun = sun.mu if sun else 1.3271244004193938e20

    def rel(self, name, ut):
        b = self.bodies[name]
        mu = self.bodies[b.parent].mu
        n = math.sqrt(mu / b.a ** 3)
        return elements_to_rv(b.a, b.e, b.inc, b.lan, b.argp, b.M0 + n * ut, mu)

    def helio(self, name, ut):
        r = (0.0, 0.0, 0.0)
        v = (0.0, 0.0, 0.0)
        cur = name
        while cur != "Sun":
            rr, vv = self.rel(cur, ut)
            r = tuple(r[i] + rr[i] for i in range(3))
            v = tuple(v[i] + vv[i] for i in range(3))
            cur = self.bodies[cur].parent
        return r, v

    def soi(self, name):
        b = self.bodies[name]
        p = self.bodies[b.parent]
        return b.a * (b.mu / p.mu) ** 0.4


def ut_of(y, mo=1, d=1, h=0, mi=0, s=0):
    import datetime
    dt = datetime.datetime(y, mo, d, h, mi, int(s))
    return (dt - datetime.datetime(EPOCH_YEAR, 1, 1)).total_seconds()


def date_of(ut):
    import datetime
    return datetime.datetime(EPOCH_YEAR, 1, 1) + datetime.timedelta(seconds=ut)


if __name__ == "__main__":
    s = System(r"C:/git/ksp/Instance/GameData")
    for n in ("Earth", "Venus", "Mars", "Jupiter", "Io", "Europa", "Ganymede", "Callisto"):
        if n in s.bodies:
            print(f"{n:10s} {s.bodies[n]}  parent={s.bodies[n].parent} R={s.bodies[n].radius/1000:.0f} km")
    print("Sun mu", s.mu_sun)
    print("Jupiter SOI (Gm)", s.soi("Jupiter") / 1e9)
