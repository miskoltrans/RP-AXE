# Human Orbital Spaceflight — King-Part Design Notes (next phase after First Orbit)

Derived from `manifest/human-orbital-partlist.md` (21 RP-1 nodes, ~140 new parts once earlyAvionics +
scienceSatellite are set aside as already-resolved). Same rule as `EARLY-TREE.md`: node = one
**non-obvious enabling breakthrough** (zero `&`), carrying a **⭐king** part + ride-alongs; cost
abstracts the R&D for the unnamed rest. This is a first pass — redline any of it.

## The framing that shapes it
First Orbit answered "can it fly." Human Orbital answers "can it fly *someone*, and get them back
alive." That's a small, sharp set of new irreducible requirements layered on top of the existing
`int_orbitalInsertion` booster: a sealed cabin (**Life Support** — new discipline, first use), a
heatshield that survives reentry (**Composite Materials** — new discipline, first use), and the
attitude control + parachute recovery the early tree *already built* for uncrewed probes. Two whole
RP-1 nodes (`earlyAvionics`, `scienceSatellite`) are re-listed in the partlist purely for
self-containedness — they were already placed in the first-orbit batch. **Skip them here.**

Most of the remaining 21 nodes are NOT new breakthroughs — they're later-year variants of engines and
systems the early tree already teaches (more `fd_multiChamber`/`fd_baffledInjector` engines, more RCS
blocks, more solar panels, bigger landing gear). Per the ENGINE PASS finding in `TREE.md` §9 ("9 solids
/ 6 multi-chamber on one node is correct king+ride-along, not a lump"), the right move for most of these
is to extend an **existing** node's `parts:` list, not mint a new one. Real judgment calls are flagged
as **Open calls** at the end.

---

## The milestone convergence

- **Crewed Reentry Capsule** `int_crewedCapsule` `[SystemsIntegration, T4]` — parents: `int_orbitalInsertion`,
  `gnc_rcs`, `aero_recovery`, `life_openLoopECLSS` (new), `cmp_ablativeTPS` (new). `anyToUnlock:false`.
  ⭐`ROC-MercuryCMBDB`. ride: `ROC-VostokCapsule`, `ROC-ZenitCapsule`, `mk1pod_v2`, `ROC-MercuryNoseCapBDB`,
  `ROC-MercuryAirbrakeBDB` (destabilizing flap — keeps the blunt end forward by design), `ROC-VostokService`,
  `RP0HumanRatedFlag`.
  *Same "relaxed convergence" test as `int_orbitalInsertion`: what's irreducible to fly a person to orbit
  and bring them home alive? An orbit-capable booster, attitude control to keep the heatshield forward,
  a heatshield, a way to decelerate, and air to breathe. Nothing else is physics — everything else
  (launch escape, a specific national capsule shape) is a practical-path nicety, kept off the gate per
  the same what-if principle that dropped staging/guidance from `int_orbitalInsertion`.*

- **Open-Loop Life Support** `life_openLoopECLSS` `[LifeSupport, T3]` — parents: `start`. ⭐`RO-LifeSupport-DummyEngine`
  (RP-1's life-support consumables module — lands, fittingly, in RP-1's own `crewSurvivability` node).
  *Bleed stored oxygen, scrub CO2 with lithium hydroxide, pack water and food for the mission's exact
  duration — the minimum a human needs to survive a sealed can for a day. First use of the LifeSupport
  lane (18-discipline set, previously untouched — the early tree never needed it).* Reuses the id/flavor
  seed already sketched in `tree/library.yaml`.

- **Ballistic Ablative Reentry** `cmp_ablativeTPS` `[CompositeMaterials, T3]` — parents: `start`.
  ⭐`RP0-SampleReturnCapsule` (deprecated but historically the right king — Corona/Discoverer-style
  film-return capsule). ride: `RP0-SampleReturnCommand`, `ROH-AdjustableHS`.
  *Proved uncrewed first: a spinning capsule with a phenolic char heatshield, snagged out of the air off
  a coastline, years before it ever carried a person. First use of the CompositeMaterials lane.* The
  Mercury/Vostok capsules' own integral heatshields (`ROC-MercuryHS`, etc.) ride inside
  `int_crewedCapsule` itself rather than duplicating a part here — same tech, already-integrated part.

## Refinement off the capsule (not a gate — see relaxed-convergence note above)

- **Pad/Ascent Abort Escape** `str_launchEscape` `[StructuresMechanisms, T4]` — parents: `int_crewedCapsule`.
  ⭐`ROC-MercuryLESBDB`. ride: `RO_mk1_LES`.
  *A solid tractor motor that yanks the capsule clear of a failing booster on explosive-bolt command — a
  distinct engineering problem (abort sensing + jettison logic + its own propulsion), not free with the
  capsule. Homed as a refinement, not a gate: a reckless program could fly without one, same reasoning
  that kept staging optional for orbit.*

## Scatter-aha inside the existing engine lines (no new gate)

- **Throttleable Restart Combustion** `fd_deepThrottleEarly` `[FluidDynamics, T3]` — parents: `fd_turbopumpFeed`.
  ⭐`ROE-XLR99` (X-15). *The world's first large, deeply throttleable, restartable liquid engine — a real
  scatter-aha, and a taste of `library.yaml`'s much later `fd_deepThrottle` (T8). Worth its own tiny node
  rather than folding into `fd_baffledInjector`'s ride-along pile, per the "one non-obvious breakthrough"
  rule — throttling is not what the LR89/LR79 boosters it's listed beside teach.*

- **Helical Directional Arrays** `tel_helicalDirectional` `[Telecommunications, T2]` — parents: `tel_telemetry`.
  ⭐`antenna_cone_toggle` (`digitalComms`). *Axial-mode helix gives circularly-polarized gain that tolerates
  a tumbling spacecraft. Reuses the id/flavor already seeded in `library.yaml`.*

## Ride-alongs only — extend an existing node, don't mint one

- **`highSpeedFlight`** (14 parts: bigger turbojets/turboprops/ramjets, `GearLarge`/`GearMedium`) → spread
  across `met_turbineAlloys` / `aero_areaRule` / `aero_afterburner` / `aero_ramjet` / `xplaneStart` by
  engine family (same capability-ladder judgment already used for the early tree's turbojets); landing
  gear rides `xplaneStart`.
- **`hypersonicFlightRP0`** (5 parts) → `aero_rocketplane` already carries `Mark1Cockpit`/`Mark2Cockpit`;
  add `MK1Cargobay`, `SXTSmallFuselage`, `vernierEngine`.
- **`earlyFlightControl`** (6 parts, RCS thruster variants + Agena Equipment Rack) → `gnc_rcs`.
- **`stabilityRP0`** (3 parts: `RO-KDU414`, `ROE-AgenaSPS`, `ROE-RangerRetro`) + **`solids1959`**'s Mercury
  retro pair (`ROC-MercuryRetroBDB`, `ROC-MercuryPosigradeBDB`) → ride `gnc_rcs` for now (see Open call 3
  for the fuller two-solutions treatment this could get instead).
- **`solids1959`**'s Scout-family stages (`ROE-Algol1`, `ROE-Altair`, `ROE-Antares1`) → `pc_solidGrains`.
- **`orbitalRocketry1958/1959/1960/1961`** (41 parts total, minus `ROE-XLR99` above) → spread across
  `fd_multiChamber` / `fd_baffledInjector` / `pc_hypergolics` by nation+family (per-engine judgment call,
  same tool-supported process as the early tree's engine pass) — see Open call 1 before doing this.
- **`materialsScienceHuman`** (4 parts: bigger service bays/radial tanks/nosecone) → `met_weldedTank` /
  `aero_fairings` ride-alongs, same as the early tree's procedural structure.
- **`primitiveSolarPanels`** (1 part) → `elec_siliconPV`.
- **`lunarRangeComms`** (1 part, `longAntenna`) → `tel_telemetry` (see Open call 4 on ordering vs
  `tel_helicalDirectional`).
- **`electronicsHuman`** (0 parts, 2 upgrades only) → no node; `RFTech-Battery-II` is a tier-upgrade with
  no part to hang a king on here (batteries are stock, ungated — this is just a capacity bump wherever
  the battery-bearing node ends up).
- **`earlyAvionics`, `scienceSatellite`** → already placed in `first-orbit-partlist.md`. Skip.

---

## Open calls

1. **The `orbitalRocketry1958–1961` engine-divergence question (carried over from `TREE.md` §9,
   DEFERRED).** These 41 engines are the historical moment the three orbital-thrust paths
   (Soviet multi-chamber / Western baffled-injector / hydrolox) would start to diverge into distinct
   national lines (R-7 successors → Metallurgy; Atlas/Titan → FluidDynamics; Agena/Centaur → Cryogenics
   per `library.yaml`'s later plan). Do we (a) just ride them onto the 3 existing nodes now and defer
   divergence to a later batch [recommended, keeps this batch small], or (b) start the divergent lines
   here since this milestone is literally when history forked? Saturn I's `H-1` clustering (in
   `orbitalRocketry1961`) is the strongest argument for "here" — clustering-for-heavy-lift is a genuine
   new breakthrough — but it also arguably belongs to a future lunar/heavy-lift batch, not "humans in
   orbit." **My lean: defer H-1/clustering to that future batch; ride the rest.**
2. **`humanRatedEDL`** (`SXTAirbag`, `SXTAirbagSmall`, `landingLeg1`, `miniLandingLeg`) — despite the RP-1
   name, these are stock aircraft landing-gear/airbag parts, not spacecraft lander legs. Likely a
   rocket-plane/lifting-body runway-recovery ride-along (`aero_rocketplane` or `xplaneStart`), but I'm not
   fully confident — flag for redline rather than guess.
3. **Orbital maneuvering as its own two-solutions node?** `stabilityRP0` + the Mercury retro pair read
   like a genuine multi-entry pair — solid single-shot retrofire (US, `ROC-MercuryRetroBDB`) vs
   restartable liquid maneuvering (Soviet, `ROE-AgenaSPS`) — mirroring `fd_multiChamber`/`fd_baffledInjector`.
   I folded them into `gnc_rcs` ride-alongs above to keep this batch smaller, but if the "choice should
   feel smart" philosophy applies here too, this could become `pc_solidRetrofire` ‖ `fd_restartableManeuvering`
   → a small multi-entry convergence. Your call — only 5 parts total, so low cost either way.
4. **`lunarRangeComms` vs `digitalComms` ordering** — `longAntenna` (Communotron 16) and `antenna_cone_toggle`
   (helical) are both single-part categories; which comes first (cost/tier) depends on which RP-1 places
   earlier in-game. Didn't verify tier order from the ConfigCache — check before wiring parents.
5. **`str_launchEscape`'s tier/parent** — proposed as a T4 child of `int_crewedCapsule`. Could equally be
   pulled forward to gate the capsule (if "no one would actually fly without one" outweighs the what-if
   principle) — see the relaxed-convergence note. Recommend keeping it a refinement, consistent with how
   `int_orbitalInsertion` already treats staging/guidance as optional.

## Node count
9 new nodes (2 new-discipline entry points + the milestone + a refinement + 2 scatter-ahas + 1 optional
multi-entry pair pending Open call 3) vs RP-1's 21 era-named nodes for the same ~140 parts. First new use
of the LifeSupport and CompositeMaterials disciplines.
