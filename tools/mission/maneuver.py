"""The three burns this project keeps needing: ejection, midcourse, flyby.

Each solver produces an analytic first guess and then a NUMBER that was measured
by flying the result (patched.shoot), not asserted. A guess that matches its
v-infinity target to 0.001 m/s and still misses the planet is the failure mode
this module exists to make impossible to ship.

Sources, so the arithmetic is checkable rather than folklore:
  * ejection geometry  = MechJebLib.FunctionImpls.RealSingleImpulseHyperbolicBurn
  * v-inf at the SOI   = MechJeb2 TransferCalculator.OptimizeEjection
  * midcourse search   = OrbitalManeuverCalculator.DeltaVAndTimeForCheapestCourseCorrection
"""
import math

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

import astro
import patched
from lambert import lambert

DAY = 86400.0


# ---------------------------------------------------------------------------
# ejection: put a given v-infinity vector on the board for the least dV
# ---------------------------------------------------------------------------
def _single_impulse(mu, r0, v0, vinf, rot):
    """One evaluation of MechJeb's hyperbolic-burn geometry at rotation `rot` (radians).

    `rot` swings the burn point around the v-infinity axis; the caller minimises
    |dV| over it. Everything else is closed form.
    """
    r0 = np.asarray(r0, float)
    v0 = np.asarray(v0, float)
    h0 = np.cross(r0, v0)
    r0m = float(np.linalg.norm(r0))
    sma = 1.0 / (2.0 / r0m - float(v0 @ v0) / mu)
    vinf = np.asarray(vinf, float)
    vinf_m2 = float(vinf @ vinf)
    sma_h = -mu / vinf_m2
    h0hat = h0 / np.linalg.norm(h0)
    e_vec = np.cross(v0, h0) / mu - r0 / r0m
    ecc = float(np.linalg.norm(e_vec))
    if ecc >= 1.0:
        raise ValueError("the parking orbit is already hyperbolic")
    p0 = sma * (1.0 - ecc * ecc)
    rp0hat = e_vec / ecc if ecc > 1e-14 else r0 / r0m
    rp0aa = np.cross(h0, rp0hat)
    rp0aa /= np.linalg.norm(rp0aa)
    vhat = vinf / math.sqrt(vinf_m2)

    dot_hv = float(h0hat @ vhat)
    if abs(abs(dot_hv) - 1.0) > 1e-15:
        v6 = np.cross(vhat, np.cross(h0hat, vhat))
    else:
        v6 = np.cross(rp0hat, vhat)
    v6 = v6 / np.linalg.norm(v6)

    def rotate(vec, axis, ang):
        axis = axis / np.linalg.norm(axis)
        return (vec * math.cos(ang) + np.cross(axis, vec) * math.sin(ang)
                + axis * float(axis @ vec) * (1 - math.cos(ang)))

    if abs(dot_hv) > 2.22044604925031e-16:
        v6 = rotate(v6, vhat, -rot)
        v7 = math.copysign(1.0, dot_hv) * np.cross(h0hat, v6)
        v7 /= np.linalg.norm(v7)
    else:
        v7 = np.cross(vhat, v6)
        v7 /= np.linalg.norm(v7)
        v7 = rotate(v7, h0hat, -rot)

    clamp = lambda x: max(-1.0, min(1.0, x))
    nu_burn = math.copysign(1.0, float(h0hat @ np.cross(rp0hat, v7))) * math.acos(clamp(float(rp0hat @ v7)))
    rb = p0 / (1.0 + ecc * math.cos(nu_burn))
    r_burn = rb * v7

    k = -sma_h / rb
    ang = math.acos(clamp(float(v7 @ vhat)))
    s, c = math.sin(ang), math.cos(ang)
    s2 = s * s
    ecc_h = max(math.sqrt(s2 + 2 * k * k + 2 * k * (1 - c) + s * math.sqrt(s2 + 4 * k * (1 - c)))
                / (math.sqrt(2.0) * k), 1.0 + 2.22e-16)
    p_h = sma_h * (1.0 - ecc_h * ecc_h)
    nu_h = math.acos(clamp(-c / ecc_h + math.sqrt(ecc_h * ecc_h - 1) / ecc_h * s))
    turn = 2.0 * math.asin(1.0 / ecc_h)
    v9 = math.cos(turn) * vhat + math.sin(turn) * np.cross(vhat, v6)
    v10 = v9 - vhat
    v10 /= np.linalg.norm(v10)
    v11 = v9 + vhat
    v11 /= np.linalg.norm(v11)
    v_pos = math.sqrt(mu / p_h) * (-math.sin(nu_h) * v10 + (ecc_h + math.cos(nu_h)) * v11)
    v_neg = math.sqrt(mu / p0) * (-math.sin(nu_burn) * rp0hat + (ecc + math.cos(nu_burn)) * rp0aa)

    r0hat = r0 / r0m
    nu_ref = math.copysign(1.0, float(h0hat @ np.cross(rp0hat, r0hat))) * math.acos(clamp(float(rp0hat @ r0hat)))
    n = math.sqrt(mu / sma ** 3)
    ea = lambda nu: math.atan2(math.sqrt(1 - ecc * ecc) * math.sin(nu), ecc + math.cos(nu))
    m_ref = ea(nu_ref) - ecc * math.sin(ea(nu_ref))
    m_burn = ea(nu_burn) - ecc * math.sin(ea(nu_burn))
    dt = (m_burn - m_ref) / n
    if dt < 0:
        dt += 2 * math.pi / n
    return {"v_neg": v_neg, "v_pos": v_pos, "r_burn": r_burn, "dt": dt,
            "dv": v_pos - v_neg, "ecc_h": ecc_h, "rot": rot}


def single_impulse_hyperbolic_burn(mu, r0, v0, vinf, scan=181):
    """Cheapest single burn out of an elliptical parking orbit onto `vinf`.

    MechJeb brackets its rotation parameter over [-30, +30] RADIANS and hands
    that to Brent, so which local minimum it lands in depends on where Brent
    happens to step. This scans a full turn first and refines the best basin,
    which is the same geometry with the global answer.
    """
    best = None
    for rot in np.linspace(-math.pi, math.pi, scan):
        try:
            s = _single_impulse(mu, r0, v0, vinf, float(rot))
        except (ValueError, ZeroDivisionError):
            continue
        m = float(np.linalg.norm(s["dv"]))
        if best is None or m < best[0]:
            best = (m, float(rot))
    if best is None:
        raise ValueError("no ejection geometry found")
    span = 2 * math.pi / (scan - 1)
    res = minimize_scalar(
        lambda x: float(np.linalg.norm(_single_impulse(mu, r0, v0, vinf, float(x))["dv"])),
        bracket=None, bounds=(best[1] - span, best[1] + span), method="bounded",
        options={"xatol": 1e-10})
    return _single_impulse(mu, r0, v0, vinf, float(res.x))


def vinf_for_transfer(system, dep_body, target, t_dep, t_arr, refine=True):
    """The v-infinity vector a departure needs, corrected for the SOI radius.

    The naive answer is v_transfer - v_planet with both taken at the planet's
    centre. The burn happens ~6,600 km out and the vehicle leaves the SOI a
    million km away days later, so MechJeb re-reads the relative velocity where
    the heliocentric conic actually crosses the SOI and converts THAT to a
    v-infinity. Skipping the correction is worth a few hundred km/s^2 of C3 and
    a wholly different arrival.
    """
    dep_body = system.body(dep_body)
    target = system.body(target)
    centre = system.common_parent(dep_body.name, target.name)
    mu_c = system.body(centre).mu
    r1, v1b = system.state(dep_body.name, t_dep, centre)
    r2, _ = system.state(target.name, t_arr, centre)
    vt1, vt2 = lambert(mu_c, np.array(r1), np.array(r2), t_arr - t_dep)
    vinf = np.asarray(vt1) - np.asarray(v1b)
    raw = vinf.copy()
    if not refine or not math.isfinite(dep_body.soi):
        return vinf, raw, None
    # where does that heliocentric conic leave the departure body's SOI?
    def sep(t):
        r, _ = astro.propagate(mu_c, np.array(r1), np.asarray(vt1), t - t_dep)
        rb, _ = system.state(dep_body.name, t, centre)
        return float(np.linalg.norm(r - np.asarray(rb))) - dep_body.soi
    hi = min(t_arr, t_dep + 90 * DAY)
    if sep(hi) < 0:
        return vinf, raw, None
    try:
        t_soi = astro.brent(sep, t_dep + 1.0, hi, tol=1e-3)
    except ValueError:
        return vinf, raw, None
    r, v = astro.propagate(mu_c, np.array(r1), np.asarray(vt1), t_soi - t_dep)
    rb, vb = system.state(dep_body.name, t_soi, centre)
    v_rel = np.asarray(v) - np.asarray(vb)
    speed = float(np.linalg.norm(v_rel))
    corrected = astro.vinf_at_radius(dep_body.mu, speed, dep_body.soi)
    vinf = v_rel / speed * corrected
    return vinf, raw, t_soi


# ---------------------------------------------------------------------------
# differential correction: aim the shot, do not just trust it
# ---------------------------------------------------------------------------
def _bplane_residual(system, traj, target, t_end, want_b, want_ut):
    """A residual that stays continuous whether or not the SOI is reached.

    Inside the SOI it is the true B-plane miss; outside, the same quantity built
    from the closest-approach relative state. That continuity is what lets one
    least-squares pass drag a trajectory from "misses by 300 Gm" to "2.6 Rj".
    """
    target = system.body(target)
    scale = target.soi if math.isfinite(target.soi) else 1e9
    p = traj.enters(target.name)
    if p is not None:
        bp = astro.bplane(target.mu, p.r0, p.v0)
        ut = p.ut0
        if bp is None:                      # captured (bound) -- use periapsis directly
            el = p.elements()
            return np.array([(el.peR - want_b[0]) / scale, 0.0, (ut - want_ut) / DAY])
        bt, br = bp["B_T"], bp["B_R"]
    else:
        ut, d, _ = patched.closest_approach(system, traj, target, traj.patches[0].ut0, t_end)
        b, r, v = traj.state(ut)
        centre = system.common_parent(b.name, target.name)
        rs, vs = np.asarray(r), np.asarray(v)
        if b.name != centre:
            rb, vb = system.state(b.name, ut, centre)
            rs, vs = rs + np.asarray(rb), vs + np.asarray(vb)
        rt, vt = system.state(target.name, ut, centre)
        dr, dv = rs - np.asarray(rt), vs - np.asarray(vt)
        s_hat = dv / np.linalg.norm(dv)
        b_vec = dr - float(dr @ s_hat) * s_hat
        k = np.array([0.0, 0.0, 1.0])
        t_hat = np.cross(s_hat, k)
        t_hat /= np.linalg.norm(t_hat)
        r_hat = np.cross(s_hat, t_hat)
        bt, br = float(b_vec @ t_hat), float(b_vec @ r_hat)
    return np.array([(bt - want_b[0]) / scale, (br - want_b[1]) / scale, (ut - want_ut) / DAY])


def b_for_periapsis(mu, vinf, peR):
    """Impact parameter that yields periapsis `peR` at excess speed `vinf`."""
    return peR * math.sqrt(1.0 + 2.0 * mu / (peR * vinf * vinf))


def refine(system, body, r_node, v_node, ut_node, target, t_end, peR_want,
           b_dir=None, ut_want=None, watch=None, max_nfev=60, verbose=False):
    """Least-squares correct a burn until the FLOWN trajectory hits the aim point.

    Unknown is the 3-vector dV at a fixed node time. The aim point is a B-plane
    target: magnitude from the periapsis you asked for, direction kept as-is
    unless you name one, which is the cheapest way to fix an arrival.
    """
    target = system.body(target)
    watch = watch or [target.name]
    r_node = np.asarray(r_node, float)
    v_node = np.asarray(v_node, float)

    def fly(dv):
        return patched.shoot(system, body, r_node, v_node + np.asarray(dv, float),
                             ut_node, t_end, watch=watch)

    dv0 = np.zeros(3)
    traj = fly(dv0)
    rep = patched.arrival_report(system, traj, target.name, t_end)
    vinf = rep.get("vinf") or rep.get("ca_vrel") or 1000.0
    b_mag = b_for_periapsis(target.mu, max(vinf, 1.0), peR_want)
    if b_dir is None:
        res0 = _bplane_residual(system, traj, target.name, t_end, (0.0, 0.0), 0.0)
        cur = np.array([res0[0], res0[1]])
        n = float(np.linalg.norm(cur))
        b_dir = cur / n if n > 1e-12 else np.array([1.0, 0.0])
    want_b = (b_dir[0] * b_mag, b_dir[1] * b_mag)
    want_ut = ut_want if ut_want is not None else (rep.get("soi_ut") or rep.get("ca_ut"))

    def resid(x):
        t = fly(x)
        r = _bplane_residual(system, t, target.name, t_end, want_b, want_ut)
        if ut_want is None:
            r[2] = 0.0                        # arrival time free
        if verbose:
            print(f"   dv={np.linalg.norm(x):9.2f} m/s  resid={np.linalg.norm(r):.4e}")
        return r

    sol = least_squares(resid, dv0, diff_step=1e-4, xtol=1e-12, ftol=1e-12,
                        gtol=1e-12, max_nfev=max_nfev)
    dv = sol.x
    traj = fly(dv)
    return {"dv": dv, "traj": traj,
            "report": patched.arrival_report(system, traj, target.name, t_end),
            "cost": float(sol.cost), "nfev": sol.nfev, "b_want": want_b}


# ---------------------------------------------------------------------------
# midcourse correction
# ---------------------------------------------------------------------------
def cheapest_correction(system, body, r0, v0, ut0, target, t_arr, peR_want,
                        t_end=None, n_times=24, watch=None, verbose=False):
    """Where along the coast is the correction cheapest, and how big is it?

    A correction gets geometrically cheaper the earlier you make it, and MechJeb
    just samples 20 points between now and closest approach for that reason.
    This does the same scan but each sample is scored by a converged shot, so
    the number quoted is the burn that actually works, not the burn that closes
    a linearised miss.
    """
    target = system.body(target)
    t_end = t_end or (t_arr + 200 * DAY)
    watch = watch or [target.name]
    out = []
    span = t_arr - ut0
    for i in range(n_times):
        t = ut0 + span * (0.02 + 0.9 * i / max(1, n_times - 1))
        r, v = astro.propagate(system.body(body).mu, np.asarray(r0), np.asarray(v0), t - ut0)
        try:
            res = refine(system, body, r, v, t, target.name, t_end, peR_want, watch=watch)
        except Exception as exc:                       # noqa: BLE001 - report, do not hide
            if verbose:
                print(f"  {t:,.0f}: {exc}")
            continue
        mag = float(np.linalg.norm(res["dv"]))
        rep = res["report"]
        ok = rep.get("captured") and abs(rep["peR"] - peR_want) / peR_want < 0.02
        out.append({"ut": t, "dv": res["dv"], "mag": mag, "ok": ok, "res": res})
        if verbose:
            print(f"  burn {t:,.0f}: {mag:8.1f} m/s  {'hit' if ok else 'MISS'}")
    good = [o for o in out if o["ok"]]
    if not good:
        return None, out
    return min(good, key=lambda o: o["mag"]), out


# ---------------------------------------------------------------------------
# flyby
# ---------------------------------------------------------------------------
def flyby_report(system, traj, body, t_end):
    """What a flyby of `body` actually does to the trajectory."""
    body = system.body(body)
    p = traj.enters(body.name)
    if p is None:
        return None
    el_in = p.elements()
    vinf_in = astro.vinf_from_state(body.mu, p.r0, p.v0)
    bp = astro.bplane(body.mu, p.r0, p.v0)
    out = {"soi_in": p.ut0, "peR": el_in.peR, "peAlt": el_in.peR - body.radius,
           "vinf": vinf_in, "ecc": el_in.ecc, "inc": math.degrees(el_in.inc),
           "impact": el_in.peR < body.radius,
           "turn": math.degrees(astro.turn_angle(body.mu, vinf_in, el_in.peR)),
           "b": bp["b"] if bp else None}
    if p.ut1 and p.end == "exit":
        r, v = p.state(p.ut1)
        rp_, vp_ = system.rel(body.name, p.ut1)
        out["soi_out"] = p.ut1
        out["v_helio_out"] = np.asarray(v) + np.asarray(vp_)
        out["dv_equiv"] = 2 * vinf_in * math.sin(
            astro.turn_angle(body.mu, vinf_in, el_in.peR) / 2)
    return out


def flyby_bend(mu, vinf_vec, peR, plane_normal=None, side=1.0):
    """Outgoing v-infinity after a periapsis pass at `peR`, bent in a chosen plane.

    Turn magnitude is fixed by (peR, |vinf|); the free choice is which way you
    bend, which is what the B-plane angle buys you.
    """
    vinf_vec = np.asarray(vinf_vec, float)
    v = float(np.linalg.norm(vinf_vec))
    delta = astro.turn_angle(mu, v, peR)
    s_hat = vinf_vec / v
    if plane_normal is None:
        k = np.array([0.0, 0.0, 1.0])
        n = np.cross(s_hat, k)
        n = n / np.linalg.norm(n)
    else:
        n = np.asarray(plane_normal, float)
        n = n / np.linalg.norm(n)
    axis = np.cross(s_hat, n)
    axis = axis / np.linalg.norm(axis) * side
    c, sn = math.cos(delta), math.sin(delta)
    rot = (s_hat * c + np.cross(axis, s_hat) * sn + axis * float(axis @ s_hat) * (1 - c))
    return rot * v, math.degrees(delta)
