"""Plan a WHOLE moon tour as one search, instead of solving one burn at a time.

Solving a tour greedily is what walks it into a corner. Each burn looks defensible against
whatever single number you happened to optimise that day -- a resonance, an arrival speed, a
pump-down -- and meanwhile a second currency drains unwatched. On Perun 2 Bus A the plane error
went 0.07 -> 8.56 -> 13.26 degrees across three individually reasonable aims, and at 13.26 the
orbit misses Callisto's plane by 432,000 km against a 37,703 km SOI, so the handoff it had spent
800 m/s working toward was simply gone. Nothing in any single step said so.

The simulation is deterministic, so the whole sequence is computable in advance. This searches it.

MODEL. A tour state is a Jupiter-centric orbit plus an epoch. One step is:

  * choose the next moon to meet, and how many revolutions to wait (a resonance n:k);
  * pay the apoapsis burn that makes n of our revolutions equal k of the moon's, which is what
    brings the moon back to our crossing point -- exactly, from vis-viva;
  * arrive, and choose the B-plane aim angle, which rotates v-infinity by the turn angle and
    hands back a new orbit.

The flyby itself is analytic (rotate v-infinity about the B-plane normal), which is why this is
fast enough to search. That model is only trustworthy away from the escape boundary and only if
the moon's state is taken at the FLYBY PERIAPSIS -- taking it an hour early once moved a predicted
apoapsis by 15 Gm. So the search proposes, and `verify` re-flies the winning itinerary through the
patched-conic shooter before anyone burns anything.

A RESONANT WAIT ONLY REPEATS AN ENCOUNTER YOU HAVE ALREADY HAD. It preserves the current
configuration, good or bad; it cannot invent a first encounter with a new moon. Handoffs to a new
moon therefore only appear here when the geometry already allows them, which is the honest answer
and the one greedy search hid.

    python tour_plan.py --vessel-id <guid> --targets Io Europa --depth 6
"""
import argparse
import math
import sys

import numpy as np

import astro
import bridge as bridge_mod
import patched
import tour
from rss_ephem import DAY, System, fmt_ut

G0 = 9.80665
NOMINAL_TRIM = 25.0          # m/s charged per flyby for the approach trim that sets the aim


def unit(x):
    x = np.asarray(x, float)
    return x / np.linalg.norm(x)


class Node:
    __slots__ = ("r", "v", "ut", "dv", "hist", "parent", "at_moon")

    def __init__(self, r, v, ut, dv, hist, parent=None, at_moon=None):
        self.at_moon = at_moon
        self.r = np.asarray(r, float)
        self.v = np.asarray(v, float)
        self.ut = ut
        self.dv = dv
        self.hist = hist
        self.parent = parent


def plane_error(system, moon_name, r, v, ut):
    return tour.rel_inc(system, moon_name, r, v, ut)


def crossing_vinf(system, body, moon, r, v):
    """True 3-D v-infinity if we met `moon` where this orbit crosses its radius.

    Uses the real moon velocity, so the out-of-plane component is included. Reporting the
    coplanar version instead understates it badly: on Bus A at 13 degrees it read 2,134 m/s
    against a true 3,312.
    """
    el = astro.elements(body.mu, r, v)
    if not (el.peR <= moon.a <= el.apR):
        return None
    vs = math.sqrt(body.mu * (2 / moon.a - 1 / el.sma))
    p = el.peR * el.apR * 2 / (el.peR + el.apR)
    h = math.sqrt(body.mu * p)
    cosg = max(-1.0, min(1.0, h / (moon.a * vs)))
    vm = math.sqrt(body.mu / moon.a)
    v_inplane = math.sqrt(vs ** 2 + vm ** 2 - 2 * vs * vm * cosg)
    irel = math.radians(plane_error(system, moon.name, r, v, 0.0))
    cross = 2 * vs * math.sin(irel / 2)
    return math.hypot(v_inplane, cross)


def landing_burn(moon, vinf):
    vesc = math.sqrt(2 * moon.mu / moon.radius)
    return math.hypot(vinf, vesc) * 1.05


def radius_crossings(mu, r, v, ut, R, horizon):
    """Every time this conic passes through radius R, exactly, over `horizon` seconds.

    Crossings are analytic: r = R fixes the true anomaly to +/-nu, and Kepler gives the time
    from periapsis. Scanning time numerically instead is how an encounter gets missed between
    two samples.
    """
    el = astro.elements(mu, r, v)
    if el.ecc >= 1 or not (el.peR <= R <= el.apR):
        return []
    p_ = el.sma * (1 - el.ecc ** 2)
    c = max(-1.0, min(1.0, (p_ / R - 1.0) / el.ecc))
    nu = math.acos(c)
    n = math.sqrt(mu / el.sma ** 3)
    out = []
    for sign in (-1.0, 1.0):
        E = 2 * math.atan2(math.sqrt(1 - el.ecc) * math.sin(sign * nu / 2),
                           math.sqrt(1 + el.ecc) * math.cos(sign * nu / 2))
        dt = (E - el.ecc * math.sin(E)) / n
        t0 = ut - el.mna / n + dt                       # this revolution's crossing
        j = 0
        while True:
            t = t0 + j * el.period
            if t > ut + horizon:
                break
            if t >= ut + 60.0:
                out.append(t)
            j += 1
            if j > 400:
                break
    return sorted(out)


def phasing_options(system, body, r, v, ut, moon_name, horizon, dv_grid):
    """Apoapsis burns that put the moon at one of our radius crossings.

    Scans a grid of burn magnitudes rather than only exact resonances: a resonance is simply
    the dv that happens to work, and searching the grid finds the near-misses too.
    """
    moon = system.body(moon_name)
    el = astro.elements(body.mu, r, v)
    if el.ecc >= 1:
        return []
    n0 = math.sqrt(body.mu / el.sma ** 3)
    t_apo = ut - el.mna / n0 + el.period / 2
    while t_apo < ut + 60.0:
        t_apo += el.period
    r_a, v_a = astro.propagate(body.mu, r, v, t_apo - ut)
    r_a = np.asarray(r_a, float)
    v_a = np.asarray(v_a, float)
    va = float(np.linalg.norm(v_a))
    found = []
    for dv in dv_grid:
        v_new = v_a * (1.0 + dv / va)
        el2 = astro.elements(body.mu, r_a, v_new)
        if el2.ecc >= 1 or el2.apR >= body.soi or not (el2.peR <= moon.a <= el2.apR):
            continue
        for t in radius_crossings(body.mu, r_a, v_new, t_apo, moon.a, horizon):
            rr, vv = astro.propagate(body.mu, r_a, v_new, t - t_apo)
            rm, _ = (np.asarray(x, float) for x in system.rel(moon_name, t))
            miss = float(np.linalg.norm(np.asarray(rr, float) - rm))
            if miss <= moon.soi:
                found.append({"dv": abs(dv), "t_burn": t_apo, "t_enc": t, "miss": miss,
                              "r_e": np.asarray(rr, float), "v_e": np.asarray(vv, float),
                              "wait": t - ut})
                break                                    # first reachable crossing per dv
    found.sort(key=lambda d: (d["dv"], d["wait"]))
    return found[:6]


def flyby(system, body, moon, r, v, ut, psi_deg, alt_m):
    """Analytic flyby: rotate v-infinity by the turn angle about the B-plane aim direction.

    The moon state is taken at `ut`, which the caller must set to the flyby periapsis.
    """
    rm, vm = (np.asarray(x, float) for x in system.rel(moon.name, ut))
    v_inf_vec = np.asarray(v, float) - vm
    vinf = float(np.linalg.norm(v_inf_vec))
    if vinf < 1.0:
        return None
    rp = moon.radius + alt_m
    turn = astro.turn_angle(moon.mu, vinf, rp)
    s_hat = unit(v_inf_vec)
    k_hat = np.array([0.0, 0.0, 1.0])
    t_hat = unit(np.cross(s_hat, k_hat))
    r_hat = np.cross(s_hat, t_hat)
    b_hat = math.cos(math.radians(psi_deg)) * t_hat + math.sin(math.radians(psi_deg)) * r_hat
    v_out = vinf * (math.cos(turn) * s_hat - math.sin(turn) * b_hat)
    return rm, vm + v_out, vinf, math.degrees(turn)


def expand(system, body, node, moons, angles, alt_m, horizon, dv_grid):
    """Every (moon, resonance, aim) this node can reach, as child nodes.

    A node sitting AT an encounter has no resonance to choose yet -- the only decision is the
    aim angle, and the phasing question belongs to the step after it.
    """
    kids = []
    if node.at_moon:
        moon = system.body(node.at_moon)
        for psi in angles:
            out = flyby(system, body, moon, node.r, node.v, node.ut, psi, alt_m)
            if out is None:
                continue
            _rm, v_new, vinf, turn = out
            el = astro.elements(body.mu, node.r, v_new)
            if el.ecc >= 1 or el.apR >= body.soi:
                continue
            kids.append(Node(node.r, v_new, node.ut, node.dv + NOMINAL_TRIM,
                             node.hist + [{"moon": node.at_moon, "ut": node.ut, "psi": psi,
                                           "vinf": vinf, "turn": turn, "n": 0, "k": 0,
                                           "phase_dv": 0.0, "wait_d": 0.0}], node))
        return kids
    for mname in moons:
        moon = system.body(mname)
        for opt in phasing_options(system, body, node.r, node.v, node.ut, mname,
                                   horizon, dv_grid):
            for psi in angles:
                out = flyby(system, body, moon, opt["r_e"], opt["v_e"], opt["t_enc"], psi, alt_m)
                if out is None:
                    continue
                _rm, v_new, vinf, turn = out
                el = astro.elements(body.mu, opt["r_e"], v_new)
                if el.ecc >= 1 or el.apR >= body.soi:
                    continue
                kids.append(Node(opt["r_e"], v_new, opt["t_enc"],
                                 node.dv + opt["dv"] + NOMINAL_TRIM,
                                 node.hist + [{"moon": mname, "ut": opt["t_enc"], "psi": psi,
                                               "vinf": vinf, "turn": turn, "n": 0, "k": 0,
                                               "phase_dv": opt["dv"],
                                               "wait_d": opt["wait"] / DAY}], node))
    return kids


def score(system, body, node, targets, weights):
    """Lower is better. Tracks BOTH currencies plus the thing the tour is actually for."""
    s = weights["dv"] * node.dv + weights["time"] * (node.hist[-1]["ut"] - node.hist[0]["ut"]) / DAY
    for t in targets:
        moon = system.body(t)
        vinf = crossing_vinf(system, body, moon, node.r, node.v)
        if vinf is None:
            s += weights["unreachable"]
            continue
        need = landing_burn(moon, vinf)
        s += weights["landing"] * max(0.0, need - targets[t])
        irel = plane_error(system, t, node.r, node.v, node.ut)
        cross = moon.a * math.sin(math.radians(irel))
        if cross > moon.soi:
            s += weights["plane"] * (cross / moon.soi)
    return s


def search(system, body, start, moons, targets, depth, beam, angles, alt_m, horizon, dv_grid, weights):
    frontier = [start]
    best_done = []
    for d in range(depth):
        kids = []
        for nd in frontier:
            kids.extend(expand(system, body, nd, moons, angles, alt_m, horizon, dv_grid))
        if not kids:
            break
        kids.sort(key=lambda n: score(system, body, n, targets, weights))
        frontier = kids[:beam]
        for nd in frontier:
            if all(closes(system, body, nd, t, targets[t]) for t in targets):
                best_done.append(nd)
        print(f"  depth {d + 1}: {len(kids):5d} branches, keeping {len(frontier)}, "
              f"best score {score(system, body, frontier[0], targets, weights):,.0f}, "
              f"{len(best_done)} complete")
    return frontier, best_done


def closes(system, body, node, moon_name, lander_dv):
    moon = system.body(moon_name)
    vinf = crossing_vinf(system, body, moon, node.r, node.v)
    if vinf is None:
        return False
    if landing_burn(moon, vinf) > lander_dv:
        return False
    cross = moon.a * math.sin(math.radians(plane_error(system, moon_name, node.r, node.v, node.ut)))
    return cross <= moon.soi


def report(system, body, node, targets):
    print(f"    total dv {node.dv:,.0f} m/s over {len(node.hist)} flybys, "
          f"{(node.hist[-1]['ut'] - node.hist[0]['ut']) / DAY:,.0f} days")
    for h in node.hist:
        print(f"      {h['moon']:9s} {fmt_ut(h['ut'])[:16]}  psi {h['psi']:5.0f}  "
              f"v_inf {h['vinf']:6,.0f}  turn {h['turn']:5.1f}  "
              f"{h['n']}:{h['k']} wait {h['wait_d']:6.1f} d  phasing {h['phase_dv']:6.1f} m/s")
    el = astro.elements(body.mu, node.r, node.v)
    print(f"      end orbit {el.peR / 1e6:,.0f} x {el.apR / 1e6:,.0f} Mm")
    for t, lander in targets.items():
        moon = system.body(t)
        vinf = crossing_vinf(system, body, moon, node.r, node.v)
        irel = plane_error(system, t, node.r, node.v, node.ut)
        cross = moon.a * math.sin(math.radians(irel))
        if vinf is None:
            print(f"      {t:9s} NOT CROSSED")
            continue
        need = landing_burn(moon, vinf)
        print(f"      {t:9s} v_inf {vinf:6,.0f}  landing {need:6,.0f} vs lander {lander:,.0f} "
              f"{'OK' if need <= lander else 'SHORT'}   plane {irel:5.2f} deg = "
              f"{cross / 1e3:8,.0f} km cross-track vs SOI {moon.soi / 1e3:,.0f} "
              f"{'reachable' if cross <= moon.soi else 'NODE ONLY'}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vessel-id", required=True)
    ap.add_argument("--body", default="Jupiter")
    ap.add_argument("--moons", nargs="+", default=["Io", "Europa", "Ganymede", "Callisto"])
    ap.add_argument("--targets", nargs="+", required=True,
                    help="moons to land on, as NAME=lander_dv (e.g. Io=3771 Europa=3268)")
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--beam", type=int, default=40)
    ap.add_argument("--angles", type=int, default=24)
    ap.add_argument("--alt", type=float, default=300.0, help="flyby altitude, km")
    ap.add_argument("--dv-step", type=float, default=4.0, help="phasing-burn grid step, m/s")
    ap.add_argument("--horizon", type=float, default=400.0, help="days to look ahead for a crossing")
    ap.add_argument("--dv-cap", type=float, default=200.0, help="m/s cap on one phasing burn")
    ap.add_argument("--port", type=int, default=8284)
    ap.add_argument("--show", type=int, default=3)
    args = ap.parse_args(argv)

    system = System()
    body = system.body(args.body)
    targets = {}
    for t in args.targets:
        name, _, dv = t.partition("=")
        targets[name] = float(dv)
    br = bridge_mod.Bridge(port=args.port)
    b, r, v, ut = br.state(system, vid=args.vessel_id)
    if b.name != body.name:
        # Mid-flyby is a perfectly normal moment to ask; fly out to the parent and plan from there.
        tr0 = patched.shoot(system, b.name, np.asarray(r, float), np.asarray(v, float), ut,
                            ut + 30 * DAY, watch=[body.name])
        out = next((p for p in tr0.patches if p.body.name == body.name), None)
        if out is None:
            sys.exit(f"vessel is in {b.name}'s SOI and does not leave it within 30 days")
        print(f"  (in {b.name}'s SOI; propagated out to {fmt_ut(out.ut0)})")
        r, v, ut = np.asarray(out.r0, float), np.asarray(out.v0, float), out.ut0
    r = np.asarray(r, float)
    v = np.asarray(v, float)
    el = astro.elements(body.mu, r, v)
    print(f"TOUR PLAN from {fmt_ut(ut)}   {el.peR / 1e6:,.0f} x {el.apR / 1e6:,.0f} Mm, "
          f"period {tour.dhms(el.period)}")
    # If an encounter is already pending, the search must START there: the first decision is its
    # aim, not a phasing burn, and a resonance from mid-coast can never produce an encounter.
    at_moon = None
    tr = patched.shoot(system, body.name, r, v, ut, ut + 400 * DAY, watch=list(args.moons))
    pend = next((p for p in tr.patches if p.body.name in args.moons), None)
    if pend is not None:
        rm, vm = (np.asarray(x, float) for x in system.rel(pend.body.name, pend.ut0))
        r, v, ut, at_moon = np.asarray(pend.r0, float) + rm, np.asarray(pend.v0, float) + vm, pend.ut0, pend.body.name
        bp = astro.bplane(pend.body.mu, pend.r0, pend.v0)
        print(f"  pending encounter: {at_moon} {fmt_ut(ut)} at "
              f"{(bp['peR'] - pend.body.radius) / 1e3:,.0f} km, v_inf {bp['vinf']:,.0f} m/s "
              f"-- search starts there, its AIM is the first decision")
    for t, lander in targets.items():
        moon = system.body(t)
        vinf = crossing_vinf(system, body, moon, np.asarray(r, float), np.asarray(v, float))
        print(f"  target {t}: lander {lander:,.0f} m/s, "
              + (f"v_inf now {vinf:,.0f} -> landing {landing_burn(moon, vinf):,.0f}"
                 if vinf else "orbit does not cross it"))
    angles = [a * 360.0 / args.angles for a in range(args.angles)]
    weights = {"dv": 1.0, "time": 0.5, "landing": 4.0, "plane": 60.0, "unreachable": 5000.0}
    start = Node(r, v, ut, 0.0, [{"moon": "start", "ut": ut, "psi": 0, "vinf": 0,
                                  "turn": 0, "n": 0, "k": 0, "phase_dv": 0, "wait_d": 0}],
                 at_moon=at_moon)
    print("\nSEARCH")
    dv_grid = list(np.arange(-args.dv_cap, args.dv_cap + 1e-9, args.dv_step))
    frontier, done = search(system, body, start, args.moons, targets, args.depth, args.beam,
                            angles, args.alt * 1e3, args.horizon * DAY, dv_grid, weights)
    pool = done or frontier
    pool.sort(key=lambda n: score(system, body, n, targets, weights))
    label = "COMPLETE ITINERARIES" if done else "BEST PARTIAL (no complete tour found)"
    print(f"\n{label}")
    for nd in pool[:args.show]:
        print()
        report(system, body, nd, targets)
    if not done:
        print("\n  No sequence reaches every target. Read the SHORT / NODE ONLY flags above:")
        print("  SHORT means the lander cannot afford the arrival; NODE ONLY means the plane")
        print("  error puts the moon out of reach except near a node. They need different fixes.")


if __name__ == "__main__":
    main()
