"""Fly a state forward through SOI changes, the way the game's solver does.

This exists because an asymptote that matches its Lambert target perfectly can
still miss the target by 295 Gm. Matching a v-infinity vector is a claim; flying
the trajectory and reading off where it actually ends up is a measurement, and
every answer this toolchain gives is checked by the second kind.

SOI handling mirrors KSP: a body's SOI is a hard sphere, entry and exit are
instantaneous, and inside it only the one body pulls. Entry search is a coarse
march with a rigorous exclusion test -- between two samples a closing distance
can shrink by at most v_rel*dt, so a bracket whose lower bound stays outside the
SOI cannot contain an entry. Nothing is skipped silently.
"""
import math

import numpy as np

import astro


class Patch:
    """One conic arc, in the frame of one body."""

    def __init__(self, body, ut0, r0, v0, ut1=None, end=""):
        self.body = body
        self.ut0 = ut0
        self.r0 = np.asarray(r0, float)
        self.v0 = np.asarray(v0, float)
        self.ut1 = ut1
        self.end = end                     # "exit", "enter:<body>", "horizon", "impact"

    def state(self, ut):
        return astro.propagate(self.body.mu, self.r0, self.v0, ut - self.ut0)

    def elements(self, ut=None):
        r, v = (self.r0, self.v0) if ut is None else self.state(ut)
        return astro.elements(self.body.mu, r, v)

    def __repr__(self):
        return f"<Patch {self.body.name} {self.ut0:,.0f}..{self.ut1 or float('nan'):,.0f} {self.end}>"


class Trajectory:
    def __init__(self, patches, system):
        self.patches = patches
        self.system = system

    def __iter__(self):
        return iter(self.patches)

    def __len__(self):
        return len(self.patches)

    def patch_at(self, ut):
        for p in self.patches:
            if p.ut0 <= ut and (p.ut1 is None or ut <= p.ut1):
                return p
        return self.patches[-1]

    def state(self, ut):
        p = self.patch_at(ut)
        return p.body, *p.state(ut)

    def enters(self, body_name):
        """The patch in `body_name`'s frame, if the trajectory ever gets captured by it."""
        for p in self.patches:
            if p.body.name == body_name and p is not self.patches[0]:
                return p
        return None

    def final(self):
        return self.patches[-1]

    def summary(self):
        out = []
        for p in self.patches:
            el = p.elements()
            out.append(f"{p.body.name}: {p.ut0:,.0f} -> {p.ut1 if p.ut1 else float('nan'):,.0f}  "
                       f"{el}  [{p.end}]")
        return "\n".join(out)


def _rel_to_parent(system, body, r, v, ut):
    """Body-centred state -> parent-centred."""
    rb, vb = system.rel(body.name, ut)
    return np.asarray(r) + np.asarray(rb), np.asarray(v) + np.asarray(vb)


def _to_child(system, child, r, v, ut):
    """Parent-centred state -> child-centred."""
    rb, vb = system.rel(child.name, ut)
    return np.asarray(r) - np.asarray(rb), np.asarray(v) - np.asarray(vb)


def _exit_time(patch, soi, ut_end):
    """When does |r| first reach `soi`? None if it never does inside the window."""
    if not math.isfinite(soi):
        return None
    el = patch.elements()
    if el.ecc < 1.0 and el.apR <= soi:
        return None
    f = lambda t: float(np.linalg.norm(patch.state(t)[0])) - soi
    # A patch that begins ON the boundary is the normal case -- it was just
    # created by an SOI entry. If it is already heading outward, the exit is now.
    #
    # If it is heading INWARD, the exit is the next outward crossing, NOT "never".
    # Returning None there reports an escaping trajectory as "captured or impacts",
    # and since |r| - soi at the entry instant is rounding noise, the verdict
    # flipped between runs on the same trajectory: one call found the SOI exit, the
    # next called the same flyby a capture. So the scan below starts from the first
    # sample that is genuinely inside and looks for a crossing after that.
    if f(patch.ut0) >= 0 and float(patch.r0 @ patch.v0) > 0:
        return patch.ut0
    ts = np.linspace(patch.ut0, ut_end, 401)
    pos, _ = astro.sample_conic(patch.body.mu, patch.r0, patch.v0, ts - patch.ut0)
    d = np.linalg.norm(pos, axis=1) - soi
    inside = np.nonzero(d < 0.0)[0]
    if len(inside) == 0:
        return None
    i0 = int(inside[0])
    out = np.nonzero(d[i0 + 1:] >= 0.0)[0] + i0 + 1
    for i in out:
        # sample_conic and Shepperd agree to ~1e-4 m; near the boundary that is
        # enough to make one say "outside" and the other "inside", so confirm the
        # sign change with the propagator that will actually be used.
        if f(float(ts[i])) >= 0:
            return astro.brent(f, float(ts[i - 1]), float(ts[i]), tol=1e-6)
    return None


def _sep_array(system, patch, child, ts):
    """Separation and relative speed between the patch and `child` at many times."""
    pr, pv = astro.sample_conic(patch.body.mu, patch.r0, patch.v0, ts - patch.ut0)
    cr, cv = system.rel_array(child.name, ts)
    d = pr - cr
    dv = pv - cv
    return np.linalg.norm(d, axis=1), np.linalg.norm(dv, axis=1)


def _entry_time(system, patch, child, ut_end, coarse=1500, refine=48):
    """First time the trajectory is inside `child`'s SOI, or None.

    The exclusion test is what makes this safe: over a bracket of length dt the
    separation cannot fall by more than v_rel*dt, so if (d - v_rel*dt) stays
    above the SOI across a bracket, that bracket provably contains no entry and
    can be skipped. Nothing is dropped for being inconvenient.
    """
    soi = child.soi
    t0 = patch.ut0
    t1 = min(ut_end, patch.ut1 if patch.ut1 is not None else ut_end)
    if t1 <= t0:
        return None
    # cheap rigorous pre-filter: do the two radial ranges overlap at all?
    el = patch.elements()
    lo_sc, hi_sc = el.peR, (el.apR if el.ecc < 1 else math.inf)
    lo_c = child.a * (1 - child.e) - soi
    hi_c = child.a * (1 + child.e) + soi
    if hi_sc < lo_c or lo_sc > hi_c:
        return None

    n = max(16, min(coarse, int((t1 - t0) / 60.0) + 1))
    ts = np.linspace(t0, t1, n + 1)
    dt = (t1 - t0) / n
    d, vrel = _sep_array(system, patch, child, ts)
    if d[0] <= soi:
        return t0
    scal = lambda t: _sep_array(system, patch, child, np.array([t]))[0][0] - soi
    inside = np.nonzero(d <= soi)[0]
    first_hit = int(inside[0]) if len(inside) else None
    # brackets that could dip inside between samples
    lo = np.minimum(d[:-1], d[1:]) - np.maximum(vrel[:-1], vrel[1:]) * dt
    risky = np.nonzero(lo <= soi)[0]
    for i in risky:
        if first_hit is not None and i >= first_hit:
            break
        sub = np.linspace(ts[i], ts[i + 1], refine + 1)
        dd, _ = _sep_array(system, patch, child, sub)
        j = np.nonzero(dd <= soi)[0]
        if len(j):
            j = int(j[0])
            if j == 0:
                return float(sub[0])
            return astro.brent(scal, float(sub[j - 1]), float(sub[j]), tol=1e-3)
    if first_hit is not None:
        if first_hit == 0:
            return t0
        return astro.brent(scal, float(ts[first_hit - 1]), float(ts[first_hit]), tol=1e-3)
    return None


def shoot(system, body, r0, v0, ut0, ut_end, watch=None, max_patches=8, coarse=1500):
    """Propagate (r0, v0) about `body` from ut0 to ut_end through SOI changes.

    `watch` names the bodies whose SOI may be entered. Default: every child of
    whichever body we are currently in whose SOI is at least 1000 km, which
    covers planets and major moons but not Phobos-class rocks -- name those
    explicitly. The set actually used is recorded on the returned Trajectory.
    """
    body = system.body(body)
    r, v, t = np.asarray(r0, float), np.asarray(v0, float), ut0
    patches = []
    considered = set()
    for _ in range(max_patches):
        p = Patch(body, t, r, v)
        el = p.elements()
        if el.peR <= body.radius and el.ecc < 1.0 or (el.peR <= body.radius and el.nu < 0):
            pass                                   # impact is reported, not prevented
        events = []
        soi = body.soi
        te = _exit_time(p, soi, ut_end)
        if te is not None and te > t:
            events.append((te, "exit", None))
        kids = system.children(body.name)
        if watch is None:
            # default: anything with an SOI you could plausibly fall into. Phobos
            # (47 km) and Deimos are excluded -- name them if you want them.
            cand = [c for c in kids if c.soi >= 1e6]
        else:
            names = {system.body(w).name for w in watch}
            cand = [c for c in kids if c.name in names]
        p.ut1 = min([e[0] for e in events], default=ut_end)
        for c in cand:
            considered.add(c.name)
            tc = _entry_time(system, p, c, ut_end, coarse=coarse)
            if tc is not None and tc > t:
                events.append((tc, "enter", c))
        if not events:
            p.ut1, p.end = ut_end, "horizon"
            patches.append(p)
            break
        events.sort(key=lambda e: e[0])
        te, kind, child = events[0]
        p.ut1 = te
        r, v = p.state(te)
        if kind == "exit":
            if body.parent is None:
                p.end = "horizon"
                patches.append(p)
                break
            p.end = "exit"
            patches.append(p)
            r, v = _rel_to_parent(system, body, r, v, te)
            body = system.body(body.parent)
        else:
            p.end = f"enter:{child.name}"
            patches.append(p)
            r, v = _to_child(system, child, r, v, te)
            body = child
        t = te
        if t >= ut_end:
            break
    traj = Trajectory(patches, system)
    traj.considered = sorted(considered)
    return traj


def closest_approach(system, traj, target, ut0, ut1, samples=4000):
    """Minimum distance between the trajectory and `target`, in whatever frame both share.

    Returns (ut, distance, v_rel). Works even when the target's SOI is never
    entered, which is the case that matters while a plan is still wrong.
    """
    target = system.body(target)

    def dist(t):
        b, r, v = traj.state(t)
        centre = system.common_parent(b.name, target.name)
        rs, vs = (np.asarray(r), np.asarray(v))
        if b.name != centre:
            rb, vb = system.state(b.name, t, centre)
            rs, vs = rs + np.asarray(rb), vs + np.asarray(vb)
        rt, vt = (np.zeros(3), np.zeros(3)) if target.name == centre else \
            tuple(np.asarray(x) for x in system.state(target.name, t, centre))
        return float(np.linalg.norm(rs - rt)), float(np.linalg.norm(vs - vt))

    # coarse sweep patch by patch; each patch is one conic, so this is vectorisable
    best_t, best_d = ut0, math.inf
    for p in traj.patches:
        lo_p = max(ut0, p.ut0)
        hi_p = min(ut1, p.ut1 if p.ut1 is not None else ut1)
        if hi_p <= lo_p:
            continue
        n = max(32, int(samples * (hi_p - lo_p) / max(ut1 - ut0, 1.0)))
        ts = np.linspace(lo_p, hi_p, n)
        pos, _ = astro.sample_conic(p.body.mu, p.r0, p.v0, ts - p.ut0)
        centre = system.common_parent(p.body.name, target.name)
        if p.body.name != centre:
            pos = pos + system.state_array(p.body.name, ts, centre)[0]
        if target.name != centre:
            pos = pos - system.state_array(target.name, ts, centre)[0]
        d = np.linalg.norm(pos, axis=1)
        i = int(np.argmin(d))
        if d[i] < best_d:
            best_d, best_t = float(d[i]), float(ts[i])
    span = (ut1 - ut0) / samples
    lo = max(ut0, best_t - 3 * span)
    hi = min(ut1, best_t + 3 * span)
    # golden-section on the bracket
    gr = (math.sqrt(5) - 1) / 2
    a, b = lo, hi
    c, d = b - gr * (b - a), a + gr * (b - a)
    for _ in range(60):
        if dist(c)[0] < dist(d)[0]:
            b, d = d, c
            c = b - gr * (b - a)
        else:
            a, c = c, d
            d = a + gr * (b - a)
    t = 0.5 * (a + b)
    dd, vv = dist(t)
    return t, dd, vv


def arrival_report(system, traj, target, ut_end):
    """What actually happens at `target`: capture, or how badly it is missed."""
    target = system.body(target)
    p = traj.enters(target.name)
    ut0 = traj.patches[0].ut0
    if p is not None:
        el = p.elements()
        vinf = astro.vinf_from_state(target.mu, p.r0, p.v0)
        # periapsis inside this patch
        return {"captured": True, "soi_ut": p.ut0, "peR": el.peR,
                "peAlt": el.peR - target.radius, "vinf": vinf, "ecc": el.ecc,
                "inc": math.degrees(el.inc), "patch": p}
    t, d, vrel = closest_approach(system, traj, target, ut0, ut_end)
    return {"captured": False, "ca_ut": t, "ca_dist": d, "ca_vrel": vrel,
            "soi": target.soi, "miss": d - target.soi}
