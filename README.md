# RP-AXE — Ahistorical Xploration & Engineering

> Realism, minus the grind. A lightweight career/science layer for Realism Overhaul that
> puts **engineering and exploration** front and centre — and takes an *axe* to the parts
> of RP-1 that get in the way.

RP-AXE is a **config-first** Kerbal Space Program 1.12 mod built on the same realism stack as
[RP-1](https://github.com/KSP-RO/RP-1) (Realism Overhaul, Real Solar System, Real Fuels,
Kerbalism, …) but it **does not ship RP-1's career plugin**. Instead it provides a thin,
purpose-built layer:

- **Lightweight progression** — a custom tech tree (yoinked from RP-1) unlocked by science.
  No build times, no facility maintenance, no part tooling, no crew training, no confidence
  economy. You design, you fly, you learn.
- **Meaningful exploration** — contracts guide you early, then get out of the way so you can
  set your own goals. "What-if" / ahistorical: there's no fixed timeline to match.
- **Near- and far-future parts are first-class** — expected, not merely suggested.
- **Educational engineering challenges** — the realism is the teacher.

## Status

✅ **MVP — config-complete & AutoTest-validated** (v0.1.0). The full loop works pluginlessly:
custom science tech tree, ported RP-1 contracts running on our own lightweight ContractConfigurator
types, a config-only "program" switcher, future-part placement (Tantares + NearFuture + Cryo/Atomics),
a flyable start node, and the economy below. The only thing not yet proven by automated test is a real
play session (build + fly) — see *Playing the MVP*. Backlog: [`docs/TASKS.md`](docs/TASKS.md).

**The RP-AXE economy** (exploration + engineering, not management):
- **Parts unlock free with science** — science is the only gate on *what* you can build.
- **RealFuels engine-config development still costs funds** — the one buy-to-unlock with real
  engineering meaning.
- **Launch cost is the only ongoing money sink** (90% part / 95% propellant recovery rewards
  recoverable, efficient designs). Generous: ~100k starting funds, milestone contracts pay well.
- **Earth is not a science farm** — sub-40 km home-planet science is removed; science comes from real
  spaceflight and exploration. The solar system holds ~57× the tree's science (see
  [`docs/SCIENCE_AUDIT.md`](docs/SCIENCE_AUDIT.md)).

## Install

CKAN (recommended): the metadata is `RP-AXE.netkan` — it pulls RP-1's realism + part stack, **minus
the RP-1 plugin**, and **conflicts with `RP-1`** (don't install both). Until it's on the CKAN registry,
add it locally via *CKAN → Settings → … → Add netkan* (or the netkan inflator). Manual: drop
`GameData/RP-AXE/` into a KSP 1.12 install that already has the dependencies (`docs/DEPENDENCIES.md`),
and make sure **`GameData/RP-1/` is not present**.

## Playing the MVP

Start a **Career**. You begin with ~100,000 funds and the full basic parts set on the `start` node
(sounding-rocket engines, early guidance, tanks, antennas, instruments) — all free to use. Build a
small sounding rocket, fly it up past 40 km for your first science, take the early contracts, and
activate a *program* (in Mission Control) to open its contract line. Tech unlocks with science; money
is for building and flying, not for unlocking parts.

## Repo layout

| Path | What it is |
|------|------------|
| `GameData/RP-AXE/seed/` | **Pristine, vendored** RP-1 config (Tree / Contracts / Science). Never edited — refreshed from upstream. |
| `GameData/RP-AXE/design/` | All RP-AXE transformations & new content — MM patches applied *after* the seed. |
| `Source/AXE/` | Boilerplate C# plugin — a *researched fallback* for the few contract checks stock ContractConfigurator can't express. |
| `docs/` | Architecture, workflow, dependencies, decisions, task list. |
| `tools/` | `deploy.ps1` (link into the test instance), `sync-seed.ps1` (refresh vendored RP-1 config). |

## Working directories (this machine)

This repo lives in `C:\git\ksp\` alongside its reference material and a test instance:

- `RP-AXE/` — **this repo** (the mod we're building).
- `RP-1/` — RP-1 **source repo**, used as reference & yoink source. Not ours.
- `LRTR/` — Less Real Than Real, another RO career. Reference only.
- `Instance/` — a KSP 1.12 install (CKAN-managed) used for testing. See [`docs/WORKFLOW.md`](docs/WORKFLOW.md).

## Quickstart for a new contributor (human or agent)

1. Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the *why* and the keep/axe/reimplement map.
2. Read [`docs/WORKFLOW.md`](docs/WORKFLOW.md) — how to build, deploy to `Instance/`, and test.
3. Pick a task from [`docs/TASKS.md`](docs/TASKS.md).
