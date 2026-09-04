"""Multiple-gravity-assist sequence search: Lambert legs joined by v-infinity matching.

The rest of this toolchain refines a trajectory you already have. This finds one from
nothing: given a body sequence and a date window per body, it scans every leg with
Lambert and then runs a dynamic program over *pairs* of encounter dates, because that
is exactly the state a flyby couples -- the leg before it sets v-infinity in, the leg
after it sets v-infinity out, and the flyby itself can only rotate the vector, never
lengthen it.

    python mga.py Earth Jupiter Saturn Uranus Neptune
        --win Earth 1976-01-01 1979-06-01 --step Earth 10
        --win Jupiter 1978-01-01 1981-06-01 --step Jupiter 20
        ...

Three things this models that a chain of Lambert arcs does not:

  * A flyby's turn angle is bounded. delta_max = asin(1/e_in) + asin(1/e_out) with
    e = 1 + rp*v_inf^2/mu, and rp cannot go below the body's surface. Ask for more
    bend than that and the sequence is not free, whatever the Lambert legs say.
  * v-infinity magnitude is conserved by an unpowered flyby. Any mismatch between the
    incoming and outgoing legs is a real burn at periapsis, priced with Oberth.
  * The AXE flyby contracts cap periapsis ALTITUDE. A gravity assist that needs to
    pass at 10 Rj cannot also bank a 150,000 km Jupiter flyby, so the cap is carried
    per body and reported, never silently assumed.

Costs are heliocentric patched-conic estimates, for RANKING sequences. The winner still
goes through patched.shoot / maneuver.aim_through before anyone believes a number.
"""
import argparse
import math

import numpy as np

from lambert import lambert
from rss_ephem import System, date_of, parse_date

DAY = 86400.0
AU = 1.495978707e11


# --------------------------------------------------------------------------- flyby
def turn_max(mu, rp, v1, v2):
    """Largest angle an unpowered pass at periapsis radius rp can bend v_inf through."""
    e1 = 1.0 + rp * v1 * v1 / mu
    e2 = 1.0 + rp * v2 * v2 / mu
    return math.asin(1.0 / e1) + math.asin(1.0 / e2)


def flyby(mu, vin, vout, rp_min, rp_cap=None, reject_dv=None):
    """Cost of joining v_inf `vin` to v_inf `vout` at one body.

    Returns (dv, rp, turn_needed, turn_available_at_rp_min).
    """
    v1 = float(np.linalg.norm(vin))
    v2 = float(np.linalg.norm(vout))
    if not (v1 > 0 and v2 > 0):
        return math.inf, math.nan, math.nan, math.nan
    c = float(np.dot(vin, vout)) / (v1 * v2)
    delta = math.acos(max(-1.0, min(1.0, c)))
    if reject_dv is not None and abs(v2 - v1) > reject_dv:
        # |v_inf| is conserved by the pass itself, so a magnitude mismatch is already a
        # lower bound on the burn -- cheap enough to test before any root finding.
        return math.inf, math.nan, math.nan, math.nan
    d_min = turn_max(mu, rp_min, v1, v2)          # most bend available
    if delta > d_min:
        # cannot bend far enough even skimming the surface: pay the shortfall.
        short = delta - d_min
        dv = math.sqrt(v1 * v1 + v2 * v2 - 2 * v1 * v2 * math.cos(short))
        return dv, rp_min, delta, d_min
    # bend is achievable; find the rp that delivers exactly this much turning
    lo = hi = rp_min
    for _ in range(200):
        hi *= 1.5
        if turn_max(mu, hi, v1, v2) < delta:
            break
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        if turn_max(mu, mid, v1, v2) > delta:
            lo = mid
        else:
            hi = mid
    rp = math.sqrt(lo * hi)
    # a magnitude change is bought at periapsis, with Oberth
    dv = abs(math.sqrt(v2 * v2 + 2 * mu / rp) - math.sqrt(v1 * v1 + 2 * mu / rp))
    if rp_cap is not None and rp > rp_cap:
        # the contract wants a closer pass than the bend needs: fly at the cap, which
        # over-bends, and pay to take the excess turn back out.
        excess = turn_max(mu, rp_cap, v1, v2) - delta
        dv += 2.0 * v2 * math.sin(min(math.pi, max(0.0, excess)) / 2.0)
        rp = rp_cap
    return dv, rp, delta, d_min


def capture_dv(mu, radius, soi, vinf, rp_R=1.5, ra_frac=0.9):
    """Cheapest burn from an arrival hyperbola into a bound orbit at this body.

    Apoapsis goes just inside the SOI because that is always the cheapest capture -- and
    the AXE `orbit*` contracts gate on PERIAPSIS (maxPeA = 2 * radius), never on period,
    so there is no reason to spend Oberth pulling the far side back down.
    """
    rp = rp_R * radius
    ra = ra_frac * soi
    a = (rp + ra) / 2.0
    return (math.sqrt(vinf * vinf + 2 * mu / rp)
            - math.sqrt(mu * (2.0 / rp - 1.0 / a)))


def escape_dv(mu, r_park, vinf):
    """Injection burn from a circular parking orbit onto a hyperbola with this v_inf."""
    return math.sqrt(vinf * vinf + 2 * mu / r_park) - math.sqrt(mu / r_park)


# --------------------------------------------------------------------------- legs
def leg_table(S, b1, b2, t1, t2, revs=(0,)):
    """v_dep and v_arr (heliocentric) for every (t1, t2) pair. NaN where none."""
    mu = S.mu_sun
    r1 = np.array([S.helio(b1, t)[0] for t in t1])
    r2 = np.array([S.helio(b2, t)[0] for t in t2])
    n1, n2 = len(t1), len(t2)
    vd = np.full((n1, n2, 3), np.nan)
    va = np.full((n1, n2, 3), np.nan)
    for i in range(n1):
        for j in range(n2):
            tof = t2[j] - t1[i]
            if tof <= 0:
                continue
            best = None
            for M in revs:
                for low in ((True,) if M == 0 else (True, False)):
                    try:
                        v1, v2 = lambert(mu, r1[i], r2[j], tof, M=M, lowpath=low)
                    except Exception:
                        continue
                    if not np.all(np.isfinite(v1)):
                        continue
                    score = float(np.linalg.norm(v1))
                    if best is None or score < best[0]:
                        best = (score, v1, v2)
            if best is not None:
                vd[i, j] = best[1]
                va[i, j] = best[2]
    return vd, va


# --------------------------------------------------------------------------- search
class Sequence:
    def __init__(self, system, bodies, grids, rp_min_frac=1.05, rp_cap=None,
                 park_alt=185e3, revs=(0,), capture_rp_R=None):
        self.S = system
        self.bodies = list(bodies)
        self.grids = [np.asarray(g, dtype=float) for g in grids]
        self.rp_cap = dict(rp_cap or {})
        if isinstance(rp_min_frac, dict):
            self.rp_min = {b: self.S.bodies[b].radius * rp_min_frac.get(b, 1.05)
                           for b in self.bodies}
        else:
            self.rp_min = {b: self.S.bodies[b].radius * rp_min_frac for b in self.bodies}
        self.park_alt = park_alt
        self.capture_rp_R = capture_rp_R
        self.legs = [leg_table(self.S, self.bodies[k], self.bodies[k + 1],
                               self.grids[k], self.grids[k + 1], revs=revs)
                     for k in range(len(self.bodies) - 1)]
        self.vbody = [np.array([self.S.helio(b, t)[1] for t in g])
                      for b, g in zip(self.bodies, self.grids)]

    def departure(self):
        b = self.S.bodies[self.bodies[0]]
        rpark = b.radius + self.park_alt
        vd, _ = self.legs[0]
        vinf = vd - self.vbody[0][:, None, :]
        c3 = np.sum(vinf * vinf, axis=2)
        dv = np.sqrt(c3 + 2 * b.mu / rpark) - math.sqrt(b.mu / rpark)
        return dv, c3

    def run(self, keep=40, max_c3=None, max_dv_leg=400.0):
        """Dynamic program over (t_k, t_k+1) states. Returns ranked (cost, path)."""
        dep_dv, c3 = self.departure()
        n0, n1 = dep_dv.shape
        states = {}
        for j in range(n1):
            col = []
            for i in range(n0):
                if not np.isfinite(dep_dv[i, j]):
                    continue
                if max_c3 is not None and c3[i, j] > max_c3:
                    continue
                col.append((float(dep_dv[i, j]), i))
            col.sort()
            for cost, i in col[:keep]:
                states[(i, j)] = (cost, (i, j))
        for k in range(1, len(self.bodies) - 1):
            body = self.S.bodies[self.bodies[k]]
            cap = self.rp_cap.get(self.bodies[k])
            va_prev = self.legs[k - 1][1]
            vd_next = self.legs[k][0]
            n_next = vd_next.shape[1]
            by_mid = {}
            for key, val in states.items():
                by_mid.setdefault(key[1], []).append((key[0], val))
            nxt = {}
            for j, entries in by_mid.items():
                vbody = self.vbody[k][j]
                for m in range(n_next):
                    vout = vd_next[j, m]
                    if not np.isfinite(vout[0]):
                        continue
                    vinf_out = vout - vbody
                    for i, (cost, path) in entries:
                        vin = va_prev[i, j]
                        if not np.isfinite(vin[0]):
                            continue
                        dv, rp, need, avail = flyby(body.mu, vin - vbody, vinf_out,
                                                    self.rp_min[self.bodies[k]], cap,
                                                    reject_dv=max_dv_leg)
                        if not np.isfinite(dv):
                            continue
                        if max_dv_leg is not None and dv > max_dv_leg:
                            continue
                        total = cost + dv
                        cur = nxt.get((j, m))
                        if cur is None or total < cur[0]:
                            nxt[(j, m)] = (total, path + (m,))
            # keep the best `keep` ways of reaching each encounter date at body k+1
            by_arrival = {}
            for key, val in nxt.items():
                by_arrival.setdefault(key[1], []).append((key, val))
            states = {}
            for m, lst in by_arrival.items():
                lst.sort(key=lambda e: e[1][0])
                for key, val in lst[:keep]:
                    states[key] = val
            if not states:
                return []
        if self.capture_rp_R is not None:
            last = self.S.bodies[self.bodies[-1]]
            va_last = self.legs[-1][1]
            priced = {}
            for key, (cost, path) in states.items():
                vin = va_last[path[-2], path[-1]] - self.vbody[-1][path[-1]]
                dv = capture_dv(last.mu, last.radius, last.soi,
                                float(np.linalg.norm(vin)), self.capture_rp_R)
                priced[key] = (cost + dv, path)
            states = priced
        out = sorted(states.values(), key=lambda e: e[0])
        return [(c, p) for c, p in out]

    def detail(self, path):
        S = self.S
        ts = [self.grids[k][path[k]] for k in range(len(self.bodies))]
        rows = []
        b0 = S.bodies[self.bodies[0]]
        rpark = b0.radius + self.park_alt
        vinf0 = self.legs[0][0][path[0], path[1]] - self.vbody[0][path[0]]
        c3 = float(np.dot(vinf0, vinf0))
        dv0 = escape_dv(b0.mu, rpark, math.sqrt(c3))
        total = dv0
        rows.append(dict(kind="depart", body=self.bodies[0], ut=ts[0], c3=c3, tof=0.0,
                         vinf=math.sqrt(c3), dv=dv0,
                         dla=math.degrees(math.asin(vinf0[2] / math.sqrt(c3)))))
        for k in range(1, len(self.bodies)):
            vin = self.legs[k - 1][1][path[k - 1], path[k]] - self.vbody[k][path[k]]
            vin_m = float(np.linalg.norm(vin))
            r_au = float(np.linalg.norm(S.helio(self.bodies[k], ts[k])[0])) / AU
            body = S.bodies[self.bodies[k]]
            if k == len(self.bodies) - 1:
                dv_cap = 0.0
                if self.capture_rp_R is not None:
                    dv_cap = capture_dv(body.mu, body.radius, body.soi, vin_m,
                                        self.capture_rp_R)
                    total += dv_cap
                rows.append(dict(kind="arrive", body=self.bodies[k], ut=ts[k],
                                 vinf=vin_m, dv=dv_cap, r_au=r_au,
                                 capture=self.capture_rp_R,
                                 tof=(ts[k] - ts[k - 1]) / DAY))
                break
            vout = self.legs[k][0][path[k], path[k + 1]] - self.vbody[k][path[k]]
            dv, rp, need, avail = flyby(body.mu, vin, vout, self.rp_min[self.bodies[k]],
                                        self.rp_cap.get(self.bodies[k]))
            total += dv
            rows.append(dict(kind="flyby", body=self.bodies[k], ut=ts[k], vinf_in=vin_m,
                             tof=(ts[k] - ts[k - 1]) / DAY,
                             vinf_out=float(np.linalg.norm(vout)), dv=dv, rp=rp,
                             rp_R=rp / body.radius, alt=rp - body.radius,
                             turn=math.degrees(need), turn_max=math.degrees(avail),
                             r_au=r_au))
        return rows, total


def fmt(rows, total):
    out = []
    for r in rows:
        d = date_of(r["ut"]).strftime("%Y-%m-%d")
        if r["kind"] == "depart":
            out.append(f"  {d}  depart {r['body']:8s} C3 {r['c3']/1e6:7.2f} km2/s2  "
                       f"v_inf {r['vinf']/1e3:5.2f} km/s  DLA {r['dla']:+6.2f} deg  "
                       f"dv {r['dv']:7.0f} m/s")
        elif r["kind"] == "flyby":
            out.append(f"  {d}  flyby  {r['body']:8s} v_inf {r['vinf_in']/1e3:5.2f}->"
                       f"{r['vinf_out']/1e3:5.2f} km/s  turn {r['turn']:5.1f}/"
                       f"{r['turn_max']:5.1f} deg  rp {r['rp_R']:6.2f} R "
                       f"({r['alt']/1e3:10,.0f} km alt)  dv {r['dv']:6.0f}   {r['r_au']:5.2f} AU"
                       f"  +{r['tof']/365.25:4.2f} yr")
        else:
            cap = (f"  CAPTURE at {r['capture']:.1f} R: {r['dv']:7,.0f} m/s      "
                   if r.get("capture") else f"{'':47s}")
            out.append(f"  {d}  arrive {r['body']:8s} v_inf {r['vinf']/1e3:5.2f} km/s"
                       f"{cap}{r['r_au']:5.2f} AU  +{r['tof']/365.25:4.2f} yr")
    span = (rows[-1]["ut"] - rows[0]["ut"]) / DAY / 365.25
    out.append(f"  TOTAL deterministic dv {total:,.0f} m/s over {span:.2f} yr")
    return "\n".join(out)


def build_grid(lo, hi, step_days):
    return np.arange(parse_date(lo), parse_date(hi) + 1, step_days * DAY)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bodies", nargs="+")
    ap.add_argument("--win", nargs=3, action="append", metavar=("BODY", "FROM", "TO"),
                    required=True)
    ap.add_argument("--step", nargs=2, action="append", metavar=("BODY", "DAYS"),
                    default=[])
    ap.add_argument("--cap", nargs=2, action="append", metavar=("BODY", "ALT_KM"),
                    default=[], help="contract periapsis ALTITUDE cap, km")
    ap.add_argument("--rp-min", type=float, default=1.05,
                    help="closest allowed pass, in body radii (default 1.05)")
    ap.add_argument("--rp-min-body", nargs=2, action="append", default=[],
                    metavar=("BODY", "RADII"), help="per-body override of --rp-min")
    ap.add_argument("--by-arrival", action="store_true",
                    help="show the cheapest tour for each final-arrival date instead of "
                         "the globally cheapest few")
    ap.add_argument("--max-c3", type=float, default=None, help="km2/s2")
    ap.add_argument("--capture", type=float, nargs="?", const=1.5, default=None,
                    metavar="RP_RADII",
                    help="price an orbit insertion at the final body (periapsis in body "
                         "radii, default 1.5) and rank on injection + assists + capture")
    ap.add_argument("--keep", type=int, default=40)
    ap.add_argument("--max-dv-flyby", type=float, default=400.0,
                    help="reject a flyby needing more than this, m/s")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--instance", default=None)
    a = ap.parse_args()

    S = System(a.instance) if a.instance else System()
    wins = {w[0]: (w[1], w[2]) for w in a.win}
    steps = {s[0]: float(s[1]) for s in a.step}
    caps = {c[0]: S.bodies[c[0]].radius + float(c[1]) * 1e3 for c in a.cap}
    grids = [build_grid(*wins[b], steps.get(b, 20.0)) for b in a.bodies]
    print("grid: " + "  ".join(f"{b}:{len(g)}" for b, g in zip(a.bodies, grids)))
    rpmin = {b: a.rp_min for b in a.bodies}
    rpmin.update({b: float(v) for b, v in a.rp_min_body})
    seq = Sequence(S, a.bodies, grids, rp_min_frac=rpmin, rp_cap=caps,
                   capture_rp_R=a.capture)
    sols = seq.run(keep=a.keep, max_dv_leg=a.max_dv_flyby,
                   max_c3=None if a.max_c3 is None else a.max_c3 * 1e6)
    print(f"{len(sols)} surviving sequences\n")
    seen = set()
    shown = 0
    for cost, path in sols:
        key = path[-1] if a.by_arrival else path[:2]
        if key in seen:
            continue
        seen.add(key)
        rows, total = seq.detail(path)
        print(fmt(rows, total))
        print()
        shown += 1
        if shown >= a.top:
            break


if __name__ == "__main__":
    main()
