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
import tour
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
        vid = getattr(args, "vessel_id", None)
        if vid:
            # An id is unambiguous by construction and KSPTOT Connect keys on names, so
            # asking it would throw the disambiguation away again. Go straight to the bridge.
            br = bridge_mod.Bridge(port=args.port)
            body, r, vel, ut = br.state(system, vid=vid, ut=ut)
            info = br.nodes(vid=vid)
            if not info.get("nodes_available"):
                why = info.get("why") or "not the active vessel"
                sys.exit(f"  {info.get('vessel')} [{vid}] has no patched conics: {why}. "
                         "Live trajectory numbers for a non-active vessel are garbage and "
                         "any node pushed to it is discarded. Switch to it in-game first.")
            return (body, np.asarray(r), np.asarray(vel), ut,
                    f"{info.get('vessel')} [live, id {vid[:8]}]", None)
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
    vid = getattr(args, "vessel_id", None)

    if getattr(args, "push", False):
        if not vessel and not vid:
            sys.exit("--push needs a vessel: pass --vessel NAME (a --park orbit is "
                     "hypothetical, so there is nothing in the game to place a node on)")
        try:
            res = br.place_nodes([(ut, n[0], n[1], n[2]) for ut, n in burns],
                                 name=None if vid else vessel, vid=vid,
                                 replace=not args.push_add)
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
        if rep.get("plane"):
            print(f"{indent}       {rep['inc_to_plane']:.2f} deg off {rep['plane']}'s orbital "
                  f"plane (asymptote floor {rep['plane_floor']:.2f} deg); periapsis latitude "
                  f"{rep['peri_lat']:+.2f} deg -- the apoapsis burn can take the plane down to "
                  f"|{rep['peri_lat']:.2f}| deg, no further")
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
    inc_floor = site.min_inclination() if site else 0.0

    # A pad's latitude is a FLOOR on inclination, not a ceiling: from latitude phi any
    # i >= phi is reachable by flying an azimuth off due east, sin(az) = cos(i)/cos(phi).
    # Pinning the scan to i = phi and then calling every window with |DLA| > phi
    # "unreachable" inverted that -- it condemned windows a LOW-latitude pad reaches most
    # easily of all, because a low pad has the most azimuth freedom. The parking plane a
    # window actually needs is i = max(|DLA|, phi), solved per row.
    def inc_for(dla):
        return inc if inc is not None else max(abs(dla), inc_floor, 28.5 if not site else 0.0)

    print(f"{dep.name} -> {arr.name}  from a {args.alt:.0f} km parking orbit "
          f"around {dep.name}   ({len(deps)} departures x {len(tofs)} TOFs)")
    if site:
        print(f"  launch times are for {site.display} ({site.lat:+.3f}, {site.lon:+.3f}); "
              f"it cannot reach below i {inc_floor:.2f} deg, and flies "
              f"i = max(|DLA|, {inc_floor:.2f}) unless --inc says otherwise")
    head = (f"{'departure':>12s} {'TOF d':>7s} {'arrival':>12s} {'C3':>8s} {'dv dep':>8s} "
            f"{'vinf arr':>9s} {'DLA':>7s} {'inc':>7s} {'RAAN':>7s}")
    if site:
        head += f" {'launch (UTC)':>17s} {'az':>7s}"
    print(head)
    for i in sorted(picked):
        td, tf, c3, dv, vinf_a, dla = rows[i]
        inc_row = inc_for(dla)
        r1, v1b = system.state(dep.name, td, centre)
        r2, v2b = system.state(arr.name, td + tf, centre)
        raan = None
        try:
            vt1, _ = lambert(mu, np.array(r1), np.array(r2), tf)
            cands = align_raan(inc_row, np.asarray(vt1) - np.asarray(v1b))
            raan = cands[0] if cands else None
        except Exception:                                           # noqa: BLE001
            raan = None
        line = (f"{date_of(td):%Y-%m-%d}   {tf / DAY:7.0f} {date_of(td + tf):%Y-%m-%d}   "
                f"{c3:8.2f} {dv:8,.0f} {vinf_a:9,.0f} {dla:7.2f} {inc_row:7.2f} "
                + (f"{raan:7.2f}" if raan is not None else f"{'--':>7s}"))
        if site:
            when = az = None
            if raan is not None:
                try:
                    # The pad crossing nearest the departure instant, not merely the next
                    # one after it: a window quoted at midnight would otherwise report a
                    # launch most of a day late for no reason.
                    ps = launch_mod.plane_passes(site, system, inc_row, raan, td - DAY, count=4)
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
        steep = [i for i in picked if abs(rows[i][5]) > inc_floor]
        if steep:
            print(f"  A window whose |DLA| exceeds the pad's {inc_floor:.2f} deg latitude is "
                  f"still reachable -- it is flown at i = |DLA| on an azimuth off due east "
                  f"(sin az = cos i / cos lat), which costs some of the rotation bonus, not "
                  f"the window. The `inc` column is the plane each row needs.")
        if inc is not None:
            missed = [i for i in picked if abs(rows[i][5]) > inc + 1e-9]
            if missed:
                print(f"  \"unreachable\" here is only because --inc {inc:.2f} was forced "
                      f"below those rows' |DLA|; drop --inc to let each row pick its plane.")
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


def _realign_direct(system, body, target, t_dep, alt, inc, cands, args):
    """Settle the parking plane against the arc it actually produces.

    For a direct transfer the plane has to contain the target's position ON ARRIVAL, but
    the arrival time is not known until the arc is searched and the arc depends on the
    plane. Two or three passes settle it. Aligning once to a Hohmann guess is not enough:
    the Moon moves 13 deg/day, so a 0.1 d error in the assumed time of flight leaves it
    out of plane and the injection pays for it as a plane change.
    """
    hoh = _hohmann_days(system, body, target, r_from=body.radius + alt * 1e3)
    lo, hi = args.tof if args.tof else [0.6 * hoh, 1.8 * hoh]
    best = None
    for _ in range(4):
        r0, v0 = park_orbit(body, alt, inc, cands[0])
        got = _direct_injection(system, body, r0, v0, t_dep, target,
                                (lo, hi), args.samples, args)
        if got is None:
            break
        if best is None or got[0] < best[0]:
            best = (got[0], cands)
        nxt = align_raan(inc, np.asarray(system.rel(target.name, got[2])[0], float))
        if not nxt or abs((nxt[0] - cands[0] + 180.0) % 360.0 - 180.0) < 1e-3:
            break
        cands = nxt
    return best[1] if best is not None else cands


def _b_dir(args):
    """B-plane aim direction from --bplane, or None to keep whatever the trajectory has.

    `--peri` fixes only the MAGNITUDE of the miss vector, so it says how close you pass and
    says nothing about which SIDE. Both solutions exist and the solver converges to whichever
    is nearer the seed -- which for Earth->Saturn 1972 is the retrograde one, arriving at
    i 158 deg. That silently breaks any tour of prograde moons and doubles an entry probe's
    airspeed. In `astro.bplane`'s frame w.k = |s x k| * B_T/|B|, so B_T > 0 is prograde;
    pure +/-T is also the minimum-inclination member of each branch.
    """
    want = getattr(args, "bplane", None)
    if not want:
        return None
    if want.startswith("plane:") or want.startswith("apsis:"):
        # plane:<Body> = minimum inclination to that body's orbital plane; apsis:<Body> = the
        # capture PERIAPSIS in that plane, which is what a moon tour actually needs (see
        # maneuver.apsis_b_dir). Both depend on the flown asymptote, so refine resolves them.
        return want
    if want not in ("prograde", "retrograde", "polar", "polar2"):
        sys.exit(f"--bplane {want}: expected prograde, retrograde, polar, polar2, plane:<Body> "
                 "or apsis:<Body>")
    # Same identity, read the other way: B_T = 0 puts w.k = 0, i.e. inclination 90.
    # A polar capture is therefore a PURE +/-R aim, and the two signs are the same
    # 90 deg orbit with its node 180 deg apart (north-going vs south-going).
    if want == "polar":
        return np.array([0.0, 1.0])
    if want == "polar2":
        return np.array([0.0, -1.0])
    return np.array([1.0, 0.0]) if want == "prograde" else np.array([-1.0, 0.0])


def _arrival_epochs(system, body, target, t_dep, args):
    """The arrival dates a departure search will consider, in one place.

    Both the parking-plane alignment and the burn search have to walk the same list,
    or the plane gets aligned to a transfer that is never flown.
    """
    if getattr(args, "arrive", None):
        return [parse_date(args.arrive)]
    hoh = _hohmann_days(system, body, target)
    lo, hi = getattr(args, "tof", None) or [0.4 * hoh, 2.0 * hoh]
    return [t_dep + d * DAY for d in np.arange(lo, hi, max((hi - lo) / 60.0, 0.05))]


def _departure_direction(system, body, target, t_dep, direct, alt, args):
    """Unit direction the parking orbit's plane has to contain, for the transfer FLOWN.

    Aligning to a Hohmann time of flight instead is a silent, expensive error: Earth ->
    Saturn's Hohmann is 2,204 d against the flown 1,500 d, which put the node 45 deg out
    and turned a 7,506 m/s departure into 11,417 m/s while still calling itself coplanar.

    Once the plane contains the asymptote the burn is monotonic in C3, so the cheapest
    arrival is the one with the smallest v-infinity -- and THAT choice does not depend on
    the parking orbit, which is what breaks the circularity between the two.
    """
    if direct:
        tof = getattr(args, "tof", None)
        days = (0.5 * (tof[0] + tof[1]) if tof
                else _hohmann_days(system, body, target, r_from=body.radius + alt * 1e3))
        u, _ = system.rel(target.name, t_dep + days * DAY)
        return np.asarray(u, float)
    best = None
    for t_arr in _arrival_epochs(system, body, target, t_dep, args):
        try:
            vinf, _, _ = maneuver.vinf_for_transfer(system, body.name, target.name,
                                                    t_dep, t_arr)
        except Exception:
            continue
        m = float(np.linalg.norm(vinf))
        if best is None or m < best[0]:
            best = (m, vinf, t_arr)
    return None if best is None else best[1]


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
        u = _departure_direction(system, body, target, t_dep, direct, alt, args)
        cands = align_raan(inc, u) if u is not None else []
        if cands and direct:
            cands = _realign_direct(system, body, target, t_dep, alt, inc, cands, args)
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
        arrivals = _arrival_epochs(system, body, target, t_dep, args)
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
            if getattr(args, "_raan_note", None):
                print(f"    *** the RAAN was solved to make this coplanar and it did not: "
                      f"the parking plane does not contain the asymptote. Do not fly this. ***")

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
                              t_end, peR_want=peR, b_dir=_b_dir(args),
                              watch=[target.name] + list(args.via or []))
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
                                  b_dir=_b_dir(args),
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


def parse_burn_at(text, ut0):
    """'+2h', '+1.5d', '+90m' from the state epoch, or a date."""
    t = str(text).strip().lower()
    if t.startswith("+"):
        scale = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": DAY}.get(t[-1])
        if scale is None:
            sys.exit(f"--burn-at {text}: a relative time ends in s, m, h or d")
        return ut0 + float(t[1:-1]) * scale
    return parse_date(text)


def print_handoff(system, chosen):
    """What the chosen aim leaves for the NEXT moon -- the number a handoff is bought with."""
    if not chosen.get("handoff") or not chosen.get("vinf_next"):
        return
    moon = system.body(chosen["handoff"])
    land = tour.landing_dv(moon, chosen["vinf_next"])
    cross, soi = chosen.get("cross_next"), chosen.get("soi_next")
    where = ""
    if cross is not None:
        where = (f", {cross / 1e3:,.0f} km cross-track vs SOI {soi / 1e3:,.0f} -- "
                 + ("reachable at any longitude" if cross <= soi else "only near a node"))
    print(f"     hands off to {moon.name}: v-infinity {chosen['vinf_next']:,.0f} m/s, "
          f"landing burn {land:,.0f} m/s, {chosen['irel_next']:.2f} deg off its plane{where}")


def alt_list(text):
    """`300,1000,3000,12000` -- flyby altitudes in km, for scanning depth as well as angle."""
    try:
        out = [float(x) for x in str(text).replace(" ", "").split(",") if x]
    except ValueError:
        out = []
    if not out:
        raise argparse.ArgumentTypeError("give altitudes in km, comma separated, e.g. 300,3000,12000")
    return out


AIM_MODES = ("pump", "resonance", "none")


def aim_mode(text):
    """`pump`, `resonance`, `none`, or `handoff:<Moon>`.

    The handoff form names the moon the flyby is FOR. It exists because the other two modes
    optimise quantities that cannot make a landing on a different moon affordable: a flyby
    never changes v-infinity at the moon doing the flying, so the only thing a Ganymede pass
    buys a Callisto lander is a gentler Callisto crossing -- and `pump`, left to itself, walks
    straight past the orbit that gives one.
    """
    t = str(text).strip()
    if t in AIM_MODES:
        return t
    if t.lower().startswith("handoff:") and t.split(":", 1)[1].strip():
        return "handoff:" + t.split(":", 1)[1].strip()
    raise argparse.ArgumentTypeError(
        f"aim must be one of {', '.join(AIM_MODES)}, or handoff:<Moon> (e.g. handoff:Callisto)")


def aim_handoff(mode):
    return mode.split(":", 1)[1] if str(mode).startswith("handoff:") else None


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
    if getattr(args, "burn_at", None):
        # A fixed burn time, solved once. The scan's first sample is 2 percent of the way to
        # the encounter -- 10 days out on a Jupiter cruise -- which is useless when the burn
        # has to happen before a launch window opens tomorrow.
        ut_b = parse_burn_at(args.burn_at, ut0)
        b_at, rb, vb = traj.state(ut_b)
        print(f"\n  --- correcting to periapsis {peR / target.radius:.3f} "
              f"R{target.name[0].lower()} ({(peR - target.radius) / 1e3:,.0f} km altitude), "
              f"burning at {fmt_ut(ut_b)} (T+{(ut_b - ut0) / DAY:.2f} d) ---")
        if getattr(args, "aim", "none") not in (None, "none"):
            # A trim onto a moon has the same B-plane freedom as the burn that set the
            # encounter up, and the same consequences: the aim decides whether the flyby
            # pumps the orbit down or throws the vessel out of the planet's SOI. Fly them.
            parent = system.body(target.parent) if getattr(target, "parent", None) else body
            hand = aim_handoff(args.aim)
            print(f"\n  AIM SCAN at {target.name} (each angle flown)")
            angles = [a * 360.0 / args.aim_steps for a in range(args.aim_steps)]
            pers = ([target.radius + a * 1e3 for a in args.aim_alts]
                    if getattr(args, "aim_alts", None) else None)
            flown = tour.aim_fly(system, parent, target, rb, vb, ut_b, np.zeros(3), peR,
                                 rep.get("soi_ut") or t_arr, angles, max_dv=args.max_dv,
                                 handoff=hand, pers=pers)
            usable = tour.usable_aims(flown, args.aim)
            if not usable:
                sys.exit("  no aim angle leaves a bound orbit that still reaches the moon"
                         + (f" and crosses {hand}" if hand else ""))
            chosen = tour.pick_aim(usable, args.aim,
                                   moon_period=tour.moon_period(system, target))
            print(f"  -> {chosen.get('picked_by', args.aim)} aim psi {chosen['psi']:.0f} deg: {chosen['peR'] / 1e6:,.0f} x "
                  f"{chosen['apR'] / 1e6:,.0f} Mm, period {tour.dhms(chosen['period'])} = "
                  f"{chosen['resonance']:.3f} {target.name} periods, {chosen['irel']:.2f} deg off its plane")
            print_handoff(system, chosen)
            res = chosen["res"]
            # --aim-alts flies SEVERAL depths, and the winner is usually not the one --peri
            # named: depth is half the aim, so the scan is allowed to pick it. Judge the
            # winner against the periapsis IT asked for, or a 8,019 km handoff aim gets
            # thrown away for not being the 300 km that was typed -- with the answer already
            # in hand and printed one line above.
            peR = chosen.get("per_want", peR)
        else:
            res = maneuver.refine(system, b_at.name, rb, vb, ut_b, target.name, t_end, peR,
                                  b_dir=_b_dir(args), watch=watch, max_dv=args.max_dv,
                                  diff_step=args.diff_step, verbose=args.verbose)
        rp = res["report"]
        # An AIM is judged on the aim scan's own tolerance, not the tighter one a plain
        # correction uses. The scan already flew every angle and kept only solves within 8
        # percent of the requested periapsis; re-testing the winner at 2 percent here threw
        # away a perfectly good 224 km Ganymede pass for not being the 300 km that was typed,
        # and told the user to go find another burn date for an answer it already had.
        tol = 0.08 if getattr(args, "aim", "none") not in (None, "none") else 0.02
        if not (rp.get("captured") and abs(rp["peR"] - peR) / peR < tol):
            print_arrival(system, target.name, rp)
            sys.exit("  the correction did not converge at that burn time; try another "
                     "--burn-at, or drop it and let the scan pick one")
        if abs(rp["peR"] - peR) / peR > 0.02:
            print(f"  note: the aim lands at {(rp['peR'] - target.radius) / 1e3:,.0f} km altitude, "
                  f"not the {(peR - target.radius) / 1e3:,.0f} km asked for -- that is the flyby "
                  f"this aim actually buys, and what everything below is computed from")
        node, _ = print_node(system, b_at, rb, vb, res["dv"], ut_b,
                             now=(save.ut if save else None), label="CORRECTION")
        print_arrival(system, target.name, rp)
        push_burns(args, [(ut_b, node)], what="correction")
        return
    print(f"\n  --- correcting to periapsis {peR / target.radius:.3f} "
          f"R{target.name[0].lower()} ({(peR - target.radius) / 1e3:,.0f} km altitude) ---")
    best, scan = maneuver.cheapest_correction(system, body.name, r0, v0, ut0, target.name,
                                              t_arr, peR, t_end=t_end,
                                              b_dir=_b_dir(args),
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


def parse_apo(system, body, text):
    """'20Gm', '400Mm', or anything parse_radius takes; a body NAME means that body's orbit radius."""
    t = str(text).strip().lower().replace(",", "")
    if t.endswith("gm"):
        return float(t[:-2]) * 1e9
    if t.endswith("mm"):
        return float(t[:-2]) * 1e6
    for b in system.bodies.values():
        if b.name.lower() == t and getattr(b, "parent", None) == body.name:
            return b.a
    return parse_radius(system, body, text)


def cmd_capture(args):
    """Orbit insertion: the retrograde burn at the periapsis of the current hyperbola."""
    system, save = load(args)
    body, r0, v0, ut0, who, _ = origin_state(system, save, args)
    mu = body.mu
    r0 = np.asarray(r0, float)
    v0 = np.asarray(v0, float)
    rn = float(np.linalg.norm(r0))
    energy = float(v0 @ v0) / 2 - mu / rn
    if energy <= 0:
        sys.exit(f"  {who} is already bound to {body.name}; capture needs a hyperbola")
    a_h = -mu / (2 * energy)
    h = np.cross(r0, v0)
    e_vec = np.cross(v0, h) / mu - r0 / rn
    ecc = float(np.linalg.norm(e_vec))
    vinf = math.sqrt(2 * energy)
    nu = math.acos(max(-1.0, min(1.0, float(e_vec @ r0) / (ecc * rn))))
    if float(r0 @ v0) < 0:
        nu = -nu
    F = 2 * math.atanh(math.sqrt((ecc - 1) / (ecc + 1)) * math.tan(nu / 2))
    M = ecc * math.sinh(F) - F
    t_p = ut0 - M / math.sqrt(mu / abs(a_h) ** 3)      # hyperbolic a is negative
    moons = [b.name for b in system.bodies.values() if getattr(b, "parent", None) == body.name]

    print(f"CAPTURE  {who}  at  {body.name}   (state at {fmt_ut(ut0)})")
    print(f"  inbound hyperbola: v-infinity {vinf:,.1f} m/s  e {ecc:.4f}  "
          f"periapsis {a_h * (1 - ecc) / 1e3:,.0f} km = {a_h * (1 - ecc) / body.radius:.3f} "
          f"R{body.name[0].lower()}  at {fmt_ut(t_p)} (T+{(t_p - ut0) / DAY:.2f} d)")
    # Fly the inbound leg with the moons watched: a moon SOI before periapsis changes everything.
    traj = patched.shoot(system, body.name, r0, v0, ut0, t_p + DAY, watch=moons)
    passes = [p.body.name for p in traj.patches if p.body.name != body.name]
    if passes:
        print(f"  NOTE: the inbound leg passes through {', '.join(passes)}'s SOI first")
    b_at, r_p, v_p = traj.state(t_p)
    if b_at.name != body.name:
        sys.exit(f"  at the nominal periapsis time the vessel is inside {b_at.name}'s SOI -- "
                 "re-aim the arrival past it, then capture")
    r_p = np.asarray(r_p, float)
    v_p = np.asarray(v_p, float)
    rp = float(np.linalg.norm(r_p))
    vp = float(np.linalg.norm(v_p))
    ra = parse_apo(system, body, args.apo)
    if ra <= rp:
        sys.exit(f"  --apo {args.apo} is inside the periapsis ({rp / 1e3:,.0f} km)")
    if ra >= body.soi:
        sys.exit(f"  --apo {args.apo} is outside {body.name}'s SOI ({body.soi / 1e9:,.2f} Gm)")
    a_new = (rp + ra) / 2
    v_ell = math.sqrt(mu * (2 / rp - 1 / a_new))
    dv = vp - v_ell
    dv_vec = -dv * v_p / vp
    node = astro.to_node(r_p, v_p, dv_vec)
    period = 2 * math.pi * math.sqrt(a_new ** 3 / mu)
    print(f"\n  --- capturing into {rp / 1e3:,.0f} x {ra / 1e6:,.0f} Mm "
          f"(apoapsis {ra / body.soi * 100:.0f}% of the SOI), period {period / DAY:,.1f} d ---")
    print(f"  BURN  {fmt_ut(t_p)}   periapsis speed {vp:,.1f} -> {v_ell:,.1f} m/s")
    print(f"    prograde {node[2]:+12,.2f} m/s")
    print(f"    normal   {node[1]:+12,.2f} m/s")
    print(f"    radial   {node[0]:+12,.2f} m/s")
    print(f"    total    {dv:12,.2f} m/s")
    if args.mass and args.thrust:
        isp = args.isp
        m0 = args.mass * 1e3
        m1 = m0 * math.exp(-dv / (isp * 9.80665))
        print(f"    {m0 / 1e3:.3f} t at {args.thrust:.2f} kN: burn {(m0 - m1) * isp * 9.80665 / (args.thrust * 1e3):,.0f} s, "
              f"{(m0 - m1):,.0f} kg of propellant, {m1 / 1e3:.3f} t after")
    # Fly one full revolution after the burn, moons watched.
    traj2 = patched.shoot(system, body.name, r_p, v_p + dv_vec, t_p, t_p + 1.05 * period, watch=moons)
    hh = np.cross(r_p, v_p + dv_vec)
    ev = np.cross(v_p + dv_vec, hh) / mu - r_p / rp
    e2 = float(np.linalg.norm(ev))
    a2 = 1 / (2 / rp - float((v_p + dv_vec) @ (v_p + dv_vec)) / mu)
    inc2 = math.degrees(math.acos(hh[2] / np.linalg.norm(hh)))
    hits = [(p.body.name, p.ut0) for p in traj2.patches if p.body.name != body.name]
    print(f"    FLOWN: {a2 * (1 - e2) / 1e3:,.0f} x {a2 * (1 + e2) / 1e6:,.0f} Mm  e {e2:.4f}  "
          f"i {inc2:.2f} deg  period {2 * math.pi * math.sqrt(a2 ** 3 / mu) / DAY:,.1f} d; "
          + (f"first revolution enters {', '.join(f'{n} at {fmt_ut(t)}' for n, t in hits)}"
             if hits else "first revolution meets no moon"))
    t_apo = t_p + period / 2
    v_apo = math.sqrt(mu * (2 / ra - 1 / a_new))
    if args.plane:
        i_rel = maneuver.inc_to_plane(system, traj2, body.name, t_p, args.plane)
        lat = maneuver.periapsis_latitude(system, traj2, body.name, t_p, args.plane)
        print(f"           {i_rel:.2f} deg off {args.plane}'s orbital plane; periapsis latitude {lat:+.2f} deg")
    print(f"\n  apoapsis {fmt_ut(t_apo)} (T+{(t_apo - ut0) / DAY:.1f} d), speed there {v_apo:,.1f} m/s")
    if args.raise_to:
        rr = parse_apo(system, body, args.raise_to)
        v1 = math.sqrt(mu * (2 / ra - 1 / ((rr + ra) / 2)))
        line = f"  raising periapsis to {rr / 1e6:,.0f} Mm ({args.raise_to}) at apoapsis: {v1 - v_apo:,.1f} m/s coplanar"
        if args.plane:
            fold = math.sqrt(v_apo ** 2 + v1 ** 2 - 2 * v_apo * v1 * math.cos(math.radians(i_rel)))
            line += (f", {fold:,.1f} m/s with the {i_rel:.2f} deg plane change folded in "
                     f"(+{fold - (v1 - v_apo):,.1f}); total with capture {dv + fold:,.0f} m/s")
        print(line)
        print("  (that burn's TIMING must be solved against the moon's phase when the time comes -- "
              "the periapsis pass has to be a real encounter, not just the right radius)")
    push_burns(args, [(t_p, node)], what="capture")


def cmd_phase(args):
    """The dv-versus-wait trade for getting the moon to BE at one of our crossings."""
    system, save = load(args)
    body, r0, v0, ut0, who, _free = origin_state(system, save, args)
    moon = system.body(args.moon)
    parent = system.body(moon.parent)
    if body.name != parent.name:
        # mid-flyby is a normal moment to ask; fly out to the parent and phase from there
        tr0 = patched.shoot(system, body.name, r0, v0, ut0, ut0 + 30 * DAY, watch=[parent.name])
        out = next((q for q in tr0.patches if q.body.name == parent.name), None)
        if out is None:
            sys.exit(f"  {who} is in {body.name}'s SOI and does not leave it within 30 days")
        print(f"  (in {body.name}'s SOI; propagated out to {fmt_ut(out.ut0)})")
        r0, v0, ut0, body = out.r0, out.v0, out.ut0, parent
    el = astro.elements(body.mu, r0, v0)
    t_moon = tour.moon_period(system, moon)
    print(f"PHASE  {who}  ->  {moon.name}   (state at {fmt_ut(ut0)})")
    print(f"  orbit {el.peR / 1e6:,.0f} x {el.apR / 1e6:,.0f} Mm, period {tour.dhms(el.period)} = "
          f"{el.period / t_moon:.3f} {moon.name} periods")
    if not (el.peR <= moon.a <= el.apR):
        print(f"  NOTE: the orbit does not cross {moon.name}'s radius ({moon.a / 1e6:,.0f} Mm) -- "
              f"a phasing burn cannot invent a crossing, only time one.")
    want_miss = parse_radius(system, moon, args.peri) if getattr(args, "peri", None) else 0.0
    opts = tour.phase_options(system, body, moon, r0, v0, ut0,
                              max_revs=args.revs, dv_cap=args.dv_cap, steps=args.steps,
                              target_miss=want_miss)
    if not opts:
        sys.exit(f"  no burn within {args.dv_cap:,.0f} m/s puts {moon.name} at a crossing inside "
                 f"{args.revs} revolutions -- raise --revs or --dv-cap")
    print("")
    print(f"  {len(opts)} options, cheapest first. The trade is dv against WAIT: changing the "
          f"period by d shifts the j-th crossing by about j*d, so looking further out is"
          f" what makes the burn small.")
    print(f"  {'burn':>17s} {'dV':>9s} {'encounter':>17s} {'wait d':>8s} {'revs':>7s} "
          f"{'miss km':>9s} {'i_rel':>6s}  resulting orbit")
    for o in opts:
        print(f"  {fmt_ut(o['t_burn'])[:17]} {o['dv_signed']:+9.2f} {fmt_ut(o['t_enc'])[:17]} "
              f"{o['wait'] / DAY:8.1f} {o['revs']:7.2f} {o['miss'] / 1e3:9,.0f} {o['irel']:6.2f}  "
              f"{o['peR'] / 1e6:,.0f} x {o['apR'] / 1e6:,.0f} Mm")
    if getattr(args, "handoff", None):
        ranked = tour.rank_by_handoff(system, body, moon, opts, args.handoff)
        if not ranked:
            sys.exit(f"  none of the phasing options produced a flown {moon.name} encounter")
        hand = system.body(args.handoff)
        print("")
        print(f"  RANKED BY THE HANDOFF TO {hand.name.upper()} -- each flyby FLOWN, no aim burn.")
        print(f"  The phasing burn IS the aim: every crossing arrives with a different "
              f"B-vector, and re-aiming afterwards")
        print(f"  cost 162-190 m/s on Bus B at every lead time tried, while a different "
              f"option was free.")
        print(f"  {'dV':>9s} {'encounter':>17s} {'wait d':>8s} {'alt km':>9s} {'turn':>6s} "
              f"{'post-flyby orbit':>24s} {'v_inf':>8s} {'landing':>8s} {'cross km':>9s}")
        for o in ranked[:12]:
            line = (f"  {o['dv_signed']:+9.2f} {fmt_ut(o['t_enc'])[:17]} {o['wait'] / DAY:8.1f} "
                    f"{o['flyby_alt'] / 1e3:9,.0f} {o['turn_deg']:6.1f} "
                    f"{o['post_peR'] / 1e6:>11,.0f} x {o['post_apR'] / 1e6:<10,.0f}")
            if o.get("vinf_next"):
                line += (f" {o['vinf_next']:8,.0f} {o['land_next']:8,.0f} {o['cross_next'] / 1e3:9,.0f}"
                         + ("" if o["cross_next"] <= o["soi_next"] else "  NODE ONLY"))
            else:
                line += f" {'no ' + hand.name:>8s}"
            print(line)
        opts = ranked
    best = opts[0]
    rb, vb = astro.propagate(body.mu, np.asarray(r0, float), np.asarray(v0, float),
                             best["t_burn"] - ut0)
    dv = np.asarray(vb, float) * (best["dv_signed"] / float(np.linalg.norm(vb)))
    node, _ = print_node(system, body, rb, vb, dv, best["t_burn"],
                         now=(save.ut if save else None), label="PHASING BURN")
    print(f"    FLOWN: {moon.name} at {fmt_ut(best['t_enc'])}, miss {best['miss'] / 1e3:,.0f} km "
          f"against a {moon.soi / 1e3:,.0f} km SOI, {best['irel']:.2f} deg off its plane")
    print(f"           then AIM it: plan.py correct --target {moon.name} --peri <alt> "
          f"--burn-at <date> --aim handoff:<NextMoon> --aim-alts ...")
    push_burns(args, [(best["t_burn"], node)], what="phasing burn")


def cmd_encounter(args):
    """The apoapsis burn that turns the next periapsis into a real moon encounter."""
    system, save = load(args)
    body, r0, v0, ut0, who, _ = origin_state(system, save, args)
    moon = system.body(args.moon)
    if getattr(moon, "parent", None) != body.name:
        sys.exit(f"  {moon.name} does not orbit {body.name}")
    per = parse_radius(system, moon, args.peri, default_alt=300e3)
    print(f"ENCOUNTER  {who}  ->  {moon.name}   (state at {fmt_ut(ut0)})")
    t_apo, seeds, sols = tour.solve(system, body, moon, np.asarray(r0, float),
                                    np.asarray(v0, float), ut0, per,
                                    before=args.before, after=args.after, step=args.step,
                                    refine_n=args.refine, max_dv=args.max_dv)
    if not seeds:
        sys.exit("  no elliptic seed reaches the moon in that window; widen --before/--after")
    good = [s for s in sols if s["ok"]]
    if not good:
        sys.exit("  no converged solution; widen the window or raise --max-dv")
    # Which solution to fly is a real choice, so expose it. For a multi-moon tour the
    # inclination to the moon's plane usually matters MORE than a few tens of m/s of v_inf:
    # at Ganymede's orbit radius 1.3 deg of relative inclination is 23,500 km of cross-track
    # against a 24,359 km SOI, so encounters are only possible near the nodes. Near-coplanar
    # lets the tour meet the moon anywhere in its orbit.
    pick = {"vinf": lambda s: s["vinf"] + 2.0 * s["mag"],
            "coplanar": lambda s: s["irel"],
            "cheap": lambda s: s["mag"]}[args.prefer]
    best = min(good, key=pick)
    if len(good) > 1:
        alts = sorted(good, key=pick)[1:4]
        print("\n  other converged solutions:")
        for a in alts:
            print(f"    {fmt_ut(a['t_k'])[:16]}  burn {a['off']:+.1f} d from apoapsis  "
                  f"{a['mag']:,.1f} m/s  v-inf {a['vinf']:,.0f}  {a['irel']:.2f} deg off plane")
    # THE AIM. A flyby costs the same at every B-plane angle and the outcome swings from
    # ejection out of the planet's SOI to a halved period, so the default aim (whatever miss
    # direction the trajectory already had) is not a choice, it is an accident. Measured on
    # Perun 2 Bus A: the default aim pumped the orbit UP to a 50.5 Gm apoapsis against
    # Jupiter's 48.2 Gm SOI -- the bus would have left the system after one pass.
    if args.aim != "none":
        print(f"\n  AIM SCAN at {moon.name} (each angle flown, not modelled -- apoapsis here is "
              f"hypersensitive to the outgoing velocity)")
        angles = [a * 360.0 / args.aim_steps for a in range(args.aim_steps)]
        hand = aim_handoff(args.aim)
        pers = ([moon.radius + a * 1e3 for a in args.aim_alts]
                if getattr(args, "aim_alts", None) else None)
        flown = tour.aim_fly(system, body, moon, best["r_b"], best["v_b"], best["t_b"],
                             best["dv"], per, best["soi_ut"], angles, max_dv=args.max_dv,
                             handoff=hand, pers=pers)
        usable = tour.usable_aims(flown, args.aim)
        if not usable:
            print("  WARNING: no aim angle leaves a bound orbit that still reaches the moon"
                  + (f" and crosses {hand}." if hand else "."))
        else:
            chosen = tour.pick_aim(usable, args.aim,
                                   moon_period=tour.moon_period(system, moon))
            print(f"  -> {chosen.get('picked_by', args.aim)} aim psi {chosen['psi']:.0f} deg: "
                  f"{chosen['peR'] / 1e6:,.0f} x {chosen['apR'] / 1e6:,.0f} Mm, period "
                  f"{tour.dhms(chosen['period'])} = {chosen['resonance']:.3f} {moon.name} periods, "
                  f"{chosen['irel']:.2f} deg off its plane")
            print_handoff(system, chosen)
            best = dict(best, dv=chosen["dv"], mag=chosen["mag"], vinf=chosen["vinf"],
                        peR=chosen["flyby_peR"], post=chosen)
    node = astro.to_node(best["r_b"], best["v_b"], best["dv"])
    print()
    print(f"  BURN  {fmt_ut(best['t_b'])}   ({best['off']:+.1f} d from apoapsis, "
          f"T+{(best['t_b'] - ut0) / DAY:.1f} d)")
    print(f"    prograde {node[2]:+12,.2f} m/s")
    print(f"    normal   {node[1]:+12,.2f} m/s")
    print(f"    radial   {node[0]:+12,.2f} m/s")
    print(f"    total    {best['mag']:12,.2f} m/s")
    dv_free, turn = tour.free_dv(moon, best["vinf"], best["peR"])
    print(f"    FLOWN: {moon.name} SOI {fmt_ut(best['soi_ut'])}, periapsis {best['peR'] / 1e3:,.0f} km "
          f"(altitude {(best['peR'] - moon.radius) / 1e3:,.0f} km)")
    print(f"           v-infinity {best['vinf']:,.0f} m/s, {best['irel']:.2f} deg off {moon.name}'s plane")
    print(f"           that pass turns {turn:.1f} deg = {dv_free:,.0f} m/s of FREE velocity change")
    if args.mass and args.thrust:
        m0 = args.mass * 1e3
        m1 = m0 * math.exp(-best["mag"] / (args.isp * 9.80665))
        print(f"           {m0 / 1e3:.3f} t at {args.thrust:.2f} kN: burn "
              f"{(m0 - m1) * args.isp * 9.80665 / (args.thrust * 1e3):,.0f} s, {m0 - m1:,.0f} kg")
    push_burns(args, [(best["t_b"], node)], what="encounter burn")


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
                                                      b_dir=_b_dir(args),
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
        # Same trap as cmd_depart: the plane has to contain the asymptote of the transfer
        # actually flown, not of a Hohmann one. Pass --arrive/--tof to pin the arc.
        u = _departure_direction(system, body, target, t_dep, direct, args.alt, args)
        if u is None:
            sys.exit(f"no transfer to {target.name} found from {fmt_ut(t_dep)}")
        cands = align_raan(inc, np.asarray(u))
        if not cands:
            sys.exit(f"inclination {inc:.2f} deg cannot contain the departure direction to "
                     f"{target.name}; it needs at least {math.degrees(math.asin(min(1.0, abs(np.asarray(u)[2] / np.linalg.norm(u))))):.2f} deg")
        raan = cands[0]
        print(f"  departing to {target.name} on {fmt_ut(t_dep)}: the coplanar parking RAAN is "
              f"{cands[0]:.2f} deg (the other node is {cands[1]:.2f} deg)")
        if not getattr(args, "arrive", None):
            print(f"  (no --arrive given, so that plane is for the cheapest arrival in the "
                  f"scanned range -- pass --arrive to match the arc `depart` is flying)")
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
            p.add_argument("--vessel-id", dest="vessel_id",
                           help="vessel GUID, for --live. Names are NOT unique -- a probe and "
                                "its bus can carry the same one, and the name lookup then "
                                "silently answers for the wrong craft (whose patched conics do "
                                "not exist, so the numbers are garbage and any node is "
                                "discarded). `/nodes` with no argument reports the active "
                                "vessel's id; use it whenever a name is ambiguous.")
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
    p.add_argument("--arrive", help="arrival date, to pin the SAME arc `depart` is flying. "
                                    "Without it the plane is solved for the cheapest arrival in "
                                    "the scanned range, which is usually a different transfer.")
    p.add_argument("--tof", nargs=2, type=float,
                   help="time-of-flight range in days to search, with --target")
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
    p.add_argument("--bplane", metavar="AIM",
                   help="which side of the target to pass. --peri fixes only how CLOSE you pass; "
                        "without this the solver keeps whichever side it already has, which for "
                        "Earth->Saturn 1972 is retrograde (i 158 deg) and breaks a moon tour. "
                        "polar/polar2 aim the arrival at inclination 90 deg (the two node "
                        "branches) -- what a biome-mapping lunar orbiter wants. apsis:<Body> "
                        "puts the capture PERIAPSIS in that body's orbital plane, prograde -- "
                        "the aim a moon tour needs, because the apoapsis burn can only rotate "
                        "about the apsidal line (apsis:Ganymede, apsis:Titan). plane:<Body> is "
                        "minimum inclination to that plane instead, which leaves the apsides at "
                        "a latitude no later burn removes; the ecliptic 'prograde' is 25 deg "
                        "off the Galilean plane on top of that.")
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
    p.add_argument("--burn-at", metavar="WHEN",
                   help="burn at this time instead of scanning for the cheapest: '+2h' or "
                        "'+1d' from the state epoch, or a date. The scan's earliest sample "
                        "is 2 percent of the way to the encounter (10 days out on a Jupiter "
                        "cruise), so this is how you burn NOW.")
    p.add_argument("--aim", type=aim_mode, default="none",
                   help="for a trim onto a MOON: fly every B-plane angle and pick one by what the "
                        "flyby then does. `pump` takes the deepest pump-down that still returns to "
                        "the moon; `handoff:<Moon>` takes the lowest v-infinity at that NEXT moon, "
                        "which is the only one of these that can make a landing there affordable. "
                        "Needs --burn-at, and overrides --bplane.")
    p.add_argument("--aim-steps", type=int, default=24, help="B-plane angles to fly (default 24)")
    p.add_argument("--aim-alts", type=alt_list, default=None, metavar="KM,KM,...",
                   help="also fly these flyby ALTITUDES (km), not just the one --peri asks for. "
                        "Depth is the other half of an aim: the angle picks which way v-infinity "
                        "turns, the periapsis picks how far. A handoff usually wants a SHALLOW "
                        "pass -- on Perun 2 the Callisto pass that hands off to Ganymede is 7 deg "
                        "of turn, i.e. 12,000 km altitude, and flown at 300 km it turns 30 deg and "
                        "every angle lands worse than doing nothing.")
    p.add_argument("--bplane", metavar="AIM",
                   help="which side of the target to pass. --peri fixes only how CLOSE you pass; "
                        "without this the solver keeps whichever side it already has, which for "
                        "Earth->Saturn 1972 is retrograde (i 158 deg) and breaks a moon tour. "
                        "polar/polar2 aim the arrival at inclination 90 deg (the two node "
                        "branches) -- what a biome-mapping lunar orbiter wants. apsis:<Body> "
                        "puts the capture PERIAPSIS in that body's orbital plane, prograde -- "
                        "the aim a moon tour needs, because the apoapsis burn can only rotate "
                        "about the apsidal line (apsis:Ganymede, apsis:Titan). plane:<Body> is "
                        "minimum inclination to that plane instead, which leaves the apsides at "
                        "a latitude no later burn removes; the ecliptic 'prograde' is 25 deg "
                        "off the Galilean plane on top of that.")
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

    p = sub.add_parser("capture", help="orbit insertion at the periapsis of the current hyperbola")
    common(p)
    p.add_argument("--apo", required=True,
                   help="apoapsis radius of the capture orbit: 20Gm, 400Mm, 2.5Rj, or a moon's name")
    p.add_argument("--plane", metavar="BODY",
                   help="report the orbit's inclination to this moon's plane and the periapsis latitude")
    p.add_argument("--raise", dest="raise_to", metavar="RADIUS|BODY",
                   help="preview the apoapsis burn that raises periapsis to this radius (or moon)")
    p.add_argument("--mass", type=float, help="stack mass in t, for the burn duration")
    p.add_argument("--thrust", type=float, help="engine thrust in kN, for the burn duration")
    p.add_argument("--isp", type=float, default=312.0, help="engine Isp in s (default 312)")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("phase",
                       help="the dv-vs-WAIT trade for meeting a moon, over many revolutions")
    common(p)
    p.add_argument("--moon", required=True, help="moon to meet, e.g. Ganymede")
    p.add_argument("--revs", type=int, default=14,
                   help="how many revolutions ahead to look (default 14). `encounter` scans only "
                        "the FIRST periapsis pass after apoapsis, so its answer is always a "
                        "one-revolution answer -- and on a non-resonant orbit that is the "
                        "expensive one. Measured on Perun 2 Bus B: forcing the next pass cost "
                        "335 m/s, coming back 16 revolutions later cost 2.3.")
    p.add_argument("--dv-cap", type=float, default=250.0, help="bound on the phasing burn, m/s")
    p.add_argument("--steps", type=int, default=1200, help="dv grid resolution")
    p.add_argument("--handoff", metavar="MOON",
                   help="rank the options by what the UNAIMED flyby then hands off to this moon, "
                        "flying each one. Use it whenever the point of the encounter is to reach a "
                        "different moon: the phasing burn already decides the B-vector, so picking "
                        "the right option is free where re-aiming afterwards is not.")
    p.add_argument("--peri", help="phase to a MISS of this size rather than to the moon's centre, "
                                  "e.g. 7000km or 1.2Rg. Aiming at the centre leaves a periapsis "
                                  "below the surface, and a multi-revolution phasing burn cannot "
                                  "be re-aimed cheaply afterwards -- on Perun 2 Bus B pulling the "
                                  "periapsis back out cost 162-190 m/s at every aim angle.")
    p.set_defaults(func=cmd_phase)

    p = sub.add_parser("encounter",
                       help="apoapsis burn that makes the next periapsis a real moon encounter")
    common(p)
    p.add_argument("--moon", required=True, help="moon to encounter, e.g. Ganymede")
    p.add_argument("--peri", help="flyby periapsis, e.g. 300km or 1.2Rg (default 300 km altitude)")
    p.add_argument("--before", type=float, default=30.0,
                   help="days before the natural periapsis pass to start the epoch scan")
    p.add_argument("--after", type=float, default=45.0, help="days after it to stop")
    p.add_argument("--step", type=float, default=0.5, help="epoch scan step, days")
    p.add_argument("--refine", type=int, default=6, help="how many seeds to refine through the shooter")
    p.add_argument("--aim", type=aim_mode, default="pump",
                   help="B-plane aim at the encounter, each angle FLOWN. `pump` takes the deepest "
                        "pump-down that still returns to the moon; `resonance` prefers a near-integer "
                        "moon-period ratio; `handoff:<Moon>` takes the lowest v-infinity at that NEXT "
                        "moon, which is what a lander on it can afford. `none` keeps whatever aim the "
                        "solver happened to land on -- which on Perun 2 ejected the bus from Jupiter, "
                        "so do not use it.")
    p.add_argument("--aim-steps", type=int, default=24, help="B-plane angles to fly (default 24)")
    p.add_argument("--aim-alts", type=alt_list, default=None, metavar="KM,KM,...",
                   help="also fly these flyby ALTITUDES (km), not just the one --peri asks for. "
                        "Depth is the other half of an aim: the angle picks which way v-infinity "
                        "turns, the periapsis picks how far. A handoff usually wants a SHALLOW "
                        "pass -- on Perun 2 the Callisto pass that hands off to Ganymede is 7 deg "
                        "of turn, i.e. 12,000 km altitude, and flown at 300 km it turns 30 deg and "
                        "every angle lands worse than doing nothing.")
    p.add_argument("--prefer", choices=["vinf", "coplanar", "cheap"], default="vinf",
                   help="which converged solution to fly. `coplanar` minimises the inclination to "
                        "the moon's plane, which for a multi-moon tour usually beats a few tens of "
                        "m/s of v-infinity: 1.3 deg at Ganymede's radius is 23,500 km of cross-track "
                        "against a 24,359 km SOI, so encounters are then only possible near the nodes.")
    p.add_argument("--max-dv", type=float, default=400.0, help="bound on the correction, m/s per axis")
    p.add_argument("--mass", type=float, help="stack mass in t, for the burn duration")
    p.add_argument("--thrust", type=float, help="engine thrust in kN, for the burn duration")
    p.add_argument("--isp", type=float, default=312.0, help="engine Isp in s (default 312)")
    p.set_defaults(func=cmd_encounter)

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
