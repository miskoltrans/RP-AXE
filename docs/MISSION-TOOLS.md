# Mission tools

`tools/mission/` computes the three burns this project keeps needing — **ejection**,
**midcourse correction**, **flyby** — against *this install's* numbers, and checks each
answer by flying it.

```
python plan.py selftest                 # run this first, always
python plan.py depart  --vessel "Perun 2" --target Jupiter --peri 2.5Rj --push
python plan.py correct --vessel "Perun 1" --target Jupiter --peri 2.5Rj
python plan.py correct --vessel "Perun 1" --target Mercury --through Venus
python plan.py flyby   --vessel "Perun 1" Jupiter
python plan.py verify  --vessel "Perun 1" --target Jupiter
python plan.py window  Earth Jupiter 1964-01-01 1972-01-01 --site cape
python plan.py launch  --target Jupiter --depart 1966-09-26 --site cape --live --alarm
python plan.py alarms                          # what the game is holding
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
| `launch.py` | launch sites, launch azimuth, and when a pad crosses an orbit plane |
| `bridge.py` | client for the AXE bridge — queries, and the node/alarm writes |
| `mga.py` | multi-gravity-assist sequence search: Lambert legs joined by v-infinity matching |
| `plan.py` | the CLI |
| `selftest.py` | 64 checks; run before trusting a number |

## `mga.py` — finding a trajectory that does not exist yet

Everything else here *refines* a trajectory you already have. `mga.py` finds one from nothing:
give it a body sequence and a date window per body and it scans every leg with Lambert, then runs
a dynamic program over **pairs** of encounter dates — because a pair is exactly the state a flyby
couples. The leg before it sets v-infinity in, the leg after sets v-infinity out, and the flyby
itself can only rotate the vector, never lengthen it.

```
python mga.py Earth Jupiter Saturn Uranus Neptune     --win Earth   1977-07-15 1977-11-01 --step Earth   2      --win Jupiter 1979-01-15 1979-07-01 --step Jupiter 5      --win Saturn  1980-09-01 1981-06-01 --step Saturn  10     --win Uranus  1984-01-01 1985-06-01 --step Uranus  20     --win Neptune 1987-05-01 1988-02-01 --step Neptune 20     --cap Saturn 150000 --cap Uranus 100000 --max-c3 200
```

Three things it models that a chain of Lambert arcs does not:

* **A flyby's turn angle is bounded.** `delta_max = asin(1/e_in) + asin(1/e_out)` with
  `e = 1 + rp*vinf^2/mu`, and `rp` cannot go below the surface. Ask for more bend than that and the
  sequence is not free, whatever the legs say. `--rp-min` / `--rp-min-body` set the floor in radii.
* **v-infinity magnitude is conserved by an unpowered pass.** Any mismatch between the incoming and
  outgoing legs is a real burn at periapsis, priced with Oberth at the `rp` the turn actually wants.
* **`--cap BODY ALT_KM` carries the AXE flyby contracts' periapsis-ALTITUDE gate.** A gravity assist
  that needs to pass at 10 Rj cannot also bank a 150,000 km Jupiter flyby, so the cap is reported per
  body rather than silently assumed. This is what says which probe banks which contract.

**Validation: handed only date grids for Earth, Venus and Mercury it recovered Mariner 10** — launch
1973-11-03, Venus 1974-02-06 at 5,156 km altitude, Mercury 1974-04-01, C3 18.2 — from a blind scan,
which is the real mission to within the grid step. That is the check to re-run after touching it.

Things worth knowing before trusting an answer:

* **The costs are for RANKING, not for flying.** They are heliocentric Lambert values taken at the
  planet's CENTRE. Jupiter's SOI is 48.2 million km across, so the flyby really happens days from
  where the arc puts it. The winner still goes through `maneuver.aim_through` / `patched.shoot`.
* **A few tens of m/s at a flyby is grid resolution, not cost.** A truly ballistic solution sits
  between the sampled dates; refine the grid before believing a non-zero number.
* **The DP prunes to the best `--keep` states per arrival date, so it minimises total dV and nothing
  else.** It will happily return a 15-year arc that is 50 m/s cheaper than a 10-year one. To trade
  time against dV, narrow the final body's window and re-run — there is no `--max-span`.
* `--by-arrival` groups the output by final-arrival date instead of by departure, which is only
  useful when the destination window is wide.

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
patched-conic solver over a proposed burn; **`/bodies`**, which reports the SOI, the
FlightGlobals index and the rotation phase that KSPTOT does not send; **`/sites`**; and the
writes. It is **off by default** — a shipped mod has no business opening a socket uninvited.
Turn it on with any of:

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
4. **Rotation phase and the launch-site zero point** (`--sites`). Every rotating body's
   `rotationAngle`, and the constant that turns a pad's body-fixed longitude into an
   inertial one. Both are things a launch *time* is built on, and both would be wrong
   *consistently* if they were wrong at all — see below.

### Endpoints

| | |
|---|---|
| `GET /ping` | scene, game, UT, counts |
| `GET /bodies` | every celestial: μ, SOI, index, state vector, **rotation phase** |
| `GET /sites` | launch sites, their lat/lon, and the pad's inertial position |
| `GET /vessel` | live elements, **state vector**, and any nodes already placed |
| `GET /predict` | KSP's own patched conics over a *proposed* burn — places nothing |
| `GET /nodes` | a vessel's maneuver nodes and the flight plan they produce |
| `POST /node` | **place** maneuver nodes |
| `POST /node/clear` | remove them |
| `GET /alarms` | alarms, plus the type/action names KAC actually declares |
| `POST /alarm` | **create** an alarm (KAC, or the stock clock if KAC is absent) |
| `POST /alarm/delete` | remove one |

**Frames (bridge 1.1).** Every vector on this wire is the **element frame** — the one KSP's
own `inclination`/`LAN`/`argumentOfPeriapsis` use, and the one a replica built from Kopernicus
configs necessarily works in. That is *not* what `Orbit.getRelativePositionAtUT` returns; see
the traps below. Bridge 1.0 emitted elements in one frame and state vectors in another, which
made `crosscheck` report a rotation as an **epoch error**. `ping` reports the version and
`Planetarium.InverseRotAngle` so a client can tell which it is talking to.

**`/vessel` exists because `/predict` cannot replace it.** `/predict` reports patch *shapes* —
sma, ecc, inc, lan, argp — with no mean anomaly and no state vector, so a trajectory can be
*evaluated* through the bridge but not *propagated*, and solving a burn needs propagation.
KSPTOT Connect serves the same thing, but it is `[KSPAddon(Flight)]` and a separate process:
"the bridge is up" and "live state is available" were two different facts. `--live` now tries
KSPTOT, falls back to `/vessel`, and names both failures if neither answers.

**It is not read-only any more.** Writes are POST-only, so nothing that merely follows a
link can trip them, and the listener is still loopback — but the single `-axe-bridge`
opt-in now covers writes too. That is worth knowing before leaving `enabled = true` sitting
in a config file.

Two deliberate behaviours on `POST /node`. It returns KSP's resulting **flight plan in the
same response that placed the burn**, so a sign error shows up one line later rather than
three hours into a time warp — and `--push` prints it. And a node whose UT is already past
is refused rather than placed: KSP accepts one and then simply never flies it, which is the
worst of both. Pass `allow_past` if that is genuinely what you want.

KAC is bound by reflection, never referenced — a hard reference would make `AXE.dll` fail to
load on an install without KAC, taking the tech tree with it. Alarm type and action names
are resolved against KAC's **live** enums, so there is no copied list here to drift; an
unknown name comes back with the valid ones. `Contract`/`ContractAuto` are refused, because
KAC deletes alarms of those types the instant anything else creates them.

The transport is covered by `tools/bridge-test`, which compiles `AxeJson`, `AxeJsonReader`
and `AxeBridgeServer` outside KSP against one `Vector3d` stub and asserts 50 things about
them in about a second — HTTP framing, bodies split across segments, JSON round-tripping
bit-exact, comma-decimal locales, 90 concurrent requests each getting *their own* answer.

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

## Targeting through a gravity assist

`correct --target X` aims a B-plane at one body. Through a flyby that residual does not
exist until the trajectory is already nearly right — so it is flat, then discontinuous, and
least squares has nothing to descend. It rejects every burn date it tries.

`correct --through Venus --target Mercury` uses a different solver: a shooting pass over
**Earth SOI → heliocentric → Venus SOI → flyby → heliocentric → Mercury**, least squares on
the **position** residual at the destination. The assists are flown by the shooter, not
approximated. Measured on the Earth→Venus fixture: a 40,008 Mm miss closed to **1,357 km on
0.08 m/s**, in under a second.

Four things here were measured rather than reasoned, and each changed the design.

**The residual is differentiable through the flyby.** `d(miss)/d(dv)` is 31 Gm per m/s,
consistent from 0.001 to 0.01 m/s steps — it was never noise. What breaks a naive attempt is
that SciPy's `diff_step` is *relative*: `h = diff_step · max(1, |x|)`. Differentiating a
3 km/s ejection directly takes 30 m/s steps; differentiating around zero with the default
takes 0.1 mm/s ones, below the shooter's own SOI root-finding noise. Solving for a small
**correction to a guess** puts the step in the `|x| < 1` regime, where `diff_step` is the
absolute step in m/s.

**The arrival epoch cannot be guessed.** Aimed at dates the trajectory has no business being
near, every solve "fails" — with the target simply elsewhere in its orbit, 100 Gm away, and
no correction of any size relevant. The window comes from where the *uncorrected* trajectory
already passes the target, not from the user.

**Unbounded, the solver answers the wrong question.** It will find a wholly different
trajectory that happens to pass through the aim point: measured, a 4,892 m/s "solution" with
a 0.0 km miss. `--max-dv` bounds it — a bound is physical and has no weight to tune, unlike a
regularisation term.

**Losing the flyby is a topology change, not a bad aim.** With no Venus patch the destination
residual is measured on a different leg entirely and carries no gradient back. The tell was
every such case stalling at the *identical* 616,000 km — Venus's SOI radius to three figures.
Recovery steers to the assist instead, and re-acquires with `refine` first.

### What it does not do

Re-acquiring a **lost** flyby works in 2 of 4 tested perturbations. From-scratch MGA sequence
search — "is there a Venus assist to Mercury in 1968 at all" — is a different algorithm
(Lambert legs chained with v∞ matching at each flyby) and is not here. The failure message
says which case you are in rather than leaving you to find out.

`reachability()` answers the hopeless case in 0.1 s instead of grinding for 17: an
Earth→Venus flyby that leaves perihelion at 75.9 Gm cannot reach Mercury, whose aphelion is
69.8 Gm. The bend a flyby delivers is bounded by its v∞ and its minimum periapsis, so no
correction of any size closes that — and saying so *is* the answer.

## From a launch window to a launch

`window` finds *dates*. Getting off the ground needs three more things, and the chain runs:

```
window  Earth Jupiter 1964-01-01 1972-01-01 --site cape    # dates, and the plane each needs
launch  --target Jupiter --depart 1966-09-26 --site cape --live --alarm
                                                           # the time of day, and the heading
depart  --vessel "Perun 2" --target Jupiter --push --alarm # the ejection burn, into the game
```

**The plane.** A departure ΔV is meaningless without a parking-orbit RAAN — from an
arbitrary node an Earth→Moon injection costs 3,426 m/s with 1,100 m/s of plane change buried
in it, and 3,143 m/s essentially pure prograde from the coplanar node. `window` now solves
and prints the coplanar RAAN per window, and `depart --park ALT INC` re-solves it exactly.

**The time of day.** A pad at latitude φ passes through a plane of inclination *i* twice per
rotation, and only if |φ| ≤ *i* ≤ 180−|φ|. `launch` solves

```
sin(RAAN − α) = −tan(φ) / tan(i)
```

for the pad's inertial longitude α and inverts the (linear) rotation to get UT. Two roots,
one ascending and one descending, repeating once per **sidereal** day — the four-minutes-a-day
drift is what makes a window slip.

**The heading.** *Not* from `sin β = cos i / cos φ`. That formula cannot tell an ascending
pass from a descending one and loses the sign on a retrograde orbit, so the in-plane velocity
direction is built instead (`v = n × r`) and resolved into the pad's own east/north frame,
which gets every case right with no quadrant rule. `selftest` then checks the constructed
value *against* the textbook one for magnitude, which is what that formula is genuinely good
for. Two azimuths are printed: the inertial one, and the one to actually fly — the Cape
already supplies 408 m/s of eastward velocity, so the vehicle provides only the difference,
and the two differ by about 2°.

This immediately paid for itself. The September 1965 Earth→Jupiter window has a departure
declination of 32.4° against Cape Canaveral's 28.6° minimum inclination: **no parking orbit
from that pad contains the departure asymptote at all.** The table says `unreachable` instead
of quoting a ΔV that cannot be flown from there.

### The launch-site zero point

The one number here that could be quietly wrong. A pad's inertial longitude is its
body-fixed longitude plus how far the body has turned, and the third term — the constant
relating `CelestialBody.rotationAngle` to the frame orbits live in — is exactly zero, by
this argument:

* `GetWorldSurfacePosition` goes through `BodyFrame`, which is
  `PlanetaryFrame(0, 90, directRotAngle)`. Expand `CelestialFrame.SetFrame` and that is a
  plain rotation about z by `directRotAngle`, nothing more.
* For any body that is not the inverse-rotating one,
  `directRotAngle = rotationAngle − Planetarium.InverseRotAngle`.
* `Planetarium.Zup` is `PlanetaryFrame(0, 90, InverseRotAngle)`, so composing the two leaves
  `R_z(rotationAngle)` — and it **must**, because a pad's inertial position cannot depend on
  which body the game happens to be inverse-rotating around.

But `InverseRotAngle` is runtime state, rewritten every frame, and it only cancels for one of
`CelestialFrame`'s two conversion directions — whose names read the opposite way round from
the intuition, the same shape of trap as MechJeb stating the normal sign backwards twice.
Get it backwards and the offset becomes `−2 × InverseRotAngle`: wrong, drifting, and
self-consistent enough that nothing internal would ever notice.

So it is **measured, not asserted.** `/sites` reports the pad's actual inertial position at
the game's own UT; `launch --live` reads the offset off that. `crosscheck --sites` diffs it
against the offline constant and fails if they part — and the bridge reports the *wrong*
convention's answer alongside, so the cancellation is something you look at rather than
something you argue about. An uncalibrated answer says so in the output every time: the
spacing, the azimuth and the plane are right regardless, and only the absolute time of day
depends on the constant.

## The traps this encodes

Each of these has cost a mission or an evening. They are all now covered by `selftest`.

**A body's radius is what ModuleManager left, not what the .cfg wrote.** RSS ships
`Jupiter_Oblate.cfg` and three siblings that restate the gas giants' equatorial radius with
`@radius *= 1.0226...`. Read the raw config and Jupiter is **1,569 km small**, Saturn 2,000,
Uranus 192, Neptune 139 — while the other 28 bodies agree exactly, which is what kept it
hidden. The trajectory never notices, because radius does not enter the propagation. Every
printed altitude does, every `Rj` does, and so does any periapsis checked against a contract's
altitude gate — `orbitJupiter` asks for `maxPeA = Radius * 2`, which is 141,884 km and not
138,746. `ModuleManager.ConfigCache` is the post-patch truth and is already on disk, so
`rss_ephem` reads radius from there and keeps the config value as `radius_cfg`.

**An inbound patch starts exactly ON the SOI, and that must not read as "never exits".**
Every patch the shooter creates at an SOI entry begins with `|r| == soi` to within rounding.
`_exit_time` used to treat "outside the boundary and heading inward" as no exit at all, so an
escaping flyby came back reported as a capture and the trajectory stopped dead at the body it
had just entered. Which way it fell was decided by whether `|r| - soi` landed at `+1e-9` or
`-1e-9`: **the same Perun 1 trajectory answered "leaves SOI 1970-04-14" on one run and
"captured or it impacts" on the next**, with nothing changed but the save's UT. The scan now
starts from the first sample that is genuinely inside. The lunar check in `selftest` had been
silently truncated by this all along — it now flies `Earth/enter:Moon -> Moon/exit ->
Earth/exit -> Sun/horizon` where it used to stop at `Moon/horizon`.

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

**`CelestialFrame.WorldToLocal` and `LocalToWorld` read backwards.** `getRelativePositionAtUT`
returns a vector that `getTruePositionAtUT` merely swizzles and adds to the parent — no frame
conversion — while `GetOrbitNormal`, an inertial quantity built from LAN and inclination, is
`Zup.WorldToLocal(OrbitFrame.Z)`. So `LocalToWorld` is the direction *into* the frame orbits
are expressed in. Picking the plausible-sounding one instead puts every launch time out by
`2 × InverseRotAngle`, which drifts with the home body's rotation.

**`CelestialFrame`'s two conversions are not symmetric in the way the names suggest, and
`getRelativePositionAtUT` does not return the element frame.** Follow it down:
`getRelativePositionFromTrueAnomaly` → `getPositionFromTrueAnomaly(tA, worldToLocal: true)`,
which builds the vector from `OrbitFrame` and returns `Planetarium.Zup.WorldToLocal(...)` of it
— a rotation by −`InverseRotAngle` about z, by a *runtime* angle tracking the inverse-rotating
body's spin. So a body's state vector is rotated relative to its own elements, intermittently:
near zero the frames agree and everything looks fine. `Orbit.UpdateFromStateVectors` applies
`Zup.LocalToWorld` to its **input**, exactly inverting the accessor — which is why `/predict`
was always right and matched `PatchedConics` to 0.000 s. Mixing the two on one wire is what
turns a rotation into a false epoch alarm.

**`window`'s C3 and dV are body-centre Lambert values, on purpose.** `v_transfer − v_planet`
taken at the planet's centre, over ~90,000 arcs, because the SOI-crossing refinement costs a
propagation each. The error is smooth across windows so the *ranking* is right — but the burn
happens a few thousand km out and the vehicle crosses Earth's 924,649 km SOI days later, so
flying those numbers misses by millions of km. Pick a window with `window`; get a burn from
`depart`, which re-solves with the correction. The footnote says so on every run.

**Convergence tracks the size of the starting miss, not the physics.** When exactly one burn
date out of a smooth sweep converges, that is not a narrow window — neighbouring dates differ
by hours of coast, not by feasibility. It means the other seeds started too far out for least
squares to climb back. Suspect the seeding, not the geometry. `correct` now says this when it
sees a lone success, and says the converse when everything fails by a similar amount.

**A fixed sample count over a variable window loses fast flybys.** `_exit_time` scanned
`linspace(ut0, ut_end, 401)` — 401 samples across however long the caller was flying. A Venus
passage dwells 34.9 h inside a 616,000 km SOI; on a 715-day horizon the step is 43 h and the
*entire passage falls between two samples*, so "when does it leave" answered "never". The
shooter then reported an escaping gravity assist as a capture. The tell is that the answer
**depended on `--horizon`** — the same flyby, two verdicts. Size the scan window from the
conic (a few times `soi/v∞`), never from the caller's horizon.

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

### Aiming the arrival PLANE, and burning now (2026-09-11)

`--peri` fixes only how close you pass. `--bplane prograde|retrograde|polar|polar2` picks the
side, but "prograde" there means **ecliptic**-prograde: on Perun 2 Bus B it reached 2.00 Rj at
i 2.7 deg in KSP's frame, which is **25.6 deg off the Galilean plane** (the moons orbit at
i ~25.4, LAN ~358) and ~45 m/s more at the perijove-raise burn. **`--bplane plane:<Body>`**
lays the arrival orbit in that body's orbital plane, prograde, as near as the incoming
asymptote's declination allows: the orbit normal must be perpendicular to the asymptote `s`,
so the nearest normal to the plane's `n` is `n` minus its `s`-component, and `B` lies along
`s x w`. The floor `asin|s.n|` is printed ("X deg off Ganymede's plane, floor Y deg") and
cannot be bought from a midcourse burn at any price. Measured on Perun 2: `plane:Ganymede`
gave 4.12 deg against a 4.09 deg floor for **6.20 m/s**, cheaper than the ecliptic aim's 7.64.

The scan in `correct` samples burn dates from 2 % of the way to the encounter, which is ten
days out on a Jupiter cruise. **`--burn-at +1h` (or `+2d`, or a date)** solves the one burn
time you name instead, for when the burn has to happen before tomorrow's launch window.

**Verify a node before burning it.** `verify --save quicksave.sfs --vessel X` flies the SAVED
nodes and is the only place that prints "*** that periapsis is INSIDE Jupiter ***"; the bridge's
`/nodes` reports a periapsis radius with no comment. Both Perun 2 buses carried MCC nodes at
0.90 and 0.77 Rj -- a 6.8 m/s burn each, into the planet -- and looked fine in the map view.

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

64 checks, in two kinds. Internal ones catch arithmetic: two independent propagators agree
to 4e-12 over 400 random states, 37 circular orbits land exactly back on the start, energy
holds to 6e-16 over 3,000 days, elements and the node basis round-trip, a Lambert arc really
lands on its target position, the pad is exactly in the plane at every crossing reported, and
the launch plane's normal matches `park_orbit`'s angular momentum to 1e-16 — which is the
joint between the launch solver and every burn `plan.py` already prints.

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
- `--push` needs a real vessel, so it does not work off a `--park` orbit — that orbit is
  hypothetical and there is nothing in the game to hang a node on. It also needs the vessel
  to be the one being flown: KSP builds a `patchedConicSolver` for the active vessel only,
  and the bridge says which of the three possible reasons applies rather than just "no".
- KSCSwitcher **relocates** the single KSC rather than adding sites, so `/sites` reports one
  pad wherever the save put it. `launch` with no `--site` reads `LastLaunchSite` out of the
  save's `LastKSC` scenario module; the 29-site table comes from KSCSwitcher's and RSS's
  configs. RSS writes its readable site names behind a `//`, which is KSP's comment marker,
  so the parser strips them exactly as the game does — the real text is read from
  `RealSolarSystem/Localization/LaunchSites/en-us.cfg`.
