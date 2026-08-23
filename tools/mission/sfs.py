"""Read a KSP save: the game clock, every vessel's orbit, and any planned nodes.

Typing a vessel's orbit in by hand is where mission arithmetic goes wrong before
it starts, so nothing in this toolchain asks you to. The save is authoritative.

Two details the format hides:
  * ORBIT.MNA is in RADIANS at epoch ORBIT.EPH, while INC/LPE/LAN are degrees.
  * ORBIT.REF is an index into FlightGlobals.Bodies (not flightGlobalsIndex).
    Modern saves also write ORBIT.IDENT with the body NAME; prefer it, and fall
    back to the index that Kopernicus.log recorded.
"""
import math
import os

import numpy as np

import astro
import cfgnode
from rss_ephem import System, date_of


class Vessel:
    def __init__(self, node, system):
        self.node = node
        self.system = system
        self.name = node.get("name", "?")
        self.type = node.get("type", "")
        self.situation = node.get("sit", "")
        self.pid = node.get("persistentId")
        self.launched = node.getf("lct")
        orb = node.node("ORBIT")
        self.orbit = orb
        ident = orb.get("IDENT") if orb else None
        ref = orb.get("REF") if orb else None
        self.body = None
        if ident and ident in system.bodies:
            self.body = system.bodies[ident]
        elif ident:
            self.body = system.bodies.get(system.alias.get(ident, ident))
        if self.body is None and ref is not None:
            self.body = system.by_index.get(int(ref))
        self.sma = orb.getf("SMA") if orb else None
        self.ecc = orb.getf("ECC") if orb else None
        self.inc = orb.getf("INC") if orb else None
        self.lpe = orb.getf("LPE") if orb else None
        self.lan = orb.getf("LAN") if orb else None
        self.mna = orb.getf("MNA") if orb else None
        self.eph = orb.getf("EPH") if orb else None

    @property
    def valid(self):
        # KSP parks landed/packed craft on a stub orbit with ECC = 1 - 1e-16 and
        # MNA = pi exactly. It parses fine and means nothing; treat it as no orbit.
        if self.body is None or self.sma is None or not math.isfinite(self.sma) or self.sma == 0.0:
            return False
        return not (self.ecc is not None and abs(self.ecc - 1.0) < 1e-12)

    def state(self, ut):
        """(r, v) about its reference body at `ut`, metres and m/s."""
        if not self.valid:
            raise ValueError(f"{self.name}: no usable orbit in the save")
        return astro.state_from_save_orbit(self.body.mu, self.sma, self.ecc, self.inc,
                                           self.lpe, self.lan, self.mna, self.eph, ut)

    def elements(self, ut):
        r, v = self.state(ut)
        return astro.elements(self.body.mu, r, v)

    def nodes(self):
        """Planned maneuver nodes: (UT, ManeuverNode.DeltaV as radial/normal/prograde)."""
        fp = self.node.node("FLIGHTPLAN")
        out = []
        if fp is None:
            return out
        for m in fp.nodes("MANEUVER"):
            dv = m.get("dV")
            if dv is None:
                continue
            out.append({"ut": m.getf("UT"),
                        "node": np.array([float(x) for x in dv.split(",")])})
        return out

    def __repr__(self):
        b = self.body.name if self.body else "?"
        return f"<Vessel {self.name!r} about {b} sma={self.sma}>"


class Save:
    def __init__(self, path, system=None):
        self.path = path
        self.system = system or System()
        root = cfgnode.load(path)
        game = root.node("GAME")
        if game is None:
            raise ValueError(f"{path}: no GAME node")
        self.game = game
        fs = game.node("FLIGHTSTATE")
        self.ut = fs.getf("UT", 0.0) if fs else 0.0
        self.active_index = int(fs.get("activeVessel", -1)) if fs else -1
        self.vessels = [Vessel(n, self.system) for n in (fs.nodes("VESSEL") if fs else [])]

    @property
    def active(self):
        if 0 <= self.active_index < len(self.vessels):
            return self.vessels[self.active_index]
        return None

    def vessel(self, name):
        """Exact match, then unique case-insensitive substring."""
        for v in self.vessels:
            if v.name == name:
                return v
        hits = [v for v in self.vessels if name.lower() in v.name.lower()]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise KeyError(f"no vessel matching {name!r}. Known: "
                           + ", ".join(sorted(v.name for v in self.vessels)))
        raise KeyError(f"{name!r} is ambiguous: " + ", ".join(v.name for v in hits))

    def __repr__(self):
        return f"<Save {os.path.basename(self.path)} UT={self.ut:,.0f} {len(self.vessels)} vessels>"


def find_save(save=None, instance=None):
    """Resolve a save name, a directory, or a full path to a .sfs file."""
    from rss_ephem import DEFAULT_INSTANCE
    instance = instance or DEFAULT_INSTANCE
    if save and os.path.isfile(save):
        return save
    saves = os.path.join(instance, "saves")
    if save:
        cand = os.path.join(saves, save, "persistent.sfs")
        if os.path.isfile(cand):
            return cand
        cand = os.path.join(saves, save)
        if os.path.isfile(cand):
            return cand
        raise FileNotFoundError(f"no save {save!r} under {saves}")
    best, best_mt = None, -1
    for d in os.listdir(saves):
        p = os.path.join(saves, d, "persistent.sfs")
        if os.path.isfile(p) and os.path.getmtime(p) > best_mt:
            best, best_mt = p, os.path.getmtime(p)
    if best is None:
        raise FileNotFoundError(f"no persistent.sfs under {saves}")
    return best


if __name__ == "__main__":
    s = Save(find_save())
    print(s, "   game date:", f"{date_of(s.ut):%Y-%m-%d %H:%M}")
    print(f"{'vessel':30s} {'body':10s} {'pe km':>12s} {'ap km':>14s} {'inc':>7s} {'ecc':>8s} nodes")
    for v in s.vessels:
        if not v.valid:
            print(f"{v.name[:30]:30s} {'-':10s} {'(no orbit: ' + (v.situation or '?') + ')':>44s}")
            continue
        el = v.elements(s.ut)
        ap = "escape" if el.ecc >= 1 else f"{(el.apR - v.body.radius) / 1e3:,.0f}"
        print(f"{v.name[:30]:30s} {v.body.name:10s} {(el.peR - v.body.radius) / 1e3:12,.0f} "
              f"{ap:>14s} {math.degrees(el.inc):7.2f} {el.ecc:8.4f} {len(v.nodes())}")
