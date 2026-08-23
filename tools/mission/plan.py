"""Mission burns for this install, read from the save and checked by flying them.

    python plan.py bodies
    python plan.py vessels
    python plan.py state "Perun 1"
    python plan.py window Earth Jupiter 1964-01-01 1968-01-01
    python plan.py depart --vessel "Perun 2" --target Jupiter --arrive 1970-05-01
    python plan.py depart --park 185 28.5 --body Earth --target Moon
    python plan.py correct --vessel "Perun 1" --target Jupiter --peri 2.5Rj
    python plan.py flyby   --vessel "Perun 1" Jupiter
    python plan.py verify  --vessel "Perun 1" --target Jupiter
    python plan.py selftest

Every burn is printed in the form KSP wants it: a UT and the three ManeuverNode
components. Every answer is followed by what happens when the result is actually
flown, because the two have disagreed before.
"""
import argparse
import json
import math
import sys

import numpy as np

import astro
import maneuver
import patched
from lambert import lambert
from rss_ephem import DAY, System, date_of, fmt_ut, parse_date
from sfs import Save, find_save

AU = 1.495978707e11


# ---------------------------------------------------------------------------
# shared plumbing
# ---------------------------------------------------------------------------
def load(args):
    """System always; the save too whenever the command could want it.

    A command that needs a vessel must fail loudly if the save is unreadable,
    but one that merely offers the game clock should not.
    """
    system = System(instance=args.instance)
    save = None
    if hasattr(args, "save"):
        try:
            save = Save(find_save(getattr(args, "save", None), args.instance), system)
        except Exception as exc:                                # noqa: BLE001
            if getattr(args, "vessel", None):
                sys.exit(f"cannot read the save: {exc}")
    return system, save


def parse_radius(system, body, text, default_alt=None):
    """'2.5Rj', '250km', '250000', or a bare altitude in km."""
    b = system.body(body)
    if text is None:
        return b.radius + (default_alt if default_alt is not None else 100e3)
    t = str(text).strip().lower().replace(",", "")
    if t.endswith("r") or (len(t) > 1 and t[-2] == "r"):
        return float(t[:-2] if t[-2] == "r" else t[:-1]) * b.radius
    if t.endswith("rj") or t.endswith("re") or t.endswith("rm"):
        return float(t[:-2]) * b.radius
    if t.endswith("km"):
        return b.radius + float(t[:-2]) * 1e3
    val = float(t)
    return b.radius + val * 1e3 if val < 1e6 else val


def park_orbit(body, alt_km, inc_deg, raan_deg):
    """A circular parking orbit as a state vector, taken at its ascending node."""
    inc, raan = math.radians(inc_deg), math.radians(raan_deg)
    r = body.radius + alt_km * 1e3
    vc = math.sqrt(body.mu / r)
    pos = np.array([r * math.cos(raan), r * math.sin(raan), 0.0])
    east = np.array([-math.sin(raan), math.cos(raan), 0.0])
    vel = vc * (east * math.cos(inc) + np.array([0.0, 0.0, 1.0]) * math.sin(inc))
    return pos, vel


def align_raan(inc_deg, u):
    """RAANs whose orbit plane of inclination `inc` contains the direction `u`.

    Departure cost is dominated by plane change, so "what does this burn cost"
    has no answer until you say where the parking orbit's node is. Rather than
    pick one arbitrarily and quote an inflated number, solve for the nodes that
    make the departure coplanar and report which one is needed.
    """
    inc = math.radians(inc_deg)
    u = np.asarray(u, float)
    u = u / np.linalg.norm(u)
    if abs(math.sin(inc)) < 1e-9:
        return []
    a, b = u[0], -u[1]
    c = -u[2] / math.tan(inc)
    rad = math.hypot(a, b)
    if rad < 1e-12 or abs(c) > rad:
        return []                       # this inclination cannot contain u at all
    phi = math.atan2(b, a)
    base = math.asin(max(-1.0, min(1.0, c / rad)))
    return [math.degrees((base - phi) % (2 * math.pi)),
            math.degrees((math.pi - base - phi) % (2 * math.pi))]


def origin_state(system, save, args):
    """Where the burn starts: a real vessel, or a synthetic parking orbit."""
    if args.vessel:
        v = save.vessel(args.vessel)
        if not v.valid:
            sys.exit(f"{v.name}: the save has no usable orbit for it ({v.situation})")
        ut = parse_date(args.at) if args.at else save.ut
        r, vel = v.state(ut)
        return v.body, np.asarray(r), np.asarray(vel), ut, v.name, None
    body = system.body(args.body)
    park = list(args.park) if isinstance(args.park, (list, tuple)) else [args.park]
    alt = float(park[0]) if park else 185.0
    inc = float(park[1]) if len(park) > 1 else 28.5
    raan = float(park[2]) if len(park) > 2 else 0.0
    pos, vel = park_orbit(body, alt, inc, raan)
    ut = parse_date(args.at) if args.at else (save.ut if save else 0.0)
    free = None if len(park) > 2 else (alt, inc)
    return (body, pos, vel, ut, f"{alt:.0f} km x {inc:.1f} deg parking orbit", free)


def print_node(system, body, r, v, dv, ut, now=None, label="BURN"):
    node = astro.to_node(r, v, dv)
    mag = float(np.linalg.norm(dv))
    print(f"  {label}  {fmt_ut(ut)}"
          + (f"   T+{(ut - now) / DAY:,.2f} d from the save" if now is not None else ""))
    print(f"    prograde {node[2]:+12,.2f} m/s")
    print(f"    normal   {node[1]:+12,.2f} m/s")
    print(f"    radial   {node[0]:+12,.2f} m/s")
    print(f"    total    {mag:12,.2f} m/s")
    return node, mag


def print_arrival(system, target, rep, indent="    "):
    t = system.body(target)
    if rep.get("captured"):
        print(f"{indent}FLOWN: enters {t.name} SOI {fmt_ut(rep['soi_ut'])}")
        print(f"{indent}       periapsis {rep['peR'] / 1e3:,.0f} km "
              f"= {rep['peR'] / t.radius:.3f} R{t.name[0].lower()}"
              f"  (altitude {rep['peAlt'] / 1e3:,.0f} km)")
        print(f"{indent}       v-infinity {rep['vinf']:,.1f} m/s   e {rep['ecc']:.4f}   "
              f"inclination {rep['inc']:.2f} deg")
        if rep["peAlt"] < 0:
            print(f"{indent}       *** that periapsis is INSIDE {t.name} ***")
    else:
        print(f"{indent}FLOWN: never enters {t.name}'s SOI.")
        print(f"{indent}       closest approach {rep['ca_dist'] / 1e9:,.3f} Gm at "
              f"{fmt_ut(rep['ca_ut'])} (SOI is {rep['soi'] / 1e9:,.3f} Gm)")
        print(f"{indent}       relative speed {rep['ca_vrel']:,.1f} m/s")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_bodies(args):
    system, _ = load(args)
    print(f"epoch {system.epoch:,.3f} s = {date_of(system.epoch):%Y-%m-%d %H:%M:%S}   "
          f"(SOI/index from {system.log_path or 'DERIVED -- Kopernicus.log missing'})")
    print(f"{'ref':>4s} {'body':10s} {'parent':10s} {'R km':>9s} {'mu':>12s} "
          f"{'SOI km':>14s} {'a Gm':>12s} {'e':>7s} {'i deg':>7s}")
    for b in sorted(system.bodies.values(), key=lambda b: (b.index if b.index is not None else 999)):
        print(f"{b.index if b.index is not None else -1:4d} {b.name:10s} {str(b.parent):10s} "
              f"{b.radius / 1e3:9,.0f} {b.mu:12.5e} {b.soi / 1e3:14,.0f} "
              f"{b.a / 1e9:12,.3f} {b.e:7.4f} {math.degrees(b.inc):7.3f}")


def cmd_vessels(args):
    args.vessel = None
    system, save = load(args)
    print(f"{save.path}   UT {save.ut:,.0f} = {date_of(save.ut):%Y-%m-%d %H:%M}")
    print(f"{'vessel':32s} {'body':10s} {'pe km':>12s} {'ap km':>13s} {'inc':>7s} {'nodes':>5s}")
    for v in save.vessels:
        if not v.valid:
            print(f"{v.name[:32]:32s} {'-':10s} {'(' + (v.situation or '?') + ')':>12s}")
            continue
        el = v.elements(save.ut)
        ap = "escape" if el.ecc >= 1 else f"{(el.apR - v.body.radius) / 1e3:,.0f}"
        print(f"{v.name[:32]:32s} {v.body.name:10s} {(el.peR - v.body.radius) / 1e3:12,.0f} "
              f"{ap:>13s} {math.degrees(el.inc):7.2f} {len(v.nodes()):5d}")


def cmd_state(args):
    system, save = load(args)
    ut = parse_date(args.at) if args.at else (save.ut if save else 0.0)
    try:
        v = save.vessel(args.what) if save else None
    except KeyError:
        v = None
    if v is not None:
        body, r, vel = v.body, *v.state(ut)
        name = v.name
    else:
        b = system.body(args.what)
        body = system.body(b.parent)
        r, vel = system.rel(b.name, ut)
        name = b.name
    r, vel = np.asarray(r), np.asarray(vel)
    el = astro.elements(body.mu, r, vel)
    print(f"{name}  about {body.name}  at {fmt_ut(ut)}")
    print(f"  r = [{r[0]:,.1f} {r[1]:,.1f} {r[2]:,.1f}] m   |r| = {np.linalg.norm(r):,.1f} m "
          f"(alt {(np.linalg.norm(r) - body.radius) / 1e3:,.1f} km)")
    print(f"  v = [{vel[0]:,.3f} {vel[1]:,.3f} {vel[2]:,.3f}] m/s   |v| = {np.linalg.norm(vel):,.3f} m/s")
    print(f"  a {el.sma / 1e3:,.1f} km   e {el.ecc:.6f}   i {math.degrees(el.inc):.4f} deg   "
          f"LAN {math.degrees(el.lan):.4f}   argp {math.degrees(el.argp):.4f}   nu {math.degrees(el.nu):.4f}")
    print(f"  periapsis {(el.peR - body.radius) / 1e3:,.1f} km   apoapsis "
          + ("escape" if el.ecc >= 1 else f"{(el.apR - body.radius) / 1e3:,.1f} km")
          + ("" if el.ecc >= 1 else f"   period {el.period / DAY:,.4f} d"))
    if v is not None:
        for n in v.nodes():
            rr, vv = v.state(n["ut"])
            print(f"  planned node {fmt_ut(n['ut'])}: radial {n['node'][0]:+,.2f}  "
                  f"normal {n['node'][1]:+,.2f}  prograde {n['node'][2]:+,.2f}  "
                  f"|dV| {np.linalg.norm(n['node']):,.2f} m/s")


def cmd_window(args):
    system, _ = load(args)
    dep, arr = system.body(args.dep), system.body(args.arr)
    centre = system.common_parent(dep.name, arr.name)
    mu = system.body(centre).mu
    t0, t1 = parse_date(args.start), parse_date(args.end)
    tof_lo, tof_hi = (args.tof if args.tof else
                      [0.4 * _hohmann_days(system, dep, arr), 2.0 * _hohmann_days(system, dep, arr)])
    deps = np.arange(t0, t1, args.step * DAY)
    tofs = np.arange(tof_lo, tof_hi, args.tofstep) * DAY
    rpark = dep.radius + args.alt * 1e3
    vcirc = math.sqrt(dep.mu / rpark)
    rows = []
    for td in deps:
        r1, v1b = system.state(dep.name, td, centre)
        best = None
        for tf in tofs:
            r2, v2b = system.state(arr.name, td + tf, centre)
            try:
                vt1, vt2 = lambert(mu, np.array(r1), np.array(r2), tf)
            except Exception:
                continue
            vinf_d = np.asarray(vt1) - np.asarray(v1b)
            c3 = float(vinf_d @ vinf_d) / 1e6
            vinf_a = float(np.linalg.norm(np.asarray(vt2) - np.asarray(v2b)))
            dv = math.sqrt(2 * dep.mu / rpark + c3 * 1e6) - vcirc
            dla = math.degrees(math.asin(np.clip(vinf_d[2] / np.linalg.norm(vinf_d), -1, 1)))
            score = dv + (vinf_a if args.include_capture else 0.0)
            if best is None or score < best[0]:
                best = (score, tf, c3, dv, vinf_a, dla)
        if best:
            rows.append((td,) + best[1:])
    if not rows:
        sys.exit("no transfers found in that window")
    # one row per launch window: local minima in departure dV. Once the real
    # windows run out the next-best rows are junk (a 600 km2/s2 C3 is not a
    # window), so cap the ratio to the best and SAY how many were dropped.
    best_c3 = min(r[2] for r in rows)
    picked, order = [], sorted(range(len(rows)), key=lambda i: rows[i][2])
    dropped = 0
    for i in order:
        if any(abs(rows[i][0] - rows[j][0]) <= args.sep * DAY for j in picked):
            continue
        if rows[i][2] > args.max_c3 * best_c3:
            dropped += 1
            continue
        picked.append(i)
        if len(picked) >= args.top:
            break
    print(f"{dep.name} -> {arr.name}  from a {args.alt:.0f} km parking orbit around {dep.name}"
          f"   ({len(deps)} departures x {len(tofs)} TOFs)")
    print(f"{'departure':>12s} {'TOF d':>7s} {'arrival':>12s} {'C3':>8s} {'dv dep':>8s} "
          f"{'vinf arr':>9s} {'DLA':>7s}")
    for i in sorted(picked):
        td, tf, c3, dv, vinf_a, dla = rows[i]
        print(f"{date_of(td):%Y-%m-%d}   {tf / DAY:7.0f} {date_of(td + tf):%Y-%m-%d}   "
              f"{c3:8.2f} {dv:8,.0f} {vinf_a:9,.0f} {dla:7.2f}")
    if dropped:
        print(f"  ({dropped} further local minima were above {args.max_c3:.0f}x the best C3 of "
              f"{best_c3:.1f} and are not launch windows; raise --max-c3 to see them)")


def _hohmann_days(system, dep, arr, r_from=None):
    """Half-period of the Hohmann ellipse between two orbits, in days.

    `r_from` overrides the departure radius for a direct transfer (parking orbit
    to moon) where the two bodies are not siblings.
    """
    if r_from is not None:
        mu = system.body(arr.parent).mu
        a = (r_from + arr.a) / 2
        return math.pi * math.sqrt(a ** 3 / mu) / DAY
    a = (dep.a + arr.a) / 2
    return math.pi * math.sqrt(a ** 3 / system.mu_sun) / DAY


def _direct_injection(system, body, r0, v0, ut0, target, tof_range, samples, args):
    """Target orbits the same body we do: one Lambert arc, no escape hyperbola.

    This is the trans-lunar case. There is no v-infinity to match -- the burn
    point matters instead, so the search runs over phase around the parking
    orbit as well as over time of flight.
    """
    el0 = astro.elements(body.mu, r0, v0)
    period = el0.period if math.isfinite(el0.period) else (tof_range[1] * DAY)
    lo, hi = tof_range
    best = None
    phases = np.linspace(0.0, period, samples, endpoint=False)
    tofs = np.linspace(lo, hi, max(8, samples // 2)) * DAY
    for dphase in phases:
        rb, vb = astro.propagate(body.mu, r0, v0, dphase)
        for tof in tofs:
            t_arr = ut0 + dphase + tof
            rt, _ = system.rel(target.name, t_arr)
            for prograde in (True, False):
                try:
                    v1, _ = lambert(body.mu, rb, np.asarray(rt), tof, prograde=prograde)
                except Exception:
                    continue
                dv = np.asarray(v1) - vb
                m = float(np.linalg.norm(dv))
                if best is None or m < best[0]:
                    best = (m, ut0 + dphase, t_arr, rb, vb, dv)
    return best


def cmd_depart(args):
    system, save = load(args)
    body, r0, v0, ut0, who, free_park = origin_state(system, save, args)
    target = system.body(args.target)
    centre = system.common_parent(body.name, target.name)
    t_dep = parse_date(args.depart) if args.depart else ut0
    if t_dep < ut0:
        sys.exit(f"departure {fmt_ut(t_dep)} is before the state epoch {fmt_ut(ut0)}")
    r0, v0 = astro.propagate(body.mu, r0, v0, t_dep - ut0)
    direct = (target.parent == body.name)
    if free_park is not None:
        alt, inc = free_park
        if direct:
            hoh = _hohmann_days(system, body, target, r_from=body.radius + alt * 1e3)
            u, _ = system.rel(target.name, t_dep + hoh * DAY)
        else:
            hoh = _hohmann_days(system, body, target)
            u, _, _ = maneuver.vinf_for_transfer(system, body.name, target.name,
                                                 t_dep, t_dep + hoh * DAY)
        cands = align_raan(inc, np.asarray(u))
        if cands:
            args._raan_note = cands
            r0, v0 = park_orbit(body, alt, inc, cands[0])
            who += f", RAAN {cands[0]:.1f} deg"
    if body.name == centre and not direct:
        sys.exit(f"{who} already orbits {centre} and {target.name} is not a satellite of it; "
                 f"use `correct` to steer it, not `depart`.")

    print(f"DEPART  {who}  ({body.name} -> {target.name})"
          + ("   [direct transfer, no SOI escape]" if direct else ""))
    if getattr(args, "_raan_note", None):
        print(f"  parking-orbit RAAN was not given, so it was solved for: "
              f"{args._raan_note[0]:.2f} deg puts the departure in-plane "
              f"(the other coplanar node is {args._raan_note[1]:.2f} deg). "
              f"Pass --park ALT INC RAAN to pin your own.")
    el0 = astro.elements(body.mu, r0, v0)
    print(f"  parking orbit: {(el0.peR - body.radius) / 1e3:,.0f} x "
          f"{(el0.apR - body.radius) / 1e3:,.0f} km, i {math.degrees(el0.inc):.2f} deg, "
          f"LAN {math.degrees(el0.lan):.2f} deg, period {el0.period / 60:,.1f} min")

    if direct:
        hoh = _hohmann_days(system, body, target, r_from=float(np.linalg.norm(r0)))
        lo, hi = args.tof if args.tof else [0.6 * hoh, 1.8 * hoh]
        best = _direct_injection(system, body, r0, v0, t_dep, target, (lo, hi),
                                 args.samples, args)
        if best is None:
            sys.exit("no transfer arc found in that time-of-flight range")
        mag, ut_node, t_arr, rn, vn, dv = best
        print(f"  searched phase around one orbit x TOF {lo:.2f}-{hi:.2f} d; best is "
              f"{(t_arr - ut_node) / DAY:.3f} d time of flight, arriving {fmt_ut(t_arr)}")
        print_node(system, body, rn, vn, dv, ut_node, now=(save.ut if save else None))
        hyp = astro.elements(body.mu, rn, vn + dv)
        print(f"    injection orbit: e {hyp.ecc:.5f}, i {math.degrees(hyp.inc):.2f} deg, "
              f"apoapsis "
              + ("escape" if hyp.ecc >= 1 else f"{(hyp.apR - body.radius) / 1e3:,.0f} km")
              + f", coast to burn {(ut_node - t_dep) / 60:,.1f} min")
    else:
        # pick an arrival
        if args.arrive:
            arrivals = [parse_date(args.arrive)]
        else:
            hoh = _hohmann_days(system, body, target)
            lo, hi = args.tof if args.tof else [0.4 * hoh, 2.0 * hoh]
            arrivals = [t_dep + d * DAY for d in np.arange(lo, hi, max((hi - lo) / 60.0, 0.05))]
        best = None
        for t_arr in arrivals:
            try:
                vinf, raw, _ = maneuver.vinf_for_transfer(system, body.name, target.name,
                                                          t_dep, t_arr)
                s = maneuver.single_impulse_hyperbolic_burn(body.mu, r0, v0, vinf)
            except Exception:
                continue
            m = float(np.linalg.norm(s["dv"]))
            if best is None or m < best[0]:
                best = (m, t_arr, vinf, raw, s)
        if best is None:
            sys.exit("no ejection geometry found over that arrival range")
        mag, t_arr, vinf, raw, s = best
        if len(arrivals) > 1:
            print(f"  searched {len(arrivals)} arrival dates; cheapest is "
                  f"{(t_arr - t_dep) / DAY:,.1f} d time of flight")
        c3 = float(vinf @ vinf) / 1e6
        print(f"  transfer: arrive {fmt_ut(t_arr)}   C3 {c3:.3f} km2/s2   "
              f"v-inf {np.linalg.norm(vinf):,.1f} m/s")
        print(f"  (v-inf at the planet centre would be {np.linalg.norm(raw):,.1f} m/s; "
              f"the SOI-crossing correction moved it {np.linalg.norm(vinf - raw):,.1f} m/s)")
        ut_node = t_dep + s["dt"]
        rn, vn = astro.propagate(body.mu, r0, v0, s["dt"])
        dv = s["dv"]
        print_node(system, body, rn, vn, dv, ut_node, now=(save.ut if save else None))
        hyp = astro.elements(body.mu, rn, vn + dv)
        print(f"    ejection hyperbola: e {hyp.ecc:.5f}, i {math.degrees(hyp.inc):.2f} deg, "
              f"periapsis {(hyp.peR - body.radius) / 1e3:,.0f} km, coast to burn "
              f"{s['dt'] / 60:,.1f} min")
        ideal = math.sqrt(2 * body.mu / np.linalg.norm(rn) + c3 * 1e6) - float(np.linalg.norm(vn))
        if mag - ideal > 1.0:
            print(f"    {mag - ideal:,.0f} m/s of that is plane change -- a coplanar departure "
                  f"from this altitude would cost {ideal:,.0f} m/s.")

    t_end = t_arr + args.horizon * DAY
    peR = parse_radius(system, target, args.peri, default_alt=None) if args.peri else None
    traj = patched.shoot(system, body.name, rn, vn + dv, ut_node, t_end,
                         watch=[target.name] + list(args.via or []))
    rep = patched.arrival_report(system, traj, target.name, t_end)
    print("\n  --- as computed ---")
    print_arrival(system, target.name, rep)

    if peR and not args.no_refine:
        print(f"\n  --- corrected to periapsis {peR / target.radius:.3f} "
              f"R{target.name[0].lower()} ({(peR - target.radius) / 1e3:,.0f} km altitude) ---")
        res = maneuver.refine(system, body.name, rn, vn + dv, ut_node, target.name,
                              t_end, peR_want=peR, watch=[target.name] + list(args.via or []))
        print_node(system, body, rn, vn, dv + res["dv"], ut_node,
                   now=(save.ut if save else None), label="BURN")
        print(f"    (that is {np.linalg.norm(res['dv']):,.2f} m/s different from the "
              f"uncorrected burn, found in {res['nfev']} shots)")
        print_arrival(system, target.name, res["report"])
        traj = res["traj"]
    if args.trajectory:
        print("\n  patches:")
        for line in traj.summary().splitlines():
            print("   ", line)


def cmd_correct(args):
    system, save = load(args)
    body, r0, v0, ut0, who, free_park = origin_state(system, save, args)
    target = system.body(args.target)
    t_end = parse_date(args.arrive) + args.horizon * DAY if args.arrive else ut0 + args.horizon * DAY
    peR = parse_radius(system, target, args.peri or "1.5r")
    watch = [target.name] + list(args.via or [])

    print(f"MIDCOURSE  {who}  ->  {target.name}   (state at {fmt_ut(ut0)})")
    traj = patched.shoot(system, body.name, r0, v0, ut0, t_end, watch=watch)
    rep = patched.arrival_report(system, traj, target.name, t_end)
    print("  --- doing nothing ---")
    print_arrival(system, target.name, rep)

    t_arr = rep.get("soi_ut") or rep.get("ca_ut")
    print(f"\n  --- correcting to periapsis {peR / target.radius:.3f} "
          f"R{target.name[0].lower()} ({(peR - target.radius) / 1e3:,.0f} km altitude) ---")
    best, scan = maneuver.cheapest_correction(system, body.name, r0, v0, ut0, target.name,
                                              t_arr, peR, t_end=t_end,
                                              n_times=args.samples, watch=watch,
                                              verbose=args.verbose)
    if not scan:
        sys.exit("  no correction converged; widen --horizon or check the target")
    print(f"  {'burn date':>22s} {'dV m/s':>10s}  result")
    for o in scan:
        print(f"  {date_of(o['ut']):%Y-%m-%d %H:%M} (T+{(o['ut'] - ut0) / DAY:7.2f} d) "
              f"{o['mag']:10,.1f}  {'hits the aim point' if o['ok'] else 'did not converge'}")
    if best is None:
        sys.exit("  none of the sampled burn times reached the aim point")
    print()
    r, v = astro.propagate(body.mu, r0, v0, best["ut"] - ut0)
    print_node(system, body, r, v, best["dv"], best["ut"], now=(save.ut if save else None),
               label="CORRECTION")
    print_arrival(system, target.name, best["res"]["report"])
    ok_scan = [o for o in scan if o["ok"]]
    if len(ok_scan) > 1:
        first, last = ok_scan[0], ok_scan[-1]
        print(f"    cheapest of {len(scan)} sampled burn times. The cost is not monotonic in "
              f"burn date -- it runs {first['mag']:,.0f} m/s at T+{(first['ut'] - ut0) / DAY:.0f} d, "
              f"{best['mag']:,.0f} m/s at the optimum, {last['mag']:,.0f} m/s at "
              f"T+{(last['ut'] - ut0) / DAY:.0f} d -- so pick the date off the table, "
              f"do not assume sooner is better.")


def cmd_flyby(args):
    system, save = load(args)
    body, r0, v0, ut0, who, free_park = origin_state(system, save, args)
    fly = system.body(args.body_target)
    t_end = ut0 + args.horizon * DAY
    watch = [fly.name] + list(args.via or [])
    print(f"FLYBY  {who}  past  {fly.name}   (state at {fmt_ut(ut0)})")
    traj = patched.shoot(system, body.name, r0, v0, ut0, t_end, watch=watch)
    rep = maneuver.flyby_report(system, traj, fly.name, t_end)
    if rep is None:
        arr = patched.arrival_report(system, traj, fly.name, t_end)
        print("  no encounter on the current trajectory:")
        print_arrival(system, fly.name, arr)
        if args.peri:
            peR = parse_radius(system, fly, args.peri)
            print(f"\n  --- solving for a {peR / fly.radius:.3f} R{fly.name[0].lower()} flyby ---")
            t_arr = arr.get("ca_ut")
            best, scan = maneuver.cheapest_correction(system, body.name, r0, v0, ut0, fly.name,
                                                      t_arr, peR, t_end=t_end,
                                                      n_times=args.samples, watch=watch)
            if scan:
                print(f"  {'burn date':>22s} {'dV m/s':>10s}  result")
                for o in scan:
                    print(f"  {date_of(o['ut']):%Y-%m-%d %H:%M} (T+{(o['ut'] - ut0) / DAY:7.2f} d) "
                          f"{o['mag']:10,.1f}  {'hits the aim point' if o['ok'] else 'did not converge'}")
            if best is None:
                sys.exit(f"  no burn time reached that flyby. The current miss is "
                         f"{arr['ca_dist'] / 1e9:,.1f} Gm against a {fly.soi / 1e9:,.3f} Gm SOI"
                         f"{' -- that is too far to fix with one burn' if arr['ca_dist'] > 50 * fly.soi else ''}"
                         f"; try `depart` for a fresh transfer instead.")
            r, v = astro.propagate(body.mu, r0, v0, best["ut"] - ut0)
            print_node(system, body, r, v, best["dv"], best["ut"],
                       now=(save.ut if save else None), label="AIM BURN")
            traj = best["res"]["traj"]
            rep = maneuver.flyby_report(system, traj, fly.name, t_end)
        else:
            return
    print(f"  enters SOI   {fmt_ut(rep['soi_in'])}")
    print(f"  periapsis    {rep['peR'] / 1e3:,.0f} km = {rep['peR'] / fly.radius:.3f} "
          f"R{fly.name[0].lower()}   (altitude {rep['peAlt'] / 1e3:,.0f} km)"
          + ("   *** IMPACT ***" if rep["impact"] else ""))
    print(f"  v-infinity   {rep['vinf']:,.1f} m/s     e {rep['ecc']:.4f}   "
          f"inclination {rep['inc']:.2f} deg")
    print(f"  deflection   {rep['turn']:.2f} deg      free dV {rep.get('dv_equiv', 0):,.1f} m/s")
    if "soi_out" in rep:
        print(f"  leaves SOI   {fmt_ut(rep['soi_out'])}")
        p = traj.patch_at(rep["soi_out"] + 1)
        el = p.elements()
        print(f"  after:       about {p.body.name}, a {el.sma / 1e9:,.3f} Gm  e {el.ecc:.5f}  "
              f"i {math.degrees(el.inc):.3f} deg  pe {el.peR / 1e9:,.3f} Gm")
    else:
        print("  does not leave the SOI inside the horizon -- it is captured or it impacts.")
    if args.trajectory:
        print("\n  patches:")
        for line in traj.summary().splitlines():
            print("   ", line)


def cmd_verify(args):
    system, save = load(args)
    body, r0, v0, ut0, who, free_park = origin_state(system, save, args)
    t_end = ut0 + args.horizon * DAY
    watch = ([system.body(args.target).name] if args.target else None)
    if watch:
        watch += list(args.via or [])
    v = save.vessel(args.vessel) if args.vessel else None
    nodes = v.nodes() if v else []
    for label, apply_nodes in (("as it flies now", False), ("with the saved node(s)", True)):
        if apply_nodes and not nodes:
            continue
        r, vel, t = r0.copy(), v0.copy(), ut0
        if apply_nodes:
            for n in sorted(nodes, key=lambda n: n["ut"]):
                r, vel = astro.propagate(body.mu, r, vel, n["ut"] - t)
                vel = vel + astro.from_node(r, vel, n["node"])
                t = n["ut"]
        traj = patched.shoot(system, body.name, r, vel, t, t_end, watch=watch)
        print(f"  {label}:")
        for line in traj.summary().splitlines():
            print("     ", line)
        if args.target:
            print_arrival(system, args.target, patched.arrival_report(system, traj, args.target, t_end), indent="      ")
        print()


def cmd_selftest(args):
    import selftest
    sys.exit(0 if selftest.run(System(instance=args.instance), verbose=True) else 1)


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="plan.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", default=r"C:/git/ksp/Instance")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, vessel=True):
        if vessel:
            p.add_argument("--vessel", help="vessel name from the save (substring is enough)")
            p.add_argument("--save", help="save folder or .sfs path; default = most recent")
            p.add_argument("--park", nargs="*", type=float, default=[185.0, 28.5],
                           metavar=("ALT_KM", "INC_DEG"),
                           help="parking orbit when there is no --vessel: ALT INC [RAAN]. Omit RAAN and the coplanar one is solved for.")
            p.add_argument("--body", default="Earth", help="parent body for --park")
            p.add_argument("--at", help="epoch for the starting state (default: the save's UT)")
        p.add_argument("--via", nargs="*", help="extra bodies whose SOI may be entered")
        p.add_argument("--horizon", type=float, default=400.0,
                       help="days past arrival to keep flying (default 400)")
        p.add_argument("--trajectory", action="store_true", help="print every patch")

    p = sub.add_parser("bodies", help="every celestial, as the game loaded it")
    p.set_defaults(func=cmd_bodies)

    p = sub.add_parser("vessels", help="every vessel in the save")
    p.add_argument("--save")
    p.set_defaults(func=cmd_vessels)

    p = sub.add_parser("state", help="orbit and state vector of a vessel or body")
    p.add_argument("what")
    p.add_argument("--save")
    p.add_argument("--at")
    p.set_defaults(func=cmd_state, vessel=None)

    p = sub.add_parser("window", help="scan launch windows between two bodies")
    p.add_argument("dep")
    p.add_argument("arr")
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("--tof", nargs=2, type=float, help="time-of-flight range in days")
    p.add_argument("--step", type=float, default=5.0)
    p.add_argument("--tofstep", type=float, default=5.0)
    p.add_argument("--alt", type=float, default=185.0, help="parking altitude, km")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--sep", type=float, default=150.0, help="days between distinct windows")
    p.add_argument("--include-capture", action="store_true")
    p.add_argument("--max-c3", type=float, default=3.0,
                   help="drop local minima worse than this multiple of the best C3")
    p.set_defaults(func=cmd_window)

    p = sub.add_parser("depart", help="ejection burn onto a transfer")
    common(p)
    p.add_argument("--target", required=True)
    p.add_argument("--depart", help="departure date (default: now)")
    p.add_argument("--arrive", help="fixed arrival date")
    p.add_argument("--tof", nargs=2, type=float, help="time-of-flight range in days to search")
    p.add_argument("--peri", help="target arrival periapsis, e.g. 2.5Rj or 250km")
    p.add_argument("--samples", type=int, default=48,
                   help="phase samples around the parking orbit (direct transfers)")
    p.add_argument("--no-refine", action="store_true")
    p.set_defaults(func=cmd_depart)

    p = sub.add_parser("correct", help="midcourse correction onto a target")
    common(p)
    p.add_argument("--target", required=True)
    p.add_argument("--arrive", help="expected arrival date, to size the horizon")
    p.add_argument("--peri", help="target periapsis, e.g. 2.5Rj or 250km (default 1.5r)")
    p.add_argument("--samples", type=int, default=12, help="burn times to try")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_correct)

    p = sub.add_parser("flyby", help="evaluate or aim a flyby")
    common(p)
    p.add_argument("body_target", metavar="BODY", help="the body to fly past")
    p.add_argument("--peri", help="solve for this flyby periapsis if there is no encounter")
    p.add_argument("--samples", type=int, default=12)
    p.set_defaults(func=cmd_flyby)

    p = sub.add_parser("verify", help="fly the current trajectory and report what happens")
    common(p)
    p.add_argument("--target")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("selftest", help="check the whole chain against known answers")
    p.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
