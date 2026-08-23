"""Launch sites, launch azimuths, and the time of day a pad passes under an orbit plane.

A launch window is only half an answer. "Depart 26 Sep 1966" says nothing about when to
press launch, and the difference matters: the plane you reach is set by the moment you
leave the pad, and being an hour out costs a plane change that no amount of good
targeting downstream recovers. `plan.py depart --park` already solves the RAAN that makes
a departure coplanar; this file solves the other half -- when the pad is in THAT plane.

Three things live here.

`sites()`     the launch sites, from KSCSwitcher's and RSS's configs.
`Site`        one pad: body, latitude, longitude, and its inertial direction over time.
`plane_pass`  when the pad crosses a given orbit plane, and on what azimuth.

THE ZERO POINT. The pad's inertial longitude is (its body-fixed longitude) plus (how far
the body has turned). The second term is `rotation_angle`, which KSP computes as
`(initialRotation + 360 * UT / rotationPeriod) % 360`, read out of CelestialBody. What is
NOT written down anywhere is the constant relating that angle to inertial longitude in
the frame orbits are expressed in. Getting it wrong shifts every launch time by the same
amount -- self-consistently, so no internal check would ever notice.

So it is measured, not derived: `/sites` reports the pad's actual inertial position
vector at the game's own UT, and `Site.calibrate()` reads the offset off that. Offline,
`OFFSET_DEG` below is used instead; `plan.py crosscheck` diffs the two and will say so if
the offline value has drifted. Trust the live number; treat the offline one as a
convenience that is checked, not as an authority.
"""
import math
import os

import numpy as np

import cfgnode
from rss_ephem import DAY, DEFAULT_INSTANCE

# Body-fixed longitude zero relative to the inertial x-axis at rotation_angle == 0.
# Measured against the running game (see `plan.py crosscheck --sites`), not derived.
# A value here that is wrong by d degrees puts every launch time wrong by
# d/360 * rotation period -- four minutes per degree on Earth.
OFFSET_DEG = 0.0


class Site:
    """One launch pad, and where it points."""

    def __init__(self, name, display, body, lat, lon, alt=0.0, source=""):
        self.name = name
        self.display = display or name
        self.body = body
        self.lat = float(lat)
        self.lon = float(lon)
        self.alt = float(alt)
        self.source = source
        self._offset = OFFSET_DEG           # replaced by calibrate()
        self._calibrated = False

    def __repr__(self):
        return f"<Site {self.name} {self.lat:+.4f},{self.lon:+.4f} on {self.body}>"

    # --- geometry --------------------------------------------------------
    def inertial_longitude(self, system, ut):
        """Where the pad points, as an angle about the body's spin axis, in degrees."""
        rot = system.rotation_angle(self.body, ut)
        if rot is None:
            raise ValueError(f"{self.body} does not rotate; a launch time is meaningless on it")
        return (self.lon + rot + self._offset) % 360.0

    def direction(self, system, ut):
        """Unit vector from the body's centre to the pad, in the z-up inertial frame."""
        a = math.radians(self.inertial_longitude(system, ut))
        p = math.radians(self.lat)
        return np.array([math.cos(p) * math.cos(a), math.cos(p) * math.sin(a), math.sin(p)])

    def calibrate(self, system, ut, r_zup):
        """Pin the zero point from a position vector the GAME reported at `ut`.

        This replaces the module constant for this Site only. It is the difference
        between a launch time that is right and one that is consistently wrong.
        """
        r = np.asarray(r_zup, float)
        if np.linalg.norm(r) <= 0:
            return None
        measured = math.degrees(math.atan2(r[1], r[0])) % 360.0
        rot = system.rotation_angle(self.body, ut)
        if rot is None:
            return None
        self._offset = (measured - self.lon - rot) % 360.0
        if self._offset > 180.0:
            self._offset -= 360.0
        self._calibrated = True
        return self._offset

    @property
    def calibrated(self):
        return self._calibrated

    @property
    def offset(self):
        return self._offset

    def rotation_speed(self, system):
        """Eastward speed the pad already has from the body's spin, m/s.

        Free delta-v at launch, and the reason the heading actually flown is not the
        inertial azimuth: the rocket only has to supply the difference.
        """
        b = system.body(self.body)
        period = b.rot
        if b.tidally_locked:
            period = system.period(self.body) or period
        if not period:
            return 0.0
        return 2 * math.pi * (b.radius + self.alt) * math.cos(math.radians(self.lat)) / period

    def min_inclination(self):
        """The lowest inclination reachable without a plane change: |latitude|."""
        return abs(self.lat)


def plane_normal(inc_deg, raan_deg):
    """Unit normal of an orbit plane, in the z-up inertial frame.

    Same convention as plan.py's park_orbit, which is pinned by the burns it produces:
    n = [sin(raan) sin(inc), -cos(raan) sin(inc), cos(inc)].
    """
    i, o = math.radians(inc_deg), math.radians(raan_deg)
    return np.array([math.sin(o) * math.sin(i), -math.cos(o) * math.sin(i), math.cos(i)])


def plane_from_normal(n):
    """(inclination, RAAN) in degrees from a plane normal. Inverse of plane_normal."""
    n = np.asarray(n, float)
    n = n / np.linalg.norm(n)
    inc = math.degrees(math.acos(max(-1.0, min(1.0, n[2]))))
    raan = math.degrees(math.atan2(n[0], -n[1])) % 360.0
    return inc, raan


def plane_passes(site, system, inc_deg, raan_deg, after_ut, count=2, v_orbit=None):
    """When does the pad cross this orbit plane, and on what heading?

    A pad at latitude phi crosses a plane of inclination i twice per rotation, and only
    if |phi| <= i <= 180 - |phi|. Solve

        r_pad . n = 0
        =>  sin(raan - alpha) = -tan(phi) / tan(i)

    for the pad's inertial longitude alpha, then invert the (linear) rotation to get UT.
    Returned in time order, starting at the first crossing at or after `after_ut`.

    The azimuth is NOT taken from the textbook `sin(beta) = cos(i)/cos(phi)`, which
    cannot tell an ascending pass from a descending one and quietly loses the sign for a
    retrograde orbit. The in-plane direction of motion is built directly instead --
    v = n x r -- and resolved into the pad's own east/north frame, which gets every case
    right without a quadrant rule.
    """
    b = system.body(site.body)
    period = b.rot
    if b.tidally_locked:
        period = system.period(site.body) or period
    if not period:
        raise ValueError(f"{site.body} does not rotate; there is no launch time to find")

    phi = math.radians(site.lat)
    inc = math.radians(inc_deg)
    if abs(math.sin(inc)) < 1e-12:
        raise ValueError("an equatorial plane has no unique crossing; any launch time is in it")
    u = -math.tan(phi) / math.tan(inc)
    if abs(u) > 1.0:
        raise ValueError(
            f"a pad at latitude {site.lat:+.3f} deg cannot reach inclination {inc_deg:.3f} deg "
            f"directly (needs {site.min_inclination():.3f} <= i <= "
            f"{180 - site.min_inclination():.3f}); launch into a reachable plane and change it, "
            f"or use a different site")

    base = math.asin(u)
    # Both roots of sin(raan - alpha) = u. These are the ascending and descending passes;
    # which is which falls out of the azimuth below rather than being assumed here.
    alphas = [(math.radians(raan_deg) - base) % (2 * math.pi),
              (math.radians(raan_deg) - (math.pi - base)) % (2 * math.pi)]

    n = plane_normal(inc_deg, raan_deg)
    out = []
    for k in range(count + 2):
        for alpha in alphas:
            # alpha = lon + rotation_angle(ut) + offset, and rotation_angle is linear in ut,
            # so this inverts exactly -- no root finding, and no chance of a missed root.
            target = (math.degrees(alpha) - site.lon - site.offset - b.initial_rotation) % 360.0
            ut = (target / 360.0) * period
            # Advance to the first occurrence at or after after_ut.
            turns = math.ceil((after_ut - ut) / period)
            ut += max(0, turns) * period
            ut += k * period
            out.append(ut)
    out = sorted(set(round(t, 6) for t in out))
    out = [t for t in out if t >= after_ut][:count]

    passes = []
    for ut in out:
        r = site.direction(system, ut)
        # Direction of motion in the plane at this point, for a prograde-about-n orbit.
        v = np.cross(n, r)
        nv = np.linalg.norm(v)
        if nv < 1e-12:
            continue
        v = v / nv
        up = r
        east = np.cross(np.array([0.0, 0.0, 1.0]), up)
        ne = np.linalg.norm(east)
        if ne < 1e-12:                      # a pad exactly at a pole has no east
            continue
        east = east / ne
        north = np.cross(up, east)
        az_inertial = math.degrees(math.atan2(float(v @ east), float(v @ north))) % 360.0

        row = {"ut": ut, "azimuth_inertial": az_inertial,
               "residual": float(r @ n),
               "ascending": bool(v[2] > 0.0)}
        if v_orbit:
            # The heading actually flown. The pad is already moving east at rotation
            # speed, so the rocket supplies only the difference -- worth ~5 deg from a
            # low-latitude site, which is not a rounding error on an ascent.
            ve = float(v @ east) * v_orbit - site.rotation_speed(system)
            vn = float(v @ north) * v_orbit
            row["azimuth_flown"] = math.degrees(math.atan2(ve, vn)) % 360.0
            row["rotation_bonus"] = site.rotation_speed(system) * math.cos(
                math.radians(az_inertial - 90.0))
        passes.append(row)
    return passes


# ---------------------------------------------------------------------------
# the site table
# ---------------------------------------------------------------------------
def sites(instance=DEFAULT_INSTANCE, gamedata=None, body="Earth"):
    """Every launch site in the install, keyed by name.

    Read from KSCSwitcher's LaunchSites.cfg and RSS's patch to it. The PQSCity block is
    what the game positions the pad from, so its latitude/longitude are the pad's -- the
    MapDecal block alongside it is terrain shaping and is offset from the pad by up to a
    couple of tenths of a degree.
    """
    if gamedata is None:
        gamedata = os.path.join(instance, "GameData")
    strings = _localization(gamedata)
    found = {}
    for rel in (os.path.join("KSCSwitcher", "LaunchSites.cfg"),
                os.path.join("RealSolarSystem", "LaunchSites.cfg")):
        path = os.path.join(gamedata, rel)
        if not os.path.exists(path):
            continue
        tree = cfgnode.load(path)
        for node in tree.walk():
            if node.name != "Site":
                continue
            name = node.get("name")
            if not name:
                continue
            city = node.node("PQSCity")
            if city is None or not city.has("latitude"):
                continue
            # RSS writes these as "displayName = #RSS_Site_woomera_name//AU - Woomera".
            # The readable half is behind a "//", which is KSP's COMMENT marker, so the
            # parser strips it exactly as the game does and only the token survives. The
            # real text lives in the localisation file, so read that rather than shipping
            # "#RSS_Site_cape_canaveral_name" to a terminal.
            display = node.get("displayName") or name
            if display.startswith("#"):
                display = strings.get(display, name.replace("_", " "))
            found[name] = Site(name, display, body,
                               city.getf("latitude", 0.0), city.getf("longitude", 0.0),
                               0.0, source=rel)
    return found


def _localization(gamedata, lang="en-us"):
    """The #RSS_Site_* -> readable-name table, or {} if the file is not there."""
    path = os.path.join(gamedata, "RealSolarSystem", "Localization", "LaunchSites", lang + ".cfg")
    if not os.path.exists(path):
        return {}
    out = {}
    for node in cfgnode.load(path).walk():
        for k, v in node.values:
            if k.startswith("#"):
                out[k] = v
    return out


def site(name, instance=DEFAULT_INSTANCE, gamedata=None, body="Earth"):
    """One site by name, matched exactly then loosely. An ambiguous name is an error."""
    table = sites(instance, gamedata, body)
    if name in table:
        return table[name]
    hits = [s for k, s in table.items()
            if name.lower() in k.lower() or name.lower() in s.display.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise KeyError(f"no launch site matching {name!r}; try one of: "
                       + ", ".join(sorted(table)[:12]) + " ...")
    raise KeyError(f"{name!r} matches {len(hits)} sites: "
                   + ", ".join(sorted(h.name for h in hits)))


def active_site(save, instance=DEFAULT_INSTANCE, gamedata=None, body="Earth"):
    """The site the save is currently launching from.

    KSCSwitcher RELOCATES the single KSC rather than adding sites, and records its choice
    as LastLaunchSite in the LastKSC scenario module. A save that has never switched has
    no such node, which means the default -- not an error.
    """
    name = None
    try:
        for node in save.game.walk():
            if node.name == "SCENARIO" and node.get("name") == "LastKSC":
                name = node.get("LastLaunchSite")
                break
    except Exception:                                               # noqa: BLE001
        name = None
    table = sites(instance, gamedata, body)
    if name and name in table:
        return table[name]
    for default in ("us_cape_canaveral", "ksc"):
        if default in table:
            return table[default]
    return next(iter(table.values())) if table else None
