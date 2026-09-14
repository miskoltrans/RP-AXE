"""The apoapsis burn that turns the next periapsis into a REAL moon encounter.

After a capture the orbit has the right periapsis RADIUS and nothing else: the moon is
somewhere else entirely when the vessel crosses its orbit. Raising periapsis to the moon's
radius is the easy half; the burn has to be timed and aimed so the crossing happens where
the moon is, and that is a two-parameter problem (when to burn, how much) with the encounter
epoch as the free variable.

The seed is EXACT in two-body terms. For a candidate encounter epoch t_k:

  * the new orbit plane is span(burn point, moon at t_k) -- a burn cannot leave the burn
    point, so the plane is forced once the encounter epoch is chosen;
  * the apsidal line stays along the burn point, which is why the capture periapsis has to
    have been aimed INTO the moons' plane (see the capture-apsides-in-moon-plane rule) --
    if it was not, no burn here can make the orbit coplanar and v_inf never comes down;
  * the periapsis radius is solved so the conic crosses the moon's radius exactly at the
    moon's direction, and the burn time is iterated until the arrival lands on t_k.

The epoch is then scanned continuously over a window around the natural periapsis pass, the
lowest-v_inf seeds are least-squares corrected on the FLOWN trajectory through the moon's
SOI, and what comes out is measured, not assumed.

Written for Saturnalija (saturn_tour.py), generalised here for Perun 2 at Jupiter.
"""
import math

import numpy as np

import astro
import maneuver
import patched
from rss_ephem import DAY, fmt_ut


def _unit(x):
    x = np.asarray(x, float)
    return x / np.linalg.norm(x)


def _anomaly_time(mu, a, e, nu):
    """Time from periapsis to true anomaly nu, elliptic."""
    E = 2 * math.atan2(math.sqrt(1 - e) * math.sin(nu / 2), math.sqrt(1 + e) * math.cos(nu / 2))
    return (E - e * math.sin(E)) / math.sqrt(mu / a ** 3)


def moon_normal(system, moon, ut):
    r, v = system.rel(moon, ut)
    return _unit(np.cross(np.asarray(r, float), np.asarray(v, float)))


def rel_inc(system, moon, r, v, ut):
    """Inclination of an orbit to the moon's instantaneous orbit plane, degrees."""
    n = float(_unit(np.cross(r, v)) @ moon_normal(system, moon, ut))
    return math.degrees(math.acos(max(-1.0, min(1.0, n))))


def seed_for(system, body, moon, r0, v0, ut0, t_apo, t_k, iters=8):
    """Exact two-body burn near apoapsis whose orbit reaches the moon's position at t_k."""
    mu = body.mu
    Q, vQ_moon = (np.asarray(x, float) for x in system.rel(moon.name, t_k))
    rq, q_hat = float(np.linalg.norm(Q)), _unit(Q)
    t_b = t_apo
    v_new = None
    for _ in range(iters):
        P, vP = astro.propagate(mu, r0, v0, t_b - ut0)
        P = np.asarray(P, float)
        vP = np.asarray(vP, float)
        ra, p_hat = float(np.linalg.norm(P)), _unit(P)
        # apsides along P, so the moon's true anomaly follows from the angle between them
        nu_q = math.pi - math.acos(max(-1.0, min(1.0, float(p_hat @ q_hat))))
        cq = math.cos(nu_q)

        def f(rp):
            e = (ra - rp) / (ra + rp)
            return rp * (1 + e) / (1 + e * cq) - rq

        lo, hi = 0.02 * rq, rq
        if f(lo) > 0 or f(hi) < 0:
            return None
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
        rp = 0.5 * (lo + hi)
        a_new = 0.5 * (ra + rp)
        e = (ra - rp) / (ra + rp)
        n_hat = _unit(np.cross(p_hat, q_hat))
        v_dir = _unit(np.cross(n_hat, p_hat))
        if float(v_dir @ vP) < 0:                       # keep the existing sense of motion
            n_hat, v_dir = -n_hat, -v_dir
        v_new = math.sqrt(mu * (2 / ra - 1 / a_new)) * v_dir
        e_hat = -p_hat
        nu_of_q = math.atan2(float(np.cross(e_hat, q_hat) @ n_hat), float(e_hat @ q_hat))
        T = 2 * math.pi * math.sqrt(a_new ** 3 / mu)
        leg = _anomaly_time(mu, a_new, e, abs(nu_of_q))
        dt = T / 2 + (leg if nu_of_q > 0 else -leg)
        t_new = t_k - dt
        if abs(t_new - t_b) < 1.0:
            t_b = t_new
            break
        t_b = t_new
    P, vP = astro.propagate(mu, r0, v0, t_b - ut0)
    P = np.asarray(P, float)
    vP = np.asarray(vP, float)
    r_arr, v_arr = astro.propagate(mu, P, v_new, t_k - t_b)
    miss = float(np.linalg.norm(np.asarray(r_arr, float) - Q))
    vinf = float(np.linalg.norm(np.asarray(v_arr, float) - vQ_moon))
    return {"t_k": t_k, "t_b": t_b, "P": P, "vP": vP, "dv": v_new - vP,
            "mag": float(np.linalg.norm(v_new - vP)), "rp": rp, "vinf": vinf, "miss": miss,
            "irel": rel_inc(system, moon.name, P, v_new, t_b),
            "branch": "outbound" if nu_of_q > 0 else "inbound"}


def solve(system, body, moon, r0, v0, ut0, per_want, *, before=30.0, after=45.0,
          step=0.5, refine_n=6, max_dv=400.0, verbose=True):
    """Scan encounter epochs, refine the best seeds on the flown trajectory, return them sorted."""
    mu = body.mu
    el0 = astro.elements(mu, r0, v0)
    n0 = math.sqrt(mu / el0.sma ** 3)
    t_apo = ut0 - el0.mna / n0 + el0.period / 2
    while t_apo < ut0:
        t_apo += el0.period
    if verbose:
        print(f"  current orbit {el0.peR / 1e6:,.0f} x {el0.apR / 1e6:,.0f} Mm, "
              f"i {math.degrees(el0.inc):.3f}, period {el0.period / DAY:,.1f} d; "
              f"apoapsis {fmt_ut(t_apo)} (T+{(t_apo - ut0) / DAY:.1f} d)")

    # centre the scan on the periapsis pass of an orbit already raised to the moon
    t_p1 = t_apo + 0.5 * 2 * math.pi * math.sqrt((0.5 * (el0.apR + moon.a)) ** 3 / mu)
    seeds = []
    n_steps = int((before + after) / step) + 1
    for i in range(n_steps):
        sd = seed_for(system, body, moon, r0, v0, ut0, t_apo, t_p1 - before * DAY + i * step * DAY)
        if sd is not None and sd["miss"] < 1e6:
            seeds.append(sd)
    if not seeds:
        return t_apo, [], []
    seeds.sort(key=lambda d: d["vinf"])
    if verbose:
        print(f"\n  SEED SCAN  {fmt_ut(t_p1 - before * DAY)[:10]} .. {fmt_ut(t_p1 + after * DAY)[:10]}, "
              f"{len(seeds)} elliptic seeds (exact two-body)")
        print(f"  {'encounter':>16s} {'burn-apo':>9s} {'dV':>7s} {'v_inf':>7s} "
              f"{'i_rel':>6s} {'new peri':>9s} {'branch':>9s}")
        for sd in seeds[:8]:
            print(f"  {fmt_ut(sd['t_k'])[:16]:>16s} {(sd['t_b'] - t_apo) / DAY:+9.1f} {sd['mag']:7.1f} "
                  f"{sd['vinf']:7.0f} {sd['irel']:6.2f} {sd['rp'] / 1e6:8,.0f}M {sd['branch']:>9s}")

    sols = []
    if verbose:
        print(f"\n  REFINE  (converged shots through {moon.name}'s SOI, periapsis "
              f"{per_want / 1e3:,.0f} km = {(per_want - moon.radius) / 1e3:,.0f} km altitude)")
        print(f"  {'encounter':>16s} {'burn-apo':>9s} {'dV total':>9s} {'v_inf':>7s} "
              f"{'i_rel':>6s} {'flyby peri':>11s}")
    for sd in seeds[:refine_n]:
        ut_want = sd["t_k"] - moon.soi / max(sd["vinf"], 1.0)
        try:
            res = maneuver.refine(system, body.name, sd["P"], sd["vP"] + sd["dv"], sd["t_b"],
                                  moon.name, sd["t_k"] + 40 * DAY, per_want, ut_want=ut_want,
                                  watch=[moon.name], max_dv=max_dv, max_nfev=120)
        except Exception as exc:                                    # noqa: BLE001 - report, don't hide
            if verbose:
                print(f"  {fmt_ut(sd['t_k'])[:16]:>16s}  failed: {exc}")
            continue
        rep = res["report"]
        if not rep.get("captured"):
            if verbose:
                print(f"  {fmt_ut(sd['t_k'])[:16]:>16s}  no encounter "
                      f"(miss {rep.get('ca_dist', 0) / 1e6:,.1f} Mm)")
            continue
        dv = sd["dv"] + res["dv"]
        ok = abs(rep["peR"] - per_want) / per_want < 0.05
        sols.append({"t_b": sd["t_b"], "off": (sd["t_b"] - t_apo) / DAY, "t_k": sd["t_k"],
                     "r_b": sd["P"], "v_b": sd["vP"], "dv": dv,
                     "mag": float(np.linalg.norm(dv)), "vinf": rep["vinf"],
                     "irel": rel_inc(system, moon.name, sd["P"], sd["vP"] + dv, sd["t_b"]),
                     "peR": rep["peR"], "soi_ut": rep["soi_ut"], "traj": res["traj"], "ok": ok})
        if verbose:
            print(f"  {fmt_ut(sd['t_k'])[:16]:>16s} {sols[-1]['off']:+9.1f} {sols[-1]['mag']:9.1f} "
                  f"{rep['vinf']:7.0f} {sols[-1]['irel']:6.2f} {rep['peR'] / 1e3:10,.0f} km"
                  + ("" if ok else "   (periapsis off)"))
    return t_apo, seeds, sols


def aim_scan(system, body, moon, traj, per_want, n=180):
    """Post-flyby orbit as a function of the B-plane aim angle at the encounter.

    THE flight rule this encodes: across the full range of aim angles a flyby costs the same
    and the outcome swings from ejection out of the planet's SOI to a halved period. The
    default aim `maneuver.refine` uses just preserves the existing miss direction, so it
    picks one of those outcomes at random -- measured on Perun 2 Bus A, it pumped the orbit
    UP to a 50.8 Gm apoapsis against Jupiter's 48.2 Gm SOI, i.e. straight out of the system.

    Gravity bends the velocity TOWARD the body, hence away from B:
        v_out = vinf * (cos(turn) * s_hat - sin(turn) * b_hat)
    """
    p_in = traj.enters(moon.name)
    if p_in is None:
        return None, []
    bp = astro.bplane(moon.mu, p_in.r0, p_in.v0)
    s_hat, t_hat, r_hat = bp["s_hat"], bp["t_hat"], bp["r_hat"]
    vinf = bp["vinf"]
    turn = astro.turn_angle(moon.mu, vinf, per_want)
    t_enc = p_in.ut0 + 3600.0
    rm, vm = (np.asarray(x, float) for x in system.rel(moon.name, t_enc))
    t_moon = 2 * math.pi * math.sqrt(moon.a ** 3 / body.mu)
    psi_now = math.degrees(math.atan2(bp["B_R"], bp["B_T"])) % 360.0
    out = []
    for i in range(n):
        psi = 360.0 * i / n
        b_hat = math.cos(math.radians(psi)) * t_hat + math.sin(math.radians(psi)) * r_hat
        v_out = vinf * (math.cos(turn) * s_hat - math.sin(turn) * b_hat)
        vs = vm + v_out
        el = astro.elements(body.mu, rm, vs)
        bound = el.ecc < 1.0 and el.apR < body.soi
        out.append({"psi": psi, "peR": el.peR, "apR": el.apR if el.ecc < 1 else float("inf"),
                    "ecc": el.ecc, "bound": bound,
                    "period": el.period if el.ecc < 1 else float("inf"),
                    "resonance": (el.period / t_moon) if el.ecc < 1 else float("inf"),
                    "irel": rel_inc(system, moon.name, rm, vs, t_enc),
                    "returns": bool(el.ecc < 1 and el.peR <= moon.a <= el.apR)})
    return {"vinf": vinf, "turn_deg": math.degrees(turn), "psi_now": psi_now,
            "moon_period": t_moon, "t_enc": t_enc}, out


def aim_fly(system, body, moon, r_b, v_b, t_b, dv0, per_want, t_ca, angles, max_dv=60.0,
            verbose=True):
    """Fly each B-plane aim angle and READ the post-flyby orbit, rather than modelling it.

    The analytic scan above is only a pre-filter and must not be trusted for the answer: after
    the flyby the vessel is near Jupiter's escape speed at the moon's radius, so apoapsis is
    hypersensitive to the outgoing velocity. Evaluating the moon's own velocity an hour off the
    flyby periapsis moved the predicted apoapsis from 35 to 50 Gm -- the difference between a
    tour and leaving the system. So refine each aim and report what the trajectory actually does.
    """
    out = []
    t_moon = 2 * math.pi * math.sqrt(moon.a ** 3 / body.mu)
    if verbose:
        print(f"  {'psi':>5s} {'dV':>8s} {'peri Mm':>9s} {'apo Mm':>10s} {'period d':>9s} "
              f"{'/moon':>8s} {'i_rel':>6s}  outcome")
    for psi in angles:
        b_dir = np.array([math.cos(math.radians(psi)), math.sin(math.radians(psi))])
        try:
            res = maneuver.refine(system, body.name, r_b, v_b + dv0, t_b, moon.name,
                                  t_ca + 60 * DAY, per_want, b_dir=b_dir, ut_want=t_ca,
                                  watch=[moon.name], max_dv=max_dv, max_nfev=80)
        except Exception:                                           # noqa: BLE001
            continue
        rep = res["report"]
        if not rep.get("captured") or abs(rep["peR"] - per_want) / per_want > 0.08:
            continue
        traj = res["traj"]
        p_in = traj.enters(moon.name)
        post = [q for q in traj.patches if q.body.name == body.name and q.ut0 > p_in.ut0]
        if not post:
            continue
        el = astro.elements(body.mu, post[0].r0, post[0].v0)
        dv = dv0 + res["dv"]
        bound = el.ecc < 1.0 and el.apR < body.soi
        rec = {"psi": psi, "dv": dv, "mag": float(np.linalg.norm(dv)),
               "peR": el.peR, "apR": el.apR if el.ecc < 1 else float("inf"), "ecc": el.ecc,
               "bound": bound, "period": el.period if el.ecc < 1 else float("inf"),
               "resonance": (el.period / t_moon) if el.ecc < 1 else float("inf"),
               "irel": rel_inc(system, moon.name, post[0].r0, post[0].v0, post[0].ut0),
               "returns": bool(el.ecc < 1 and el.peR <= moon.a <= el.apR),
               "vinf": rep["vinf"], "flyby_peR": rep["peR"], "traj": traj, "res": res}
        out.append(rec)
        if verbose:
            ap = f"{rec['apR'] / 1e6:10,.0f}" if bound else "    ESCAPE"
            pe = f"{rec['period'] / DAY:9.2f}" if bound else "        -"
            rr = f"{rec['resonance']:8.3f}" if bound else "       -"
            st = ("returns to " + moon.name) if rec["returns"] else (
                "bound, misses the moon" if bound else "LEAVES " + body.name.upper())
            print(f"  {psi:5.0f} {rec['mag']:8.1f} {rec['peR'] / 1e6:9,.0f} {ap} {pe} {rr} "
                  f"{rec['irel']:6.2f}  {st}")
    return out


def pick_aim(scan, mode="pump"):
    """Choose a B-plane aim angle from the scan. `pump` = the deepest pump-down that still
    returns to the moon; `resonance` = the nearest near-integer moon-period ratio below it."""
    usable = [a for a in scan if a["bound"] and a["returns"]]
    if not usable:
        return None
    if mode == "resonance":
        best = None
        for a in usable:
            k = round(a["resonance"])
            if k < 1:
                continue
            if abs(a["resonance"] - k) < 0.02 and (best is None or a["period"] < best["period"]):
                best = a
        if best is not None:
            best["picked_by"] = "resonance"
            return best
        # No integer ratio is reachable at this v_inf and periapsis -- the achievable ratios
        # simply do not span one. Say so rather than silently reporting a pump aim as resonant.
        mode = "pump (no integer resonance reachable)"
    # Pump-down is nearly flat near its minimum, and the inclination to the moon's plane is
    # not: on Perun 2 Bus B the strict apoapsis minimum bought 0.07 % of apoapsis for 1.27 deg
    # of relative inclination, which at Ganymede's radius is 28,000 km of cross-track against a
    # 24,359 km SOI -- it would have cost the NEXT encounter. Break the near-tie on inclination.
    lo = min(a["apR"] for a in usable)
    near = [a for a in usable if a["apR"] <= lo * 1.02]
    chosen = min(near, key=lambda a: a["irel"])
    chosen["picked_by"] = mode if mode != "pump" else "pump"
    return chosen


def free_dv(moon, vinf, per):
    """Velocity change a single flyby at that periapsis imposes -- the whole point of the tour."""
    turn = astro.turn_angle(moon.mu, vinf, per)
    return 2 * vinf * math.sin(turn / 2), math.degrees(turn)
