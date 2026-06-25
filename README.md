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

🚧 **Pre-MVP / project setup.** See [`docs/TASKS.md`](docs/TASKS.md) for the backlog and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the pieces fit together.

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
