# RP-AXE — Canonical Part List (T1 curation log)

Working doc for T1 (lock the part list before building the tree). Built by comparing clean/expanded
RO and RP-1 reference installs. Tooling: `tools/ro_coverage.py` parser; diff scripts in scratchpad.

## Curation rule (the line we curate on)
1. **Plausibility floor is automatic.** RO's `HardRemoveNonRO` flag (shipped by RP-1-ExpressInstall,
   `RP1Express.cfg` → `:FOR[HardRemoveNonRO]`) makes RealismOverhaul **delete** every non-RO part
   instead of tagging it. So anything un-physical (e.g. KerbalFoundries anti-grav repulsors) is gone
   before we even look. **RO-config floor ≈ "physically plausible".** → AXE keeps this flag; the old
   D10 "sack non-RO to a node" machinery is unnecessary.
2. **Eligible = real spaceflight history OR plausible real engineering** (= RO-configured). History is
   the floor we extend from; plausible future/ahistorical tech is allowed; don't invent what we don't
   have to invent.
3. **From the eligible set, exclude REDUNDANT or LOW-VALUE parts.** That's the actual curation work.
   *"Low-value" is not yet defined — discover it as we curate.*

## Key mechanics found
- Both clean installs run `HardRemoveNonRO` → **0 non-RO parts present** in any reference install; only
  RO-supported subsets exist (e.g. Tantares: 324 PART nodes defined in-folder → **120** survive).
- Clean part-universe diff (RO_clean 1331 ↔ RP1_clean 1282): **1116 shared** RO core · RP-1 **drops 215**
  (RO-supported parts it chose to cut) · RP-1-base adds 166 (SXT/VenStock/RP-1/Kerbalism).
- Expanded adds the **same 35 candidate mods** to both flavours; ro flavour ends +816 parts, rp1 flavour
  +444 — the gap is RP-1's stricter per-pack curation (analysis below).

## 215-drop review (RP-1's clean removals) — DECISIONS
- **187 stock/MH parts** (Squad 134 + SquadExpansion 53): ✅ **inherit the cut** (procedural + RO replace
  them) — the bloat removal we want.
- **28 non-stock drops, by flagged category:**

| Cat | Parts | Decision |
|---|---|---|
| 1 · RO parts | `B10_APASv2` (APAS-95 dock), `ROE-ModularResistojetRCS` | ✅ **Drop** — duplicates available elsewhere |
| 2 · ProceduralParts RF | `proceduralTankOre`; `proceduralTankRealFuels`; `proceduralSRBRealFuels` | ✅ **Keep Ore** (ISRU); **sack** the PP tank (covered by `RO-RFTank-*` series + ROTanks) and the PP SRB |
| 3 · ReStockPlus | Saturn I + IB/V IUs; inflatable airlock; 3 fairings, 2 adapters, battery, nosecone | ✅ **Keep** the 2 Saturn IUs (+ tag with AXE avionics) and the airlock; **sack** the rest (procedural fairings/adapters cover them) |
| 4 · KerbalFoundries | rover wheels (kept by RP-1); 8 tracks, screw-drive, skid, truck wheels | ✅ **Keep the plausible mobility** (reverse RP-1's cut) — all real engineering; screw-drive flagged for the "low-value" pass |

### Build notes carried forward
- Kept Saturn IUs (and historical avionics generally) get the **AXE avionics module/tag** at placement.
- Sacking the procedural SRB → **RocketMotorMenagerie becomes the solids workhorse** (likely dependency).
- **Park for the avionics phase (P4):** RealismOverhaul ships its own historical avionics parts
  (`RealismOverhaul/Parts/Avionics/Able/Agena/Centaur/Delta` + Saturn) that RP-1 drops — strong
  keep-and-tag candidates.

## Science system — RP-1's RP0* is the backbone (curation decoupled from science)
Investigated via reference caches (`ro_expanded` = native/no-Kerbalism; `rp1_expanded` = real baseline).
- **RP-1 + Kerbalism IS the science baseline.** It strips every mod's *native* experiments and assigns its
  own **RP0\* suite: 96 experiments / 69 instrument families** — tiered (massSpec ×4, imageSpec ×4,
  infraredRad ×4, photos ×4, visibleImaging ×5, magScan ×3, RPWS ×3, cosmicRay/bioScan ×2) + ~55 one-off
  historical experiments (ALSEP, lunar seismic network, ISRU demo, supersonic flight, TV broadcast,
  materials processing, biology, UV/X-ray astronomy…). Ported wholesale like contracts.
- **Instruments = RP-1's own 32 `category=Science` parts** (`RO-IonMassSpectrometer`→massSpec1,
  `RO-EarlyMagnet`→magScan1, the TV/film-camera, IR-radiometer, UV/IR-spectrometer, RPWS, cosmic-ray
  tiers — one part per experiment tier). **This is the instrument backbone.**
- **Every other mod's dedicated instruments are REDUNDANT → RP-1 cuts them.** Confirmed: Coatl's **29**
  native instruments → **all 29 cut**; DMagic's surviving 5 add **0 unique** (US-wedge reskins). Inherit.
- **Only SSPX (+20 unique) and US2 (+7 unique) ADD science** — sole carriers of station/lab/long-duration
  science (closed-loop ag, materials, lunar surface, UV/X-ray astronomy) + stock goo/seismic/materials.
  **Keep their science parts.**
- **Consequences:** (1) science-part curation = HARDWARE merit; cutting redundant instruments loses **no**
  science (RP0* rides along on RP-1-configured buses). (2) Vision's "balance around **DMagic**" is
  superseded — DMagic instruments are redundant reskins of RP-1's; backbone is RP0*. (3) value-add parts
  beyond RP-1's set carry **no** science until we author RP0* assignments (→ gap-fill list). (4) **SCANsat
  absent** → stock orbital/surface scanners are inert (no experiment); revisit if SCANsat is added.

### Parked: KerbalismExpanded — instrument-MODEL remap candidates (revisit when/if added)
User may later add **KerbalismExpanded** (adds NEW experiments beyond RP-1's RP0*). Implication for our
science cuts: a part cut as "redundant instrument" may actually be a **unique real-instrument MODEL** with
no current RP0* config that could be **remapped** to a future KerbalismExpanded experiment. So when cutting
science/instrument parts, distinguish *redundant model* (cut freely) from **unique-instrument model**
(cut-for-now but **flag as a remap candidate** — keep recoverable, e.g. route to the Experimental node,
don't lose the asset). Revisit the cut-instrument list when KerbalismExpanded is in.
**Known remap candidates so far:** Coatl MOLA laser altimeter, HiRISE telescope, IUVS UV / THEMIS IR
spectrometers, gamma-ray spectrometer, dust collectors; Tantares **Travers SAR** (synthetic-aperture radar)
+ **Priroda** earth-resources camera. (These are unique instruments, *not* duplicates of RP-1's RO-* set.)

## Per-mod expanded-pack curation (in progress)
Going mod-by-mod through RP-1's per-pack cuts, recording AXE's call. Lens: **science/exploration delivery
+ real-engineering education** is the value axis (science is the central pillar; probes are liked because
they deliver it). Inherit RP-1's redundant/low-value cuts; reverse cuts of science/exploration-delivery or
historical-education parts.

**Low-value (emerging definition, from these calls):** standalone duplicate **solar panels** (RO/procedural
solar covers them); **mod-specific science instruments** (→ DMagic); **part-specific decouplers/RCS/legs**
(→ generic/procedural); **deprecated** dupes; niche film-return **spy-sat** subsystems (KH-9).

| Mod | RO has | AXE keeps | Notes |
|---|---|---|---|
| RN_US_Probes | 106 | **75** | Inherit 31 component cuts: 11 std solar panels (redundant), 12-part KH-9 spy-sat family, 8 part-specific decouplers/RCS/legs. Reverse: 13 iconic whole-probes (Mariner-Mars 3/4–10, LRO, LADEE, LCROSS, Juno, Helios, Mars Observer, Sphinx, TDRS A-G) **+ the 3 orbital/mapping scanners** (Galileo/LADEE/Magellan — SCANsat/ISRU hardware, *not* science; final config pends SCANsat decision). Prune RaiderNick's 3 internal `DEPRECATED` dupes. |
| RN_Soviet_Probes | 27 | **23** | Reverse 15 whole probes + integral sub-parts (Luna 2/3/10/11/13, Venera 1, Molniya-1, Polyot, Proton 1-4 sats, Strela bus + astro/radio/vernier). Inherit 4 redundant cuts: `molniya_asas` (deprecated), 2 RCS blocks (Venera/Strela → generic), 1 payload decoupler. Corrects RP-1's US-centric bias (kept only 8/27). |
| CoatlAerospace | 123 | **74** | Inherit RP-1's 49 cuts: all **29 dedicated instruments** (redundant with RP-1's RO-* set, per Science section) + 8 solar panels + 4 batteries + 2 tanks + RCS/misc. Keep the **hardware** (buses, antennas, RTGs, reaction wheels, EDL aeroshells). Optional adds flagged: SSTL-150 bus, STAR-24C motor. |
| Tantares | 119 | **48** | Value-add over RP-1 (RP-1 cut all 119). Cut ~71 redundant: engines→ROEngines, capsules→ROCapsules, generic structural→SSPX, solar/tanks/RCS/radiators→procedural/RO, antennas→RealAntennas; + ISS-Russian segment (Zarya/Zvezda/Nauka/Pirs ~22). Keep recognizable Soviet craft (Mir complex + LK-700 + TKS); 2 instruments → Experimental remap. **Exact list in Curated keep-lists below.** |
| TantaresLV | 1 | **0** | inherit RP-1's cut (ROEngines/procedural cover). |
| KerwisChineseAerospacePack | 62 | **19** | Pure Long March launch-vehicle pack (no crewed craft). Keep RP-1's **18 YF engines** (unique — 0 YF in ROEngines, fills the Chinese-engine gap) + add **`DFH-1`** (DongFangHong-1, first satellite — historical-firsts education). Cut 43 structural: CZ tanks/upper-stages, 7 fairings, 5 VEB instrument compartments, adapters/interstages/wings → procedural. |
| NearFuturePropulsion | 26 | **20** | inherit RP-1 — cut 4 xenon/argon tanks (→ procedural RF) + 2 dup thruster variants (EPEX MPD, Starlink HET); keep the 20 real electric thrusters (Hall/ion/VASIMR/MPD/PIT). |
| NearFutureConstruction / NF-Electrical | 47 / 33 | **36 / 20** | inherit RP-1's trim-redundant pattern (redundant tanks/variants cut, future content kept). |
| NF-Exploration / NF-LaunchVehicles / NF-Aeronautics | 20 / 12 / 5 | **kept whole** | inherit RP-1 (kept entirely). |
| KerbalAtomics / CryoEngines / FarFutureTechnologies / RocketMotorMenagerie / HullCameraVDS | 3 / 7 / 21 / 6 / 11 | **kept whole** | inherit RP-1 — unique future-propulsion/camera content (RMM = our solids workhorse). |
| NearFutureSolar | 29 | **6** | Rest redundant with RO's 4 *resizable* solar panels (solar = low-value rule). Keep a curated **"advanced solar" tier** of distinct tech RO doesn't convey (concentrating PV + roll-out blanket + large rigid + curved). List below. |
| NearFutureSpacecraft | 3 | **0** | The 3 RO-supported parts are just RCS thrusters (the pods were non-RO, already deleted) → redundant with RO/stock RCS. **Mod removed from `../expansion modpack.ckan`** (nothing to keep). |

## Curated keep-lists (exact part names, manifest-ready)
### Tantares — 48 kept
- **LK-700 lander (7):** `aquarius_crew_s1p5_1` `vela_landing_leg_srf_1` `vela_landing_leg_srf_2` `aquarius_heatshield_s1p5_1` `aquarius_drogue_parachute_s0_1` `aquarius_parachute_s0p5_1` `vela_high_gain_antenna_srf_1`
- **Mir Core (5):** `eridani_crew_s2_1` `eridani_crew_s2_s1p5_1` `eridani_crew_s1p5_1` `aquila_node_s0p5_1` `eridani_node_adapter_s1p5_s0p5_1`
- **Kvant-1 (3):** `acamar_adapter_s2_s0p5_1` `acamar_crew_s2_1` `acamar_science_processor_s2_1`
- **Kvant-2 (5):** `ro_kvant-2_adapter_s2_s0p5_1` `ro_kvant-2_adapter_s2_s1p5_1` `ro_kvant-2_crew_s1p5_2` `aquila_crew_s1_3` `aquila_lab_s1_1`
- **Kristall (7):** `aquila_adapter_s2_s0p5_1` `aquila_adapter_s2_s1p5_1` `aquila_crew_s1p5_2` `aquila_crew_s1_1` `aquila_adapter_s1p5_1` `aquila_node_s0p5_2` `aquila_node_adapter_s1_1`
- **Spektr (5):** `ro_spektr_adapter_s2_s0p5_1` `ro_spektr_adapter_s2_s1p5_1` `ro_spektr_crew_s1p5_2` `aquila_structural_cone_s1p5_1` `aquila_lab_s1p5_1`
- **Priroda (5):** `ro_priroda_adapter_s2_s0p5_1` `ro_priroda_adapter_s2_s1p5_1` `ro_priroda_crew_s1p5_2` `aquila_experiment_rack_s1p5_1` `aquila_lab_s1p5_2`
- **Sofora truss (3):** `rana_mount_srf_1` `rana_truss_srf_1` `rana_truss_srf_2`
- **TKS ferry (6):** `aquila_control_s2_1` `ro_TKS_adapter_s2_s0p5_1` `ro_TKS_adapter_s2_s1p5_1` `ro_TKS_crew_s1p5_2` `alnair_les_s0_2` `sargas_decoupler_s1p5_1`
- **Remap → Experimental (2):** `aquila_sensor_synthetic_aperture_radar_srf_1` (Travers SAR) · `aquila_sensor_visible_light_telescope_s0_1` (Priroda cam)

### NearFutureSolar — 6 kept (advanced-solar tier)
- **Concentrating PV:** `nfs-panel-deploying-concentrator-1x4-juno-1` (K12-K, Juno-style)
- **Roll-out blanket (ROSA/Gateway tech):** `nfs-panel-deploying-blanket-starship-1` (OKEB-25R 'Starship', small) · `nfs-panel-deploying-blanket-dsg-1` (OKEB-100 'Gateway', station) · `nfs-panel-deploying-blanket-arm-1` (OKEB-150R 'Halo', large circular)
- **Large rigid array:** `nfs-panel-deploying-advanced-2x20-hub-1` (K55-A 'Megalador')
- **Curved expanding:** `nfs-panel-deploying-curved-375-1` (NIV-75-R)

## Next
- Continue mod-by-mod **hardware** curation: Kerwis (Chinese), NearFuture suite, US2, SSPX, SXT/VenStock, the rest.
