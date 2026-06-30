# RP-AXE — PARTUPGRADE Curation (T3)

Curates the **626 RP-1-authored `PARTUPGRADE`s** that are absent under AXE (no RP-1) into a
final keep-list. Builds on the audit ([`upgrade_audit.py`](../tools/upgrade_audit.py) →
`manifest/upgrades-absent.tsv`); curation is reproducible via
[`tools/curate_upgrades.py`](../tools/curate_upgrades.py) → **`manifest/upgrades-curated.tsv`**.

Why upgrades matter: the part diff only sees `PART` nodes, so PARTUPGRADEs are invisible to it.
They are also AXE's **discipline-scatter mechanism** — one part, breakthrough-gated config
improvements unlocked across enabling-discipline nodes (RESTART.md T1 note). A node's payload is
`unlocks:{parts:[…], upgrades:[…]}`.

## Result

| Disposition | N | Bucket | Meaning |
|---|---:|---|---|
| `KEEP-engine` | 462 | KEEP | RFUpgrade_X whose engine `CONFIG X` lives on a **curated** engine |
| `KEEP-engine-typelevel` | 15 | KEEP | RealFuels per-engine-**TYPE** tech levels (Solids/Nuclear/RCS/Cryo…) |
| `KEEP-capability` | 13 | KEEP | procedural-mass, cockpit-ceiling, sat-bus tech on curated parts |
| `DROP-orphan` | 53 | DROP | RFUpgrade_X for a CONFIG **absent** from our RO install |
| `DROP-axed-career` | 36 | DROP | KCT (22) + facility (10) + airlaunch (4) — career layer axed |
| `DROP-superseded-avionics` | 35 | DROP | `Tree/ProceduralAvionics.cfg` — AXE rewrote avionics |
| `REVIEW-keep-candidate` | 10 | REVIEW | `HDD-Upgrade-*` Kerbalism data-storage subsystem — **scope call** |
| `EXPERIMENTAL-engine` | 2 | EXP | CONFIG only on an uncurated engine → rides it to the side-node |
| **Total** | **626** | | **490 KEEP · 124 DROP · 12 REVIEW/EXP** |

The **490 keepers** map to **108 distinct RP-1 `techRequired` nodes** — that, not 490 individual
edits, is the size of the P2 remap (RP-1 node → AXE node).

## A. Engine progression (532 → 462 keep / 53 orphan / 2 experimental + 15 type-levels)

`Tree/TREE-Engines.cfg` defines, per real engine variant, a 5-part block:

1. `PARTUPGRADE { name = RFUpgrade_<config>; techRequired = …; deleteme = 1 }` — the tree icon.
2. `PART { name = RFUpgrade_engineConfigSource_<config>; engineType = <engine> }` — links the
   config to its engine.
3. `@PART[…source…]:AFTER[RealismOverhaulEngines] %MODULE[…EngineConfigs] %CONFIG[<config>]` — sets `specLevel`.
4. `@PARTUPGRADE[RFUpgrade_<config>]:AFTER[…]` — description.
5. `!PART[…source…]:AFTER[…]` — deletes the dummy source.

Separately, a top-of-file `@PART[*]:HAS[@MODULE[Module*EngineConfigs]]:BEFORE[RealismOverhaulEnginesPost]`
block carries, per config, `@CONFIG[<config>] { %techRequired = …; %cost = …; *@PARTUPGRADE[…]/deleteme -= 1 }`
— the **techRequired/cost placement** plus the deleteme decrement.

**Orphan filter = RP-1's own `deleteme` mechanism, computed offline.** Each upgrade starts
`deleteme = 1`; if its engine `CONFIG` is present on a live part, `deleteme -= 1` → 0; then
`Tree/UpgradeCleanup.cfg` runs `!PARTUPGRADE:HAS[#deleteme[>0]]:AFTER[zzzRP-0]` and deletes any
upgrade still flagged. We reproduce this by parsing the live `ModuleManager.ConfigCache`
(`Module*EngineConfigs` → `CONFIG{name}` → host PART) and cross-referencing the 1820 curated parts:

- **462 KEEP-engine** — config on a curated engine.
- **53 DROP-orphan** — config absent from our installed RealismOverhaulEngines. RP-1 authored
  these against an RO version with engine variants we don't ship (e.g. `Merlin1B` — RO ships
  Merlin1A/1C/1D, not 1B; `NK-32`, `11D23`, `RD-0235`). Harmless either way: **vendoring the
  whole file self-filters them via `deleteme`/UpgradeCleanup at load.**
- **2 EXPERIMENTAL-engine** — `RFUpgrade_30x_NK-33`, `RFUpgrade_8x_NK-43`: config only on
  uncurated SXT K-1 parts (`SXTK1BaseLarge`, `SXTK1Base5m`) → they follow their part to the
  Experimental side-node, off the balanced tree.

`Tree/RFTechLevels.cfg` (**15 KEEP-engine-typelevel**) is the orthogonal RealFuels system: per
engine **type** (Solids/Nuclear/RCS/Cryo/…) it raises the RF tech level at tech nodes. Type-level,
not per-config — all types are present, so all keep. (This is *not* the legacy `techLevel` knob RO
dropped; it's the `RF_TECHLEVELS`/`TLTECH*` map.)

**Vendor strategy (P2):** vendor `Tree/TREE-Engines.cfg` **whole** + `Tree/UpgradeCleanup.cfg`
(self-filters against whatever engines are installed, robust to RO version drift) +
`Tree/RFTechLevels.cfg`. Then **remap every `techRequired` → AXE node** (the 108-node map). The
companion `@CONFIG` techRequired/cost patches are *in* TREE-Engines.cfg, so they ride along — just
remap their node names too.

## B. Capability keepers (13)

All pair with a companion `%UPGRADES { UPGRADE { name__ = … } }` patch on the **target part** —
that patch must be vendored with the bare `PARTUPGRADE`.

- **`PFTech-Fairing-I…VI`** (6) — procedural fairing/structure `minDensity` (mass) tech. Targets
  every procedural part (`@PART:AFTER[RealismOverhaul]` over `ProceduralFairingSide`/`ModuleROTank`/
  `ProceduralPart`). Procedural is AXE's workhorse → **keep**. Companion: `Tree/PFTechLevels.cfg`.
- **`X2CockpitUpgrade`** (1) — raises `crewDeathAltitude` 30 km → 75 km on `RO-X1Cockpit` (curated).
  Companion: `Tree/CockpitUpgrades.cfg`.
- **`RP-1-PayloadTech-EarlyAvionics`, `-Axial`, `RFTech-ComSat-II/III`, `RFTech-NavSat-II/III`** (6)
  — ComSat/NavSat bus avionics + equipment tech on `RP-1-CommunicationSat` / `RP-1-NavigationSat`
  (both curated, vendored RP-1-authored buses). Companion: `Tree/PayloadLevels.cfg` +
  `Parts/ContractSat/{Communication,Navigation}Sat.cfg`.

## C. DROP (124)

- **53 DROP-orphan** — see §A.
- **35 DROP-superseded-avionics** (`Tree/ProceduralAvionics.cfg`) — AXE ships its own
  `ModuleAxeAvionics` TIER ladder (settled decision); RP-1's procedural-avionics upgrades are dead.
- **36 DROP-axed-career** — `Tree/KCTUpgrades.cfg` (22, engineer/researcher efficiency),
  `Tree/TechFacilityUpgrades.cfg` (10), `Tree/AirlaunchTechlevels.cfg` (4, RP-0/KCT airlaunch
  capability — "not a part you can use", consumed by the axed airlaunch plugin).

## D. Open decision — HDD data-storage (10, `REVIEW-keep-candidate`)

`HDD-Upgrade-Early … HDD-Upgrade-2020` scale science **data-storage capacity** (6.3 kB → 3 TB)
across tech nodes. This is **not** part of the avionics rewrite — it's the **Kerbalism** hard-drive
system (`Science/HardDriveConfigs.cfg`, `KERBALISM_HDD_SIZES`, applied via `RO-KerbalismHardDrives`
/ `RP-0-KerbalismHardDrives` to `ModuleScienceContainer`/`ModuleCommand`/`proceduralAvionics`/
`ROT-ProbeCore` — the last two curated). AXE uses Kerbalism, so it *can* keep this; the cost is
vendoring/maintaining a ~1000-line Kerbalism HDD subsystem. **Decision deferred to the user** — keep
the data-storage progression axis, or drop it and let parts use stock/Kerbalism default capacities.

## Reproduce

```
python tools/upgrade_audit.py      # -> manifest/upgrades-absent.tsv (needs a fresh ConfigCache)
python tools/curate_upgrades.py    # -> manifest/upgrades-curated.tsv
```

The curated TSV columns: `name · techRequired · sourcefile · disposition · companion_patch ·
reason · title`. It is the input to the **P2** tree-placement + `techRequired → AXE-node` remap.
