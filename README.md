# RP-AXE — Ahistorical Xploration & Engineering

> Realism, minus the grind. A lightweight career for Realism Overhaul that puts **engineering and
> exploration** front and centre — and takes an *axe* to the parts of RP-1 that get in the way.

RP-AXE is a Kerbal Space Program 1.12 mod built on the same realism stack as
[RP-1](https://github.com/KSP-RO/RP-1) (Realism Overhaul, Real Solar System, Real Fuels, Kerbalism,
…) but it **replaces RP-1's career plugin** with a thin, purpose-built layer of its own. It
**conflicts with RP-1** — install one or the other, never both.

## What you get

- **A tech tree built from scratch.** ~530 nodes organised by engineering discipline — metallurgy,
  propellant chemistry, cryogenics, microelectronics, guidance, telecommunications, nuclear
  engineering, life support and so on. Each node is a real industrial *breakthrough* with its own
  flavour text, not an era or an "Advanced Engines III". Parts land on the breakthrough that made
  them hard, so a lander is assembled from nodes across the tree.
- **Science is the gate.** The tree unlocks with science, and science comes from real spaceflight
  and exploration — home-planet science below 40 km is removed. The solar system holds far more
  science than the tree costs, so you finish it by exploring broadly, not by farming.
- **No management treadmill.** No build times, no facility maintenance, no part tooling, no crew
  training, no reliability run-data grind. Parts carry an entry cost (R&D) and launching costs
  money (ops); timewarp is free, so **the launch is the gate**, never the calendar.
- **Engineering that bites.** Avionics have a steerable-mass capacity; overload one and your
  control inputs degrade instead of locking out. Engines improve through tech-gated config
  ladders. The tracking station climbs an 11-level Deep Space Network ladder. Parts that aren't
  rated for re-entry burn up.
- **Tools that respect your time.** An in-editor flight simulator (test a craft in an orbit you
  haven't reached yet before committing the mission), tech-gated airlaunch from the SPH, free
  switching between launch sites, a program switcher that charters RP-1's 35 programs in any order.
- **Ahistorical.** There is no timeline to match. Near- and far-future parts are first-class
  citizens of the tree, and crewed-station science (KerbalismLab) is integrated and balanced.

## Requirements

- KSP **1.12.x** (tested on 1.12.5) with the **Making History** and **Breaking Ground** DLCs.
- The full RO/RSS dependency stack — CKAN installs it for you (below). It is the RP-1 Express set
  minus RP-1, plus a curated expansion of part mods (Nertea's Near Future and Far Future suites,
  CryoEngines, KerbalAtomics, SSPXr, Tantares, Coatl, the RN probe packs, Universal Storage 2,
  Rocket Motor Menagerie, SCANsat, …).
- The graphics preset is RP-1 Express **High** (Parallax, Scatterer, 16K RSS textures, RSSVE-HR).
  Budget **40+ GB** of disk and a machine that already runs RP-1 at that preset comfortably.

## Install

**CKAN (recommended).** Until RP-AXE is on the CKAN registry, add its metadata locally: *CKAN →
Settings → … → Add netkan* and point it at `RP-AXE.netkan` from this repository, then install
`RP-AXE`. CKAN pulls every dependency and refuses the install if `RP-1` is present (the `conflicts`
rule). Expect a long download the first time.

**Manual.** Install the dependency set first — the CKAN metapackage `RP-AXE-deps.ckan` (*CKAN →
File → Install from .ckan file*) is the exact list — then unzip the release so that
`GameData/RP-AXE/` sits in your KSP folder. Make sure **`GameData/RP-1/` does not exist**.

Then start a **new Career** game. The difficulty presets are AXE's own; Normal is the balanced one.

> SCANsat: the dependency is the standard CKAN SCANsat. The author also maintains a GPU-rendered
> fork ([miskoltrans/SCANsat-GPU](https://github.com/miskoltrans/SCANsat-GPU)) with the same parts;
> it is an optional drop-in replacement, not required.

## Known issues

- DynamicBatteryStorage (a dependency of the Near Future mods) logs one `NullReferenceException`
  pair on every editor and flight scene load when Kerbalism is present. It is cosmetic, it is DBS's
  bug, and RP-1 installs show the same lines.
- RSSVE-HR 3.1.0 declares a `NeptuneClouds` cubemap it does not ship, which silently disables the
  Saturn, Titan, Uranus and Venus cloud layers. Copy the six `NeptuneClouds*.dds` from the RSSVE-LR
  archive into `GameData/RSSVE/Textures/` to restore them.
- The first launch after install compiles every part and takes several minutes.

## For developers

| path | what it is |
|------|------------|
| `GameData/RP-AXE/seed/` | **Pristine, vendored** RP-1 config and part assets. Never edited; refreshed from upstream via `tools/sync-seed.ps1` / `sync-rp1-parts.ps1`. |
| `GameData/RP-AXE/design/` | Everything RP-AXE changes or adds — ModuleManager patches applied *after* the seed. |
| `Source/AXE/` | **`AXE.dll`**, the load-bearing plugin: the ContractConfigurator types the contracts need, the program switcher, avionics, facility gates, airlaunch, the simulator, the R&D render. Not RP-1's plugin; never ships `RP0.dll`. |
| `tree/` | The tree source — `nodes.yaml` + `disciplines.yaml`, compiled by `tools/build_tree.py` into the game cfgs and a browser viewer (`tree/render/prototype/axe-tree-standalone.html`). |
| `manifest/` | The curated part list (`curated-parts.tsv`), upgrade curation and capability data. |
| `docs/` | Architecture, workflow, decisions. **Start with [`docs/RESTART.md`](docs/RESTART.md)**, the single source of truth; then [`docs/WORKFLOW.md`](docs/WORKFLOW.md) (build, deploy, test) and [`docs/TREE.md`](docs/TREE.md). |
| `tools/` | Build, audit and packaging scripts. `package_release.py` builds the release zip; `rebuild-instance.ps1` recreates the test install from CKAN metadata and boots it through the automated checks. |

Releases: see [`docs/RELEASE.md`](docs/RELEASE.md). Changes: [`CHANGELOG.md`](CHANGELOG.md).

## License

CC-BY-NC-SA-4.0. RP-AXE is a derivative of RP-1 and vendors work from several other projects —
see [`LICENSE.md`](LICENSE.md) for the full attribution.
