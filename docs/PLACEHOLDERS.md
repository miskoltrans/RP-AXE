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

> **STUB:** `build_tree` currently emits each grant as a `partUpgrade` (flagged provisional). The
> real emission — an avionics-plugin tier gate / a tracking-station facility unlock — is still to be
> wired. The `grants:` **data is stable**; only its emission will evolve. Do not hand-edit the cfg.

## Track 1 — Avionics (ONE track, mapped to RP-1 "Science-Core")
Decision (user, 2026-07-02): a **single** avionics track. RP-1's Near-Earth and Deep-Space avionics
lines are `DROP`ped; the 8 **Science-Core** tiers are the tree-visible avionics progression. Each
node `grants:` the corresponding avionics-plugin tier.

| RP-1 Science-Core tier | → RP-AXE node (draft) | plugin tier | milestone |
|---|---|---|---|
| basicAvionics | gnc_… | ? | band 1 |
| avionicsPrototypes | gnc_… | ? | band 1 |
| earlyAvionics | gnc_… | ? | band 1 |
| postWarAvionics | gnc_… | ? | band 1 |
| improvedAvionics | gnc_… | ? | band 2 |
| matureAvionics | gnc_… | ? | band 2 |
| largeScaleAvionics | gnc_… | ? | band 2/3 |
| interplanetaryProbes | gnc_… | ? | band 3 |

**OPEN — user's call:** these 8 RP-1 tiers ↔ the avionics plugin's **13-tier** ladder is *not* 1:1.
Fill the `plugin tier` column (and confirm discipline: GuidanceControl vs Computing) before authoring.

## Track 2 — Deep Space Network / tracking-station levels (KEEP, definitely in-game)
5 levels, each a **Telecommunications** node that `grants:` the tracking-station facility level
(extends comms range / downlink). NOT plugin-covered — real gating.

| RP-1 | → RP-AXE node (draft) | milestone |
|---|---|---|
| RP0Level2TrackingStation | tel_… | band 1 |
| RP0Level3TrackingStation | tel_… | band 1/2 |
| RP0Level4TrackingStation | tel_… | band 2 |
| RP0Level5TrackingStation | tel_… | band 2/3 |
| RP0Level6TrackingStation | tel_… | band 3 |

## Agent checklist (per milestone)
1. Read the milestone partlist; collect `KEEP-avionics` / `KEEP-dsn` items whose tier lands here.
2. For each, author a **capability node** (no `parts:`), naming the enabling breakthrough (naming gate).
3. Give it `grants: [<the placeholder id>]`.
4. Home it by the usual rules (discipline lane, tier, parents), then `build_tree` + verify.
