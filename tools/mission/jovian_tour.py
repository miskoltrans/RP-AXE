"""Jovian capture + Galilean tour arithmetic on the install's own moon elements.

Capture into a Jupiter orbit is absurdly cheap (Oberth at 35 km/s escape speed) and the whole
mission cost lives in what you do AFTER: apojove sets the tour clock, perijove sets which moon
you can reach, and a single Ganymede/Callisto encounter can pay for both.
"""
import math

from rss_ephem import System

MOONS = ("Io", "Europa", "Ganymede", "Callisto")


class Tour:
    def __init__(self, S=None):
        self.S = S or System(r"C:/git/ksp/Instance/GameData")
        self.J = self.S.bodies["Jupiter"]
        self.mu = self.J.mu
        self.R = self.J.radius

    # --- basic conics -----------------------------------------------------
    def v_at(self, r, a):
        return math.sqrt(self.mu * (2 / r - 1 / a))

    def period(self, a):
        return 2 * math.pi * math.sqrt(a ** 3 / self.mu)

    def capture(self, vinf, rp, ra):
        a = (rp + ra) / 2
        return math.sqrt(vinf ** 2 + 2 * self.mu / rp) - self.v_at(rp, a)

    def raise_periapsis(self, rp0, rp1, ra):
        """Burn at apojove to move perijove rp0 -> rp1, keeping ra."""
        return abs(self.v_at(ra, (rp1 + ra) / 2) - self.v_at(ra, (rp0 + ra) / 2))

    # --- moon encounters --------------------------------------------------
    def flyby_turn(self, moon, vinf, alt_km=300.0):
        """Max velocity change a single flyby of `moon` can impose."""
        b = self.S.bodies[moon]
        rp = b.radius + alt_km * 1e3
        e = 1 + rp * vinf ** 2 / b.mu
        delta = 2 * math.asin(1 / e)
        return 2 * vinf * math.sin(delta / 2), math.degrees(delta)

    def encounter(self, moon, rp_orbit, ra_orbit):
        """v-infinity relative to `moon` when crossing its orbit, tangential case."""
        b = self.S.bodies[moon]
        r = b.a
        a = (rp_orbit + ra_orbit) / 2
        if r > 2 * a - rp_orbit + 1:
            return None
        v_sc = self.v_at(r, a)
        v_moon = math.sqrt(self.mu / r)
        return v_sc, v_moon, abs(v_sc - v_moon)


def report(vinf_kms=5.69, rp_rj=3.0):
    t = Tour()
    Rj = t.R
    rp = rp_rj * Rj
    vinf = vinf_kms * 1000
    print(f"Jupiter  R = {Rj/1e3:,.0f} km   mu = {t.mu:.4e}   SOI = {t.S.soi('Jupiter')/1e9:.1f} Gm")
    print(f"arrival v-inf = {vinf_kms} km/s,  perijove = {rp_rj} Rj = {rp/1e3:,.0f} km\n")

    print("CAPTURE  (burn at perijove; contract cap is perijove <= 3.0 Rj)")
    print(f"{'apojove km':>12s} {'period d':>9s} {'dv m/s':>8s}")
    for ra in (50e6, 20e6, 10e6, 5e6, 3e6, 2e6, 1e6):
        ra_m = ra * 1e3
        a = (rp + ra_m) / 2
        print(f"{ra:12,.0f} {t.period(a)/86400:9.1f} {t.capture(vinf, rp, ra_m):8.0f}")

    print("\nPERIJOVE WALK  (single burn at apojove, apojove held at 20e6 km)")
    ra_m = 20e6 * 1e3
    prev = rp
    print(f"{'target':>10s} {'r km':>12s} {'dv m/s':>8s} {'cum':>7s}")
    cum = 0
    for m in ("Callisto", "Ganymede", "Europa", "Io"):
        r = t.S.bodies[m].a
        dv = t.raise_periapsis(prev, r, ra_m)
        cum += dv
        print(f"{m:>10s} {r/1e3:12,.0f} {dv:8.0f} {cum:7.0f}")
        prev = r

    print("\nMOON ENCOUNTERS from a rp=moon, ra=20e6 km orbit")
    print(f"{'moon':>10s} {'v_sc':>8s} {'v_moon':>8s} {'v_inf':>8s} {'max dv':>8s} {'turn deg':>9s} {'SOI alt km':>11s}")
    for m in MOONS:
        v_sc, v_moon, vi = t.encounter(m, t.S.bodies[m].a, ra_m)
        dv, turn = t.flyby_turn(m, vi)
        soi_alt = (t.S.soi(m) - t.S.bodies[m].radius) / 1e3
        print(f"{m:>10s} {v_sc:8.0f} {v_moon:8.0f} {vi:8.0f} {dv:8.0f} {turn:9.1f} {soi_alt:11,.0f}")

    print("\nGANYMEDE PUMP-DOWN  (one 300 km flyby, orbit rp=Ganymede)")
    g = t.S.bodies["Ganymede"]
    for ra0 in (20e6, 10e6, 5e6):
        v_sc, v_moon, vi = t.encounter("Ganymede", g.a, ra0 * 1e3)
        dv, _ = t.flyby_turn("Ganymede", vi)
        v_new = v_sc - dv
        inv_a = 2 / g.a - v_new ** 2 / t.mu
        if inv_a <= 0:
            print(f"  from ra={ra0/1e6:.0f}e6 km -> escape")
            continue
        a_new = 1 / inv_a
        ra_new = 2 * a_new - g.a
        print(f"  from ra={ra0/1e6:5.1f}e6 km (P={t.period((g.a+ra0*1e3)/2)/86400:6.1f} d)"
              f" -> ra={ra_new/1e9:5.2f}e6 km (P={t.period(a_new)/86400:6.1f} d)  free dv {dv:.0f} m/s")


if __name__ == "__main__":
    report()
