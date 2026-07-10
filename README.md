# RP-AXE — Ahistorical Xploration & Engineering

> Realism, minus the grind. A lightweight career/science layer for Realism Overhaul that
> puts **engineering and exploration** front and centre — and takes an *axe* to the parts
> of RP-1 that get in the way.

RP-AXE is a **config-first** Kerbal Space Program 1.12 mod built on the same realism stack as
[RP-1](https://github.com/KSP-RO/RP-1) (Realism Overhaul, Real Solar System, Real Fuels,
Kerbalism, …) but it **does not ship RP-1's career plugin** and **conflicts with RP-1** (don't
install both). Instead it provides a thin, purpose-built layer:

- **Lightweight progression** — a bespoke tech tree, rebuilt from scratch and unlocked by science.
  No build times, no facility maintenance, no part tooling, no crew training, no reliability
  run-data grind. You design, you fly, you learn.
- **Engineering-first tree** — nodes are real industrial *breakthroughs* (not eras, not generic
  "Advanced Engines"), organised by discipline; parts scatter to the breakthrough that made them
  hard. Research-paper node names, flavour text, an education pillar.
- **Meaningful exploration** — contracts guide you early, then get out of the way so you can set
  your own goals. "What-if" / ahistorical: there's no fixed timeline to match.
- **Near- and far-future parts are first-class** — expected, not merely suggested.

## Status

🚧 **Under active rebuild — the "restart".** The project's first cut (a config-complete MVP,
preserved at tag `pre-restart-mvp`) was deliberately torn down to rebuild the tech tree, part
baseline, and economy from scratch. Built so far: the discipline tech tree (~217 nodes, compiled
from `tree/nodes.yaml`) with an in-game R&D render, the RP-1 science wiring, the avionics ladder,
ported contracts running on our own ContractConfigurator types, a config-only program switcher,
and a tech-gated airlaunch system. In progress: full part-placement realization and economy
calibration. **The live roadmap (phases P0–P6) and every settled decision are in
[`docs/RESTART.md`](docs/RESTART.md) — the single source of truth.**

**The RP-AXE economy** (exploration + engineering, not management):
- **Science is the primary gate** on progression — the tree unlocks with science, and science
  comes from real spaceflight and exploration, not a home-planet farm (sub-40 km Earth science is
  removed).
- **Parts carry an entry cost** (abstracting R&D) — `base[tier] × weight[category]`, a
  funds-as-texture layer, *not* free. RealFuels engine-config development also costs funds.
- **Launch cost is the main ongoing money sink** (high part/propellant recovery rewards
  recoverable, efficient designs). No time pressure: timewarp is free, so money is never a
  time-farmed resource — **the launch is the gate**.
- **The solar system dwarfs the tree's cost** — see the budget writeup in
  [`docs/SCIENCE.md`](docs/SCIENCE.md) (~3.9M reachable science vs. a ~300k tree).

## Install

CKAN: the metadata is `RP-AXE.netkan` — it pulls RP-1's realism + part stack, **minus the RP-1
plugin**, and **conflicts with `RP-1`** (don't install both). The complete dependency set is the
metapackage `RP-AXE-deps.ckan` (see [`docs/WORKFLOW.md`](docs/WORKFLOW.md)). Until it's on the CKAN
registry, add it locally via *CKAN → Settings → … → Add netkan*. Manual: drop `GameData/RP-AXE/`
into a KSP 1.12 install that already has the dependencies, and make sure **`GameData/RP-1/` is not
present**.

## Repo layout

| Path | What it is |
|------|------------|
| `GameData/RP-AXE/seed/` | **Pristine, vendored** RP-1 config (Tree / Contracts / Science). Never edited — refreshed from upstream via `tools/sync-seed.ps1`. |
| `GameData/RP-AXE/design/` | All RP-AXE transformations & new content — ModuleManager patches applied *after* the seed. |
| `Source/AXE/` | **`AXE.dll` — the load-bearing plugin.** Implements the ContractConfigurator types the contracts need, Career-enable, the program switcher, the avionics modules, the tracking-station / facility gates, the airlaunch system, and the in-game R&D tree render. *Not* RP-1's plugin; never ships `RP0.dll`. |
| `tree/` | The tech-tree source — `nodes.yaml` + `disciplines.yaml`, compiled by `tools/build_tree.py` into the game cfgs + renders. |
| `manifest/` | The curated part list (`curated-parts.tsv`, 1820) + upgrade curation + capability data. |
| `docs/` | Architecture, workflow, and decisions. Start with [`RESTART.md`](docs/RESTART.md). |
| `tools/` | `build_tree.py` (compile the tree), `deploy.ps1` (link into the test instance), `rebuild-instance.ps1` (nuke & restore a test install), `sync-seed.ps1` (refresh vendored RP-1 config). |

## Working directories (this machine)

This repo lives in `C:\git\ksp\` alongside its reference material and a test instance:

- `RP-AXE/` — **this repo** (the mod we're building).
- `RP-1/` — RP-1 **source repo**, used as reference & yoink source. Not ours.
- `LRTR/` — Less Real Than Real, another RO career. Reference only.
- `Instance/` — a KSP 1.12 install (CKAN-managed) used for testing. See [`docs/WORKFLOW.md`](docs/WORKFLOW.md).

## Quickstart for a new contributor (human or agent)

1. Read [`docs/RESTART.md`](docs/RESTART.md) — the roadmap, the keep/rebuild map, and every settled decision.
2. Read [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — how to build `AXE.dll`, deploy to `Instance/`, and test.
3. For the tree specifically: [`docs/TREE.md`](docs/TREE.md) (architecture) + [`docs/SCIENCE.md`](docs/SCIENCE.md) (budget).
