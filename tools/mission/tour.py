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


def dhms(seconds):
    """A tour is a conversation about periods, and decimal days hide the resonance."""
    if seconds is None or seconds == float("inf") or seconds != seconds:
        return "        -"
    t = int(round(seconds))
    return f"{t // 86400:3d}d {t % 86400 // 3600:02d}h {t % 3600 // 60:02d}m {t % 60:02d}s"


def moon_period(system, moon):
    """Orbital period of a moon about its parent -- the unit a tour's resonances are counted in."""
    b = system.body(moon) if isinstance(moon, str) else moon
    return 2 * math.pi * math.sqrt(b.a ** 3 / system.body(b.parent).mu)


def moon_normal(system, moon, ut):
    r, v = system.rel(moon, ut)
    return _unit(np.cross(np.asarray(r, float), np.asarray(v, float)))


def rel_inc(system, moon, r, v, ut):
    """Inclination of an orbit to the moon's instantaneous orbit plane, degrees."""
    n = float(_unit(np.cross(r, v)) @ moon_normal(system, moon, ut))
    return math.degrees(math.acos(max(-1.0, min(1.0, n))))


def handoff_vinf(system, body, moon, r, v, ut):
    """v-infinity this orbit would arrive with at `moon`, if the moon were at the crossing.

    The number that decides a MOON HANDOFF, and the one neither `pump` nor `resonance` looks at.
    A flyby cannot change v-infinity at the body doing the flying, so the only thing a Ganymede
    pass can do for a Callisto landing is reshape the orbit until the Callisto crossing is
    nearly tangential. `pump` walks straight past that point -- the deepest pump-down stops
    reaching the outer moon at all -- and `resonance` only repeats the encounter already had.

    Phasing is deliberately ignored: this answers "how fast would we meet it", not "would we".
    The moon's velocity is taken as circular in its own instantaneous plane at the crossing
    point, so a plane error shows up here as extra v-infinity, which is exactly how it is paid.

    Returns None when the orbit does not reach the moon's radius at all.
    """
    b = system.body(moon) if isinstance(moon, str) else moon
    el = astro.elements(body.mu, r, v)
    if el.ecc >= 1.0:
        return None
    rm = b.a
    # The test is NOT "does the conic cross the moon's orbit radius" -- it is "does it come
    # within the moon's SOI". Those differ exactly where the best handoffs live: the lowest
    # v-infinity is at a TANGENTIAL crossing, and a strict crossing test throws away every
    # orbit whose apsis sits just short of the moon's radius, which is the whole useful band.
    # Ganymede's SOI is 24,359 km on a 1,070,800 km orbit; Callisto's 37,703 on 1,883,800.
    if rm > el.apR:
        if rm - el.apR > b.soi:
            return None
        rm = el.apR                                   # evaluate at apoapsis, just inside
    elif rm < el.peR:
        if el.peR - rm > b.soi:
            return None
        rm = el.peR
    p_semi = el.sma * (1 - el.ecc ** 2)
    c = (p_semi / rm - 1.0) / el.ecc if el.ecc > 1e-12 else 0.0
    nu_x = math.acos(max(-1.0, min(1.0, c)))
    t0 = _anomaly_time(body.mu, el.sma, el.ecc, el.nu)
    best = None
    for nu in (nu_x, -nu_x):                      # outbound and inbound crossing
        dt = (_anomaly_time(body.mu, el.sma, el.ecc, nu) - t0) % el.period
        rr, vv = astro.propagate(body.mu, r, v, dt)
        rr = np.asarray(rr, float)
        vv = np.asarray(vv, float)
        n_hat = moon_normal(system, b.name, ut + dt)
        v_moon = math.sqrt(body.mu / b.a) * _unit(np.cross(n_hat, rr))
        vinf = float(np.linalg.norm(vv - v_moon))
        irel = rel_inc(system, b.name, rr, vv, ut + dt)
        rec = {"vinf": vinf, "dt": dt, "outbound": nu > 0, "irel": irel,
               # Cross-track at the moon's own radius, against its SOI: the number that says
               # whether the encounter can happen ANYWHERE in the moon's orbit or only near a
               # node. Degrees hide this -- 1.3 deg at Ganymede is already 23,500 km.
               "cross": b.a * math.sin(math.radians(irel)), "soi": b.soi}
        if best is None or vinf < best["vinf"]:
            best = rec
    return best


def landing_dv(moon, vinf, margin=1.05):
    """Deceleration to land from a hyperbolic arrival -- sqrt(v_inf^2 + v_esc^2), with margin.

    Capturing first and then descending costs the same to within a few m/s, so the square root
    is the honest price either way.
    """
    vesc = math.sqrt(2 * moon.mu / moon.radius)
    return margin * math.hypot(vinf, vesc)


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


def radius_crossings(mu, r_a, v_a, t_apo, radius, t_end, max_revs=400):
    """Every time this conic crosses `radius`, from t_apo out to t_end. Two per revolution."""
    el = astro.elements(mu, r_a, v_a)
    if el.ecc >= 1 or not (el.peR <= radius <= el.apR):
        return []
    p_semi = el.sma * (1 - el.ecc ** 2)
    c = (p_semi / radius - 1.0) / el.ecc if el.ecc > 1e-12 else 0.0
    if abs(c) > 1.0:
        return []
    nu = math.acos(max(-1.0, min(1.0, c)))
    t_pe = t_apo + el.period / 2.0
    out = []
    for sgn in (-1.0, 1.0):
        t0 = t_pe + _anomaly_time(mu, el.sma, el.ecc, sgn * nu)
        j = 0
        while j < max_revs:
            t = t0 + j * el.period
            if t > t_end:
                break
            if t > t_apo + 60.0:
                out.append(t)
            j += 1
    return sorted(out)


def phase_options(system, body, moon, r0, v0, ut0, *, max_revs=12, dv_cap=250.0,
                  steps=1200, keep=8, target_miss=0.0):
    """Apoapsis burns that put the MOON at one of our crossings, n revolutions from now.

    WAIT REVOLUTIONS, DO NOT FORCE THE NEXT PASS. `solve` scans only the first periapsis pass
    after apoapsis, so its cheapest answer is always a one-revolution answer -- and on a
    non-resonant orbit that is the expensive one. Measured on Perun 2 Bus B at Ganymede: forcing
    the next pass cost 335 m/s, while letting the orbit come back on a 4:27 resonance cost 175.8
    and gave a better plane and a deeper pump-down, for 143 extra days.

    The physics is just that changing the period by d shifts the j-th crossing by about j*d, so
    the further out you are willing to look, the smaller the burn that lands the moon on it. This
    scans the burn magnitude against every crossing inside the horizon and reports the frontier,
    which is a dv-versus-wait trade for the caller to pick from -- not a single number.
    """
    mu = body.mu
    el0 = astro.elements(mu, r0, v0)
    if el0.ecc >= 1:
        return []
    n0 = math.sqrt(mu / el0.sma ** 3)
    t_apo = ut0 - el0.mna / n0 + el0.period / 2
    while t_apo < ut0 + 60.0:
        t_apo += el0.period
    r_a, v_a = astro.propagate(mu, np.asarray(r0, float), np.asarray(v0, float), t_apo - ut0)
    r_a, v_a = np.asarray(r_a, float), np.asarray(v_a, float)
    va = float(np.linalg.norm(v_a))
    t_end = t_apo + max_revs * el0.period * 1.6 + moon_period(system, moon)

    def miss_at(dv, t):
        rr, _ = astro.propagate(mu, r_a, v_a * (1.0 + dv / va), t - t_apo)
        rm, _ = system.rel(moon.name, t)
        return float(np.linalg.norm(np.asarray(rr, float) - np.asarray(rm, float)))

    def score(dv, t):
        # PHASE TO THE FLYBY YOU WANT, not to the moon's centre. Phasing to a 1,390 km miss on
        # Perun 2 Bus B put Ganymede's centre on the nose -- a periapsis below the surface --
        # and every aim angle then cost 162-190 m/s just to pull the periapsis back out. A
        # multi-revolution phasing burn cannot be re-aimed cheaply afterwards either, because
        # any later burn is amplified by the revolutions still to come. So ask for the miss
        # you actually want up front; it costs the same.
        return abs(miss_at(dv, t) - target_miss)

    def best_cross(dv):
        v_new = v_a * (1.0 + dv / va)
        el = astro.elements(mu, r_a, v_new)
        if el.ecc >= 1 or el.apR >= body.soi:
            return None
        best = None
        for t in radius_crossings(mu, r_a, v_new, t_apo, moon.a, t_end):
            m = score(dv, t)
            if best is None or m < best[0]:
                best = (m, t)
        return best

    grid = [-dv_cap + 2 * dv_cap * i / steps for i in range(steps + 1)]
    curve = [(dv, best_cross(dv)) for dv in grid]
    found = []
    for i in range(1, len(curve) - 1):
        a_, b_, c_ = curve[i - 1][1], curve[i][1], curve[i + 1][1]
        if b_ is None:
            continue
        if (a_ is not None and a_[0] < b_[0]) or (c_ is not None and c_[0] < b_[0]):
            continue                                   # not a local minimum in dv
        step = 2 * dv_cap / steps
        cand = None
        for j in range(81):                            # refine on a 40x finer grid
            d2 = curve[i][0] - step + 2 * step * j / 80
            bc = best_cross(d2)
            if bc and (cand is None or bc[0] < cand[0]):
                cand = (bc[0], d2, bc[1])
        if not cand or cand[0] > moon.soi:
            continue
        _err, d2, t = cand
        m = miss_at(d2, t)
        if m > moon.soi:
            continue
        v2 = v_a * (1.0 + d2 / va)
        rr, vv = astro.propagate(mu, r_a, v2, t - t_apo)
        el2 = astro.elements(mu, r_a, v2)
        found.append({"dv": abs(d2), "dv_signed": d2, "t_burn": t_apo, "t_enc": t,
                      "miss": m, "wait": t - ut0, "revs": (t - t_apo) / el2.period,
                      "period": el2.period, "peR": el2.peR, "apR": el2.apR,
                      "r_e": np.asarray(rr, float), "v_e": np.asarray(vv, float),
                      "r_burn": r_a, "v_burn": v_a,
                      "irel": rel_inc(system, moon.name, rr, vv, t)})
    found.sort(key=lambda d: (round(d["t_enc"] / 3600.0), d["dv"]))
    uniq, seen = [], set()
    for f in found:
        k = round(f["t_enc"] / 7200.0)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    uniq.sort(key=lambda d: d["dv"])
    return uniq[:keep]


def rank_by_handoff(system, body, moon, opts, handoff, horizon_d=120.0):
    """Fly each phasing option's UNAIMED flyby and score it by what it hands off to `handoff`.

    THE PHASING BURN IS THE AIM. On a multi-revolution phasing there are many crossings to
    choose from, and each one arrives at the moon with a different B-vector -- so the aim is
    already decided by which crossing you pick. Re-aiming afterwards is the expensive way round:
    on Perun 2 Bus B every B-plane angle that reached Europa cost 162-190 m/s at 5, 12 and 45
    days of lead time alike, while simply choosing a different phasing option landed the natural
    flyby on a better handoff for 18 m/s -- and the flyby itself is free.
    """
    hand = system.body(handoff) if isinstance(handoff, str) else handoff
    out = []
    for o in opts:
        rb, vb = o["r_burn"], o["v_burn"]
        vb2 = np.asarray(vb, float) * (1.0 + o["dv_signed"] / float(np.linalg.norm(vb)))
        tr = patched.shoot(system, body.name, np.asarray(rb, float), vb2, o["t_burn"],
                           o["t_enc"] + horizon_d * DAY, watch=[moon.name])
        p_in = tr.enters(moon.name)
        if p_in is None:
            continue
        bp = astro.bplane(moon.mu, p_in.r0, p_in.v0)
        after = [q for q in tr.patches if q.body.name == body.name and q.ut0 > p_in.ut0]
        if not after:
            continue
        el = astro.elements(body.mu, after[0].r0, after[0].v0)
        rec = dict(o)
        rec.update({"flyby_alt": bp["peR"] - moon.radius, "flyby_vinf": bp["vinf"],
                    "turn_deg": math.degrees(astro.turn_angle(moon.mu, bp["vinf"], bp["peR"])),
                    "post_peR": el.peR, "post_apR": el.apR, "post_period": el.period})
        h = handoff_vinf(system, body, hand, after[0].r0, after[0].v0, after[0].ut0)
        if h:
            rec.update({"handoff": hand.name, "vinf_next": h["vinf"], "irel_next": h["irel"],
                        "cross_next": h["cross"], "soi_next": h["soi"],
                        "land_next": landing_dv(hand, h["vinf"])})
        out.append(rec)
    out.sort(key=lambda d: (d.get("vinf_next") is None, d.get("vinf_next", 9e9)))
    return out


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
            verbose=True, handoff=None, pers=None):
    """Fly each B-plane aim angle and READ the post-flyby orbit, rather than modelling it.

    The analytic scan above is only a pre-filter and must not be trusted for the answer: after
    the flyby the vessel is near Jupiter's escape speed at the moon's radius, so apoapsis is
    hypersensitive to the outgoing velocity. Evaluating the moon's own velocity an hour off the
    flyby periapsis moved the predicted apoapsis from 35 to 50 Gm -- the difference between a
    tour and leaving the system. So refine each aim and report what the trajectory actually does.
    """
    out = []
    t_moon = 2 * math.pi * math.sqrt(moon.a ** 3 / body.mu)
    hand = system.body(handoff) if handoff else None
    # DEPTH IS THE OTHER HALF OF THE AIM, and for a handoff it is usually the bigger half.
    # The B-plane angle chooses the DIRECTION v-infinity rotates; the periapsis chooses HOW
    # FAR. Measured on Perun 2 Bus A's free 1983-12-22 Callisto pass: the orbit that hands off
    # to Ganymede is 7 degrees of turn away, which is a 12,000 km altitude. Flown at the
    # habitual 300 km the pass turns 30 degrees, sails straight past it, and every angle in
    # the scan lands somewhere worse than doing nothing. Deeper is not better -- it is only
    # more, and a handoff wants the right amount.
    pers = list(pers) if pers else [per_want]
    if verbose:
        extra = (f" {'v_inf ' + hand.name[:4]:>11s} {'off ' + hand.name[:4]:>9s}"
                 if hand else "")
        depth = f" {'alt km':>9s}" if len(pers) > 1 else ""
        print(f"  {'psi':>5s}{depth} {'dV':>8s} {'peri Mm':>9s} {'apo Mm':>10s} {'period':>17s} "
              f"{'/moon':>8s} {'i_rel':>6s}{extra}  outcome")
        print(f"  (one {moon.name} period = {dhms(t_moon)}; * = still inside {moon.name}'s "
              f"{moon.soi / 1e3:,.0f} km SOI at any longitude)")
    for per_want, psi in ((p, a) for p in pers for a in angles):
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
        rec["cross_self"] = moon.a * math.sin(math.radians(rec["irel"]))
        rec["soi_self"] = moon.soi
        if hand is not None:
            h = handoff_vinf(system, body, hand, post[0].r0, post[0].v0, post[0].ut0)
            rec["handoff"] = hand.name
            rec["vinf_next"] = h["vinf"] if h else None
            rec["irel_next"] = h["irel"] if h else None
            rec["cross_next"] = h["cross"] if h else None
            rec["soi_next"] = h["soi"] if h else None
            rec["land_next"] = landing_dv(hand, h["vinf"]) if h else None
        out.append(rec)
        if verbose:
            ap = f"{rec['apR'] / 1e6:10,.0f}" if bound else "    ESCAPE"
            pe = dhms(rec["period"]) if bound else "                -"
            rr = f"{rec['resonance']:8.3f}" if bound else "       -"
            st = ("returns to " + moon.name) if rec["returns"] else (
                "bound, misses the moon" if bound else "LEAVES " + body.name.upper())
            extra = ""
            if hand is not None:
                # Print the plane next to the speed. A tour spends TWO currencies and the aim
                # that wins on v-infinity is regularly the one that wrecks the plane: on this
                # very scan psi 0 beat psi 345 by 87 m/s of v-infinity and cost 2.1 degrees,
                # which at Callisto's radius is 79,900 km of cross-track against a 37,703 km
                # SOI -- an encounter only near a node, if at all.
                extra = (f" {rec['vinf_next']:11,.0f} {rec['irel_next']:9.2f}"
                         if rec.get("vinf_next") else f" {'no cross':>11s} {'-':>9s}")
            depth = (f" {(rec['flyby_peR'] - moon.radius) / 1e3:9,.0f}" if len(pers) > 1
                     else "")
            plane = f"{rec['irel']:6.2f}{'*' if rec['cross_self'] <= rec['soi_self'] else ' '}"
            print(f"  {psi:5.0f}{depth} {rec['mag']:8.1f} {rec['peR'] / 1e6:9,.0f} {ap} {pe} {rr} "
                  f"{plane}{extra}  {st}")
    return out


def usable_aims(flown, mode="pump"):
    """Which flown aims are candidates at all, which depends on what the aim is FOR.

    `pump` and `resonance` need the flyby to hand back an orbit that meets the same moon again.
    A HANDOFF does not: its whole purpose is to leave for a different moon, and insisting on a
    return would throw away the answer. It needs the post-flyby orbit to reach the next moon.
    """
    if str(mode).startswith("handoff"):
        return [a for a in flown if a["bound"] and a.get("vinf_next")]
    return [a for a in flown if a["bound"] and a["returns"]]


def pick_aim(scan, mode="pump", moon_period=None, drift_tol=0.3 * DAY):
    """Choose a B-plane aim angle from the scan.

    `pump` takes the deepest pump-down that still returns to the moon. `resonance` takes the
    SHORTEST period whose return drifts less than `drift_tol` against the moon, which is what
    makes the following encounter nearly free; it falls back to `pump` when none qualifies.
    `handoff` takes the lowest v-infinity at the NEXT moon, which is the only one of the three
    that can make a landing on that moon affordable -- see `handoff_vinf`.
    """
    usable = usable_aims(scan, mode)
    if not usable:
        return None
    if str(mode).startswith("handoff"):
        # TWO currencies, and the cheapest v-infinity is regularly the one that spends the
        # other. Perun 2 Bus A's plane went 0.07 -> 8.56 -> 13.26 deg across three aims that
        # were each defensible on their own metric, and at 13.26 deg the orbit missed
        # Callisto's plane by 432,000 km against a 37,703 km SOI -- the handoff it had spent
        # 800 m/s working toward was simply gone. So the plane is a GATE here, not a
        # tie-break: prefer the aims that leave the next moon reachable anywhere in its
        # orbit, and only give that up when nothing does.
        reachable = [a for a in usable
                     if a.get("cross_next") is not None and a["cross_next"] <= a["soi_next"]]
        pool = reachable or usable
        lo = min(a["vinf_next"] for a in pool)
        near = [a for a in pool if a["vinf_next"] <= lo * 1.02]
        best = min(near, key=lambda a: (not a["returns"],
                                        a.get("irel_next") if a.get("irel_next") is not None
                                        else a["irel"]))
        best["picked_by"] = (f"handoff:{best.get('handoff', '?')}" if reachable else
                             f"handoff:{best.get('handoff', '?')} (NO aim keeps it in-plane -- "
                             f"this one needs a node crossing)")
        return best
    if mode == "resonance" and not moon_period:
        mode = "pump (no moon period given)"
    if mode == "resonance":
        # Score the ratio error as DRIFT IN TIME, not as a fraction of the ratio. A 70:1 return
        # that is 0.003 periods off drifts less per revolution than a 6:1 that is 0.03 off, so a
        # fractional tolerance makes long useless resonances look better than short good ones --
        # measured on Perun 2 Bus A, it picked a 70:1 at 501 days over a near-6:1 at 42 days and
        # threw the whole pump-down away. What the tour wants is the SHORTEST period whose drift
        # is small enough that the next phasing burn is cheap.
        cand = []
        for a in usable:
            k = round(a["resonance"])
            if k < 1:
                continue
            drift = abs(a["resonance"] - k) * moon_period
            if drift <= drift_tol:
                cand.append((drift, a))
        if cand:
            lo = min(a["period"] for _d, a in cand)
            near = [(d, a) for d, a in cand if a["period"] <= lo * 1.05]
            best = min(near, key=lambda da: (da[1]["irel"], da[0]))[1]
            best["picked_by"] = "resonance"
            return best
        # No integer ratio is reachable at this v_inf and periapsis within the drift tolerance.
        # Say so rather than silently reporting a pump aim as resonant.
        mode = "pump (no usable resonance)"
    # THE PLANE IS A GATE HERE TOO, not a tie-break on a 2 percent window.
    # Pump-down is nearly flat near its minimum and the inclination to the moon's plane is not,
    # so the strict apoapsis minimum keeps buying fractions of a percent of apoapsis with whole
    # degrees of plane. Measured on Perun 2 Bus B at Ganymede: psi 330 pumps to 1,556 Mm at
    # 2.62 deg = 48,950 km of cross-track against a 24,359 km SOI (encounters only near a node),
    # psi 315 pumps to 1,595 Mm -- 2.5 percent worse, so just outside the old window -- at
    # 0.48 deg = 8,970 km, reachable anywhere, for 1.7 m/s more. The 2 percent rule was tuned on
    # a case where the plane cost 1.27 deg; it is not a general answer. Cross-track against the
    # SOI is, because that is the number that decides whether the next encounter exists.
    reachable = [a for a in usable
                 if a.get("cross_self") is not None and a["cross_self"] <= a["soi_self"]]
    pool = reachable or usable
    lo = min(a["apR"] for a in pool)
    near = [a for a in pool if a["apR"] <= lo * 1.02]
    chosen = min(near, key=lambda a: a["irel"])
    chosen["picked_by"] = (mode if mode != "pump" else "pump") + (
        "" if reachable else " (NO aim keeps it in-plane -- this one needs a node crossing)")
    return chosen


def free_dv(moon, vinf, per):
    """Velocity change a single flyby at that periapsis imposes -- the whole point of the tour."""
    turn = astro.turn_angle(moon.mu, vinf, per)
    return 2 * vinf * math.sin(turn / 2), math.degrees(turn)
