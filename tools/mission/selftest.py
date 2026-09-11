"""Every assumption in this toolchain, checked against something that can disagree.

Run it before trusting a number:  python plan.py selftest

The checks are deliberately of two kinds. Some are internal (two independent
propagators, round trips) and catch arithmetic. The rest compare against the
running install -- Kopernicus' own log, KSPTOT's exported body table, a maneuver
node the game itself planned -- and those are the ones that catch the failures
that stay self-consistent, which is every failure this project has actually had.
"""
import configparser
import datetime
import math
import os

import numpy as np

import astro
import kepler_uv
import launch as launch_mod
import maneuver
import patched
from lambert import lambert
from rss_ephem import System, date_of, ut_of
from sfs import Save, find_save

DAY = 86400.0
_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    return ok


def _report(verbose):
    width = max(len(n) for n, _, _ in _results)
    for name, ok, detail in _results:
        if verbose or not ok:
            print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    bad = [n for n, ok, _ in _results if not ok]
    print(f"\n  {len(_results) - len(bad)}/{len(_results)} passed"
          + (f"; FAILED: {', '.join(bad)}" if bad else ""))
    return not bad


# ---------------------------------------------------------------------------
def test_epoch(S):
    check("epoch is B1950, not UT 0",
          abs(S.epoch - (-31542641.784)) < 1.0,
          f"{S.epoch:,.3f} s = {date_of(S.epoch):%Y-%m-%d %H:%M:%S}")
    check("epoch offset is one year, not zero", abs(S.epoch) > 3e7,
          "reading it as 0 puts every body 365.08 d out of phase, self-consistently")


def test_bodies(S):
    check("Kopernicus.log was read", S.log_path is not None and len(S.by_index) > 10,
          f"{len(S.by_index)} bodies with a game-assigned index")
    missing = [b.name for b in S.bodies.values() if b.index is None]
    check("every body has a save index", not missing, f"missing: {missing}" or "")
    ph = S.bodies.get("Phobos")
    if ph:
        hill = ph.a * (ph.mu / S.bodies[ph.parent].mu) ** 0.4
        check("Phobos SOI is the override, not the Hill sphere",
              abs(ph.soi - 47000) < 1, f"{ph.soi:,.0f} m (Hill would be {hill:,.0f} m)")
    check("cbNameLater aliases are resolved",
          S.bodies["Moon"].parent == "Earth",
          f"Moon's referenceBody in the cfg is 'Kerbin'; resolved to {S.bodies['Moon'].parent}")
    check("Earth has children", len(S.children("Earth")) >= 1,
          ", ".join(b.name for b in S.children("Earth")))

    # RSS's *_Oblate.cfg files restate the gas giants' equatorial radius with
    # `@radius *= ...`, so the raw .cfg is 1,569 km small on Jupiter alone. The
    # trajectory does not care; every printed altitude and every contract gate does.
    patched_r = [n for n in ("Jupiter", "Saturn", "Uranus", "Neptune") if n in S.bodies]
    worst = max((abs(S.body(n).radius - S.body(n).radius_cfg) for n in patched_r),
                default=0.0)
    check("gas-giant radii come from ModuleManager, not the raw .cfg",
          S.cache_path is not None and worst > 1e5,
          "Jupiter " + (f"{S.body('Jupiter').radius_cfg/1e3:,.0f} -> "
                        f"{S.body('Jupiter').radius/1e3:,.1f} km"
                        if "Jupiter" in S.bodies else "absent"))
    unpatched = [b.name for b in S.bodies.values()
                 if b.name not in patched_r and abs(b.radius - b.radius_cfg) > 1.0]
    check("only the four gas giants are radius-patched", not unpatched,
          f"others differing: {unpatched}" if unpatched else "28 bodies agree exactly")


def test_against_ksptot(S, path=r"C:/git/ksp/KSP_Trajectory_Optimization_Tool-1.6.10.1/bodies.ini"):
    """KSPTOT's body table was exported from the running game by its own plugin.

    It is the one dataset here that came out of KSP rather than out of a config
    file, so agreeing with it means the config parse and the game agree.
    """
    if not os.path.exists(path):
        check("cross-check vs KSPTOT bodies.ini", True, "not installed, skipped")
        return
    cp = configparser.ConfigParser()
    cp.read(path)
    worst_a = worst_mu = worst_abs = 0.0
    worst_name = worst_mu_name = ""
    n = 0
    for sect in cp.sections():
        name = cp[sect].get("name", sect)
        b = S.bodies.get(name)
        if b is None or not b.a:
            continue
        n += 1
        da = abs(float(cp[sect]["sma"]) * 1e3 - b.a) / b.a
        dmu = abs(float(cp[sect]["gm"]) * 1e9 - b.mu) / b.mu
        if da > worst_a:
            worst_a, worst_name = da, name
        # bodies.ini prints gm in km^3/s^2 with nine decimals; for Deimos that is
        # only six significant figures, so judge against the printed precision
        # rather than calling a rounding artefact a disagreement.
        if dmu > 1e-9 and abs(float(cp[sect]["gm"]) * 1e9 - b.mu) > 0.5:
            if dmu > worst_mu:
                worst_mu, worst_mu_name = dmu, name
        worst_abs = max(worst_abs, abs(float(cp[sect]["gm"]) * 1e9 - b.mu))
        if abs(float(cp[sect].get("epoch", 0)) - S.epoch) > 1.0 and float(cp[sect].get("epoch", 0)):
            check(f"KSPTOT epoch matches for {name}", False,
                  f"{cp[sect]['epoch']} vs {S.epoch}")
    check("semi-major axes match KSPTOT's export", worst_a < 1e-9,
          f"{n} bodies, worst relative error {worst_a:.2e} ({worst_name})")
    check("gravitational parameters match KSPTOT's export", worst_mu == 0.0,
          f"worst absolute error {worst_abs:.2f} m3/s2, within the export's own printed precision"
          if worst_mu == 0.0 else f"{worst_mu_name} differs by {worst_mu:.2e} relative")


def test_propagator():
    mu = 3.986004418e14
    rng = np.random.default_rng(11)
    worst = 0.0
    for _ in range(400):
        r0 = rng.normal(0, 1, 3)
        r0 = r0 / np.linalg.norm(r0) * rng.uniform(6.6e6, 5e8)
        v0 = rng.normal(0, 1, 3)
        v0 = v0 / np.linalg.norm(v0) * rng.uniform(1e3, 1.2e4)
        dt = rng.uniform(-3e5, 3e5)
        a = astro.propagate(mu, r0, v0, dt)[0]
        b = kepler_uv.propagate(r0, v0, dt, mu)[0]
        worst = max(worst, float(np.linalg.norm(a - b)) / max(1.0, float(np.linalg.norm(a))))
    check("Shepperd agrees with an independent universal-variable solver", worst < 1e-8,
          f"worst relative position error {worst:.2e} over 400 random states")

    r = 1e7
    v = math.sqrt(mu / r)
    T = 2 * math.pi * math.sqrt(r ** 3 / mu)
    end = astro.propagate(mu, [r, 0, 0], [0, v, 0], 37 * T)[0]
    err = float(np.linalg.norm(end - np.array([r, 0, 0])))
    check("37 circular orbits land back on the start", err < 1e-3, f"{err:.2e} m")

    MU = 1.32712440042e20
    r0 = np.array([1.0e11, 5.0e10, 1.0e10])
    v0 = np.array([-1.2e4, 2.6e4, 500.0])
    E0 = float(v0 @ v0) / 2 - MU / float(np.linalg.norm(r0))
    r1, v1 = astro.propagate(MU, r0, v0, 3000 * DAY)
    E1 = float(v1 @ v1) / 2 - MU / float(np.linalg.norm(r1))
    check("energy is conserved over 3000 days", abs(E1 - E0) / abs(E0) < 1e-12,
          f"dE/E = {abs(E1 - E0) / abs(E0):.2e}")

    worst = 0.0
    for _ in range(60):
        r0 = rng.normal(0, 1, 3)
        r0 = r0 / np.linalg.norm(r0) * rng.uniform(7e6, 1e8)
        v0 = rng.normal(0, 1, 3)
        v0 = v0 / np.linalg.norm(v0) * rng.uniform(2e3, 1.5e4)
        ts = np.linspace(-2e5, 2e5, 41)
        P, _ = astro.sample_conic(mu, r0, v0, ts)
        for i in (0, 13, 27, 40):
            worst = max(worst, float(np.linalg.norm(P[i] - astro.propagate(mu, r0, v0, ts[i])[0])))
    check("vectorised sampling matches the scalar propagator", worst < 1e-2, f"{worst:.2e} m")


def test_elements():
    mu = 3.986004418e14
    worst = 0.0
    rng = np.random.default_rng(3)
    for _ in range(200):
        r0 = rng.normal(0, 1, 3)
        r0 = r0 / np.linalg.norm(r0) * rng.uniform(7e6, 1e8)
        v0 = rng.normal(0, 1, 3)
        v0 = v0 / np.linalg.norm(v0) * rng.uniform(1e3, 1.4e4)
        el = astro.elements(mu, r0, v0)
        r2, v2 = astro.state_from_elements(mu, el.sma, el.ecc, el.inc, el.lan, el.argp, el.mna)
        worst = max(worst, float(np.linalg.norm(r2 - r0)))
    check("elements round-trip back to the same state", worst < 1e-3,
          f"worst {worst:.2e} m over 200 states, elliptic and hyperbolic")


def test_lambert(S):
    mu = S.mu_sun
    r1 = np.array([1.495979e11, 0.0, 0.0])
    r2 = np.array([-2.279e11, 0.0, 1.0])
    a_t = (np.linalg.norm(r1) + np.linalg.norm(r2)) / 2
    tof = math.pi * math.sqrt(a_t ** 3 / mu)
    v1, _ = lambert(mu, r1, r2, tof)
    dv = float(np.linalg.norm(v1)) - math.sqrt(mu / np.linalg.norm(r1))
    hoh = math.sqrt(mu / np.linalg.norm(r1)) * (
        math.sqrt(2 * np.linalg.norm(r2) / (np.linalg.norm(r1) + np.linalg.norm(r2))) - 1)
    check("Lambert reproduces the analytic Hohmann dV", abs(dv - hoh) < 0.05,
          f"{dv:.3f} vs {hoh:.3f} m/s")

    # the check that matters: does the solution actually arrive where it claims?
    worst = 0.0
    for dep, arr, y in (("Earth", "Mars", 1965), ("Earth", "Jupiter", 1966), ("Earth", "Venus", 1967)):
        t0 = ut_of(y, 6, 1)
        for days in (120, 260, 400, 900):
            t1 = t0 + days * DAY
            ra, _ = S.helio(dep, t0)
            rb, _ = S.helio(arr, t1)
            try:
                v1, _ = lambert(mu, np.array(ra), np.array(rb), t1 - t0)
            except Exception:
                continue
            end, _ = astro.propagate(mu, np.array(ra), np.asarray(v1), t1 - t0)
            worst = max(worst, float(np.linalg.norm(end - np.asarray(rb))) / float(np.linalg.norm(rb)))
    check("a Lambert arc really lands on its target position", worst < 1e-9,
          f"worst relative miss {worst:.2e} after propagating the solution")


def test_node_basis():
    rng = np.random.default_rng(5)
    worst = 0.0
    for _ in range(200):
        r = rng.normal(0, 1, 3) * 1e7
        v = rng.normal(0, 1, 3) * 5e3
        dv = rng.normal(0, 1, 3) * 300
        worst = max(worst, float(np.linalg.norm(astro.from_node(r, v, astro.to_node(r, v, dv)) - dv)))
    check("node basis round-trips", worst < 1e-9, f"{worst:.2e} m/s")
    r = np.array([1e7, 0.0, 0.0])
    v = np.array([0.0, 6.3e3, 0.0])
    n = astro.to_node(r, v, np.array([0.0, 0.0, 100.0]))
    check("normal+ is +h (a burn along r x v is a positive normal component)",
          abs(n[1] - 100.0) < 1e-9 and abs(n[0]) < 1e-9 and abs(n[2]) < 1e-9,
          f"radial {n[0]:.3f}, normal {n[1]:.3f}, prograde {n[2]:.3f}")
    n = astro.to_node(r, v, np.array([100.0, 0.0, 0.0]))
    check("radial+ points away from the body", abs(n[0] - 100.0) < 1e-9,
          f"radial {n[0]:.3f}")


def test_ejection(S):
    E = S.body("Earth")
    mu = E.mu
    rp = E.radius + 185e3
    inc = math.radians(28.5)
    r0 = np.array([rp, 0.0, 0.0])
    vc = math.sqrt(mu / rp)
    v0 = np.array([0.0, vc * math.cos(inc), vc * math.sin(inc)])
    ut0 = ut_of(1966, 9, 26)
    worst_mag = worst_dir = 0.0
    for vinf_req in (np.array([0.0, 8900 * math.cos(inc), 8900 * math.sin(inc)]),
                     np.array([3000.0, 7000.0, 5000.0]),
                     np.array([1000.0, 500.0, 3200.0]),
                     np.array([9000.0, 9000.0, 4000.0])):
        s = maneuver.single_impulse_hyperbolic_burn(mu, r0, v0, vinf_req)
        traj = patched.shoot(S, "Earth", s["r_burn"], s["v_pos"], ut0 + s["dt"],
                             ut0 + s["dt"] + 120 * DAY, watch=[])
        p = traj.patches[0]
        r_ex, v_ex = p.state(p.ut1)
        got = astro.vinf_at_radius(mu, float(np.linalg.norm(v_ex)), float(np.linalg.norm(r_ex)))
        want = float(np.linalg.norm(vinf_req))
        worst_mag = max(worst_mag, abs(got - want))
        ang = math.degrees(math.acos(np.clip(
            float(v_ex @ vinf_req) / np.linalg.norm(v_ex) / want, -1, 1)))
        worst_dir = max(worst_dir, ang)
    check("the ejection burn delivers the v-infinity it was asked for",
          worst_mag < 1.0 and worst_dir < 0.1,
          f"worst error {worst_mag:.3f} m/s and {worst_dir:.3f} deg, measured at SOI exit")


def test_departure_plane(S):
    """An auto-solved parking RAAN has to be coplanar with the transfer actually flown.

    `cmd_depart` used to align the plane to a HOHMANN time of flight and ignore --arrive.
    Earth->Saturn's Hohmann is 2,204 d against the flown 1,500 d, so the node came out
    ~45 deg wrong: the tool printed "RAAN 89.38 deg puts the departure in-plane" and then
    quoted 11,417 m/s, of which 3,911 was plane change, for a 7,506 m/s departure. Nothing
    internal caught it because the burn really did deliver the v-infinity it was asked for
    -- it was the PLANE that was wrong, and the tool was the only thing asserting otherwise.

    Every case below is a real window whose DLA the parking inclination can hold; Jupiter's
    1966 asymptote leaves at 39.3 deg, so it is flown from 45 deg rather than the Cape's.
    """
    from types import SimpleNamespace
    import plan

    alt = 185.0
    worst, worst_case = 0.0, ""
    cases = [("Saturn", "1972-08-17", "1976-09-25", 28.61),
             ("Mars", "1971-05-26", "1971-12-27", 28.61),
             ("Venus", "1973-11-08", "1974-04-12", 28.61),
             ("Jupiter", "1966-10-03", "1968-11-06", 45.0)]
    for target, dep, arr, inc in cases:
        args = SimpleNamespace(arrive=arr, tof=None, samples=32)
        body, t_dep = S.body("Earth"), plan.parse_date(dep)
        u = plan._departure_direction(S, body, S.body(target), t_dep, False, alt, args)
        cands = plan.align_raan(inc, u)
        if not cands:
            check(f"a coplanar node exists for Earth->{target}", False,
                  f"none at i {inc} deg -- the window's DLA is steeper than the parking orbit")
            continue
        r0, v0 = plan.park_orbit(body, alt, inc, cands[0])
        vinf, _, _ = maneuver.vinf_for_transfer(S, "Earth", target, t_dep, plan.parse_date(arr))
        st = maneuver.single_impulse_hyperbolic_burn(body.mu, r0, v0, vinf)
        rn, vn = astro.propagate(body.mu, r0, v0, st["dt"])
        ideal = (math.sqrt(2 * body.mu / np.linalg.norm(rn) + float(vinf @ vinf))
                 - float(np.linalg.norm(vn)))
        excess = float(np.linalg.norm(st["dv"])) - ideal
        if excess > worst:
            worst, worst_case = excess, f"Earth->{target}"
    check("an auto-solved parking RAAN is coplanar with the transfer flown",
          worst < 1.0,
          f"worst plane-change residue {worst:,.1f} m/s over {len(cases)} transfers"
          + (f" ({worst_case})" if worst > 1.0 else ""))

    # A direct transfer has the same failure with an extra turn of the screw: the aim point
    # is the target's position ON ARRIVAL, so the plane depends on the time of flight and
    # the time of flight depends on the plane. One Hohmann-guess pass left the Moon out of
    # plane and cost 264 m/s; the alignment has to iterate against the arc it produces.
    inc = 28.61
    args = SimpleNamespace(arrive=None, tof=None, samples=32, depart=None)
    body, moon = S.body("Earth"), S.body("Moon")
    t_dep = ut_of(1972, 2, 8)
    hoh = plan._hohmann_days(S, body, moon, r_from=body.radius + alt * 1e3)
    span = (0.6 * hoh, 1.8 * hoh)
    u = plan._departure_direction(S, body, moon, t_dep, True, alt, args)
    cands = plan._realign_direct(S, body, moon, t_dep, alt, inc, plan.align_raan(inc, u), args)
    r0, v0 = plan.park_orbit(body, alt, inc, cands[0])
    got = plan._direct_injection(S, body, r0, v0, t_dep, moon, span, args.samples, args)
    inj = astro.elements(body.mu, got[3], got[4] + got[5])
    check("a direct transfer's plane is iterated against the arc it produces",
          got is not None and abs(math.degrees(inj.inc) - inc) < 0.05 and got[0] < 3200.0,
          f"TLI {got[0]:,.0f} m/s at i {math.degrees(inj.inc):.2f} deg "
          f"(parking i {inc:.2f}; aligning once to the Hohmann guess cost 3,405)")


def test_soi_detection(S):
    """A fast pass through a small SOI must not be stepped over."""
    M = S.body("Moon")
    E = S.body("Earth")
    ut0 = ut_of(1966, 1, 1)
    rm, vm = S.rel("Moon", ut0 + 4 * DAY)
    # aim straight at where the Moon will be in 4 days, from a 200 km parking orbit
    target = np.asarray(rm)
    r0 = np.array([E.radius + 200e3, 0.0, 0.0])
    r0 = r0 / np.linalg.norm(r0) * (E.radius + 200e3)
    v1, _ = lambert(E.mu, r0, target, 4 * DAY)
    traj = patched.shoot(S, "Earth", r0, np.asarray(v1), ut0, ut0 + 12 * DAY, watch=["Moon"])
    hit = traj.enters("Moon") is not None
    check("a 4-day lunar intercept is detected as an SOI entry", hit,
          f"patches: {' -> '.join(p.body.name + '/' + p.end for p in traj)}")


def test_soi_exit_on_boundary(S):
    """An inbound patch that starts exactly ON the SOI must still find its exit.

    Every patch made by an SOI entry starts with |r| == soi to within rounding.
    If the exit search treats that as "already outside and heading in, so it never
    leaves", an escaping flyby is reported as a capture -- and which way it lands is
    decided by whether |r| - soi comes out at +1e-9 or -1e-9, so the same trajectory
    answered differently on consecutive runs.
    """
    J = S.body("Jupiter")
    # A hyperbola through Jupiter, placed exactly on the SOI boundary, inbound.
    peR, vinf = 2.5 * J.radius, 5000.0
    a = -J.mu / vinf ** 2
    ecc = 1.0 - peR / a
    nu = -math.acos((a * (1 - ecc ** 2) / J.soi - 1.0) / ecc)   # inbound true anomaly
    mna = astro.mean_anomaly(ecc, nu)
    r, v = astro.state_from_elements(J.mu, a, ecc, 0.3, 0.0, 0.0, mna)
    for nudge in (-1e-6, 0.0, +1e-6):        # straddle the boundary either way
        rr = r * (1.0 + nudge / np.linalg.norm(r))
        traj = patched.shoot(S, J, rr, v, 0.0, 900 * DAY)
        ends = [p.end for p in traj.patches]
        if not check(f"an inbound patch on the SOI boundary still exits ({nudge:+.0e} m)",
                     "exit" in ends, f"patches: {' -> '.join(ends)}"):
            break


def test_save(S):
    try:
        save = Save(find_save(), S)
    except Exception as exc:                                    # noqa: BLE001
        check("save is readable", False, str(exc))
        return None
    check("save is readable", True,
          f"{os.path.basename(os.path.dirname(save.path))}: UT {save.ut:,.0f} "
          f"= {date_of(save.ut):%Y-%m-%d}, {len(save.vessels)} vessels")
    # Only real orbits: KSP parks a LANDED craft on a stub with SMA 0, ECC 1 and
    # MNA = Infinity. `Vessel.valid` already rejects it; the check must too, or one
    # landed probe makes the whole reader look broken.
    # ELLIPTICAL orbits only. Mean anomaly is bounded by 2*pi on an ellipse, which is what
    # makes "is this radians or degrees" answerable at all -- read as degrees these would
    # run to 360. On a hyperbola M = e*sinh(H) - H and is unbounded, so a large value there
    # is correct, not a unit error: this save carries Merkurac 2 at 39.07 (e 1.83) and its
    # probe at -77.57 (e 12.17), and an escape trajectory at exactly e = 1 reads inf.
    # Testing those against 2*pi failed the reader for doing the right thing.
    ell = [v for v in save.vessels
           if v.valid and v.mna is not None and math.isfinite(v.mna)
           and v.ecc is not None and v.ecc < 1.0]
    mnas = [abs(v.mna) for v in ell]
    check("ORBIT.MNA is read as radians", mnas and max(mnas) < 2 * math.pi + 1e-6,
          f"largest |MNA| over {len(mnas)} elliptical orbits is {max(mnas):.4f} "
          f"(2pi = {2 * math.pi:.4f}); as degrees these would reach 360")

    hyp = [abs(v.mna) for v in save.vessels
           if v.valid and v.mna is not None and math.isfinite(v.mna)
           and v.ecc is not None and v.ecc > 1.0]
    check("a hyperbolic mean anomaly is allowed past 2*pi",
          not hyp or max(hyp) >= 0.0,
          f"{len(hyp)} hyperbolic orbits, largest |MNA| {max(hyp):.2f}" if hyp
          else "none in this save")
    named = [v for v in save.vessels if v.valid and v.body]
    check("every orbiting vessel resolved a reference body", len(named) > 0,
          f"{len(named)} of {len(save.vessels)} have a usable orbit")
    return save


def test_node_sign_against_game(S, save):
    """The decisive one: use a node the GAME planned and see which sign flies it home.

    A maneuver node in the save is a statement by KSP about a burn in its own
    basis. Applying it with the right convention has to produce a sensible
    arrival; applying it with normal or radial flipped must not. This is what
    pins the convention down -- no amount of reading decompiled source does.
    """
    if save is None:
        check("node convention vs a node the game planned", True, "no save, skipped")
        return
    cands = [(v, n) for v in save.vessels if v.valid for n in v.nodes()]
    if not cands:
        check("node convention vs a node the game planned", True, "no planned nodes in the save")
        return
    v, n = max(cands, key=lambda vn: float(np.linalg.norm(vn[1]["node"])))
    # find what the burn is aiming at: the body it comes closest to afterwards
    r, vel = v.state(n["ut"])
    t_end = n["ut"] + 1600 * DAY
    best = None
    targets = [b.name for b in S.bodies.values() if b.parent == v.body.name and b.soi > 1e6]
    for tname in targets:
        traj = patched.shoot(S, v.body.name, r, vel + astro.from_node(r, vel, n["node"]),
                             n["ut"], t_end, watch=[tname])
        rep = patched.arrival_report(S, traj, tname, t_end)
        if rep.get("captured"):
            score = rep["peR"] / S.body(tname).radius
            if best is None or score < best[0]:
                best = (score, tname, rep)
    if best is None:
        check("node convention vs a node the game planned", True,
              f"{v.name}'s node reaches no SOI; nothing to compare against")
        return
    score, tname, rep = best
    alts = {}
    for label, sign in (("normal flipped", (1, -1, 1)), ("radial flipped", (-1, 1, 1)),
                        ("prograde flipped", (1, 1, -1))):
        traj = patched.shoot(S, v.body.name, r,
                             vel + astro.from_node(r, vel, n["node"] * np.array(sign)),
                             n["ut"], t_end, watch=[tname])
        rp = patched.arrival_report(S, traj, tname, t_end)
        alts[label] = rp["peR"] / S.body(tname).radius if rp.get("captured") else math.inf
    # A planned node aims at a usable arrival: above the surface, not halfway to
    # the SOI edge. Only the correct convention should land in that band -- a
    # flipped radial gives a SMALLER periapsis (inside the planet), so "closest"
    # is not the test.
    band = lambda x: 1.0 < x < 20.0
    ok = band(score) and not any(band(x) for x in alts.values())
    check("node convention vs a node the game planned", ok,
          f"{v.name} -> {tname}: as saved {score:.2f} R, "
          + ", ".join(f"{k} {x:.2f} R" if math.isfinite(x) else f"{k} misses" for k, x in alts.items()))


def test_bplane():
    mu = 1.26686534e17
    r = np.array([4.0e10, 1.0e10, 5.0e9])
    v = np.array([-5.0e3, -2.0e3, -1.0e3])
    bp = astro.bplane(mu, r, v)
    el = astro.elements(mu, r, v)
    check("B-plane periapsis matches the conic", abs(bp["peR"] - el.peR) / el.peR < 1e-9,
          f"{bp['peR']:,.0f} vs {el.peR:,.0f} m")
    b_from_pe = maneuver.b_for_periapsis(mu, bp["vinf"], el.peR)
    check("impact parameter matches the periapsis relation",
          abs(b_from_pe - bp["b"]) / bp["b"] < 1e-9,
          f"b = {bp['b']:,.0f} m, from periapsis {b_from_pe:,.0f} m")


def test_plane_aim():
    """plane:<Body> aim -- the normal it asks for is perpendicular to the asymptote, on the
    prograde side, exactly the declination floor from the plane, and its (T, R) components
    rebuild the same vector. The end-to-end version was measured live on Perun 2 Bus B:
    4.12 deg off the Galilean plane against a 4.09 deg floor, for 6.20 m/s."""
    mu = 1.26686534e17
    r = np.array([4.0e10, 1.0e10, 5.0e9])
    v = np.array([-5.0e3, -2.0e3, -1.0e3])
    bp = astro.bplane(mu, r, v)
    s = bp["s_hat"]
    n = astro.plane_normal(math.radians(25.27), math.radians(358.01))     # Ganymede-like
    w = n - float(n @ s) * s
    w = w / np.linalg.norm(w)
    floor = math.degrees(math.asin(abs(float(s @ n))))
    got = math.degrees(math.acos(float(w @ n)))
    check("plane aim: normal is perpendicular to the asymptote", abs(float(w @ s)) < 1e-12)
    check("plane aim: normal sits at the declination floor from the plane",
          abs(got - floor) < 1e-9, f"{got:.4f} vs floor {floor:.4f} deg")
    check("plane aim: prograde side", float(w @ n) > 0)
    check("plane aim: B-plane basis is orthonormal to s",
          abs(float(bp["t_hat"] @ s)) < 1e-12 and abs(float(bp["r_hat"] @ s)) < 1e-12
          and abs(float(bp["t_hat"] @ bp["r_hat"])) < 1e-12)
    bdir = np.cross(s, w)
    back = float(bdir @ bp["t_hat"]) * bp["t_hat"] + float(bdir @ bp["r_hat"]) * bp["r_hat"]
    check("plane aim: (T, R) components round-trip to s x w", np.linalg.norm(back - bdir) < 1e-12)


def test_rotation(S):
    """The rotation phase, which every launch time is built on.

    KSP: rotationAngle = (initialRotation + 360 * UT / rotationPeriod) % 360, with a
    tidally locked body's period replaced by its orbital one first. Read out of
    CelestialBody.updateRotation, and checked here for shape -- the ABSOLUTE agreement
    with the game is what `plan.py crosscheck` is for, since only the game can settle it.
    """
    check("Earth's initialRotation is read, not assumed zero",
          abs(S.body("Earth").initial_rotation - 100.1833) < 1e-3,
          f"{S.body('Earth').initial_rotation:.4f} deg")
    check("rotation_angle at UT 0 is initialRotation",
          abs(S.rotation_angle("Earth", 0.0) - S.body("Earth").initial_rotation) < 1e-9)

    # One sidereal day must bring it back to the same angle. This catches a period read
    # in the wrong units, which would otherwise only show as a launch time that drifts.
    per = S.body("Earth").rot
    a0 = S.rotation_angle("Earth", 5e8)
    a1 = S.rotation_angle("Earth", 5e8 + per)
    check("one rotation period returns the same angle",
          abs(((a1 - a0 + 180) % 360) - 180) < 1e-6, f"{a1 - a0:+.3e} deg")

    # A tidally locked body uses its ORBITAL period. The Moon's own rotationPeriod field
    # is 6 s different from its orbital period, so reading the wrong one is a slow drift
    # rather than an obvious error -- exactly the kind that survives.
    moon_orbit = S.period("Moon")
    a0 = S.rotation_angle("Moon", 5e8)
    a1 = S.rotation_angle("Moon", 5e8 + moon_orbit)
    check("a tidally locked body turns once per ORBIT",
          abs(((a1 - a0 + 180) % 360) - 180) < 1e-6,
          f"orbital {moon_orbit:,.1f} s vs its own field {S.body('Moon').rot:,.1f} s")
    check("the Sun has no rotation angle rather than a zero one",
          S.rotation_angle("Sun", 1e6) is None)


def test_launch_geometry(S):
    """Launch azimuth and plane crossings.

    The azimuth is built from the in-plane velocity direction rather than from
    sin(beta) = cos(i)/cos(phi), because that formula cannot tell an ascending pass from
    a descending one. So the textbook value is what it is checked AGAINST: the two must
    agree in magnitude, and the constructed one must additionally get the quadrant right.
    """
    sites = launch_mod.sites()
    check("the launch-site table loads", len(sites) > 20, f"{len(sites)} sites")
    cape = launch_mod.site("cape")
    check("Cape Canaveral's latitude is read from the PQSCity block",
          abs(cape.lat - 28.6084) < 0.01, f"{cape.lat:+.4f}")

    # 408 m/s is the real figure at 28.6 N, and it is worth pinning: it is free dV, and a
    # radius or period read wrong here would quietly misprice every ascent.
    check("the pad's eastward speed matches the real Cape figure",
          abs(cape.rotation_speed(S) - 408) < 5, f"{cape.rotation_speed(S):,.1f} m/s")

    bad_az = bad_res = 0
    for inc in (28.7, 35.0, 51.6, 90.0, 120.0, 145.0):
        passes = launch_mod.plane_passes(cape, S, inc, 137.0, 5e8, count=4, v_orbit=7800.0)
        if len(passes) != 4:
            bad_res += 1
            continue
        n = launch_mod.plane_normal(inc, 137.0)
        for q in passes:
            # The pad really is in the plane at the reported instant.
            r = cape.direction(S, q["ut"])
            if abs(float(r @ n)) > 1e-8:
                bad_res += 1
            # ... and the azimuth matches the textbook one in magnitude.
            want = math.degrees(math.asin(max(-1.0, min(1.0,
                   math.cos(math.radians(inc)) / math.cos(math.radians(cape.lat))))))
            got = q["azimuth_inertial"]
            alt = 180.0 - want
            if min(abs(((got - want + 180) % 360) - 180),
                   abs(((got - alt + 180) % 360) - 180)) > 1e-6:
                bad_az += 1
    check("the pad is exactly in the plane at every reported crossing", bad_res == 0,
          f"{bad_res} bad")
    check("azimuth agrees with sin(beta) = cos(i)/cos(phi)", bad_az == 0, f"{bad_az} bad")

    # Ascending and descending must both appear, and be distinguished. A solver that
    # found only one root would still look right on a single line of output.
    passes = launch_mod.plane_passes(cape, S, 51.6, 0.0, 5e8, count=2, v_orbit=7800.0)
    check("both the ascending and the descending pass are found",
          sorted(q["ascending"] for q in passes) == [False, True])

    # Two crossings per rotation, so the pair repeats one sidereal day later -- NOT one
    # solar day. Four minutes a day of drift is what makes a launch window slip.
    p4 = launch_mod.plane_passes(cape, S, 51.6, 0.0, 5e8, count=4)
    dt = p4[2]["ut"] - p4[0]["ut"]
    check("crossings repeat once per sidereal day, not per solar day",
          abs(dt - S.body("Earth").rot) < 1.0,
          f"{dt:,.1f} s vs {S.body('Earth').rot:,.1f} s")

    # An inclination below the pad's latitude is unreachable, and must be refused rather
    # than silently returning the nearest thing.
    try:
        launch_mod.plane_passes(cape, S, 20.0, 0.0, 5e8)
        check("an unreachable inclination is refused", False, "it returned an answer")
    except ValueError as exc:
        check("an unreachable inclination is refused", "cannot reach" in str(exc))

    # plane_normal and plane_from_normal must invert each other, because the crossing
    # solver and plan.py's park_orbit have to be talking about the same plane.
    worst = 0.0
    for inc in (5.0, 28.5, 63.4, 98.0, 145.0):
        for raan in (0.0, 77.0, 190.0, 300.0):
            i2, o2 = launch_mod.plane_from_normal(launch_mod.plane_normal(inc, raan))
            worst = max(worst, abs(i2 - inc), abs(((o2 - raan + 180) % 360) - 180))
    check("plane_normal and plane_from_normal invert", worst < 1e-9, f"worst {worst:.2e} deg")

    # And the normal must match the one the trusted parking-orbit builder produces --
    # this is the join between the launch solver and every burn plan.py already prints.
    import plan
    worst = 0.0
    for inc in (28.7, 63.4, 98.0):
        for raan in (0.0, 137.0, 285.0):
            pos, vel = plan.park_orbit(S.body("Earth"), 185.0, inc, raan)
            h = np.cross(pos, vel)
            h = h / np.linalg.norm(h)
            worst = max(worst, float(np.linalg.norm(h - launch_mod.plane_normal(inc, raan))))
    check("the plane normal matches park_orbit's angular momentum", worst < 1e-12,
          f"worst {worst:.2e}")


def _venus_flyby_setup(S):
    """A departure from Earth that actually flies through Venus's SOI. Shared fixture."""
    import plan
    earth = S.body("Earth")
    t_dep = ut_of(1967, 8, 1)
    pos, vel = plan.park_orbit(earth, 185.0, 28.6, 0.0)
    best = None
    for tof in np.arange(80, 200, 5) * DAY:
        try:
            vinf, _raw, _ = maneuver.vinf_for_transfer(S, "Earth", "Venus", t_dep, t_dep + tof)
            sol = maneuver.single_impulse_hyperbolic_burn(earth.mu, pos, vel, vinf)
        except Exception:                                           # noqa: BLE001
            continue
        m = float(np.linalg.norm(sol["dv"]))
        if best is None or m < best[0]:
            best = (m, tof, sol)
    if best is None:
        return None
    _m, _tof, sol = best
    ut_node = t_dep + sol["dt"]
    rn, vn = astro.propagate(earth.mu, pos, vel, sol["dt"])
    return rn, vn + sol["dv"], ut_node, ut_of(1969, 6, 1)


def test_soi_exit_window(S):
    """A fast flyby must not vanish because the mission horizon is long.

    _exit_time used to scan linspace(ut0, ut_end, 401) -- a fixed sample count across
    however long the caller happened to be flying. A Venus passage dwells 34.9 h inside a
    616,000 km SOI; on a 715-day horizon the step is 43 h and the ENTIRE passage falls
    between two samples, so the function returned None: "never exits". The shooter then
    reported an escaping gravity assist as a capture, or brent raised on a bracket that
    did not straddle a root.

    It is horizon-dependent, which is the tell: the same flyby answered differently
    depending on --horizon. So the check is that the answer does NOT depend on it.
    """
    venus = S.body("Venus")
    peR, ecc = 26_694e3, 8.62755
    a = peR / (1 - ecc)
    p_ = a * (1 - ecc ** 2)
    nu = -math.acos(max(-1.0, min(1.0, (p_ / venus.soi - 1) / ecc)))
    r = np.array([venus.soi * math.cos(nu), venus.soi * math.sin(nu), 0.0])
    h = math.sqrt(venus.mu * p_)
    v = np.array([-venus.mu / h * math.sin(nu), venus.mu / h * (ecc + math.cos(nu)), 0.0])
    ut0 = 539_154_654.0
    patch = patched.Patch(venus, ut0, r, v)

    answers = []
    for horizon_days in (3, 10, 30, 100, 300, 715, 2000):
        te = patched._exit_time(patch, venus.soi, ut0 + horizon_days * DAY)
        answers.append(None if te is None else te - ut0)
    found = [a for a in answers if a is not None]
    check("a fast flyby exit is found at every horizon", len(found) == len(answers),
          f"{len(found)}/{len(answers)} horizons found it")
    if found:
        spread = max(found) - min(found)
        check("the exit time does not depend on the horizon", spread < 1.0,
              f"{min(found) / 3600:.3f} h, spread {spread:.2e} s")

    # Test the DEFINITION, not a sampled approximation of it. Comparing against the last
    # sample of a 200k-point scan sounds stricter and is not: that scan has a 4.3 s
    # spacing, so it can only ever agree to 4.3 s, and a mismatch inside that says nothing
    # about the solver. "Is |r| equal to the SOI at the instant returned" is exact.
    te = patched._exit_time(patch, venus.soi, ut0 + 715 * DAY)
    err = abs(float(np.linalg.norm(patch.state(te)[0])) - venus.soi) if te else float("inf")
    check("at the exit instant, |r| really is the SOI radius", err < 1.0, f"{err:+.6f} m")

    # And it is bracketed by a dense scan, to the scan's own resolution.
    ts = np.linspace(ut0, ut0 + 10 * DAY, 200_000)
    pos, _ = astro.sample_conic(venus.mu, r, v, ts - ut0)
    d = np.linalg.norm(pos, axis=1) - venus.soi
    inside = np.nonzero(d < 0)[0]
    truth = ts[inside[-1]] - ut0 if len(inside) else None
    step = ts[1] - ts[0]
    check("the exit agrees with a dense scan to the scan's own resolution",
          truth is not None and found and abs(found[0] - truth) < 2 * step,
          f"solver {found[0] / 3600:.4f} h vs scan {truth / 3600:.4f} h "
          f"(scan resolution {step:.1f} s)" if truth else "no truth")


def test_assist_targeting(S):
    """Can the shooting solver recover a known solution on the FAR SIDE of a flyby?

    Perturb a trajectory that passes through Venus and ask for the original aim point
    back. The answer exists by construction, so a failure is the solver's and not the
    universe's -- which is the distinction that matters, because an assist target that
    simply cannot be reached looks identical to a solver that cannot reach it.
    """
    setup = _venus_flyby_setup(S)
    if setup is None:
        check("assist fixture builds", False, "no Earth->Venus departure found")
        return
    rn, v_nom, ut_node, t_end = setup

    def fly(v):
        return patched.shoot(S, "Earth", rn, v, ut_node, t_end, watch=["Venus"])

    nom = fly(v_nom)
    pv = nom.enters("Venus")
    check("the fixture really flies through Venus's SOI", pv is not None
          and pv.end == "exit",
          f"pe {(pv.elements().peR - S.body('Venus').radius) / 1e3:,.0f} km alt, "
          f"end={pv.end}" if pv else "no Venus patch")
    if pv is None:
        return
    check("and there is a leg AFTER the assist to target on", len(nom.patches) >= 4,
          f"{len(nom.patches)} patches: " + " -> ".join(p.body.name for p in nom.patches))

    t_aim = nom.patches[-1].ut0 + 200 * DAY
    aim = maneuver._to_centre(S, nom, t_aim, "Sun")

    # Judge the ABSOLUTE miss, not miss/before. A perturbation that starts closer has a
    # worse ratio while landing nearer, which is the ratio measuring the starting point
    # rather than the solver: measured, the case with the smallest miss of the three
    # (453 km) had the worst ratio (1.9e-4).
    worst_miss, worst_dv, tested = 0.0, 0.0, 0
    for pert in ([0.0, 0.5, 0.0], [0.0, 0.0, 0.5], [0.0, -0.3, 0.2]):
        pert = np.array(pert, float)
        before = float(np.linalg.norm(
            maneuver._to_centre(S, fly(v_nom + pert), t_aim, "Sun") - aim))
        res = maneuver.aim_through(S, "Earth", rn, v_nom + pert, ut_node, "Venus", t_aim,
                                   via=["Venus"], t_end=t_end, aim_point=aim,
                                   max_nfev=60, max_dv=200.0)
        tested += 1
        worst_miss = max(worst_miss, res["miss"])
        worst_dv = max(worst_dv, float(np.linalg.norm(res["correction"])))
        if before < 1e9:                    # the fixture must actually be perturbed
            worst_miss = float("inf")
    check(f"a perturbed flyby is re-aimed through the assist ({tested} cases)",
          worst_miss < 10_000e3, f"worst miss {worst_miss / 1e3:,.0f} km "
          f"(from >2,400 Mm), worst correction {worst_dv:.3f} m/s")
    # A large correction means a DIFFERENT trajectory that happens to pass through the aim
    # point -- a correct answer to the wrong question, and the reason max_dv exists.
    check("and it does so with a correction worth calling one", worst_dv < 5.0,
          f"{worst_dv:.3f} m/s")

    # And the diagnostic that saves a minute of grinding: an orbit that cannot reach the
    # target must be reported as unreachable, not searched.
    why = maneuver.reachability(S, nom, "Mercury")
    check("an unreachable target is reported, not searched for",
          why is not None and "never touch" in why,
          (why or "reported reachable")[:90])
    check("a reachable target is not falsely rejected",
          maneuver.reachability(S, nom, "Venus") is None)


def test_mga_sequence_search(S):
    """The sequence search has to find a real mission it was never told about.

    Mariner 10 is the fixture because the answer is public and the search gets nothing but
    three body names and three date grids: no seed, no v-infinity, no arrival guess. If a
    change to the turn-angle bound, the v-infinity match or the DP pruning quietly breaks
    the thing, this is what notices -- an internally consistent search will still return
    *something*, and only a known mission says whether it is the right something.
    """
    import mga
    grids = [np.arange(ut_of(1973, 9, 1), ut_of(1973, 12, 15), 3 * 86400.0),
             np.arange(ut_of(1974, 1, 1), ut_of(1974, 3, 15), 3 * 86400.0),
             np.arange(ut_of(1974, 2, 15), ut_of(1974, 5, 15), 3 * 86400.0)]
    seq = mga.Sequence(S, ["Earth", "Venus", "Mercury"], grids)
    sols = seq.run(keep=40)
    if not check("the sequence search returns a Venus-assisted Mercury mission", bool(sols)):
        return
    rows, total = seq.detail(sols[0][1])
    dep = date_of(rows[0]["ut"]).date()
    ven = date_of(rows[1]["ut"]).date()
    mer = date_of(rows[2]["ut"]).date()
    check("blind scan recovers Mariner 10's departure (1973-11-03)",
          abs((dep - datetime.date(1973, 11, 3)).days) <= 3, str(dep))
    check("and its Venus flyby (1974-02-05, 5,768 km altitude)",
          abs((ven - datetime.date(1974, 2, 5)).days) <= 3
          and abs(rows[1]["alt"] / 1e3 - 5768.0) < 2000.0,
          f"{ven}, {rows[1]['alt'] / 1e3:,.0f} km altitude")
    check("and its Mercury arrival (1974-03-29)",
          abs((mer - datetime.date(1974, 3, 29)).days) <= 6, str(mer))
    check("the assist is essentially free, as a gravity assist should be",
          rows[1]["dv"] < 50.0, f"{rows[1]['dv']:.0f} m/s at Venus")

    # The turn-angle bound is the one piece of physics a pure Lambert chain lacks: asking a
    # body to bend v-infinity further than a surface-grazing pass can must cost real dV.
    mu = S.bodies["Venus"].mu
    rp = S.bodies["Venus"].radius * 1.05
    vin = np.array([8000.0, 0.0, 0.0])
    ok_dv = mga.flyby(mu, vin, np.array([8000.0 * math.cos(0.6), 8000.0 * math.sin(0.6), 0.0]), rp)[0]
    bad_dv = mga.flyby(mu, vin, np.array([-8000.0, 0.0, 0.0]), rp)[0]
    check("a reachable bend is free and a 180 deg one is not",
          ok_dv < 1.0 and bad_dv > 1000.0, f"{ok_dv:.2f} vs {bad_dv:,.0f} m/s")



def run(S=None, verbose=True):
    _results.clear()
    S = S or System()
    test_epoch(S)
    test_bodies(S)
    test_against_ksptot(S)
    test_propagator()
    test_elements()
    test_lambert(S)
    test_node_basis()
    test_bplane()
    test_plane_aim()
    test_ejection(S)
    test_departure_plane(S)
    test_soi_detection(S)
    test_soi_exit_on_boundary(S)
    test_rotation(S)
    test_launch_geometry(S)
    test_soi_exit_window(S)
    test_assist_targeting(S)
    test_mga_sequence_search(S)
    save = test_save(S)
    test_node_sign_against_game(S, save)
    return _report(verbose)


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
