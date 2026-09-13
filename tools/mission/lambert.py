"""Izzo (2015) Lambert solver, zero- and multi-revolution.

Self-contained (numpy only) so mission planning never depends on an install-time package.
Validated in __main__ against an analytic Hohmann transfer and against Pioneer 10's real
Earth->Jupiter leg.
"""
import numpy as np

_TWOPI = 2.0 * np.pi


def _hyp2f1b(x):
    """2F1(3, 1, 5/2, x), series form (converges for |x| < 1)."""
    if x >= 1.0:
        return np.inf
    res = 1.0
    term = 1.0
    for i in range(500):
        term = term * (3 + i) * (1 + i) / (5 / 2 + i) * x / (i + 1)
        res_new = res + term
        if res_new == res:
            return res
        res = res_new
    return res


def _compute_y(x, ll):
    return np.sqrt(1 - ll ** 2 * (1 - x ** 2))


def _compute_psi(x, y, ll):
    if -1 <= x < 1:
        return np.arccos(np.clip(x * y + ll * (1 - x ** 2), -1.0, 1.0))
    if x > 1:
        return np.arcsinh((y - x * ll) * np.sqrt(x ** 2 - 1))
    return 0.0


def _tof_equation_y(x, y, T0, ll, M):
    if M == 0 and np.sqrt(0.6) < x < np.sqrt(1.4):
        eta = y - ll * x
        S_1 = (1 - ll - x * eta) * 0.5
        Q = 4 / 3 * _hyp2f1b(S_1)
        T_ = (eta ** 3 * Q + 4 * ll * eta) * 0.5
    else:
        psi = _compute_psi(x, y, ll)
        T_ = ((psi + M * np.pi) / np.sqrt(np.abs(1 - x ** 2)) - x + ll * y) / (1 - x ** 2)
    return T_ - T0


def _tof_equation_p(x, y, T, ll):
    return (3 * T * x - 2 + 2 * ll ** 3 * x / y) / (1 - x ** 2)


def _tof_equation_p2(x, y, T, dT, ll):
    return (3 * T + 5 * x * dT + 2 * (1 - ll ** 2) * ll ** 3 / y ** 3) / (1 - x ** 2)


def _tof_equation_p3(x, y, _T, dT, ddT, ll):
    return (7 * x * ddT + 8 * dT - 6 * (1 - ll ** 2) * ll ** 5 * x / y ** 5) / (1 - x ** 2)


def _householder(p0, T0, ll, M, tol=1e-11, maxiter=60):
    for _ in range(maxiter):
        y = _compute_y(p0, ll)
        fval = _tof_equation_y(p0, y, T0, ll, M)
        T = fval + T0
        fder = _tof_equation_p(p0, y, T, ll)
        fder2 = _tof_equation_p2(p0, y, T, fder, ll)
        fder3 = _tof_equation_p3(p0, y, T, fder, fder2, ll)
        denom = fder * (fder ** 2 - fval * fder2) + fder3 * fval ** 2 / 6
        if denom == 0:
            return p0
        p = p0 - fval * ((fder ** 2 - fval * fder2 / 2) / denom)
        if abs(p - p0) < tol:
            return p
        p0 = p
    return p0


def _initial_guess(T, ll, M, lowpath=True):
    if M == 0:
        T_0 = np.arccos(ll) + ll * np.sqrt(1 - ll ** 2)
        T_1 = 2 * (1 - ll ** 3) / 3
        if T >= T_0:
            return (T_0 / T) ** (2 / 3) - 1
        if T < T_1:
            return 5 / 2 * T_1 / T * (T_1 - T) / (1 - ll ** 5) + 1
        return (T_0 / T) ** (np.log2(T_1 / T_0)) - 1
    x_0l = (((M * np.pi + np.pi) / (8 * T)) ** (2 / 3) - 1) / (((M * np.pi + np.pi) / (8 * T)) ** (2 / 3) + 1)
    x_0r = (((8 * T) / (M * np.pi)) ** (2 / 3) - 1) / (((8 * T) / (M * np.pi)) ** (2 / 3) + 1)
    return x_0l if lowpath else x_0r


def lambert(mu, r1, r2, tof, M=0, prograde=True, lowpath=True):
    """Return (v1, v2) in m/s for a transfer r1 -> r2 in `tof` seconds."""
    r1 = np.asarray(r1, dtype=float)
    r2 = np.asarray(r2, dtype=float)
    c = r2 - r1
    c_norm = np.linalg.norm(c)
    r1_norm = np.linalg.norm(r1)
    r2_norm = np.linalg.norm(r2)
    s = (r1_norm + r2_norm + c_norm) * 0.5
    i_r1 = r1 / r1_norm
    i_r2 = r2 / r2_norm
    i_h = np.cross(i_r1, i_r2)
    nh = np.linalg.norm(i_h)
    if nh == 0:
        raise ValueError("collinear position vectors")
    i_h = i_h / nh
    ll = np.sqrt(max(0.0, 1 - min(1.0, c_norm / s)))
    if i_h[2] < 0:
        ll = -ll
        i_t1 = np.cross(i_r1, i_h)
        i_t2 = np.cross(i_r2, i_h)
    else:
        i_t1 = np.cross(i_h, i_r1)
        i_t2 = np.cross(i_h, i_r2)
    if not prograde:
        ll = -ll
        i_t1, i_t2 = -i_t1, -i_t2
    T = np.sqrt(2 * mu / s ** 3) * tof
    x0 = _initial_guess(T, ll, M, lowpath)
    x = _householder(x0, T, ll, M)
    y = _compute_y(x, ll)
    gamma = np.sqrt(mu * s / 2)
    rho = (r1_norm - r2_norm) / c_norm
    sigma = np.sqrt(max(0.0, 1 - rho ** 2))
    V_r1 = gamma * ((ll * y - x) - rho * (ll * y + x)) / r1_norm
    V_r2 = -gamma * ((ll * y - x) + rho * (ll * y + x)) / r2_norm
    V_t1 = gamma * sigma * (y + ll * x) / r1_norm
    V_t2 = gamma * sigma * (y + ll * x) / r2_norm
    return V_r1 * i_r1 + V_t1 * i_t1, V_r2 * i_r2 + V_t2 * i_t2


def max_revs(mu, r1, r2, tof):
    """Largest M for which a multi-rev solution can exist."""
    a_min = (np.linalg.norm(r1) + np.linalg.norm(r2) + np.linalg.norm(np.asarray(r2) - np.asarray(r1))) / 4
    t_min = np.pi * np.sqrt(a_min ** 3 / mu)
    return int(tof / (2 * t_min))


if __name__ == "__main__":
    mu = 1.32712440042e20
    # 1) Analytic Hohmann, 1 AU -> 1.524 AU, 180 deg
    r1 = np.array([1.495979e11, 0, 0])
    r2 = np.array([-2.279e11, 0, 1.0])  # nudge off collinear
    a_t = (np.linalg.norm(r1) + np.linalg.norm(r2)) / 2
    tof = np.pi * np.sqrt(a_t ** 3 / mu)
    v1, v2 = lambert(mu, r1, r2, tof)
    dv1 = np.linalg.norm(v1) - np.sqrt(mu / np.linalg.norm(r1))
    hoh = np.sqrt(mu / np.linalg.norm(r1)) * (np.sqrt(2 * np.linalg.norm(r2) / (np.linalg.norm(r1) + np.linalg.norm(r2))) - 1)
    print(f"Hohmann check: lambert dv1={dv1:.2f} m/s   analytic={hoh:.2f} m/s   err={abs(dv1-hoh):.3f}")

    # 2) Pioneer 10 Earth->Jupiter, real dates, against the install's own ephemeris
    from rss_ephem import System, ut_of
    S = System()
    t0 = ut_of(1972, 3, 3, 1, 49)
    t1 = ut_of(1973, 12, 4, 2, 26)
    rE, vE = S.helio("Earth", t0)
    rJ, vJ = S.helio("Jupiter", t1)
    v1, v2 = lambert(S.mu_sun, rE, rJ, t1 - t0)
    c3 = np.linalg.norm(np.array(v1) - np.array(vE)) ** 2 / 1e6
    vinf = np.linalg.norm(np.array(v2) - np.array(vJ)) / 1000
    print(f"Pioneer 10: C3={c3:.1f} km^2/s^2 (actual ~129), arrival vinf={vinf:.2f} km/s (actual ~9.2 hyperbolic excess)")
