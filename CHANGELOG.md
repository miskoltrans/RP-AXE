# Changelog

The in-game copy (shown once per new version by KerbalChangelog) is
`GameData/RP-AXE/RP-AXE-Changelog.cfg`; keep the two in step.

## 1.0.0 — first public release

- **Tech tree:** a from-scratch, discipline-based tree of ~530 breakthrough nodes compiled from
  `tree/nodes.yaml`, science-gated, with an in-game R&D render (discipline colours, hover lineage,
  OR-gates drawn dashed).
- **Ported from RP-1:** the science instrument suite and crewed science, 35 programs and their
  contracts (running on AXE's own ContractConfigurator types), the engine-config upgrade ladders,
  the DSN tracking-station levels, airlaunch, range safety, non-reentry-rated parts, dev parts.
- **AXE's own:** avionics with steerable-mass capacity and control corruption on overload instead
  of a lock; an in-editor flight simulator; a funds economy with no build times, tooling,
  maintenance, crew training or reliability grind; free launch-site switching; a capstone +
  program-completion payout model.
- **KerbalismLab:** 65 crewed-station experiments integrated and rebalanced.
- **Packaging:** CKAN metadata (`RP-AXE.netkan`), KSP-AVC version file, `tools/package_release.py`.
