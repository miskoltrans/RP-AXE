# RP-AXE — Science Solvency Audit (2026-06-26)

First-order audit answering: *is the tech tree winnable with the science the world actually holds, and
where does each milestone's science come from?* Script: `tools/science_audit.py` (data-driven from the
shipped tree + experiment configs). Science pace is RP-1 original (**×1.0** — we trialled a ×0.8 trim,
then reverted it: at this margin it barely matters and ×1.0 keeps science a slightly more meaningful gate).

## Headline
**Science is not a binding constraint anywhere.** The real gates in RP-AXE are time, funds (launch
cost), and engineering — not science scarcity.

- **Tree cost: ~115,070 science.** *(The raw tree total is ~215k, but ~100k of that is the single
  hidden `ORPHANS` dump node — cost 99,999 — which no one unlocks. Real progression is ~115k.)*
- **Collectable science in the system: ~6.6 million** — **~57× the whole tree.**
- **Every era is solvent** with large margin (reachable science ≫ cumulative node cost at every step).

## Per-era solvency (cumulative node cost vs cumulative reachable science)
| Era (≈year) | tree cost so far | reachable science | |
|---|--:|--:|---|
| first orbit ~1958 | 1,128 | 78,951 | ✅ |
| early Moon/inner-planet probes ~1961 | 1,451 | 195,514 | ✅ |
| crewed + early landing ~1964 | 2,215 | 412,069 | ✅ |
| adv probes / stations ~1967 | 3,986 | 593,599 | ✅ |
| **crewed lunar (Apollo) ~1968** | **4,331** | **593,599** | ✅ |
| stations / NF-precursor ~1972 | 7,072 | 3,440,388 | ✅ |
| modern ~2019 | 44,493 | 6,603,810 | ✅ |
| endgame (colonization) | 115,070 | 6,603,810 | ✅ |

The tree is **front-cheap, back-loaded**: reaching Apollo-era tech costs only ~4.3k science; the bulk
(~70k) is the 2019+ modern and 2051-2150 colonization frontier most campaigns never finish.

## The two questions
- **Reach the Moon on Earth science? → Yes, overwhelmingly.** Earth orbital + high-altitude science
  (post sub-40km removal) ≈ **21,000** available vs **~1,250** to reach Moon-capable tech.
- **Apollo on lunar science? → Yes.** ~**4,331** to reach crewed-lunar tech vs **~58k** Moon /
  **~79k** Earth+Moon available.

## Per-body collectable science (the exploration map)
Inner system funds the early-mid tree; the outer system is enormous (high multipliers):
Earth 21k · Moon 58k · Venus 53k · Mars 64k · Phobos/Deimos 51k each · Mercury 114k · Vesta/Ceres 91k ·
Jupiter system ~126-228k/body · Saturn system ~151-237k/body · Uranus/Neptune systems ~224-343k/body ·
Pluto/Charon 440k each.

## What this validates
- Removing Earth sub-40km science (`EarthScienceRemoval.cfg`) is **safe** — Earth is the smallest
  source; the margin is enormous.
- Science is *so* abundant it's a weak gate. If we ever want science to feel more meaningful, the lever
  is making **frontier/key nodes more expensive**, not cheaper. (This is why the ×0.8 pace trim was
  reverted — easing an already-trivial gate wasn't worth it.)

## Assumptions & limits (why these are estimates, not exact)
- Biome counts per body are estimated (Earth 15, Moon 12, …); only affects biome-specific experiments
  (most high-value ones are not biome-specific, so impact is small).
- Experiment→body assignment is heuristic by name (Lunar*→Moon, Earth/station/supersonic→Earth,
  geophysics/imaging→all bodies).
- "Reachable" assumes you actually fly the missions; early-era reachable is lower than a body's full
  total (high-value instruments are late-tech) — but early node costs are tiny, so still solvent.
- Not modelled (all make it *more* solvent or are time- not science-limits): Kerbalism data-transmission
  time & caps, contract science rewards, recovery science.
- The ±on absolute numbers is large, but the **~57× margin** makes the conclusion robust.
