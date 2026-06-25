# AXE contract types — triage & status (M2)

RP-1's contracts reference custom ContractConfigurator types from `CC_RP0.dll` (which we don't
ship). We register the same names in `AXE.dll` (CC discovers factories by class name minus the
`Factory`/`Requirement` suffix). Per project direction: real logic where it's cheap and meaningful
for the early game; stock-simple where RP-1's version was fancy; always-pass no-ops for checks tied
to removed systems or low value; `ProgramActive` always-true until the M4 program switcher.

Counts are actual failures from the M1 `KSP.log`.

| Type | Kind | Uses | Status | Notes |
|---|---|---|---|---|
| `ProgramActive` | requirement | 368 | **stub: always-true** | Real gating wired in **M4** (AxeProgramHandler). Parses `program` now. |
| `RP1CollectScience` | param | 63 | **real (simplified)** | Completes when science is received (recovered/transmitted) for a matching `subject` id or `experiment` (+ optional `targetBody`). No fractional/per-biome aggregation. |
| `RP1ReturnHome` | param | 74 | **real (simplified)** | Landed/splashed on home body. Dropped RP-1's maxSpeed/facility nuance. |
| `DownrangeDistance` | param | 10 | **real** | Great-circle distance flown from lift-off point. |
| `ReachMach` | param | 1 | **real** | `vessel.mach > mach`. |
| `AcceptContractBehaviour` | behaviour | 2 | **real** | Auto-accepts named contract on a lifecycle event. |
| `HorizontalLanding` | param | 19 | **real** | Glide check (horizontal speed > \|vertical\| × cot(descentAngle)), latched while airborne. Ported from RP-1. |
| `AvionicsCheck` | param | 12 | no-op | Avionics removed; RP-1's also auto-passed without it. |
| `VesselBuiltAt` | param | 27 | no-op | KCT removed; RP-1's also auto-passed without it. |
| `RP1Rendezvous` | param | 3 | no-op | Revisit: real proximity check (drop KCT "different-launch"). |
| `RP1NoDocking` | param | 1 | no-op | Revisit. |
| `ImpactCB` | param | 2 | no-op | Iconic (lunar impact); revisit to make real. |
| `RP1HasSamples` | param | 2 | no-op | Kerbalism sample check; revisit. |
| `RP1HasExperiment` | param | 2 | no-op | Kerbalism experiment check; revisit. |

Implementation: `Source/AXE/Contracts/` — `AxeAlwaysComplete.cs` (shared no-op), `NoOpFactories.cs`,
`ReachMach.cs`, `ReturnHome.cs`, `DownrangeDistance.cs`, `CollectScience.cs`, `ProgramActive.cs`,
`AcceptContract.cs`.

## Known M2 leftovers
- **Duplicate contract names:** ✅ resolved — `design/Contracts/DedupeContracts.cfg` deletes the
  redundant copy of `FirstTundraSat` (keeps `TargetedSats`) and `landingTriton` (keeps
  `NeptuneMoonLandings`), matched by `group`. (Confirm with the M2 in-game validation.)
- **Expression functions** (still deferred) `RP1CommsPayload()` / `RP1WeatherPayload()` (RP0 `ContractGUI`): used by
  3 advanced "Commercial Applications 2" contracts; those will fail to parse until we stub the
  functions. Out of MVP scope.
- No-op upgrades: promote `ImpactCB`, `RP1Rendezvous`, `HorizontalLanding`, Kerbalism sample/experiment
  to real checks in a later polish pass.
