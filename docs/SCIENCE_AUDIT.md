# RP-AXE — Science Solvency Audit (2026-06-26)

First-order audit answering: *is the tech tree winnable with the science the world actually holds, and
where does each milestone's science come from?* Script: `tools/science_audit.py` (data-driven from the
shipped tree + experiment configs).

## Headline
**Science is not a binding constraint anywhere.** The real gates in RP-AXE are time, funds (launch
cost), and engineering — not science scarcity.

- **Tree cost (after our ×0.8 trim): ~92,056 science.** *(Note: the raw tree total is ~172k, but
  ~80k of that is the single hidden `ORPHANS` dump node — cost 99,999 — which no one unlocks. Real
  progression is ~115k unscaled → ~92k trimmed.)*
- **Collectable science in the system: ~6.6 million** — **~72× the whole tree.**
- **Every era is solvent** with large margin (reachable science ≫ cumulative node cost at every step).

## Per-era solvency (cumulative node cost vs cumulative reachable science)
| Era (≈year) | tree cost so far | reachable science | |
|---|--:|--:|---|
| first orbit ~1958 | 902 | 78,951 | ✅ |
| early Moon/inner-planet probes ~1961 | 1,161 | 195,514 | ✅ |
| crewed + early landing ~1964 | 1,772 | 412,069 | ✅ |
| adv probes / stations ~1967 | 3,189 | 593,599 | ✅ |
| **crewed lunar (Apollo) ~1968** | **3,465** | **593,599** | ✅ |
| stations / NF-precursor ~1972 | 5,658 | 3,440,388 | ✅ |
| modern ~2019 | 35,594 | 6,603,810 | ✅ |
| endgame (colonization) | 92,056 | 6,603,810 | ✅ |

The tree is **front-cheap, back-loaded**: reaching Apollo-era tech costs only ~3.5k science; the bulk
(~56k) is the 2051-2150 colonization frontier most campaigns never finish.

## The two questions
- **Reach the Moon on Earth science? → Yes, overwhelmingly.** Earth orbital + high-altitude science
  (post sub-40km removal) ≈ **21,000** available vs **~1,000** to reach Moon-capable tech.
- **Apollo on lunar science? → Yes.** ~**3,465** to reach crewed-lunar tech vs **~58k** Moon /
  **~79k** Earth+Moon available.

## Per-body collectable science (the exploration map)
Inner system funds the early-mid tree; the outer system is enormous (high multipliers):
Earth 21k · Moon 58k · Venus 53k · Mars 64k · Phobos/Deimos 51k each · Mercury 114k · Vesta/Ceres 91k ·
Jupiter system ~126-228k/body · Saturn system ~151-237k/body · Uranus/Neptune systems ~224-343k/body ·
Pluto/Charon 440k each.

## What this validates
- Removing Earth sub-40km science (`EarthScienceRemoval.cfg`) is **safe** — Earth is the smallest
  source; the margin is enormous.
- The ×0.8 pace trim is **safe** (and barely matters at 72× headroom; it mainly smooths early pacing).
- If anything, science is *so* abundant it's a weak gate — if we ever want science to feel more
  meaningful, the lever is making **frontier/key nodes more expensive**, not cheaper.

## Assumptions & limits (why these are estimates, not exact)
- Biome counts per body are estimated (Earth 15, Moon 12, …); only affects biome-specific experiments
  (most high-value ones are not biome-specific, so impact is small).
- Experiment→body assignment is heuristic by name (Lunar*→Moon, Earth/station/supersonic→Earth,
  geophysics/imaging→all bodies).
- "Reachable" assumes you actually fly the missions; early-era reachable is lower than a body's full
  total (high-value instruments are late-tech) — but early node costs are tiny, so still solvent.
- Not modelled (all make it *more* solvent or are time- not science-limits): Kerbalism data-transmission
  time & caps, contract science rewards, recovery science.
- The ±on absolute numbers is large, but the **72× margin** makes the conclusion robust.
