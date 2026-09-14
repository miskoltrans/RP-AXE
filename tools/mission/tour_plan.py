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
import sfs as sfs_mod
import maneuver
import patched
import tour
from rss_ephem import DAY, System, fmt_ut

G0 = 9.80665
NOMINAL_TRIM = 25.0          # m/s placeholder, replaced by the real solve in price_aims
MIN_FLYBY_ALT = 50e3         # never plan a pass below this; the solver does not check the ground
AIM_TOL = 0.06               # a solve that misses the requested periapsis by more than this is
                             # NOT the flyby that was asked for, and must not enter the plan


def unit(x):
    x = np.asarray(x, float)
    return x / np.linalg.norm(x)


class Node:
    __slots__ = ("r", "v", "ut", "dv", "hist", "parent", "at_moon", "pending", "priced",
                 "trim_from")

    def __init__(self, r, v, ut, dv, hist, parent=None, at_moon=None, pending=None):
        self.at_moon = at_moon
        self.pending = pending
        self.priced = False
        self.trim_from = None       # (r, v, ut) the vessel is really at, for the first aim
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
    v_rel = math.hypot(v_inplane, cross)
    # ...but the relative speed at the moon's orbit radius is NOT the hyperbolic excess a
    # landing burn is priced on. The encounter happens at the edge of a real SOI, so the well
    # from r_soi outward is already spent: v_inf^2 = v_rel^2 - 2*mu/r_soi. At the inner moons
    # that term is large -- at Io it is 1.52e6 m^2/s^2. Measured on Perun 2 Bus B's 421 x 734 Mm
    # orbit: this returned 2,276 m/s and priced the landing at 3,601 against a 3,778 m/s lander,
    # a "SHORT by 177" verdict on the flown encounter that actually arrives at 1,897 and lands
    # for 3,350 with 428 m/s spare. Reporting the pre-SOI speed cancels missions that close.
    excess = v_rel * v_rel - 2 * moon.mu / moon.soi
    return math.sqrt(excess) if excess > 0 else 0.0


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
                found.append({"dv": abs(dv), "dv_signed": dv, "t_burn": t_apo,
                              "t_enc": t, "miss": miss,
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
                                           "phase_dv": 0.0, "wait_d": 0.0}], node,
                             pending=({"r": node.trim_from[0], "v": node.trim_from[1],
                                       "t": node.trim_from[2] + 3600.0, "moon": node.at_moon,
                                       "psi": psi, "t_enc": node.ut}
                                      if node.trim_from else None)))
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
                                               "dv_signed": opt["dv_signed"],
                                               "t_burn": opt["t_burn"],
                                               "wait_d": opt["wait"] / DAY}], node,
                                 pending={"r": node.r, "v": node.v, "t": opt["t_burn"],
                                          "moon": mname, "psi": psi, "t_enc": opt["t_enc"]}))
    return kids


def price_aims(system, body, nodes, alt_m, max_dv=300.0):
    """Swap the assumed trim for the burn that ACTUALLY achieves each aim, and carry the FLOWN
    post-flyby state forward.

    The flat NOMINAL_TRIM is what made these plans fiction. On Perun 2 Bus A the aim the plan
    wanted at Callisto really cost 425 m/s -- seventeen times the assumption and more than the
    whole itinerary it appeared in -- because what it demanded was a plane rotation, not a
    periapsis change. Pricing only the surviving beam keeps it affordable: one shooter solve per
    beam member per depth, not one per branch. It also makes the plan EXACT, since every kept
    node now sits on a trajectory the shooter flew rather than on the point-mass approximation
    that made the first Bus A itinerary fail verification at leg one.
    """
    out = []
    for nd in nodes:
        if nd.priced or not nd.pending:
            out.append(nd)
            continue
        q = nd.pending
        moon = system.body(q["moon"])
        bd = np.array([math.cos(math.radians(q["psi"])), math.sin(math.radians(q["psi"]))])
        try:
            res = maneuver.refine(system, body.name, np.asarray(q["r"], float),
                                  np.asarray(q["v"], float), q["t"], moon.name,
                                  q["t_enc"] + 300 * DAY, moon.radius + alt_m, b_dir=bd,
                                  watch=[moon.name], max_dv=max_dv, max_nfev=90)
        except (ValueError, RuntimeError, ArithmeticError):
            # Only numerical failures are expected here. A bare `except Exception` hid a
            # NameError (maneuver was never imported at module level) behind "no candidate
            # converged" for an hour -- every branch died silently and the search looked broken.
            continue
        rp = res["report"]
        if not rp.get("captured"):
            continue
        # THE CHECK THAT EVERYTHING ELSE DEPENDED ON. `refine` does not fail when it cannot
        # reach the requested aim within max_dv -- it returns its best effort, which has been
        # measured at a 14,473 km graze and at a periapsis 1,312 km BELOW Ganymede's surface.
        # Accepting those put flybys into the plan that bear no relation to the pass that was
        # asked for, and every number downstream -- bending, arrival speed, plane, the delta-v
        # it would buy -- described the request rather than the result. A branch may only
        # survive if its aim is genuinely reachable.
        want = moon.radius + alt_m
        if rp["peR"] < moon.radius + MIN_FLYBY_ALT:
            continue
        if abs(rp["peR"] - want) / want > AIM_TOL:
            continue
        traj = res["traj"]
        p_in = traj.enters(moon.name)
        post = [x for x in traj.patches if x.body.name == body.name and x.ut0 > p_in.ut0]
        if not post:
            continue
        el = astro.elements(body.mu, post[0].r0, post[0].v0)
        if el.ecc >= 1 or el.apR >= body.soi:
            continue
        true_dv = float(np.linalg.norm(res["dv"]))
        nd.dv = nd.dv - NOMINAL_TRIM + true_dv
        nd.r = np.asarray(post[0].r0, float)
        nd.v = np.asarray(post[0].v0, float)
        nd.ut = post[0].ut0
        nd.hist[-1]["vinf"] = rp["vinf"]
        nd.hist[-1]["aim_dv"] = true_dv
        nd.hist[-1]["ut"] = rp["soi_ut"]
        nd.hist[-1]["alt"] = (rp["peR"] - moon.radius) / 1e3
        nd.priced, nd.pending = True, None
        out.append(nd)
    return out


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
        priced = price_aims(system, body, kids[:beam * 2], alt_m)
        if not priced:
            # Nothing at this depth had a reachable aim. That is an answer, not a crash: keep the
            # deepest frontier that did survive and report it.
            print(f"  depth {d + 1}: {len(kids):5d} branches, none with a reachable aim -- "
                  f"stopping at depth {d}")
            break
        priced.sort(key=lambda n: score(system, body, n, targets, weights))
        frontier = priced[:beam]
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


def status(system, body, r, v, ut, targets, moons, horizon_d=400.0):
    """The three numbers that decide the mission, for a state you can hand it after any burn.

    This exists because nothing was checking them. Every burn on Bus A passed its own local
    test -- a resonance ratio, an arrival speed, a pump-down -- while the plane error went
    0.07 -> 8.56 -> 13.26 degrees and took the Callisto handoff with it. Printing a period
    ratio looked excellent at the exact moment the tour was being lost. Run this after EVERY
    burn and paste it whether or not it looks good; that is the whole point.
    """
    r = np.asarray(r, float)
    v = np.asarray(v, float)
    el = astro.elements(body.mu, r, v)
    print(f"STATUS {fmt_ut(ut)}   {el.peR / 1e6:,.0f} x {el.apR / 1e6:,.0f} Mm  "
          f"period {tour.dhms(el.period)}")
    worst = "OK"
    for t, lander in targets.items():
        moon = system.body(t)
        vinf = crossing_vinf(system, body, moon, r, v)
        irel = plane_error(system, t, r, v, ut)
        cross = moon.a * math.sin(math.radians(irel))
        if vinf is None:
            print(f"  {t:9s} orbit does not cross it        plane {irel:5.2f} deg")
            worst = "BLOCKED"
            continue
        need = landing_burn(moon, vinf)
        flag = "OK" if need <= lander else f"SHORT by {need - lander:,.0f}"
        if need > lander and worst == "OK":
            worst = "SHORT"
        print(f"  {t:9s} v_inf {vinf:6,.0f}  landing {need:6,.0f} vs lander {lander:,.0f}  {flag:<16s}"
              f" plane {irel:5.2f} deg = {cross / 1e3:8,.0f} km cross-track vs SOI "
              f"{moon.soi / 1e3:,.0f} {'any longitude' if cross <= moon.soi else 'near a node'}")
    # Look ahead in REVOLUTIONS, not in a fixed number of days. A fixed 400-day window is
    # nothing on a 24-day orbit whose encounters recur on a ten-month synodic beat: it reported
    # "no encounter, a phasing burn is owed" for a Bus A that had a free Ganymede pass waiting
    # 414 days out, and the phasing burn it asked for was not owed at all.
    el0 = astro.elements(body.mu, r, v)
    look = max(horizon_d * DAY, 40 * el0.period) if el0.ecc < 1 else horizon_d * DAY
    tr = patched.shoot(system, body.name, r, v, ut, ut + look, watch=list(moons))
    hits = [p for p in tr.patches if p.body.name in moons]
    if hits:
        for p in hits[:3]:
            bp = astro.bplane(p.body.mu, p.r0, p.v0)
            print(f"  next: {p.body.name} {fmt_ut(p.ut0)} at "
                  f"{(bp['peR'] - p.body.radius) / 1e3:,.0f} km, v_inf {bp['vinf']:,.0f} m/s"
                  f"  (T+{(p.ut0 - ut) / DAY:,.0f} d)")
    else:
        print(f"  next: no encounter in the next {look / DAY:,.0f} days "
              f"({look / el0.period:,.0f} revolutions) -- a phasing burn is owed")
    print(f"  verdict: {worst}")
    return worst


def verify(system, body, root_r, root_v, root_ut, node, alt_m, moons):
    """Re-fly the itinerary through the patched-conic shooter, leg by leg.

    The search flies analytic flybys, which is what makes it fast and also what makes it
    untrustworthy on its own -- that model already moved a predicted apoapsis by 15 Gm once.
    So every leg is replayed here: the phasing burn is applied at its apoapsis, the arc is
    shot with the moon's SOI watched, and the aim is solved with `maneuver.refine` against the
    real geometry. What comes out is measured, not modelled.
    """
    import maneuver
    r = np.asarray(root_r, float)
    v = np.asarray(root_v, float)
    ut = root_ut
    legs = [h for h in node.hist if h["moon"] != "start"]
    total = 0.0
    print(f"  {'leg':>3s} {'moon':9s} {'planned':16s} {'flown':16s} {'alt km':>8s} "
          f"{'v_inf':>7s} {'plan v_inf':>10s} {'dV':>8s}")
    for i, h in enumerate(legs):
        moon = system.body(h["moon"])
        if h.get("t_burn"):
            el = astro.elements(body.mu, r, v)
            if el.ecc >= 1:
                print(f"  {i + 1:3d}  hyperbolic before the burn -- chain broken")
                return False
            rb, vb = astro.propagate(body.mu, r, v, h["t_burn"] - ut)
            rb = np.asarray(rb, float)
            vb = np.asarray(vb, float)
            vb = vb * (1.0 + h["dv_signed"] / float(np.linalg.norm(vb)))
            r, v, ut = rb, vb, h["t_burn"]
            total += abs(h["dv_signed"])
        t_end = h["ut"] + 400 * DAY
        try:
            res = maneuver.refine(system, body.name, r, v, ut, moon.name, t_end,
                                  moon.radius + alt_m, b_dir=np.array(
                                      [math.cos(math.radians(h["psi"])),
                                       math.sin(math.radians(h["psi"]))]),
                                  watch=[moon.name], max_dv=120.0, max_nfev=120)
        except Exception as exc:                                    # noqa: BLE001
            print(f"  {i + 1:3d} {moon.name:9s} {fmt_ut(h['ut'])[:16]:16s} aim solve failed: {exc}")
            return False
        rep = res["report"]
        if not rep.get("captured"):
            print(f"  {i + 1:3d} {moon.name:9s} {fmt_ut(h['ut'])[:16]:16s} NO ENCOUNTER "
                  f"(miss {rep.get('ca_dist', 0) / 1e6:,.1f} Mm)")
            return False
        trim = float(np.linalg.norm(res["dv"]))
        total += trim
        tr = res["traj"]
        p_in = tr.enters(moon.name)
        post = [q for q in tr.patches if q.body.name == body.name and q.ut0 > p_in.ut0]
        if not post:
            print(f"  {i + 1:3d} {moon.name:9s} left {body.name} after the flyby -- chain broken")
            return False
        r = np.asarray(post[0].r0, float)
        v = np.asarray(post[0].v0, float)
        ut = post[0].ut0
        print(f"  {i + 1:3d} {moon.name:9s} {fmt_ut(h['ut'])[:16]:16s} {fmt_ut(rep['soi_ut'])[:16]:16s} "
              f"{(rep['peR'] - moon.radius) / 1e3:8,.0f} {rep['vinf']:7,.0f} {h['vinf']:10,.0f} "
              f"{trim + abs(h.get('dv_signed', 0.0)):7,.1f}")
    el = astro.elements(body.mu, r, v)
    print(f"  FLOWN end orbit {el.peR / 1e6:,.0f} x {el.apR / 1e6:,.0f} Mm, total {total:,.0f} m/s "
          f"(search said {node.dv:,.0f})")
    return True


def report(system, body, node, targets):
    print(f"    total dv {node.dv:,.0f} m/s over {len(node.hist)} flybys, "
          f"{(node.hist[-1]['ut'] - node.hist[0]['ut']) / DAY:,.0f} days")
    for h in node.hist:
        print(f"      {h['moon']:9s} {fmt_ut(h['ut'])[:16]}  psi {h['psi']:5.0f}  "
              f"v_inf {h['vinf']:6,.0f}  turn {h['turn']:5.1f}  "
              f"alt {h.get('alt', -1):7,.0f} km  phasing {h['phase_dv']:6.1f}  "
              f"aim {h.get('aim_dv', -1):7.1f} m/s")
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


def origin(system, args):
    """Where the tour starts: the running game, or the save when KSP is not up.

    A tour is solved on rails and the vessel is not being flown while it is solved, so the
    save is a perfectly good source -- and refusing to plan because KSP happens to be closed
    is the tool failing for a reason that has nothing to do with the mission.
    """
    if not args.save:
        try:
            return bridge_mod.Bridge(port=args.port).state(system, vid=args.vessel_id,
                                                           name=args.vessel)
        except bridge_mod.BridgeError:
            print("  [the AXE bridge is not answering -- planning from the save instead]")
    save = sfs_mod.Save(sfs_mod.find_save(args.save), system)
    key = (args.vessel_id or "").replace("-", "").lower()
    ves = None
    if key:
        for w in save.vessels:
            if (w.node.get("pid") or "").replace("-", "").lower() == key:
                ves = w
                break
    if ves is None:
        if not args.vessel:
            raise SystemExit("  no vessel: give --vessel-id matching the save, or --vessel NAME")
        ves = save.vessel(args.vessel)
    r, v = ves.state(save.ut)
    print(f"  [save {save.path}: {ves.name} at {fmt_ut(save.ut)}]")
    return ves.body, np.asarray(r, float), np.asarray(v, float), save.ut


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vessel-id")
    ap.add_argument("--vessel", help="vessel name, when there is no id (save lookup only)")
    ap.add_argument("--save", help="plan from this save instead of the running game")
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
    ap.add_argument("--status", action="store_true",
                    help="skip the search: just print the numbers that decide the mission")
    ap.add_argument("--verify", action="store_true",
                    help="re-fly the best itinerary through the patched-conic shooter")
    args = ap.parse_args(argv)

    system = System()
    body = system.body(args.body)
    targets = {}
    for t in args.targets:
        name, _, dv = t.partition("=")
        targets[name] = float(dv)
    b, r, v, ut = origin(system, args)
    if args.status:
        # Report where the vessel IS. The pending-encounter hop below rewrites r/v/ut
        # to the future encounter, which is the right start for a SEARCH and exactly
        # the wrong thing to call "status" -- it showed the pre-flyby plane error as
        # though the burn had not helped.
        rr, vv, uu = np.asarray(r, float), np.asarray(v, float), ut
        if b.name != body.name:
            t0 = patched.shoot(system, b.name, rr, vv, uu, uu + 30 * DAY, watch=[body.name])
            o = next((q for q in t0.patches if q.body.name == body.name), None)
            if o is not None:
                rr, vv, uu = np.asarray(o.r0, float), np.asarray(o.v0, float), o.ut0
        status(system, body, rr, vv, uu, targets, args.moons, args.horizon)
        return
    if b.name != body.name:
        # Mid-flyby is a perfectly normal moment to ask; fly out to the parent and plan from there.
        tr0 = patched.shoot(system, b.name, np.asarray(r, float), np.asarray(v, float), ut,
                            ut + 30 * DAY, watch=[body.name])
        out = next((p for p in tr0.patches if p.body.name == body.name), None)
        if out is None:
            sys.exit(f"vessel is in {b.name}'s SOI and does not leave it within 30 days")
        print(f"  (in {b.name}'s SOI; propagated out to {fmt_ut(out.ut0)})")
        r, v, ut = np.asarray(out.r0, float), np.asarray(out.v0, float), out.ut0
    r0_real, v0_real, ut0_real = np.asarray(r, float), np.asarray(v, float), ut
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
    start.trim_from = (np.asarray(r0_real, float), np.asarray(v0_real, float), ut0_real)
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
    if args.verify and pool:
        print("")
        print("VERIFY (patched-conic shooter, aims solved against the real geometry)")
        ok = verify(system, body, r, v, ut, pool[0], args.alt * 1e3, args.moons)
        print("  -> itinerary VERIFIED" if ok else "  -> itinerary DID NOT survive the shooter")
    if not done:
        print("\n  No sequence reaches every target. Read the SHORT / NODE ONLY flags above:")
        print("  SHORT means the lander cannot afford the arrival; NODE ONLY means the plane")
        print("  error puts the moon out of reach except near a node. They need different fixes.")


if __name__ == "__main__":
    main()
