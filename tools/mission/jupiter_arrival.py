"""Earth->Jupiter window trade for RP-AXE: departure cost, arrival geometry, capture cost.

Three things decide a Jovian mission and only one of them is the porkchop:

  * departure dv from a 185 km parking orbit (C3),
  * arrival v-infinity -> Jupiter orbit insertion at a chosen perijove,
  * arrival GEOMETRY -- the Sun-Earth-Jupiter elongation (a conjunction arrival means no
    downlink for weeks) and the declination of v-infinity above the moons' orbital plane,
    which is the floor on the capture orbit's inclination and therefore on how hard the
    Galilean tour is.

    python jupiter_arrival.py --dep-from 1964-01-01 --dep-to 1964-12-31
"""
import argparse
import math

import numpy as np

from lambert import lambert
from rss_ephem import System, date_of, ut_of

AU = 1.495978707e11
DAY = 86400.0


def plane_normal(body):
    i, l = body.inc, body.lan
    return np.array([math.sin(l) * math.sin(i), -math.cos(l) * math.sin(i), math.cos(i)])


class Jovian:
    def __init__(self, S):
        self.S = S
        self.J = S.bodies["Jupiter"]
        self.mu = self.J.mu
        self.R = self.J.radius
        self.n_eq = plane_normal(S.bodies["Ganymede"])

    def capture_dv(self, vinf, rp, ra):
        """Insertion burn at perijove rp into an ellipse with apojove ra."""
        v_hyp = math.sqrt(vinf ** 2 + 2 * self.mu / rp)
        a = (rp + ra) / 2
        v_ell = math.sqrt(self.mu * (2 / rp - 1 / a))
        return v_hyp - v_ell

    def v_apo(self, rp, ra):
        a = (rp + ra) / 2
        return math.sqrt(self.mu * (2 / ra - 1 / a))


def elongation(S, t):
    rE = np.array(S.helio("Earth", t)[0])
    rJ = np.array(S.helio("Jupiter", t)[0])
    a = -rE
    b = rJ - rE
    return math.degrees(math.acos(np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b)))


def evaluate(S, jov, td, tf, rp_rj=3.0, ra_km=20e6):
    mu = S.mu_sun
    muE = S.bodies["Earth"].mu
    rpark = S.bodies["Earth"].radius + 185e3
    ta = td + tf
    rE, vE = S.helio("Earth", td)
    rJ, vJ = S.helio("Jupiter", ta)
    v1, v2 = lambert(mu, np.array(rE), np.array(rJ), tf)
    vinf_dep = v1 - np.array(vE)
    vinf_arr = v2 - np.array(vJ)
    c3 = float(vinf_dep @ vinf_dep) / 1e6
    dv_dep = math.sqrt(2 * muE / rpark + c3 * 1e6) - math.sqrt(muE / rpark)
    vinf = float(np.linalg.norm(vinf_arr))
    rp = rp_rj * jov.R
    dv_cap = jov.capture_dv(vinf, rp, ra_km * 1e3)
    # declination of the incoming asymptote above the moons' plane == min capture inclination
    decl = math.degrees(math.asin(abs(float(np.dot(vinf_arr, jov.n_eq)) / vinf)))
    return dict(dep=td, tof=tf, arr=ta, c3=c3, dv_dep=dv_dep, vinf=vinf,
                dv_cap=dv_cap, total=dv_dep + dv_cap, incl=decl,
                dla=math.degrees(math.asin(vinf_dep[2] / np.linalg.norm(vinf_dep))),
                elong=elongation(S, ta))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dep-from", default="1964-03-01")
    ap.add_argument("--dep-to", default="1964-12-31")
    ap.add_argument("--tof", nargs=2, type=int, default=[800, 1400])
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--tofstep", type=int, default=10)
    ap.add_argument("--rp", type=float, default=3.0, help="capture perijove in Jupiter radii")
    ap.add_argument("--ra", type=float, default=20e6, help="capture apojove, km")
    ap.add_argument("--min-elong", type=float, default=0.0)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--sort", default="total", choices=["total", "c3", "vinf", "incl"])
    a = ap.parse_args()
    S = System()
    jov = Jovian(S)
    y, m, d = map(int, a.dep_from.split("-"))
    t0 = ut_of(y, m, d)
    y, m, d = map(int, a.dep_to.split("-"))
    t1 = ut_of(y, m, d)
    rows = []
    td = t0
    while td <= t1:
        for tof in range(a.tof[0], a.tof[1] + 1, a.tofstep):
            r = evaluate(S, jov, td, tof * DAY, a.rp, a.ra)
            if r["elong"] >= a.min_elong:
                rows.append(r)
        td += a.step * DAY
    rows.sort(key=lambda r: r[a.sort])
    print(f"capture: perijove {a.rp:.1f} Rj, apojove {a.ra/1e6:.1f}e6 km   filter: elongation >= {a.min_elong} deg")
    print(f"{'departure':>11s} {'TOF':>5s} {'arrival':>11s} {'C3':>6s} {'dvLEO':>6s} {'vinf':>5s} "
          f"{'dvJOI':>6s} {'TOTAL':>6s} {'incl':>5s} {'DLA':>6s} {'elong':>6s}")
    for r in rows[:a.top]:
        print(f"{str(date_of(r['dep']).date()):>11s} {r['tof']/DAY:5.0f} {str(date_of(r['arr']).date()):>11s} "
              f"{r['c3']:6.1f} {r['dv_dep']/1000:6.3f} {r['vinf']/1000:5.2f} {r['dv_cap']/1000:6.3f} "
              f"{r['total']/1000:6.3f} {r['incl']:5.1f} {r['dla']:6.1f} {r['elong']:6.1f}")


if __name__ == "__main__":
    main()
