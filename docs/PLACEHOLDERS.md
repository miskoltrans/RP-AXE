# Provisional Placeholder Parts → Nodes

How RP-AXE turns **capability placeholders** — things that are *not* physical parts or RealFuels
engine upgrades — into tree nodes. Today that means two families lifted from RP-1's tech tree and
shelved as `REFERENCE` during curation, now included **provisionally**:

- the **avionics** capability ladder, and
- the **Deep Space Network / tracking-station** levels.

## Disposition convention (in the milestone partlists)
The `curated` column / inline tag in `manifest/*-partlist.{tsv,md}` tells an agent what to do:

| tag | meaning |
|---|---|
| `yes` / `KEEP-engine` / `KEEP-*` | curated — PLACE it |
| `KEEP-avionics` | provisional avionics-tier placeholder — place as a **capability node** |
| `KEEP-dsn` | provisional DSN / tracking-station placeholder — place as a **capability node** |
| `DROP-*` | explicitly dropped — do NOT place |
| `REFERENCE-*` | *(retired)* was "don't place"; superseded by `KEEP-*` / `DROP-*` |

When an agent builds a milestone, it **places the `KEEP-avionics` / `KEEP-dsn` items** in that
milestone's partlist — as capability nodes, not physical parts.

## The `grants:` node field
Capability nodes carry no `parts:`; they carry **`grants:`** — a list of capability/facility unlocks.
`build_tree` emits each grant into the node's `Unlocks {}` block and counts it toward node content
(so a part-less node isn't treated as empty / hidden). Render badge shows it as `+Ng`.

```yaml
- id: gnc_avionicsTierN
  title: "..."               # name the enabling breakthrough, per the naming gate
  discipline: GuidanceControl
  tier: <milestone tier>
  parents: [...]
  grants: [avionicsTierN]    # what researching this node unlocks
```

> **Emission (DONE for display):** each grant is emitted as a real, visible R&D **display token** in
> `design/Tree/AxeGrantUpgrades.cfg` — a `PARTUPGRADE` bound to the granting node (`techRequired`, set
> in `AxePartPlacement.cfg`), `entryCost 0`, retitled/redescribed in AXE language with real per-tier
> stat deltas. `AXE.dll`'s `AxeGrantUpgradeUnlock` auto-marks them unlocked on research (no buy step),
> so a node reads like RP-1's own avionics nodes. The tokens carry **no stat MODULE** — the actual
> effect is applied elsewhere (avionics tier: `ModuleAxeAvionics` reads the researched node; DSN level:
> CustomBarnKit `@TRACKING` + `AxeTrackingStationGate`). The `grants:` **data is stable**; do not
> hand-edit the generated cfg.

## The implementation backlog — [IMPL-TODO.md](IMPL-TODO.md) (generated)
REFERENCE / provisional content lives in the tree **on purpose** — it's there to build against when
we implement it, not to be dropped. Every `grants:` capability stub is auto-collected into
`docs/IMPL-TODO.md` on each `build_tree` run, grouped by family (DSN levels, avionics tiers, …) with
a note on what game-side work each still needs. That generated file is the single checklist of "in
the tree, but its effect isn't wired yet."

For anything that needs implementation but isn't a `grants:` capability (e.g. a physical part whose
special behaviour needs a plugin), add an **`impl_todo: "<what's missing>"`** field to its node: it
lands in the same backlog and stamps a `// NEEDS-IMPL:` comment into the emitted cfg.

## Track 1 — Avionics ✅ SHIPPED (mapped to RP-1 "Science-Core" + "Deep-Space")
Original decision (user, 2026-07-02) was a **single** track: RP-1's Near-Earth and Deep-Space lines
`DROP`ped, the Science-Core tiers as the only tree-visible progression. **Near-Earth stays dropped;
Deep-Space came back** as the Unshielded/Radiation-Shielded second axis (AVIONICS_SPEC "Axis 2",
built 2026-07-14) — its own serial `shd_*` chain mirroring the Guided rungs one-for-one, because
RP-1's real Deep-Space ladder is a per-tier data table, not a multiplier on Near-Earth.

**The 8-tiers-↔-13-tier question is answered by what shipped:** all 13 non-`start` plugin rungs are
tree-visible (the extra 5 came from AVIONICS_SPEC's late Computing-era rungs), so the mapping is 1:1
in both directions. Discipline: **GuidanceControl** for the early rungs and for the whole `shd_*`
chain, **Computing** from the digital-computer rung onward. Ground truth = the `TIER` blocks in
`design/Tree/AxeAvionicsCore.cfg`; this table mirrors them.

| RP-1 tier | Guided node (`tech =`) | T | Shielded node (`shTech =`) | T |
|---|---|--:|---|--:|
| *(floor)* | `start` | 0 | — | |
| postWarAvionics | `gnc_postWarAvionics` | 1 | — | |
| avionicsPrototypes | `gnc_avionicsPrototypes` | 2 | — | |
| earlyAvionics | `gnc_earlyAvionics` | 4 | — | |
| basicAvionics | `gnc_basicAvionics` | 5 | `shd_basicAvionics` | 6 |
| interplanetaryProbes | `gnc_interplanetaryAvionics` | 7 | `shd_interplanetaryAvionics` | 8 |
| improvedAvionics | `comp_digitalGuidanceComputer` | 8 | `shd_digitalGuidanceComputer` | 9 |
| matureAvionics | `comp_realTimeFlightComputer` | 9 | `shd_realTimeFlightComputer` | 10 |
| largeScaleAvionics | `comp_networkedAvionics` | 10 | `shd_networkedAvionics` | 11 |
| advancedAvionics | `comp_multiplyRedundantFlightComputer` | 11 | `shd_multiplyRedundantFlightComputer` | 12 |
| nextGenAvionics | `comp_distributedAvionicsBus` | 12 | `shd_distributedAvionicsBus` | 13 |
| longTermAvionics | `comp_softwareDefinedFlightControl` | 13 | `shd_softwareDefinedFlightControl` | 14 |
| internationalAvionics | `comp_interoperableAvionicsStandard` | 14 | `shd_interoperableAvionicsStandard` | 15 |
| modernAvionics | `comp_commercialOffTheShelfAvionics` | 15 | `shd_commercialOffTheShelfAvionics` | 16 |

**How the gate actually works — not through the grants.** `ModuleAxeAvionics` reads these node ids
directly (`ApplyTier()` walks `tech =`, `ApplyShieldedTier()` walks `shTech =`) and `guidanceTech`
gates whether guidance can activate at all. The 23 `Science-Core-*` / `Deep-Space-*` grant tokens are
**presentation only** — see the Emission note above. Two consequences worth remembering: the tokens
can never be the thing that breaks the ladder, and a **renamed node silently freezes a tier**
(`GetTechnologyState` returns `Unavailable` for an unknown id, no error) — which is exactly the
2026-07-08 bug in AVIONICS_SPEC. `check_tech_refs.py` is the guard; keep those ids in it.

## Track 2 — Deep Space Network / tracking-station levels ✅ SHIPPED
10 levels (`RP0Level2…11TrackingStation`), each a **Telecommunications** node that `grants:` the
tracking-station facility level (extends comms range / downlink). **All placed** along the comms
ladder (`tel_dopplerRanging` → `tel_opticalDownlink`), and the effect is real in-game, in three
pieces: the 11-level ladder + DSN gain from `design/Settings/AxeTrackingStation.cfg` (CustomBarnKit
`@TRACKING`, consumed by RealAntennas); the per-level tech gate generated into
`design/Tree/AxeFacilityGates.cfg` (`AXEBUILDINGTECHS`, derived from these very grants); and
enforcement by `AXE.dll`'s `AxeTrackingStationGate`. Smoke-tested in-game.

| grant | → RP-AXE node | tier |
|---|---|---|
| RP0Level2TrackingStation | tel_dopplerRanging | T5 |
| RP0Level3TrackingStation | tel_pcmTelemetry | T6 |
| RP0Level4TrackingStation | tel_deployableHighGainDish | T7 |
| RP0Level5TrackingStation | tel_phasedArrayRelay | T8 |
| RP0Level6TrackingStation | tel_blockCoding | T9 |
| RP0Level7TrackingStation | tel_convolutionalCoding | T10 |
| RP0Level8TrackingStation | tel_xBandDownlink | T11 |
| RP0Level9TrackingStation | tel_antennaArraying | T12 |
| RP0Level10TrackingStation | tel_kaBandDownlink | T13 |
| RP0Level11TrackingStation | tel_opticalDownlink | T14 |

Ground station TL tracks the facility level directly (`GroundStationTechLevel =
round(MaxTL × normalisedFacilityLevel)`, career only — sandbox/science pin it to max), so with an
11-level ladder and `MaxTL = 10` each rung is worth exactly one ground tech level. That is what makes
the two band rungs land where they do: `RP0Level8` puts the ground at TL7, which is where RO gives the
DSN its X-band dish, and `commsTL7` on the same node clears `BandInfo[X].TechLevel = 7` onboard —
both ends of the link open together. `RP0Level10` + `commsTL9` do the same for Ka.

## Agent checklist (per milestone)
1. Read the milestone partlist; collect `KEEP-avionics` / `KEEP-dsn` items whose tier lands here.
2. For each, author a **capability node** (no `parts:`), naming the enabling breakthrough (naming gate).
3. Give it `grants: [<the placeholder id>]`.
4. Home it by the usual rules (discipline lane, tier, parents), then `build_tree` + verify.
