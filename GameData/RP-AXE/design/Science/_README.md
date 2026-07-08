# design/Science — RP-AXE science patches

- `EarthScienceRemoval.cfg` — (pre-existing) Kopernicus Earth-science tweak.
- `CrewScience/` — RP-1 crewed-science, tech-remapped (see that folder's `_README.md`).
- `HardDriveConfigs.cfg` + `HardDriveUpgrades.cfg` — **Kerbalism data-storage system**, localized from
  RP-1 with the avionics tech ladder remapped to AXE nodes (below).

## HardDrive (science data storage) — ported 2026-07-08

RP-1 stores science *data* in Kerbalism `HardDrive` modules (replacing stock `ModuleScienceContainer`)
and scales the procedural-avionics part's capacity up across the avionics tech ladder. Two files:

- **`HardDriveUpgrades.cfg`** — 10 stock `PARTUPGRADE`s (`HDD-Upgrade-Early` … `-2020`), each
  `techRequired = <avionics node>`. (Was `RP-1/Tree/HardDriveUpgrades.cfg`.)
- **`HardDriveConfigs.cfg`** — strips stock `ModuleScienceContainer`, adds a `HardDrive` to every
  `ModuleCommand` part, and links the 10 upgrades onto `proceduralAvionics|ROT-ProbeCore` with per-tier
  `dataCapacity`. Also sets fixed capacities for named probes/capsules, EVA, labs, sample-return, and
  private goo/photography drives. (Was `RP-1/Science/HardDriveConfigs.cfg`.)

Mechanism is **stock KSP part upgrades** (no RP0.dll): the module's `UPGRADES { UPGRADE { name__ = … } }`
is stock KSP's upgrade-reference syntax (the `__` is a field name, not a disable).

### Remap table (RP-1 avionics node → AXE node), era-matched, all verified in `AxeTechTree.cfg`

| RP-1 (HDD tier / era) | AXE node | | RP-1 | AXE node |
|---|---|---|---|---|
| `earlyAvionics` (1958 tape) | `gnc_earlyAvionics` | | `advancedAvionics` (1975) | `comp_networkedAvionics` |
| `basicAvionics` (1960 tape) | `gnc_basicAvionics` | | `longTermAvionics` (1990) | `comp_multiplyRedundantFlightComputer` |
| `interplanetaryProbes` (1961) | `gnc_interplanetaryAvionics` | | `internationalAvionics` (1998 SSR) | `comp_distributedAvionicsBus` |
| `matureAvionics` (1964 transistor) | `comp_digitalGuidanceComputer` | | `modernAvionics` (2010 flash) | `comp_softwareDefinedFlightControl` |
| `largeScaleAvionics` (1969 digital) | `comp_realTimeFlightComputer` | | `advModernAvionics` (2020 flash) | `comp_interoperableAvionicsStandard` |

Applied to both `techRequired =` (PARTUPGRADE) and `techRequired__ =` (module UPGRADE) so the gate is
consistent on both sides.

### ⚠️ Why in `design/` + sync-seed caveat
Authored here (not `seed/`) because the tech gates sit inside `@PART`/`UPGRADE` blocks a design overlay
can't rewrite. Both `HardDriveConfigs.cfg` (Science/) and `HardDriveUpgrades.cfg` (Tree/) are vendored by
`sync-seed.ps1`'s folder list, so a blind re-run would re-introduce RP-1's versions and **double-add a
`HardDrive` to every command part**. See `CrewScience/_README.md` and the `rp-axe-science-wiring-port`
memory — drop `Science` (and don't re-vendor `Tree/HardDriveUpgrades.cfg`) before running sync-seed.
