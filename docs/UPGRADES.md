# RP-AXE — PARTUPGRADE Curation (T3)

Curates the **626 RP-1-authored `PARTUPGRADE`s** that are absent under AXE (no RP-1) into a
final keep-list. Builds on the audit ([`upgrade_audit.py`](../tools/upgrade_audit.py) →
`manifest/upgrades-absent.tsv`); curation is reproducible via
[`tools/curate_upgrades.py`](../tools/curate_upgrades.py) → **`manifest/upgrades-curated.tsv`**.

Why upgrades matter: the part diff only compares `PART` nodes, so PARTUPGRADEs are invisible to it.
They are also AXE's **discipline-scatter mechanism** — one part, breakthrough-gated config
improvements unlocked across enabling-discipline nodes (RESTART.md T1 note). A node's payload is
`unlocks:{parts:[…], upgrades:[…]}`.

## Result — 553 KEEP · 45 REFERENCE · 28 DROP (+32 addendum below → 576 KEEP / 658 total)

| Disposition | N | Bucket | Meaning |
|---|---:|---|---|
| `KEEP-engine` | 462 | KEEP | RFUpgrade_X whose engine `CONFIG X` lives on a **curated** engine |
| `KEEP-engine-dormant` | 53 | KEEP | RFUpgrade_X whose CONFIG is absent now — vendored **inert**, wakes if a mod adds it |
| `KEEP-engine-typelevel` | 15 | KEEP | RealFuels per-engine-**TYPE** tech levels (Solids/Nuclear/RCS/Cryo…) |
| `KEEP-capability` | 23 | KEEP | procedural-mass (6), cockpit-ceiling (1), sat-bus (6), **HDD data-storage (10)** |
| `REFERENCE-avionics` | 35 | REFERENCE | superseded by AXE's TIER ladder; keep `AVIONICSCONFIGS` as impl reference |
| `REFERENCE-comms-dsn` | 10 | REFERENCE | DSN tracking-station tech gating; ref for AXE comms/ground-station axis |
| `DROP-axed-career` | 26 | DROP | KCT engineer/researcher efficiency (22) + airlaunch (4) |
| `DROP-no-curated-host` | 2 | DROP | N1 cluster configs (`30x_NK-33`, `8x_NK-43`) — no curated cluster part |
| **Total** | **626** | | |

The **active keepers** (everything KEEP except the 53 dormant) map to **115 distinct RP-1
`techRequired` nodes** — that, not 553 edits, is the size of the P2 remap (RP-1 node → AXE node).

## A. Engine progression (532)

`Tree/TREE-Engines.cfg` defines, per real engine variant, a 5-part block: a
`PARTUPGRADE { name = RFUpgrade_<config>; techRequired = …; deleteme = 1 }` icon; a
`PART { … engineType = <engine> }` linking the config to its engine; a `%CONFIG[<config>]` spec
patch; a description patch; and a delete of the dummy source. Separately a top-of-file
`@PART[*]:HAS[@MODULE[Module*EngineConfigs]]` block carries, per config,
`@CONFIG[<config>] { %techRequired = …; %cost = …; *@PARTUPGRADE[…]/deleteme -= 1 }` — the
**techRequired/cost placement** plus the deleteme decrement.

**Orphan filter = RP-1's own `deleteme` mechanism, computed offline.** Each upgrade starts
`deleteme = 1`; if its engine `CONFIG` is present on a live part, `deleteme -= 1` → 0; then
`Tree/UpgradeCleanup.cfg` runs `!PARTUPGRADE:HAS[#deleteme[>0]]:AFTER[zzzRP-0]` and deletes any
upgrade still flagged. We reproduce this by parsing the live `ModuleManager.ConfigCache`
(`Module*EngineConfigs` → `CONFIG{name}` → host PART) and cross-referencing the 1820 curated parts:

- **462 KEEP-engine** — config on a curated engine.
- **53 KEEP-engine-dormant** — config absent from our installed RealismOverhaulEngines (RP-1
  authored these against an RO version with variants we don't ship — e.g. `Merlin1B` when RO ships
  Merlin1A/1C/1D; `NK-32`; `11D23`). **Decision: keep them (see §E).** Vendored whole, they stay
  inert via deleteme and **wake automatically if a mod later supplies that engine config**.
- **2 DROP-no-curated-host** — `RFUpgrade_30x_NK-33`, `RFUpgrade_8x_NK-43`: these are the **N1
  Block A / Block B** cluster configs (30× NK-15/33, 8× NK-15V/43). The only live host is the
  uncurated SXT N1 stage parts (`SXTK1BaseLarge` / `SXTK1Base5m`, titled "N1 Block A/B"). We curate
  the standalone engines (`ROE-NK33`/`ROE-NK43`) but not the cluster bases, so no curated part can
  use these configs → **sacked**. (Revisit if AXE ever curates/authors an N1 first stage.)

`Tree/RFTechLevels.cfg` (**15 KEEP-engine-typelevel**) is the orthogonal RealFuels system: per
engine **type** (Solids/Nuclear/RCS/Cryo/…) it raises the RF tech level at tech nodes. All types
are present → all keep. (Not the legacy `techLevel` knob RO dropped; it's the `RF_TECHLEVELS` map.)

**Vendor strategy (P2):** vendor `Tree/TREE-Engines.cfg` **whole** + `Tree/UpgradeCleanup.cfg` +
`Tree/RFTechLevels.cfg`, then **remap every `techRequired` → AXE node** (the 115-node map). The
companion `@CONFIG` techRequired/cost patches are *in* TREE-Engines.cfg, so they ride along.

## B. Capability keepers (23)

All pair with a companion `%UPGRADES { UPGRADE { name__ = … } }` patch on the **target part** —
vendor that patch with the bare `PARTUPGRADE`.

- **`PFTech-Fairing-I…VI`** (6) — procedural fairing/structure `minDensity` (mass) tech. Targets
  every procedural part. Procedural is AXE's workhorse → keep. Companion: `Tree/PFTechLevels.cfg`.
- **`X2CockpitUpgrade`** (1) — `crewDeathAltitude` 30→75 km on `RO-X1Cockpit` (curated).
  Companion: `Tree/CockpitUpgrades.cfg`.
- **`RP-1-PayloadTech-*`, `RFTech-{Com,Nav}Sat-II/III`** (6) — ComSat/NavSat bus avionics +
  equipment tech on `RP-1-CommunicationSat` / `RP-1-NavigationSat` (both curated). Companion:
  `Tree/PayloadLevels.cfg` + `Parts/ContractSat/*`.
- **`HDD-Upgrade-Early…2020`** (10) — **KEEP** (decided). Scales science **data-storage capacity**
  (6.3 kB → 3 TB) across tech nodes. This is the **Kerbalism** hard-drive system
  (`Science/HardDriveConfigs.cfg`, `KERBALISM_HDD_SIZES`, applied via `RO-/RP-0-KerbalismHardDrives`
  to `ModuleScienceContainer`/`ModuleCommand`/`proceduralAvionics`/`ROT-ProbeCore` — last two
  curated). AXE uses Kerbalism, so it keeps the data-storage progression axis. P2 must vendor the
  ~1000-line HDD subsystem and remap the 10 nodes. Companion: `Tree/HardDriveUpgrades.cfg` +
  `Science/HardDriveConfigs.cfg`.

## C. Reference — kept for design, not vendored as live upgrades (45)

### C1. Avionics (35, `Tree/ProceduralAvionics.cfg`)

AXE already **supersedes** RP-1's procedural-avionics progression: `ModuleAxeAvionics` +
`design/Tree/AxeAvionicsCore.cfg` reimplement the per-tier factors as a 13-node `TIER` ladder, and
`AxeAvionicsCore.cfg:115-118` **actively deletes** these icons
(`!PARTUPGRADE[Near-Earth-*|Science-Core-*|Deep-Space-*]:FINAL`). So the 35 are dead as a
*mechanism*. Their value is the source `AVIONICSCONFIGS` data — kept as the **implementation
reference**. AXE's TIER ladder already covers `massFactor`/`powerFactor` (Near-Earth) and
`scMassFactor`/`scPowerFactor`/`scDensity`/`scAllowAxial` (Science-Core), 1:1 (`tools/avionics_compare.py`).

**What RP-1 encodes, and what AXE has built** (per-tier; updated 2026-07-07):

| RP-1 `TECHLIMIT` field | AXE status | note |
|---|---|---|
| `massFactor` / `powerFactor` | ✅ in TIER ladder | Near-Earth, verbatim |
| `scMassFactor` / `scPowerFactor` / `allowAxial` | ✅ in TIER ladder | Science-Core |
| `costExponent` / `costConstant` / `costFactor` | ✅ **built** | `GetModuleCost`/`IPartCostModifier`, RP-1's hump curve verbatim (see below) |
| `hasScienceContainer` (from `basicAvionics`) | ✅ **built** | gated in `ModuleAxeAvionics`, checked at flight start like RP-1's own `Start()` logic |
| `kosDiskSpace`, `kosECPerInstruction`, `kosSpaceCostFactor`, `kosSpaceMassFactor` | ✅ **bridge built, inert** | reflected onto a `kOSProcessor` module if present; no-op today since kOS isn't an AXE dependency |
| `interplanetary` (Deep-Space range model) | ❌ dropped (intended) | **Deep-Space does not exist in AXE**; range = comms (RealAntennas), not avionics |

**Cost / hardware-efficiency optimization.** Avionics hardware carries a funds cost, and that cost is
where **hardware-efficiency optimization** shows up across tech progression. RP-1's curve is the
reference and tells the story well — it is a **hump, not a monotonic drop**:
`cost = (M^0.46172 + 3.034)·costFactor`, with `costFactor` rising through the early era (sophistication
costs more), peaking, then falling as manufacturing matures:

```
start 48.12 → prototypes 51.56 → early 54.13 → basic 56.84 → interplanetary 59.68 →
improved 62.67 → mature 65.80 (peak ~1964-66) → largeScale 58.85 → advanced 47.08 →
nextGen 37.67 → longTerm 30.13 → international 24.11 → modern 19.29
```

Contrast the mass/power factors AXE already has, which fall **monotonically** (pure efficiency gain):
the cost hump is a distinct, richer signal — early IC/transistor avionics are expensive before
mass-production efficiency brings advanced hardware down below where it started. Built as
`costExponent`/`costConstant`/`costFactor` on the `TIER` nodes + `GetModuleCost` in
`ModuleAxeAvionics` (same polynomial as mass, keyed off the as-built load, frozen at launch);
Science-Core cost is `scCostFactor` flat. See `docs/AVIONICS_COMPARISON.md` §H.

kOS integration is wired the same duck-typed-reflection way as the RealFuels/ProceduralPart bridge —
it will activate automatically (per-tier disk space, EC-per-instruction, cost, mass) the moment kOS is
added as a dependency, rather than needing a follow-up implementation pass. See
`docs/AVIONICS_COMPARISON.md` §I. Only Deep-Space/`interplanetary` stays intentionally dropped.

### C2. Comms / DSN tracking-station (10, `Tree/TechFacilityUpgrades.cfg`)

`RP0Level2…11TrackingStation` gate the **Deep Space Network tracking-station** tech levels to comms
research nodes (`lunarRangeComms` → `modernComms`), each adding DSN gain (dB). In RP-1 these gate
the *ability to upgrade the Tracking Station building* (a career/facility mechanic AXE axes), **but
the DSN-tech-by-comms-node progression is reference-worthy** — it lines up with the **live**
`RealAntennas` `commsTL1-10` upgrades (`manifest/upgrades-live.tsv`), which AXE keeps via the mod.
Reference for AXE's comms/ground-station axis when P2 places the comms branch.

## D. DROP (28)

`DROP-axed-career` (26):
- **`rp0EngineerUpgrade*` (12) + `rp0ResearcherUpgrade*` (10)** (`Tree/KCTUpgrades.cfg`) — KCT
  personnel build-rate / research-rate efficiency multipliers. No AXE KCT; `description = unset`,
  no part payload → genuinely dead, no reference value.
- **`airlaunchTL1…4` (4)** (`Tree/AirlaunchTechlevels.cfg`) — tree-icon mirrors of RP-1's airlaunch
  capability gates, consumed by the axed RP0.dll/KCT airlaunch subsystem. The icons do nothing
  without the plugin. (Airlaunch itself is an interesting sacked feature — parked in
  RESTART.md "Parked ideas"; the reusable reference is `SCMData/AirlaunchLevels.cfg` +
  `Source/RP0/SpaceCenter/AirlaunchTechLevel.cs` / `UI/KCT/GUI_Airlaunch.cs`, not these upgrades.)

`DROP-no-curated-host` (2):
- **`RFUpgrade_30x_NK-33`, `RFUpgrade_8x_NK-43`** — N1 Block A/B cluster configs whose only host is
  the uncurated SXT N1 stage parts; no curated cluster part → sacked (see §A).

## E. Decision — keep the 53 engine orphans? **Yes.**

The question: vendor the upgrades whose engine config our RO doesn't currently ship? **Keep them**,
by vendoring `Tree/TREE-Engines.cfg` whole (rather than a hand-trimmed subset):

1. **Safe.** RP-1's `deleteme` + `Tree/UpgradeCleanup.cfg` delete any upgrade whose CONFIG is
   absent, every load. No root engine config ⇒ no upgrade — exactly as you noted. No orphan ever
   shows a broken icon.
2. **Forward-compatible.** If a player installs a mod that adds one of these engine variants, the
   matching upgrade **wakes automatically** — no AXE change needed.
3. **Nearly free to wire.** **31 of the 34** distinct orphan tech nodes are already in the
   115-node active-keeper remap, so once we remap the keepers the orphans inherit valid AXE nodes
   for free. Only **3** nodes are orphan-only: `nuclearPropulsionNF2`, `prototypeHydrolox`,
   `stagedCombustion2019` (late/future) — add 3 lines to the remap and all 53 are fully wired.

The alternative (hand-trim to 462) is more work, loses forward-compat, and gains nothing — the
deleteme mechanism already makes the orphans cost-free at runtime. **Keep whole; remap all nodes.**

## Reproduce

```
python tools/upgrade_audit.py      # -> manifest/upgrades-absent.tsv (needs a fresh ConfigCache)
python tools/curate_upgrades.py    # -> manifest/upgrades-curated.tsv
```

Columns: `name · techRequired · sourcefile · disposition · companion_patch · reason · title`. This
is the input to **P2** tree-placement + the `techRequired → AXE-node` remap.

## Addendum (2026-07-01) — 32 more, found outside RP-1's own folder

T3's scope was "RP-1-authored PARTUPGRADEs" (`upgrade_audit.py` walks only `GameData/RP-1`). That
missed upgrades that are **live under AXE already** (they ship from a kept dependency) but hardcode
or get patched onto an RP-1 techRequired id — found investigating `[not-in-curated]` tags in
`manifest/human-orbital-partlist.md`. Two shapes:

1. **Baked in directly** — RealismOverhaul's `RO_RealFuels.cfg` per-tank-**TYPE** ladder (21: Sep/Iso/
   Balloon/ServiceModule/Battery/WetWing material & capacity tiers + AddLifeSupport/AddOxygenGas) sets
   `techRequired` to an RP-1 node id in its own definition — no RP-1 folder involvement, so
   `upgrade_audit.py`'s RP-1-only walk could never see it. New disposition **`KEEP-tank-typelevel`**
   (sibling of `KEEP-engine-typelevel`) — 21.
2. **Patched, not defined, by RP-1** — ROHeatshields' material presets (6: Heatsink/MercuryHS/
   GeminiHS/EarlyLunarHS/LunarHS/Inflatable) and RealFuels' MLI-wrapping tiers (5: MLI.Upgrade1-5) are
   defined against a **stock** techRequired (`engineering101`/`generalConstruction`) by their own mod,
   then re-gated by an `@PARTUPGRADE[name]{ %techRequired = ... }` **patch** inside RP-1's folder —
   `upgrade_audit.py`'s regex only matches fresh `PARTUPGRADE {` headers, not patch blocks, so these
   were invisible too. `KEEP-capability` — 11.

Ground-truthed against the compiled reference cache (not source-text guessing): 4 similarly-named
RP-1 patch targets (`RFTech-Tank-Iso-Al`, `RFTech-Tank-Balloon-SteelAl`, and RP-1's own
`-Tank-`-missing typo `RFTech-Balloon-SteelAlCu/Li`) compile to nothing and were correctly excluded.

**Deliberately still out of scope** (has its own mechanism / different milestone): `commsTL1-10` /
`solarTL*` already carry a `KEEP-techlevel-TODO` placeholder in the `extract_*_partlist.py` scripts
(prior user note) — folding them in here would fork that decision. `Upgrade-Colony` (Kerbalism
Sickbay, `techRequired=improvedHabitats`) is a single different-mod one-off far past current milestone
scope.

**Result: 626 → 658 rows** (553 → 576 KEEP). Reproduce: `python tools/curate_upgrades_addendum.py`
(run after `curate_upgrades.py`; merges + re-sorts `upgrades-curated.tsv` in place).
