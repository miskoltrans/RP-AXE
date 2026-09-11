"""Saturnalija arrival: probe-corridor burn (stack), release, orbiter deflection burn.

Everything is two-body about Saturn (the vessel is 90 d inside the SOI on a pure hyperbola);
each answer is then re-flown through patched.shoot with every moon watched, and burn 1 is
checked against KSP's own PatchedConics through /predict before it is pushed.
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.optimize import minimize

import astro
import bridge as bridge_mod
import patched
from rss_ephem import DAY, System, fmt_ut

VID = "744a14e4-901e-446b-a9a1-d108bf2f01c0"
PUSH = "--push" in sys.argv
BURN2 = "--burn2" in sys.argv
CAPTURE_GM = None                      # --capture 40 : push the orbit-insertion burn into a 40 Gm apoapsis
if "--capture" in sys.argv:
    CAPTURE_GM = float(sys.argv[sys.argv.index("--capture") + 1])          # burn 1 flown and probe released: solve/push the orbiter deflection only
PROBE_VID = "dca47272-53e1-4afc-befd-24c9036bfc50"

PROBE_PE_KM = 59_745.0      # 7 deg inertial path at 1,400 km -- the designed corridor
ORB_PE_KM = 80_000.0        # orbiter capture periapsis radius
LEAD_S = 600.0              # orbiter periapsis this long BEFORE the probe tops the atmosphere
CAPTURE_APO_M = 20e9        # 80,000 km x 20 Gm capture ellipse
T1_OFFSET = 3600.0          # burn 1 one hour from now
T2_OFFSET = 3 * 3600.0      # burn 2 two hours after burn 1 (release in between)

# vehicle, from the save (persistent.sfs part masses + resources)
M_STACK = 2.9626            # t wet
M_SAT_PROBE = 0.3330        # t, radial-decoupler subtree
M_TITAN_PROBE = 0.7361      # t, stack-decoupler subtree
M_PROP = 0.9691             # t UDMH+NTO
ISP = 315.0
THRUST = 18.89e3
VE = ISP * 9.80665

system = System()
sat = system.body("Saturn")
MU, R, ATM = sat.mu, sat.radius, 2_000e3
OMEGA = 2 * math.pi / sat.rot
MOONS = ["Titan", "Rhea", "Iapetus", "Dione", "Tethys", "Enceladus", "Mimas"]

br = bridge_mod.Bridge()
info = br.nodes(vid=VID)
if not info.get("nodes_available"):
    sys.exit(f"not the active vessel: {info.get('why')}")
body, r0, v0, ut0 = br.state(system, vid=VID)
assert body.name == "Saturn", body.name
print(f"live: {info['vessel']} about {body.name} at {fmt_ut(ut0)}  nodes={len(info['nodes'])}")


def peri_time(r, v, ut):
    """UT of periapsis of the conic through (r, v) at ut (hyperbolic or elliptic)."""
    el = astro.elements(MU, r, v)
    n = math.sqrt(MU / abs(el.sma) ** 3)
    return ut - el.mna / n, el


def radius_crossing(r, v, ut, rad, t_hi):
    """First inbound time after ut at which |r| == rad (bisection on the conic)."""
    f = lambda t: np.linalg.norm(astro.propagate(MU, r, v, t - ut)[0]) - rad
    lo, hi = ut, t_hi
    if f(lo) < 0:
        raise ValueError("already inside")
    if f(hi) > 0:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def solve(r_b, v_b, ut_b, pe_km, t_pe_want=None, label=""):
    """Minimum |dv| at (r_b, v_b, ut_b) giving periapsis pe_km [and periapsis time]."""
    def cons_pe(x):
        rr, vv = r_b, v_b + x
        el = astro.elements(MU, rr, vv)
        return (el.peR - pe_km * 1e3) / 1e3          # km
    cons = [{"type": "eq", "fun": cons_pe}]
    if t_pe_want is not None:
        def cons_t(x):
            tp, _ = peri_time(r_b, v_b + x, ut_b)
            return (tp - t_pe_want) / 10.0             # 10-s units
        cons.append({"type": "eq", "fun": cons_t})
    obj = lambda x: float(x @ x)
    best = None
    for seed in ([0, 0, 0], [3, 0, 0], [0, 3, 0], [0, 0, 3], [-3, 0, 0], [0, -3, 0], [-6, 0, 0], [6, 0, 0], [6, 0, 3]):
        res = minimize(obj, np.array(seed, float), constraints=cons, method="SLSQP",
                       options={"maxiter": 1000, "ftol": 1e-12})
        if not res.success:
            continue
        ok = all(abs(c["fun"](res.x)) < 0.05 for c in cons)
        if ok and (best is None or res.fun < best.fun):
            best = res
    if best is None:
        sys.exit(f"{label}: no solution")
    dv = best.x
    node = astro.to_node(r_b, v_b, dv)
    el = astro.elements(MU, r_b, v_b + dv)
    tp, _ = peri_time(r_b, v_b + dv, ut_b)
    print(f"\n{label}  {fmt_ut(ut_b)}   T+{(ut_b - ut0) / 3600:.2f} h")
    print(f"    prograde {node[2]:+9.3f}   normal {node[1]:+9.3f}   radial {node[0]:+9.3f}   "
          f"|dv| {np.linalg.norm(dv):.3f} m/s")
    print(f"    -> peri {el.peR / 1e3:,.1f} km (alt {(el.peR - R) / 1e3:,.1f})  i {math.degrees(el.inc):.3f} deg  "
          f"e {el.ecc:.5f}  periapsis {fmt_ut(tp)}")
    return dv, node, el, tp


def fly_check(r_b, v_b, ut_b, label):
    """Re-fly through the patched-conic shooter with every moon watched."""
    tp, _ = peri_time(r_b, v_b, ut_b)
    traj = patched.shoot(system, "Saturn", r_b, v_b, ut_b, tp + 5 * DAY, watch=MOONS)
    print(f"    shooter [{label}]: " + " | ".join(
        f"{p.body.name} {p.end}" for p in traj.patches))
    for m in MOONS:
        t, d, vr = patched.closest_approach(system, traj, m, ut_b, tp)
        soi = system.body(m).soi
        flag = "  <-- INSIDE SOI" if d < soi else ""
        if d < 30 * soi or flag:
            print(f"      {m:10s} closest {d / 1e3:12,.0f} km at {fmt_ut(t)}  (SOI {soi / 1e3:,.0f} km){flag}")
    return traj


if CAPTURE_GM is not None:
    # Chain through whatever nodes the game already holds (burn 2 if it has not fired yet).
    pending = sorted(info.get("nodes") or [], key=lambda n: n["ut"])
    r, v, t = r0.copy(), v0.copy(), ut0
    for n in pending:
        r, v = astro.propagate(MU, r, v, n["ut"] - t)
        comps = (n.get("radial", 0.0), n.get("normal", 0.0), n.get("prograde", 0.0))
        v = v + astro.from_node(r, v, comps)
        t = n["ut"]
        print(f"chained through pending node at {fmt_ut(t)}: {math.sqrt(sum(c * c for c in comps)):.3f} m/s")
    tp, elh = peri_time(r, v, t)
    rp, vp = astro.propagate(MU, r, v, tp - t)
    rpn, vp_hyp = np.linalg.norm(rp), np.linalg.norm(vp)
    apo = CAPTURE_GM * 1e9
    a_cap = 0.5 * (rpn + apo)
    vp_ell = math.sqrt(MU * (2 / rpn - 1 / a_cap))
    dv_cap = vp_hyp - vp_ell
    node_c = np.array([0.0, 0.0, -dv_cap])                 # pure retrograde at periapsis
    v_after = vp + astro.from_node(rp, vp, node_c)
    el_c = astro.elements(MU, rp, v_after)
    period = 2 * math.pi * math.sqrt(a_cap ** 3 / MU)
    print(f"\nCAPTURE  {fmt_ut(tp)}   (T+{(tp - ut0) / DAY:.1f} d)   incoming peri {elh.peR / 1e3:,.1f} km  v_inf {astro.vinf_from_state(MU, r, v):,.1f}")
    print(f"    prograde {node_c[2]:+9.2f}   normal {node_c[1]:+9.2f}   radial {node_c[0]:+9.2f}   |dv| {dv_cap:,.2f} m/s")
    print(f"    -> {el_c.peR / 1e3:,.0f} x {el_c.apR / 1e3:,.0f} km  e {el_c.ecc:.5f}  i {math.degrees(el_c.inc):.3f}  "
          f"period {period / DAY:,.1f} d  apoapsis {fmt_ut(tp + period / 2)}  ({apo / sat.soi * 100:.0f}% of the SOI)")
    for gm in (20.0, 40.0):
        a2 = 0.5 * (rpn + gm * 1e9)
        print(f"    (for reference, {gm:.0f} Gm: {vp_hyp - math.sqrt(MU * (2 / rpn - 1 / a2)):,.1f} m/s)")
    m_orb = M_STACK - M_SAT_PROBE - 0.012
    burn_s = m_orb * 1e3 * (1 - math.exp(-dv_cap / VE)) * VE / THRUST
    print(f"    {m_orb:.3f} t, burn {burn_s:.0f} s at {THRUST / 1e3:.2f} kN -> starts {burn_s / 2:.0f} s before periapsis")
    traj = patched.shoot(system, "Saturn", rp, v_after, tp, tp + 1.05 * period, watch=MOONS)
    print("    shooter [one full rev after capture]: " + " | ".join(f"{p.body.name} {p.end}" for p in traj.patches))
    for m in MOONS:
        tt, d, vr = patched.closest_approach(system, traj, m, tp, tp + 1.05 * period)
        soi = system.body(m).soi
        flag = "  <-- INSIDE SOI" if d < soi else ""
        if d < 60 * soi or flag:
            print(f"      {m:10s} closest {d / 1e3:12,.0f} km at {fmt_ut(tt)}  (SOI {soi / 1e3:,.0f} km){flag}")
    if PUSH:
        res = br.place_nodes([(tp, node_c[0], node_c[1], node_c[2])], vid=VID, replace=not pending)
        print(f"\nPUSHED to {res['vessel']}: {res['placed']} node(s)" + ("  (appended after the pending node)" if pending else ""))
        for n in res.get("nodes", []):
            print(f"    node {fmt_ut(n['ut'])}  prograde {n['prograde']:+.3f}  normal {n['normal']:+.3f}  radial {n['radial']:+.3f}  |{n['magnitude']:.3f}|")
        for i, pt in enumerate(res.get("flight_plan") or []):
            pe, ap = pt.get("peR"), pt.get("apR")
            print(f"    plan {i}: {pt.get('body'):8s} {fmt_ut(pt.get('start_ut'))} -> {pt.get('transition')}"
                  + (f"   pe {pe / 1e3:,.1f} km" if pe else "") + (f"  ap {ap / 1e3:,.0f} km" if ap and ap > 0 else ""))
        al = br.alarm(tp, name=f"Saturnalija: SATURN ORBIT INSERTION {dv_cap:,.0f} m/s", margin=3600,
                      notes=f"Retrograde at periapsis into 80,000 km x {CAPTURE_GM:,.0f} Gm, {burn_s:.0f} s burn centred on the node. "
                            f"Capture FIRST, then switch to Saturnalija Probe before it tops the atmosphere ~10 min later "
                            f"(KSP will not switch away from a vessel in atmosphere). Re-run saturn_arrival.py --capture {CAPTURE_GM:.0f} --push "
                            f"after burn 2 has flown to re-align the node with the real periapsis.",
                      type="Raw", action="KillWarp", vessel="Saturnalija")
        print(f"    alarm {al.get('id')} via {al.get('backend')}")
        if pending:
            print("    NOTE: chained on the un-flown burn 2; after burn 2 flies, re-run --capture to re-time the node.")
    else:
        print("\n(dry run -- pass --push to place the capture node and set the alarm)")
    sys.exit(0)

if BURN2:
    # The probe is its own vessel now: its trajectory sets the entry clock, not the orbiter's.
    pb, rpr, vpr, utpr = br.state(system, vid=PROBE_VID)
    assert pb.name == "Saturn"
    rpr, vpr = astro.propagate(MU, rpr, vpr, ut0 - utpr)
    tpp, elp = peri_time(rpr, vpr, ut0)
    print(f"probe: peri {elp.peR / 1e3:,.1f} km (alt {(elp.peR - R) / 1e3:,.1f})  i {math.degrees(elp.inc):.3f}  "
          f"periapsis {fmt_ut(tpp)}   (corridor asked {PROBE_PE_KM:,.0f} km)")
    t_atm = radius_crossing(rpr, vpr, ut0, R + ATM, tpp)
    t_1200 = radius_crossing(rpr, vpr, ut0, R + 1200e3, tpp)
    for name, t in (("2,000 km atmosphere top", t_atm), ("1,400 km", radius_crossing(rpr, vpr, ut0, R + 1400e3, tpp)),
                    ("1,200 km band top", t_1200), ("1,100 km band bottom", radius_crossing(rpr, vpr, ut0, R + 1100e3, tpp))):
        rr, vv = astro.propagate(MU, rpr, vpr, t - ut0)
        rn = np.linalg.norm(rr)
        gam = math.degrees(math.asin(float(rr @ vv) / (rn * np.linalg.norm(vv))))
        vrel = vv - np.cross(np.array([0, 0, OMEGA]), rr)
        gam_rel = math.degrees(math.asin(float(rr @ vrel) / (rn * np.linalg.norm(vrel))))
        print(f"    {name:24s} {fmt_ut(t)}  T-peri {tpp - t:7.0f} s   v {np.linalg.norm(vv):,.0f} m/s "
              f"gamma {gam:+.2f}   rel {np.linalg.norm(vrel):,.0f} m/s gamma {gam_rel:+.2f}")
    tpo, elo = peri_time(r0, v0, ut0)
    print(f"orbiter now: peri {elo.peR / 1e3:,.1f} km  i {math.degrees(elo.inc):.3f}  periapsis {fmt_ut(tpo)}  "
          f"separation from probe {np.linalg.norm(r0 - rpr) / 1e3:,.1f} km, {np.linalg.norm(v0 - vpr):.3f} m/s")
    t2 = ut0 + T1_OFFSET
    r2, v2 = astro.propagate(MU, r0, v0, t2 - ut0)
    t_pe_want = t_atm - LEAD_S
    dv2, node2, el2, tp2 = solve(r2, v2, t2, ORB_PE_KM, t_pe_want=t_pe_want,
                                 label=f"BURN 2  (orbiter -> {ORB_PE_KM:,.0f} km, periapsis {LEAD_S:.0f} s before the probe tops the atmosphere)")
    v2p = v2 + dv2
    fly_check(r2, v2p, t2, "after burn 2")
    rp, vp = astro.propagate(MU, r2, v2p, tp2 - t2)
    rpn, vp_hyp = np.linalg.norm(rp), np.linalg.norm(vp)
    a_cap = 0.5 * (rpn + CAPTURE_APO_M)
    vp_ell = math.sqrt(MU * (2 / rpn - 1 / a_cap))
    dv_cap = vp_hyp - vp_ell
    m_orb = M_STACK - M_SAT_PROBE - 0.006
    burn_s = m_orb * 1e3 * (1 - math.exp(-dv_cap / VE)) * VE / THRUST
    print(f"\nCAPTURE at {fmt_ut(tp2)}: dV {dv_cap:,.1f} m/s retrograde, {burn_s:.0f} s burn; ends "
          f"{(t_atm - tp2) - burn_s / 2:.0f} s before the probe tops the atmosphere")
    v_cap = vp * (vp_ell / vp_hyp)
    r_hold, _ = astro.propagate(MU, rpr, vpr, t_1200 - ut0)
    print("RELAY (orbiter after capture vs probe, probe held at its 1,200 km point):")
    for dt in (0, 300, 600, 900, 1200):
        t = t_atm + dt
        ro, _ = astro.propagate(MU, rp, v_cap, t - tp2)
        rpb = astro.propagate(MU, rpr, vpr, t - ut0)[0] if t <= t_1200 else r_hold
        d = ro - rpb
        elev = math.degrees(math.asin(float(d @ (rpb / np.linalg.norm(rpb))) / np.linalg.norm(d)))
        print(f"    atm+{dt:5d} s  range {np.linalg.norm(d) / 1e3:9,.0f} km   elevation {elev:+6.1f} deg")
    pred = br.predict(vid=VID, ut=t2, dv=(node2[0], node2[1], node2[2]), horizon=120)
    print("\nKSP /predict for burn 2:")
    for i, p in enumerate(pred.get("patches") or pred.get("flight_plan") or []):
        print(f"    {i}: {p.get('body')} {p.get('transition')}  pe {p.get('peR', 0) / 1e3:,.1f} km  "
              f"start {fmt_ut(p.get('start_ut')) if p.get('start_ut') else '-'}")
    if PUSH:
        res = br.place_nodes([(t2, node2[0], node2[1], node2[2])], vid=VID, replace=True)
        print(f"\nPUSHED to {res['vessel']}: {res['placed']} node(s)")
        for n in res.get("nodes", []):
            print(f"    node {fmt_ut(n['ut'])}  prograde {n['prograde']:+.3f}  normal {n['normal']:+.3f}  radial {n['radial']:+.3f}  |{n['magnitude']:.3f}|")
        for i, pt in enumerate(res.get("flight_plan") or []):
            pe = pt.get("peR")
            print(f"    plan {i}: {pt.get('body'):8s} {fmt_ut(pt.get('start_ut'))} -> {pt.get('transition')}"
                  + (f"   pe {pe / 1e3:,.1f} km" if pe else ""))
        al = br.alarm(t2, name="Saturnalija: orbiter deflection burn", margin=600,
                      notes=f"Burn 2 of the arrival sequence, {np.linalg.norm(dv2):.2f} m/s, orbiter only. Periapsis "
                            f"{ORB_PE_KM:,.0f} km timed {LEAD_S:.0f} s BEFORE the probe tops the atmosphere ({fmt_ut(t_atm)}). "
                            f"Capture {dv_cap:,.0f} m/s retrograde at {fmt_ut(tp2)}, THEN switch to the probe.",
                      type="Raw", action="KillWarp", vessel="Saturnalija")
        print(f"    alarm {al.get('id')} via {al.get('backend')}")
    else:
        print("\n(dry run -- pass --push to place burn 2 and set the alarm)")
    sys.exit(0)

# ---------------------------------------------------------------- as it flies now
tp0, el0 = peri_time(r0, v0, ut0)
vinf = astro.vinf_from_state(MU, r0, v0)
print(f"now: peri {el0.peR / 1e3:,.1f} km  i {math.degrees(el0.inc):.3f}  v_inf {vinf:,.1f} m/s  "
      f"periapsis {fmt_ut(tp0)}  (T+{(tp0 - ut0) / DAY:.1f} d)")
traj0 = patched.shoot(system, "Saturn", r0, v0, ut0, tp0 + 2 * DAY, watch=MOONS)
for m in MOONS:
    t, d, vr = patched.closest_approach(system, traj0, m, ut0, tp0)
    print(f"    inbound closest to {m:10s} {d / 1e6:9,.3f} Mm at {fmt_ut(t)}   v_rel {vr:,.0f} m/s")

# ---------------------------------------------------------------- burn 1: stack -> probe corridor
t1 = ut0 + T1_OFFSET
r1, v1 = astro.propagate(MU, r0, v0, t1 - ut0)
dv1, node1, el1, tp1 = solve(r1, v1, t1, PROBE_PE_KM, label="BURN 1  (whole stack -> probe entry corridor)")
v1p = v1 + dv1
fly_check(r1, v1p, t1, "after burn 1")

# probe entry timeline on that hyperbola
t_atm = radius_crossing(r1, v1p, t1, R + ATM, tp1)
t_1400 = radius_crossing(r1, v1p, t1, R + 1400e3, tp1)
t_1200 = radius_crossing(r1, v1p, t1, R + 1200e3, tp1)
t_1100 = radius_crossing(r1, v1p, t1, R + 1100e3, tp1)
print("\nPROBE ENTRY (ballistic, no drag):")
for name, t in (("2,000 km atmosphere top", t_atm), ("1,400 km", t_1400), ("1,200 km band top", t_1200), ("1,100 km band bottom", t_1100)):
    rr, vv = astro.propagate(MU, r1, v1p, t - t1)
    rn = np.linalg.norm(rr)
    gam = math.degrees(math.asin(float(rr @ vv) / (rn * np.linalg.norm(vv))))
    vrel = vv - np.cross(np.array([0, 0, OMEGA]), rr)
    gam_rel = math.degrees(math.asin(float(rr @ vrel) / (rn * np.linalg.norm(vrel))))
    lat = math.degrees(math.asin(rr[2] / rn))
    print(f"    {name:24s} {fmt_ut(t)}  T-peri {tp1 - t:7.0f} s   v {np.linalg.norm(vv):,.0f} m/s "
          f"gamma {gam:+.2f}   rel {np.linalg.norm(vrel):,.0f} m/s gamma {gam_rel:+.2f}   lat {lat:+.1f}")
print(f"    ballistic 1,200 -> 1,100 km takes {t_1100 - t_1200:.0f} s; the chute must hold it there >= 300 s")

# ---------------------------------------------------------------- burn 2: orbiter -> 80,000 km, timed
t2 = ut0 + T2_OFFSET
r2, v2 = astro.propagate(MU, r1, v1p, t2 - t1)
t_pe_want = t_atm - LEAD_S
dv2, node2, el2, tp2 = solve(r2, v2, t2, ORB_PE_KM, t_pe_want=t_pe_want,
                             label=f"BURN 2  (orbiter alone -> {ORB_PE_KM:,.0f} km, periapsis {LEAD_S:.0f} s before probe tops the atmosphere)")
v2p = v2 + dv2
fly_check(r2, v2p, t2, "after burn 2")
dv2_free, _, _, tp2_free = solve(r2, v2, t2, ORB_PE_KM, label="   (same without the timing constraint, for reference)")
print(f"    timing costs {np.linalg.norm(dv2) - np.linalg.norm(dv2_free):+.3f} m/s; untimed periapsis would be "
      f"{(tp2_free - t_atm) / 60:+.1f} min from atmosphere entry")

# ---------------------------------------------------------------- capture at periapsis
rp, vp = astro.propagate(MU, r2, v2p, tp2 - t2)
rpn = np.linalg.norm(rp)
vp_hyp = np.linalg.norm(vp)
a_cap = 0.5 * (rpn + CAPTURE_APO_M)
vp_ell = math.sqrt(MU * (2 / rpn - 1 / a_cap))
dv_cap = vp_hyp - vp_ell
print(f"\nCAPTURE at {fmt_ut(tp2)}: r {rpn / 1e3:,.0f} km  v_hyp {vp_hyp:,.1f} -> v_ell {vp_ell:,.1f}  "
      f"dV {dv_cap:,.1f} m/s retrograde  -> {rpn / 1e3:,.0f} x {CAPTURE_APO_M / 1e3:,.0f} km, "
      f"period {2 * math.pi * math.sqrt(a_cap ** 3 / MU) / DAY:,.1f} d")
m_orb = M_STACK - M_SAT_PROBE - (M_STACK * (1 - math.exp(-np.linalg.norm(dv1) / VE)))
m_orb -= m_orb * (1 - math.exp(-np.linalg.norm(dv2) / VE))
burn_s = m_orb * 1e3 * (1 - math.exp(-dv_cap / VE)) * VE / THRUST
print(f"    orbiter+Titan probe {m_orb:.3f} t at capture; burn {burn_s:.0f} s at {THRUST / 1e3:.2f} kN "
      f"-> start {burn_s / 2:.0f} s before periapsis, ends {LEAD_S - burn_s / 2:.0f} s before the probe tops the atmosphere")

# relay geometry: orbiter (post-capture ellipse) vs probe (ballistic to 1,200 km, then held there)
v_cap = vp * (vp_ell / vp_hyp)
print("\nRELAY GEOMETRY (orbiter after capture vs probe; probe held at its 1,200 km point once there):")
r_hold, _ = astro.propagate(MU, r1, v1p, t_1200 - t1)
for dt in (0, 300, 600, 900, 1200, 1800):
    t = t_atm + dt
    ro, _ = astro.propagate(MU, rp, v_cap, t - tp2)
    if t <= t_1200:
        rpb, _ = astro.propagate(MU, r1, v1p, t - t1)
    else:
        rpb = r_hold
    d = ro - rpb
    up = rpb / np.linalg.norm(rpb)
    elev = math.degrees(math.asin(float(d @ up) / np.linalg.norm(d)))
    print(f"    atm+{dt:5d} s  range {np.linalg.norm(d) / 1e3:9,.0f} km   elevation from probe {elev:+6.1f} deg   "
          f"probe alt {(np.linalg.norm(rpb) - R) / 1e3:,.0f} km   orbiter r {np.linalg.norm(ro) / 1e3:,.0f} km")

# ---------------------------------------------------------------- mass / dV ledger
print("\nDELTA-V LEDGER (Isp 315):")
m = M_STACK
prop = M_PROP
def burn(name, dv, m, prop, drop=0.0):
    used = m * (1 - math.exp(-dv / VE))
    m2, p2 = m - used, prop - used
    print(f"    {name:44s} {dv:7.1f} m/s   {m:6.3f} -> {m2 - drop:6.3f} t   prop left {p2:.3f} t")
    return m2 - drop, p2
m, prop = burn("burn 1 (stack)", np.linalg.norm(dv1), m, prop, drop=M_SAT_PROBE)
m, prop = burn("burn 2 (orbiter, after probe release)", np.linalg.norm(dv2), m, prop)
m, prop = burn("SOI capture", dv_cap, m, prop)
m, prop = burn("apoapsis plane + periapsis raise (design)", 334, m, prop, drop=M_TITAN_PROBE)
print(f"    after Titan-probe release: {m:.3f} t, prop {prop:.3f} t -> {VE * math.log(m / (m - prop)):,.0f} m/s "
      f"left for the tour (design 513) + polar endgame (design 457)")

# ---------------------------------------------------------------- KSP's own answer, then push
pred = br.predict(vid=VID, ut=t1, dv=(node1[0], node1[1], node1[2]), horizon=120)
print("\nKSP /predict for burn 1:")
import json as _json
_pl = pred.get("patches") or pred.get("flight_plan") or []
for i, p in enumerate(_pl):
    keep = {k: p.get(k) for k in ("body", "start_ut", "end_ut", "transition", "peR", "apR", "inc", "ecc", "sma")
            if p.get(k) is not None}
    if keep.get("start_ut"):
        keep["start"] = fmt_ut(keep.pop("start_ut"))
    if keep.get("end_ut"):
        keep["end"] = fmt_ut(keep.pop("end_ut"))
    if keep.get("peR"):
        keep["pe_km"] = round(keep.pop("peR") / 1e3, 1)
    if keep.get("apR"):
        keep["ap_km"] = round(keep.pop("apR") / 1e3, 1)
    print("   ", i, _json.dumps(keep, default=str))
if not _pl:
    print("   ", _json.dumps(pred, default=str)[:1500])
if PUSH:
    res = br.place_nodes([(t1, node1[0], node1[1], node1[2])], vid=VID, replace=True)
    print(f"\nPUSHED to {res['vessel']}: {res['placed']} node(s)")
    for n in res.get("nodes", []):
        print(f"    node {fmt_ut(n['ut'])}  prograde {n['prograde']:+.3f}  normal {n['normal']:+.3f}  radial {n['radial']:+.3f}  |{n['magnitude']:.3f}|")
    for i, pt in enumerate(res.get("flight_plan") or []):
        pe = pt.get("peR")
        print(f"    plan {i}: {pt.get('body'):8s} {fmt_ut(pt.get('start_ut'))} -> {pt.get('transition')}"
              + (f"   pe {pe / 1e3:,.1f} km" if pe else ""))
    al = br.alarm(t1, name="Saturnalija: probe-corridor burn (stack)", margin=600,
                  notes=f"Burn 1 of the arrival sequence, {np.linalg.norm(dv1):.2f} m/s, whole stack. Aims periapsis "
                        f"{PROBE_PE_KM:,.0f} km (7 deg entry). AFTER it: right-click the radial decoupler, release the Saturn "
                        f"probe, then re-run saturn_arrival.py for burn 2 (orbiter back to 80,000 km).",
                  type="Raw", action="KillWarp", vessel="Saturnalija")
    print(f"    alarm {al.get('id')} via {al.get('backend')}")
else:
    print("\n(dry run -- pass --push to place burn 1 and set the alarm)")
