"""Saturnalija tour: the apoapsis burn that puts the captured orbiter onto the Titan ladder.

`python saturn_tour.py apo [--push] [--alt 1000]`

The burn near apoapsis of the capture ellipse raises periapsis and rotates the plane so that the
following periapsis pass is a real Titan encounter. The seed is EXACT in two-body terms: for a
candidate encounter epoch t_k, the new plane is span(burn point, Titan at t_k), the apsidal line
stays along the burn point, and the periapsis is solved so the orbit crosses Titan's radius at
Titan's direction at t_k (burn time iterated). The epoch is scanned continuously over ~5 Titan
revolutions, the lowest-v_inf seeds are least-squares corrected on the FLOWN trajectory
(patched.shoot through Titan's SOI), the B-plane angle is scanned for a Titan resonance, and the
aimed solution is pushed through the bridge.

WHY v_inf IS ~4,500 AND NOT THE DESIGN'S 2,708: the capture orbit's line of apsides is 21 deg out
of Titan's plane, so no single burn at apoapsis can make the orbit coplanar with Titan, and the
planes that do reach Titan cross its orbit at a steep flight-path angle. The design's "fold the
plane change into the apoapsis burn" needed the capture periapsis aimed INTO the moons' plane at
arrival; that aim was spent on minimum inclination instead. See rp-axe-saturn-mission memory.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

import astro
import bridge as bridge_mod
import maneuver
import patched
from rss_ephem import DAY, System, fmt_ut

VID = "744a14e4-901e-446b-a9a1-d108bf2f01c0"
PUSH = "--push" in sys.argv
ALT_KM = float(sys.argv[sys.argv.index("--alt") + 1]) if "--alt" in sys.argv else 1000.0

system = System()
sat, titan = system.body("Saturn"), system.body("Titan")
MU = sat.mu
T_TITAN = 2 * math.pi * math.sqrt(titan.a ** 3 / MU)
V_TITAN = math.sqrt(MU / titan.a)
PER_WANT = titan.radius + ALT_KM * 1e3

br = bridge_mod.Bridge()
info = br.nodes(vid=VID)
if not info.get("nodes_available"):
    sys.exit(f"not the active vessel: {info.get('why')}")
body, r0, v0, ut0 = br.state(system, vid=VID)
assert body.name == "Saturn"
el0 = astro.elements(MU, r0, v0)
n0 = math.sqrt(MU / el0.sma ** 3)
tp0 = ut0 - el0.mna / n0                        # last periapsis
t_apo = tp0 + el0.period / 2
print(f"live {info['vessel']} {fmt_ut(ut0)}: {el0.peR / 1e3:,.0f} x {el0.apR / 1e6:,.0f} Mm, i {math.degrees(el0.inc):.3f}, "
      f"period {el0.period / DAY:,.1f} d, apoapsis {fmt_ut(t_apo)}  (T+{(t_apo - ut0) / DAY:.0f} d)")


def unit(x):
    x = np.asarray(x, float)
    return x / np.linalg.norm(x)


def titan_normal(ut):
    r, v = system.rel("Titan", ut)
    return unit(np.cross(r, v))


def rel_inc(r, v, ut):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(unit(np.cross(r, v)) @ titan_normal(ut))))))


def post_flyby(rep_patch, ut_exit):
    """Saturn-centric elements after leaving Titan's SOI."""
    r, v = rep_patch.state(ut_exit)
    rt, vt = system.rel("Titan", ut_exit)
    rs, vs = np.asarray(r) + np.asarray(rt), np.asarray(v) + np.asarray(vt)
    return astro.elements(MU, rs, vs), rs, vs


# ------------------------------------------------------------------ exact two-body seed for a Titan encounter at t_k
def anomaly_time(a, e, nu):
    """Time from periapsis to true anomaly nu (elliptic)."""
    E = 2 * math.atan2(math.sqrt(1 - e) * math.sin(nu / 2), math.sqrt(1 + e) * math.cos(nu / 2))
    M = E - e * math.sin(E)
    return M / math.sqrt(MU / a ** 3)


def seed_for(t_k):
    """Burn near apoapsis whose orbit passes through Titan's position at t_k.

    Plane = span(burn point, Titan); apsidal line stays along the burn point; periapsis solved so
    the orbit crosses Titan's radius exactly at Titan's direction. Iterates the burn time so the
    arrival at Titan is t_k. Returns None if no elliptic solution exists.
    """
    Q, vT = (np.asarray(x, float) for x in system.rel("Titan", t_k))
    rq, q_hat = float(np.linalg.norm(Q)), unit(Q)
    t_b = t_apo
    for _ in range(8):
        P, vP = astro.propagate(MU, r0, v0, t_b - ut0)
        ra, p_hat = float(np.linalg.norm(P)), unit(P)
        cosang = float(p_hat @ q_hat)
        nu_q = math.pi - math.acos(max(-1.0, min(1.0, cosang)))     # true anomaly of Q, apsides along P
        cq = math.cos(nu_q)

        def f(rp):
            e = (ra - rp) / (ra + rp)
            return rp * (1 + e) / (1 + e * cq) - rq
        lo, hi = 0.05e9, rq
        if f(lo) > 0 or f(hi) < 0:
            return None
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if f(mid) < 0:
                lo = mid
            else:
                hi = mid
        rp = 0.5 * (lo + hi)
        a_new = 0.5 * (ra + rp)
        e = (ra - rp) / (ra + rp)
        n_hat = unit(np.cross(p_hat, q_hat))
        v_dir = unit(np.cross(n_hat, p_hat))
        if float(v_dir @ vP) < 0:                 # keep the motion prograde (same sense as now)
            n_hat, v_dir = -n_hat, -v_dir
        v_new = math.sqrt(MU * (2 / ra - 1 / a_new)) * v_dir
        e_hat = -p_hat
        nu_of_q = math.atan2(float(np.cross(e_hat, q_hat) @ n_hat), float(e_hat @ q_hat))
        T = 2 * math.pi * math.sqrt(a_new ** 3 / MU)
        dt = T / 2 + (anomaly_time(a_new, e, abs(nu_of_q)) if nu_of_q > 0 else -anomaly_time(a_new, e, abs(nu_of_q)))
        t_b_new = t_k - dt
        if abs(t_b_new - t_b) < 1.0:
            t_b = t_b_new
            break
        t_b = t_b_new
    P, vP = astro.propagate(MU, r0, v0, t_b - ut0)
    rQ, vQ = astro.propagate(MU, P, v_new, t_k - t_b)
    miss = float(np.linalg.norm(rQ - Q))
    vinf = float(np.linalg.norm(vQ - vT))
    gam = math.degrees(math.asin(float(unit(rQ) @ unit(vQ))))
    return {"t_k": t_k, "t_b": t_b, "P": P, "vP": vP, "dv": v_new - vP, "mag": float(np.linalg.norm(v_new - vP)),
            "rp": rp, "vinf": vinf, "gamma": gam, "irel": rel_inc(P, v_new, t_b), "miss": miss,
            "branch": "outbound" if nu_of_q > 0 else "inbound"}


# natural periapsis pass of a periapsis-raised orbit, to centre the scan
t_p1 = t_apo + 0.5 * 2 * math.pi * math.sqrt((0.5 * (el0.apR + titan.a)) ** 3 / MU)
print(f"\nSEED SCAN: Titan encounter epoch t_k from {fmt_ut(t_p1 - 30 * DAY)[:10]} to {fmt_ut(t_p1 + 45 * DAY)[:10]}, "
      f"two-body exact (burn near apoapsis {fmt_ut(t_apo)[:16]})")
print(f"  {'encounter':>16s} {'burn-apo d':>10s} {'dV':>7s} {'v_inf':>7s} {'gamma':>6s} {'i_rel':>6s} {'peri Mm':>8s} {'branch':>8s}")
seeds = []
for i in range(0, 150):
    t_k = t_p1 - 30 * DAY + i * 0.5 * DAY
    sd = seed_for(t_k)
    if sd is None or sd["miss"] > 1e6:
        continue
    seeds.append(sd)
seeds_by_vinf = sorted(seeds, key=lambda d: d["vinf"])
for sd in seeds_by_vinf[:12]:
    print(f"  {fmt_ut(sd['t_k'])[:16]:>16s} {(sd['t_b'] - t_apo) / DAY:+10.1f} {sd['mag']:7.1f} {sd['vinf']:7.0f} "
          f"{sd['gamma']:+6.1f} {sd['irel']:6.1f} {sd['rp'] / 1e6:8,.0f} {sd['branch']:>8s}")
print(f"  ({len(seeds)} elliptic seeds; cheapest burn {min(d['mag'] for d in seeds):.1f} m/s, lowest v_inf {seeds_by_vinf[0]['vinf']:,.0f})")

# ------------------------------------------------------------------ refine the best seeds through the shooter
print(f"\nREFINE  (converged shots through Titan's SOI, periapsis {ALT_KM:,.0f} km altitude)")
print(f"  {'encounter':>16s} {'burn-apo d':>10s} {'dV total':>9s} {'v_inf':>7s} {'i_rel':>6s} {'Titan pe':>9s}")
sols = []
for sd in seeds_by_vinf[:6]:
    t_b, r_b, v_b = sd["t_b"], sd["P"], sd["vP"]
    ut_want = sd["t_k"] - titan.soi / sd["vinf"]
    try:
        res = maneuver.refine(system, "Saturn", r_b, v_b + sd["dv"], t_b, "Titan", sd["t_k"] + 40 * DAY,
                              PER_WANT, ut_want=ut_want, watch=["Titan"], max_dv=60.0, max_nfev=120)
    except Exception as exc:                                        # noqa: BLE001
        print(f"  {fmt_ut(sd['t_k'])[:16]:>16s}  failed: {exc}")
        continue
    rep = res["report"]
    if not rep.get("captured"):
        print(f"  {fmt_ut(sd['t_k'])[:16]:>16s}  no encounter (miss {rep.get('ca_dist', 0) / 1e6:,.1f} Mm)")
        continue
    dv_tot = sd["dv"] + res["dv"]
    irel = rel_inc(r_b, v_b + dv_tot, t_b)
    ok = abs(rep["peR"] - PER_WANT) / PER_WANT < 0.02
    sols.append({"t_b": t_b, "off": (t_b - t_apo) / DAY, "r_b": r_b, "v_b": v_b, "dv": dv_tot, "mag": float(np.linalg.norm(dv_tot)),
                 "vinf": rep["vinf"], "irel": irel, "peR": rep["peR"], "t_ca": ut_want, "traj": res["traj"], "ok": ok, "k": 0})
    print(f"  {fmt_ut(sd['t_k'])[:16]:>16s} {(t_b - t_apo) / DAY:+10.1f} {np.linalg.norm(dv_tot):9.1f} {rep['vinf']:7.0f} "
          f"{irel:6.2f} {rep['peR'] / 1e3:9,.0f}{'' if ok else '  (pe off)'}")
good = [s for s in sols if s["ok"]]
if not good:
    sys.exit("no converged solution")
best = min(good, key=lambda s: s["vinf"] + 2.0 * s["mag"])
print(f"\nCHOSEN burn {best['off']:+.1f} d from apoapsis: {best['mag']:.1f} m/s, v_inf {best['vinf']:,.0f}, i_rel {best['irel']:.2f}")

# ------------------------------------------------------------------ aim: B-plane angle scan at the chosen encounter
p_in = best["traj"].enters("Titan")
bp = astro.bplane(titan.mu, p_in.r0, p_in.v0)
s_hat = bp["s_hat"]
k_hat = np.array([0.0, 0.0, 1.0])
t_hat = unit(np.cross(s_hat, k_hat))
r_hat = np.cross(s_hat, t_hat)
vinf = bp["vinf"]
delta = astro.turn_angle(titan.mu, vinf, PER_WANT)
t_enc = p_in.ut0 + 3600.0
rt, vt = (np.asarray(x) for x in system.rel("Titan", t_enc))
print(f"\nAIM SCAN at Titan (v_inf {vinf:,.0f}, max turn {math.degrees(delta):.1f} deg at {ALT_KM:,.0f} km):")
print(f"  {'psi':>5s} {'peri Mm':>8s} {'apo Mm':>9s} {'period d':>9s} {'/Titan':>7s} {'i_rel':>6s}")
aims = []
for psi in range(0, 360, 15):
    b_hat = math.cos(math.radians(psi)) * t_hat + math.sin(math.radians(psi)) * r_hat
    v_out = vinf * (math.cos(delta) * s_hat - math.sin(delta) * b_hat)   # gravity bends TOWARD the body, away from B
    vs = vt + v_out
    el = astro.elements(MU, rt, vs)
    irel = math.degrees(math.acos(max(-1, min(1, float(unit(np.cross(rt, vs)) @ titan_normal(t_enc))))))
    per = el.period / DAY if el.ecc < 1 else float("inf")
    aims.append((psi, el, irel))
    print(f"  {psi:5d} {el.peR / 1e6:8,.0f} {el.apR / 1e6 if el.ecc < 1 else float('inf'):9,.0f} {per:9.2f} "
          f"{per / (T_TITAN / DAY):7.3f} {irel:6.2f}")
# fine scan: the aim whose post-flyby period is a Titan resonance, lowest i_rel wins
fine = []
for psi10 in range(0, 3600, 5):
    psi = psi10 / 10
    b_hat = math.cos(math.radians(psi)) * t_hat + math.sin(math.radians(psi)) * r_hat
    v_out = vinf * (math.cos(delta) * s_hat - math.sin(delta) * b_hat)   # gravity bends TOWARD the body, away from B
    vs = vt + v_out
    el = astro.elements(MU, rt, vs)
    if el.ecc >= 1:
        continue
    irel = math.degrees(math.acos(max(-1, min(1, float(unit(np.cross(rt, vs)) @ titan_normal(t_enc))))))
    fine.append((psi, el, irel, el.period / T_TITAN))
res_opts = []
for ratio, name in ((3.0, "3:1"), (4.0, "4:1"), (2.5, "5:2"), (3.5, "7:2"), (5.0, "5:1"), (2.0, "2:1")):
    near = [f for f in fine if abs(f[3] - ratio) < 0.03]
    if near:
        f = min(near, key=lambda f: f[2])
        res_opts.append((name, f))
        print(f"  resonance {name}: psi {f[0]:6.1f}  {f[1].peR / 1e6:,.0f} x {f[1].apR / 1e6:,.0f} Mm  "
              f"period {f[1].period / DAY:.2f} d  i_rel {f[2]:.2f}")
if res_opts:
    pref = [o for o in res_opts if o[1][1].apR >= 3.4e9] or res_opts
    name, f = min(pref, key=lambda o: o[1][1].period)
    psi_best = f[0]
    print(f"  -> aim {name} at psi {psi_best:.1f} deg: {f[1].peR / 1e6:,.0f} x {f[1].apR / 1e6:,.0f} Mm, period "
          f"{f[1].period / DAY:.2f} d, i_rel {f[2]:.2f} (pump-down floor at this v_inf: "
          f"{min(a[1].apR for a in aims if a[1].ecc < 1) / 1e6:,.0f} Mm apoapsis)")
else:
    pump = min((a for a in aims if a[1].ecc < 1), key=lambda a: a[1].apR)
    psi_best = pump[0]
    print(f"  -> no resonance reachable in one pass; pump-down aim psi {psi_best} deg: {pump[1].peR / 1e6:,.0f} x "
          f"{pump[1].apR / 1e6:,.0f} Mm, period {pump[1].period / DAY:.1f} d, i_rel {pump[2]:.2f}")
b_dir = np.array([math.cos(math.radians(psi_best)), math.sin(math.radians(psi_best))])

# ------------------------------------------------------------------ final solve with the aim
res = maneuver.refine(system, "Saturn", best["r_b"], best["v_b"] + best["dv"], best["t_b"], "Titan",
                      best["t_ca"] + 60 * DAY, PER_WANT, b_dir=b_dir, ut_want=best["t_ca"],
                      watch=["Titan"], max_dv=50.0, max_nfev=80)
dv_f = best["dv"] + res["dv"]
rep = res["report"]
node = astro.to_node(best["r_b"], best["v_b"], dv_f)
el_post = astro.elements(MU, best["r_b"], best["v_b"] + dv_f)
fr = maneuver.flyby_report(system, res["traj"], "Titan", best["t_ca"] + 60 * DAY)
print(f"\nAPOAPSIS BURN  {fmt_ut(best['t_b'])}   (T+{(best['t_b'] - ut0) / DAY:.1f} d, {best['off']:+.1f} d from apoapsis)")
print(f"    prograde {node[2]:+9.2f}   normal {node[1]:+9.2f}   radial {node[0]:+9.2f}   |dv| {np.linalg.norm(dv_f):.2f} m/s")
print(f"    -> {el_post.peR / 1e6:,.0f} x {el_post.apR / 1e6:,.0f} Mm, period {el_post.period / DAY:,.1f} d, "
      f"i {math.degrees(el_post.inc):.2f} (to Titan's plane {rel_inc(best['r_b'], best['v_b'] + dv_f, best['t_b']):.2f})")
print(f"    TITAN 1: enters SOI {fmt_ut(fr['soi_in'])}, periapsis {fr['peR'] / 1e3:,.0f} km (alt {fr['peAlt'] / 1e3:,.0f}), "
      f"v_inf {fr['vinf']:,.0f}, turn {fr['turn']:.1f} deg, free dV {fr.get('dv_equiv', 0):,.0f}")
if "soi_out" in fr:
    el_x, rs, vs = post_flyby(res["traj"].enters("Titan"), fr["soi_out"])
    print(f"    after:   {el_x.peR / 1e6:,.0f} x {el_x.apR / 1e6:,.0f} Mm, period {el_x.period / DAY:.1f} d = "
          f"{el_x.period / T_TITAN:.2f} Titan periods, i_rel {math.degrees(math.acos(float(unit(np.cross(rs, vs)) @ titan_normal(fr['soi_out'])))):.2f} deg")
    print("    " + " | ".join(f"{p.body.name} {p.end}" for p in res["traj"].patches))
m0 = 2.045                       # t after capture (2.618 less 573 kg burned)
VE = 315 * 9.80665
print(f"    mass {m0:.3f} t -> burn {m0 * 1e3 * (1 - math.exp(-np.linalg.norm(dv_f) / VE)) * VE / 18890:.0f} s; "
      f"prop after {0.388 - m0 * (1 - math.exp(-np.linalg.norm(dv_f) / VE)):.3f} t")

if PUSH:
    out = br.place_nodes([(best["t_b"], node[0], node[1], node[2])], vid=VID, replace=True)
    print(f"\nPUSHED to {out['vessel']}: {out['placed']} node(s)")
    for n in out.get("nodes", []):
        print(f"    node {fmt_ut(n['ut'])}  prograde {n['prograde']:+.3f}  normal {n['normal']:+.3f}  radial {n['radial']:+.3f}  |{n['magnitude']:.3f}|")
    for i, pt in enumerate(out.get("flight_plan") or []):
        pe, ap = pt.get("peR"), pt.get("apR")
        print(f"    plan {i}: {pt.get('body'):8s} {fmt_ut(pt.get('start_ut'))} -> {pt.get('transition')}"
              + (f"   pe {pe / 1e3:,.0f} km" if pe else "") + (f"  ap {ap / 1e6:,.0f} Mm" if ap and ap > 0 else ""))
    al = br.alarm(best["t_b"], name=f"Saturnalija: APOAPSIS BURN {np.linalg.norm(dv_f):,.0f} m/s -> Titan", margin=DAY,
                  notes=f"Plane change + periapsis raise onto the Titan ladder. Titan 1 encounter {fmt_ut(fr['soi_in'])}, "
                        f"v_inf {fr['vinf']:,.0f}, aim {ALT_KM:,.0f} km. Re-run saturn_tour.py apo --push a few days before the "
                        f"burn to re-solve from the live state.",
                  type="Raw", action="KillWarp", vessel="Saturnalija")
    print(f"    alarm {al.get('id')} via {al.get('backend')}")
else:
    print("\n(dry run -- pass --push to place the node and set the alarm)")
