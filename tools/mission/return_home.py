"""Return-to-Earth injection from a moon orbit.

`plan.py depart --target Earth` cannot do this: Earth is the parent frame's origin, so
the Lambert solve divides by a zero position vector. This solves it as a shoot instead --
scan the burn point around the current orbit, solve the burn that drops the geocentric
periapsis onto the target radius, and report what the trajectory actually does.
"""
import argparse, sys
import numpy as np
from rss_ephem import System, fmt_ut, parse_date, DEFAULT_INSTANCE
import astro, patched, bridge as bridge_mod

DAY = 86400.0


def earth_peri(system, body, r, v, ut, horizon_d, home="Earth"):
    """Fly it. Returns (periapsis radius m, UT of periapsis, trajectory) or (None, None, traj)."""
    traj = patched.shoot(system, body, r, v, ut, ut + horizon_d * DAY, watch=[home])
    for p in traj.patches[1:]:
        if p.body.name == home:
            el = p.elements()
            rp = el.sma * (1.0 - el.ecc)
            # time to periapsis on this patch
            t_end = p.ut1 if p.ut1 else ut + horizon_d * DAY
            ts = np.linspace(p.ut0, t_end, 4000)
            rs = np.array([np.linalg.norm(p.state(t)[0]) for t in ts])
            return rp, float(ts[int(np.argmin(rs))]), traj
    return None, None, traj


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vessel-id", required=True)
    ap.add_argument("--peri", default="60km", help="target Earth periapsis altitude, e.g. 60km")
    ap.add_argument("--port", type=int, default=8284)
    ap.add_argument("--instance", default=DEFAULT_INSTANCE)
    ap.add_argument("--samples", type=int, default=240)
    ap.add_argument("--horizon", type=float, default=30.0)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--alarm", nargs="?", const="Return burn")
    a = ap.parse_args(argv)

    system = System(instance=a.instance)
    br = bridge_mod.Bridge(port=a.port)
    body, r0, v0, ut0 = br.state(system, vid=a.vessel_id)
    r0 = np.asarray(r0, float); v0 = np.asarray(v0, float)
    info = br.nodes(vid=a.vessel_id)
    name = info.get("vessel")

    home = system.body(body.name).parent_name if hasattr(system.body(body.name), "parent_name") else "Earth"
    home = "Earth"
    el0 = astro.elements(body.mu, r0, v0)
    period = 2 * np.pi * np.sqrt(el0.sma ** 3 / body.mu)
    alt = float(a.peri.rstrip("km")) * 1000.0
    want = system.body(home).radius + alt

    print(f"RETURN  {name} [live, id {a.vessel_id[:8]}]  ({body.name} -> {home})")
    print(f"  current orbit: {(el0.sma*(1-el0.ecc)-body.radius)/1000:,.0f} x "
          f"{(el0.sma*(1+el0.ecc)-body.radius)/1000:,.0f} km, i {np.degrees(el0.inc):.2f} deg, "
          f"period {period/60:.1f} min")
    print(f"  target {home} periapsis {alt/1000:,.0f} km altitude (r {want/1000:,.0f} km)")

    # Scan burn point around one orbit; at each, bisect |dv| along -velocity (lower geocentric
    # energy) and +velocity, and keep whichever reaches the target radius for less.
    best = None
    for i in range(a.samples):
        ut = ut0 + 60.0 + period * i / a.samples
        r, v = astro.propagate(body.mu, r0, v0, ut - ut0)
        vh = v / np.linalg.norm(v)
        for sign in (-1.0, +1.0):
            lo, hi = 0.0, 1400.0
            f_lo, _, _ = earth_peri(system, body, r, v, ut, a.horizon, home)
            # walk outward until the periapsis brackets the target
            prev = None
            found = None
            for mag in np.arange(40.0, 1400.0, 40.0):
                rp, _, _ = earth_peri(system, body, r, v + sign * mag * vh, ut, a.horizon, home)
                if rp is None:
                    prev = (mag, None); continue
                if prev is not None and prev[1] is not None and (prev[1] - want) * (rp - want) < 0:
                    found = (prev[0], mag); break
                prev = (mag, rp)
            if not found:
                continue
            lo, hi = found
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                rp, _, _ = earth_peri(system, body, r, v + sign * mid * vh, ut, a.horizon, home)
                if rp is None:
                    lo = mid; continue
                rp_lo, _, _ = earth_peri(system, body, r, v + sign * lo * vh, ut, a.horizon, home)
                if (rp_lo - want) * (rp - want) <= 0:
                    hi = mid
                else:
                    lo = mid
            mag = 0.5 * (lo + hi)
            if best is None or mag < best[0]:
                best = (mag, ut, sign, r, v, vh)

    if best is None:
        sys.exit("  no return trajectory found in one orbit of burn points -- widen --samples "
                 "or --horizon, or the target periapsis is unreachable from this orbit")

    mag, ut, sign, r, v, vh = best
    dv = sign * mag * vh

    # Least-squares polish on all three components so the flown periapsis lands on the target.
    def resid(d):
        rp, _, _ = earth_peri(system, body, r, v + d, ut, a.horizon, home)
        return 1e9 if rp is None else (rp - want)
    for _ in range(30):
        f = resid(dv)
        if abs(f) < 2000.0:
            break
        J = np.zeros(3)
        for k in range(3):
            e = np.zeros(3); e[k] = 0.5
            J[k] = (resid(dv + e) - f) / 0.5
        if not np.any(J):
            break
        step = -f * J / (J @ J)
        if np.linalg.norm(step) > 60.0:
            step *= 60.0 / np.linalg.norm(step)
        dv = dv + step

    rp, ut_pe, traj = earth_peri(system, body, r, v + dv, ut, a.horizon, home)
    node = astro.to_node(r, v, dv)
    print()
    print(f"  BURN  {fmt_ut(ut)}   T+{(ut-ut0)/60:,.1f} min from now")
    print(f"    prograde {node[2]:+12,.2f} m/s")
    print(f"    normal   {node[1]:+12,.2f} m/s")
    print(f"    radial   {node[0]:+12,.2f} m/s")
    print(f"    total    {np.linalg.norm(dv):12,.2f} m/s")
    print()
    print("    FLOWN:")
    for p in traj.patches:
        el = p.elements()
        print(f"      {p.body.name:<8} {fmt_ut(p.ut0)} -> {p.end or 'horizon':<12} "
              f"pe {(el.sma*(1-el.ecc))/1000:>10,.0f} km  i {np.degrees(el.inc):6.2f} deg")
    if rp is not None:
        eb = system.body(home)
        print(f"      {home} periapsis {(rp-eb.radius)/1000:,.1f} km altitude at {fmt_ut(ut_pe)}")
        # entry speed at 120 km interface
        ri = eb.radius + 120000.0
        pe_patch = [p for p in traj.patches[1:] if p.body.name == home][0]
        el = pe_patch.elements()
        vis = np.sqrt(eb.mu * (2.0 / ri - 1.0 / el.sma)) if el.sma > 0 or el.ecc > 1 else float("nan")
        print(f"      entry speed at 120 km interface: {vis:,.0f} m/s   e {el.ecc:.4f}")
        print(f"      coast {(ut_pe-ut)/DAY:,.2f} d from the burn")

    if a.push:
        res = br.place_nodes([{"ut": ut, "radial": node[0], "normal": node[1],
                               "prograde": node[2]}], vid=a.vessel_id, replace=True)
        print(f"\n  PUSHED: {res}")
    if a.alarm:
        res = br.alarm(ut, name=a.alarm, notes="return-to-Earth injection")
        print(f"  ALARM  {a.alarm} at {fmt_ut(ut)}  {res}")


if __name__ == "__main__":
    main()
