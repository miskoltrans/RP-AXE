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
| `earlyAvionics` (Early tape) | `tel_onboardRecording` (T2) | | `advancedAvionics` (1975) | `comp_multiplyRedundantFlightComputer` |
| `basicAvionics` (Basic) | `elec_semiconductorDiode` (T2) | | `longTermAvionics` (1990) | `comp_softwareDefinedFlightControl` |
| `interplanetaryProbes` (1961) | `elec_transistor` (T3) | | `internationalAvionics` (1998) | `comp_interoperableAvionicsStandard` |
| `matureAvionics` (1964) | `tel_appSatellites` (T4) | | `modernAvionics` (2010) | `comp_commercialOffTheShelfAvionics` |
| `largeScaleAvionics` (1969) | `comp_networkedAvionics` | | `advModernAvionics` (2020) | `comp_commercialOffTheShelfAvionics` |

**The first four rungs were re-homed 2026-07-29.** The original mapping name-matched RP-1's `earlyAvionics` →
AXE's `gnc_earlyAvionics` and bucketed the next three onto `gnc_basicAvionics`. Same words, different jobs:
RP-1's `earlyAvionics` costs 7 (23 science from `start`), AXE's `gnc_earlyAvionics` is **T4/29** (44 from
`start`) and `gnc_basicAvionics` is **T5**. With `proceduralAvionics` basing at `dataCapacity = 0` (RP-1's
own default, kept), that left a fresh career with *literally zero* data storage until 44 science — every file
experiment unrunnable except as a real-time transmit stream, and the VAB capacity slider dead because it
multiplies the base. Storage now homes on the **data-handling spine**, which is where recording hardware
actually lives; guidance keeps the guidance.

The first rung got its own node, `tel_onboardRecording` (**Endless-Loop Tape Recording**, Telecom T2), added
2026-07-29. AXE already had a lane for the live downlink (`tel_telemetry`) and one for physical return
(`opt_filmReturn`), but none for store-and-forward — which is why every HDD rung sat on a borrowed node.
Rungs `-1969` onward stay on the Computing flight-computer lane; by then storage genuinely *is* the
computer's memory, so that home is honest. The middle rungs ride the electronics that drove their density
(diode → transistor → operational-satellite payloads). Cumulative science from `start`: **4 / 4 / 15 / 44**.

If the tree's HDD-Upgrade placement changes (re-run `build_tree.py`), re-sync these `techRequired`/
`techRequired__` values to the new `AxePartPlacement.cfg` mapping.

### Why in `design/` (and how sync-seed stays safe)
Authored here (not `seed/`) because the tech gates sit inside `@PART`/`UPGRADE` blocks a design overlay
can't rewrite — so these are AXE-node copies, and RP-1's originals must not also ship in `seed/` (they'd
**double-add a `HardDrive` to every command part**). `sync-seed.ps1` handles this: after the wholesale
`Science/`+`Tree/` vendor it **strips** `HardDriveConfigs.cfg`(+`.disabled`) and `Tree/HardDriveUpgrades.cfg`
(plus `Experiments/CrewScience`) via its `$designOwned` list. Add any new design-owned science file to that
list too. See `CrewScience/_README.md` and the `rp-axe-science-wiring-port` memory.
