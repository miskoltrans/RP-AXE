# RP-AXE — Ahistorical Xploration & Engineering

> Realism, minus the grind. A lightweight career for Realism Overhaul that puts **engineering and
> exploration** front and centre — and takes an *axe* to the parts of RP-1 that get in the way.

**Status: 0.9 public beta.** Every system below is built and has been played through, but the
balance has had one pair of eyes on it. Bug reports and balance notes are the point of this release.

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

The full inventory of what differs from RP-1 (removed, replaced, ported, changed) is
[`docs/CHANGES-VS-RP1.md`](docs/CHANGES-VS-RP1.md).

## Requirements

- KSP **1.12.x** (tested on 1.12.5). **Breaking Ground** is strongly recommended: the Robotics
  discipline places its 28 robotics parts. Making History is optional.
- The RO/RSS realism stack plus the part mods the tree is built on — CKAN installs all of it as
  hard dependencies (below): the RP-1 Express part set minus RP-1, plus a curated expansion
  (Nertea's Near Future and Far Future suites, CryoEngines, KerbalAtomics, SSPXr, Tantares, Coatl,
  the RN probe packs, Universal Storage 2, Rocket Motor Menagerie, SCANsat, …). Every one of them
  has parts placed in the tree, which is why none is optional.
- Graphics are **your choice**. RSS needs one texture pack and CKAN asks which; the author plays on
  the RP-1 Express **High** preset (Parallax, Scatterer, 16K textures, RSSVE-HR — about 8 GB more
  than Low). Budget **40+ GB** of disk for the full High install.

## Install

**CKAN (recommended).** Until RP-AXE is on the CKAN registry, download `RP-AXE-<version>.ckan`
**and** one of `RP-AXE-Express-Low.ckan` / `RP-AXE-Express-High.ckan` from the
[release page](https://github.com/miskoltrans/RP-AXE/releases), then *CKAN → File → Install from
.ckan file* with both selected. The Express file is the one-click preset: RP-AXE, its recommended
tools (MechJeb, TestFlight, alarm clock, transfer planners, editor helpers, Scatterer) and a graphics
set — Low is 4K planet textures, High is the author's RP-1-Express-High set (Parallax, 16K textures,
RSSVE-HR, about 8 GB more). When CKAN then offers *further* recommendations, those come from the
dependencies themselves (ModularLaunchPads recommends Bluedog Design Bureau, RSS recommends Parallax,
and so on) — **decline them** unless you want them; the tree places nothing from them. CKAN refuses
the install if `RP-1` is present (the `conflicts` rule). Expect a long download the first time.

Command line, same thing:

```
ckan install -c RP-AXE-0.9.0.ckan -c RP-AXE-Express-Low.ckan --no-recommends --gamedir <your KSP folder>
```

Installing `RP-AXE-<version>.ckan` on its own also works in the CKAN window: it asks for the texture
pack and offers the recommendations one by one. On the command line a headless install cannot ask,
and silently skips the choice — add the pack yourself afterwards:

```
ckan install -c RP-AXE-0.9.0.ckan --gamedir <your KSP folder> --headless
ckan install RSSTextures4096 --gamedir <your KSP folder> --headless
```

> Installing into a KSP folder that already holds mods installed by hand? CKAN refuses to overwrite
> any file it did not install itself, and part mods ship example craft into `Ships/`. If it stops with
> "tried to overwrite a file", delete that file and retry.

**Manual.** Install the dependency set first — the metapackage `RP-AXE-deps.ckan` (*CKAN → File →
Install from .ckan file*) is the author's complete environment, High graphics included — then unzip
the release so that `GameData/RP-AXE/` sits in your KSP folder. Make sure **`GameData/RP-1/` does
not exist**.

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
| `tools/` | Build, audit and packaging scripts. `package_release.py` builds the release zip; `gen_netkan.py` writes the CKAN relationships from one classification; `rebuild-instance.ps1` recreates the test install from CKAN metadata and boots it through the automated checks. |
| `tools/mission/` | A mission planner for this install: reads your save, plans ejection / midcourse / flyby / capture burns and moon tours on the install's own ephemeris, and can verify them against the running game through the localhost bridge. See [`docs/MISSION-TOOLS.md`](docs/MISSION-TOOLS.md). |

Releases: see [`docs/RELEASE.md`](docs/RELEASE.md). Changes: [`CHANGELOG.md`](CHANGELOG.md).

## License

CC-BY-NC-SA-4.0. RP-AXE is a derivative of RP-1 and vendors work from several other projects —
see [`LICENSE.md`](LICENSE.md) for the full attribution.
