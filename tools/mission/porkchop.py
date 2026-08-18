"""Ballistic transfer scan (porkchop) between two bodies, on the install's own ephemeris.

    python porkchop.py Earth Jupiter 1964-01-01 1972-01-01 --tof 300 1600

Reports, per launch window, the minimum-C3 and minimum-total solutions with departure Δv from a
185 km parking orbit, arrival v-infinity, and the declination of the launch asymptote.
"""
import argparse
import datetime as dt

import numpy as np

from lambert import lambert
from rss_ephem import System, ut_of, date_of

AU = 1.495978707e11
DAY = 86400.0


def parse_date(s):
    y, m, d = (int(x) for x in s.split("-"))
    return ut_of(y, m, d)


def scan(S, dep_body, arr_body, t0, t1, tof_lo, tof_hi, dep_step=5.0, tof_step=5.0, r_park=None):
    """Return a record array over the (departure, tof) grid."""
    mu = S.mu_sun
    deps = np.arange(t0, t1, dep_step * DAY)
    tofs = np.arange(tof_lo, tof_hi, tof_step) * DAY
    dep_r = np.array([S.helio(dep_body, t)[0] for t in deps])
    dep_v = np.array([S.helio(dep_body, t)[1] for t in deps])
    out = np.full((len(deps), len(tofs), 4), np.nan)  # c3, vinf_arr, dla, dv_park
    mu_dep = S.bodies[dep_body].mu
    if r_park is None:
        r_park = S.bodies[dep_body].radius + 185e3
    v_circ = np.sqrt(mu_dep / r_park)
    for i, td in enumerate(deps):
        for j, tf in enumerate(tofs):
            ta = td + tf
            ra, va = S.helio(arr_body, ta)
            try:
                v1, v2 = lambert(mu, dep_r[i], np.array(ra), tf)
            except Exception:
                continue
            vinf_dep = v1 - dep_v[i]
            c3 = float(vinf_dep @ vinf_dep) / 1e6
            out[i, j, 0] = c3
            out[i, j, 1] = float(np.linalg.norm(v2 - np.array(va))) / 1000
            n = np.linalg.norm(vinf_dep)
            out[i, j, 2] = np.degrees(np.arcsin(np.clip(vinf_dep[2] / n, -1, 1)))
            out[i, j, 3] = (np.sqrt(2 * mu_dep / r_park + c3 * 1e6) - v_circ) / 1000
    return deps, tofs, out


def windows(deps, tofs, out, top=12, sep_days=200):
    """Pick local minima in C3, one per launch window."""
    c3 = out[:, :, 0]
    best_per_dep = np.nanmin(np.where(np.isnan(c3), np.inf, c3), axis=1)
    picked = []
    order = np.argsort(best_per_dep)
    for i in order:
        if not np.isfinite(best_per_dep[i]):
            continue
        if any(abs(deps[i] - deps[k]) < sep_days * DAY for k in picked):
            continue
        picked.append(i)
        if len(picked) >= top:
            break
    return sorted(picked, key=lambda i: deps[i])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dep")
    ap.add_argument("arr")
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--tof", nargs=2, type=float, default=[300, 1600])
    ap.add_argument("--step", type=float, default=5.0)
    ap.add_argument("--tofstep", type=float, default=5.0)
    ap.add_argument("--gamedata", default=r"C:/git/ksp/Instance/GameData")
    a = ap.parse_args()
    S = System(a.gamedata)
    deps, tofs, out = scan(S, a.dep, a.arr, parse_date(a.start), parse_date(a.end),
                           a.tof[0], a.tof[1], a.step, a.tofstep)
    print(f"{a.dep} -> {a.arr}   grid {len(deps)} departures x {len(tofs)} TOFs")
    print(f"{'departure':>12s} {'TOF d':>6s} {'C3':>7s} {'dv185':>7s} {'vinf_a':>7s} {'DLA':>6s}  {'arrival':>12s}")
    for i in windows(deps, tofs, out):
        j = int(np.nanargmin(np.where(np.isnan(out[i, :, 0]), np.inf, out[i, :, 0])))
        c3, vinf, dla, dv = out[i, j]
        print(f"{str(date_of(deps[i]).date()):>12s} {tofs[j]/DAY:6.0f} {c3:7.1f} {dv:7.3f} {vinf:7.2f} {dla:6.1f}  "
              f"{str(date_of(deps[i]+tofs[j]).date()):>12s}")


if __name__ == "__main__":
    main()
