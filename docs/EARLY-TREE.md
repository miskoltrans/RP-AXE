# Early Tree — Optimal Node Design (parts-first, to first orbit)

Derived from the 395-part first-orbit partlist (`manifest/first-orbit-partlist.tsv`, MLP + cosmetics
set aside), on our terms. Node = one **non-obvious enabling breakthrough** (zero `&`), carrying a **⭐king**
part + ride-alongs; **cost abstracts the R&D** for the unnamed rest.

## The framing that shapes it
Reaching orbit is **two axes at once**, and the optimal tree makes both load-bearing:
1. **Propulsion** — exhaust velocity × thrust (the engine line).
2. **Structural mass-fraction** — how empty-light you can build (the tank line). *Atlas reached orbit because
   of its balloon tank as much as its engine.* So tankage is a first-class breakthrough line, not filler.
First Orbit is where those two lines meet **staging** and **guidance**. Everything else (the spacecraft, its
power, its senses) is a parallel spread you also grow. **Science is scattered by difficulty, never a branch.**

Tiers run **T0→T4** (deliberate 3–4-tier depth to orbit). `[NEW]` = didn't exist / re-derived.

---

## T0 — roots (parallel, thin)
- `start` — the shared toolbox (7 parts: proc structure/tank/nosecone/avionics/wing + barometer + thermometer). **Deliberately tiny.**
- `parking` (cost 999) · `hire_JPL` / `hire_OKB` (probe charters) — parallel roots, off the spine.

## T1 — the two programs
- **Sounding Rocketry** `[FluidDynamics]` — ⭐`ROE-Aerobee`; the de Laval nozzle + a spin-stabilised powder/liquid dart. ride: `ROE-ORM65`, `TinyTim`, `ROE-Veronique*`, `ROMeteoSustainer`, `basicFin`.
- **Cambered-Airfoil Flight** `[Aerodynamics]` — ⭐`SXTMerlin66prop`; the aviation start — a wing that flies and a piston to pull it. ride: **all props** (`SXT*Prop`, `SXTTinyprop`, Jumo/R-2800), early cockpits (`RO-OldFighterCockpit`, `RO-X1Cockpit`), `RO-B9ProcWing-Early`+CS, `Gear*`/`KF-ALG-*`, pitot intakes, tails, nose cones.

## T2 — first real breakthroughs
**Propulsion (Isp line)**
- **Turbopump Feed** `[FluidDynamics]` — ⭐`ROE-RD100` (V-2), ride `ROE-A4`, `ROE-A7`. *The pump breaks the tank-pressure ceiling — the first engine that can be big.* (RD-100 king, per redline.)
- **Composite Solid Grains** `[PropellantChemistry]` — ⭐`ROE-BabySergeant`; cast AP/Al grain. ride: Sergeant clusters, `ROE-GCRC`, `ROE-25KS18000`, `ROE-NikeM5E1`, `ROE-Aerobee`(solid var).

**Structure (mass-fraction line)**
- **Welded Pressure Vessels** `[Metallurgy]` — ⭐`ROT-ServiceModule`; the first tank that holds pressure and flies. ride: `ROT-*-SM`, `RO-RFTank-*`, `ROT-*-Separate` tanks.
- **Pyrotechnic Separation** `[StructuresMechanisms]` — ⭐`proceduralStackDecoupler`; cut a stage on command. ride: all decouplers/separators, `sepMotor*`, sep-motor solids, `KzThrustPlate`.

**Control**
- **Rate-Gyro Steering** `[GuidanceControl]` — capability + a programmed autopilot; steer the ascent.

**Aviation**
- **Turbine Superalloys** `[Metallurgy]` — ⭐`RO-DerwentV`; *the jet is unlocked by materials, not aero* — Nimonic blades survive the hot turbine. ride: `RO-J35`, `RO-VK1`. (scatter aha)

**Science (scattered)**
- **Exposure Sample Boxes** `[Metallurgy]` — ⭐`GooExperiment`; a heavy stress-box, not a delicate instrument (VISION). ride: `BioCapsule`, `USGooBayWedge`, `SXTProbeGooo`, **`RO-Micrometeorite`** (impact panel).
- **Ionization Counters** `[NuclearEngineering, early]` — ⭐`RO-GeigerMuller`; a gas-discharge tube that reads radiation. *Explorer 1 → Van Allen belts.* Homes early in the otherwise-empty Nuclear lane. ride: `RP0probeVanguardXray`.

## T3 — refinement to orbital class
**Propulsion**
- **Gas-Generator Cycle** `[FluidDynamics]` — ⭐`ROE-RD107`/`RD108` (R-7); bleed gas spins the pump, thrust at orbital scale. ride: `ROE-LR79`/`LR89`/`LR105`, verniers, `ROE-RD211`/`S155`/`Gamma301`/`X405`/`YF2*`/`Stentor`/`S2253`.
- **Hypergolic Ignition** `[PropellantChemistry]` — ⭐`ROE-AJ10Early`; contact-igniting storables → restartable upper stages. ride: `ROE-RD200`.

**Structure (mass-fraction)**
- **Chemical Milling** `[Metallurgy]` — ⭐`ROT-GenericTank-Integral`; etch away all non-load-path → isogrid at a fraction of the mass. ride: every `ROT-*-Integral`, `RO-RFTank-Integral`.
- **Pressure-Stabilized Monocoque** `[Metallurgy]` — ⭐`ROT-AtlasTank-Balloon`; a wall so thin it only holds shape under pressure. **The orbital enabler.** ride: `RO-RFTank-BalloonNew`, `ROT-*-Balloon`.
- **Stored-Strain Booms** `[StructuresMechanisms]` — ⭐`str_deployableBooms` part; a mast that springs out on orbit — **and the only way to read a clean magnetic field**, so ⭐`RO-EarlyMagnet` (magnetometry) rides here (scatter).

**Spacecraft systems**
- **Sealed Spacecraft Bus** `[Microelectronics]` — ⭐`ROT-ProbeCore` (king), ride `probeCoreSphere_v2` (Sputnik), `SXTSputnik`; a sealed, thermally-managed vessel that runs its own timeline unattended.
- **Reaction-Control Thrusters** `[GuidanceControl]` — ⭐`ROE-ModularRCS`; opposed cold-gas pairs. ride: the ~40 RCS blocks.
- **Photovoltaic Conversion** `[ElectricalPower]` — ⭐`ROS-StaticSolarPanel`; sunlight → watts, indefinitely. ride: `RO_EarlyTinySolarPanel`, `RO-rangerSolarPanel`.
- **Radiative Thermal Balance** `[Thermodynamics]` — reject heat with coatings/louvers alone (capability).
- **Directional Telemetry** `[Telecommunications]` — ⭐`SXTAntenna` (Sputnik beacon); ride `SurfAntenna`.
- **Staged Canopy Descent** `[Aerodynamics]` — ⭐`RC_cone` (king), ride `RC_radial`, `RC_cone_double`, `RC_stack`, `parachute*`. *Recovery — a real gap, now filled.*

**Science (scattered)**
- **Film-Return Optics** `[OpticsPhotonics]` — ⭐`RO-BasicFilmCamera`; expose + scan-transmit. ride `science_module`.
- **In-Situ Mass Spectrometry** `[Microelectronics]` — ⭐`RO-IonMassSpectrometer`; sort ions by mass. ride `USFluidSpectroWedge`. *(dedicated — no clean host.)*

**Aviation**
- **Transonic Area-Ruling** `[Aerodynamics]` — ⭐`RO-J47`; the coke-bottle waist through Mach 1. ride `RO-J48`/`JT3C`/`Sapphire`/`Avon`/`RD9B`, `aje_j57`, swept wings.
- **Shock-Compression Inlets** `[Aerodynamics]` — ⭐`RO-shockConeIntake125`; controlled shock train past Mach 2. ride the other shock cones, supersonic B9 wings.

## T4 — the milestone and its neighbours
- **First Orbital Capability** `[SystemsIntegration]` — CONVERGENCE of **Gas-Generator Cycle** (or your chosen engine) + **Pressure-Stabilized Monocoque** (mass fraction) + **Pyrotechnic Separation** + **Rate-Gyro Steering**. *You build your own satellite from the bus, power and antenna above.*
- **Applications Satellite Bus** `[SystemsIntegration]` — ⭐`RP-1-CommunicationSat`/`NavigationSat`; comsat/navsat that flies contracts and farms science. (branches off First Orbit.)
- **Vidicon Imaging** `[OpticsPhotonics]` — ⭐`RO-EarlyTVCamera`; live video, no film to recover.
- **Cryogenic Hydrogen Handling** `[Cryogenics]` — ⭐`ROE-RL10Fixed`; the LH2 problem → highest-Isp upper stage.
- **Afterburning Turbojets** `[Aerodynamics]` — ⭐`aje_j79`; ride `aje_j75`, `RO-AL7F`, `RO-Atar101D`.
- **Ram Compression** `[Aerodynamics]` — ⭐`RO-Nord1500`; discard the turbine above Mach 2. ride `RO-RJ43/47/55`.
- **Rocket-Boosted Airframes** `[Aerodynamics]` — ⭐`ROE-XLR11` (X-1); ride `XLR10/25/41`, X-15 cockpits → edge of space.

---

## Where the bulk goes (not breakthrough nodes)
- **Modular structure** (struts, I-beams, panels, trusses, adapters, couplers, wing connectors, winglets, tail fins) → ride-along on `start`'s procedural structure + `Pyrotechnic Separation`; not their own nodes.
- **Jettisonable fairings** (`Kz*`, `RSB*`, `SSTU*`) → one node **Fairing Jettison** `[Aerodynamics, T2]`, ⭐`KzResizableFairingBase`.
- **Cosmetics** (lights, hull-cameras, decals, ladders, non-MLP launch clamps) → **parking** (off-tree). Pure bloat, like the MLP set.

## Node count
~30 breakthrough nodes for the whole early game (both tracks + spacecraft + scattered science), across T1–T4,
vs RP-1's ~19 era×function nodes for the same parts. Kings assigned per your redlines. Names are a first pass —
redline any.

## Open calls
1. **Ionization Counters in the Nuclear lane** (early scatter) vs Microelectronics — I chose Nuclear.
2. **Magnetometer rolled onto the boom node** — good, or should magnetometry be dedicated?
3. **Turbine Superalloys** puts the first jet in Metallurgy — keep that scatter, or home jets in Aerodynamics?
