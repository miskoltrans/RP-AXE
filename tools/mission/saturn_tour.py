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
MODE = next((a for a in sys.argv[1:] if not a.startswith("-")), "apo")
WANT_RES = sys.argv[sys.argv.index("--resonance") + 1] if "--resonance" in sys.argv else None
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
    # /vessel reads the Orbit object and is valid for any vessel; only the SOLVER (and therefore
    # pushing a node) needs the craft to be active. So solve read-only and refuse only the push.
    # /vessel reads the Orbit object and is valid for ANY vessel; only KSP's patched-conic SOLVER
    # (and therefore pushing a node) needs the craft to be active. So solve read-only, refuse the push.
    print("NOTE: " + str(info.get("why")))
    print("      Solving read-only; --push needs Saturnalija active in flight.")
    if PUSH:
        sys.exit("  refusing to push: nodes written to a non-active vessel are discarded by KSP.")
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


# ------------------------------------------------------------------ titan1: probe corridor, release, orbiter deflection
if MODE == "titan1":
    # Deep enough that a shallow execution error still enters: Titan's surface is at 2,573 km, so a
    # 2,173 km aim keeps ~0.7 m/s of margin on the side that would skip out, and going deeper only
    # steepens an entry that the chute flattens anyway.
    CORRIDOR = titan.radius - 400e3
    ATM = 600e3                                # Titan's atmosphere tops here (maxAltitude, merged cache)
    LEAD_D = float(sys.argv[sys.argv.index("--lead") + 1]) if "--lead" in sys.argv else 10.0
    PSI = float(sys.argv[sys.argv.index("--psi") + 1]) if "--psi" in sys.argv else 170.0
    # Where the orbiter's periapsis should sit relative to the drone hitting the atmosphere. The drone
    # decelerates, opens its chute near 200 km, then needs 343 s between 100 and 80 km at beta 50; that
    # band is expected around entry+500..850 s, so centre the radio pass on it.
    # Opt-in only. Forcing the radio pass onto the science band means retiming the orbiter's arrival by
    # ~900 s, which costs ~36 m/s this late, and the contract does NOT need it: CollectScience only
    # requires the FlyingHigh SUBJECT to be transmitted eventually, so the drone can sit on its chute
    # (2 RTGs, 0.3 m S-band dish) and squirt 450 bits at the orbiter on the next resonant pass.
    RELAY_C = float(sys.argv[sys.argv.index("--relay") + 1]) if "--relay" in sys.argv else None
    M_STACK, M_DRONE, PROP = 1.9385, 0.7361, 0.2776          # t, live from the save
    VE, THRUST = 315 * 9.80665, 18890.0
    mu_t = titan.mu

    t_end = ut0 + 800 * DAY
    traj = patched.shoot(system, "Saturn", r0, v0, ut0, t_end, watch=["Titan"])
    p_in = traj.enters("Titan")
    if p_in is None:
        sys.exit("no Titan encounter on the current trajectory")
    t_enc, bp0 = p_in.ut0, astro.bplane(titan.mu, p_in.r0, p_in.v0)
    t_b = t_enc - LEAD_D * DAY
    _, r_b, v_b = traj.state(t_b)
    b_dir = np.array([math.cos(math.radians(PSI)), math.sin(math.radians(PSI))])
    print("\nTITAN 1  encounter " + fmt_ut(t_enc) + "   burns at " + fmt_ut(t_b) + f" (E-{LEAD_D:.0f} d)")
    print(f"  uncorrected: periapsis {bp0['peR'] / 1e3:,.0f} km, v_inf {bp0['vinf']:,.0f} m/s")

    def peri_time(r, v, ut):
        el = astro.elements(mu_t, r, v)
        return ut - el.mna / math.sqrt(mu_t / abs(el.sma) ** 3)

    def crossing(r, v, ut, rad, t_hi):
        f = lambda t: float(np.linalg.norm(astro.propagate(mu_t, r, v, t - ut)[0])) - rad
        lo, hi = ut, t_hi
        if f(lo) < 0 or f(hi) > 0:
            return None
        for _ in range(80):
            m = 0.5 * (lo + hi)
            lo, hi = (m, hi) if f(m) > 0 else (lo, m)
        return 0.5 * (lo + hi)

    def solve(rb, vb, tb, peR, label, ut_want=None):
        res = maneuver.refine(system, "Saturn", rb, vb, tb, "Titan", t_enc + 80 * DAY, peR,
                              b_dir=b_dir, ut_want=ut_want, watch=["Titan"], max_dv=60.0, max_nfev=120)
        node = astro.to_node(rb, vb, res["dv"])
        pp = res["traj"].enters("Titan")
        bpx = astro.bplane(titan.mu, pp.r0, pp.v0)
        if label:
            print("\n" + label + "  " + fmt_ut(tb))
            print(f"    prograde {node[2]:+9.3f}   normal {node[1]:+9.3f}   radial {node[0]:+9.3f}   "
                  f"|dv| {float(np.linalg.norm(res['dv'])):.3f} m/s")
            print(f"    -> Titan periapsis {bpx['peR'] / 1e3:,.1f} km (alt {(bpx['peR'] - titan.radius) / 1e3:+,.1f} km), "
                  f"v_inf {bpx['vinf']:,.0f}, SOI entry {fmt_ut(pp.ut0)}")
        return res, node, pp, bpx

    # --- burn A: the whole stack onto the drone's entry corridor
    resA, nodeA, ppA, bpA = solve(r_b, v_b, t_b, CORRIDOR, "BURN A  (stack -> drone entry corridor)")
    tpA = peri_time(ppA.r0, ppA.v0, ppA.ut0)
    t_atm = crossing(ppA.r0, ppA.v0, ppA.ut0, titan.radius + ATM, tpA)
    print("\n  DRONE ENTRY (ballistic, no drag -- the chute sets everything below 200 km):")
    for name, alt in (("atmosphere top", ATM), ("chute deploy", 200e3), ("band top", 100e3), ("band bottom", 80e3)):
        t = crossing(ppA.r0, ppA.v0, ppA.ut0, titan.radius + alt, tpA)
        if t is None:
            print(f"    {name:18s} alt {alt / 1e3:5,.0f} km  not reached ballistically")
            continue
        rr, vv = astro.propagate(mu_t, ppA.r0, ppA.v0, t - ppA.ut0)
        rn = float(np.linalg.norm(rr))
        gam = math.degrees(math.asin(float(rr @ vv) / (rn * float(np.linalg.norm(vv)))))
        print(f"    {name:18s} alt {alt / 1e3:5,.0f} km  {fmt_ut(t)}  entry{t - t_atm:+6.0f} s  "
              f"v {float(np.linalg.norm(vv)):,.0f} m/s  gamma {gam:+.1f} deg  "
              f"lat {math.degrees(math.asin(rr[2] / rn)):+.1f}")
    marginA = (titan.radius - CORRIDOR) / 1e3 / ((bp0['peR'] - CORRIDOR) / 1e3 / float(np.linalg.norm(resA["dv"])))
    print(f"    execution margin: {marginA:.2f} m/s too little and the drone skips out instead of entering")

    # --- burn B: the orbiter alone, back out to the flyby aim, TIMED so the radio pass covers the band
    r_b2, v_b2 = astro.propagate(MU, r_b, v_b + resA["dv"], 600.0)
    t_b2 = t_b + 600.0
    resB, nodeB, ppB, bpB = solve(r_b2, v_b2, t_b2, PER_WANT, None)
    if RELAY_C is not None:
        # The pass PEAKS when the orbiter goes over the drone's descent point, which has nothing to do
        # with the orbiter's own Titan periapsis -- so iterate on the over-flight, not on periapsis.
        for _ in range(3):
            t_hold = crossing(ppA.r0, ppA.v0, ppA.ut0, titan.radius + 200e3, tpA) or t_atm
            rh = astro.propagate(mu_t, ppA.r0, ppA.v0, t_hold - ppA.ut0)[0]
            ts_ = np.arange(t_atm - 1800, t_atm + 3600, 10.0)
            el_ = [float(astro.propagate(mu_t, ppB.r0, ppB.v0, t - ppB.ut0)[0] @ unit(rh)) /
                   float(np.linalg.norm(astro.propagate(mu_t, ppB.r0, ppB.v0, t - ppB.ut0)[0] - rh)) for t in ts_]
            t_peak = float(ts_[int(np.argmax(el_))])
            shift = (t_atm + RELAY_C) - t_peak
            if abs(shift) < 10.0:
                break
            resB, nodeB, ppB, bpB = solve(r_b2, v_b2, t_b2, PER_WANT, None, ut_want=ppB.ut0 + shift)
    tpB = peri_time(ppB.r0, ppB.v0, ppB.ut0)
    print("\nBURN B  (orbiter alone -> flyby aim, 10 min after the release)  " + fmt_ut(t_b2))
    print(f"    prograde {nodeB[2]:+9.3f}   normal {nodeB[1]:+9.3f}   radial {nodeB[0]:+9.3f}   "
          f"|dv| {float(np.linalg.norm(resB['dv'])):.3f} m/s")
    print(f"    -> Titan periapsis {bpB['peR'] / 1e3:,.1f} km (alt {(bpB['peR'] - titan.radius) / 1e3:+,.1f} km), "
          f"periapsis at drone entry{tpB - t_atm:+.0f} s"
          + (f" (asked {RELAY_C:+.0f})" if RELAY_C is not None else ""))
    frB = maneuver.flyby_report(system, resB["traj"], "Titan", t_enc + 80 * DAY)
    print(f"    v_inf {frB['vinf']:,.0f}, turn {frB['turn']:.2f} deg, free dV {frB.get('dv_equiv', 0):,.0f} m/s")
    if "soi_out" in frB:
        el_x, rs, vs = post_flyby(resB["traj"].enters("Titan"), frB["soi_out"])
        print(f"    after:  {el_x.peR / 1e6:,.0f} x {el_x.apR / 1e6:,.0f} Mm, {el_x.period / DAY:.2f} d = "
              f"{el_x.period / T_TITAN:.3f} Titan periods, i_rel "
              f"{math.degrees(math.acos(float(unit(np.cross(rs, vs)) @ titan_normal(frB['soi_out'])))):.2f} deg")

    # --- relay visibility, drone held at its 200 km point (chute descent barely moves it)
    t_200 = crossing(ppA.r0, ppA.v0, ppA.ut0, titan.radius + 200e3, tpA) or t_atm
    r_hold = astro.propagate(mu_t, ppA.r0, ppA.v0, t_200 - ppA.ut0)[0]

    def elev_at(t):
        ro = astro.propagate(mu_t, ppB.r0, ppB.v0, t - ppB.ut0)[0]
        rp_ = astro.propagate(mu_t, ppA.r0, ppA.v0, t - ppA.ut0)[0] if t <= t_200 else r_hold
        d = ro - rp_
        return math.degrees(math.asin(float(d @ unit(rp_)) / float(np.linalg.norm(d)))), float(np.linalg.norm(d))

    ts = np.arange(t_atm - 600, t_atm + 3600, 10.0)
    vis = [t for t in ts if elev_at(t)[0] > 0]
    print("\n  RELAY (drone to orbiter, UHF both ends):")
    if vis:
        peak = max(ts, key=lambda t: elev_at(t)[0])
        print(f"    above the drone's horizon entry{vis[0] - t_atm:+.0f} s to entry{vis[-1] - t_atm:+.0f} s "
              f"({(vis[-1] - vis[0]) / 60:.1f} min), peaking {elev_at(peak)[0]:+.0f} deg at entry{peak - t_atm:+.0f} s")
        print("    NOT a hard requirement: the contract's CollectScience only needs the FlyingHigh subject")
        print("    transmitted eventually, so a miss here just defers it to the next resonant Titan pass.")
    else:
        print("    orbiter never rises above the drone's horizon; the data waits for the next Titan pass")
    for dt in (0, 300, 500, 650, 850, 1000, 1400):
        e, rng = elev_at(t_atm + dt)
        print(f"    entry+{dt:5d} s   range {rng / 1e3:7,.0f} km   elevation {e:+6.1f} deg")

    # --- ledger
    dvA, dvB = float(np.linalg.norm(resA["dv"])), float(np.linalg.norm(resB["dv"]))
    usedA = M_STACK * (1 - math.exp(-dvA / VE))
    m_rel = M_STACK - usedA - M_DRONE
    usedB = m_rel * (1 - math.exp(-dvB / VE))
    m_fin = m_rel - usedB
    prop_left = PROP - usedA - usedB
    print(f"\n  LEDGER: stack {M_STACK:.3f} t -> burn A {dvA:.2f} m/s ({usedA * 1e3:.1f} kg, "
          f"{usedA * 1e3 * VE / THRUST:.1f} s of main engine) -> release drone {M_DRONE:.3f} t "
          f"-> burn B {dvB:.2f} m/s ({usedB * 1e3:.2f} kg)")
    print(f"          orbiter {m_fin:.3f} t, propellant {prop_left:.3f} t = "
          f"{VE * math.log(m_fin / (m_fin - prop_left)):,.0f} m/s left for the tour")

    if PUSH:
        out = br.place_nodes([(t_b, nodeA[0], nodeA[1], nodeA[2])], vid=VID, replace=True)
        print(f"\nPUSHED to {out['vessel']}: {out['placed']} node(s)  (burn A only -- B needs the release first)")
        for n in out.get("nodes", []):
            print("    node " + fmt_ut(n['ut']) + f"  prograde {n['prograde']:+.4f}  normal {n['normal']:+.4f}  "
                  f"radial {n['radial']:+.4f}  |{n['magnitude']:.4f}|")
        for i, pt in enumerate(out.get("flight_plan") or []):
            pe = pt.get("peR")
            print(f"    plan {i}: " + f"{pt.get('body'):8s} " + fmt_ut(pt.get('start_ut')) + f" -> {pt.get('transition')}"
                  + (f"   pe {pe / 1e3:,.0f} km" if pe else ""))
        al = br.alarm(t_b, name=f"Saturnalija: TITAN 1 sequence (burn A {dvA:.1f} m/s)", margin=DAY,
                      notes=(f"1) fly the placed node, {dvA:.2f} m/s -- it aims the STACK at the drone's entry corridor "
                             f"(Titan periapsis {CORRIDOR / 1e3:,.0f} km); {marginA:.2f} m/s short and the drone skips out. "
                             f"2) right-click the STACK decoupler, release the Titan drone. 3) re-run "
                             f"`saturn_tour.py titan1 --push` for burn B, {dvB:.2f} m/s, which returns the orbiter to "
                             f"{ALT_KM:,.0f} km. 4) the orbiter needs "
                             f"NO action at the flyby -- switch to the drone before 600 km altitude and ride it down: chute "
                             f"~200 km, arm the experiment only below 100 km. Encounter {fmt_ut(t_enc)}. The relay sets about "
                             f"400 s after entry, so the 450-bit transmit most likely lands on the NEXT resonant Titan "
                             f"pass; that is fine, the contract only needs the FlyingHigh subject transmitted eventually."),
                      type="Raw", action="KillWarp", vessel="Saturnalija")
        print(f"    alarm {al.get('id')} via {al.get('backend')}")
    else:
        print("\n(dry run -- pass --push to place burn A and set the alarm)")
    sys.exit(0)

# ------------------------------------------------------------------ mcc: clean up the Titan aim
if MODE == "mcc":
    t_end = ut0 + 800 * DAY
    traj = patched.shoot(system, "Saturn", r0, v0, ut0, t_end, watch=["Titan"])
    p_in = traj.enters("Titan")
    if p_in is None:
        rep = patched.arrival_report(system, traj, "Titan", t_end)
        sys.exit(f"no Titan encounter on the current trajectory: closest {rep['ca_dist'] / 1e6:,.1f} Mm")
    bp = astro.bplane(titan.mu, p_in.r0, p_in.v0)
    vinf, s_hat = bp["vinf"], bp["s_hat"]
    k_hat = np.array([0.0, 0.0, 1.0])
    t_hat = unit(np.cross(s_hat, k_hat))
    r_hat = np.cross(s_hat, t_hat)
    psi_now = math.degrees(math.atan2(bp["B_R"], bp["B_T"])) % 360
    b_want = maneuver.b_for_periapsis(titan.mu, vinf, PER_WANT)
    delta = astro.turn_angle(titan.mu, vinf, PER_WANT)
    print(f"\nTITAN ENCOUNTER {fmt_ut(p_in.ut0)}  ({(p_in.ut0 - ut0) / DAY:.0f} d of coast)")
    print(f"  v_inf {vinf:,.0f} m/s   flown periapsis {bp['peR'] / 1e3:,.0f} km, |B| {bp['b'] / 1e3:,.0f} km at psi {psi_now:.1f} deg")
    print(f"  asked {PER_WANT / 1e3:,.0f} km (alt {ALT_KM:,.0f}): |B| {b_want / 1e3:,.0f} km, turn "
          f"{math.degrees(delta):.2f} deg vs the {math.degrees(astro.turn_angle(titan.mu, vinf, bp['peR'])):.2f} deg it would turn now")

    # what each B-plane angle does to the post-flyby orbit, at the asked periapsis
    t_enc = p_in.ut0 + 2600.0
    rt, vt = (np.asarray(x) for x in system.rel("Titan", t_enc))
    fine = []
    for x in range(0, 3600, 5):
        psi = x / 10.0
        b_hat = math.cos(math.radians(psi)) * t_hat + math.sin(math.radians(psi)) * r_hat
        v_out = vinf * (math.cos(delta) * s_hat - math.sin(delta) * b_hat)
        vs = vt + v_out
        el = astro.elements(MU, rt, vs)
        if el.ecc >= 1:
            continue
        irel = math.degrees(math.acos(max(-1, min(1, float(unit(np.cross(rt, vs)) @ titan_normal(t_enc))))))
        fine.append((psi, el, irel, el.period / T_TITAN))
    if not fine:
        sys.exit("every aim at this periapsis leaves Saturn -- pump down first")
    print(f"  reachable in one pass: period {min(f[1].period for f in fine) / DAY:.1f} to "
          f"{max(f[1].period for f in fine) / DAY:,.0f} d ({min(f[3] for f in fine):.2f} to {max(f[3] for f in fine):,.1f} Titan periods)")
    print("\n  resonances reachable in ONE pass:")
    opts = {}
    for num, den, name in ((2, 1, "2:1"), (5, 2, "5:2"), (3, 1, "3:1"), (7, 2, "7:2"), (4, 1, "4:1"),
                           (9, 2, "9:2"), (5, 1, "5:1"), (11, 2, "11:2"), (6, 1, "6:1"), (7, 1, "7:1")):
        near = [f for f in fine if abs(f[3] - num / den) < 0.02]
        if near:
            f = min(near, key=lambda f: f[2])
            opts[name] = f
            print(f"    {name:>4s}: psi {f[0]:6.1f}   {f[1].peR / 1e6:,.0f} x {f[1].apR / 1e6:,.0f} Mm   "
                  f"{f[1].period / DAY:6.2f} d   i_rel {f[2]:.2f} deg")
    if not opts:
        sys.exit("no resonance is reachable in one pass at this periapsis")
    if WANT_RES and WANT_RES not in opts:
        sys.exit(f"{WANT_RES} is not reachable; have {', '.join(opts)}")
    name = WANT_RES or min(opts, key=lambda n: opts[n][1].period)
    f = opts[name]
    psi_best = f[0]
    print(f"  -> aiming {name} at psi {psi_best:.1f} deg: {f[1].peR / 1e6:,.0f} x {f[1].apR / 1e6:,.0f} Mm, "
          f"{f[1].period / DAY:.2f} d, i_rel {f[2]:.2f} deg")
    b_dir = np.array([math.cos(math.radians(psi_best)), math.sin(math.radians(psi_best))])

    print(f"\nCORRECTION SCAN (each row is a converged shot):")
    best, scan = maneuver.cheapest_correction(system, "Saturn", r0, v0, ut0, "Titan", p_in.ut0, PER_WANT,
                                              t_end=p_in.ut0 + 80 * DAY, n_times=10, watch=["Titan"],
                                              max_dv=60.0, b_dir=b_dir)
    for o in scan:
        print(f"  {fmt_ut(o['ut'])[:16]:>16s}  T+{(o['ut'] - ut0) / DAY:7.1f} d  {o['mag']:8.2f} m/s  "
              f"{'hits the aim point' if o['ok'] else 'did not converge'}")
    if best is None:
        sys.exit("no burn time reached the aim point")
    r_b, v_b = astro.propagate(MU, r0, v0, best["ut"] - ut0)
    node = astro.to_node(r_b, v_b, best["dv"])
    fr = maneuver.flyby_report(system, best["res"]["traj"], "Titan", p_in.ut0 + 80 * DAY)
    print(f"\nMIDCOURSE  {fmt_ut(best['ut'])}   (T+{(best['ut'] - ut0) / DAY:.1f} d)")
    print(f"    prograde {node[2]:+9.3f}   normal {node[1]:+9.3f}   radial {node[0]:+9.3f}   |dv| {best['mag']:.3f} m/s")
    print(f"    TITAN 1: SOI {fmt_ut(fr['soi_in'])}, periapsis {fr['peR'] / 1e3:,.0f} km (alt {fr['peAlt'] / 1e3:,.0f}), "
          f"v_inf {fr['vinf']:,.0f}, turn {fr['turn']:.2f} deg, free dV {fr.get('dv_equiv', 0):,.0f}")
    if "soi_out" in fr:
        el_x, rs, vs = post_flyby(best["res"]["traj"].enters("Titan"), fr["soi_out"])
        print(f"    after:   {el_x.peR / 1e6:,.0f} x {el_x.apR / 1e6:,.0f} Mm, {el_x.period / DAY:.2f} d = "
              f"{el_x.period / T_TITAN:.3f} Titan periods, i_rel "
              f"{math.degrees(math.acos(float(unit(np.cross(rs, vs)) @ titan_normal(fr['soi_out'])))):.2f} deg")
    if PUSH:
        out = br.place_nodes([(best["ut"], node[0], node[1], node[2])], vid=VID, replace=True)
        print(f"\nPUSHED to {out['vessel']}: {out['placed']} node(s)")
        for n in out.get("nodes", []):
            print(f"    node {fmt_ut(n['ut'])}  prograde {n['prograde']:+.4f}  normal {n['normal']:+.4f}  "
                  f"radial {n['radial']:+.4f}  |{n['magnitude']:.4f}|")
        for i, pt in enumerate(out.get("flight_plan") or []):
            pe, ap = pt.get("peR"), pt.get("apR")
            print(f"    plan {i}: {pt.get('body'):8s} {fmt_ut(pt.get('start_ut'))} -> {pt.get('transition')}"
                  + (f"   pe {pe / 1e3:,.0f} km" if pe else "") + (f"  ap {ap / 1e6:,.0f} Mm" if ap and ap > 0 else ""))
        al = br.alarm(best["ut"], name=f"Saturnalija: Titan aim MCC {best['mag']:.2f} m/s", margin=DAY,
                      notes=f"Cleans the Titan-1 aim from {bp['peR'] / 1e3:,.0f} km to {PER_WANT / 1e3:,.0f} km and sets the "
                            f"{name} resonance (psi {psi_best:.1f}). Encounter {fmt_ut(p_in.ut0)}. Tiny burn -- use RCS. "
                            f"Re-run `saturn_tour.py mcc --push` afterwards to re-check the aim.",
                      type="Raw", action="KillWarp", vessel="Saturnalija")
        print(f"    alarm {al.get('id')} via {al.get('backend')}")
    else:
        print("\n(dry run -- pass --push to place the node and set the alarm)")
    sys.exit(0)

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
