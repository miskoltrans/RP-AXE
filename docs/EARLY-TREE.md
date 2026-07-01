# Early Tree — Breakthrough Map (parts-first, to the first-orbit milestone)

Re-developing the early nodes from the **actual part subset** RP-1 uses up to first orbit
(`manifest/first-orbit-partlist.tsv`, 144 parts + 61 upgrades), on OUR terms — not a 1:1 copy of
RP-1's era×function grid.

**Philosophy (from the user):** a node is a **tech breakthrough**. It carries **1 or a few KING parts**
it directly enables — the hero(es) that *are* the breakthrough — plus a tail of **ride-along** parts
("…and here's more we found along the way"). The node's **science cost abstracts the R&D** for all the
unnamed parts/tech. So: pick the kings, hang the rest, let cost do the rest.

Legend: **★ king** · ride-alongs listed after · `[have]` = node exists in spine · `[NEW]` = to add ·
`[?]` = judgment call I want you to confirm. Probes (Sputnik/Vanguard/Pioneer) go to the `hire_*`
charters, off the main tree.

---

## Propulsion — liquid

- **Turbopump-Fed Liquid Propulsion** `[have: fd_turbopumpLiquid]`
  ★ `ROE-RD100` (V-2/RD-100) · ride: `ROE-A7` (Redstone), `ROE-RD200` (peroxide)
- **Rocket-Powered Research Aircraft** `[have: aero_rocketplane]`
  ★ `ROE-XLR11` (X-1) · ride: `ROE-XLR10`, `ROE-XLR25`, `ROE-XLR41`
- **Orbital Kerolox Booster (gas-generator)** `[have: fd_gasGenerator]`
  ★ `ROE-RD107`/`ROE-RD108` (R-7) · ride: `ROE-LR89(_2)` (Atlas), `ROE-LR79` (Thor), `ROE-LR105(_2)`,
  `ROE-LR101*` (verniers), `ROE-RD211`, `ROE-S155`, `ROE-Gamma301`, `ROE-S2253`, `ROE-Stentor`,
  `ROE-X405` (Vanguard), `ROE-JupiterVernier`, `YF2_Engine`, `YF2_with_shell`
- **Storable Hypergolic Upper Stage** `[NEW — Propellant Chemistry]` `[?]`
  ★ `ROE-AJ10Early` (AJ10) — the storable-propellant chemistry breakthrough; upper stages & spacecraft
  propulsion. *Missing from the spine entirely; AJ10 is a genuine king with no home.*

## Propulsion — solid

- **Cast Solid Rocket Motors** `[have: pc_solidGrain]`
  ★ `ROE-BabySergeant` (Explorer 1's spin-up upper) · ride: `ROE-BabySergeantX3(Dec)`, `…X11(Dec)`,
  `ROE-GCRC`, `ROE-25KS18000`, `ROE-18KS7800`, `ROE-NikeM5E1`

## Materials & Structures

- **Welded Pressure-Vessel Tankage** `[have: met_weldedSteel]`
  ★ `ROT-ServiceModule` · ride: `RO-RFTank-SM`, `ROT-MiscTank-ServiceModule`, `ROT-Nose-ServiceModule`
- **Isogrid Machined Tankage** `[NEW — Metallurgy, ~chem-milling]` `[?]`
  ★ `ROT-GenericTank-Integral` ("Isogrid Structure") · ride: every `ROT-*-Integral` (~15 modular tanks:
  Atlas/Booster/Katniss/Lander/Misc/Nose/Radial/Spherical/Toroidal), `RO-RFTank-Integral`
- **Steel Balloon Tankage (Atlas)** `[NEW — Metallurgy]` `[?]`
  ★ `ROT-AtlasTank-Balloon` (Atlas "steel balloon") · ride: `RO-RFTank-BalloonNew`, `ROT-BalloonTank-New`,
  `ROT-KatnissTank-Balloon`
- **Staging & Separation** `[have: str_stageSeparation]`
  ★ `Decoupler_1` (TD-12) · ride: `Decoupler_2`, `restock-decoupler/separator-1875-1`, `radialDecoupler1-2`,
  `radialDecoupler2`, `shortDecoupler1-2`, `ROE-CastorDecoupler`, `ROT-AtlasDecoupler`, sep motors
  (`sepMotor1/Large/Small`, `SnubOtron`)
- **Adapters, Couplers & Bays** `[ride-along → start/structures]` `[?]`
  `adapterSize2-Size1(Slant)`, `stackBiCoupler_v2`, `stackTriCoupler_v2`, `stackPoint1`, `ServiceBay_125_v2`,
  `ca_tank_mp_s` · plus oddballs `rotor_01`/`rotor_01s` (light rotors → Robotics later, or off)

## Avionics & Guidance

- **Spin-Stabilized Probe Core** `[have: mic_vacuumTubes — maybe rename]` `[?]`
  ★ `probeCoreSphere_v2` (Sputnik PS-1 core) · ride: `SXTSputnik`. *(The modular-Sputnik brain.)*
  — `gnc_rateGyros` and `tel_pcmTelemetry` already exist as the guidance/telemetry capability gates.

## Science instruments — the big gap (scatter by difficulty, per VISION)

- **Cosmic-Ray & Radiation Detection** `[NEW]` `[?]`
  ★ `RO-GeigerMuller` (Explorer 1 → the Van Allen belts) · ride: `RO-Micrometeorite`, `RP0probeVanguardXray`
- **Spaceborne Magnetometry** `[NEW]` `[?]` ★ `RO-EarlyMagnet`
- **Mass Spectrometry** `[NEW]` `[?]` ★ `RO-IonMassSpectrometer` · ride: `USFluidSpectroWedge`
- **Film & TV Imaging** `[have: opt_filmCameras, opt_tvImaging]` ★ `RO-BasicFilmCamera`, `RO-EarlyTVCamera`
- **Biological Sampling / Mystery Goo** `[NEW]` `[?]` — VISION says Goo scatters to **Metallurgy**
  (heavy structural sample box under thermal/atmo stress). ★ `GooExperiment` · ride: `BioCapsule`,
  `USGooBayWedge`, `SXTProbeGooo`, `BioCapsule`
- **Atmospheric Sounding** `[have-ish: barometer/thermometer at start]` ★ `USThermoBaroWedge` (wedge form)

## Power

- **Silicon Photovoltaics** `[have: elec_siliconPV]`
  ★ `ROS-StaticSolarPanel` · ride: `RO_EarlyTinySolarPanel`, `RO-rangerSolarPanel`
  — primary battery has no part (EC lives in the procedural avionics).

## Comms / Applications

- **Applications Satellite Bus** `[NEW]` `[?]`
  ★ `RP-1-CommunicationSat`, `RP-1-NavigationSat` — the first comsat/navsat buses (contract hardware).

## Aviation

- **Early Turbojet** `[have: met_turbojet]` ★ `RO-J35` · ride: `RO-VK1`
- **Axial Turbojet & Swept Wing** `[have: aero_transonicFlight]`
  ★ `RO-J47` · ride: `RO-J48`, `RO-JT3C`/`aje_j57`, `RO-Sapphire203`, `aje_avon`, `RO-RD9B`, cockpits
  (`RO-FighterInlineCockpit`, `SXTClyde`)
- **Supersonic Inlet & Airframe** `[have: aero_supersonicCruise]`
  ★ `RO-shockConeIntake125` + `RO-B9ProcWing-Supersonic` · ride: other shock-cone intakes, `RO-B9ProcAMWing/CS-Supersonic`,
  `SXTRadialAirIntakeShockCone`, `shockConeIntake`, `RO-X1Cockpit`, `SXTmk3Cockpit52`
- **Mach-2 Turbojet** `[have: aero_supersonicCruise, or split]` `[?]`
  ★ `aje_j79` (J79) · ride: `aje_j75`, `RO-AL7F`, `RO-Atar101D`
- **Ramjet Propulsion** `[NEW]` `[?]`
  ★ `RO-RJ43` / `RO-Nord1500` (combined-cycle) · ride: `RO-RJ47`, `RO-RJ55`
- **Reflight Structures** `[ride-along]` `KF-ALG-Medium` (gear), `airbrake1`, `nacelleBody`, `radialEngineBody`

## Upgrades (61)
Mostly `KEEP-engine` — the RFUpgrade config ladder rides its engine's node (A-9, Model39c, RD-101/102/103,
A-6/A-7, RD-107-8D74PS, J47/J57/J79 variants, …). Capability ones (`PFTech-Fairing-I`, `X2CockpitUpgrade`,
`HDD-Upgrade-Early`, `RP-1-PayloadTech`) ride their host node. `REFERENCE-avionics` (Science-Core / Near-Earth)
map to our avionics module. `DROP-axed-career` (rp0Engineer/Researcher, airlaunchTL) are already dropped.

---

## What this changes vs the current spine
**Kings with no home today → NEW nodes to add:** Storable Hypergolic Upper Stage (AJ10) · Isogrid Tankage ·
Balloon Tankage · Spin-Stabilized Probe Core · Radiation Detection · Magnetometry · Mass Spectrometry ·
Biological Sampling/Goo · Applications Satellite Bus · Mach-2 Turbojet · Ramjet. (~11 new breakthroughs.)
**Already right:** turbopump/rocketplane/gas-generator/solid propulsion, welded tankage, staging, PV,
early/swept/supersonic jets, film+TV imaging.

## Judgment calls for you (the `[?]`s)
1. **Science instruments** — separate breakthroughs per sensor (Geiger / magnetometer / mass-spec / Goo)?
   And does **Goo → Metallurgy** (VISION) or a Life-Support/Chem home?
2. **Tank materials** — are **isogrid** and **balloon** two distinct breakthroughs, or one "satellite-era
   tankage"? (RP-1 lumps all 35 at one node; I'd rather split by the real materials trick.)
3. **Applications satellite bus** — a real node, or does the comsat/navsat bus ride an integration node?
4. **AJ10 hypergolic upper stage** — confirm it earns its own Propellant-Chemistry node (I think yes).
5. Anything I mis-flagged as king vs ride-along.
