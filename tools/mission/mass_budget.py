"""Stage sizing for the Jupiter orbiter: LEO mass required for a given orbiter dry mass.

Two stages that matter:
  * TJI (trans-Jupiter injection) burnt within hours of launch -> hydrolox is fine, boiloff is not
    a factor, RL10A-3-3 (442 s) is the best engine in the current tech state.
  * The spacecraft's own engine, fired 2.5 years later for Jupiter orbit insertion and again for
    every tour burn -> must be storable and many-ignition; KTDU-425 (312 s, 50 ignitions).
"""
import math

G0 = 9.80665


def rocket(dv, isp, m_final):
    """Initial mass for a burn of `dv` ending at `m_final`."""
    return m_final * math.exp(dv / (isp * G0))


def stage_with_tankage(dv, isp, payload, dry_fraction):
    """Stage whose dry mass is dry_fraction * propellant mass. Returns (m0, prop, dry)."""
    r = math.exp(dv / (isp * G0))
    # m0 = payload + dry + prop ; m0 / (payload + dry) = r ; dry = f*prop
    prop = payload * (r - 1) / (1 - dry_fraction * (r - 1))
    dry = dry_fraction * prop
    return payload + dry + prop, prop, dry


def orbiter(dry_t, dv_tour=1800.0, isp=312.0, tank_fraction=0.12):
    """Spacecraft wet mass at Jupiter arrival for a given dry mass (dry excludes propellant)."""
    r = math.exp(dv_tour / (isp * G0))
    prop = dry_t * (r - 1) / (1 - tank_fraction * (r - 1))
    return dry_t + prop * (1 + tank_fraction), prop


if __name__ == "__main__":
    DV_TJI = 6446.0        # 185 km circular -> C3 81.3
    GRAV_LOSS = 150.0      # finite-burn loss on a ~370 s RL10 injection
    print("Orbiter sizing (KTDU-425, Isp 312 s, 12% tankage on the storable propellant)")
    print(f"{'dry t':>7s} {'dv tour':>8s} {'prop t':>7s} {'wet t':>7s} | "
          f"{'TJI prop t':>10s} {'TJI dry t':>9s} {'LEO t':>7s}")
    for dry in (0.30, 0.40, 0.50, 0.60, 0.80, 1.00):
        for dv_tour in (1800.0,):
            wet, prop = orbiter(dry, dv_tour)
            m0, tji_prop, tji_dry = stage_with_tankage(DV_TJI + GRAV_LOSS, 442.0, wet, 0.15)
            print(f"{dry:7.2f} {dv_tour:8.0f} {prop:7.3f} {wet:7.3f} | {tji_prop:10.2f} {tji_dry:9.2f} {m0:7.2f}")
    print("\nSensitivity: LEO mass per 100 kg of orbiter dry mass")
    a = stage_with_tankage(DV_TJI + GRAV_LOSS, 442.0, orbiter(0.5, 1800.0)[0], 0.15)[0]
    b = stage_with_tankage(DV_TJI + GRAV_LOSS, 442.0, orbiter(0.6, 1800.0)[0], 0.15)[0]
    print(f"  d(LEO)/d(dry) = {(b-a)/0.1*0.1:.2f} t per 100 kg")
    print("\nTour dv sensitivity at 0.5 t dry")
    for dv in (1200, 1500, 1800, 2200, 2600):
        wet, prop = orbiter(0.5, dv)
        m0 = stage_with_tankage(DV_TJI + GRAV_LOSS, 442.0, wet, 0.15)[0]
        print(f"  {dv:5.0f} m/s -> orbiter {wet:5.3f} t, LEO {m0:6.2f} t")
