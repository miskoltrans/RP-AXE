# seed/ -- vendored RP-1 config (read-only import)

This folder is **imported, pristine RP-1 config** that RP-AXE ships and loads as-is. **Never
hand-edit anything here.** All RP-AXE changes live in `../design/` as ModuleManager patches that
apply *after* the seed (`:AFTER[...]` / `:FINAL`). Keeping the seed untouched makes the periodic
upstream refresh a clean diff. See `docs/ARCHITECTURE.md` section 8.

Refreshed by `tools/sync-seed.ps1`. Committed to the repo so the mod is self-contained.
(Keep this file ASCII-only -- the sync script round-trips it through PowerShell 5.1.)

**License:** RP-1 is **CC-BY-NC-SA-4.0**. Shipping these derived configs requires attribution to
the RP-1 Group (and `pehvbot/LRTR` for entry-cost reference values) and remains non-commercial /
share-alike. Ship `LICENSE.md` accordingly.

## What gets vendored (MVP)
| seed path | from `RP-1/GameData/RP-1/` | notes |
|---|---|---|
| `Tree/` | `Tree/` | node defs (`RP0TechTree.cfg`), `TREE-*` placements, `OrphanNode.cfg`, icons |
| `Contracts/` | `Contracts/` | the ~387 contract types (de-railed/fixed by `design/` patches) |
| `Science/` | `Science/` | science rebalance (pure config, survives pluginless) |

**Omitted on purpose:** `Plugins/` (the DLL), the live Programs system, and anything that only
feeds the RP0 plugin (KCT presets, maintenance/tooling/leaders/crew/avionics configs).

## Source / last sync
- Upstream: KSP-RO/RP-1 -- local source at `C:\git\ksp\RP-1` (instance had RP-1 **v4.4.0.0**).
- Synced from "C:\git\ksp\RP-1\GameData\RP-1" on 2026-06-28 01:28. RP-1.version: { "NAME": "Realistic Progression One", "URL": "https://raw.githubusercontent.com/KSP-RO/RP-1/master/GameData/RP-1/RP-1.version", "DOWNLOAD": "https://github.com/KSP-RO/RP-1/releases/download/v4.4.0.0/RP-1-v4.4.0.0.zip", "HOMEPAGE": "https://github.com/KSP-RO/RP-1/", "VERSION": { "MAJOR": 4, "MINOR": 4, "PATCH": 0, "BUILD": 0 }, "KSP_VERSION": { "MAJOR": "1", "MINOR": "12", "PATCH": "3" }, "KSP_VERSION_MIN": { "MAJOR": "1", "MINOR": "12", "PATCH": "0" }, "KSP_VERSION_MAX": { "MAJOR": "1", "MINOR": "12", "PATCH": "99" } }

