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


def _arrival_state(system, traj, target, soi_ut):
    b, r, v = traj.state(soi_ut + 60.0)
    if b.name != target:
        raise ValueError(f"trajectory is in {b.name}'s SOI just after the {target} entry it reported")
    return np.asarray(r, float), np.asarray(v, float)


def inc_to_plane(system, traj, target, soi_ut, plane_body):
    """Angle (deg) between the arrival orbit's normal and `plane_body`'s orbital plane."""
    r, v = _arrival_state(system, traj, target, soi_ut)
    pb = system.body(plane_body)
    w = np.cross(r, v)
    w = w / np.linalg.norm(w)
    n = astro.plane_normal(pb.inc, pb.lan)
    return math.degrees(math.acos(max(-1.0, min(1.0, float(w @ n)))))


def periapsis_latitude(system, traj, target, soi_ut, plane_body):
    """Latitude (deg) of the arrival periapsis vector above `plane_body`'s orbital plane.

    THE number that decides whether a moon tour's plane can ever be fixed: a burn only reaches
    planes that contain the burn point, and the cheap burn point is apoapsis, on the same line.
    """
    r, v = _arrival_state(system, traj, target, soi_ut)
    mu = system.body(target).mu
    h = np.cross(r, v)
    e_vec = np.cross(v, h) / mu - r / np.linalg.norm(r)
    e_hat = e_vec / np.linalg.norm(e_vec)
    pb = system.body(plane_body)
    n = astro.plane_normal(pb.inc, pb.lan)
    return math.degrees(math.asin(max(-1.0, min(1.0, float(e_hat @ n)))))


def apsis_b_dir(system, traj, target, t_end, plane_body, peR_want):
    """B-plane aim that puts the arrival PERIAPSIS in `plane_body`'s orbital plane, prograde.

    This is the aim a moon tour wants, and `plane_b_dir` is NOT: minimum inclination leaves the
    apsidal line at a latitude the apoapsis burn cannot remove (Saturnalija: 21 deg, tour dead;
    Perun 2 as first aimed: 4 deg, Ganymede 75,000 km off the plane at perijove). With the
    periapsis on the node line the whole arrival inclination comes out at apoapsis for
    2 v_apo sin(i/2), folded into the periapsis raise.

    Geometry: the periapsis direction is e_hat = cos(beta) s + sin(beta) B_hat with
    cos(beta) = 1/e (astro.bplane's own construction, s downstream), and e follows from the
    periapsis radius asked for. e_hat . n = 0 then fixes the angle of B_hat in the B-plane to
    two roots; the prograde one has (B_hat x s) . n > 0. Returns (b_dir, |floor| deg).
    """
    target = system.body(target)
    pb = system.body(plane_body)
    rep = patched.arrival_report(system, traj, target.name, t_end)
    if not rep.get("captured"):
        raise ValueError(f"no {target.name} arrival to aim from -- correct the miss first")
    r, v = _arrival_state(system, traj, target.name, rep["soi_ut"])
    bp = astro.bplane(target.mu, r, v)
    s = bp["s_hat"]
    n = astro.plane_normal(pb.inc, pb.lan)
    ecc = 1.0 + peR_want * bp["vinf"] ** 2 / target.mu
    beta = math.acos(1.0 / ecc)
    e1 = n - float(n @ s) * s
    e1n = float(np.linalg.norm(e1))
    e1 = e1 / e1n
    e2 = np.cross(s, e1)
    c = -float(n @ s) / (e1n * math.tan(beta))
    if abs(c) > 1.0:
        raise ValueError(f"the asymptote is {math.degrees(math.asin(abs(float(n @ s)))):.2f} deg "
                         f"out of {pb.name}'s plane -- no {peR_want / 1e3:,.0f} km periapsis lies in it")
    sn = math.sqrt(1.0 - c * c)
    pick = None
    for sgn in (1.0, -1.0):
        bh = c * e1 + sgn * sn * e2
        w = np.cross(bh, s)
        if float(w @ n) > 0:
            pick = bh
    if pick is None:
        pick = c * e1 + sn * e2
    d = np.array([float(pick @ bp["t_hat"]), float(pick @ bp["r_hat"])])
    return d / np.linalg.norm(d), math.degrees(math.asin(min(1.0, abs(float(s @ n)))))


def plane_b_dir(system, traj, target, t_end, plane_body):
    """B-plane aim that lays the arrival orbit as close to `plane_body`'s orbital plane as the
    incoming asymptote allows, on the prograde side.

    The orbit normal w must be perpendicular to the asymptote s, so the nearest w to the
    plane's normal n is n with its s-component removed; the residual angle asin|s.n| is the
    asymptote's declination above the plane and cannot be bought from here at any price
    (Perun 2: floor 4.09 deg, and the ecliptic-prograde aim sat 25.6 deg off the Galilean
    plane for the same periapsis). B lies along s x w, because r -> -L s + B on the way in
    gives h = r x v along B x s. Returns (b_dir in astro.bplane's (T, R) basis, floor deg).
    """
    target = system.body(target)
    pb = system.body(plane_body)
    rep = patched.arrival_report(system, traj, target.name, t_end)
    if not rep.get("captured"):
        raise ValueError(f"no {target.name} arrival to aim a plane from -- correct the miss first")
    r, v = _arrival_state(system, traj, target.name, rep["soi_ut"])
    bp = astro.bplane(target.mu, r, v)
    s = bp["s_hat"]
    n = astro.plane_normal(pb.inc, pb.lan)
    w = n - float(n @ s) * s
    w = w / np.linalg.norm(w)
    bdir = np.cross(s, w)
    d = np.array([float(bdir @ bp["t_hat"]), float(bdir @ bp["r_hat"])])
    return d / np.linalg.norm(d), math.degrees(math.asin(min(1.0, abs(float(s @ n)))))


def _spec_b_dir(system, traj, target, t_end, spec, peR_want):
    kind, _, plane_of = spec.partition(":")
    if kind == "apsis":
        return apsis_b_dir(system, traj, target, t_end, plane_of, peR_want)
    return plane_b_dir(system, traj, target, t_end, plane_of)


def refine(system, body, r_node, v_node, ut_node, target, t_end, peR_want,
           b_dir=None, ut_want=None, watch=None, max_nfev=60, verbose=False,
           max_dv=1000.0, diff_step=1e-2):
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
    plane_of, plane_floor, spec = None, None, None
    if isinstance(b_dir, str):
        # "plane:Ganymede" -- minimum inclination to that body's orbital plane.
        # "apsis:Ganymede" -- periapsis IN that plane, which is what a moon tour needs.
        # Both depend on the flown asymptote, so they are resolved here and re-resolved once
        # on the corrected trajectory (the MCC moves the asymptote a little).
        spec = b_dir
        kind, _, plane_of = b_dir.partition(":")
        if kind not in ("plane", "apsis") or not plane_of:
            raise ValueError(f"unknown b_dir spec {b_dir!r}; use 'plane:<Body>', 'apsis:<Body>' or a 2-vector")
        b_dir, plane_floor = _spec_b_dir(system, traj, target.name, t_end, spec, peR_want)
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

    # Bounded, for the same reason aim_through is: unbounded, least squares is free to
    # find a wholly different trajectory that happens to graze the aim point, and it does
    # -- a measured 4,892 m/s "solution" with a 0.0 km miss. And diff_step is RELATIVE in
    # SciPy (h = diff_step * max(1, |x|)), so the old 1e-4 meant 0.1 mm/s steps around
    # zero, below the shooter's own SOI root-finding noise.
    sol = least_squares(resid, dv0, diff_step=diff_step,
                        bounds=(-abs(max_dv), abs(max_dv)),
                        xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=max_nfev)
    dv = sol.x
    traj = fly(dv)
    if spec:
        # second pass: the aim was built on the no-burn asymptote; rebuild it on the corrected one
        try:
            b_dir, plane_floor = _spec_b_dir(system, traj, target.name, t_end, spec, peR_want)
            want_b = (b_dir[0] * b_mag, b_dir[1] * b_mag)
            sol = least_squares(resid, dv, diff_step=diff_step,
                                bounds=(-abs(max_dv), abs(max_dv)),
                                xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=max_nfev)
            dv = sol.x
            traj = fly(dv)
        except ValueError:
            pass
    report = patched.arrival_report(system, traj, target.name, t_end)
    if plane_of and report.get("captured"):
        report["plane"] = plane_of
        report["inc_to_plane"] = inc_to_plane(system, traj, target.name, report["soi_ut"], plane_of)
        report["peri_lat"] = periapsis_latitude(system, traj, target.name, report["soi_ut"], plane_of)
        report["plane_floor"] = plane_floor
    return {"dv": dv, "traj": traj, "report": report,
            "cost": float(sol.cost), "nfev": sol.nfev, "b_want": want_b}


# ---------------------------------------------------------------------------
# targeting THROUGH a gravity assist
# ---------------------------------------------------------------------------
def _to_centre(system, traj, ut, centre):
    """Spacecraft position at `ut`, expressed relative to `centre`."""
    b, r, _v = traj.state(ut)
    r = np.asarray(r, float)
    if b.name == centre:
        return r
    rb, _vb = system.state(b.name, ut, centre)
    return r + np.asarray(rb)


def assist_passes(system, traj, via):
    """What the trajectory actually did at each assist body.

    Reported rather than assumed. A solver that only measures the DESTINATION will
    happily buy the arrival with a flyby 200 km under the cloud tops, and the answer
    looks perfect right up until the vehicle is inside the planet.
    """
    out = []
    for name in via or []:
        body = system.body(name)
        p = traj.enters(body.name)
        if p is None:
            out.append({"body": body.name, "entered": False})
            continue
        el = p.elements()
        vinf = math.sqrt(max(0.0, float(p.v0 @ p.v0) - 2.0 * body.mu / float(np.linalg.norm(p.r0))))
        row = {"body": body.name, "entered": True, "ut": p.ut0,
               "peR": el.peR, "peAlt": el.peR - body.radius, "ecc": el.ecc,
               "vinf": vinf, "impact": el.peR <= body.radius,
               "exits": p.end == "exit"}
        if el.ecc > 1.0:
            # Turn angle of the hyperbola, and the dV an equivalent burn would have cost.
            row["turn"] = 2.0 * math.degrees(math.asin(1.0 / el.ecc))
            row["dv_equiv"] = 2.0 * vinf * (1.0 / el.ecc)
        out.append(row)
    return out


def natural_arrival(system, traj, target, t_end, after=None):
    """When the UNCORRECTED trajectory comes closest to `target`, on its last leg.

    The arrival epoch cannot be guessed. Ask for a date the trajectory has no business
    being near and the target is simply somewhere else in its orbit -- 100 Gm away, with
    no correction of any size able to fix it -- and the solve reports a failure that looks
    like the method not working. It is not: the sensitivity through a Venus flyby measures
    ~31 Gm per m/s, which closes a 36 Gm miss with about a metre per second. The whole
    difficulty is aiming at the right WHEN.
    """
    last = traj.patches[-1]
    start = max(last.ut0, after if after is not None else last.ut0)
    stop = min(last.ut1 if last.ut1 else t_end, t_end)
    if stop <= start:
        return None, None
    ut, dist, _ = patched.closest_approach(system, traj, target, start, stop)
    return ut, dist


def reachability(system, traj, target):
    """Can the trajectory's final orbit reach the target's orbit at all?

    A radius check, and it is worth doing FIRST because it is the difference between a
    one-line answer and a minute of least squares that ends in "nothing closed". A Venus
    flyby that leaves perihelion at 75.9 Gm cannot reach Mercury, whose aphelion is
    69.8 Gm, and no correction of any size changes that -- the bend a flyby can deliver is
    bounded by its v-infinity and its minimum periapsis.

    Returns None when the two annuli overlap (i.e. nothing to report).
    """
    target = system.body(target)
    last = traj.patches[-1]
    if last.body.name != target.parent:
        return None                       # not a common-centre comparison; say nothing
    el = last.elements()
    t_pe = target.a * (1 - target.e)
    t_ap = target.a * (1 + target.e)
    if el.ecc >= 1.0:
        lo, hi = el.peR, float("inf")
    else:
        lo, hi = el.peR, el.apR
    if lo <= t_ap and hi >= t_pe:
        return None
    if lo > t_ap:
        return (f"the trajectory's perihelion is {lo / 1e9:,.1f} Gm and {target.name}'s "
                f"aphelion is {t_ap / 1e9:,.1f} Gm -- the orbits never touch, so no "
                f"correction reaches it. A bigger bend or a different assist is needed, "
                f"not a better solve.")
    return (f"the trajectory's aphelion is {hi / 1e9:,.1f} Gm and {target.name}'s "
            f"perihelion is {t_pe / 1e9:,.1f} Gm -- the orbits never touch.")


def aim_through(system, body, r0, v0, ut0, target, t_arr, via=None, t_end=None,
                dv_guess=None, diff_step=1e-2, max_nfev=60, verbose=False,
                aim_point=None, max_dv=500.0):
    """Solve the burn at `ut0` that puts the FLOWN trajectory at `target` on `t_arr`.

    The whole point is that the assists are flown, not approximated: `via` bodies go into
    the shooter's watch list, so the trajectory really enters and leaves their SOIs and
    the residual is measured after all of them. Earth SOI -> heliocentric -> Venus SOI ->
    flyby -> heliocentric -> Mercury, with least squares closing the loop.

    Two things differ from `refine`, and both are why `refine` cannot do this job:

    * **The residual is a plain position miss**, not a B-plane miss. B-plane coordinates
      are built from the arrival hyperbola at ONE body; through a flyby the arrival
      hyperbola does not exist until the trajectory is already nearly right, so the
      residual is flat-then-discontinuous and least squares has nothing to descend.
      Position at a fixed epoch is smooth everywhere, and 3 unknowns against 3 equations
      is square.
    * **The unknown is a CORRECTION to a guess**, so it stays near zero. SciPy's
      `diff_step` is relative -- `h = diff_step * max(1, |x|)` -- so differentiating a
      3 km/s ejection directly takes 30 m/s steps, while differentiating around zero with
      the default takes 0.1 mm/s steps that are below the shooter's own SOI root-finding
      noise. The first is too coarse to be a derivative, the second is pure noise. Solving
      for a small correction puts the step in the |x| < 1 regime where `diff_step` IS the
      absolute step in m/s, and 1e-2 m/s is a real lever through a flyby.

    Returns the correction (`dv`), the flown trajectory, the residual miss in metres, and
    what happened at each assist.
    """
    body_name = system.body(body).name
    target = system.body(target)
    via = [system.body(v).name for v in (via or [])]
    watch = list(dict.fromkeys(via + [target.name]))
    t_end = t_end if t_end is not None else t_arr + 30 * DAY
    if t_end < t_arr:
        t_end = t_arr + DAY
    centre = system.common_parent(body_name, target.name)
    scale = target.soi if math.isfinite(target.soi) and target.soi > 0 else target.radius * 100.0

    r0 = np.asarray(r0, float)
    v0 = np.asarray(v0, float)
    dv_guess = np.zeros(3) if dv_guess is None else np.asarray(dv_guess, float)

    def fly(x):
        return patched.shoot(system, body_name, r0, v0 + dv_guess + np.asarray(x, float),
                             ut0, t_end, watch=watch)

    def miss_vec(traj):
        # If a required assist was LOST, steer back to it rather than to the destination.
        #
        # Without this the solver cannot recover from a perturbation big enough to miss
        # the flyby: with no Venus patch the trajectory never leaves the inbound
        # heliocentric leg, so the destination residual is measured on a completely
        # different arc and points nowhere useful. Measured: a 0.5 m/s radial nudge lost
        # the encounter and the solve then sat at a 156,065,501 km miss -- the same value
        # for every such case, which is the tell that it is a topology change and not a
        # hard aim point.
        #
        # The closest approach to the assist body IS continuous across that boundary, and
        # it is the same trick _bplane_residual already uses for a direct arrival. Weighted
        # up so re-acquiring the flyby always beats any in-SOI refinement.
        for name in via:
            if traj.enters(name) is None:
                ab = system.body(name)
                first, last = traj.patches[0], traj.patches[-1]
                ut_ca, _d, _ = patched.closest_approach(
                    system, traj, ab.name, first.ut0, min(last.ut1 or t_end, t_end))
                rs = _to_centre(system, traj, ut_ca, centre)
                rb, _ = system.state(ab.name, ut_ca, centre)
                return (rs - np.asarray(rb, float)) * 4.0

        rs = _to_centre(system, traj, t_arr, centre)
        if aim_point is not None:
            # A fixed point rather than a body. Used to test the shooting machinery
            # itself: perturb a known-good trajectory and check the solver puts it back,
            # which separates "the solver is broken" from "no solution exists".
            return rs - np.asarray(aim_point, float)
        rt, _ = system.state(target.name, t_arr, centre)
        return rs - np.asarray(rt, float)

    def resid(x):
        m = miss_vec(fly(x))
        if verbose:
            print(f"   |x|={np.linalg.norm(x):9.3f} m/s  miss={np.linalg.norm(m) / 1e6:12,.1f} Mm")
        return m / scale

    # Re-acquire a lost assist FIRST, with the residual built for that job.
    #
    # The recovery term above pulls a trajectory that has lost its flyby back toward the
    # assist body, but it stalls exactly at the SOI boundary -- measured, repeatedly, at
    # 616,000 km for Venus, which is its SOI radius to three figures. That is the residual
    # changing character at the boundary: outside, it measures approach; inside, it
    # measures the destination, and the two do not meet.
    #
    # _bplane_residual was written to be continuous across precisely that boundary, so use
    # it. One refine() per lost assist to get back inside, then the destination solve runs
    # from a trajectory that has its flyby.
    seed = np.zeros(3)
    probe = fly(seed)
    for name in via:
        if probe.enters(name) is None:
            ab = system.body(name)
            try:
                pre = refine(system, body_name, r0, v0 + dv_guess, ut0, ab.name,
                             t_end, peR_want=ab.radius * 1.5, watch=watch,
                             max_nfev=max(20, max_nfev // 2))
            except Exception:                                       # noqa: BLE001
                break
            if pre["traj"].enters(ab.name) is not None:
                seed = np.asarray(pre["dv"], float)
                probe = fly(seed)
            break

    # Bound the correction rather than regularising it. Unbounded, the solver is free to
    # find a completely different trajectory that happens to pass through the aim point --
    # measured: a 4,892 m/s "solution" with a 0.0 km miss, which is a correct answer to
    # the wrong question. A box bound says what a correction IS, with no weight to tune.
    lo, hi = -abs(max_dv), abs(max_dv)
    seed = np.clip(seed, lo + 1e-9, hi - 1e-9)
    sol = least_squares(resid, seed, diff_step=diff_step,
                        bounds=(lo, hi),
                        xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=max_nfev)
    traj = fly(sol.x)
    m = miss_vec(traj)
    return {"dv": dv_guess + sol.x, "correction": sol.x, "traj": traj,
            "miss": float(np.linalg.norm(m)), "miss_vec": m,
            "t_arr": t_arr, "nfev": sol.nfev, "cost": float(sol.cost),
            "assists": assist_passes(system, traj, via),
            "hit": float(np.linalg.norm(m)) < scale}


def default_arrivals(system, body, r0, v0, ut0, target, via=None, t_end=None,
                     dv_guess=None, span_days=90.0, n=13):
    """Arrival epochs worth trying: a window around where the trajectory already goes.

    Returns (epochs, natural_ut, natural_miss) so a caller can say what it aimed at.
    """
    via = [system.body(v).name for v in (via or [])]
    watch = list(dict.fromkeys(via + [system.body(target).name]))
    v_start = np.asarray(v0, float) + (np.zeros(3) if dv_guess is None
                                       else np.asarray(dv_guess, float))
    traj = patched.shoot(system, system.body(body).name, np.asarray(r0, float), v_start,
                         ut0, t_end, watch=watch)
    # Only look for the encounter AFTER the last assist -- the trajectory may pass close
    # to the destination on the way in, and correcting to that would skip the flyby.
    after = None
    for name in via:
        p = traj.enters(name)
        if p is not None and p.ut1:
            after = max(after or 0.0, p.ut1)
    ut, dist = natural_arrival(system, traj, target, t_end, after=after)
    if ut is None:
        return [], None, None
    half = span_days * DAY / 2.0
    return list(np.linspace(ut - half, ut + half, n)), ut, dist


def scan_arrivals(system, body, r0, v0, ut0, target, arrivals, via=None, t_end=None,
                  dv_guess=None, peR_want=None, diff_step=1e-2, max_nfev=60,
                  verbose=False, max_dv=500.0):
    """`aim_through` over a set of arrival epochs, cheapest first.

    An arrival date is not free to choose: through an assist the reachable set is narrow,
    and neighbouring dates differ by hundreds of m/s or do not close at all. So the table
    is printed rather than a single date being picked and presented as the answer.
    """
    rows = []
    if arrivals:
        probe = patched.shoot(
            system, system.body(body).name, np.asarray(r0, float),
            np.asarray(v0, float) + (np.zeros(3) if dv_guess is None else np.asarray(dv_guess, float)),
            ut0, t_end if t_end is not None else max(arrivals) + 30 * DAY,
            watch=list(dict.fromkeys([system.body(v).name for v in (via or [])]
                                     + [system.body(target).name])))
        why = reachability(system, probe, target)
        if why:
            return None, [{"t_arr": arrivals[0], "ok": False, "why": why, "fatal": True}]
    for t_arr in arrivals:
        try:
            res = aim_through(system, body, r0, v0, ut0, target, t_arr, via=via,
                              t_end=t_end, dv_guess=dv_guess, diff_step=diff_step,
                              max_nfev=max_nfev, verbose=verbose, max_dv=max_dv)
        except Exception as exc:                                    # noqa: BLE001
            rows.append({"t_arr": t_arr, "ok": False, "why": f"{type(exc).__name__}: {exc}"})
            continue
        res["ok"] = res["hit"]
        res["mag"] = float(np.linalg.norm(res["correction"]))
        # An arrival bought by flying through a planet is not an arrival.
        bad = [a for a in res["assists"] if a.get("impact") or not a.get("entered")]
        if bad:
            res["ok"] = False
            res["why"] = ("missed " if not bad[0].get("entered") else "impacts ") + bad[0]["body"]
        rows.append(res)
    good = [r for r in rows if r.get("ok")]
    best = min(good, key=lambda r: r["mag"]) if good else None
    return best, rows


# ---------------------------------------------------------------------------
# midcourse correction
# ---------------------------------------------------------------------------
def cheapest_correction(system, body, r0, v0, ut0, target, t_arr, peR_want,
                        t_end=None, n_times=24, watch=None, verbose=False,
                        max_dv=1000.0, diff_step=1e-2, b_dir=None):
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

    # Where the vessel actually IS at each candidate burn time.
    #
    # This used to be astro.propagate(mu_of_starting_body, r0, v0, dt) -- one conic about
    # whichever body the vessel happened to be in at ut0, for the whole coast. The moment
    # the trajectory crosses an SOI that state is fiction, and it is fiction that still
    # looks like a state vector, so every sampled burn was solved from a position the
    # vessel is never at and the quoted costs were nonsense.
    #
    # Measured: Merkurac 2 leaves Venus's SOI 0.5 days out and the FIRST sample is at
    # 1.45 days, so every one of the ten burn dates was on the wrong conic. The scan asked
    # for 8,576-67,048 m/s to lower a Mercury periapsis that an impact-parameter estimate
    # prices at 6 m/s, and rejected all of them.
    #
    # Fly it properly and read the state off the trajectory, which also gives the BODY the
    # vessel is in at that moment -- refine needs the right frame, not just the right point.
    coast = patched.shoot(system, system.body(body).name, np.asarray(r0, float),
                          np.asarray(v0, float), ut0, max(t_end, t_arr), watch=watch)
    for i in range(n_times):
        t = ut0 + span * (0.02 + 0.9 * i / max(1, n_times - 1))
        b_at, r, v = coast.state(t)
        try:
            res = refine(system, b_at.name, r, v, t, target.name, t_end, peR_want,
                         b_dir=b_dir, watch=watch, max_dv=max_dv, diff_step=diff_step)
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
