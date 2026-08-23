# Mission tools

`tools/mission/` computes the three burns this project keeps needing — **ejection**,
**midcourse correction**, **flyby** — against *this install's* numbers, and checks each
answer by flying it.

```
python plan.py selftest                 # run this first, always
python plan.py depart  --vessel "Perun 2" --target Jupiter --peri 2.5Rj
python plan.py correct --vessel "Perun 1" --target Jupiter --peri 2.5Rj
python plan.py flyby   --vessel "Perun 1" Jupiter
python plan.py verify  --vessel "Perun 1" --target Jupiter
python plan.py window  Earth Jupiter 1964-01-01 1972-01-01
python plan.py crosscheck --vessel "Perun 1"   # needs KSP running with -axe-bridge
```

Every burn prints as a UT plus the three `ManeuverNode` components, in the order and
signs KSP wants. Every answer is followed by a `FLOWN:` block — what the patched-conic
shooter says actually happens when that burn is flown to the target.

## Why the `FLOWN:` line exists

The failure that motivated all of this: a departure whose asymptote matched its Lambert
target to 0.0000 m/s, and which missed Jupiter by 295 Gm. Matching a v-infinity vector is
a *claim*. Flying the trajectory through its SOI transitions and reading off the arrival
periapsis is a *measurement*. Only the second one can be wrong out loud.

So the pipeline is always: analytic guess → shoot it → least-squares correct the burn
until the flown B-plane target is hit → shoot again and print the result.

## Layout

| file | what it owns |
|---|---|
| `cfgnode.py` | KSP ConfigNode reader, with the game's own one-key-per-line splitting |
| `rss_ephem.py` | every body: Kopernicus elements, plus index and SOI as the game computed them |
| `astro.py` | Shepperd propagator, elements, the maneuver-node basis, B-plane |
| `lambert.py` | Izzo 2015, zero- and multi-revolution |
| `sfs.py` | the save: game clock, vessel orbits, planned nodes |
| `patched.py` | the shooter — propagation through SOI entry and exit |
| `maneuver.py` | ejection / midcourse / flyby solvers and the differential corrector |
| `ksptot.py` | client for KSPTOT Connect — live vessel state, no new plugin needed |
| `bridge.py` | client for the AXE bridge — `/predict` and `/bodies` only |
| `plan.py` | the CLI |
| `selftest.py` | 27 checks; run before trusting a number |

Older single-purpose scripts (`porkchop.py`, `jupiter_arrival.py`, `jovian_tour.py`,
`link_budget.py`, `mass_budget.py`) still work and share `rss_ephem`.

## The live bridge

Live state comes from **KSPTOT Connect**, which ships with KSPTOT, is already installed at
`GameData/KSPTOTConnect`, listens on **8282**, and whitelists `127.0.0.1` unconditionally —
no flag, no config. `ksptot.py` speaks it. Its command set already covers `GetUT`,
`GetVesselIDList`, `GetVesselNameByGUID`, `GetVesselOrbitByGUID` and the maneuver nodes, so
none of that is duplicated here. Two limits: it is `[KSPAddon(Startup.Flight)]`, so it only
answers while a vessel is being flown; and `GetVesselIDList` returns *commandable* craft
only, so debris is invisible to it.

Its wire format is `[32 bytes ASCII command, SPACE-padded][1 byte class][4 bytes uint32 BE
length][data]`. The space padding has to be measured, not read: `NetworkMessage.GetRawMessage`
writes the command into a zero-filled buffer, and a NUL-padded request is dropped silently —
zero bytes back, no error.

`AXE.dll` covers only what KSPTOT Connect cannot: **`/predict`**, which runs KSP's own
patched-conic solver over a proposed burn, and **`/bodies`**, which reports the SOI and the
FlightGlobals index that KSPTOT does not send. It is **off by default** — a shipped mod has
no business opening a socket uninvited. Turn it on with any of:

```
KSP_x64.exe -axe-bridge
AXE_BRIDGE=1
enabled = true      in GameData/RP-AXE/Plugins/PluginData/Bridge.cfg
```

Then:

```
python plan.py bridge --vessels                  # what is the game holding right now
python plan.py crosscheck --vessel "Perun 1"     # diff this toolchain against KSP
python plan.py correct --vessel "Perun 1" --target Jupiter --live
```

`--live` works on `depart`, `correct`, `flyby` and `verify`, and takes state from the game
rather than the save. That removes the single most likely source of a wrong answer in
practice: **the save is only as fresh as the last save.**

### `crosscheck` — the part that matters

Three comparisons, each against KSP rather than against more of my own code:

1. **Ephemeris.** Every body's position at the game's own UT, game vs. this toolchain. A
   wrong epoch moves every body *consistently*, so nothing internal notices — but the game
   is not in on it. This check would have caught the B1950 bug in one command. It also
   diffs μ, SOI and the `FlightGlobals.Bodies` index.
2. **Vessel state.** KSPTOT Connect's live reading against the one rebuilt from the save's
   elements. A disagreement is either a reader bug or simply a stale save, and the UTs
   printed alongside tell you which.
3. **The shooter vs `PatchedConics`.** `/predict` applies a proposed burn to a throwaway
   `Orbit` and runs *KSP's own* patched-conic solver over it, returning every patch. The
   command lines that up against `patched.shoot` and reports, per patch, whether the bodies
   match, how far apart the SOI transitions are, and how far apart the periapsides are.

Endpoints: `/ping`, `/bodies`, `/predict`. There is no write endpoint — it cannot place a
node or touch a save. (KSPTOT Connect *does* have `NodeData` / `NodeDataWRTPeri`, so pushing
a node into the game is already solved if that is ever wanted.)

For a repeatable session, `-axe-load=<save>` loads a save straight from the main menu and
`-axe-focus=<vessel>` flies one, so a crosscheck needs no clicking. Both are command-line
only, never config — a stray cfg value that loads someone's save on every launch is a far
worse failure than typing a flag.

### What it measured

Run against the live game (RSS/RO career at UT 496,651,291), the answer to "how far does
this replica drift from KSP" is: **not measurably.**

| check | result |
|---|---|
| every body's position, game vs. replica | worst **1.2e-11** relative, over 32 bodies |
| μ, SOI, and body index | identical for all 33 |
| vessel state, KSPTOT vs. the save reader | **0.000000 m**, 0 m/s |
| three-way: KSPTOT vs. AXE vs. save | agree to **66 µm** |
| SOI transition times, shooter vs. `PatchedConics` | **0.000 s** across a 3-year, 3-patch trajectory |
| Jupiter periapsis after capture | 183,655.4 km both, **0.0 km** apart |
| post-flyby solar periapsis | 770,364,920.3 km both, **0.0 km** apart |

The transport is separately covered by a standalone harness that compiles `AxeJson.cs` and
`AxeBridgeServer.cs` outside KSP — neither has a KSP dependency. That confirms doubles
round-trip bit-exact, `NaN`/`Infinity` serialise as `null`, strings escape, values stay
invariant under a comma-decimal locale, a throwing handler returns HTTP 500 without killing
the server, and 90 concurrent requests across 6 threads all succeed.

**Threading.** Accept and socket I/O run off the main thread; every handler runs *on* it, via
a queue that the worker blocks on. Nothing in the KSP or Unity API is thread-safe, and
touching `FlightGlobals` from a socket thread shows up as a native crash in `Player.log` with
no managed stack. KSPTOT Connect is built the same way for the same reason.

## The traps this encodes

Each of these has cost a mission or an evening. They are all now covered by `selftest`.

**RSS states its elements at B1950.0, not at UT 0.** `RSSKopernicusSettings.cfg` carries
`Epoch = -31542641.784` and Kopernicus propagates `M(t) = M0 + n(t - Epoch)`. Ignore it and
every body is 365.08 days out of phase — *self-consistently*, so Lambert still closes to
zero, the synodic spacing is still exactly right, and the phase angle still matches the
textbook. Nothing internal can detect it.

**A maneuver node's normal component is `+h`, and MechJeb's source says otherwise twice.**
`OrbitExtensions.DeltaVToManeuverNodeCoordinates` writes `dot(-NormalPlus, dV)` into
`DeltaV.y`, but its own `OrbitNormal()` is `-GetOrbitNormal().xzy`, and stock's
`Orbit.GetOrbitNormal()` is `Zup.WorldToLocal(OrbitFrame.Z)` with
`OrbitFrame.Z = normalize(cross(pos, vel))`. The two negations cancel. In the right-handed
z-up frame:

```
prograde = v_hat
normal   = normalize(r x v)
radial   = normalize(v_hat x normal)      # == the part of r_hat perpendicular to v
node.DeltaV = (radial, normal, prograde)
```

This is pinned by an *empirical* test, not by reading source: `selftest` takes a maneuver
node the game itself planned and flies it. As saved, Perun 1's node produces a 2.65 Rj
Jupiter periapsis; with normal flipped it is 21.68 Rj, with radial flipped 0.23 Rj (inside
the planet), with prograde flipped 409 Rj.

**`ORBIT.REF` is the *runtime* `flightGlobalsIndex`, not the one in the .cfg.** It indexes
`FlightGlobals.Bodies`, and Kopernicus renumbers `flightGlobalsIndex` on load so the two
agree at runtime — measured across all 33 bodies through the bridge, `index ==
flight_globals_index` every time. The **config** value is only a load-order hint and
disagrees for 25 of 33: Ceres is `flightGlobalsIndex = 50` in its cfg and `12` at runtime,
Callisto `4` and `15`. `Kopernicus.log` records the runtime numbering — `Found Body:
Moon:9 -> SOI = 66167158.65` — so that file is read rather than the cfg. Newer saves also
write `ORBIT.IDENT` with the body *name*, which is preferred when present.

**A body's SOI is not always `a*(mu/mu_parent)^0.4`.** Phobos, Deimos and Mimas carry an
explicit `sphereOfInfluence`. Phobos' is 47 km against a 7.2 km Hill sphere — six times
larger. The same `Kopernicus.log` line gives the SOI the game is actually using.

**`ORBIT.MNA` is radians; `INC`/`LPE`/`LAN` are degrees.** Reading MNA as degrees puts a
vessel most of the way around its orbit while every other element still looks right.

**RSS renames Kerbin to Earth with `cbNameLater`, but the Moon's `referenceBody` still says
`Kerbin`.** Unaliased, Earth silently has no children and no lunar transfer can be planned.

**The departure v-infinity is not `v_transfer - v_planet` at the planet's centre.** The burn
happens 6,600 km out and the vehicle crosses the SOI a million km away, days later. Like
MechJeb's `TransferCalculator.OptimizeEjection`, the transfer conic is propagated to where
it actually crosses the departure SOI and the relative velocity *there* is converted to a
v-infinity. Worth ~60 m/s on an Earth→Mars departure — small, but it is the difference
between a periapsis and a miss.

**Correction cost is not monotonic in burn date.** For Perun 1 → Jupiter it runs 119 m/s at
T+23 d, 68 m/s at T+167 d, and 460 m/s at T+892 d. "Burn as early as possible" is wrong;
`correct` prints the whole table so the minimum is visible rather than assumed.

**Departure cost is meaningless without a parking-orbit RAAN.** From an arbitrary node, an
Earth→Moon injection came out at 3,426 m/s with 1,100 m/s of normal in it. From the
coplanar node it is 3,143 m/s, essentially pure prograde. When `--park` is given without a
RAAN, the coplanar one is solved for and reported; pass three numbers to pin your own.

## Where the algorithms come from

Decompiled from the install's own `MechJeb2.dll` / `MechJebLib.dll` and `Assembly-CSharp.dll`:

- ejection geometry — `MechJebLib.FunctionImpls.RealSingleImpulseHyperbolicBurn`
  (with one deliberate change: MechJeb brackets its rotation parameter over ±30 **radians**
  and hands that to Brent, so which local minimum it finds depends on where Brent steps.
  `single_impulse_hyperbolic_burn` scans a full turn first and refines the best basin.)
- propagation — `MechJebLib.TwoBody.Shepperd`
- SOI patching — `OrbitalManeuverCalculator.PatchedConicInterceptBody` / `SOI_intercept`
- midcourse search — `OrbitalManeuverCalculator.DeltaVAndTimeForCheapestCourseCorrection`
- node basis — `OrbitExtensions.DeltaVToManeuverNodeCoordinates` and stock `Orbit.GetOrbitNormal`

## What `selftest` checks

27 checks, in two kinds. Internal ones catch arithmetic: two independent propagators agree
to 4e-12 over 400 random states, 37 circular orbits land exactly back on the start, energy
holds to 6e-16 over 3,000 days, elements and the node basis round-trip, a Lambert arc really
lands on its target position.

The ones that matter compare against something outside the code: Kopernicus' own log,
KSPTOT's `bodies.ini` (exported from the running game by its plugin — 32 bodies agree to
3e-14 on semi-major axis), a maneuver node the game planned, and an ejection burn measured
at SOI exit rather than asserted. Those are what catch the failures that stay
self-consistent, which is every failure this project has actually had.

## Notes

- Bodies with SOIs under 1,000 km (Phobos, Deimos, Mimas) are not watched for SOI entry by
  default — name them with `--via` if you need them. The set actually considered is
  recorded on every trajectory.
- `window` drops local minima worse than 3× the best C3, because once the real windows run
  out the next-best rows are not windows. It says how many it dropped.
- `--horizon` is days past arrival to keep flying; a large SOI like Jupiter's takes
  hundreds of days to cross, so raise it if a flyby reports no exit.
