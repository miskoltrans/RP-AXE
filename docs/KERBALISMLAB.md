# RP-AXE — KerbalismLab Integration Plan (P3 crewed-station science)

Turnkey plan for landing **KerbalismLab** (crewed-station lab science) in AXE. Read with
[`SCIENCE.md`](SCIENCE.md) §1/§3/§4 (budget + blocker diagnosis) and
[`RESTART.md`](RESTART.md) P3. This supersedes SCIENCE.md §4's "re-author as plain Experiments"
default — **the decision is now Path A: vendor the mod as-authored, make it load, remap, re-point.**

> **STATUS 2026-07-15 — BUILT (static-validated; in-game load test pending).** Configs authored under
> `GameData/RP-AXE/design/Science/KerbalismLab/` via `tools/build_kerbalismlab.py` (65 experiments vendored,
> 10 marquee Mir/Kvant gates, all techs remapped, all target nodes verified in `AxeTechTree.cfg`, every
> instrument package has a curated host). The §4 remap is **locked** — committed table lives in that folder's
> `_README.md`. Remaining: deploy + `-axe-autotest` load test, then the deferred balance pass.

## Decisions locked (2026-07-14)

1. **Path A — vendor + keep.** Vendor the minimal Kerbalism ScienceRework **lab** framework so the
   fork loads unchanged (slots, values, durations, crew, big-data all as the creator built them). Do
   **not** re-author the 65 experiments; do **not** vendor KerbalismScienceOnly wholesale (its
   Orbital/Crew/Unmanned/Atmospheric/Underwater groups are a full alternative science system that would
   conflict with the RP0\* backbone).
2. **Polish all instrument tags.** Re-point every `*LabExperimentPackage` onto the AXE/RO part that
   provides the matching real instrument — not just the 6 that currently have no host. Consistent scheme,
   zero dependency on which stock donor incidentally survived RO's `HardRemoveNonRO`.
3. **Delete the ScienceBox clone.** `HighEnergy` re-points to the cosmic-ray detectors, so the fork's
   `+PART[ScienceBox]→ScienceBox-HighEnergy` clone (donor `ScienceBox` absent in AXE) is removed, not fixed.
4. **Home-system body scope + balance = a later trim** (SCIENCE.md §4 step 4). Ship with the creator's
   `BodyAllowed` as-is first; the "overpowered deep-space tail" is theoretical (needs crewed bases
   everywhere — realistically ~4–15k). Revisit only if the solvency play-session shows it bites.

## How the mechanic works (three gates)

A KerbalismLab experiment runs when all three hold:
1. **Host lab part unlocked** — the crewed lab carrying the `Configure` "Laboratory Experiments" host is
   researched + built. *(Already free: AXE's lab parts are placed in the tree.)*
2. **Experiment `UnlockTech` researched** — the SETUP option appears in the lab's slot menu. *(Stock/CTT
   node IDs → **needs remap**, §4.)*
3. **Required instrument present** (`requirements = Module:XLabExperimentPackage`) — a runtime hardware
   check that the vessel carries a part tagged with that instrument. *(**needs re-point**, §3.)*

The slot machinery (`Configure`, `BaseSlots`, upgrades) is what makes the lab a **loadout choice** — you
fit a subset of experiments into a station, limited slots, more slots via tech. Path A keeps this intact.

---

## 1. Framework subset to vendor

Source: `C:\git\ksp\KerbalismScienceOnly\GameData\KerbalismScienceOnly\System\ScienceRework\`.
Vendor **only** these four pieces into `GameData/RP-AXE/design/Science/KerbalismLab/` (design-owned —
tech-remapped, so NOT `seed/`; sync-seed never touches it). Everything is `:NEEDS[FeatureScience]`.

| # | Piece | From | Role | Adapt? |
|---|---|---|---|---|
| A | Scaffold nodes | `Internal.cfg` | Creates the temp `KERBALISM_GROUP_SETTINGS` root (+ siblings) at load, deletes `:FINAL`. Without it every `@KERBALISM_GROUP_SETTINGS` lookup fails → the ~132 errors. | **Trim** — keep `KERBALISM_GROUP_SETTINGS` create/delete; ⚠ see HDD note |
| B | Lab group + base exps | `Tweakables/StockGroups-Lab.cfg` | The `LAB_EXPERIMENTS` block: `BaseSlots=1`, `UpgradeTech`, `LabDataRateMultiplier=2`, `LabECMultiplier=5`, + the 6 base experiments (CHILLED/RELAX/JAMMED/TRAPPED/SALINE/BIRDIE) + matbay/goo slots. | **Remap** its 8 stock techs (§4) |
| C | Base-exp processing | `Groups/LabExperiments.cfg` | Adds the base `Experiment` MODULEs, the `Configure` SETUPs, wires values from B. | verbatim |
| D | Configure host attach | `NewScience.cfg` (stock lab patch — locate; **not** in ScienceRework/) | Adds the `Configure { title = Laboratory Experiments }` host to lab parts. **This is the file that decides *which parts are labs*.** | **Re-target** to AXE lab parts (§2) |

**⚠ HDD-scaffold overlap.** `Internal.cfg` also creates `KERBALISM_HDD_SIZES`, which AXE **already**
provides via the KEPT HDD subsystem (`seed/Science/HardDriveConfigs.cfg`, `KERBALISM_HDD_SIZES`). Do
**not** double-create it — vendor only the `KERBALISM_GROUP_SETTINGS` create/delete lines from `Internal.cfg`
(and `KERBALISM_EXPERIMENT_VALUES`/`KERBALISM_ANTENNA_RATES` only if a vendored file references them; the
lab subset does not). Verify no duplicate-node MM warning after deploy.

**Do NOT vendor** (these are the conflicting alt-science system): `Groups/{Orbital,Crew,Unmanned,Atmospheric,Underwater}Experiments.cfg`,
their `StockGroups-*.cfg`, `ScienceDefs-*.cfg`, `Patches-Experiments.cfg` (global stock-experiment reconfigure),
`Patches-Antennas.cfg`, `Patches-HardDrives.cfg`.

## 2. Which parts are labs (the Configure host, piece D)

Attach the `Laboratory Experiments` Configure host to AXE's **curated crewed-lab parts** (confirmed present
in the instance): `Large_Crewed_Lab`, `L25mSci`, `ROC-ApolloMissionModule4`, `Skylab`, the SSPX `aquila_lab_*`
family. AXE already gives these the Kerbalism `Laboratory` module (`seed/Science/Lab.cfg`,`ScienceLabs.cfg`) —
piece D adds the experiment-slot Configure alongside it. Simplest target selector: any part that has the
`Laboratory` module (mirrors the fork's `#title[Laboratory?Experiments]` convention). Confirm the host lands
on all intended labs post-deploy (the fork's 65 experiments self-attach to *anything* carrying the host, so
this one patch is what turns a part into a lab).

## 3. Instrument re-point table (polish — all packages)

Edit the vendored `InstrumentTagging.cfg`: change each tag's target from the stock donor to the AXE/RO part.
The tag attaches to the part; the part's tech node is wherever AXE already placed it (node column = info /
balance awareness only). **Instrument-backed packages → RO instruments; intrinsically-in-lab packages stay on
their natural host** (there is no RO "materials bay" to point at — the lab *is* the instrument).

| Package | # exp | Re-point to (exists in AXE) | Note |
|---|---|---|---|
| **Magnetometer** | 3 | `RO-EarlyMagnet\|RO-HeliumMagnet\|RO-FluxgateMagnet` | was: stock `magnetometer` (gone) |
| **Plasma** | 2 | `RO-PlasmaWave\|RO-SWPlasmaAnalyzer\|RO-RPWS` | already-fine, unify for consistency |
| **Gravity** | 2 | `sensorGravimeter\|retinaGravimeter` | was: stock `gravityScan` (gone) |
| **Visual** | 3 | `RO-EarlyTVCamera\|RO-BasicTVCamera\|RO-ImprovedTVCamera\|RO-AdvancedImager\|RO-HIRES` | was: `Cupola` (gone) |
| **Multispectral** | 9 | `RO-IRIS\|RO-NIMS\|RO-VIMS\|RO-UVSpectrometer` | was: stock `OrbitalScanner` |
| **Spectrometer** | 4 | `RO-UVSpectrometer\|RO-IRIS\|RO-NIMS` | was: stock `OrbitalScanner` |
| **HighEnergy** | 3 | `RO-GeigerMuller\|RO-ScintillationCounter\|RP0Cherenkov` | was: `ScienceBox` clone (deleted, §5) |
| **Atmosphere** | 2 | `sensorAtmosphere` (GC/MS) `\|PAPBarometer\|sensorBarometer` | was: stock `atmosphereAnalysis` (gone) |
| **Telescope** | 5 | `sspx-cupola-telescope-125-1` (+ `sspx-observation-25-1`); CALET/AMS-02 may prefer `RO-ScintillationCounter` ("Cosmic Ray Telescope") | was: stock `infraredTelescope` (gone); station telescope = ideal fit |
| **Radar** | 7 | RO radar-altimeter instrument **(confirm exact part name)**, else keep `SurveyScanner` | verify RO part; SurveyScanner is the safe fallback |
| **Radio** | ~6 | keep `AntennaRadioLab` (clones `RelayAntenna100`, present) | works as-is |
| **Materials** | 6 | keep on surviving Materials Bay (`mobileMaterialsLab` part) **or** run in-lab (blank `requirements`) | no RO analog — in-lab science |
| **Biology** | 1 | keep on Goo (`mysteryGoo`) **or** `Greenhouse` | in-lab science |
| **Surface** | 4 | keep `SurfaceScanner` **or** run in-lab | no RO analog |
| Drill *(req)* | 2 | `*Drill*` (`kerbalism-drill` present) — keep | |
| Greenhouse *(req)* | 4 | Kerbalism `Greenhouse` — keep | |
| RobotArm *(req)* | 1 | robot-arm part w/ `ModuleRobotArmScanner` **(confirm present)** | ChemCam-2 |

Non-part requirements need no host: `Shadow` (JAMMED), `Sunlight` (CATS/IBATE/MastCam), blank (RELAX/SALINE/
TRAPPED/BIRDIE/Strata-1 — run in any lab).

**Two part-name confirmations before build:** the RO radar-altimeter instrument, and the robot-arm part
(`ModuleRobotArmScanner`). If either is absent → keep the surviving stock donor (SurveyScanner) / drop the one
robot-arm experiment.

## 4. Tech remap (UnlockTech → AXE node)

Same pattern as [`design/Science/CrewScience/_README.md`](../GameData/RP-AXE/design/Science/CrewScience/_README.md):
era-match, verify every target exists in `design/Tree/AxeTechTree.cfg`. **These are `UnlockTech` *values*
(in the vendored group + experiment files), not `:HAS[]` filter directives — so a plain find-replace across
the vendored files works** (unlike CrewScience's filter-directive problem; no overlay needed).

**LOCKED (2026-07-15).** Philosophy: for crewed-**station** experiments, menu availability tracks **station
capability** → the Life-Support / station ladder, era-stepped, preserving the creator's stagger; runnability
stays with the §3 instrument. Lab is at `int_orbitalLab` (T9): techs ≤ T9 = "available with your first lab",
> T9 stagger up. **Plus** 10 marquee experiments override to their thematic Mir module (T11): Kvant-1
(HaloSat/NICER/CALET), Kristall (SODI-Colloid/Platan/TPSMMO), Priroda (ECOSTRESS/GEDI/BeaverCube), Kvant-2
(Tanpopo). **Committed table + rationale: `../GameData/RP-AXE/design/Science/KerbalismLab/_README.md`.**
The find-replace is codified in `tools/build_kerbalismlab.py` (`REMAP` + `MARQUEE`). Original first-cut kept
below for reference:

| stock tech | → AXE node (first cut) | | stock tech | → AXE node (first cut) |
|---|---|---|---|---|
| `engineering101` | early (~T2) | | `electronics` | `elec_transistor` (T3) |
| `survivability` | ~T2–3 | | `electrics` | `elec_transistor` (T3) |
| `basicScience` | ~T3 science | | `experimentalElectrics` | `elec_integratedCircuit` (T7) |
| `generalConstruction` | ~T3 | | `miniaturization` | ~T7–8 |
| `highAltitudeFlight` | aviation ~T3–4 | | `unmannedTech` | ~T4 (probes) |
| `scienceTech` | ~T4 science | | `advUnmanned` | ~T6–7 |
| `spaceExploration` | ~T4–5 | | `hydroponics` | a Life-Support greenhouse node (~T5+) |
| `fieldScience` | ~T5 (geology) | | `heavyLanding` | a lander node (~T8–9) |
| `precisionEngineering` | ~T5 | | `aerodynamicSystems` | aero ~T5–6 |
| `advScienceTech` | ~T5–6 | | `advConstruction` | `str_*` (~T5–6) |
| `advExploration` | ~T6 | | `specializedScienceTech` | ~T6–7 |
| `experimentalScience` | ~T7–8 | | `longTermScienceTech` | ~T8–9 |

Ship a fixed remap table (`design/Science/KerbalismLab/_README.md`, mirroring CrewScience) so it's auditable;
`tools/check_tech_refs.py --cache` catches any dangling target.

## 5. ScienceBox clone — delete

In the vendored `InstrumentTagging.cfg`, remove the `+PART[ScienceBox]:...{ @name = ScienceBox-HighEnergy ... }`
block entirely (donor `ScienceBox` isn't in AXE). `HighEnergy` experiments (Vsplesk, SOLAR-ISOIS, BTN-Neutron)
are covered by the §3 re-point to `RO-GeigerMuller|RO-ScintillationCounter|RP0Cherenkov`. Also drop the
`+PART[RelayAntenna100]→AntennaRadioLab` block **only if** you'd rather re-point Radio onto an RO antenna; the
default keeps it (RelayAntenna100 is present).

---

## Build sequence

1. **Vendor framework subset** (§1 A–D) → `design/Science/KerbalismLab/`; trim `Internal.cfg` to the
   GROUP_SETTINGS scaffold (mind the HDD overlap); re-target the Configure host (D) to AXE lab parts (§2).
2. **Vendor the 65 fork experiment cfgs** + `InstrumentTagging.cfg` into the same folder. They self-attach
   via the host — no per-experiment part wiring.
3. **Re-point instrument tags** (§3) + **delete ScienceBox clone** (§5) in `InstrumentTagging.cfg`.
4. **Tech remap** (§4): find-replace `UnlockTech` values across the vendored group + experiment files from
   the fixed table; write `_README.md`.
5. **Confirm 2 part names** (RO radar altimeter, robot-arm) — re-point or drop accordingly.
6. **Deploy + load-test** (`deploy.ps1`; `-axe-autotest`). Success = MM cache writes with **0**
   `KERBALISM_GROUP_SETTINGS` errors, no duplicate `KERBALISM_HDD_SIZES` warning, career loads.
7. **Verify in-game** (SANDBOX): a crewed lab (e.g. `Large_Crewed_Lab`) exposes the Configure
   "Laboratory Experiments" slot menu; unlocked experiments appear; one runs given crew + its instrument.
8. **check_tech_refs.py --cache** → 0 dangling. Commit.
9. **Balance pass (deferred)**: body-scope tail + baseValue calibration vs the ~298k budget target, tuned in
   the P3 solvency play-session (SCIENCE.md §4 step 4).

## Verification checklist

- [ ] MM cache writes; 0 `Can't find nodeType:KERBALISM_GROUP_SETTINGS`.
- [ ] No duplicate `KERBALISM_HDD_SIZES` (HDD subsystem still intact).
- [ ] Configure host present on every intended AXE lab part; absent elsewhere.
- [ ] Each `*LabExperimentPackage` tag lands on ≥1 present AXE part (grep cache post-deploy).
- [ ] `check_tech_refs.py --cache` = 0 dangling UnlockTech.
- [ ] In-game: slot menu works; an experiment completes and banks science.

## Open / deferred

- **Body scope + values** — creator's `BodyAllowed` shipped as-is; trim the deep-space tail only if the
  solvency play-session shows it (SCIENCE.md §3b/§4).
- **Slot-upgrade techs** — `UpgradeTech=advScienceTech`, `ReconfigureTech=fieldScience` (in group B) are part
  of the §4 remap; the reconfigure-in-field upgrade is a nice-to-have, not load-bearing.
- **Crew-star gating** — experiments require `Scientist:N`; confirm AXE's kerbal-leveling reaches those tiers,
  else the top-star ones are dead content (flatten to `Scientist`/`True` if not). *(Verify AXE crew leveling.)*
