"""Return-to-Earth injection from a moon orbit.

`plan.py depart --target Earth` cannot do this: Earth is the parent frame's origin, so
the Lambert solve divides by a zero position vector. This solves it as a shoot instead.

TWO THINGS SET THE ANSWER, AND THE SECOND ONE IS THE EXPENSIVE ONE:

  1. WHEN.  A prograde burn can only throw v-infinity along directions that lie in the
     vessel's orbital plane, and a return has to throw it AGAINST the Moon's orbital
     velocity.  So the cost is set by `h_hat . v_hat_moon` -- 0 means the retrograde
     direction is in-plane and the burn is cheap, +-1 means it is perpendicular and no
     amount of prograde reaches Earth.  h_hat is fixed (inertial); v_hat_moon sweeps a
     full turn per lunar month, so the metric crosses zero twice a month whatever the
     orbit.  Measured on Svarog Ferry 1979-06-01: 1,624 m/s at h.v = +0.914, 753 m/s
     seven days later at h.v = +0.12.  `--days` scans for that window.
  2. WHAT.  At the good epoch the burn is essentially pure prograde; away from it the
     solver needs out-of-plane freedom, so the search is over the full v-infinity VECTOR
     (MechJeb's RealSingleImpulseHyperbolicBurn picks the cheapest burn point for it)
     under an equality constraint on the geocentric periapsis.

Analytic guess -> fly it -> re-seed on the measured SOI exit time -> Newton-polish the
flown periapsis onto the target.  Every answer ends in a FLOWN: block.

MechJeb's own "return from a moon" does the same job in one click and is the fast path
when KSP is in front of you; this exists for planning without the game, for picking the
window, and for pushing the node unattended.
"""
import argparse, math, sys

import numpy as np
from scipy.optimize import minimize

from rss_ephem import System, fmt_ut, DEFAULT_INSTANCE
import astro, patched, maneuver, bridge as bridge_mod

DAY = 86400.0


def time_to_periapsis(mu, r, v):
    """Seconds from this state to the NEXT periapsis passage. Ellipse or hyperbola."""
    el = astro.elements(mu, r, v)
    e, sma, nu = el.ecc, el.sma, el.nu
    if e < 1.0:
        ea = 2.0 * math.atan2(math.sqrt(1 - e) * math.sin(nu / 2),
                              math.sqrt(1 + e) * math.cos(nu / 2))
        n = math.sqrt(mu / sma ** 3)
        t = (ea - e * math.sin(ea)) / n            # time SINCE periapsis, signed
        return (2 * math.pi / n - t) if t > 0 else -t
    ha = 2.0 * math.atanh(math.sqrt((e - 1) / (e + 1)) * math.tan(nu / 2))
    t = (e * math.sinh(ha) - ha) / math.sqrt(mu / (-sma) ** 3)
    return -t if t < 0 else float("inf")           # already outbound: never again


def earth_peri(system, body, r, v, ut, horizon_d, home="Earth"):
    """Fly it. Returns (periapsis radius m, UT of the FIRST periapsis, trajectory).

    The periapsis TIME is taken from the conic, not from an argmin over samples: a return
    ellipse crosses perigee twice inside a 30 d horizon at the same radius to within a
    metre, so sampling picks whichever passage a sample happened to land nearest -- a coin
    flip that lands one full orbital period (10.7 d on the Svarog return) late. That is
    invisible in the periapsis ALTITUDE, which is right either way, and it is the number a
    life-support margin is computed from.
    """
    traj = patched.shoot(system, body, r, v, ut, ut + horizon_d * DAY, watch=[home])
    for p in traj.patches[1:]:
        if p.body.name == home:
            el = p.elements()
            rp = el.sma * (1.0 - el.ecc)
            rr, vv = p.state(p.ut0)
            dt = time_to_periapsis(p.body.mu, rr, vv)
            if not math.isfinite(dt):
                return rp, None, traj
            return rp, float(p.ut0 + dt), traj
    return None, None, traj


def soi_exit_ut(traj, body):
    """UT the trajectory leaves `body`'s SOI, or None."""
    for p in traj.patches:
        if p.body.name == body.name and p.ut1:
            return p.ut1
    return None


def alignment(system, hn, ut, moon="Moon"):
    """h_hat . v_hat_moon -- 0 means a prograde burn throws v-inf in the right direction."""
    _, vm = system.rel(moon, ut)
    vm = np.asarray(vm, float)
    return float(hn @ (vm / np.linalg.norm(vm)))


def align_windows(system, hn, ut0, days, moon="Moon", step=0.1):
    """UTs in [ut0, ut0+days] where the alignment metric crosses zero."""
    ts = np.arange(ut0, ut0 + days * DAY, step * DAY)
    vals = np.array([alignment(system, hn, t, moon) for t in ts])
    out = []
    for i in range(len(ts) - 1):
        if vals[i] == 0.0 or vals[i] * vals[i + 1] < 0:
            f = abs(vals[i]) / (abs(vals[i]) + abs(vals[i + 1]))
            out.append(float(ts[i] + f * (ts[i + 1] - ts[i])))
    return out


def geo_peri(mu_home, rm, vm, vinf):
    """Geocentric periapsis radius of the state the vehicle has when it leaves the SOI."""
    v = vm + vinf
    rn = float(np.linalg.norm(rm))
    en = float(v @ v) / 2.0 - mu_home / rn
    h2 = float(np.cross(rm, v) @ np.cross(rm, v))
    sma = -mu_home / (2.0 * en)
    ecc = math.sqrt(max(1.0 + 2.0 * en * h2 / mu_home ** 2, 0.0))
    return sma * (1.0 - ecc)


def analytic_burn(system, body, home, r0, v0, ut0, ut_ref, want, tof_d=0.75, scan=37):
    """Cheapest single impulse at/after `ut_ref` whose SOI-exit state has periapsis `want`.

    Free variables are the three components of v-infinity; the burn point that buys a given
    v-infinity most cheaply is closed form (MechJeb's geometry), so this is a 3-DOF solve.
    """
    rr, vv = astro.propagate(body.mu, r0, v0, ut_ref - ut0)
    rm, vm = system.rel(body.name, ut_ref + tof_d * DAY)
    rm = np.asarray(rm, float); vm = np.asarray(vm, float)
    mu_home = system.body(home).mu

    rn = float(np.linalg.norm(rm))
    sma = (rn + want) / 2.0
    vt = math.sqrt(mu_home * (2.0 / rn - 1.0 / sma))
    that = np.cross(np.cross(rm, vm), rm); that /= np.linalg.norm(that)
    seed = vt * that - vm                      # kill the Moon's transverse velocity

    def cost(x, s=scan):
        try:
            b = maneuver.single_impulse_hyperbolic_burn(body.mu, rr, vv, x, scan=s)
        except (ValueError, ZeroDivisionError):
            return 1e6
        return float(np.linalg.norm(b["dv"]))

    res = minimize(cost, seed, method="SLSQP", options={"maxiter": 150, "ftol": 1e-4, "eps": 1.0},
                   constraints=[{"type": "eq",
                                 "fun": lambda x: (geo_peri(mu_home, rm, vm, x) - want) / 1e6}])
    b = maneuver.single_impulse_hyperbolic_burn(body.mu, rr, vv, res.x, scan=361)
    return {"ut": ut_ref + b["dt"], "r": b["r_burn"], "v": b["v_neg"], "dv": b["dv"],
            "mag": float(np.linalg.norm(b["dv"])), "vinf": res.x}


# ---------------------------------------------------------------------------
# global search.  A local solve on this problem is not safe: the return family has
# several disconnected basins (a direct fall vs a loop out past apogee and back),
# and SLSQP picks whichever one the seed is nearest.  Measured on Svarog Ferry, a
# min-TIME solve returned a CHEAPER burn than the min-DELTA-V solve at the same
# epoch -- impossible, and the tell that both were local.  So scan the v-infinity
# DIRECTION globally and root-solve the magnitude, which is one dimension and
# monotone.  ~1,100 directions is enough to separate the basins.
# ---------------------------------------------------------------------------
def _sphere(nt=72, npol=36):
    out = []
    for i in range(npol):
        ct = -1.0 + 2.0 * (i + 0.5) / npol
        st = math.sqrt(max(1.0 - ct * ct, 0.0))
        for j in range(nt):
            ph = 2 * math.pi * j / nt
            out.append([st * math.cos(ph), st * math.sin(ph), ct])
    return np.array(out)


def _peri_many(mu_home, rm, vm, V):
    """Geocentric periapsis for a stack of candidate v-infinity vectors."""
    v = vm + V
    rn = float(np.linalg.norm(rm))
    en = 0.5 * np.einsum("ij,ij->i", v, v) - mu_home / rn
    h = np.cross(rm, v)
    sma = -mu_home / (2.0 * en)
    ecc = np.sqrt(np.maximum(1.0 + 2.0 * en * np.einsum("ij,ij->i", h, h) / mu_home ** 2, 0.0))
    return sma * (1.0 - ecc)


def time_to_soi(mu, r, v, soi):
    """Seconds until the state leaves radius `soi`, or None if it never does."""
    lo, hi = 0.0, 8 * DAY
    if float(np.linalg.norm(astro.propagate(mu, r, v, hi)[0])) < soi:
        return None
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if float(np.linalg.norm(astro.propagate(mu, r, v, mid)[0])) < soi:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def scan_epoch(system, body, home, r0, v0, ut0, ut_ref, want, dirs, cap=1e9, tof_d=0.8):
    """Every single-impulse return at this epoch: (|dv|, total days from ut0, burn)."""
    mu_home = system.body(home).mu
    rr, vv = astro.propagate(body.mu, r0, v0, ut_ref - ut0)
    rm, vm = system.rel(body.name, ut_ref + tof_d * DAY)
    rm = np.asarray(rm, float); vm = np.asarray(vm, float)
    mags = np.linspace(150.0, 2600.0, 180)
    cands = []
    for d in dirs:
        f = _peri_many(mu_home, rm, vm, np.outer(mags, d)) - want
        sg = np.sign(f)
        for k in np.where(sg[:-1] * sg[1:] < 0)[0]:
            lo, hi = mags[k], mags[k + 1]
            f_lo = f[k]
            for _ in range(36):
                mid = 0.5 * (lo + hi)
                if f_lo * (_peri_many(mu_home, rm, vm, (mid * d)[None, :])[0] - want) < 0:
                    hi = mid
                else:
                    lo = mid
            cands.append(0.5 * (lo + hi) * d)
    out = []
    for vinf in cands:
        try:
            b = maneuver.single_impulse_hyperbolic_burn(body.mu, rr, vv, vinf, scan=19)
        except (ValueError, ZeroDivisionError):
            continue
        mag = float(np.linalg.norm(b["dv"]))
        if mag > cap:
            continue
        rb, vb = b["r_burn"], b["v_neg"] + b["dv"]
        ts = time_to_soi(body.mu, rb, vb, body.soi)
        if ts is None:
            continue
        rs, vs = astro.propagate(body.mu, rb, vb, ts)
        rmm, vmm = system.rel(body.name, ut_ref + b["dt"] + ts)
        tp = time_to_periapsis(mu_home, np.asarray(rmm, float) + rs, np.asarray(vmm, float) + vs)
        if not math.isfinite(tp):
            continue
        out.append({"ut": ut_ref + b["dt"], "r": b["r_burn"], "v": b["v_neg"], "dv": b["dv"],
                    "mag": mag, "vinf": vinf,
                    "total": (ut_ref + b["dt"] - ut0 + ts + tp) / DAY,
                    "coast": (ts + tp) / DAY})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vessel-id", required=True)
    ap.add_argument("--peri", default="60km", help="target Earth periapsis altitude, e.g. 60km")
    ap.add_argument("--port", type=int, default=8284)
    ap.add_argument("--instance", default=DEFAULT_INSTANCE)
    ap.add_argument("--days", type=float, default=10.0,
                    help="scan this many days of departure epochs; 0 = burn now")
    ap.add_argument("--step", type=float, default=0.5, help="epoch step, days")
    ap.add_argument("--budget", type=float, default=1e9, help="delta-v you actually have, m/s")
    ap.add_argument("--deadline", type=float, default=None,
                    help="days of consumables from NOW; the burn must get home inside this")
    ap.add_argument("--horizon", type=float, default=25.0)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--alarm", nargs="?", const="Return burn")
    a = ap.parse_args(argv)

    system = System(instance=a.instance)
    br = bridge_mod.Bridge(port=a.port)
    body, r0, v0, ut0 = br.state(system, vid=a.vessel_id)
    r0 = np.asarray(r0, float); v0 = np.asarray(v0, float)
    info = br.nodes(vid=a.vessel_id)
    name = info.get("vessel")
    if not info.get("nodes_available", True):
        print(f"  WARNING  {info.get('why')} -- live numbers for a non-active vessel are garbage")

    home = "Earth"
    home_body = system.body(home)
    el0 = astro.elements(body.mu, r0, v0)
    period = 2 * np.pi * np.sqrt(el0.sma ** 3 / body.mu)
    alt = float(a.peri.rstrip("km")) * 1000.0
    want = home_body.radius + alt
    hn = np.cross(r0, v0); hn = hn / np.linalg.norm(hn)

    print(f"RETURN  {name} [live, id {a.vessel_id[:8]}]  ({body.name} -> {home})")
    print(f"  current orbit: {(el0.sma*(1-el0.ecc)-body.radius)/1000:,.0f} x "
          f"{(el0.sma*(1+el0.ecc)-body.radius)/1000:,.0f} km, i {np.degrees(el0.inc):.2f} deg, "
          f"period {period/60:.1f} min")
    print(f"  target {home} periapsis {alt/1000:,.0f} km altitude (r {want/1000:,.0f} km)")
    print(f"  alignment now: h.v_moon = {alignment(system, hn, ut0, body.name):+.3f} "
          f"(0 = prograde throws v-inf the right way, +-1 = no prograde return exists)")

    # --- search: every epoch, every basin ---------------------------------
    dirs = _sphere()
    span = np.arange(0.0, max(a.days, 0.01) + 1e-9, a.step) if a.days > 0 else np.array([0.0])
    sols = []
    for w in span:
        sols += scan_epoch(system, body, home, r0, v0, ut0, ut0 + 60.0 + w * DAY, want,
                           dirs, cap=a.budget)
    if not sols:
        sys.exit(f"  no return within {a.budget:,.0f} m/s over {a.days:.0f} d -- raise --budget "
                 f"or --days (alignment now is {alignment(system, hn, ut0, body.name):+.3f}; "
                 f"a return needs it near 0)")

    print()
    print(f"{len(sols)} solutions.  what more delta-v buys:")
    print(f"    {'budget':>8}  {'soonest home':>13}  {'burn T+':>8} {'|dv|':>8}")
    caps = [c for c in (700, 800, 850, 900, 950, 1000, 1100, 1300, 1500, 1750, 2000)
            if c <= a.budget + 300]
    for cap in caps:
        f = [x for x in sols if x["mag"] <= cap]
        if not f:
            continue
        b = min(f, key=lambda z: z["total"])
        print(f"    {cap:8,.0f}  {b['total']:10.2f} d  {(b['ut']-ut0)/DAY:8.2f} {b['mag']:8.1f}")

    feasible = sols
    if a.deadline:
        feasible = [x for x in sols if x["total"] <= a.deadline]
        if not feasible:
            soonest = min(sols, key=lambda z: z["total"])
            sys.exit(f"\n  NOTHING ARRIVES BY T+{a.deadline:.2f} d WITHIN "
                     f"{a.budget:,.0f} m/s.\n  soonest is T+{soonest['total']:.2f} d "
                     f"for {soonest['mag']:,.1f} m/s.")
        guess = min(feasible, key=lambda z: z["mag"])      # cheapest that still makes it
        print()
        print(f"cheapest arrival by T+{a.deadline:.2f} d: {guess['mag']:,.1f} m/s, "
              f"home T+{guess['total']:.2f} d")
    else:
        guess = min(feasible, key=lambda z: z["mag"])
        print()
        print(f"cheapest return: {guess['mag']:,.1f} m/s, home T+{guess['total']:.2f} d")

    # The polish moves |dv| by tens of m/s, so the budget has to bind on the POLISHED
    # burn, not on the scan's estimate -- a 928 m/s candidate polished to 950 and would
    # have been quoted against a 947 m/s tank it does not fit.  Walk the ranked list and
    # keep the first one that still fits once it actually hits the target periapsis.
    def polish(c):
        dv = c["dv"].copy()

        def resid(d):
            rp, _, _ = earth_peri(system, body, c["r"], c["v"] + d, c["ut"], a.horizon, home)
            return 1e9 if rp is None else (rp - want)

        for _ in range(30):
            f = resid(dv)
            if abs(f) < 500.0:
                break
            J = np.zeros(3)
            for k in range(3):
                e = np.zeros(3); e[k] = 0.5
                J[k] = (resid(dv + e) - f) / 0.5
            if not np.any(J):
                break
            step = -f * J / (J @ J)
            if np.linalg.norm(step) > 40.0:
                step *= 40.0 / np.linalg.norm(step)
            dv = dv + step
        return dv

    # Near-duplicate candidates off the direction grid polish in opposite directions -- one
    # 928 m/s estimate landed at 952, its neighbour at 944 -- so trying only the top few
    # rejects a burn that fits.  Walk deeper before giving up.
    ranked = sorted(feasible, key=lambda z: z["mag"])
    chosen = None
    skipped = 0
    for c in ranked[:40]:
        dv = polish(c)
        mag = float(np.linalg.norm(dv))
        rp, _, _ = earth_peri(system, body, c["r"], c["v"] + dv, c["ut"], a.horizon, home)
        if rp is None or abs(rp - want) > 5000.0:
            continue
        if mag <= a.budget:
            chosen = (c, dv); break
        skipped = skipped + 1
    if chosen is None:
        sys.exit(f"  every candidate polishes past {a.budget:,.0f} m/s -- the scan's estimate "
                 f"fits but the flown burn does not.")
    guess, dv = chosen
    ut, r, v = guess["ut"], guess["r"], guess["v"]
    if skipped:
        print(f"    ({skipped} cheaper-looking candidates polished past the budget)")

    rp, ut_pe, traj = earth_peri(system, body, r, v + dv, ut, a.horizon, home)
    node = astro.to_node(r, v, dv)
    print()
    print(f"  BURN  {fmt_ut(ut)}   T+{(ut-ut0)/DAY:,.2f} d from now   "
          f"(h.v_moon {alignment(system, hn, ut, body.name):+.3f})")
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
