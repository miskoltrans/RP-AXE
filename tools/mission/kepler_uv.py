"""Universal-variable Kepler propagator (Vallado). Works for ellipse, parabola, hyperbola."""
import numpy as np, math

def stumpff_c2c3(psi):
    if psi > 1e-6:
        s = math.sqrt(psi)
        return (1 - math.cos(s)) / psi, (s - math.sin(s)) / (s ** 3)
    if psi < -1e-6:
        s = math.sqrt(-psi)
        return (1 - math.cosh(s)) / psi, (math.sinh(s) - s) / (s ** 3)
    return 0.5, 1.0 / 6.0

def propagate(r0, v0, dt, mu, tol=1e-10, itmax=200):
    r0 = np.asarray(r0, float); v0 = np.asarray(v0, float)
    rn = np.linalg.norm(r0); vn = np.linalg.norm(v0)
    alpha = 2.0 / rn - vn * vn / mu           # 1/a
    if alpha > 1e-12:
        chi = math.sqrt(mu) * dt * alpha
    elif abs(alpha) < 1e-12:
        h = np.cross(r0, v0); p = float(h @ h) / mu
        s = 0.5 * math.atan(1.0 / (3.0 * math.sqrt(mu / p ** 3) * dt))
        t_ = math.tan(s)
        # tan(s) goes negative for dt < 0; a plain **(1/3) returns a complex root
        # and raises, which is how a perfectly good parabolic case looked like a bug.
        w = math.atan(math.copysign(abs(t_) ** (1.0 / 3.0), t_))
        chi = math.sqrt(p) * 2.0 / math.tan(2 * w)
    else:
        a = 1.0 / alpha
        num = -2 * mu * alpha * dt
        den = float(r0 @ v0) + math.copysign(1, dt) * math.sqrt(-mu * a) * (1 - rn * alpha)
        chi = math.copysign(1, dt) * math.sqrt(-a) * math.log(num / den)
    rdotv = float(r0 @ v0)
    for _ in range(itmax):
        psi = chi * chi * alpha
        c2, c3 = stumpff_c2c3(psi)
        r = chi * chi * c2 + rdotv / math.sqrt(mu) * chi * (1 - psi * c3) + rn * (1 - psi * c2)
        chi_new = chi + (math.sqrt(mu) * dt - chi ** 3 * c3 - rdotv / math.sqrt(mu) * chi ** 2 * c2
                         - rn * chi * (1 - psi * c3)) / r
        if abs(chi_new - chi) < tol:
            chi = chi_new
            break
        chi = chi_new
    psi = chi * chi * alpha
    c2, c3 = stumpff_c2c3(psi)
    r = chi * chi * c2 + rdotv / math.sqrt(mu) * chi * (1 - psi * c3) + rn * (1 - psi * c2)
    f = 1 - chi ** 2 / rn * c2
    g = dt - chi ** 3 / math.sqrt(mu) * c3
    gdot = 1 - chi ** 2 / r * c2
    fdot = math.sqrt(mu) / (r * rn) * chi * (psi * c3 - 1)
    return f * r0 + g * v0, fdot * r0 + gdot * v0
