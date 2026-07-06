# RP-AXE Band 3 — Tech Tree Design

Band 3 = **robotic-landers → stations ‖ crewed-moon ‖ inner-orbiters**. Tier fence: **T1-T6 signed off,
do not re-litigate. New nodes land T7+.** Working file scope so far: `manifest/interplanetary-lunar-probes-partlist.tsv`
ONLY (engines first, per user) — `crewed-lunar-landing-partlist.tsv` not yet started.

Ground rule re-confirmed this session: **ahistorical.** Sequencing/tiering/naming comes from technology +
gameplay balance, never from which nation historically did something first or when in the real calendar —
era_x is a historical artifact of RO's tree, not a design signal. Compare candidates by PERFORMANCE
(thrust/Isp/propellant, `manifest/engine-stats.tsv`) against existing nodes, never by era_x.

## Sign-off status
Everything through band 2 (136 nodes) is SIGNED OFF. **Touching a signed-off node is fine — sign-off protects
decisions already made, not the literal YAML.** Below is a **PROPOSAL**, nothing here is authored into
`tree/nodes.yaml` yet.

## Method used this pass (REVISED)
**The only hard rule: an upgrade may never live in the same node as its own base part (doctrine #4).** For
every band-3 engine candidate (part or upgrade — weighted equally), checked the candidate's host part-id against
the exact `parts:` list of the existing node its lineage continues:
- **Host NOT in that node's `parts:`** (the node is upgrade-only, or holds a different sibling part-id) →
  **add the upgrade directly to the existing node.** No new node needed, signed-off or not.
- **Host IS in that node's `parts:`** → doctrine #4 forces a separate node.

## Engine spine — PROPOSED (interplanetary-lunar-probes engines only)

### Direct additions to existing nodes (no doctrine-4 conflict)

| Existing node | Add | Why safe |
|---|---|---|
| `pc_ntoHypergolics` (0 parts) | RD-250-8D518 (RD-215), RD-252-8D724 (RD-219), RD-855, RD-856 | enabler-only, no base part to conflict with |
| `fd_vacuumExpansion` (0 parts) | X-405H-3, RD-0108, RL10A-3-1, XLR81-BA-11 (Agena), YF-22B, YF-23B, RD-225-8D721 | enabler-only |
| `met_cooledTurbine` (0 parts) | Avon302, J79-GE-10/11/17, R-11F2S-300, WP-7, WP-7A, WP-6A, PT6A-27/28, R-15BD-300 | enabler-only |
| `av_ramjetAdvanced` (parts: `RO-RD012`) | MA20S-4 (host `RO-RJ43`) | RJ43 isn't this node's base part — RD012 is |
| `fd_restartableUpper` (parts: Agena/`ROE-AJ10Mid`/Juno45K/Juno6K) | AJ10-118, AJ10-118D (host `ROE-AJ10Early`) | **verified in engine-stats.tsv: `ROE-AJ10Mid` and `ROE-AJ10Early` are distinct part-ids with entirely separate config chains** — no conflict, and the node already holds AJ10-42/101A/142 (same `ROE-AJ10Early` lineage) as upgrades, so this is just the next entries in an already-established list |

This resolves the earlier "thin node" problem for the ramjet and AJ10 candidates — they just fold into existing
lists instead of needing their own node.

### New nodes (doctrine #4 forces separation — host part already lives in the obvious parent node)

**Tier re-checked against each node's OWN parent (not a flat band-opening tier)** — band 2 ran a real
3-generation arc (T4→T5→T6) instead of dumping everything at T4; band 3's opener gets the same treatment.
Parent-tier gaps of 2-4 (`fd_clusteredThrustGrowth`, `fd_titanStorableConversion`, `fd_ammoniaCombustionRefinement`
at 2; `pc_juno_ClF3`, `pc_orscDebut` at 3; `pc_pioneerUpperStage` at 4) are fine — bands are windowed, not
strictly parent-tier+1 — but the SEVEN candidates are not all the same generation as each other, so they don't
all belong at the same tier:

| Node (proposed id) | Title | Tier | Parent(s) | Payload |
|---|---|---|---|---|
| `fd_clusteredThrustGrowth` | Clustered-Chamber Thrust Uprating | **7** | `fd_longMarchStorable` | upgrades: YF-20B, YF-25K — modest thrust-only bump, no chemistry change |
| `fd_ammoniaCombustionRefinement` | Stabilized Ammonia Combustion | **7** | `fd_throttlingRocket` | upgrades: [XLR99-RM-3, XLR99-RM-5] — same, direct continuation |
| `fd_titanStorableConversion` | Storable-Propellant Booster Conversion | **7** | `fd_titanTandem` + `pc_ntoHypergolics` | upgrades: LR87-AJ-5/-Kero, LR87-AJ-7/-Kero, LR91-AJ-5/-Kero, LR91-AJ-7/-Kero (BOTH kerolox-continuing and storable-switch configs unlock together, anyToUnlock-style); real strategic pivot but its parents are already in place — the natural headline opener |
| `pc_juno_ClF3` | Chlorine-Trifluoride Oxidiser *(gamble)* | **7** | `fd_restartableUpper` | upgrades: [Juno45k-BII, Juno6k-BII] — mirrors `pc_fluorine`'s gamble pattern; shallow parent, meant as an early quirky detour, not a late payoff |
| `pc_pioneerUpperStage` | Spin-Stabilized Solid Upper Stage | **7** | `pc_compositeSolid` + `hire_JPL` | parts: [PioneerVernier, pioneer1_booster, p1_decoupler]; upgrades: [JPL-532A] — genuinely early content (Pioneer 0-2), parallel probe/charter track, doesn't need engine-spine depth (same as band 2's charter arc sitting shallower than its engine spine) |
| `fd_gasGeneratorCeiling` | Gas-Generator Thrust Ceiling | **8** | `fd_saturnKerolox` | upgrades: H-1-188K, H-1-200K, E-1-468k, RD-111-8D716A — explicitly "the ceiling" of the old cycle; reads better as reached AFTER the T7 refinements, not alongside them |
| `pc_orscDebut` | Oxidiser-Rich Staged Combustion | **8** | `fd_regenCooling` | parts: [ROE-RD58]; upgrades: [11D33] — ORSC's Isp jump (~340s+ vs the established ~290-320s kerolox ceiling) is a real leap, not a refinement; parent confirmed regen-cooling derivative (routing all propellant through the chamber wall is the real prerequisite for routing it through a preburner too) |

**Design payoff**: `fd_gasGeneratorCeiling` and `pc_orscDebut` landing at the SAME tier (T8) is not a
coincidence of the math — it's a genuine narrative beat: the old gas-generator cycle hits its practical
ceiling in the exact generation that staged combustion arrives to supersede it.

### Open judgment calls (flagging, not deciding)
- **Viking `UH25+NTO` blend** (Viking-4B/5B) nets out to ~flat performance despite a nominal chemistry-string
  change — arguably not a real capability event. Not placed above; candidate for skipping/parking rather than
  inventing a node for a wash.
- Still untouched from this file: Mariner/Surveyor probe verniers (`rn_mariner1_2`, `rn_surveyor_engines`,
  `rn_surveyor_s_engine`, `ROE-TD339`), the 1962/64/66 solid family (Algol II, Antares, Castor2, Star-series,
  UA1204/1205/1206/1207, AJ260), RCS propellant chemistry (deferred earlier), Apollo SPS precursor (`AJ10-137`),
  capsule-integrated RCS/retro (Gemini OAMS, Voskhod airlock/retro). Next batch.

## Naming pass
Checked every proposed title against the paper-title/mechanism rule (no artifact, no capability, no "X & Y").
All 7 pass — each names a real mechanism (thrust ceiling, clustered uprating, storable conversion, combustion
stabilization, spin stabilization, exotic oxidiser, staged combustion). No collisions this time (the two
combustion-refinement-flavored names from the earlier draft are gone now that those lineages fold directly into
their existing signed-off nodes instead of getting new titles).

## Balance pass
- Sizes: the 7 new nodes range 1-8 upgrades; `pc_orscDebut` and `pc_pioneerUpperStage` carry real parts (1 and 3)
  with a clear king each — within the ~3-ideal/6-max rule.
- **Fan-out re-checked and now clean**: since 5 of the original 12 candidate-lineages fold directly into
  existing nodes (no new child-node edge at all), `pc_ntoHypergolics`'s dependents only grow by ONE
  (`fd_titanStorableConversion`, a genuine crossover) — from 2 to **3**, not the 4 that triggered the earlier
  flag. No fan-out concerns remain in this batch.
- All other touched parents (`fd_saturnKerolox`, `fd_longMarchStorable`, `fd_titanTandem`, `fd_throttlingRocket`,
  `pc_compositeSolid`, `hire_JPL`, `fd_restartableUpper`, `fd_regenCooling`) gain at most 1 new dependent each.
- **Tier (revised)**: 5 nodes at T7, 2 at T8 — a real 2-generation arc, not the flat T7 first proposed. Parent-tier
  gaps of 2-4 are expected (bands are windowed, not strictly parent-tier+1 — band 2 showed the same pattern), but
  each node's OWN generation was re-judged rather than assumed uniform. See tier rationale in the table above.

## Story pass
Every proposed edge read aloud as "X led to Y" or "same family":
- `fd_saturnKerolox` → `fd_gasGeneratorCeiling`: directly continues that node's OWN flavor text ("the last and
  largest of the simple gas-generator boosters"). **Reads true, strongest edge in the batch.**
- `fd_longMarchStorable` → `fd_clusteredThrustGrowth`: clustering led to more thrust per cluster. **Reads true.**
- `fd_titanTandem` + `pc_ntoHypergolics` → `fd_titanStorableConversion`: tandem staging AND NTO chemistry
  together were needed for Titan's storable conversion. **Reads true, genuine crossover** (doctrine #9).
- `fd_throttlingRocket` → `fd_ammoniaCombustionRefinement`: same base part (XLR99), direct continuation.
  **Reads true.**
- `pc_compositeSolid` + `hire_JPL` → `pc_pioneerUpperStage`: the composite-solid motor family AND the JPL charter
  together produced Pioneer's own upper stage. **Reads true, crossover.**
- `fd_restartableUpper` → `pc_juno_ClF3`: same base part (Juno), oxidiser-swap side-branch — **exact structural
  match to the existing `pc_fluorine`←`pc_ntoHypergolics` precedent.** Reads true.
- `fd_regenCooling` → `pc_orscDebut`: regenerative cooling (routing ALL propellant through the chamber wall) is
  the real prerequisite for staged combustion (routing it through a preburner too). **Confirmed this session —
  reads true.**

All edges pass. No re-litigation needed on any of them.

## Second Generation Capsules — PROPOSED (Gemini ‖ Voskhod)

Ground-truthed via `manifest/part-capabilities.tsv` (mass/category/modules) before designing. Real breakthrough
per generation, vs. band 2's Mercury‖Vostok: Gemini's OAMS = first US **powered orbital maneuvering**
(prerequisite for rendezvous); Voskhod's airlock = first **EVA/spacewalk** capability. Two mis-filings caught by
ground-truthing rather than trusting RO's x-bucket: `rn_surveyor_engines` (Surveyor's lander engine) sits in the
"Early Docking" bucket only by tech-node coincidence; `ROE-TD339`/`rn_surveyor_s_engine` sit in "Early Landing"
alongside Gemini's own heatshield for the same reason. Both belong with Surveyor, not here (next batch).

**Precedent check**: `int_mercuryCapsule` (T6) bundles Mercury's OWN RCS (`ROC-MercuryRCS2BDB`) into the capsule
node itself (not split out) — 6 parts, at the cap. Recovery hardware (parachutes/retro-pack/airbags) for BOTH
Mercury AND Vostok already lives together in ONE shared `edl_crewedRecovery` (T6) node, which also carries the
`MercuryHS` TPS-ladder upgrade. Following that exact structure rather than inventing a new one:

| Node (proposed id) | Title | Tier | Parent(s) | Payload |
|---|---|---|---|---|
| `int_geminiCapsule` | Powered Orbital Maneuvering | 7 | `int_mercuryCapsule` | parts: `ROC-GeminiCMBDB` (king), `ROC-GeminiEquipmentSectionBDB`, `ROC-GeminiNoseCapBDB`, `ROC-GeminiNoseconeAeroBDB`, `ROC-GeminiOAMSBDB`, `ROC-GeminiOAMSRCSBDB` — 6 parts, OAMS bundled in like Mercury bundled its own RCS |
| `int_voskhodCabin` | Inflatable-Airlock Descent Module | 7 | `int_vostokCapsule` | parts: `ROC-VoskhodCapsule` (king), `ROC-VoskhodAirlock` — the airlock IS the breakthrough, bundled with the capsule same as Gemini |
| `gnc_rendezvousDocking` | Orbital Rendezvous and Docking | 8 | `int_geminiCapsule` + `gnc_spacecraftRCS` | parts: `ROC-AgenaPort` (king, the actual docking mechanism), `ROC-AgenaFairing`, `ROC-GeminiNoseconeBDB` — genuinely separate capability (early Gemini flights flew without ever docking); deeper tier than the capsule itself since it needs OAMS to already exist |

**Extend existing `edl_crewedRecovery` (T6) directly** — no new node, no doctrine-4 conflict (none of these
part-ids match what's already there): add `ROC-GeminiParachuteBDB`, `ROC-GeminiParachuteDrogueBDB`,
`ROC-GeminiRetrogradeSectionBDB`, `ROC-ReentryControlSystemBDB`, `ROC-RetrogradeDecouplerBDB`,
`ROC-GeminiHSBDB`, `ROC-VoskhodRetroBooster` as parts, and the `GeminiHS` TPS-ladder upgrade — continuing the
exact `MercuryHS`→`GeminiHS` progression already flagged as band-3 debt.

### Open loose ends
- **`ROAdvCapsule`** ("Advanced Command Pod", mass 1.2t, `ModuleCommand`+`ModuleScienceContainer`, no nation/mission
  markers) — best guess is a generic/non-historical capsule option for this generation (no Gemini/Voskhod-specific
  hardware), but not confirmed. Needs a quick look before placing; not blocking the rest of this proposal.
- **Generic RCS-block catalog parts** in the "Early Docking" bucket (`HeavyRcs`, `RCSBlock_413`, `RCSBlock_550`
  + `restock-*` variants, `ROC-ApolloRCS`, `ROC-D2RCS`, `sasModule`, `dockingPort3`) aren't Gemini-specific — they're
  utility/catalog hardware becoming available at this tier for later ships (Apollo/Soyuz-analog) not yet built.
  Likely belong in a fixed-catalog dead-end off the procedural RCS king, matching the standing doctrine — lower
  priority, not placed above.
- Tier check: `int_geminiCapsule`/`int_voskhodCabin` at T7 (direct 1-tier succession from T6) and
  `gnc_rendezvousDocking` at T8 (needs the T7 capsule first) — same 2-generation-arc pattern as the engine spine,
  not flattened.

## Robotic Landers + Interplanetary Bus — PROPOSED (Surveyor ‖ Mariner)

Ground-truthed thrust/propellant/modules before designing (`manifest/part-capabilities.tsv` + original census).
Real breakthrough per lineage:

**Surveyor = first soft lunar landing.** The actual historical sequence is two-stage: a solid retro
(`rn_surveyor_retro`, Star-37) kills most of the descent velocity in one vacuum-start burn, then a THROTTLEABLE,
gimbaled liquid vernier cluster (`rn_surveyor_engines`, MMH+MON10, `ModuleGimbal` + a ~3.5:1 min/max thrust
range per the engine-stats data) flies the final controlled touchdown. `rn_surveyor_s_engine`/`ROE-TD339` are
the same vernier hardware as a single-unit part (parallels the LR87/LR87_11/LR87_Single multi-wrapper pattern
already seen in the engine spine).

Checked whether the retro rocket should instead fold into the existing `pc_retroKick` (T4, "Vacuum-Start Solid
Impulse" — mechanically compatible, no doctrine-4 conflict). Decided **against** folding it in: `pc_retroKick`'s
own story is "coming home from orbit" (Mercury retro/posigrade, Agena retro/spin), and Surveyor's retro isn't
that — splitting the retro from its vernier would break the one thing actually worth teaching here, which is the
COMBINATION (coarse solid braking → fine throttled liquid touchdown = a soft landing). Kept together as one
systems-level breakthrough instead, crossing over from both lineages.

| Node (proposed id) | Title | Tier | Parent(s) | Payload |
|---|---|---|---|---|
| `edl_continuousThrottleDescent` | Continuous-Throttle Descent | 7 | `pc_retroKick` + `gnc_spacecraftRCS` | parts: `rn_surveyor_engines` (king), `rn_surveyor_retro`, `rn_surveyor_s_engine`, `ROE-TD339` |

**Mariner = first 3-axis-stabilized probe bus.** `rn_mariner1_2` (Mariner 1/2, integrated bus+engine, simple
hydrazine attitude thruster) vs `ca_argo-mk2` (Mariner Mars/Venus bus, `ModuleKerbNetAccess` for
mapping/imaging, no engine of its own — bus is decoupled from propulsion choice) are a real generational step:
spin-stabilization (Pioneer's `pc_pioneerUpperStage`, already placed) can't hold a camera steady on a flyby
target; 3-axis stabilization can. That's the actual mechanism, not "better bus."

| Node (proposed id) | Title | Tier | Parent(s) | Payload |
|---|---|---|---|---|
| `gnc_threeAxisStabilizedBus` | Three-Axis Attitude Stabilization | 7 | `hire_JPL` + `pc_pioneerUpperStage` | parts: `ca_argo-mk2` (king), `ca_argo-mk2-solar`, `rn_mariner1_2` |

### Open loose ends (queued, not blocking)
- Confirm `rn_surveyor_s_engine`/`ROE-TD339` really are the same hardware as `rn_surveyor_engines` in
  single-unit form (assumed from matching titles/config, not independently verified beyond that).
- `pc_pioneerUpperStage` as a PARENT for the Mariner bus (spin-stabilization "led to" 3-axis stabilization as a
  contrast/supersession, not a direct technical dependency) is a softer story-pass edge than most others in this
  doc — flagged for the deferred story pass, not resolved now.

## Apollo Service Propulsion System — PROPOSED (`AJ10-137`)

Ground-truthed via `manifest/engine-stats.tsv`: 97.416 kN fixed thrust, 314s Isp, **Aerozine50+MON1**
(MON1 = NTO inhibited with 1% nitric oxide specifically to stop it corroding the tank over a week-plus
mission — not generic NTO), **pressureFed=True** (no turbopump — a deliberate reliability choice for an
engine with zero in-flight repair option), **ignitions=50**, **ullage=True**. This is the real Apollo Service
Propulsion System engine, not a mere precursor — the engine that has to work every single time to get a crew
out of lunar orbit.

The real mechanism/breakthrough here is **pressure-feed simplicity traded for restart reliability** — fewer
moving parts (no turbopump) at the cost of some performance, because this engine gets no do-over.

| Node (proposed id) | Title | Tier | Parent(s) | Payload |
|---|---|---|---|---|
| `fd_pressureFedRestart` | Pressure-Fed Multi-Restart Combustion | 8 | `pc_ntoHypergolics` + `fd_restartableUpper` + `pc_retroKick` | parts: [`ROE-AJ10-137`] |

**Ullage gate — FIRED (user confirmed).** `pc_retroKick` added as a third crossover parent: you need reliable
ullage-settling hardware (the posigrade motors already living there) before a long-coast, pressure-fed engine
can be trusted to relight. This resolves the band-2→3 deferred debt item ("thin in band 2, real breakthrough in
band 3") in the same move as placing `AJ10-137` — first 3-way crossover in band 3, an explicit exception to
"sparingly" because all three lanes (chemistry, restart, ullage) are genuinely load-bearing here, not decorative.

## Solids family (1962/64/66) — PROPOSED

Ground-truthed thrust/isp/propellant for every part before grouping (`manifest/engine-stats.tsv`). Confidence
varies more here than earlier sections — flagged where a placement is a best guess rather than a confirmed read.

**Two direct-adds surfaced while doing this pass** (checked against `pc_retroKick`'s existing `parts:` — no
doctrine-4 conflict):
- `ROC-GeminiRetroMECBDB` (Star-13E, deorbit motor) — this is Gemini's actual retro ENGINE, not the structural
  section (`ROC-GeminiRetrogradeSectionBDB`, already in the `edl_crewedRecovery` extension above). Missed on the
  first Gemini pass since it was filed under the "solids1964" bucket, not "Second Generation Capsules" — caught
  now by doing the broader sweep. Matches `pc_retroKick`'s own mechanism ("coming home from orbit") exactly.
- `ROE-TX280` (S-IV Ullage Motor) — a literal ullage-settling motor, same mechanism `pc_retroKick` already covers
  via the posigrade motors.
- (`ROC-GeminiRetroBDB`, listed as deprecated in the source .md, not in engine-stats — skip, not curated.)

**Confident groupings (real breakthrough, clear king):**

| Node (proposed id) | Title | Tier | Parent(s) | Payload |
|---|---|---|---|---|
| `pc_scoutMarkII` | Composite-Binder Solid Stages | 7 | `pc_scoutSolids` | parts: `ROE-Algol2`/`_Inline` (king), `ROE-Antares2`/`_Inline`, `ROE-AltairII`, `ROE-AltairIII` — direct "Mark II" successors of Scout's own already-placed stages |
| `pc_strapOnMarkII` | Composite-Binder Strap-On Solid | 7 | `pc_strapOnSolids` | parts: `ROE-Castor2`/`_Inline` (king), `ROE-M55` — M55's PBAA propellant + mid-range thrust fits this lineage better than the segmented boosters below, though tentative (flagged) |
| `pc_segmentedCasting` | Segmented Solid-Grain Casting | 7 | `pc_compositeSolid` | parts: `ROE-UA1204`/`ROE-UA1205` (king), `ROE-1204sepMotor`/`ROE-1205sepMotor`, `ROE-AJ260SLA`/`ROE-AJ260SLF` — real mechanism: casting propellant in stacked SEGMENTS instead of one piece, the only way to scale a solid motor past a single-cast grain's diameter limit. AJ-260's ~4x thrust jump over UA1205 is the same mechanism at larger scale, not a different one. **Parent fixed during the story pass below** — first draft had no parent at all |
| `pc_apogeeKickStage` | Solid Apogee-Kick Stage | 7 | `pc_retroKick` | parts: `ROE-Star13D`, `ROE-Star13`, `ROE-Star13A`, `ROE-Star37`, `ROE-Star37E` (king) — same STAR-motor family as Gemini's retro, but a genuinely different ROLE: precision apogee-kick/final-orbit injection for a satellite or probe, not deorbit. Homed by role, not hardware family |

### Open / unresolved (flagging rather than guessing)
- **`ROE-SR19`/`ROE-SR73`** (CTPB, 267.7/152 kN) — tentatively grouped with `pc_scoutMarkII` on thrust-class/era
  proximity alone; I don't have a confirmed real-world identity for these two, unlike everything else in this
  batch. Lowest-confidence call in this section.
- **`ROE-Alcyone1`** ("Alcyone 1 BE-3", NGNC propellant — an unusual propellant code I haven't cross-checked)
  — not placed anywhere above. Needs a real look before homing it.
- **M55's placement in `pc_strapOnMarkII`** is a propellant/thrust-class match, not a confirmed lineage — flagged
  for the deferred story pass.

## Naming + balance + story pass on the 4 later batches (Gemini‖Voskhod, Surveyor‖Mariner, AJ10-137, solids)

### Renames applied
Real mechanism found in the data for each, not guessed:
- `int_geminiCapsule`: "Maneuverable Orbital Cabin" → **"Powered Orbital Maneuvering"** — "maneuverable" was a
  capability claim; the mechanism is active hypergolic thrust replacing Mercury's passive/ballistic flight.
- `fd_pressureFedRestart`: "Pressure-Fed Restart Reliability" → **"Pressure-Fed Multi-Restart Combustion"** —
  "reliability" is the outcome, not the mechanism.
- `pc_scoutMarkII`: "Uprated Multi-Stage Solid Stack" → **"Composite-Binder Solid Stages"** — checked Algol/Altair's
  actual propellant codes rather than guessing: Altair goes `PSPC → PBAA → PBAN` (Mk I → II → III), a real,
  documented solid-propellant binder evolution (early polysulfide → composite polybutadiene binders), not just
  "uprated."
- `pc_strapOnMarkII`: "Uprated Strap-On Solid" → **"Composite-Binder Strap-On Solid"** — same confirmed mechanism
  (Castor 1 `PSPC` → Castor 2 `PBAA`, +46s Isp). Kept as a separate node from `pc_scoutMarkII` (different vehicle
  role: Scout's own stack vs. an external strap-on booster) rather than merged, but named consistently since
  it's genuinely the same underlying chemistry.

### Fan-out re-checks — resolved with real baselines, not re-flagged blind
Pulled each parent's ACTUAL existing dependents from `tree/nodes.yaml` instead of estimating:
- **`pc_ntoHypergolics`: corrected to 5 dependents, not 4.** My earlier count missed `pc_fluorine`, which also
  parents here (`tree/nodes.yaml:862`) — so the real band-2 baseline was 3 (`pc_fluorine`, `fd_longMarchStorable`,
  `fd_sovietStorable`), not 2, before band 3 added `fd_titanStorableConversion` and `fd_pressureFedRestart`. This
  is meaningfully higher than the >3 flag threshold. **Recommend accepting as flavor** (same call band 2 made on
  H-1<R-7): every one of the 5 dependents is a genuinely distinct vehicle lineage independently drawing on the
  same NTO-chemistry breakthrough (Chinese clustering, Soviet tandem, a fluorine gamble, Titan's conversion,
  Apollo's SPS) — that's what a real foundational chemistry node looks like, not a taxonomy smell. Your call to
  override.
- **`pc_retroKick`**: confirmed 0 band-2 baseline dependents, +3 from band 3 (`edl_continuousThrottleDescent`,
  `fd_pressureFedRestart`, `pc_apogeeKickStage`) = 3 total. At the threshold, not over — same "legitimate
  foundational enabler" pattern, no action needed.
- **`hire_JPL`**: confirmed 1 baseline (`charter_usEarly`) + 2 from band 3 = 3 total. At threshold; expected for
  a charter root (established exception).
- **`gnc_spacecraftRCS`**: confirmed **0** existing dependents in the signed-off tree (nothing currently parents
  onto it) + 2 from band 3 = 2 total. No concern — the "baseline unknown" flag from last pass is now closed.
- **`fd_restartableUpper`**: confirmed 1 baseline (`fd_spacecraftPropulsion`) + 2 from band 3 = 3 total. At
  threshold, acceptable.

### Story pass
- `int_mercuryCapsule` → `int_geminiCapsule`: blunt-body ballistic capsule led to a maneuverable follow-on with
  its own powered attitude/translation control. **Reads true.**
- `int_vostokCapsule` → `int_voskhodCabin`: direct — Voskhod WAS a modified Vostok sphere plus an airlock.
  **Reads true, strong edge.**
- `int_geminiCapsule` + `gnc_spacecraftRCS` → `gnc_rendezvousDocking`: powered maneuvering AND fine RCS control
  together are both required to actually close on and dock with a target. **Reads true, genuine crossover.**
- `pc_retroKick` + `gnc_spacecraftRCS` → `edl_continuousThrottleDescent`: coarse solid braking heritage AND
  throttleable-RCS heritage together produced a soft landing. **Reads true, genuine crossover.**
- `pc_compositeSolid` → `pc_segmentedCasting`: composite-grain chemistry led to segmented casting as the
  manufacturing scale-up past a single-cast grain's diameter limit. **Reads true — this edge didn't exist before
  this pass; the first draft had no parent at all, caught here.**
- `pc_retroKick` → `pc_apogeeKickStage`: same single-precise-vacuum-burn mechanism, retargeted from deorbit to
  final-orbit injection. **Reads true.**
- `pc_ntoHypergolics` + `fd_restartableUpper` + `pc_retroKick` → `fd_pressureFedRestart`: already justified when
  the ullage crossover was fired — all three lanes genuinely load-bearing. **Reads true.**
- `pc_scoutSolids` → `pc_scoutMarkII`, `pc_strapOnSolids` → `pc_strapOnMarkII`: direct continuations, now backed
  by the confirmed binder-chemistry data above. **Read true.**
- **`hire_JPL` + `pc_pioneerUpperStage` → `gnc_threeAxisStabilizedBus`: still the weakest edge in the document,
  and I don't think it should just be noted a third time.** `pc_pioneerUpperStage`'s parts are Pioneer's solid
  UPPER-STAGE BOOSTER, not an attitude-control system — the connection to 3-axis stabilization is "spin
  stabilization got superseded by a different approach to the same problem," not a technical building block.
  Real alternative: parent `gnc_threeAxisStabilizedBus` off `gnc_spacecraftRCS` instead (the actual thruster
  hardware 3-axis control needs) and drop `pc_pioneerUpperStage` as a parent entirely. **This needs your call,
  not mine** — it's a real re-architecture, not a naming tweak.

All other edges pass; the two items above (`pc_ntoHypergolics` fan-out, the Mariner parent) are genuine open
decisions, not just re-statements of earlier flags.
