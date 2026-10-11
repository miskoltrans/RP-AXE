"""Midcourse correction that lays the arrival orbit plane through a surface site.

`--bplane polar` fixes the arrival INCLINATION but leaves the node line wherever the
asymptote puts it, so the site underneath can be half a rotation away -- on Svarog Ferry 3
the first overhead pass came 13.66 d after arrival. The orbit plane must contain the incoming
asymptote `s`, so the only plane through `s` that also contains the site is the one spanned by
`s` and the site position: B_hat is the component of r_site perpendicular to s, and the orbit
normal is s x B_hat. The resulting inclination is not 90 deg, but it can never be lower than
the site latitude, so for a near-polar site it stays near-polar.
"""
import argparse
import math
import sys

import numpy as np

from rss_ephem import System, fmt_ut, DEFAULT_INSTANCE
import astro
import patched
import maneuver
import launch as launch_mod
import bridge as bridge_mod

DAY = 86400.0


def locked_offset(system, body_name, ut):
    """Longitude zero point of a TIDALLY LOCKED body, from its sub-parent point.

    A locked body keeps longitude 0 facing its parent, so the inertial longitude of the
    parent direction is the zero point. That is a physical constraint rather than a constant
    measured on Earth's launch pads, which is what launch.OFFSET_DEG is.

    The instantaneous sub-parent point is NOT the zero point: KSP rotates a body uniformly
    while its orbit is eccentric, so the sub-parent longitude oscillates about the true zero
    by the libration amplitude (the Moon's is about +-8 deg). The constant is the MEAN, so
    average around one full orbit and report the spread as the honest uncertainty.
    """
    period = system.period(body_name) or 27.321661 * DAY
    offs = []
    for k in range(240):
        t = ut + period * k / 240.0
        rb, _ = system.rel(body_name, t)
        d = -np.asarray(rb, float)
        d = d / np.linalg.norm(d)
        sub = math.degrees(math.atan2(d[1], d[0])) % 360.0
        rot = system.rotation_angle(body_name, t)
        if rot is None:
            raise ValueError(body_name + " does not rotate")
        offs.append(math.radians((sub - rot) % 360.0))
    mean = math.degrees(math.atan2(float(np.mean(np.sin(offs))), float(np.mean(np.cos(offs)))))
    dev = [((math.degrees(o) - mean + 180.0) % 360.0) - 180.0 for o in offs]
    spread = float(max(abs(min(dev)), abs(max(dev))))
    return mean, spread, len(offs)


def perp_to(vec, s):
    """Component of `vec` perpendicular to unit vector `s`, normalised."""
    b = vec - float(vec @ s) * s
    n = float(np.linalg.norm(b))
    if n < 1e-6:
        raise ValueError("the site lies along the asymptote; its plane is undefined")
    return b / n


def solve_side(system, body, rn, vn, burn_ut, tgt, t_end, peR, site, sign, passes=3):
    """Refine a burn whose arrival plane contains the site, on one side of the target."""
    dv = np.zeros(3)
    out = None
    for _ in range(passes):
        traj = patched.shoot(system, body, rn, vn + dv, burn_ut, t_end, watch=[tgt.name])
        rep = patched.arrival_report(system, traj, tgt.name, t_end)
        if not rep.get("captured"):
            return None
        r_a, v_a = maneuver._arrival_state(system, traj, tgt.name, rep["soi_ut"])
        bp = astro.bplane(tgt.mu, r_a, v_a)
        if bp is None:
            return None
        s = bp["s_hat"]
        r_site = site.direction(system, rep["soi_ut"]) * tgt.radius
        w = np.cross(s, sign * perp_to(r_site, s))
        w = w / np.linalg.norm(w)
        bdir = np.cross(s, w)
        d = np.array([float(bdir @ bp["t_hat"]), float(bdir @ bp["r_hat"])])
        d = d / np.linalg.norm(d)
        out = maneuver.refine(system, body, rn, vn, burn_ut, tgt.name, t_end, peR,
                              b_dir=d, watch=[tgt.name], max_dv=400.0)
        dv = out["dv"]
    if out is None or not out["report"].get("captured"):
        return None
    rep = out["report"]
    r_a, v_a = maneuver._arrival_state(system, out["traj"], tgt.name, rep["soi_ut"])
    wn = np.cross(r_a, v_a)
    wn = wn / np.linalg.norm(wn)
    r_site = site.direction(system, rep["soi_ut"]) * tgt.radius
    off = math.degrees(math.asin(min(1.0, abs(float(wn @ r_site)) / tgt.radius)))
    inc, lan = launch_mod.plane_from_normal(wn)
    return {"dv": dv, "traj": out["traj"], "rep": rep, "off": off,
            "inc": inc, "lan": lan, "sign": sign}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vessel-id", required=True)
    ap.add_argument("--target", default="Moon")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--site-name", default="site")
    ap.add_argument("--peri", default="100km")
    ap.add_argument("--burn-at", type=float, default=None, help="absolute UT for the burn")
    ap.add_argument("--after", type=float, default=2.0,
                    help="percent of the way to arrival, when no --burn-at")
    ap.add_argument("--port", type=int, default=8284)
    ap.add_argument("--instance", default=DEFAULT_INSTANCE)
    ap.add_argument("--horizon", type=float, default=60.0)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--alarm", default=None)
    a = ap.parse_args(argv)

    system = System(instance=a.instance)
    br = bridge_mod.Bridge(port=a.port)
    body, r0, v0, ut0 = br.state(system, vid=a.vessel_id)
    r0 = np.asarray(r0, float)
    v0 = np.asarray(v0, float)
    name = br.nodes(vid=a.vessel_id).get("vessel")
    tgt = system.body(a.target)
    alt = float(a.peri.rstrip("km")) * 1000.0
    peR = tgt.radius + alt

    print("OVER-SITE MCC  " + str(name) + " [live, id " + a.vessel_id[:8] + "]  -> " + tgt.name)
    print("  site %s  lat %+.4f  lon %+.4f" % (a.site_name, a.lat, a.lon))

    t_end = ut0 + a.horizon * DAY
    traj0 = patched.shoot(system, body, r0, v0, ut0, t_end, watch=[tgt.name])
    rep0 = patched.arrival_report(system, traj0, tgt.name, t_end)
    if not rep0.get("captured"):
        sys.exit("  no arrival to aim from -- this trajectory does not reach the SOI")
    soi_ut = rep0["soi_ut"]
    print("  doing nothing: SOI %s  pe %.0f km alt"
          % (fmt_ut(soi_ut), (rep0["peR"] - tgt.radius) / 1000))

    off, spread, n = locked_offset(system, tgt.name, soi_ut)
    print("\n  %s longitude zero point from tidal locking: %+.3f deg "
          "(mean of %d samples over one orbit, libration +-%.2f deg)"
          % (tgt.name, off, n, spread))
    delta = ((off - launch_mod.OFFSET_DEG + 180.0) % 360.0) - 180.0
    print("  launch.OFFSET_DEG is %+.3f deg -- differs by %+.3f deg, so the Earth-pad default "
          "would put the site %.0f km off" % (launch_mod.OFFSET_DEG, delta,
          math.radians(math.degrees(math.asin(min(1.0, abs(math.cos(math.radians(a.lat))
          * math.sin(math.radians(delta))))))) * tgt.radius / 1000))

    site = launch_mod.Site(a.site_name, a.site_name, tgt.name, a.lat, a.lon)
    site._offset = off
    site._calibrated = True

    burn_ut = a.burn_at if a.burn_at else ut0 + a.after / 100.0 * (soi_ut - ut0)
    rn, vn = astro.propagate(body.mu, r0, v0, burn_ut - ut0)

    best = None
    for sign in (+1.0, -1.0):
        cand = solve_side(system, body, rn, vn, burn_ut, tgt, t_end, peR, site, sign)
        if cand is None:
            print("\n  side %+.0f: did not converge" % sign)
            continue
        print("\n  side %+.0f:  %8.2f m/s   arrival i %6.2f deg  LAN %7.2f   "
              "site %5.2f deg out of plane (%.0f km cross-track)"
              % (sign, float(np.linalg.norm(cand["dv"])), cand["inc"], cand["lan"],
                 cand["off"], math.radians(cand["off"]) * tgt.radius / 1000))
        if best is None or np.linalg.norm(cand["dv"]) < np.linalg.norm(best["dv"]):
            best = cand

    if best is None:
        sys.exit("  neither side converged")

    dv = best["dv"]
    rep = best["rep"]
    node = astro.to_node(rn, vn, dv)
    print("\n  CORRECTION  %s   T+%.2f d" % (fmt_ut(burn_ut), (burn_ut - ut0) / DAY))
    print("    prograde %+12.2f m/s" % node[2])
    print("    normal   %+12.2f m/s" % node[1])
    print("    radial   %+12.2f m/s" % node[0])
    print("    total    %12.2f m/s" % float(np.linalg.norm(dv)))
    print("    FLOWN: SOI %s   pe %.0f km alt   i %.2f deg   LAN %.2f"
          % (fmt_ut(rep["soi_ut"]), (rep["peR"] - tgt.radius) / 1000, best["inc"], best["lan"]))
    print("           site %.2f deg out of the arrival plane" % best["off"])

    try:
        ps = launch_mod.plane_passes(site, system, best["inc"], best["lan"], rep["soi_ut"], count=3)
        print("    overhead passes after arrival:")
        for p in ps:
            print("      %s  %+7.2f d" % (fmt_ut(p["ut"]), (p["ut"] - rep["soi_ut"]) / DAY))
    except Exception as exc:                                        # noqa: BLE001
        print("    (overhead pass solver: %s)" % exc)

    if a.push:
        res = br.place_nodes([{"ut": burn_ut, "radial": node[0], "normal": node[1],
                               "prograde": node[2]}], vid=a.vessel_id, replace=True)
        print("\n  PUSHED: placed %s" % res.get("placed"))
        for p in res.get("flight_plan", []):
            print("    %-7s -> %-10s pe %9.0f km  inc %8.4f  lan %8.3f"
                  % (p["body"], p["transition"], p["peR"] / 1000, p["inc_deg"], p["lan_deg"]))
    if a.alarm:
        print("  ALARM %s" % br.alarm(burn_ut, name=a.alarm, notes="over-site MCC").get("ok"))


if __name__ == "__main__":
    main()
