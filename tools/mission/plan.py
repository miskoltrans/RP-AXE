"""Mission burns for this install, read from the save and checked by flying them.

    python plan.py bodies
    python plan.py vessels
    python plan.py state "Perun 1"
    python plan.py window Earth Jupiter 1964-01-01 1968-01-01 --site cape
    python plan.py launch  --target Jupiter --depart 1966-09-26 --site cape --alarm
    python plan.py depart --vessel "Perun 2" --target Jupiter --arrive 1970-05-01
    python plan.py depart --park 185 28.5 --body Earth --target Moon
    python plan.py correct --vessel "Perun 1" --target Jupiter --peri 2.5Rj --push
    python plan.py flyby   --vessel "Perun 1" Jupiter
    python plan.py verify  --vessel "Perun 1" --target Jupiter
    python plan.py selftest

Every burn is printed in the form KSP wants it: a UT and the three ManeuverNode
components. Every answer is followed by what happens when the result is actually
flown, because the two have disagreed before.

--push places the burn in the running game as a maneuver node instead of making you
retype it, and prints KSP's own flight plan for what it just placed. --alarm sets a
KAC alarm for it. Both need the bridge on (-axe-bridge).
"""
import argparse
import json
import math
import sys

import numpy as np

import astro
import bridge as bridge_mod
import ksptot as ksptot_mod
import launch as launch_mod
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
    """Where the burn starts: the running game, the save, or a synthetic parking orbit."""
    if getattr(args, "live", False):
        # KSPTOT Connect first -- it is already installed and already serves this. But it is
        # [KSPAddon(Flight)] and a separate process, so it can be absent while the AXE bridge
        # is perfectly happy. Falling back rather than failing makes --live mean --live.
        ut = parse_date(args.at) if args.at else None
        try:
            kt = ksptot_mod.KspTot(port=args.ksptot_port)
            body, r, vel, ut = kt.state(system, name=args.vessel, ut=ut)
            label = (args.vessel or kt.vessel_name(kt.vessel_ids()[0])) + " [live]"
        except ksptot_mod.KspTotError as exc:
            try:
                br = bridge_mod.Bridge(port=args.port)
                body, r, vel, ut = br.state(system, name=args.vessel, ut=ut)
                label = (args.vessel or "active vessel") + " [live, AXE bridge]"
            except bridge_mod.BridgeError as exc2:
                print("no live state available.")
                print(f"  KSPTOT Connect: {exc}")
                print(f"  AXE bridge:     {exc2}")
                sys.exit(1)
        return body, np.asarray(r), np.asarray(vel), ut, label, None
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


def push_burns(args, burns, what="burn"):
    """Place computed burns in the running game, and/or set an alarm for the first one.

    `burns` is [(ut, (radial, normal, prograde)), ...] -- exactly what print_node prints.

    The response carries KSP's OWN flight plan for what was just placed, and it is
    printed rather than discarded. That is the entire reason to write through the bridge
    instead of typing six numbers into a gizmo: a sign error shows up here, one line
    later, instead of three hours into a time warp.
    """
    if not getattr(args, "push", False) and getattr(args, "alarm", None) is None:
        return
    if not burns:
        print("\n  (nothing to push -- no burn was solved)")
        return
    br = bridge_mod.Bridge(port=args.port)
    vessel = getattr(args, "push_vessel", None) or getattr(args, "vessel", None)

    if getattr(args, "push", False):
        if not vessel:
            sys.exit("--push needs a vessel: pass --vessel NAME (a --park orbit is "
                     "hypothetical, so there is nothing in the game to place a node on)")
        try:
            res = br.place_nodes([(ut, n[0], n[1], n[2]) for ut, n in burns],
                                 name=vessel, replace=not args.push_add)
        except bridge_mod.BridgeError as exc:
            sys.exit(f"  push failed: {exc}")
        print(f"\n  PUSHED to {res['vessel']}: placed {res['placed']} node(s)"
              + (f", removed {res['removed']}" if res.get("removed") else ""))
        for n in res.get("nodes", []):
            print(f"    node {fmt_ut(n['ut'])}   prograde {n['prograde']:+11,.2f}  "
                  f"normal {n['normal']:+11,.2f}  radial {n['radial']:+11,.2f}  "
                  f"total {n['magnitude']:,.2f} m/s")
        plan = res.get("flight_plan") or []
        if plan:
            print("    KSP's own flight plan for what was just placed:")
            for i, pt in enumerate(plan):
                pe = pt.get("peR")
                print(f"      {i}: {pt.get('body'):10s} {fmt_ut(pt.get('start_ut'))}"
                      f" -> {pt.get('transition')}"
                      + (f"   pe {pe / 1e3:,.0f} km" if pe else ""))
        else:
            # An empty flight plan after a successful place is not "fine": it means KSP
            # solved the burn into nothing. Say so rather than letting the ok stand alone.
            print("    KSP returned an EMPTY flight plan for these nodes -- check the burn.")

    if getattr(args, "alarm", None) is not None:
        ut0 = burns[0][0]
        name = args.alarm or f"AXE {what}"
        notes = (f"{what} placed by plan.py: "
                 + ", ".join(f"{fmt_ut(ut)} dV {math.sqrt(sum(x * x for x in n)):,.1f} m/s"
                             for ut, n in burns))
        try:
            res = br.alarm(ut0, name=name, notes=notes, margin=args.alarm_margin,
                           vessel=vessel, type=args.alarm_type)
        except bridge_mod.BridgeError as exc:
            sys.exit(f"  alarm failed: {exc}")
        print(f"  ALARM  \"{name}\" ({res['backend']}) at {fmt_ut(ut0)}"
              + (f", firing {args.alarm_margin:,.0f} s early" if args.alarm_margin else "")
              + f"   [id {res['id']}]")


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
            # Body-centre v-infinity, deliberately: this is a SCAN over ~90,000
            # Lambert arcs and the SOI-crossing refinement costs a propagation each.
            # It ranks windows correctly because the error is smooth across them, but
            # the absolute C3 and dV are optimistic and MUST NOT be flown -- see the
            # footnote below and `depart`, which re-solves with the correction.
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
    # The parking plane. A departure dV is meaningless without one -- from an arbitrary
    # node an Earth->Moon injection costs 3,426 m/s with 1,100 m/s of plane change in it,
    # and 3,143 m/s essentially pure prograde from the coplanar node. So solve the RAAN
    # that makes each window coplanar and print it, rather than quoting an inflated number
    # and leaving the reader to discover why.
    site = None
    inc = args.inc
    if args.site:
        site = launch_mod.site(args.site, instance=args.instance, body=dep.name)
        if inc is None:
            inc = site.min_inclination()
    if inc is None:
        inc = 28.5

    print(f"{dep.name} -> {arr.name}  from a {args.alt:.0f} km x {inc:.2f} deg parking orbit "
          f"around {dep.name}   ({len(deps)} departures x {len(tofs)} TOFs)")
    if site:
        print(f"  launch times are for {site.display} ({site.lat:+.3f}, {site.lon:+.3f}); "
              f"it cannot reach below i {site.min_inclination():.2f} deg")
    head = (f"{'departure':>12s} {'TOF d':>7s} {'arrival':>12s} {'C3':>8s} {'dv dep':>8s} "
            f"{'vinf arr':>9s} {'DLA':>7s} {'RAAN':>7s}")
    if site:
        head += f" {'launch (UTC)':>17s} {'az':>7s}"
    print(head)
    for i in sorted(picked):
        td, tf, c3, dv, vinf_a, dla = rows[i]
        r1, v1b = system.state(dep.name, td, centre)
        r2, v2b = system.state(arr.name, td + tf, centre)
        raan = None
        try:
            vt1, _ = lambert(mu, np.array(r1), np.array(r2), tf)
            cands = align_raan(inc, np.asarray(vt1) - np.asarray(v1b))
            raan = cands[0] if cands else None
        except Exception:                                           # noqa: BLE001
            raan = None
        line = (f"{date_of(td):%Y-%m-%d}   {tf / DAY:7.0f} {date_of(td + tf):%Y-%m-%d}   "
                f"{c3:8.2f} {dv:8,.0f} {vinf_a:9,.0f} {dla:7.2f} "
                + (f"{raan:7.2f}" if raan is not None else f"{'--':>7s}"))
        if site:
            when = az = None
            if raan is not None:
                try:
                    # The pad crossing nearest the departure instant, not merely the next
                    # one after it: a window quoted at midnight would otherwise report a
                    # launch most of a day late for no reason.
                    ps = launch_mod.plane_passes(site, system, inc, raan, td - DAY, count=4)
                    if ps:
                        best_p = min(ps, key=lambda q: abs(q["ut"] - td))
                        when, az = best_p["ut"], best_p["azimuth_inertial"]
                except ValueError:
                    when = az = None
            line += (f" {date_of(when):%m-%d %H:%M}     {az:7.2f}" if when is not None
                     else f" {'unreachable':>17s} {'--':>7s}")
        print(line)
    if dropped:
        print(f"  ({dropped} further local minima were above {args.max_c3:.0f}x the best C3 of "
              f"{best_c3:.1f} and are not launch windows; raise --max-c3 to see them)")
    print("  RAAN is the parking-orbit ascending node that makes the departure coplanar; "
          "`depart` re-solves it exactly.")
    print("  C3 and dv here are BODY-CENTRE Lambert values -- v_transfer - v_planet taken at "
          "the planet's centre. The burn happens a few thousand km out and the vehicle "
          f"crosses {dep.name}'s {dep.soi / 1e3:,.0f} km SOI days later, so flying these "
          "numbers misses by millions of km. Use them to PICK a window; run `depart` for a "
          "burn, which re-reads the relative velocity at the SOI crossing.")
    if not site:
        print("  Pass --site NAME (e.g. --site cape) to get the launch time of day as well.")
    else:
        unreachable = [i for i in picked if rows[i][5] > inc or rows[i][5] < -inc]
        if unreachable:
            print(f"  \"unreachable\" means the departure asymptote leaves at a declination "
                  f"steeper than i {inc:.2f} deg, so no parking orbit from this pad contains "
                  f"it: that window costs a plane change or a dogleg on top of the dV above.")
        _warn_uncalibrated(site)


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
        node, _ = print_node(system, body, rn, vn, dv, ut_node, now=(save.ut if save else None))
        args._burn = (ut_node, node)
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
        node, _ = print_node(system, body, rn, vn, dv, ut_node, now=(save.ut if save else None))
        args._burn = (ut_node, node)
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
        node, _ = print_node(system, body, rn, vn, dv + res["dv"], ut_node,
                             now=(save.ut if save else None), label="BURN")
        args._burn = (ut_node, node)      # the refined burn supersedes the raw one
        print(f"    (that is {np.linalg.norm(res['dv']):,.2f} m/s different from the "
              f"uncorrected burn, found in {res['nfev']} shots)")
        print_arrival(system, target.name, res["report"])
        traj = res["traj"]
    if args.trajectory:
        print("\n  patches:")
        for line in traj.summary().splitlines():
            print("   ", line)
    burn = getattr(args, "_burn", None)
    push_burns(args, [burn] if burn else [], what="ejection")


def print_assists(rows, indent="    "):
    """What actually happened at each assist. Never inferred -- read off the flown patches."""
    for a in rows:
        if not a.get("entered"):
            print(f"{indent}{a['body']}: NOT ENTERED -- there is no assist on this trajectory")
            continue
        line = (f"{indent}{a['body']}: periapsis {a['peAlt'] / 1e3:,.0f} km altitude"
                f"   v-inf {a['vinf']:,.0f} m/s")
        if a.get("turn"):
            line += f"   turn {a['turn']:.2f} deg   free dV {a.get('dv_equiv', 0):,.0f} m/s"
        print(line)
        if a.get("impact"):
            print(f"{indent}       *** that periapsis is INSIDE {a['body']} ***")
        elif not a.get("exits"):
            print(f"{indent}       does not leave {a['body']}'s SOI inside the horizon")


def cmd_correct_through(args, system, save, body, r0, v0, ut0, who):
    """Correct through one or more gravity assists onto a final target.

    `correct` proper aims a B-plane at ONE body. Through a flyby that residual does not
    exist until the trajectory is already nearly right, so least squares has nothing to
    descend and the scan rejects every burn date it tries. This aims at a POSITION at the
    destination instead, with the assists flown by the shooter rather than approximated.
    """
    target = system.body(args.target)
    via = [system.body(v).name for v in args.through]
    t_end = parse_date(args.arrive) + args.horizon * DAY if args.arrive \
        else ut0 + args.horizon * DAY

    print(f"CORRECT  {who}  ->  {' -> '.join(via)}  ->  {target.name}   "
          f"(state at {fmt_ut(ut0)})")

    if args.arrive:
        arrivals = [parse_date(args.arrive)]
        nat_ut = nat_d = None
    else:
        arrivals, nat_ut, nat_d = maneuver.default_arrivals(
            system, body.name, r0, v0, ut0, target.name, via=via, t_end=t_end,
            span_days=args.span, n=args.samples)
        if not arrivals:
            sys.exit(f"  the trajectory never comes near {target.name} inside the horizon; "
                     f"raise --horizon or give --arrive DATE")
        print(f"  uncorrected, it passes {target.name} on {fmt_ut(nat_ut)} at "
              f"{nat_d / 1e9:,.2f} Gm. Scanning {len(arrivals)} arrival epochs around that "
              f"-- the epoch cannot be guessed, and aiming at one the trajectory has no "
              f"business being near reports a failure that is really just the target being "
              f"elsewhere in its orbit.")

    best, rows = maneuver.scan_arrivals(
        system, body.name, r0, v0, ut0, target.name, arrivals, via=via, t_end=t_end,
        max_dv=args.max_dv, diff_step=args.diff_step, max_nfev=args.max_nfev,
        verbose=args.verbose)

    fatal = [r for r in rows if r.get("fatal")]
    if fatal:
        sys.exit(f"  {fatal[0]['why']}")

    print(f"\n  {'arrival':>22s} {'dV m/s':>10s} {'miss':>14s}  assist")
    for r in rows:
        if "traj" not in r:
            print(f"  {date_of(r['t_arr']):%Y-%m-%d %H:%M} {'--':>10s} {'--':>14s}  "
                  f"{r.get('why', 'did not converge')}")
            continue
        a = r["assists"][0] if r["assists"] else {}
        note = ("no encounter" if not a.get("entered")
                else f"{a['body']} pe {a['peAlt'] / 1e3:,.0f} km"
                     + ("  IMPACT" if a.get("impact") else ""))
        miss = r["miss"]
        ms = f"{miss / 1e3:,.0f} km" if miss < 1e9 else f"{miss / 1e9:,.1f} Gm"
        print(f"  {date_of(r['t_arr']):%Y-%m-%d %H:%M} "
              f"{float(np.linalg.norm(r['correction'])):10,.2f} {ms:>14s}  {note}"
              + ("  HIT" if r.get("ok") else ""))

    if best is None:
        sys.exit(f"\n  no arrival epoch closed. The best miss was "
                 f"{min((r['miss'] for r in rows if 'miss' in r), default=float('nan')) / 1e9:,.2f} Gm "
                 f"against a {target.soi / 1e9:,.4f} Gm SOI. If the misses all sit at the "
                 f"ASSIST's SOI radius the flyby was lost and could not be re-acquired -- "
                 f"aim at the assist first with `flyby {via[0]} --peri`, then correct again.")

    print()
    node, _ = print_node(system, body, r0, v0, best["correction"], ut0,
                         now=(save.ut if save else None), label="CORRECTION")
    print(f"    arrives {fmt_ut(best['t_arr'])}, {best['miss'] / 1e3:,.0f} km from "
          f"{target.name}'s centre ({best['miss'] / target.soi:.3f} of its SOI), "
          f"found in {best['nfev']} shots")
    print_assists(best["assists"])
    print("\n  --- as flown ---")
    for line in best["traj"].summary().splitlines():
        print("   ", line)
    rep = patched.arrival_report(system, best["traj"], target.name, t_end)
    print_arrival(system, target.name, rep)

    if args.peri:
        # Shape the arrival now that we are actually there. The B-plane refine could not
        # converge from 36 Gm away; from inside the SOI it is the right tool.
        peR = parse_radius(system, target, args.peri)
        print(f"\n  --- shaping the arrival to periapsis {peR / target.radius:.3f} "
              f"R{target.name[0].lower()} ---")
        try:
            res = maneuver.refine(system, body.name, r0, v0, ut0, target.name, t_end,
                                  peR_want=peR, watch=via + [target.name],
                                  max_nfev=args.max_nfev)
        except Exception as exc:                                    # noqa: BLE001
            print(f"    could not shape it: {type(exc).__name__}: {exc}")
        else:
            node, _ = print_node(system, body, r0, v0, res["dv"], ut0,
                                 now=(save.ut if save else None), label="CORRECTION")
            print_assists(maneuver.assist_passes(system, res["traj"], via))
            print_arrival(system, target.name, res["report"])
            best = {"correction": res["dv"], "t_arr": best["t_arr"]}

    push_burns(args, [(ut0, node)], what="assist correction")


def cmd_correct(args):
    system, save = load(args)
    body, r0, v0, ut0, who, free_park = origin_state(system, save, args)
    if getattr(args, "through", None):
        return cmd_correct_through(args, system, save, body, r0, v0, ut0, who)
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
                                              verbose=args.verbose,
                                              max_dv=args.max_dv, diff_step=args.diff_step)
    if not scan:
        sys.exit("  no correction converged; widen --horizon or check the target")
    print(f"  {'burn date':>22s} {'dV m/s':>10s}  result")
    for o in scan:
        print(f"  {date_of(o['ut']):%Y-%m-%d %H:%M} (T+{(o['ut'] - ut0) / DAY:7.2f} d) "
              f"{o['mag']:10,.1f}  {'hits the aim point' if o['ok'] else 'did not converge'}")
    ok_n = sum(1 for o in scan if o["ok"])
    if ok_n == 1:
        # Convergence tracks the size of the STARTING miss, not the physics. One lone
        # success across a smooth sweep of burn dates is not a narrow launch window --
        # neighbouring dates differ by hours of coast, not by feasibility. It means the
        # other seeds started too far out for least squares to climb back.
        print("  NOTE: exactly one burn date converged. Convergence tracks the size of the "
              "starting miss, so a lone success across a smooth sweep points at SEEDING, "
              "not at the geometry. Re-run with more --samples, or seed from a date nearer "
              "the encounter with --at.")
    if best is None:
        sys.exit("  none of the sampled burn times reached the aim point. Convergence "
                 "tracks the starting miss: if every date failed by a similar amount the "
                 "seed is the problem, and if they failed by wildly different amounts the "
                 "geometry is.")
    print()
    r, v = astro.propagate(body.mu, r0, v0, best["ut"] - ut0)
    node, _ = print_node(system, body, r, v, best["dv"], best["ut"],
                         now=(save.ut if save else None), label="CORRECTION")
    print_arrival(system, target.name, best["res"]["report"])
    push_burns(args, [(best["ut"], node)], what="correction")
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
                                                      n_times=args.samples, watch=watch,
                                                      max_dv=args.max_dv)
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
            node, _ = print_node(system, body, r, v, best["dv"], best["ut"],
                                 now=(save.ut if save else None), label="AIM BURN")
            args._burn = (best["ut"], node)
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
    burn = getattr(args, "_burn", None)
    push_burns(args, [burn] if burn else [], what="flyby aim burn")


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


def _warn_uncalibrated(site, calibrated=False):
    """Say plainly when a launch TIME is only right up to an unknown constant.

    The pad's inertial longitude needs a zero point that is not written down anywhere,
    so launch.py measures it from the running game and falls back to a module constant.
    An uncalibrated answer has the right SHAPE -- right spacing, right azimuth, right
    inclination limits -- and a possibly wrong absolute time, which is exactly the kind
    of wrongness that gets trusted. So it is stated every time rather than buried.
    """
    if calibrated or site.calibrated:
        return
    print(f"  NOTE: the launch TIME is uncalibrated (offset {site.offset:+.3f} deg assumed). "
          f"Spacing, azimuth and the plane are right regardless; the absolute time of day "
          f"is only right if that offset is. Run with --live, or check it with "
          f"`plan.py crosscheck --sites`.")


def _calibrate_site(site, system, args):
    """Pin the site's zero point from the running game. Returns True if it worked."""
    try:
        br = bridge_mod.Bridge(port=args.port)
        data = br.sites()
    except bridge_mod.BridgeError as exc:
        print(f"  (not calibrated against the game: {exc})")
        return False
    ut = data.get("ut")
    for entry in data.get("sites", []):
        for sp in entry.get("spawn_points", []):
            r = sp.get("r_zup")
            if not r or not sp.get("resolved", True):
                continue
            # KSCSwitcher relocates the single KSC, so the game reports ONE pad wherever
            # the save put it. Match on position, not on name: the game's site is called
            # "KSC" no matter which historical pad it currently sits on.
            if abs(sp.get("latitude", 999) - site.lat) > 0.05:
                continue
            if abs(((sp.get("longitude", 999) - site.lon + 180) % 360) - 180) > 0.05:
                continue
            off = site.calibrate(system, ut, r)
            if off is not None:
                print(f"  calibrated against the running game at {fmt_ut(ut)}: "
                      f"offset {off:+.4f} deg")
                return True
    print(f"  (the game is not currently at {site.display}; its live pad is somewhere else, "
          f"so the zero point could not be measured -- switch KSC or drop --live)")
    return False


def cmd_launch(args):
    """When to launch, from where, on what heading, to reach a given orbit plane."""
    system, save = load(args)
    body = system.body(args.body)
    if args.site:
        site = launch_mod.site(args.site, instance=args.instance, body=body.name)
    else:
        site = launch_mod.active_site(save, instance=args.instance, body=body.name)
        if site is None:
            sys.exit("no launch sites found; pass --site NAME")
    inc = args.inc if args.inc is not None else max(args.park_inc, site.min_inclination())

    print(f"LAUNCH  {site.display}  ({site.lat:+.4f}, {site.lon:+.4f}) on {body.name}")
    print(f"  reachable inclinations {site.min_inclination():.3f} to "
          f"{180 - site.min_inclination():.3f} deg without a plane change")
    print(f"  the pad is already moving east at {site.rotation_speed(system):,.1f} m/s")

    calibrated = _calibrate_site(site, system, args) if args.live else False

    # --- what plane? -----------------------------------------------------
    raan = args.raan
    if raan is None:
        if not args.target:
            sys.exit("say which plane: --raan DEG, or --target BODY (with --depart DATE) "
                     "to solve for the one that makes the departure coplanar")
        target = system.body(args.target)
        t_dep = parse_date(args.depart) if args.depart else (save.ut if save else 0.0)
        direct = (target.parent == body.name)
        if direct:
            hoh = _hohmann_days(system, body, target, r_from=body.radius + args.alt * 1e3)
            u, _ = system.rel(target.name, t_dep + hoh * DAY)
        else:
            hoh = _hohmann_days(system, body, target)
            u, _, _ = maneuver.vinf_for_transfer(system, body.name, target.name,
                                                 t_dep, t_dep + hoh * DAY)
        cands = align_raan(inc, np.asarray(u))
        if not cands:
            sys.exit(f"inclination {inc:.2f} deg cannot contain the departure direction to "
                     f"{target.name}; it needs at least {math.degrees(math.asin(min(1.0, abs(np.asarray(u)[2] / np.linalg.norm(u))))):.2f} deg")
        raan = cands[0]
        print(f"  departing to {target.name} on {fmt_ut(t_dep)}: the coplanar parking RAAN is "
              f"{cands[0]:.2f} deg (the other node is {cands[1]:.2f} deg)")
    after = parse_date(args.after) if args.after else (save.ut if save else 0.0)

    print(f"  target plane: i {inc:.3f} deg, RAAN {raan:.3f} deg\n")
    try:
        passes = launch_mod.plane_passes(site, system, inc, raan, after,
                                         count=args.count, v_orbit=args.v_orbit)
    except ValueError as exc:
        sys.exit(f"  {exc}")
    if not passes:
        sys.exit("  no crossing found -- that should not happen; report it")

    print(f"  {'launch (UTC)':>22s} {'from now':>12s} {'az inertial':>12s} "
          f"{'az flown':>10s} {'node':>11s}")
    for q in passes:
        dt = q["ut"] - after
        print(f"  {date_of(q['ut']):%Y-%m-%d %H:%M:%S} {dt / 3600:10,.2f} h "
              f"{q['azimuth_inertial']:12.2f} {q.get('azimuth_flown', float('nan')):10.2f} "
              f"{'ascending' if q['ascending'] else 'descending':>11s}")
    print(f"\n  az flown is the heading to actually fly: the pad already supplies "
          f"{site.rotation_speed(system):,.0f} m/s of eastward velocity, so the vehicle "
          f"provides only the difference.")
    _warn_uncalibrated(site, calibrated)

    if args.alarm is not None:
        pick = passes[args.pick]
        name = args.alarm or f"AXE launch {site.name}"
        notes = (f"launch {site.display} into i {inc:.2f} RAAN {raan:.2f}, "
                 f"azimuth {pick.get('azimuth_flown', pick['azimuth_inertial']):.2f} deg"
                 + ("" if calibrated else "  [UNCALIBRATED time of day]"))
        try:
            br = bridge_mod.Bridge(port=args.port)
            res = br.alarm(pick["ut"], name=name, notes=notes, margin=args.alarm_margin,
                           type=args.alarm_type)
        except bridge_mod.BridgeError as exc:
            sys.exit(f"  alarm failed: {exc}")
        print(f"\n  ALARM  \"{name}\" ({res['backend']}) at {fmt_ut(pick['ut'])}"
              + (f", firing {args.alarm_margin:,.0f} s early" if args.alarm_margin else "")
              + f"   [id {res['id']}]")


def cmd_alarms(args):
    """List the alarms the game is holding, or delete one."""
    br = bridge_mod.Bridge(port=args.port)
    if args.delete:
        try:
            br.delete_alarm(args.delete)
        except bridge_mod.BridgeError as exc:
            sys.exit(str(exc))
        print(f"deleted alarm {args.delete}")
        return
    try:
        data = br.alarms()
    except bridge_mod.BridgeError as exc:
        sys.exit(str(exc))
    print(f"alarms via {data['backend']}   (UT {fmt_ut(data['ut'])})")
    if data.get("kac"):
        print(f"  {data['kac']}")
    rows = sorted(data.get("alarms", []), key=lambda a: a.get("ut", 0.0))
    if not rows:
        print("  (none)")
    for a in rows:
        print(f"  {fmt_ut(a['ut'])}  {a.get('remaining', 0) / 3600:9,.2f} h  "
              f"{(a.get('type') or '?'):16s} {(a.get('name') or ''):32.32s} [{a.get('id')}]")
        if a.get("notes"):
            print(f"      {a['notes'][:110]}")
    if data.get("alarm_types"):
        print("\n  types KAC accepts:  " + ", ".join(data["alarm_types"]))
        print("  actions:            " + ", ".join(data.get("alarm_actions", [])))


def cmd_bridge(args):
    """Ping the running game, and optionally list what it is holding."""
    system, _ = load(args)
    br = bridge_mod.Bridge(port=args.port)
    try:
        info = br.ping()
    except bridge_mod.BridgeError as exc:
        sys.exit(str(exc))
    print(f"AXE bridge {info.get('bridge')} on port {args.port}")
    print(f"  scene    {info.get('scene')}")
    print(f"  game     {info.get('game')}")
    ut = info.get("ut")
    print(f"  UT       {fmt_ut(ut) if ut == ut else 'no game loaded'}")
    print(f"  bodies   {info.get('bodies')}    vessels {info.get('vessels')}"
          f"    active {info.get('active')}")
    if not args.vessels:
        return
    print()
    kt = ksptot_mod.KspTot(port=args.ksptot_port)
    try:
        rows = kt.vessels()
    except ksptot_mod.KspTotError as exc:
        print(f"  live vessels unavailable: {exc}")
        return
    print(f"  vessels, from KSPTOT Connect on {args.ksptot_port} "
          f"(commandable craft only -- debris is not in its list)")
    print(f"  {'vessel':32s} {'body':10s} {'pe km':>12s} {'ap km':>13s} {'inc':>7s}")
    for v in rows:
        if "ref_index" not in v or not math.isfinite(v.get("sma_km", float("nan"))):
            print(f"  {v['name'][:32]:32s} (no orbit)")
            continue
        b = system.by_index[int(round(v["ref_index"]))]
        ap = "escape" if v["ecc"] >= 1 else f"{v['ap_alt_km']:,.0f}"
        print(f"  {v['name'][:32]:32s} {b.name:10s} {v['pe_alt_km']:12,.0f} {ap:>13s} "
              f"{v['inc_deg']:7.2f}")


def cmd_crosscheck(args):
    """Diff this toolchain against the running game: ephemeris, state, and the shooter.

    Every historical bug in these tools was a state-interpretation error that stayed
    perfectly self-consistent, so nothing internal could catch it. This is the command
    that cannot be fooled by that, because the other side of the comparison is KSP.
    """
    system, _ = load(args)
    br = bridge_mod.Bridge(port=args.port)
    fails = []

    print("=== 1. ephemeris: every body position, at the game's own UT ===")
    try:
        ut, rows = bridge_mod.check_bodies(system, br)
    except bridge_mod.BridgeError as exc:
        # "KSP is not running" is a normal thing to discover, not a crash.
        sys.exit(str(exc))
    print(f"  UT {fmt_ut(ut)}")
    try:
        info = br.ping()
        ver, ira = info.get("bridge"), info.get("inverse_rot_angle")
        if ira is not None and ira == ira:
            print(f"  bridge {ver}, Planetarium.InverseRotAngle = {ira:.4f} deg")
        if ver in (None, "1.0"):
            # Say it BEFORE the table, because the table is what looks alarming.
            print("  WARNING: bridge 1.0 emits state vectors rotated by -InverseRotAngle "
                  "relative to its own elements. Any position disagreement below is that "
                  "rotation, NOT an epoch error. Rebuild AXE.dll and restart KSP.")
    except bridge_mod.BridgeError:
        pass
    rows.sort(key=lambda r: -r["rel"])
    print(f"  {'body':10s} {'|dr| m':>14s} {'relative':>10s} {'d(mu)':>10s} {'d(SOI) m':>12s}  index")
    for r in rows[:args.top]:
        dmu = abs(r["mu_game"] - r["mu_mine"]) / r["mu_game"] if r["mu_game"] else 0.0
        dsoi = abs(r["soi_game"] - r["soi_mine"])
        same = "ok" if r["index_game"] == r["index_mine"] else f"MISMATCH {r['index_game']}/{r['index_mine']}"
        print(f"  {r['body']:10s} {r['err_m']:14,.3f} {r['rel']:10.2e} {dmu:10.2e} {dsoi:12,.1f}  {same}")
    worst = max((r["rel"] for r in rows), default=0.0)
    idx_bad = [r["body"] for r in rows if r["index_game"] != r["index_mine"]]
    soi_bad = [r["body"] for r in rows if abs(r["soi_game"] - r["soi_mine"]) > 1.0]
    print(f"  worst relative position error {worst:.2e} over {len(rows)} bodies")
    rot_rows = [r for r in rows if "rot_err_deg" in r]
    if rot_rows:
        worst_rot = max(rot_rows, key=lambda r: abs(r["rot_err_deg"]))
        print(f"  rotation phase: worst disagreement {worst_rot['rot_err_deg']:+.6f} deg "
              f"on {worst_rot['body']}, over {len(rot_rows)} rotating bodies")
        if abs(worst_rot["rot_err_deg"]) > 1e-3:
            fails.append(f"rotation angle on {worst_rot['body']} is "
                         f"{worst_rot['rot_err_deg']:+.4f} deg out -- every launch TIME on it "
                         f"is wrong by {abs(worst_rot['rot_err_deg']) / 360 * (system.body(worst_rot['body']).rot or 0) / 60:,.1f} min")
    if worst > 1e-6:
        fails.append(f"ephemeris disagrees with the game by {worst:.2e} relative "
                     f"-- suspect the epoch or the element parse")
    if idx_bad:
        fails.append("body index mismatch: " + ", ".join(idx_bad))
    if soi_bad:
        fails.append("SOI mismatch: " + ", ".join(soi_bad))

    if args.sites:
        print("\n=== launch sites: the pad position, game vs the config ===")
        try:
            data = br.sites()
        except bridge_mod.BridgeError as exc:
            print(f"  unavailable: {exc}")
            data = None
        if data:
            table = launch_mod.sites(instance=args.instance)
            live_ut = data["ut"]
            inv = data.get("inverse_rot_angle")
            print(f"  the game is holding {len(data['sites'])} site(s) at UT {fmt_ut(live_ut)}"
                  + (f";  Planetarium.InverseRotAngle = {inv:.4f} deg" if inv is not None else ""))
            for entry in data["sites"]:
                for sp in entry.get("spawn_points", []):
                    if not sp.get("resolved", True) or sp.get("r_zup") is None:
                        continue
                    lat, lon = sp["latitude"], sp["longitude"]
                    match = None
                    for cand in table.values():
                        if (abs(cand.lat - lat) < 0.05
                                and abs(((cand.lon - lon + 180) % 360) - 180) < 0.05):
                            match = cand
                            break
                    label = f"{entry.get('name')}/{sp.get('name')}"
                    print(f"  {label:28.28s} {lat:+9.4f} {lon:+10.4f}  "
                          f"config match: {match.name if match else 'NONE'}")
                    if match is None:
                        # Not a failure. KSCSwitcher relocates the pad, and a save sitting on
                        # a site that is not in the shipped list is a legitimate state.
                        continue
                    off = match.calibrate(system, live_ut, sp["r_zup"])
                    if off is None:
                        continue
                    drift = ((off - launch_mod.OFFSET_DEG + 180) % 360) - 180
                    print(f"  {'':28s} measured zero point {off:+.4f} deg; "
                          f"launch.OFFSET_DEG is {launch_mod.OFFSET_DEG:+.4f} "
                          f"({drift:+.4f} deg out"
                          + (f" = {abs(drift) / 360 * (system.body(match.body).rot or 0) / 60:,.1f} min "
                             f"of launch time)" if drift else ")"))
                    # The other frame convention, reported by the bridge alongside. If the
                    # conversion direction were backwards the offset would be off by exactly
                    # -2 * InverseRotAngle -- so showing both turns "which way round is
                    # CelestialFrame?" from an argument into a measurement.
                    if sp.get("r_zup_wrong") is not None and inv is not None:
                        probe = launch_mod.Site(match.name, match.display, match.body,
                                                match.lat, match.lon)
                        other = probe.calibrate(system, live_ut, sp["r_zup_wrong"])
                        if other is not None:
                            predicted = ((-2.0 * inv + 180) % 360) - 180
                            print(f"  {'':28s} the other convention gives {other:+.4f} deg; "
                                  f"-2*InverseRotAngle is {predicted:+.4f} "
                                  f"({'as predicted' if abs(((other - predicted + 180) % 360) - 180) < 0.01 else 'NOT as predicted'})")
                    # A wrong constant here shifts every OFFLINE launch time by the same
                    # amount and stays perfectly self-consistent, so this is the only place
                    # it can be caught.
                    if abs(drift) > 0.01:
                        fails.append(f"launch.OFFSET_DEG is {drift:+.4f} deg out against the "
                                     f"game (measured {off:+.4f}); every offline launch time "
                                     f"is shifted by "
                                     f"{abs(drift) / 360 * (system.body(match.body).rot or 0) / 60:,.1f} min")

    if not args.vessel:
        print("\n  (pass --vessel NAME to also check a vessel state and the shooter)")
    else:
        print(f"\n=== 2. vessel state: {args.vessel} (KSPTOT Connect vs the save) ===")
        kt = ksptot_mod.KspTot(port=args.ksptot_port)
        try:
            body, gr, gv, live_ut = kt.state(system, name=args.vessel)
        except ksptot_mod.KspTotError as exc:
            sys.exit(f"  {exc}")
        try:
            save = Save(find_save(args.save, args.instance), system)
            sv = save.vessel(args.vessel)
            mr, mv = sv.state(live_ut)
            dr = float(np.linalg.norm(np.asarray(mr) - gr))
            print(f"  live UT {fmt_ut(live_ut)};  save UT {fmt_ut(save.ut)}")
            print(f"  body: live {body.name}, save {sv.body.name}")
            print(f"  save-derived vs live: |dr| = {dr:,.6f} m   "
                  f"|dv| = {np.linalg.norm(np.asarray(mv) - gv):,.9f} m/s")
            if body.name != sv.body.name:
                fails.append(f"reference body differs: live {body.name}, save {sv.body.name}")
            if dr > 1.0:
                fails.append("the save-derived vessel state disagrees with the live one by "
                             f"{dr:,.1f} m -- if the UTs differ the save is simply older, "
                             "which is exactly why --live exists")
        except Exception as exc:                                    # noqa: BLE001
            print(f"  (no save comparison: {exc})")
        d = {"ut": live_ut}

        print("\n=== 3. the shooter vs KSP's own patched-conic solver ===")
        dv = [float(x) for x in args.dv.split(",")] if args.dv else [0.0, 0.0, 0.0]
        ut_node = parse_date(args.at) if args.at else d["ut"]
        game = br.predict(name=args.vessel, ut=ut_node, dv=dv,
                          horizon=args.horizon, maxpatches=args.maxpatches)
        r, v = gr, gv
        if ut_node != d["ut"]:
            r, v = astro.propagate(body.mu, gr, gv, ut_node - d["ut"])
        burn = astro.from_node(r, v, dv)
        names = {p["body"] for p in game["patches"] if p.get("body")}
        watch = sorted(names - {body.name}) or None
        traj = patched.shoot(system, body.name, r, v + burn, ut_node,
                             ut_node + args.horizon * DAY, watch=watch)
        print(f"  burn (radial, normal, prograde) = {dv}   |dV| {np.linalg.norm(burn):,.3f} m/s")
        print(f"  watching {watch or 'the defaults'}")
        print(f"  {'#':>2s} {'game body':12s} {'shooter':12s} {'d(start) s':>12s} "
              f"{'game peR km':>15s} {'shooter peR km':>15s} {'d(peR) km':>12s}")
        for row in bridge_mod.compare_patches(system, game["patches"], traj):
            gb, mb = row["game_body"] or "-", row["mine_body"] or "-"
            if row.get("dt_start") is None:
                print(f"  {row['i']:2d} {gb:12s} {mb:12s} {'--':>12s} {'--':>15s} "
                      f"{'--':>15s} {'--':>12s}")
                fails.append(f"patch {row['i']}: one side has a patch the other does not "
                             f"(game {gb}, shooter {mb})")
                continue
            flag = "" if row["same_body"] else "   <-- DIFFERENT BODY"
            print(f"  {row['i']:2d} {gb:12s} {mb:12s} {row['dt_start']:12,.3f} "
                  f"{row['game_peR'] / 1e3:15,.1f} {row['mine_peR'] / 1e3:15,.1f} "
                  f"{row['dpeR'] / 1e3:12,.1f}{flag}")
            if not row["same_body"]:
                fails.append(f"patch {row['i']}: the game says {gb}, the shooter says {mb}")
            elif abs(row["dt_start"]) > args.tol_s:
                fails.append(f"patch {row['i']} ({gb}) starts {row['dt_start']:,.1f} s apart")
        if game.get("truncated"):
            print(f"  (the game stopped at {args.maxpatches} patches; raise --maxpatches)")

    print()
    if fails:
        print("  DISAGREEMENTS:")
        for f in fails:
            print(f"    - {f}")
        sys.exit(1)
    print("  the replica and the running game agree.")


def cmd_selftest(args):
    import selftest
    sys.exit(0 if selftest.run(System(instance=args.instance), verbose=True) else 1)


# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="plan.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance", default=r"C:/git/ksp/Instance")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def alarm_flags(p):
        p.add_argument("--alarm", nargs="?", const="", metavar="NAME",
                       help="set an alarm for the result (KAC, or the stock clock if KAC is "
                            "absent). Give a name, or pass it bare for a default one.")
        p.add_argument("--alarm-margin", type=float, default=0.0, metavar="SECONDS",
                       help="fire the alarm this many seconds early (default 0)")
        p.add_argument("--alarm-type", default="Raw",
                       help="KAC alarm type; `plan.py alarms` lists what KAC accepts. "
                            "Contract/ContractAuto are refused -- KAC deletes those.")

    def common(p, vessel=True, push=True):
        if vessel:
            p.add_argument("--vessel", help="vessel name from the save (substring is enough)")
            p.add_argument("--save", help="save folder or .sfs path; default = most recent")
            p.add_argument("--park", nargs="*", type=float, default=[185.0, 28.5],
                           metavar=("ALT_KM", "INC_DEG"),
                           help="parking orbit when there is no --vessel: ALT INC [RAAN]. Omit RAAN and the coplanar one is solved for.")
            p.add_argument("--body", default="Earth", help="parent body for --park")
            p.add_argument("--at", help="epoch for the starting state (default: the save's UT)")
            p.add_argument("--live", action="store_true",
                           help="read state from the running game via the AXE bridge, not the save")
            p.add_argument("--port", type=int, default=bridge_mod.DEFAULT_PORT,
                           help="AXE bridge port")
            p.add_argument("--ksptot-port", type=int, default=ksptot_mod.DEFAULT_PORT,
                           help="KSPTOT Connect port (live vessel state)")
        p.add_argument("--via", nargs="*", help="extra bodies whose SOI may be entered")
        p.add_argument("--horizon", type=float, default=400.0,
                       help="days past arrival to keep flying (default 400)")
        p.add_argument("--trajectory", action="store_true", help="print every patch")
        # Only on commands that actually SOLVE a burn. `verify` reports what existing nodes
        # do; giving it a --push that silently did nothing would be worse than not having it.
        if vessel and push:
            alarm_flags(p)
            p.add_argument("--push", action="store_true",
                           help="place the solved burn in the running game as a maneuver node "
                                "(needs -axe-bridge and --vessel)")
            p.add_argument("--push-add", action="store_true",
                           help="keep the vessel's existing nodes instead of replacing them")
            p.add_argument("--push-vessel",
                           help="push to this vessel instead of --vessel")

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
    p.add_argument("--inc", type=float,
                   help="parking inclination, deg (default: the site's latitude, else 28.5)")
    p.add_argument("--site", help="launch site, to also print the launch time of day")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--sep", type=float, default=150.0, help="days between distinct windows")
    p.add_argument("--include-capture", action="store_true")
    p.add_argument("--max-c3", type=float, default=3.0,
                   help="drop local minima worse than this multiple of the best C3")
    p.set_defaults(func=cmd_window)

    p = sub.add_parser("launch", help="when to launch to reach a given orbit plane")
    p.add_argument("--site", help="launch site name (default: the one the save is using)")
    p.add_argument("--body", default="Earth", help="body being launched from")
    p.add_argument("--target", help="solve the plane that makes a departure to this body coplanar")
    p.add_argument("--depart", help="departure date, with --target")
    p.add_argument("--inc", type=float, help="parking inclination, deg")
    p.add_argument("--park-inc", type=float, default=28.5,
                   help="inclination floor when --inc is not given (raised to the site's latitude)")
    p.add_argument("--raan", type=float, help="parking RAAN, deg -- give this or --target")
    p.add_argument("--alt", type=float, default=185.0, help="parking altitude, km")
    p.add_argument("--after", help="earliest launch date to report (default: the save's UT)")
    p.add_argument("--count", type=int, default=6, help="crossings to list")
    p.add_argument("--pick", type=int, default=0, help="which listed crossing --alarm uses")
    p.add_argument("--v-orbit", type=float, default=7800.0,
                   help="orbital speed used for the rotation correction on the flown azimuth")
    p.add_argument("--live", action="store_true",
                   help="calibrate the pad's zero point against the running game -- do this, "
                        "or the time of day is only right up to an unknown constant")
    p.add_argument("--save")
    p.add_argument("--port", type=int, default=bridge_mod.DEFAULT_PORT)
    alarm_flags(p)
    p.set_defaults(func=cmd_launch)

    p = sub.add_parser("alarms", help="list the alarms the game is holding")
    p.add_argument("--port", type=int, default=bridge_mod.DEFAULT_PORT)
    p.add_argument("--delete", metavar="ID", help="delete this alarm instead of listing")
    p.set_defaults(func=cmd_alarms)

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
    p.add_argument("--through", nargs="+", metavar="BODY",
                   help="gravity-assist bodies to fly THROUGH on the way to --target. "
                        "Switches to a position-residual shooting solver: the assists are "
                        "flown by the shooter, not approximated, and the B-plane residual "
                        "that cannot see past a flyby is not used.")
    p.add_argument("--arrive", help="expected arrival date, to size the horizon "
                                    "(with --through, the arrival epoch to aim at)")
    p.add_argument("--peri", help="target periapsis, e.g. 2.5Rj or 250km (default 1.5r)")
    p.add_argument("--samples", type=int, default=12,
                   help="burn times to try; with --through, arrival epochs to scan")
    p.add_argument("--span", type=float, default=90.0,
                   help="days either side of the natural encounter to scan (--through)")
    p.add_argument("--max-dv", type=float, default=1000.0,
                   help="bound on the correction, m/s per axis. Unbounded, least squares "
                        "can find a wholly different trajectory that grazes the aim point "
                        "-- measured, a 4,892 m/s answer with a 0 km miss. Raise it if a "
                        "genuinely large correction is expected.")
    p.add_argument("--diff-step", type=float, default=1e-2,
                   help="finite-difference step for the shooting Jacobian, m/s. SciPy's is "
                        "relative, so this is the step near zero.")
    p.add_argument("--max-nfev", type=int, default=60, help="shots per arrival epoch")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_correct)

    p = sub.add_parser("flyby", help="evaluate or aim a flyby")
    common(p)
    p.add_argument("body_target", metavar="BODY", help="the body to fly past")
    p.add_argument("--peri", help="solve for this flyby periapsis if there is no encounter")
    p.add_argument("--samples", type=int, default=12)
    p.add_argument("--max-dv", type=float, default=1000.0,
                   help="bound on the aim burn, m/s per axis")
    p.set_defaults(func=cmd_flyby)

    p = sub.add_parser("verify", help="fly the current trajectory and report what happens")
    common(p, push=False)
    p.add_argument("--target")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("bridge", help="ping the running game through the AXE bridge")
    p.add_argument("--port", type=int, default=bridge_mod.DEFAULT_PORT)
    p.add_argument("--ksptot-port", type=int, default=ksptot_mod.DEFAULT_PORT)
    p.add_argument("--vessels", action="store_true", help="also list the game's vessels")
    p.set_defaults(func=cmd_bridge)

    p = sub.add_parser("crosscheck", help="diff this toolchain against the running game")
    p.add_argument("--port", type=int, default=bridge_mod.DEFAULT_PORT)
    p.add_argument("--ksptot-port", type=int, default=ksptot_mod.DEFAULT_PORT)
    p.add_argument("--vessel", help="also check this vessel's state and a predicted trajectory")
    p.add_argument("--save")
    p.add_argument("--at", help="node epoch for the prediction (default: now)")
    p.add_argument("--dv", help="node components to test, 'radial,normal,prograde'")
    p.add_argument("--horizon", type=float, default=400.0)
    p.add_argument("--maxpatches", type=int, default=8)
    p.add_argument("--top", type=int, default=8, help="worst N bodies to print")
    p.add_argument("--tol-s", type=float, default=1.0,
                   help="allowed disagreement in an SOI transition time, seconds")
    p.add_argument("--sites", action="store_true",
                   help="also check the launch-site zero point that launch times depend on")
    p.set_defaults(func=cmd_crosscheck)

    p = sub.add_parser("selftest", help="check the whole chain against known answers")
    p.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
