# design/Science — RP-AXE science patches

- `EarthScienceRemoval.cfg` — (pre-existing) Kopernicus Earth-science tweak.
- `CrewScience/` — RP-1 crewed-science, tech-remapped (see that folder's `_README.md`).
- `HardDriveConfigs.cfg` + `HardDriveUpgrades.cfg` — **Kerbalism data-storage system**, localized from
  RP-1 with the avionics tech ladder remapped to AXE nodes (below).
- `Configure.cfg` + `US2.cfg` — **Kerbalism `Configure` SETUP tech-gates** (the in-VAB instrument/
  experiment selector on probe cores, capsules, lunar bases, and US2 wedges), localized from RP-1
  (`Science/Configure.cfg` + `Parts/Science/US2.cfg`). Each SETUP is gated **where its content unlocks**:
  probe instruments at their standalone part's node (`AxePartPlacement.cfg`), crew/lunar experiments at
  their `EXPERIMENT_DEFINITION techRequired` (`CrewScience/`), supersonic at `av_afterburner`/`av_ramjet`.
  Authored here because the `tech =` gates live inside `@PART` patch bodies (not overlayable); both are in
  sync-seed's `$designOwned` strip-list. `AxeSurfaceSampleGate.cfg` is a 1-gate late-pass overlay for the
  lone EVA `Deep Surface Sample` gate in seed's `SurfaceSample.cfg`.

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

### Remap table — **defers to AXE's existing tree curation**

AXE's tree already **places** these 10 upgrades (`AxeTechTree.cfg` `partUpgrade = HDD-Upgrade-*`),
**gates** them (`AxePartPlacement.cfg` `@PARTUPGRADE[…]{ %techRequired = … }`), and **costs** them
(`AxePartCost.cfg`) — the T3 upgrade curation anticipated them; they were dormant until this file
shipped the definitions. So the authoritative RP-1→AXE mapping is AxePartPlacement's, and the
`techRequired` here is set to **match** it (AxePartPlacement's `%techRequired` overrides the
PARTUPGRADE side anyway; the module-`UPGRADE` `techRequired__` in `HardDriveConfigs.cfg` is NOT
overridden, so it must match — that is the reason these values are kept in sync here):

| RP-1 (HDD tier / era) | AXE node | | RP-1 | AXE node |
|---|---|---|---|---|
| `earlyAvionics` (Early tape) | `gnc_earlyAvionics` | | `advancedAvionics` (1975) | `comp_multiplyRedundantFlightComputer` |
| `basicAvionics` (Basic) | `gnc_basicAvionics` | | `longTermAvionics` (1990) | `comp_softwareDefinedFlightControl` |
| `interplanetaryProbes` (1961) | `gnc_basicAvionics` | | `internationalAvionics` (1998) | `comp_interoperableAvionicsStandard` |
| `matureAvionics` (1964) | `gnc_basicAvionics` | | `modernAvionics` (2010) | `comp_commercialOffTheShelfAvionics` |
| `largeScaleAvionics` (1969) | `comp_networkedAvionics` | | `advModernAvionics` (2020) | `comp_commercialOffTheShelfAvionics` |

If the tree's HDD-Upgrade placement changes (re-run `build_tree.py`), re-sync these `techRequired`/
`techRequired__` values to the new `AxePartPlacement.cfg` mapping.

### Why in `design/` (and how sync-seed stays safe)
Authored here (not `seed/`) because the tech gates sit inside `@PART`/`UPGRADE` blocks a design overlay
can't rewrite — so these are AXE-node copies, and RP-1's originals must not also ship in `seed/` (they'd
**double-add a `HardDrive` to every command part**). `sync-seed.ps1` handles this: after the wholesale
`Science/`+`Tree/` vendor it **strips** `HardDriveConfigs.cfg`(+`.disabled`) and `Tree/HardDriveUpgrades.cfg`
(plus `Experiments/CrewScience`) via its `$designOwned` list. Add any new design-owned science file to that
list too. See `CrewScience/_README.md` and the `rp-axe-science-wiring-port` memory.
