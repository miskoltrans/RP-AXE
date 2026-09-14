# ksp-oracle

Runs KSP's **own** `Orbit` and `PatchedConics` outside the game — no Unity runtime, no running
KSP, no save — as a worker process that `tools/mission` can call tens of thousands of times a
minute.

```
pwsh tools/ksp-oracle/build.ps1        # compiles and runs the selftest
```

```python
from oracle import Oracle
orc = Oracle(system)                                   # system is an rss_ephem.System
traj = orc.shoot("Jupiter", r, v, ut0, ut0 + 400 * 86400)
many = orc.shoot_many(jobs)                            # one round trip, thousands of flights
```

`shoot` returns a real `patched.Trajectory`, so `enters`, `closest_approach` and
`arrival_report` all work unchanged.

## Why this exists

`patched.shoot` is a faithful replica: it agrees with the live game to **0.000 s** on SOI
transitions. The problem was never accuracy, it was **cost** — 3.4 seconds for a four-patch
flight. That one number is why `tour_plan.py` models flybys analytically instead of flying them,
and an analytic flyby is precisely the thing this project has already measured as failing: the
rotation formula is right to 0.08°, the epoch it is evaluated at is not. So the tour search
optimised a quantity that does not survive being flown, and a flyby had to actually happen
before the next one could be planned.

Measured, same trajectory, same machine:

| | replica | oracle |
|---|---|---|
| one 4-patch flight | 3,285.7 ms | 36.8 ms |
| batched, per flight | — | **0.462 ms** |
| an 86,400-shot flown tour search | 79 hours | **40 s** |

And it agrees with the replica where the replica was already right:

| check | result |
|---|---|
| ephemeris vs `rss_ephem`, 6 bodies | worst **9.1e-13** relative |
| patch chain | `Earth/enter:Moon -> Moon/exit -> Earth/exit -> Sun/horizon`, identical |
| all three SOI transition times | **0.000 s** apart |
| patch start positions | **0.0 m** apart |

## How it runs headless

`Orbit` and `PatchedConics` are pure managed arithmetic. What stops them running outside the
game is that `CelestialBody`, `OrbitDriver` and `Planetarium` derive from `MonoBehaviour`. Four
things get past that, and every one of them is load-bearing — miss any and you get a plausible,
self-consistent wrong answer rather than an error.

1. **Construct with `FormatterServices.GetUninitializedObject`.** No constructor runs, so nothing
   reaches for a native peer. `Orbit` itself is an ordinary class and is simply `new`ed.
2. **Write backing fields, not properties.** `CelestialBody.position`'s setter writes
   `bodyTransform.position` and throws; its getter is pure. `CelestialBody.orbit` is read-only
   and returns `orbitDriver.orbit`, so the driver is the only way to hang an orbit on a body.
3. **Fake the Unity liveness pointer.** `_CalculatePatch` contains
   `if (!orbitDriver.celestialBody) continue;`, and an uninitialized object reads as *destroyed*,
   so every body is skipped and no encounter is ever found. `IsNativeObjectAlive` is only
   `m_CachedPtr != IntPtr.Zero`, and `CompareBaseObjects`' both-non-null branch is plain
   reference equality, so any non-zero fake works and nothing dereferences it. Never call
   `GetInstanceID()`, which does.
4. **Set `StartUT` and `EndUT` before calling.** `CalculatePatch` searches between them.
   Without them the solver reports `ORBIT_INTERSECT` forever and never `ENCOUNTER` — it can see
   that the orbits cross and never that the body is there. `PatchedConicSolver` sets
   `StartUT = now`, `EndUT = StartUT + period` (or `period` alone when hyperbolic, which is
   `+Infinity`), plus `patchStartTransition = INITIAL`.

### The frame, which is the one that bites

`Planetarium.Zup` must be built with **`PlanetaryFrame(0, 90, 0)`**, not `SetFrame(0, 90, 0)` —
`SetFrame` takes radians and that 90 is degrees. `PlanetaryFrame` at `InverseRotAngle = 0` works
out to exactly the identity, which is what makes the element frame and the frame
`getRelativePositionAtUT` returns coincide.

Get it wrong and **every element is still bit-perfect**. `UpdateFromStateVectors` applies
`Zup.LocalToWorld` to its input and `getRelativePositionAtUT` applies `WorldToLocal` on the way
out, so a state vector round-trips cleanly through *any* Zup. But a body's orbit is built from
elements and never passes through Zup at all — so the vessel ends up in a rotated frame from the
bodies, and the only symptom is that no encounter is ever found. This cost an hour here. The
selftest now asserts `Zup` **is** the identity rather than that a round trip survives it.

`inverseRotAngle` is held at zero deliberately. In game it tracks the inverse-rotating body's
spin, which is why `getRelativePositionAtUT` does not return the element frame there — the trap
that once made `crosscheck` report a rotation as an epoch error.

## Deliberate differences from `patched.shoot`

* **`watch` is ignored.** KSP considers everything in `Planetarium.Orbits` and has no
  minimum-SOI cutoff, so Phobos-class bodies are *not* silently skipped the way the replica
  skips them by default.
* **A horizon past one revolution is not what the game does.** KSP gives patch 0 exactly one
  period, which is why the map view never shows an encounter two orbits out. Passing a longer
  `ut_end` is allowed and is reported back in `trajectory.note` rather than applied quietly.
* **Infinity and NaN cross the wire as `null`**, exactly as the in-game bridge does. A null
  `soi` or `apR` means infinite.

## Protocol

Line-delimited JSON on stdin/stdout — a pipe, not a socket, because nothing but the parent
should ever be able to reach it.

| op | |
|---|---|
| `ping` | version, and how many bodies are loaded |
| `system` | define the body tree (sent once, from `rss_ephem`) |
| `body` | one body's state at a UT — the ephemeris crosscheck |
| `shoot` | one flight |
| `shoot_batch` | many flights, one round trip — what a flown search should use |

The body tree comes from `rss_ephem` rather than being read here, on purpose. `rss_ephem`
already resolves the post-ModuleManager radii, the SOIs Kopernicus actually logged, the B1950
epoch and the RSS renames; a second reader would be a second source of truth free to drift from
the one every other tool uses.

`AxeJson.cs` and `AxeJsonReader.cs` are compiled straight out of `Source/AXE/Bridge` — the same
files the in-game bridge uses, already covered by `tools/bridge-test`.
