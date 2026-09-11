"""Two-body core, transcribed from what the game and MechJeb actually run.

Everything lives in the right-handed z-up frame KSP stores its elements in
(Planetarium.Zup), so nothing here ever touches KSP's left-handed world frame
and no handedness bug can leak in.

The one convention worth writing down, because it is double-negated in MechJeb
and impossible to guess:

    ManeuverNode.DeltaV = (radial_out, normal, prograde)

    prograde = v_hat
    normal   = normalize(r x v)          <- the angular momentum direction
    radial   = normalize(v_hat x normal) == component of r_hat perpendicular to v

    MechJeb writes `new Vector3d(dot(RadialPlus,dV), dot(-NormalPlus,dV), dot(Prograde,dV))`
    (OrbitExtensions.DeltaVToManeuverNodeCoordinates) and its own OrbitNormal() is
    `-GetOrbitNormal().xzy`, while stock's Orbit.GetOrbitNormal() is
    `Zup.WorldToLocal(OrbitFrame.Z)` with `OrbitFrame.Z = normalize(cross(pos, vel))`.
    The two minus signs cancel: the node's y really is +h.
"""
import math

import numpy as np


# ---------------------------------------------------------------------------
# propagation: Shepperd's method, the one MechJebLib uses everywhere
# ---------------------------------------------------------------------------
def propagate(mu, r0, v0, dt, tol=1e-12, itmax=50):
    """Universal-variable two-body propagation (Shepperd 1985), any conic.

    Continued-fraction Gauss series rather than a Newton solve on Stumpff
    functions: it does not lose digits near the parabolic boundary, which is
    exactly where a departure hyperbola with e ~ 1.0001 lives.
    """
    r0 = np.asarray(r0, dtype=float)
    v0 = np.asarray(v0, dtype=float)
    if dt == 0.0:
        return r0.copy(), v0.copy()
    r0mag = float(np.linalg.norm(r0))
    sigma0 = float(r0 @ v0)
    beta = 2.0 * mu / r0mag - float(v0 @ v0)     # = mu/a
    u = 0.0
    umax, umin = math.inf, -math.inf
    if beta != 0.0:
        umax = 1.0 / math.sqrt(abs(beta))
        umin = -umax
    n_rev = 0.0
    if beta > 0.0:
        n_rev = math.floor((1.0 + (beta * dt - 2.0 * sigma0) * math.sqrt(beta) / (math.pi * mu)) / 2.0)
    deltat_tol = 1e-12 * abs(dt)
    u_prev = t_prev = None
    U1 = U2 = rr = 0.0
    for _ in range(itmax):
        q = beta * u * u
        q = q / (1.0 + q)
        # Gauss continued fraction for the U-series, iterated to machine agreement
        n_, m_, k_, dd, ll, gg, signk, prev_g = 0.0, 1.0, 1.0, 3.0, 1.0, 1.0, -5.0, 0.0
        while gg != prev_g:
            signk = -signk
            k_ += 2.0
            dd += 4.0 * k_
            n_ += (1.0 + signk) * k_
            m_ = dd / (dd - n_ * m_ * q)
            ll = (m_ - 1.0) * ll
            prev_g = gg
            gg = prev_g + ll
        U0w2 = 1.0 - 2.0 * q
        U1w2 = 2.0 * u * (1.0 - q)
        U0 = 2.0 * U0w2 * U0w2 - 1.0
        U1 = 2.0 * U0w2 * U1w2
        U2 = 2.0 * U1w2 * U1w2
        U3 = 2.0 * U1w2 * U2 * gg / 3.0
        if n_rev != 0.0:
            U3 += 2.0 * math.pi * n_rev / (beta * math.sqrt(beta))
        rr = r0mag * U0 + sigma0 * U1 + mu * U2
        t = r0mag * U1 + sigma0 * U2 + mu * U3
        dtdu = 4.0 * rr / (1.0 + beta * u * u)
        dterr = dt - t
        if abs(dterr) < deltat_tol or (u_prev is not None and (u == u_prev or t == t_prev)):
            break
        u_prev, t_prev = u, t
        du = dterr / dtdu
        if du > 0.0:
            umin = u
            u += du
            if u > umax:
                u = 0.5 * (umin + umax)
        else:
            umax = u
            u += du
            if u < umin:
                u = 0.5 * (umin + umax)
    f = 1.0 - mu / r0mag * U2
    g = r0mag * U1 + sigma0 * U2
    gdot = 1.0 - mu / rr * U2
    fdot = -mu * U1 / (r0mag * rr)
    return f * r0 + g * v0, fdot * r0 + gdot * v0


# ---------------------------------------------------------------------------
# elements
# ---------------------------------------------------------------------------
class Elements:
    __slots__ = ("mu", "sma", "ecc", "inc", "lan", "argp", "nu", "mna", "period",
                 "peR", "apR", "h", "energy")

    def __repr__(self):
        pe = f"{self.peR / 1e3:,.0f}"
        ap = "escape" if self.ecc >= 1 else f"{self.apR / 1e3:,.0f}"
        return (f"<a={self.sma / 1e3:,.0f} km e={self.ecc:.5f} i={math.degrees(self.inc):.3f} "
                f"pe={pe} ap={ap} km>")

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


def elements(mu, r, v):
    """State vectors -> classical elements, using KSP's own angle conventions."""
    r = np.asarray(r, float)
    v = np.asarray(v, float)
    rm = float(np.linalg.norm(r))
    vm = float(np.linalg.norm(v))
    h = np.cross(r, v)
    hm = float(np.linalg.norm(h))
    e_vec = np.cross(v, h) / mu - r / rm
    ecc = float(np.linalg.norm(e_vec))
    energy = vm * vm / 2 - mu / rm
    sma = math.inf if abs(ecc - 1.0) < 1e-12 else -mu / (2 * energy)
    inc = math.acos(max(-1.0, min(1.0, h[2] / hm)))
    n = np.array([-h[1], h[0], 0.0])
    nm = float(np.linalg.norm(n))
    if nm < 1e-9:                      # equatorial: put the node on +x
        n = np.array([1.0, 0.0, 0.0])
        nm = 1.0
        lan = 0.0
    else:
        lan = math.atan2(n[1], n[0]) % (2 * math.pi)
    if ecc < 1e-9:                     # circular: argp measured to the position
        argp = 0.0
        nu = math.atan2(float(np.dot(np.cross(n, r), h / hm)), float(np.dot(n, r))) % (2 * math.pi)
    else:
        argp = math.atan2(float(np.dot(np.cross(n, e_vec), h / hm)), float(np.dot(n, e_vec))) % (2 * math.pi)
        nu = math.atan2(float(np.dot(np.cross(e_vec, r), h / hm)), float(np.dot(e_vec, r)))
    el = Elements()
    el.mu, el.sma, el.ecc, el.inc, el.lan, el.argp, el.nu = mu, sma, ecc, inc, lan, argp, nu
    el.h, el.energy = hm, energy
    el.peR = sma * (1 - ecc) if ecc < 1 else sma * (1 - ecc)
    el.apR = sma * (1 + ecc) if ecc < 1 else math.inf
    el.period = 2 * math.pi * math.sqrt(sma ** 3 / mu) if ecc < 1 else math.inf
    el.mna = mean_anomaly(ecc, nu)
    return el


def mean_anomaly(ecc, nu):
    if ecc < 1.0:
        E = 2 * math.atan2(math.sqrt(1 - ecc) * math.sin(nu / 2), math.sqrt(1 + ecc) * math.cos(nu / 2))
        return E - ecc * math.sin(E)
    H = 2 * math.atanh(math.sqrt((ecc - 1) / (ecc + 1)) * math.tan(nu / 2))
    return ecc * math.sinh(H) - H


def kepler_hyperbolic(M, ecc, tol=1e-13):
    H = math.asinh(M / ecc) if abs(M) > 6 else M / (ecc - 1.0)
    if not math.isfinite(H):
        H = math.copysign(1.0, M)
    for _ in range(200):
        f = ecc * math.sinh(H) - H - M
        fp = ecc * math.cosh(H) - 1.0
        d = -f / fp
        H += d
        if abs(d) < tol:
            break
    return H


def state_from_elements(mu, sma, ecc, inc, lan, argp, mna, dt=0.0):
    """Elements + mean anomaly (advanced by `dt` seconds) -> (r, v). Angles in radians."""
    if ecc < 1.0:
        n = math.sqrt(mu / sma ** 3)
        M = mna + n * dt
        from rss_ephem import kepler_E
        E = kepler_E(M, ecc)
        nu = 2 * math.atan2(math.sqrt(1 + ecc) * math.sin(E / 2), math.sqrt(1 - ecc) * math.cos(E / 2))
        r = sma * (1 - ecc * math.cos(E))
    else:
        a = abs(sma)
        n = math.sqrt(mu / a ** 3)
        M = mna + n * dt
        H = kepler_hyperbolic(M, ecc)
        nu = 2 * math.atan2(math.sqrt(ecc + 1) * math.sinh(H / 2), math.sqrt(ecc - 1) * math.cosh(H / 2))
        r = a * (ecc * math.cosh(H) - 1)
    p = abs(sma) * abs(1 - ecc * ecc)
    h = math.sqrt(mu * p)
    rp = np.array([r * math.cos(nu), r * math.sin(nu), 0.0])
    vp = np.array([-mu / h * math.sin(nu), mu / h * (ecc + math.cos(nu)), 0.0])
    cO, sO = math.cos(lan), math.sin(lan)
    ci, si = math.cos(inc), math.sin(inc)
    cw, sw = math.cos(argp), math.sin(argp)
    R = np.array([
        [cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
        [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
        [sw * si, cw * si, ci],
    ])
    return R @ rp, R @ vp


def state_from_save_orbit(mu, sma, ecc, inc_deg, lpe_deg, lan_deg, mna, eph, ut):
    """A save's ORBIT node -> state at `ut`.

    KSP writes INC/LPE/LAN in degrees and MNA in RADIANS at epoch EPH. Reading
    MNA as degrees puts a vessel most of the way round its orbit and still looks
    plausible, so this is the only place that conversion should ever happen.
    """
    return state_from_elements(mu, sma, ecc, math.radians(inc_deg), math.radians(lan_deg),
                               math.radians(lpe_deg), mna, ut - eph)


# ---------------------------------------------------------------------------
# maneuver-node basis
# ---------------------------------------------------------------------------
def node_basis(r, v):
    """(radial_out, normal, prograde) unit vectors -- the ManeuverNode axes."""
    r = np.asarray(r, float)
    v = np.asarray(v, float)
    prograde = v / np.linalg.norm(v)
    h = np.cross(r, v)
    normal = h / np.linalg.norm(h)
    radial = np.cross(prograde, normal)
    return radial, normal, prograde


def to_node(r, v, dv):
    """World dV -> (radial, normal, prograde), i.e. ManeuverNode.DeltaV (x, y, z)."""
    radial, normal, prograde = node_basis(r, v)
    dv = np.asarray(dv, float)
    return np.array([float(radial @ dv), float(normal @ dv), float(prograde @ dv)])


def from_node(r, v, comps):
    """(radial, normal, prograde) -> world dV."""
    radial, normal, prograde = node_basis(r, v)
    c = np.asarray(comps, float)
    return c[0] * radial + c[1] * normal + c[2] * prograde


# ---------------------------------------------------------------------------
# hyperbolic / v-infinity helpers
# ---------------------------------------------------------------------------
def vinf_from_state(mu, r, v):
    """Hyperbolic excess speed of a state (0 if it is bound)."""
    r = np.asarray(r, float)
    energy = float(v @ v) / 2 - mu / float(np.linalg.norm(r))
    return math.sqrt(2 * energy) if energy > 0 else 0.0


def vinf_at_radius(mu, v_rel, radius):
    """Excess speed implied by a relative speed measured at `radius` from a body.

    Deriving v-inf from the speed at the SOI boundary rather than assuming the
    boundary is at infinity is worth 1-2% on a lunar transfer and is why the
    departure asymptote and the actual trajectory used to disagree.
    """
    e2 = v_rel * v_rel - 2 * mu / radius
    return math.sqrt(e2) if e2 > 0 else 0.0


def turn_angle(mu, vinf, rp):
    """Flyby deflection for a periapsis pass at `rp` with excess speed `vinf`."""
    if vinf <= 0:
        return math.pi
    e = 1 + rp * vinf * vinf / mu
    return 2 * math.asin(1.0 / e)


def periapsis_for_turn(mu, vinf, delta):
    """Inverse of turn_angle: the periapsis that gives deflection `delta`."""
    e = 1.0 / math.sin(delta / 2)
    return (e - 1) * mu / (vinf * vinf)


def bplane(mu_body, r_rel, v_rel):
    """B-plane coordinates (B.T, B.R, |B|) of an incoming hyperbolic state.

    The miss vector B is what you actually steer with a midcourse burn: its
    magnitude sets the flyby periapsis and its direction sets which way you are
    deflected, and unlike periapsis it stays well-behaved when you miss entirely.
    """
    r_rel = np.asarray(r_rel, float)
    v_rel = np.asarray(v_rel, float)
    rm = float(np.linalg.norm(r_rel))
    energy = float(v_rel @ v_rel) / 2 - mu_body / rm
    if energy <= 0:
        return None
    vinf = math.sqrt(2 * energy)
    h = np.cross(r_rel, v_rel)
    w_hat = h / np.linalg.norm(h)
    e_vec = np.cross(v_rel, h) / mu_body - r_rel / rm
    ecc = float(np.linalg.norm(e_vec))
    e_hat = e_vec / ecc
    p_hat = np.cross(w_hat, e_hat)                         # in-plane, 90 deg past periapsis
    a = -mu_body / (2 * energy)
    b = abs(a) * math.sqrt(max(ecc * ecc - 1.0, 0.0))
    # asymptote true anomaly: cos(nu_inf) = -1/e; incoming takes the negative branch
    cs, sn = -1.0 / ecc, math.sqrt(max(1.0 - 1.0 / (ecc * ecc), 0.0))
    s_in = cs * e_hat - sn * p_hat                         # incoming asymptote direction
    s_hat = -s_in                                          # the B-plane normal, pointing downstream
    k = np.array([0.0, 0.0, 1.0])
    t_hat = np.cross(s_hat, k)
    t_hat = t_hat / np.linalg.norm(t_hat)
    r_hat = np.cross(s_hat, t_hat)
    b_vec = b * np.cross(s_hat, w_hat)
    return {"vinf": vinf, "b": b, "B_T": float(b_vec @ t_hat), "B_R": float(b_vec @ r_hat),
            "peR": a * (1 - ecc), "s_hat": s_hat, "b_vec": b_vec,
            "t_hat": t_hat, "r_hat": r_hat, "w_hat": w_hat}


def plane_normal(inc, lan):
    """Unit normal of an orbit plane from its inclination and node (radians), z-up frame."""
    return np.array([math.sin(lan) * math.sin(inc), -math.cos(lan) * math.sin(inc), math.cos(inc)])


# ---------------------------------------------------------------------------
# root finding on a propagated trajectory
# ---------------------------------------------------------------------------
def brent(f, lo, hi, tol=1e-9, itmax=200):
    """Plain Brent root find; raises if the bracket does not straddle a root."""
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        raise ValueError("bracket does not straddle a root")
    a, b, fa, fb = lo, hi, flo, fhi
    c, fc = a, fa
    d = e = b - a
    for _ in range(itmax):
        if fb * fc > 0:
            c, fc, d, e = a, fa, b - a, b - a
        if abs(fc) < abs(fb):
            a, b, c = b, c, b
            fa, fb, fc = fb, fc, fb
        tol1 = 2 * 2.22e-16 * abs(b) + 0.5 * tol
        xm = 0.5 * (c - b)
        if abs(xm) <= tol1 or fb == 0.0:
            return b
        if abs(e) >= tol1 and abs(fa) > abs(fb):
            s = fb / fa
            if a == c:
                p, q = 2 * xm * s, 1 - s
            else:
                q, r_ = fa / fc, fb / fc
                p = s * (2 * xm * q * (q - r_) - (b - a) * (r_ - 1))
                q = (q - 1) * (r_ - 1) * (s - 1)
            if p > 0:
                q = -q
            p = abs(p)
            if 2 * p < min(3 * xm * q - abs(tol1 * q), abs(e * q)):
                e, d = d, p / q
            else:
                d = e = xm
        else:
            d = e = xm
        a, fa = b, fb
        b += d if abs(d) > tol1 else math.copysign(tol1, xm)
        fb = f(b)
    return b


# ---------------------------------------------------------------------------
# vectorised sampling: one conic, many times
# ---------------------------------------------------------------------------
def _kepler_E_vec(M, e, iters=80):
    M = np.mod(M, 2 * np.pi)
    E = np.where(e < 0.8, M, np.pi) + np.zeros_like(M)
    for _ in range(iters):
        d = -(E - e * np.sin(E) - M) / (1 - e * np.cos(E))
        E = E + d
        if np.all(np.abs(d) < 1e-14):
            break
    return E


def _kepler_H_vec(M, e, iters=120):
    # H is clipped to +-350: cosh(350) is ~1e152, still finite, and any sample that
    # far down a hyperbola is only ever asked "are you past the SOI yet" -- letting
    # it overflow to inf would answer that correctly but noisily.
    H = np.where(np.abs(M) > 6.0, np.arcsinh(np.clip(M / e, -1e150, 1e150)), M / (e - 1.0))
    H = np.clip(H, -350.0, 350.0)
    for _ in range(iters):
        d = -(e * np.sinh(H) - H - M) / (e * np.cosh(H) - 1.0)
        H = np.clip(H + np.clip(d, -1.0, 1.0), -350.0, 350.0)
        if np.all(np.abs(d) < 1e-13):
            break
    return H


def sample_conic(mu, r0, v0, dts):
    """States along one conic at many offsets from (r0, v0). Returns (N,3), (N,3).

    Built on the perifocal basis taken straight from the state vectors rather
    than from angles, so a circular or equatorial orbit -- where LAN and argp
    stop being defined -- samples exactly as well as any other.
    """
    r0 = np.asarray(r0, float)
    v0 = np.asarray(v0, float)
    dts = np.atleast_1d(np.asarray(dts, float))
    rm = float(np.linalg.norm(r0))
    h = np.cross(r0, v0)
    h_hat = h / np.linalg.norm(h)
    e_vec = np.cross(v0, h) / mu - r0 / rm
    ecc = float(np.linalg.norm(e_vec))
    energy = float(v0 @ v0) / 2 - mu / rm
    if ecc > 1e-12:
        e_hat = e_vec / ecc
    else:
        e_hat = r0 / rm
    p_hat = np.cross(h_hat, e_hat)
    p = float(h @ h) / mu
    nu0 = math.atan2(float(r0 @ p_hat), float(r0 @ e_hat))
    if ecc < 1.0:
        a = -mu / (2 * energy)
        n = math.sqrt(mu / a ** 3)
        M0 = mean_anomaly(ecc, nu0)
        E = _kepler_E_vec(M0 + n * dts, ecc)
        nu = 2 * np.arctan2(math.sqrt(1 + ecc) * np.sin(E / 2), math.sqrt(1 - ecc) * np.cos(E / 2))
    else:
        a = abs(-mu / (2 * energy)) if abs(energy) > 1e-30 else math.inf
        n = math.sqrt(mu / a ** 3)
        M0 = mean_anomaly(ecc, nu0)
        H = _kepler_H_vec(M0 + n * dts, ecc)
        nu = 2 * np.arctan2(math.sqrt(ecc + 1) * np.sinh(H / 2), math.sqrt(ecc - 1) * np.cosh(H / 2))
    cn, sn = np.cos(nu), np.sin(nu)
    den = 1 + ecc * cn
    rr = p / np.where(np.abs(den) < 1e-300, 1e-300, den)
    pos = rr[:, None] * (cn[:, None] * e_hat + sn[:, None] * p_hat)
    k = math.sqrt(mu / p)
    vel = k * (-sn[:, None] * e_hat + (ecc + cn)[:, None] * p_hat)
    return pos, vel
