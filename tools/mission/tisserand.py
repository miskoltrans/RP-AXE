"""Tisserand-graph feasibility for a moon ladder: does it close on assists alone?

`tour_plan.py` searches a tour you already believe is possible. This answers the question
upstream of it -- whether a chain of moons can be walked at all without propulsion -- and it
answers it in closed form, so a whole system screens in a second instead of a search.

MODEL. Moons are circular and coplanar about the parent. At a moon of orbital radius r_m and
speed v_m, a spacecraft is described by the v-infinity magnitude and the PUMP ANGLE alpha,
the in-plane angle between v-infinity and the moon's velocity:

    v_sc^2 = v_m^2 + vinf^2 + 2 v_m vinf cos(alpha)      (energy -> semi-major axis)
    v_t    = v_m + vinf cos(alpha)                        (h = r_m v_t -> eccentricity)

alpha = 0 is the fastest possible orbit at that radius, alpha = pi the slowest, and every
orbit reachable at that moon without a burn lies on that one curve: THE CONTOUR IS THE MOON'S
ENTIRE UNPOWERED REACH. An unpowered pass conserves vinf and moves alpha by at most the turn
angle

    delta_max = 2 asin(1 / (1 + r_fly vinf^2 / mu_moon))

so a ladder closes iff (a) the contour at the arrival vinf reaches far enough in -- its
minimum periapsis must fall to the next moon's radius -- and (b) the alpha that does it is
within a sensible number of delta_max steps of where you arrive.

WHAT IT DELIBERATELY DOES NOT MODEL. Phasing: whether the moon is actually THERE on the pass
that wants it, which is a resonance question and `tour_plan.py`'s job. So a "closes" here is
a necessary condition, not a flight plan -- it says the energy and the turn authority exist.
The answer in the other direction is the strong one: when this says a rung does NOT close, no
amount of searching will find it, because the contour is the complete unpowered reach.

    python tisserand.py ladder --parent Saturn --moons Rhea Dione Tethys Enceladus Mimas
    python tisserand.py ladder --parent Saturn --moons Rhea Dione --vinf 300:2500:100
    python tisserand.py contour --parent Saturn --moon Rhea --vinf 800
    python tisserand.py selftest
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

from rss_ephem import System


# --------------------------------------------------------------------------- core

def moon_params(system, parent, name):
    p = system.body(parent)
    b = system.body(name)
    return dict(name=name, mu_p=p.mu, mu=b.mu, r=b.a, R=b.radius, soi=b.soi,
                v=math.sqrt(p.mu / b.a), inc=b.inc, lan=b.lan)


def orbit_at(mu_p, r_m, v_m, vinf, alpha):
    """The parent-centric orbit produced by vinf at pump angle alpha. None if unbound."""
    v_sc2 = v_m * v_m + vinf * vinf + 2.0 * v_m * vinf * math.cos(alpha)
    v_t = v_m + vinf * math.cos(alpha)
    inv_a = 2.0 / r_m - v_sc2 / mu_p
    if inv_a <= 0.0:
        return None                                  # escapes the parent
    a = 1.0 / inv_a
    h = r_m * v_t
    e2 = 1.0 - h * h / (mu_p * a)
    e = math.sqrt(max(0.0, e2))
    return dict(a=a, e=e, rp=a * (1.0 - e), ra=a * (1.0 + e), h=h, v=math.sqrt(v_sc2))


def contour(mu_p, r_m, v_m, vinf, n=2001):
    """Every orbit reachable at this moon at this vinf, as alpha runs 0..pi."""
    out = []
    for alpha in np.linspace(0.0, math.pi, n):
        o = orbit_at(mu_p, r_m, v_m, vinf, float(alpha))
        if o is not None:
            o['alpha'] = float(alpha)
            out.append(o)
    return out


def turn_max(mu_m, r_fly, vinf):
    """Bend available in one unpowered pass at periapsis radius r_fly."""
    if vinf <= 0.0:
        return math.pi
    e = 1.0 + r_fly * vinf * vinf / mu_m
    return 2.0 * math.asin(1.0 / e)


def bend_dv(vinf, delta):
    """The burn that pass saved you: the chord of the rotation."""
    return 2.0 * vinf * math.sin(0.5 * delta)


def vinf_at_radius(mu_p, a, e, r, v_m_target):
    """vinf a given orbit hands you when it crosses radius r, against a circular moon there."""
    if r < a * (1.0 - e) - 1e-6 or (a > 0 and r > a * (1.0 + e) + 1e-6):
        return None                                   # the orbit never gets there
    v2 = mu_p * (2.0 / r - 1.0 / a)
    if v2 <= 0.0:
        return None
    h = math.sqrt(mu_p * a * max(0.0, 1.0 - e * e))
    v_t = h / r
    v_r2 = max(0.0, v2 - v_t * v_t)
    return math.sqrt(v_r2 + (v_t - v_m_target) ** 2)


def tisserand_param(mu_p, r_ref, a, e, inc=0.0):
    """Conserved across an unpowered pass at the reference moon. Used by selftest."""
    return r_ref / a + 2.0 * math.cos(inc) * math.sqrt((a / r_ref) * (1.0 - e * e))


# --------------------------------------------------------------------------- ladder

def rung(A, B, vinf_A, alt_km, n=4001):
    """One step: arrive at A with vinf_A, hand off to B. B may be inside or outside A."""
    r_fly = A['R'] + alt_km * 1e3
    dmax = turn_max(A['mu'], r_fly, vinf_A)
    cs = contour(A['mu_p'], A['r'], A['v'], vinf_A, n)
    if not cs:
        return dict(ok=False, why='vinf unbinds the orbit at %s' % A['name'], dmax=dmax)
    rp_min = min(c['rp'] for c in cs)
    ra_max = max(c['ra'] for c in cs)
    if rp_min > B['r']:
        return dict(ok=False, dmax=dmax, rp_min=rp_min, ra_max=ra_max,
                    deficit=rp_min - B['r'], outward=False,
                    why='contour bottoms out at %.1f Mm, %s is at %.1f Mm'
                        % (rp_min / 1e6, B['name'], B['r'] / 1e6))
    if ra_max < B['r']:
        return dict(ok=False, dmax=dmax, rp_min=rp_min, ra_max=ra_max,
                    deficit=B['r'] - ra_max, outward=True,
                    why='contour tops out at %.1f Mm, %s is at %.1f Mm'
                        % (ra_max / 1e6, B['name'], B['r'] / 1e6))
    best = None
    for c in cs:
        if c['rp'] > B['r'] or c['ra'] < B['r']:
            continue
        vb = vinf_at_radius(A['mu_p'], c['a'], c['e'], B['r'], B['v'])
        if vb is None:
            continue
        if best is None or vb < best['vinf_B']:
            best = dict(vinf_B=vb, **c)
    if best is None:
        return dict(ok=False, dmax=dmax, rp_min=rp_min,
                    why='no contour point crosses %s' % B['name'])
    # The alpha you ARRIVE with is set by the leg before, so the honest cost is the worst
    # case: alpha swept from the fast end (0) to the one wanted, in delta_max steps.
    passes = max(1, int(math.ceil(best['alpha'] / dmax))) if dmax > 0 else 999
    best.update(ok=True, dmax=dmax, passes=passes, rp_min=rp_min,
                dv_per_pass=bend_dv(vinf_A, dmax))
    return best


def patch_burn(A, B, vinf_A, n=4001):
    """Cheapest propulsive patch when the contour cannot reach B.

    Over every orbit on A's contour, price the APOAPSIS burn that lowers periapsis to B's
    radius, and keep the cheapest. Apoapsis is where that burn is cheapest, and the contour
    point with the deepest periapsis is not generally the one with the best apoapsis to burn
    at -- so this is a search over the contour, not an evaluation at its low point.
    """
    mu = A['mu_p']
    best = None
    for c in contour(mu, A['r'], A['v'], vinf_A, n):
        ra = c['ra']
        if ra <= B['r']:
            continue                                   # cannot reach out to burn usefully
        if c['rp'] <= B['r']:
            return dict(dv=0.0, free=True, rp=c['rp'], ra=ra, alpha=c['alpha'])
        a1 = 0.5 * (c['rp'] + ra)
        a2 = 0.5 * (B['r'] + ra)
        v1 = math.sqrt(mu * (2.0 / ra - 1.0 / a1))
        v2 = math.sqrt(mu * (2.0 / ra - 1.0 / a2))
        dv = abs(v1 - v2)
        if best is None or dv < best['dv']:
            best = dict(dv=dv, free=False, rp=c['rp'], ra=ra, alpha=c['alpha'])
    return best or dict(dv=float('inf'), free=False, rp=float('nan'), ra=float('nan'),
                        alpha=float('nan'))


def run_chain(system, parent, moons, vinf0, alt_km, max_passes=12):
    """Trace ONE vehicle down the ladder, carrying vinf from rung to rung."""
    M = [moon_params(system, parent, m) for m in moons]
    vinf = vinf0
    total_dv = 0.0
    total_passes = 0
    print("chain: arrive %s at vinf %.0f m/s, flyby floor %.0f km altitude\n"
          % (M[0]['name'], vinf0, alt_km))
    print("%-22s%9s%11s%9s%10s%9s%9s"
          % ('rung', 'vinf@A', 'turn/pass', 'passes', 'rp_min', 'patch dv', 'vinf@B'))
    for i in range(len(M) - 1):
        A, B = M[i], M[i + 1]
        r = rung(A, B, vinf, alt_km)
        label = "%s -> %s" % (A['name'], B['name'])
        if r['ok']:
            total_passes += r['passes']
            print("%-22s%9.0f%10.2fd%9d%10.1f%9s%9.0f"
                  % (label, vinf, math.degrees(r['dmax']), r['passes'],
                     r['rp_min'] / 1e6, '-', r['vinf_B']))
            vinf = r['vinf_B']
            continue
        p = patch_burn(A, B, vinf)
        total_dv += p['dv']
        total_passes += 1
        # after the patch the orbit has rp = B.r; the vinf it hands B follows from that orbit
        a2 = 0.5 * (B['r'] + p['ra'])
        e2 = (p['ra'] - B['r']) / (p['ra'] + B['r'])
        vb = vinf_at_radius(A['mu_p'], a2, e2, B['r'], B['v'])
        print("%-22s%9.0f%10.2fd%9s%10.1f%9.0f%9.0f   BROKEN -- %s"
              % (label, vinf, math.degrees(r['dmax']), '-', r['rp_min'] / 1e6,
                 p['dv'], vb if vb else float('nan'), r['why']))
        vinf = vb if vb else vinf
    print("\ntotal propulsive patch: %.0f m/s over %d flyby passes" % (total_dv, total_passes))
    return total_dv


def run_ladder(system, parent, moons, vinfs, alt_km):
    M = [moon_params(system, parent, m) for m in moons]
    print("parent %s: mu=%.5g" % (parent, M[0]['mu_p']))
    print("%-11s%9s%8s%9s%11s%10s" % ('moon', 'a (Mm)', 'v_orb', 'R (km)', 'mu', 'SOI (km)'))
    for m in M:
        print("%-11s%9.1f%8.0f%9.1f%11.4g%10.0f"
              % (m['name'], m['r'] / 1e6, m['v'], m['R'] / 1e3, m['mu'], m['soi'] / 1e3))
    print()
    for i in range(len(M) - 1):
        A, B = M[i], M[i + 1]
        print("=== %s -> %s   (%.0f -> %.0f Mm) ==="
              % (A['name'], B['name'], A['r'] / 1e6, B['r'] / 1e6))
        print("%8s%11s%9s%10s%9s%10s%8s%8s%9s  verdict"
              % ('vinf@A', 'turn/pass', 'dv/pass', 'rp_min', 'rp*', 'ra*',
                 'alpha*', 'passes', 'vinf@B'))
        for vinf in vinfs:
            r = rung(A, B, vinf, alt_km)
            dm = math.degrees(r.get('dmax', 0.0))
            dv = bend_dv(vinf, r.get('dmax', 0.0))
            if not r['ok']:
                rpm = r.get('rp_min', float('nan')) / 1e6
                print("%8.0f%10.2fd%9.0f%10.1f%9s%10s%8s%8s%9s  NO -- %s"
                      % (vinf, dm, dv, rpm, '', '', '', '', '', r['why']))
                continue
            print("%8.0f%10.2fd%9.0f%10.1f%9.1f%10.1f%7.1fd%8d%9.0f  %s"
                  % (vinf, dm, dv, r['rp_min'] / 1e6, r['rp'] / 1e6, r['ra'] / 1e6,
                     math.degrees(r['alpha']), r['passes'], r['vinf_B'],
                     'closes' if r['passes'] <= 12 else 'closes (many passes)'))
        print()


# --------------------------------------------------------------------------- selftest

def selftest(system):
    ok = True

    def chk(name, cond, extra=''):
        nonlocal ok
        ok = ok and bool(cond)
        print("  [%s] %s %s" % ('PASS' if cond else 'FAIL', name, extra))

    S = moon_params(system, 'Saturn', 'Rhea')
    mu_p = S['mu_p']

    o = orbit_at(mu_p, S['r'], S['v'], 800.0, math.pi / 2)
    chk('alpha=90deg keeps r_m between rp and ra',
        o['rp'] <= S['r'] + 1 and o['ra'] >= S['r'] - 1,
        "rp=%.1f r_m=%.1f ra=%.1f Mm" % (o['rp'] / 1e6, S['r'] / 1e6, o['ra'] / 1e6))

    v_back = vinf_at_radius(mu_p, o['a'], o['e'], S['r'], S['v'])
    chk('vinf round-trips through the orbit', abs(v_back - 800.0) < 1e-6,
        "%.6f m/s" % v_back)

    ts = [tisserand_param(mu_p, S['r'], c['a'], c['e'])
          for c in contour(mu_p, S['r'], S['v'], 800.0, 201)]
    chk('Tisserand parameter constant along a contour',
        max(ts) - min(ts) < 1e-9, "spread %.2e" % (max(ts) - min(ts)))

    chk('turn angle falls as vinf rises',
        turn_max(S['mu'], S['R'], 500) > turn_max(S['mu'], S['R'], 2000))

    T = moon_params(system, 'Saturn', 'Titan')
    chk('Titan out-turns Rhea at equal vinf',
        turn_max(T['mu'], T['R'], 1000) > turn_max(S['mu'], S['R'], 1000),
        "%.1fd vs %.1fd" % (math.degrees(turn_max(T['mu'], T['R'], 1000)),
                            math.degrees(turn_max(S['mu'], S['R'], 1000))))

    c0 = orbit_at(mu_p, S['r'], S['v'], 600.0, 0.0)
    cp = orbit_at(mu_p, S['r'], S['v'], 600.0, math.pi)
    chk('alpha=0 raises apoapsis, alpha=pi lowers periapsis',
        c0['ra'] > S['r'] and cp['rp'] < S['r'],
        "ra=%.0f Mm, rp=%.0f Mm" % (c0['ra'] / 1e6, cp['rp'] / 1e6))

    print("\n%s" % ('ALL PASS' if ok else 'FAILURES'))
    return 0 if ok else 1


# --------------------------------------------------------------------------- cli

def parse_vinfs(spec):
    if ':' in spec:
        lo, hi, step = (float(x) for x in spec.split(':'))
        n = int(round((hi - lo) / step)) + 1
        return [lo + i * step for i in range(n)]
    return [float(x) for x in spec.split(',')]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=['ladder', 'chain', 'contour', 'selftest'])
    ap.add_argument('--parent', default='Saturn')
    ap.add_argument('--moons', nargs='+', default=[])
    ap.add_argument('--moon', default=None)
    ap.add_argument('--vinf', default='400:2400:200')
    ap.add_argument('--alt', type=float, default=50.0, help='flyby altitude floor, km')
    ap.add_argument('--install', default=None)
    a = ap.parse_args()

    system = System(a.install) if a.install else System()

    if a.mode == 'selftest':
        return selftest(system)
    if a.mode == 'chain':
        vs = parse_vinfs(a.vinf)
        for v in vs:
            run_chain(system, a.parent, a.moons, v, a.alt)
            print()
        return 0
    if a.mode == 'contour':
        m = moon_params(system, a.parent, a.moon)
        for vinf in parse_vinfs(a.vinf):
            dmax = turn_max(m['mu'], m['R'] + a.alt * 1e3, vinf)
            print("--- %s vinf %.0f m/s   turn/pass %.2f deg (%.0f m/s)"
                  % (a.moon, vinf, math.degrees(dmax), bend_dv(vinf, dmax)))
            print("%7s%10s%11s%10s%8s" % ('alpha', 'rp (Mm)', 'ra (Mm)', 'a (Mm)', 'e'))
            for c in contour(m['mu_p'], m['r'], m['v'], vinf, 19):
                print("%7.1f%10.1f%11.1f%10.1f%8.4f"
                      % (math.degrees(c['alpha']), c['rp'] / 1e6, c['ra'] / 1e6,
                         c['a'] / 1e6, c['e']))
        return 0
    run_ladder(system, a.parent, a.moons, parse_vinfs(a.vinf), a.alt)
    return 0


if __name__ == '__main__':
    sys.exit(main())
