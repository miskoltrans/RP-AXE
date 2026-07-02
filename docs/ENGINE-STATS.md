# RP-AXE — Engine & Booster Stats + Upgrade Paths (RP-1 reference)

Lookup reference for **every curated engine and booster** (part-capabilities `disc = engine:*`): each part's RealFuels config variants, the RP-1 tech node that unlocks each, and its key stats. A RealFuels engine part carries one `ModuleEngineConfigs` with many selectable **`CONFIG`s**; each better CONFIG is gated behind an RP-1 tech node via an `RFUpgrade_<config>` PARTUPGRADE — so the **ordered set of a part's CONFIGs *is* its upgrade path**. See [UPGRADES.md](UPGRADES.md) for how those PARTUPGRADEs are curated.

- **Coverage:** 429 / 441 curated engine/booster parts, 1117 config variants. 413 from the RP-1 reference (with tech placement), 16 RO-only (stats but **no** RP-1 tech node — RP-1 doesn't ship them). 12 airbreathing/hybrid parts have no RealFuels config path (listed at the end).
- **Full detail (greppable):** [`manifest/engine-stats.tsv`](../manifest/engine-stats.tsv) — one row per (part, config), all fields below plus reliability, ullage, pressureFed, ignitions, rated burn time, mass mult.
- **Source:** `ksp_rp1_expanded/GameData/ModuleManager.ConfigCache` (RO engines with RP-1's `Tree/TREE-Engines.cfg` `techRequired`/`cost` placement baked in); tech-node titles + era ordering from `RP-1/Tree/RP0TechTree.cfg` (`pos.x`).
- **Reproduce:** `python RP-AXE/tools/extract_engine_stats.py` (regenerates the TSV and this doc).

**Reading the tables.** *Variants* = number of CONFIGs. *Tech span* = tech node of the earliest CONFIG → the latest (the length of the upgrade path). *Thrust* = vacuum `maxThrust` kN across variants. *IspVac* is in **seconds** for curve-mode engines; small RCS/OMS/cold-gas thrusters use RealFuels' tech-level system where Isp is a *fraction* of a per-type ceiling (marked `†TL-frac` — see the TSV `ispMode` column), and airbreathing jets defined via `ModuleEngineConfigs` have no rocket Isp (thrust only). `‡` marks the RO-only parts.

## Engine count by type

| Type | Engines | Config variants |
|---|---:|---:|
| Solid motors & boosters | 73 | 93 |
| Kerolox (kerosene / LOX) | 76 | 238 |
| Hypergolic (storable) | 140 | 468 |
| Cryogenic (hydrolox / methalox) | 69 | 194 |
| Other (nuclear, electric, exotic, jets) | 71 | 124 |
| **Total** | **429** | **1117** |

## Longest upgrade paths

| Part | Title | Variants | Tech span |
|---|---|---:|---|
| `ROE-RL10Fixed` | RL-10 Series (Non-Extendable Nozzle) | 20 | Prototype Hydrolox Engines → Near Future Hydrolox Engines |
| `RO-2kN-Thruster` | 2.2/3.6kN Thruster | 17 | Starting Parts → Reusable Attitude Control |
| `ROE-generic-full` | 1.1/1.78kN Thruster | 17 | Starting Parts → Reusable Attitude Control |
| `ROE-generic-half` | 550/890N Thruster | 17 | Starting Parts → Reusable Attitude Control |
| `ROE-generic-quarter` | 275/445N Thruster | 17 | Starting Parts → Reusable Attitude Control |
| `ca_jib` | Generic 0.5 kN Thruster | 17 | Starting Parts → Reusable Attitude Control |
| `microEngine` | 1.1/1.78kN Thruster | 17 | Starting Parts → Reusable Attitude Control |
| `ROE-Agena` | XLR81 (Agena) Vacuum Engine | 14 | 1958 Orbital Rocketry → 1998-2003 Orbital Rocketry |
| `ROE-LR87` | LR87 | 12 | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry |
| `ROE-LR87_11` | LR87 Booster (Shielded) | 12 | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry |
| `ROE-LR87_Single` | LR87 | 12 | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry |
| `ROE-LR91` | LR91 | 12 | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry |

## Solid motors & boosters — 73 parts

| Part | Title | Var | Base config | Tech span | Thrust kN (vac) | IspVac | Propellants |
|---|---|---:|---|---|---|---|---|
| `AM_MLP_GeneralROFI` | Multi ROFI Sparker | 1 | `(single config)` | Starting Parts | 0.1 | 80 | SolidFuel |
| `AM_MLP_ShuttleLauncherTSM` | Shuttle Launcher Tail Service Mast | 1 | `(single config)` | Starting Parts | 0.1 | 80 | SolidFuel |
| `ROE-R103` | R-103 Booster | 1 | `R-103` | Starting Parts | 11.192 | 220 | NGNC |
| `ROE-25KS18000` | Aerojet 2.5KS-18000 | 1 | `2_5KS18000` | Early Solid Rocket Engines | 88.068 | 198.8 | NGNC |
| `ROE-18KS7800` | Aerojet 1.8KS-7800 | 1 | `1_8KS7800` | Basic Solid Rocket Engines | 34.0912 | 238.8 | NGNC |
| `ROE-NikeM5E1` | Nike M5E1 | 1 | `Nike-M5E1` | Basic Solid Rocket Engines | 217.96 | 228 | NGNC |
| `ROE-BabySergeant` | Baby Sergeant (5.4KS-1975) | 2 | `T17-E2` | 1956-1957 Solid Rocket Engines → 1958 Solid Rocket Engines | 8 | 220-235 | PSPC |
| `ROE-BabySergeantX11` | Baby Sergeant 11x Cluster | 2 | `T17-E2` | 1956-1957 Solid Rocket Engines → 1958 Solid Rocket Engines | 88 | 220-235 | PSPC |
| `ROE-BabySergeantX3` | Baby Sergeant 3x Cluster | 2 | `T17-E2` | 1956-1957 Solid Rocket Engines → 1958 Solid Rocket Engines | 24 | 220-235 | PSPC |
| `ROE-Castor1` | Castor 1 | 3 | `XM-20` | 1956-1957 Solid Rocket Engines → 1959-1960 Solid Rocket Engines | 304.3-349.3 | 214.5-273.21 | PSPC |
| `ROE-GCRC` | GCRC 33KS-2800 | 1 | `GCRC` | 1956-1957 Solid Rocket Engines | 17.3 | 237.46 | PSPC |
| `PioneerVernier` | Pioneer Adjustment Motor | 1 | `Pioneer-JPL-532A` | 1958 Solid Rocket Engines | 0.06 | 235 | PSPC |
| `ROE-Altair` | Altair X-248 | 1 | `Altair` | 1959-1960 Solid Rocket Engines | 16.35 | 255.04 | PSPC |
| `tiros-1` | Tiros-1 Satellite | 1 | `(single config)` | Basic Avionics and Probes | 1.2 | 360 | SolidFuel |
| `ROC-MercuryLESBDB` | Mercury Launch Escape System | 1 | `(single config)` | Basic Capsules | 231.3 | 225 | PSPC |
| `RO_mk1_LES` | Launch Escape System (Mercury) | 1 | `LES` | Basic Capsules | 231.3 | 190 | SolidFuel |
| `ROE-Alcyone1` | Alcyone 1 BE-3 | 1 | `Alcyone-1` | 1962-1963 Solid Rocket Engines | 26.69 | 270.4 | NGNC |
| `ROE-Star13D` | STAR 13D | 1 | `Star-13D` | 1962-1963 Solid Rocket Engines | 3.06 | 223 | PSPC |
| `ROC-GeminiRetroMECBDB` | Gemini Retro Rocket (Star-13E) | 1 | `Star-13E` | 1964-1965 Solid Rocket Engines | 2.78 | 256.3 | PSPC |
| `ROC-VoskhodCapsule` | Voskhod Descent Module | 1 | `(single config)` | Second Generation Capsules | 16.7 | 250 | SolidFuel |
| `ROE-TX280` | S-IV TX-280 Ullage Motor | 1 | `TX-280` | 1964-1965 Solid Rocket Engines | 15.2 | 222 | PSPC |
| `ROE-Star37E` | STAR 37E | 1 | `STAR-37E` | 1966 Solid Rocket Engines | 68.8 | 284 | HTPB |
| `ROC-D2Block1LES` | D-2 Block I Abort Motor | 1 | `(single config)` | Lunar Orbiter Capsules | 230 | 225 | PSPC |
| `LaunchEscapeSystem` | Launch Escape System (Apollo) | 1 | `LES` | Mature Capsules | 689.5 | 190 | SolidFuel |
| `ROC-ApolloLESBDB` | Apollo Launch Escape System (LES) | 1 | `LES_Escape` | Mature Capsules | 693.7 | 172 | HTPB |
| `ROC-GeminiBEquipmentSection` | Gemini B Adapter Module | 1 | `(single config)` | Mature Capsules | 1 | 255 | PSPC |
| `SXTWaxWing` | Waxwing | 1 | `Waxwing` | 1967-1968 Solid Rocket Engines | 34.35 | 278 | CTPB |
| `ROC-BigGeminiLES` | Big G Launch Escape System | 1 | `(single config)` | Improved Capsules | 693.7 | 172 | HTPB |
| `ROE-Antares3` | Antares III (STAR 31) | 1 | `Star-31` | 1976-1980 Solid Rocket Engines | 100.374 | 294.36 | HTPB |
| `RO-RSRM` | RSRM | 3 | `RSRM-1981` | 1981-1985 Solid Rocket Engines → 1992-1997 Solid Rocket Engines | 14819 | 268 | PBAN |
| `ROE-Star37FM` | STAR 37FM | 2 | `STAR-37FM` | 1981-1985 Solid Rocket Engines → 2009-2018 Solid Rocket Engines | 54.8-55.6 | 289.8-293.7 | HTPB |
| `ROE-Star48B` | STAR 48B | 3 | `Star-48B/Long` | 1981-1985 Solid Rocket Engines | 76.1-78 | 286-292.1 | HTPB |
| `restock-srb-anvil-1` | RSRM | 3 | `RSRM-1981` | 1981-1985 Solid Rocket Engines → 1992-1997 Solid Rocket Engines | 14819 | 268 | PBAN |
| `ROE-Castor120` | Castor 120 | 3 | `Castor-120` | 1986-1991 Solid Rocket Engines | 1875-2125 | 280 | HTPB |
| `ROE-Castor4A` | Castor 4A | 1 | `Castor-4A` | 1986-1991 Solid Rocket Engines | 538 | 265 | HTPB |
| `ROE-GEM40` | GEM 40 | 2 | `GEM-40/Ground` | 1986-1991 Solid Rocket Engines | 644-666 | 274-283.4 | HTPB |
| `ROE-SRMU` | SRMU | 1 | `SRMU` | 1986-1991 Solid Rocket Engines | 8233.78 | 281 | HTPB |
| `ROE-Star5D` | STAR 5D | 1 | `Star-5D` | 1992-1997 Solid Rocket Engines | 6.272 | 256 | HTPB |
| `ROE-AJ60` | AJ-60A | 2 | `AJ-60A` | 1998-2008 Solid Rocket Engines | 1688.4 | 275 | HTPB |
| `ROE-Castor4AXL` | Castor 4AXL | 1 | `Castor-4AXL` | 1998-2008 Solid Rocket Engines | 765 | 282.4 | HTPB |
| `ROE-GEM46` | GEM 46 | 3 | `GEM-46/TVC-Ground` | 1998-2008 Solid Rocket Engines | 875-915 | 277.8-290.7 | HTPB |
| `ROE-GEM60` | GEM 60 | 2 | `GEM-60/TVC` | 1998-2008 Solid Rocket Engines | 1235.95-1248.91 | 274 | HTPB |
| `ROE-Star8` | STAR 8 (RAD) | 1 | `Star-8` | 1998-2008 Solid Rocket Engines | 7.749 | 273 | HTPB |
| `ROE-Castor30` | Castor 30A | 1 | `Castor-30A` | 2009-2018 Solid Rocket Engines | 330.765 | 293.1 | HTPB |
| `ROE-Castor30XL` | Castor 30XL | 1 | `Castor-30XL` | 2009-2018 Solid Rocket Engines | 533.342 | 294.4 | HTPB |
| `ROE-GEM63` | GEM 63 | 1 | `GEM-63` | 2009-2018 Solid Rocket Engines | 1658 | 275 | HTPB |
| `MassiveBooster` | RSRMV | 1 | `RSRMV` | 2019-2028 Solid Rocket Engines | 15800 | 266 | PBAN |
| `ROC-OrionCover1` | Orion SM Fairing - 1 | 1 | `LES` | Commercial Capsules | 6 | 150 | SolidFuel |
| `ROC-OrionCover2` | Orion SM Fairing - 2 | 1 | `LES` | Commercial Capsules | 6 | 150 | SolidFuel |
| `ROC-OrionCover3` | Orion ESM Fairing - 3 | 1 | `LES` | Commercial Capsules | 6 | 150 | SolidFuel |
| `ROC-MercuryPosigradeBDB` | Mercury Posigrade Kick Motor | 1 | `MercuryPosigrade` | — | 1.779 | 206 | PSPC |
| `ROC-MercuryRetroBDB` | Mercury Retro (TE-M-316) | 1 | `TE-M-316` | — | 5.1 | 206 | PSPC |
| `ROC-VoskhodAirlock` | Voskhod Airlock | 1 | `AirlockRetro` | — | 0.5 | 120 | PSPC |
| `ROC-VoskhodRetroBooster` | Voskhod Retro Package | 1 | `VOSKRetro` | — | 117.7 | 224 | HTPB |
| `ROE-1204sepMotor` | UA1204 Nosecone & Separation Motor | 1 | `SolidFuel` | — | 160 | 154 | PSPC |
| `ROE-1205sepMotor` | UA1205 Nosecone & Separation Motor | 1 | `SolidFuel` | — | 160 | 154 | PSPC |
| `ROE-1206sepMotor` | UA1206 Nosecone & Separation Motor | 1 | `SolidFuel` | — | 160 | 154 | PSPC |
| `ROE-1207sepMotor` | UA1207 Nosecone & Separation Motor | 1 | `SolidFuel` | — | 160 | 154 | PSPC |
| `ROE-1208sepMotor` | UA1208 Nosecone & Separation Motor | 1 | `SolidFuel` | — | 160 | 154 | PSPC |
| `ROE-Agena_Retro_TypeIII` | Agena Retrorocket Type III | 1 | `RetroTypeIII` | — | 0.609 | 217.8 | PSPC |
| `ROE-Agena_Spinrocket` | Agena 1KS30HA Spin Rocket | 1 | `1KS30HA` | — | 0.169 | 114 | PSPC |
| `ROSmallSpinMotor` | Spin Motor (Small) | 1 | `SpinSmall` | — | 6 | 225 | PSPC |
| `SnubOtron` | Separation Motor (Small) | 1 | `SolidFuel` | — | 18 | 225 | PSPC |
| `TinyTim` | Tiny Tim Booster | 2 | `30Klbf` | — | 146.6-244.4 | 222 | NGNC |
| `alnair_les_s0_2` ‡ | TKS VA Capsule LES | 1 | `VALES` | — | 2700 | 295.5 | HTPB |
| `aquarius_parachute_s0p5_1` ‡ | LK-700 Capsule Parachute | 1 | `(single config)` | advLanding | 56 | 250 | SolidFuel |
| `ius_bottom` | IUS Booster First Stage | 1 | `Orbus-21` | — | 267.77 | 295.5 | HTPB |
| `pioneer1_booster` | Pioneer 0/1/2 Top Boosters | 1 | `SolidFuel` | — | 1.12 | 235 | PSPC |
| `pioneer_0_1_2` | Pioneer 0/1/2 | 1 | `SolidFuel` | — | 13.3 | 235 | PSPC |
| `rn_surveyor_retro` | Surveyor Star 37 Solid Retro Booster | 1 | `Star-37` | — | 43.5 | 260 | HTPB |
| `sepMotor1` | Radial Separation Motor (Medium) | 1 | `SolidFuel` | — | 98 | 225 | PSPC |
| `sepMotorLarge` | Radial Separation Motor (Large) | 1 | `SolidFuel` | — | 392 | 225 | PSPC |
| `sepMotorSmall` | Radial Separation Motor (Small) | 1 | `SolidFuel` | — | 17.64 | 225 | PSPC |

## Kerolox (kerosene / LOX) — 76 parts

| Part | Title | Var | Base config | Tech span | Thrust kN (vac) | IspVac | Propellants |
|---|---|---:|---|---|---|---|---|
| `RO-DerwentV` | Derwent Turbojet | 2 | `DerwentV` | Starting Parts | 15.56-15.7 | — (airbreathing) | Kerosene |
| `RO-J35` | J35 Turbojet | 2 | `J35-A-11` | Supersonic Plane Development → Supersonic Flight | 16.68-21.8 | — (airbreathing) | Kerosene |
| `RO-VK1` | VK-1 Turbojet | 1 | `VK-1` | Supersonic Plane Development | 26.47 | — (airbreathing) | Kerosene |
| `RO-J47` | J47 Turbojet | 3 | `J47-GE-15` | Supersonic Flight → Mature Supersonic Flight | 23.13-26.47 | — (airbreathing) | Kerosene |
| `RO-J48` | J48/Tay Turbojet | 2 | `J48-P-5` | Supersonic Flight → Mature Supersonic Flight | 36.9-37.8 | — (airbreathing) | Kerosene |
| `RO-JT3C` | J57 Turbojet (No Afterburner) | 4 | `J57-P-1W` | Supersonic Flight → Mature Supersonic Flight | 40.03-49.82 | — (airbreathing) | Kerosene |
| `RO-RD9B` | RD-9 Turbojet | 7 | `RD-9B` | Supersonic Flight → Mature Turbofans | 31.87-39.7 | — (airbreathing) | Kerosene |
| `RO-Sapphire203` | Sapphire Turbojet | 2 | `Sapphire101` | Supersonic Flight → Mature Supersonic Flight | 36.9-48.9 | — (airbreathing) | Kerosene |
| `aje_avon` | Avon Turbojet | 4 | `Avon107` | Supersonic Flight → Advanced Jet Engines | 33.4-72.77 | — (airbreathing) | Kerosene |
| `aje_j57` | J57 Turbojet | 4 | `J57-P-8` | Supersonic Flight → Advanced Jet Engines | 64.5-87.2 | — (airbreathing) | Kerosene |
| `RO-AL7F` | AL-7 Turbojet | 3 | `AL-7F` | Mature Supersonic Flight → High Speed Flight | 88.8-99 | — (airbreathing) | Kerosene |
| `RO-Atar101D` | Atar 101 Turbojet | 2 | `Atar101D` | Mature Supersonic Flight → High Speed Flight | 29.42-34.3 | — (airbreathing) | Kerosene |
| `RO-RJ43` | RJ43 Ramjet | 4 | `RJ43-MA-3` | Mature Supersonic Flight → Advanced Jet Engines | 51-54 | — (airbreathing) | Kerosene |
| `RO-RJ47` | RJ47 Ramjet | 1 | `XRJ47-W-5` | Mature Supersonic Flight | 67 | — (airbreathing) | Kerosene |
| `RO-RJ55` | RJ55/J67 Combined Cycle Ramjet | 1 | `J67-W-3` | Mature Supersonic Flight | 99.42 | — (airbreathing) | Kerosene |
| `ROE-LR89_2` | LR43/LR89 | 8 | `XLR43-NA-3` | Basic Rocketry → 1986-1991 Orbital Rocketry | 617.4-1032.5 | 265-293.4 | Ethanol90+LqdOxygen · RP-1+LqdOxygen |
| `aje_j75` | J75 Turbojet | 3 | `J75-P-17` | Mature Supersonic Flight → High Speed Flight | 109-131.2 | — (airbreathing) | Kerosene |
| `aje_j79` | J79 Turbojet | 11 | `J79-GE-3A` | Mature Supersonic Flight → Mature Turbofans | 51.82-83.4 | — (airbreathing) | Kerosene |
| `ROE-LR101Inline_2` | LR101 | 3 | `LR101-NA-3` | 1956-1957 Orbital Rocketry → 1986-1991 Orbital Rocketry | 2.976-5.304 | 238-247 | RP-1+LqdOxygen |
| `ROE-LR101_2` | LR101 | 3 | `LR101-NA-3` | 1956-1957 Orbital Rocketry → 1986-1991 Orbital Rocketry | 2.976-5.304 | 238-247 | RP-1+LqdOxygen |
| `ROE-LR105_2` | LR105 | 7 | `LR43-NA-5` | 1956-1957 Orbital Rocketry → 1986-1991 Orbital Rocketry | 240.2-386.4 | 301-316 | RP-1+LqdOxygen |
| `RO-J85GE5` | J85 Turbojet | 2 | `J85-GE-5` | High Speed Flight → Efficient Supersonic Engines | 17.1-22.2 | — (airbreathing) | Kerosene |
| `RO-Nord1500` | Nord 1500/Atar Combined Cycle Ramjet | 1 | `Atar101E-3` | High Speed Flight | 34.3 | — (airbreathing) | Kerosene |
| `RO-R11F` | R-11 Turbojet | 7 | `R-11F-300` | High Speed Flight → Mature Turbofans | 56.39-60.82 | — (airbreathing) | Kerosene |
| `RO-RD012` | RD-012 Ramjet | 1 | `RD-012U` | High Speed Flight | 76 | — (airbreathing) | Kerosene |
| `RO-RJ59` | RJ59 Ramjet | 1 | `XRJ59-MA-3` | High Speed Flight | 100 | — (airbreathing) | Kerosene |
| `ROE-RD0105` | RD-0105/0109 | 2 | `RD-0105` | 1958 Orbital Rocketry → 1960 Orbital Rocketry | 49.4-54.5 | 316-323.5 | Kerosene+LqdOxygen |
| `ROE-RZ` | RZ.1/RZ.2 | 3 | `RZ.1` | 1958 Orbital Rocketry → 1960 Orbital Rocketry | 696.6-791.2 | 282-288 | RP-1+LqdOxygen |
| `SXTPWPT6` | PT6A Turboprop | 11 | `PT6A-6A` | High Speed Flight → Refined Turbofans | 8.4-13 | — (airbreathing) | Kerosene |
| `aje_atar` | Atar 09 Turbojet | 2 | `Atar09B` | High Speed Flight → Advanced Jet Engines | 58.84-70.6 | — (airbreathing) | Kerosene |
| `miniJetEngine` | J85 Turbojet (No Afterburner) | 1 | `J85-GE-4` | High Speed Flight | 13.1 | — (airbreathing) | Kerosene |
| `ROE-RD0110` | RD-0107/0110 | 4 | `RD-0107` | 1960 Orbital Rocketry → 1965 Orbital Rocketry | 297.9-318.78 | 326-330.4 | Kerosene+LqdOxygen |
| `ROE-H1C` | H-1C Series | 7 | `H-1-165K` | 1961 Orbital Rocketry → 1976-1980 Orbital Rocketry | 846.76-1480.6 | 295-297 | RP-1+LqdOxygen |
| `ROE-H1D` | H-1D Series | 9 | `H-1-165K` | 1961 Orbital Rocketry → 1986-1991 Orbital Rocketry | 846.76-1480.6 | 295-302 | RP-1+LqdOxygen |
| `ROE-RD111` | RD-111 | 2 | `RD-111-8D716` | 1961 Orbital Rocketry → 1963 Orbital Rocketry | 1628 | 309.5-318 | Kerosene+LqdOxygen · Kerosene+CooledLqdOxygen |
| `ROE-RD58` | S1.5400/RD-58 Series | 8 | `S1_5400` | First ORSC Engines → 2004-2008 ORSC Engines | 63.7-86.3 | 338.6-362 | Kerosene+LqdOxygen · RG-1+LqdOxygen · Syntin+LqdOxygen |
| `ROE-RS27` | H-1/RS-27 | 9 | `H-1-165K` | 1961 Orbital Rocketry → 1986-1991 Orbital Rocketry | 846.76-1480.6 | 295-302 | RP-1+LqdOxygen |
| `ROE-E1` | E-1 | 7 | `E-1` | 1963 Orbital Rocketry → 1976-1980 Orbital Rocketry | 1947.53-2828.57 | 290-310 | RP-1+LqdOxygen |
| `RO-Olympus593` | Olympus 593 Turbojet | 1 | `Olympus593-610` | Advanced Jet Engines | 169.2 | — (airbreathing) | Kerosene |
| `RO-R13` | R-13 Turbojet | 7 | `R-13-300` | Advanced Jet Engines → Refined Turbofans | 62.77-68.95 | — (airbreathing) | Kerosene |
| `RO-R15BD` | R-15 Turbojet | 3 | `R-15B-300` | Advanced Jet Engines → Efficient Supersonic Engines | 109.8-142.2 | — (airbreathing) | Kerosene |
| `nfa-turbofan-25-2` | Olympus 593 Turbojet | 1 | `Olympus593-610` | Advanced Jet Engines | 169.2 | — (airbreathing) | Kerosene |
| `nfa-vtol-0625-1` | RB.162 Turbojet | 3 | `RB162-4D` | Advanced Jet Engines → Efficient Supersonic Engines | 19.57-26.73 | — (airbreathing) | Kerosene |
| `nfa-vtol-125-1` | 2x RB.162 Turbojet | 3 | `RB162-4D` | Advanced Jet Engines → Efficient Supersonic Engines | 39.14-53.46 | — (airbreathing) | Kerosene |
| `turboFanEngine` | J58 Turbojet | 3 | `J58-P-4` | Advanced Jet Engines → Refined Turbofans | 151.2-158.8 | — (airbreathing) | Kerosene |
| `RO-A136` | A-136 Nuclear Turbo-Ramjet | 1 | `A-136` | Prototype Nuclear Propulsion | 104.8 | — (airbreathing) | EnrichedUranium+PlaceholderAir |
| `ROE-F1` | F-1 | 3 | `F-1-1.5M` | 1967 Orbital Rocketry → 1976-1980 Orbital Rocketry | 7775.49-9189.6 | 301-306.2 | RP-1+LqdOxygen |
| `JetEngine` | TF/CF34 High-Bypass Turbofan | 4 | `CF34-1A` | Efficient Supersonic Engines → Refined Turbofans | 40.32-41.25 | — (airbreathing) | Kerosene |
| `RO-D30F6` | D-30 Low-Bypass Turbofan | 1 | `D-30F6` | Efficient Supersonic Engines | 152 | — (airbreathing) | Kerosene |
| `RO-R25F` | R-25 Turbojet | 1 | `R-25-300` | Efficient Supersonic Engines | 97.1 | — (airbreathing) | Kerosene |
| `aje_f404` | F404 Low-Bypass Turbofan | 3 | `F404-GE-400` | Efficient Supersonic Engines → Refined Turbofans | 71.17-80.51 | — (airbreathing) | Kerosene |
| `nfa-turbojet-25-1` | GE4 Turbojet | 2 | `GE4-J5P` | Efficient Supersonic Engines → Mature Turbofans | 281-297 | — (airbreathing) | Kerosene |
| `turboFanSize2` | CF6 High-Bypass Turbofan | 4 | `CF6-6` | Efficient Supersonic Engines → Mature Turbofans | 184.6-233.5 | — (airbreathing) | Kerosene |
| `turboJet` | F100 Low-Bypass Turbofan | 5 | `F100-PW-100` | Efficient Supersonic Engines → Advanced Turbofans | 106-144.6 | — (airbreathing) | Kerosene |
| `SXTKe90TurboJet` | D-18 High-Bypass Turbofan | 1 | `D-18T` | Mature Turbofans | 229.8 | — (airbreathing) | Kerosene |
| `aje_al31` | AL-31 Low-Bypass Turbofan | 3 | `AL-31F` | Mature Turbofans → Scramjet Engines | 122.4-142.2 | — (airbreathing) | Kerosene |
| `RO-SXT-R79` | R-79 Turbofan | 3 | `R-79-300` | Refined Turbofans | 147.1-176.15 | — (airbreathing) | Kerosene |
| `RO-nfa-RD41` | 2x RD-41 Turbojet | 1 | `RD-41` | Refined Turbofans | 80.42 | — (airbreathing) | Kerosene |
| `RO-WS10` | WS-10 Low-Bypass Turbofan | 3 | `WS-10A` | Scramjet Engines → Advanced Turbofans | 132-144 | — (airbreathing) | Kerosene |
| `ROE-RD180` | RD-180 | 1 | `RD-180` | 1998-2003 ORSC Engines | 4152 | 338.4 | RP-1+LqdOxygen |
| `SXTVTOLturboFan` | F135 Low-Bypass Turbofan | 1 | `F135-PW-600` | Scramjet Engines | 182 | — (airbreathing) | Kerosene |
| `YF100_Engine-double-withShell2` | YF-100 with CZ-5 Boattail | 2 | `YF-100` | 1998-2003 ORSC Engines → 2014-2018 ORSC Engines | 2681-2794 | 335-337 | RP-1+LqdOxygen |
| `YF100_Engine_S` | YF-100 | 2 | `YF-100` | 1998-2003 ORSC Engines → 2014-2018 ORSC Engines | 1340.5-1397 | 335-337 | RP-1+LqdOxygen |
| `ROE-Merlin1A` | Merlin 1A | 1 | `Merlin1A` | 2004-2008 Orbital Rocketry | 369.2 | 288.5 | RP-1+LqdOxygen |
| `ROE-Merlin1C` | Merlin 1C | 1 | `Merlin1C` | 2004-2008 Orbital Rocketry | 482.63 | 304.8 | RP-1+LqdOxygen |
| `ROE-Merlin1CV` | Merlin 1C Vacuum | 1 | `Merlin1CVac` | 2009-2013 Orbital Rocketry | 524.9 | 336 | Kerosene+LqdOxygen |
| `ROE-Merlin1D` | Merlin 1D | 3 | `Merlin1D` | 2009-2013 Orbital Rocketry → 2014-2018 Orbital Rocketry | 742.4-914.12 | 311 | RP-1+LqdOxygen · CooledRP-1+CooledLqdOxygen |
| `ROE-Merlin1DV` | Merlin 1D Vacuum | 2 | `Merlin1DVac` | 2009-2013 Orbital Rocketry → 2014-2018 Orbital Rocketry | 805-934.12 | 345-348 | RP-1+LqdOxygen · CooledRP-1+CooledLqdOxygen |
| `ROE-RD191` | RD-191 | 4 | `RD-191` | 2009-2013 ORSC Engines → 2014-2018 ORSC Engines | 1918-2085 | 337.5-339.2 | RP-1+LqdOxygen · RG-1+LqdOxygen |
| `nflv-engine-rs84-1` | RS-84 | 1 | `RS-84` | 2009-2013 ORSC Engines | 5026.49 | 324 | RP-1+LqdOxygen |
| `ROE-Rutherford` | Rutherford | 1 | `Rutherford-SL` | 2014-2018 Orbital Rocketry | 24.91 | 317 | RP-1+LqdOxygen+ElectricCharge |
| `ROE-RutherfordVac` | Rutherford Vacuum | 1 | `RutherfordVac` | 2014-2018 Orbital Rocketry | 25.79 | 343 | RP-1+LqdOxygen+ElectricCharge |
| `nflv-engine-ar1-1` | AR-1 | 1 | `AR-1` | 2014-2018 ORSC Engines | 2487 | 337 | RP-1+LqdOxygen |
| `nflv-engine-ar1c-1` | AR-1 | 1 | `AR-1` | 2014-2018 ORSC Engines | 14922 | 337 | RP-1+LqdOxygen |
| `ROE-F1B` | F-1B | 1 | `F-1B` | 2019-2028 Orbital Rocketry | 8815 | 299 | RP-1+LqdOxygen |
| `SXTNK12M` | NK-12 Turboprop | 4 | `NK-12` | — | 80.2-108.7 | — (airbreathing) | Kerosene |

## Hypergolic (storable) — 140 parts

| Part | Title | Var | Base config | Tech span | Thrust kN (vac) | IspVac | Propellants |
|---|---|---:|---|---|---|---|---|
| `RO-2kN-Thruster` | 2.2/3.6kN Thruster | 17 | `Nitrogen` | Starting Parts → Reusable Attitude Control | 0.576-3.64 | 0.195-1.329 †TL-frac | Nitrogen · HTP · NitrousOxide · Aerozine50+NTO … |
| `ROE-A4` | Model 39 | 5 | `Model39b` | Starting Parts → Early Rocketry | 245-400 | 227-255 | Ethanol75+LqdOxygen · Hydyne+LqdOxygen · Visol+Salbei |
| `ROE-Aerobee` | Aerobee | 4 | `WAC-Corporal` | Starting Parts → Early Rocketry | 7.733-21.28 | 226-235.44 | ANFA22+IRFNA-III · ANFA37+IRFNA-III |
| `ROE-VeroniqueAK` | Véronique | 3 | `Veronique` | Starting Parts → 1956-1957 Orbital Rocketry | 49.3-73.8 | 249-261 | Kerosene+IRFNA-III · Turpentine+IWFNA |
| `ROE-generic-full` | 1.1/1.78kN Thruster | 17 | `Nitrogen` | Starting Parts → Reusable Attitude Control | 0.288-1.82 | 0.195-1.329 †TL-frac | Nitrogen · HTP · NitrousOxide · Aerozine50+NTO … |
| `ROE-generic-half` | 550/890N Thruster | 17 | `Nitrogen` | Starting Parts → Reusable Attitude Control | 0.144-0.91 | 0.195-1.329 †TL-frac | Nitrogen · HTP · NitrousOxide · Aerozine50+NTO … |
| `ROE-generic-quarter` | 275/445N Thruster | 17 | `Nitrogen` | Starting Parts → Reusable Attitude Control | 0.072-0.455 | 0.195-1.329 †TL-frac | Nitrogen · HTP · NitrousOxide · Aerozine50+NTO … |
| `ROMeteoSustainer` | U-1250 | 3 | `U-1250` | Starting Parts → Early Rocketry | 14.417-23 | 232.1-241.3 | Kerosene+AK20 |
| `ca_jib` | Generic 0.5 kN Thruster | 17 | `Nitrogen` | Starting Parts → Reusable Attitude Control | 0.144-0.91 | 0.195-1.329 †TL-frac | Nitrogen · HTP · NitrousOxide · Aerozine50+NTO … |
| `microEngine` | 1.1/1.78kN Thruster | 17 | `Nitrogen` | Starting Parts → Reusable Attitude Control | 0.288-1.82 | 0.195-1.329 †TL-frac | Nitrogen · HTP · NitrousOxide · Aerozine50+NTO … |
| `ROE-ORM65` | ORM-65 | 3 | `ORM-65` | Post-War Rocketry Testing → Early Rocketry | 1.588-3.176 | 233 | Kerosene+AK20 |
| `ROE-RD100` | RD-100 | 6 | `RD-100` | Post-War Rocketry Testing → 1956-1957 Orbital Rocketry | 307-500.14 | 235-248 | Ethanol75+LqdOxygen · Ethanol90+LqdOxygen |
| `ROE-XLR10` | XLR10 | 1 | `XLR10-RM-2` | Post-War Rocketry Testing | 110.5 | 214.5 | Ethanol90+LqdOxygen |
| `ROE-XLR11` | XLR11 | 5 | `XLR11-RM-3` | Post-War Rocketry Testing → 1964 Orbital Rocketry | 26.68-47.08 | 226.6-234.4 | Ethanol75+LqdOxygen |
| `ROE-A7` | NAA-75-110 A-Series | 4 | `XLR43-NA-1` | Early Rocketry → 1956-1957 Orbital Rocketry | 383-409.36 | 248-265 | Ethanol75+LqdOxygen · Hydyne+LqdOxygen |
| `ROE-RD200` | RD-200 | 1 | `RD-200` | Early Rocketry | 98.51 | 234 | Kerosene+AK20 |
| `ROE-S2253` | S2.253/S3.42/S5.2 | 4 | `S2.253` | Basic Rocketry → 1965 Orbital Rocketry | 94.8-165.5 | 255-265 | Kerosene+AK20 · Kerosene+AK27 · UDMH+AK27 |
| `ROE-Stentor` | Stentor Booster | 1 | `Stentor` | Basic Rocketry | 121 | 220 | RP-1+HTP |
| `ROE-XLR25` | XLR25 | 1 | `XLR25-CW-1` | Basic Rocketry | 73.75 | 230 | Ethanol75+LqdOxygen |
| `ROE-Castor1_Inline` | Castor 1 | 3 | `XM-20` | 1956-1957 Solid Rocket Engines → 1959-1960 Solid Rocket Engines | 304.3-349.3 | 214.5-273.21 | PSPC |
| `ROE-AJ10Early` | AJ10 Series (Early) | 6 | `AJ10-37` | 1956-1957 Orbital Rocketry → 1962 Orbital Rocketry | 33-34.25 | 265-272.5 | UDMH+IWFNA · UDMH+IRFNA-III |
| `ROE-Gamma301` | Gamma-201/301 | 3 | `Gamma-201` | 1956-1957 Orbital Rocketry → 1961 Orbital Rocketry | 84.3-133.447 | 226.9-269 | RP-1+HTP |
| `ROE-LR79` | LR79 | 6 | `S-3` | 1956-1957 Orbital Rocketry → 1963 Orbital Rocketry | 696.6-873 | 284-305.5 | RP-1+LqdOxygen · UDMH+LqdOxygen |
| `ROE-RD107` | RD-107/117 | 10 | `RD-107-8D74` | 1956-1957 Orbital Rocketry → 1998-2003 Orbital Rocketry | 972.3-1033.3 | 306-319.99 | Kerosene+LqdOxygen · CooledKerosene+CooledLqdOxygen · CooledSyntin+CooledLqdOxygen |
| `ROE-RD108` | RD-108/118 | 10 | `RD-108-8D75` | 1956-1957 Orbital Rocketry → 1998-2003 Orbital Rocketry | 803.2-1011 | 308-320.39 | Kerosene+LqdOxygen · CooledKerosene+CooledLqdOxygen · CooledSyntin+CooledLqdOxygen |
| `ROE-RD211` | RD-211 | 5 | `RD-211-8D57` | 1956-1957 Orbital Rocketry → 1960 Orbital Rocketry | 622.7-749.2 | 253-264 | Kerosene+AK20 · Kerosene+AK27 |
| `ROE-S155` | S-155 | 1 | `S-155` | 1956-1957 Orbital Rocketry | 39 | 255 | Tonka250+AK20 |
| `ROE-X405` | X-405 (XLR50-GE-2) | 1 | `X-405` | 1956-1957 Orbital Rocketry | 135.28 | 278 | Kerosene+LqdOxygen |
| `YF2_Engine` | YF-2 (no gimbal) | 3 | `YF-1` | 1956-1957 Orbital Rocketry → 1959 Orbital Rocketry | 1046.52-1214.4 | 259.8-267.2 | UDMH+AK27 · UDMH+NTO |
| `YF2_with_shell` | YF-2 with Boattail | 3 | `YF-1` | 1956-1957 Orbital Rocketry → 1959 Orbital Rocketry | 1046.52-1214.4 | 259.8-267.2 | UDMH+AK27 · UDMH+NTO |
| `ROE-Gamma2` | Gamma 2 | 2 | `Gamma-2` | 1958 Orbital Rocketry → 1961 Orbital Rocketry | 68.236-75.1 | 267-279.4 | RP-1+HTP |
| `ROE-Gamma8` | Gamma 8 | 2 | `Gamma-8` | 1958 Orbital Rocketry → 1961 Orbital Rocketry | 256.395-266.893 | 251-269 | RP-1+HTP |
| `ROE-Viking2` | Viking 2 | 1 | `Viking-2` | 1958 Orbital Rocketry | 698 | 282.4 | UDMH+NTO |
| `YF3_Engine` | YF-3 (no gimbal) | 2 | `YF-3` | 1958 Orbital Rocketry → 1959 Orbital Rocketry | 294.2-320.2 | 280-286.9 | UDMH+AK27 · UDMH+NTO |
| `YF3_with_shell` | YF-3 with Boattail | 2 | `YF-3` | 1958 Orbital Rocketry → 1959 Orbital Rocketry | 294.2-320.2 | 280-286.9 | UDMH+AK27 · UDMH+NTO |
| `ROE-Antares1_Inline` | Antares I X-254 | 1 | `Antares-I` | 1959-1960 Solid Rocket Engines | 62.2751 | 256 | PBAA |
| `ROE-LR87` | LR87 | 12 | `LR87-AJ-1` | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry | 1531.9-2421.6 | 285.2-308.4 | RP-1+LqdOxygen · Aerozine50+NTO · CooledAerozine50+CooledNTO · CooledRP-1+CooledLqdOxygen |
| `ROE-LR87_11` | LR87 Booster (Shielded) | 12 | `LR87-AJ-1` | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry | 1531.9-2421.6 | 285.2-308.4 | RP-1+LqdOxygen · Aerozine50+NTO · CooledAerozine50+CooledNTO · CooledRP-1+CooledLqdOxygen |
| `ROE-LR87_Single` | LR87 | 12 | `LR87-AJ-1` | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry | 765.95-1210.8 | 285.2-308.4 | RP-1+LqdOxygen · Aerozine50+NTO · CooledAerozine50+CooledNTO · CooledRP-1+CooledLqdOxygen |
| `ROE-LR91` | LR91 | 12 | `LR91-AJ-1` | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry | 358.54-472.5 | 309.2-319.9 | RP-1+LqdOxygen · Aerozine50+NTO |
| `ROE-LR91-4V` | LR91 (4 Vernier) | 12 | `LR91-AJ-1` | 1959 Orbital Rocketry → 1986-1991 Orbital Rocketry | 358.54-472.5 | 309.2-319.9 | RP-1+LqdOxygen · Aerozine50+NTO |
| `ROE-Viking4` | Viking (4/4B) | 3 | `Viking-4` | 1959 Orbital Rocketry → 1967 Orbital Rocketry | 721.4-808 | 289.9-292.7 | UDMH+NTO · UH25+NTO |
| `ROE-Viking5` | Viking (5/6) | 4 | `Viking-5` | 1959 Orbital Rocketry → 1967 Orbital Rocketry | 692.8-760 | 278.3-280.6 | UDMH+NTO · UH25+NTO |
| `ROE-XLR99` | XLR99 | 3 | `XLR99-RM-1` | 1959 Orbital Rocketry → 1966 Orbital Rocketry | 257.3-369.2 | 276-298 | LqdAmmonia+LqdOxygen |
| `ROC-VostokService` | Vostok/Voskhod/Zenit Service Module | 1 | `S5.4` | 1960 Orbital Rocketry | 15.83 | 266 | Tonka250+AK20 |
| `ROE-AJ10Mid` | AJ10 Series (Mid) | 2 | `AJ10-104` | 1960 Orbital Rocketry → 1965 Orbital Rocketry | 35.1-35.2 | 278 | UDMH+IRFNA-III |
| `ROE-Juno45K` | Juno IVB JPL 45K Engine | 2 | `Juno45k-BI` | 1960 Orbital Rocketry → 1962 Orbital Rocketry | 200.17-253.369 | 304-305 | Hydrazine+NTO · Hydrazine+ClF3 |
| `ROE-Juno6K` | Juno IV 6k Engine | 2 | `Juno6k-BI` | 1960 Orbital Rocketry → 1962 Orbital Rocketry | 26.6893-34.176 | 300-302 | Hydrazine+NTO · Hydrazine+ClF3 |
| `ROE-RD109` | RD-109/119 | 2 | `RD-109-8D711` | 1960 Orbital Rocketry → 1961 Orbital Rocketry | 100.5-101.6 | 334-362 | UDMH+LqdOxygen |
| `ROE-RD215` | RD-216 (2x RD-215) | 6 | `RD-215-8D513` | 1960 Orbital Rocketry → 1970-1971 Orbital Rocketry | 1739.8-1775 | 289-301.4 | UDMH+AK27 · UDMH+NTO |
| `ROE-RD215_Single` | RD-215 | 6 | `RD-215-8D513` | 1960 Orbital Rocketry → 1970-1971 Orbital Rocketry | 869.9-887.5 | 289-301.4 | UDMH+AK27 · UDMH+NTO |
| `ROE-X405H` | X-405H | 4 | `X-405H` | 1960 Orbital Rocketry → 1970-1971 Orbital Rocketry | 150.5-186.42 | 318.68-330.53 | RP-1+LqdOxygen |
| `YF20_Engine` | YF-20 | 4 | `YF-20` | 1960 Orbital Rocketry → 1968 Orbital Rocketry | 778.2-839.6 | 289.5 | UDMH+NTO |
| `YF21_Engine` | YF-21 | 4 | `YF-20` | 1960 Orbital Rocketry → 1968 Orbital Rocketry | 3112.8-3358.4 | 289.5 | UDMH+NTO |
| `YF21_with_shell_CZ-2` | YF-21 with CZ-2 Boattail | 4 | `YF-20` | 1960 Orbital Rocketry → 1968 Orbital Rocketry | 3112.8-3358.4 | 289.5 | UDMH+NTO |
| `YF21_with_shell_CZ-2C` | YF-21 with CZ-2C Boattail | 4 | `YF-20` | 1960 Orbital Rocketry → 1968 Orbital Rocketry | 3112.8-3358.4 | 289.5 | UDMH+NTO |
| `YF21_with_shell_CZ-2D` | YF-21 with CZ-2D Boattail | 4 | `YF-20` | 1960 Orbital Rocketry → 1968 Orbital Rocketry | 3112.8-3358.4 | 289.5 | UDMH+NTO |
| `YF22_Engine` | YF-22 | 3 | `YF-22` | 1960 Orbital Rocketry → 1968 Orbital Rocketry | 719.8-784.5 | 288.9-298 | UDMH+NTO |
| `YF23_Engine` | YF-23 | 2 | `YF-23` | 1960 Orbital Rocketry → 1963 Orbital Rocketry | 11.525-11.8 | 279.5-296.8 | UDMH+NTO |
| `YF25K_Engine` | YF-20 with Boattail (no gimbal) | 4 | `YF-20` | 1960 Orbital Rocketry → 1968 Orbital Rocketry | 778.2-839.6 | 289.5 | UDMH+NTO |
| `RO-KDU414` | S5.19 | 1 | `S5.19` | Stability | 1.96 | 272 | UDMH+AK20 |
| `ROE-AgenaSPS` | Agena-D Secondary Propulsion System | 3 | `Model8250` | Stability → Docking and Crew Transfer | 0.4-0.9608 | 255.8-278 | UDMH+MON3 · UDMH+IRFNA-III+ElectricCharge · UDMH+IRFNA-IV+ElectricCharge |
| `ROE-G1` | G-1 | 2 | `G-1` | 1961 Orbital Rocketry → 1965 Orbital Rocketry | 53.38-55.02 | 357-368 | Hydrazine+LqdFluorine |
| `ROE-RD219` | RD-219 | 3 | `RD-219-8D713` | 1961 Orbital Rocketry → 1970-1971 Orbital Rocketry | 882.6-941.4 | 293-318 | UDMH+AK27 · UDMH+NTO |
| `ROE-RD855` | RD-851/855 | 2 | `RD-851` | 1961 Orbital Rocketry → 1964 Orbital Rocketry | 81.2-82 | 279-292 | UDMH+AK27 · UDMH+NTO |
| `ROE-RD856` | RD-852/856 | 2 | `RD-852` | 1961 Orbital Rocketry → 1964 Orbital Rocketry | 12.06-13.48 | 255-280.5 | UDMH+AK27 · UDMH+NTO |
| `ROE-RangerRetro` | MC-4-610 | 1 | `MC-4-610` | Stability | 0.255 | 234.97 | Hydrazine |
| `ROE-Antares2_Inline` | Antares IIA X-259 | 1 | `Antares-II` | 1962-1963 Solid Rocket Engines | 93.0746 | 281.4 | PBAA |
| `RO-KTDU5A` | KTDU-5A | 1 | `KTDU-5A` | 1963 Orbital Rocketry | 45.53 | 287 | Tonka250+AK27 |
| `ROE-RD0203` | RD-0203/0204 | 2 | `RD-0203` | 1963 ORSC Engines → 1967 ORSC Engines | 558.9-569.2 | 311 | UDMH+NTO |
| `ROE-RD0212` | RD-0205/0212 | 4 | `RD-0205` | 1963 ORSC Engines → 1992-1997 ORSC Engines | 605.5-638.18 | 324.6-325.3 | UDMH+NTO |
| `ROE-RD0213` | RD-0206/0213 | 4 | `RD-0206` | 1963 ORSC Engines → 1992-1997 ORSC Engines | 575.5-607.2 | 326-327 | UDMH+NTO |
| `ROE-RD0214` | RD-0207/0214 | 2 | `RD-0207` | 1963 ORSC Engines → 1967 ORSC Engines | 7.745 | 293-297 | UDMH+NTO |
| `ROE-Castor2_Inline` | Castor 2 | 2 | `Castor-2-SL` | 1964-1965 Solid Rocket Engines | 318.1-369.23 | 260.7-282.2 | PBAA |
| `ROE-S523` | S5.23 | 1 | `S5.23` | 1964 Orbital Rocketry | 157.6 | 303 | UDMH+AK27 |
| `ROE-SR19` | SR19 | 1 | `SR19-AJ-1` | 1964-1965 Solid Rocket Engines | 267.7 | 288 | CTPB |
| `ROE-TD339` | TD-339 | 1 | `TD-339` | Early Landing | 0.462 | 287 | MMH+MON10 |
| `ROE-RD0210` | RD-0208/0210 | 4 | `RD-0208` | 1965 ORSC Engines → 1992-1997 ORSC Engines | 574.05-626 | 326.105-341.5 | UDMH+NTO |
| `ROE-RD275` | RD-253/RD-275 | 6 | `RD-253` | 1965 ORSC Engines → 2004-2008 ORSC Engines | 1545-1830 | 315.5-316 | UDMH+NTO |
| `ROE-AJ10-137` | AJ10-137 (Service Propulsion System) | 1 | `AJ10-137` | 1966 Orbital Rocketry | 97.416 | 314 | Aerozine50+MON1 |
| `ROE-KTDU35` | KTDU-35 | 1 | `S5_60` | 1966 Orbital Rocketry | 4.09 | 278 | UDMH+AK27 |
| `ROE-RD254` | RD-254 | 6 | `RD-254-11D44` | 1966 ORSC Engines → 2009-2013 ORSC Engines | 1622-1922 | 327.3-327.8 | UDMH+NTO |
| `ROE-C1` | C-1 | 1 | `C-1` | Docking and Crew Transfer | 0.445 | 301 | Aerozine50+MON1 |
| `LargeOMS` | Astris | 2 | `AstrisI` | 1968 Orbital Rocketry | 22.56-23.3 | 297-310 | Aerozine50+NTO |
| `RO-KTDU417` | KTDU-417 | 1 | `11D417` | Lunar Landing | 18.89 | 314 | UDMH+NTO |
| `ROC-LEMLMDEBDB` | Lunar Module Descent Engine (LMDE) | 3 | `LMDE-H` | Lunar Landing → 1972-1975 Orbital Rocketry | 43.5-46.92 | 303-306.4 | Aerozine50+MON1 |
| `ROE-LMDE` | Lunar Module Descent Engine (LMDE) | 3 | `LMDE-H` | Lunar Landing → 1972-1975 Orbital Rocketry | 43.5-46.92 | 303-306.4 | Aerozine50+MON1 |
| `ROE-KTDU425A` | KTDU-425 | 2 | `KTDU-425` | 1970-1971 Orbital Rocketry → 1972-1975 Orbital Rocketry | 18.85-18.89 | 312-315 | UDMH+NTO |
| `ROE-MR80TDE` | MR-80 (TDE) | 1 | `MR-80-TDE` | Improved Landing Engines | 2.811 | 210 | Hydrazine |
| `ROE-HiPAT` | R-4D | 3 | `R-4D-11` | Space Station Attitude Control → Large Spaceplane Control | 0.511-0.556 | 311-329 | MMH+MON3 · Hydrazine+MON3 |
| `ROE-RD270` | RD-270 | 4 | `RD-270-8D420` | 1972-1975 ORSC Engines → 1976-1980 ORSC Engines | 6325.3-7159 | 322-365 | UDMH+NTO · PB-1+HTP · RG-1+LqdOxygen |
| `ROE-Antares3_Inline` | Antares III (STAR 31) | 1 | `Star-31` | 1976-1980 Solid Rocket Engines | 100.374 | 294.36 | HTPB |
| `ROE-R40B` | R-40 | 4 | `R-40A` | Large Spaceplane Control | 3.87-4 | 281-293 | MMH+MON3 · MMH+NTO |
| `ca_lahar` | R-40 | 4 | `R-40A` | Large Spaceplane Control | 3.87-4 | 281-293 | MMH+MON3 · MMH+NTO |
| `ROE-AJ10AdvLong` | AJ10 Series (Advanced Long Nozzle) | 1 | `AJ10-118K` | 1986-1991 Orbital Rocketry | 43.6 | 319.2 | Aerozine50+MON1 |
| `ROE-LEROS1B` | LEROS-1b (635N) | 3 | `LEROS-1b` | Standardized Docking Ports | 0.456-0.707 | 317-324 | Hydrazine+MON1 · MMH+MON3 |
| `ROE-R42` | R-42 | 4 | `R-42` | Standardized Docking Ports → Large Docking Ports | 0.89 | 305-327 | MMH+MON3 · MMH+NTO · Hydrazine+MON3 · Hydrazine+NTO |
| `pit-125` | PIT Mk Va Pulsed Inductive Thruster | 4 | `PITV-Ammonia-40` | 1986-1997 Electric Propulsion → 2009-2018 Electric Propulsion | 0.00072-0.02292 | 4100-7000 | Ammonia+ElectricCharge · Hydrazine+ElectricCharge |
| `restock-engine-125-pug` | Aestus | 3 | `Aestus` | 1992-1997 Orbital Rocketry → 2014-2018 Orbital Rocketry | 27.8-55.4 | 306-340 | MMH+MON3 |
| `ROE-S598M` | S5.98M | 1 | `S5.98M` | 1998-2003 ORSC Engines | 19.61 | 328 | UDMH+NTO |
| `neo_dawn` | Dawn | 1 | `NSTAR` | 1998-2008 Electric Propulsion | 9e-05 | 3200 | XenonGas |
| `neo_ds1` | Deep Space 1 | 1 | `NSTAR` | 1998-2008 Electric Propulsion | 9e-05 | 3200 | XenonGas |
| `ROE-MR80B` | MR-80B (MLE) | 1 | `MR-80B` | Large Rover Designs | 3.603 | 223 | Hydrazine |
| `ROC-CSTRS88` | CST-100 Launch Abort Engines (LAE) | 1 | `LAE` | Modern Capsules | 773.96 | 252 | MMH+MON3+Helium |
| `ROE-LEROS4` | LEROS-4 (1100N) | 1 | `LEROS-4` | Grid Fins | 1.1 | 323 | MMH+MON3 |
| `ROE-SuperDraco` | SuperDraco | 1 | `SuperDraco` | Grid Fins | 85 | 280 | MMH+NTO |
| `ROE-SuperDracoDouble` | Twin SuperDraco | 1 | `SuperDraco` | Grid Fins | 170 | 280 | MMH+NTO |
| `ROC-GeminiOAMSBDB` | Gemini Orbit Attitude and Maneuvering System (SE-7-100) | 1 | `OAMS` | — | 0.440374 | 296 | MMH+NTO |
| `ROC-LFVBDB` | Lunar Flying Vehicle | 1 | `LFV` | — | 1.868 | 295 | Aerozine50+MON1 |
| `ROC-OrionESM` | Orion European Service Module | 1 | `8*R-4D-11` | — | 3.92 | 311 | MMH+MON3 |
| `ROC-OrionLAS` | Orion LAS and BPC | 1 | `Orion-LAS` | — | 1779.28 | 290 | HTPB |
| `ROE-AJ10-190` | AJ10-190 | 2 | `AJ10-190-OMS` | — | 26.7-33.4 | 316 | MMH+MON3 |
| `ROE-JupiterVernier` | S-3D Vernier Exhaust | 2 | `S-3_Vernier` | — | 1.5 | 200-220 | UDMH+LqdOxygen · RP-1+LqdOxygen |
| `ROE-S592` | S5.92 | 2 | `S5.92` | — | 19.61-20.01 | 327-333.2 | UDMH+NTO |
| `ROE-XLR41` | XLR41 | 1 | `XLR41-NA-1` | — | 333 | 239 | Ethanol75+LqdOxygen |
| `ca_trident` | Bi-Propellant Apogee Engine | 2 | `3x400N-Apogee` | — | 1.275 | 321 | MMH+MON3 · MMH+NTO |
| `galileo_mb` | Galileo Spacecraft | 1 | `S400 - 1` | — | 0.4 | 303 | MMH+MON3 |
| `ius_top` | IUS Booster Second Stage | 1 | `Orbus-6E` | — | 113.87 | 303.5 | HTPB |
| `luna_ktdu` | Luna 9/10/13 KTDU | 1 | `Luna KTDU` | — | 44 | 287 | AK27+Tonka250 |
| `luna_vernier` ‡ | Luna Vernier | 1 | `Luna KTDU` | — | 0.15 | 287 | AK27+Tonka250 |
| `magellan` | Magellan | 1 | `MR-104` | — | 3.528 | 239 | Hydrazine |
| `molniya1` ‡ | Molniya-1 | 1 | `Molniya Sat` | — | 1.96 | 290 | AK20+Tonka250 |
| `neo_near` | NEAR - Shoemaker | 1 | `LVA` | — | 0.45 | 317 | Hydrazine+NTO |
| `polyot` ‡ | Polyot | 1 | `Polyot` | — | 1.96 | 290 | AK20+Tonka250 |
| `polyot_side_engine` ‡ | Polyot Side Engine | 1 | `Polyot` | — | 1.96 | 290 | AK20+Tonka250 |
| `rn_cassini` | Cassini Spacecraft | 1 | `CME` | — | 0.89 | 321 | MMH+MON3 |
| `rn_juno_spacecraft` ‡ | Juno | 1 | `Leros-1b` | — | 0.635 | 317 | Hydrazine+MON3 |
| `rn_ladee` ‡ | Lunar Atmosphere Dust and Environment Explorer | 1 | `HiPAT` | — | 0.455 | 323 | MMH+NTO |
| `rn_lro` ‡ | Lunar Reconnaissance Orbiter | 1 | `LRO` | — | 0.3559 | 317 | Hydrazine+NTO |
| `rn_mariner10` ‡ | Mariner 10 | 1 | `Mariner 10 Engine` | — | 0.222 | 234.97 | Hydrazine |
| `rn_mariner1_2` | Mariner 1/2 | 1 | `Mariner 1/2 Engine` | — | 0.225 | 234.97 | Hydrazine |
| `rn_mariner3-4` ‡ | Mariner 3/4 | 1 | `Mariner 3/4 Engine` | — | 0.222 | 234.97 | Hydrazine |
| `rn_mariner5` ‡ | Mariner 5 | 1 | `Mariner 5 Engine` | — | 0.222 | 234.97 | Hydrazine |
| `rn_mariner6-7` ‡ | Mariner 6/7 | 1 | `Mariner 6/7 Engine` | — | 0.223 | 234.97 | Hydrazine |
| `rn_mariner8-9` ‡ | Mariner 8/9 | 1 | `RS-2101A` | — | 1.34 | 287 | MMH+NTO |
| `rn_mars_observer` ‡ | Mars Observer | 1 | `4xR-4D` | — | 1.96 | 312 | MMH+NTO |
| `rn_messenger` | MESSENGER | 1 | `LVA` | — | 0.645 | 317 | Hydrazine+NTO |
| `rn_surveyor_engines` | Surveyor Engines | 1 | `Thiokol TD-339` | — | 1.3878 | 287 | MMH+MON10 |
| `rn_surveyor_s_engine` | TD-339 | 1 | `Thiokol TD-339` | — | 0.4626 | 287 | MMH+MON10 |
| `rn_venera1` ‡ | Venera 1/Mars 1M | 1 | `Venera 1` | — | 1.96 | 290 | AK20+Tonka250 |

## Cryogenic (hydrolox / methalox) — 69 parts

| Part | Title | Var | Base config | Tech span | Thrust kN (vac) | IspVac | Propellants |
|---|---|---:|---|---|---|---|---|
| `RO-model304` | Model 304 Turbojet | 1 | `Model304-2` | High Speed Flight | 60.1 | — (airbreathing) | LqdHydrogen |
| `ROE-Agena` | XLR81 (Agena) Vacuum Engine | 14 | `Model117` | 1958 Orbital Rocketry → 1998-2003 Orbital Rocketry | 53.42-75.62 | 265.5-446.2 | Kerosene+IRFNA-III · UDMH+IRFNA-III · LqdFluorine+LqdHydrogen · UDMH+IRFNA-IV … |
| `ROE-RL10Fixed` | RL-10 Series (Non-Extendable Nozzle) | 20 | `RL10A-1` | Prototype Hydrolox Engines → Near Future Hydrolox Engines | 64.75-108.3 | 360-470.5 | LqdHydrogen+LqdOxygen · LqdMethane+LqdOxygen |
| `ROE-LR87_LH2` | AJ23-65 | 4 | `LR87-LH2-TitanC` | Early Hydrolox Engines → 1969 Hydrolox Engines | 667-889 | 403-434 | LqdHydrogen+LqdOxygen |
| `ROE-RZ20` | RZ.20 | 2 | `RZ20-Mk1` | Early Hydrolox Engines → 1968 Hydrolox Engines | 70-72.56 | 410-425 | LqdHydrogen+LqdOxygen |
| `ROE-AJ10Adv` | AJ10 Series (Advanced Short Nozzle) | 5 | `AJ10-138` | 1964 Orbital Rocketry → 1976-1980 Orbital Rocketry | 26.67-42.1 | 302.2-433 | Aerozine50+NTO · LqdHydrogen+LqdOxygen |
| `ROC-D2AJ10-133` | AJ10-133-LH | 3 | `AJ10-133-LH` | Improved Hydrolox Engines → 1976-1980 Orbital Rocketry | 26.67-35.585 | 310.6-433 | LqdHydrogen+LqdOxygen · Aerozine50+NTO |
| `ROE-HM7` | HM-7 | 4 | `HM-7` | Improved Hydrolox Engines → 1986-1991 Hydrolox Engines | 62.4-64.8 | 440.8-446 | LqdHydrogen+LqdOxygen |
| `ROE-J2` | J-2 | 4 | `J-2-200K` | Improved Hydrolox Engines → 1972-1975 Hydrolox Engines | 889.644-1178.78 | 418-436 | LqdHydrogen+LqdOxygen |
| `YF75D_Engine` | YF-75 | 3 | `YF-75` | Improved Hydrolox Engines → 1998-2003 Hydrolox Engines | 78.45-92.11 | 439.6-451.1 | LqdHydrogen+LqdOxygen |
| `YF75_Engine` | YF-75 | 3 | `YF-75` | Improved Hydrolox Engines → 1998-2003 Hydrolox Engines | 156.9-184.22 | 439.6-451.1 | LqdHydrogen+LqdOxygen |
| `KIWIA24` | Kiwi A3 Atomic Rocket Motor | 1 | `KIWIA24-Hydrogen` | Prototype Nuclear Propulsion | 29.3 | 768 | LqdHydrogen+EnrichedUranium |
| `KIWIB48` | Kiwi B4E Atomic Rocket Motor | 1 | `KIWIB48-Hydrogen` | Prototype Nuclear Propulsion | 220 | 831 | LqdHydrogen+EnrichedUranium |
| `ROC-LEMLMAEBDB` | Lunar Module Ascent Engine (LMAE) | 2 | `LMAE` | Lunar Landing → 2019-2028 Orbital Rocketry | 15.57-24.5 | 311-356 | Aerozine50+MON1 · LqdMethane+LqdOxygen |
| `ROE-LMAE` | Lunar Module Ascent Engine (LMAE) | 2 | `LMAE` | Lunar Landing → 2019-2028 Orbital Rocketry | 15.57-24.5 | 311-356 | Aerozine50+MON1 · LqdMethane+LqdOxygen |
| `ROE-M1` | M-1 | 5 | `M-1-Spec` | 1969 Hydrolox Engines → 1986-1991 Hydrolox Engines | 5337.87-8006.8 | 414-430 | LqdHydrogen+LqdOxygen |
| `NERVA_NRX` | NERVA NRX | 1 | `NERVA_NRX-Hydrogen` | Early Nuclear Propulsion | 243 | 848 | LqdHydrogen+EnrichedUranium |
| `Phoebus1N50` | Phoebus 1B Atomic Rocket Motor | 1 | `Phoebus1N50-Hydrogen` | Early Nuclear Propulsion | 299 | 828 | LqdHydrogen+EnrichedUranium |
| `ROE-LR129` | LR129 | 4 | `XLR129-P-1` | Prototype FRSC Engines → 1992-1997 FRSC Engines | 1049.2-1538.8 | 435-440 | LqdHydrogen+LqdOxygen |
| `ROE-NERVAXE` | Nerva XE-Prime | 1 | `NERVA_XE-Hydrogen` | Early Nuclear Propulsion | 239 | 850 | LqdHydrogen+EnrichedUranium |
| `ROE-RD57` | RD-57 | 3 | `RD-57` | Prototype FRSC Engines → 1998-2008 FRSC Engines | 392.3-432 | 456.6-461 | LqdHydrogen+LqdOxygen |
| `RO_KVD1` | RD-56/KVD-1/CE-7.5 | 3 | `RD-56` | Prototype FRSC Engines → 2009-2013 FRSC Engines | 69.55-73.6 | 447.5-461.5 | LqdHydrogen+LqdOxygen |
| `ROE-HG3` | HG-3 | 8 | `HG-3` | 1976-1980 FRSC Engines → 1986-1991 FRSC Engines | 1382.07-1422.44 | 445-458 | LqdHydrogen+LqdOxygen |
| `ROE-J2T` | J-2T | 2 | `J-2T-200K` | 1976-1980 Hydrolox Engines → 1981-1985 Hydrolox Engines | 889.3-1111.6 | 440-442 | LqdHydrogen+LqdOxygen |
| `PEWEE100` | Peewee 100 Atomic Rocket Motor | 3 | `PEWEE100-Hydrogen` | Basic Nuclear Propulsion | 111-227.3 | 440-901 | LqdHydrogen+EnrichedUranium · LqdAmmonia+EnrichedUranium · LqdAmmonia+LqdMethane+EnrichedUranium |
| `Phoebus2N100` | Phoebus 2A Atomic Rocket Motor | 1 | `Phoebus2N100-Hydrogen` | Basic Nuclear Propulsion | 913 | 813 | LqdHydrogen+EnrichedUranium |
| `RO-KA-PrincetonLNTR` | Princeton LNTR | 2 | `PrincetonLNTR-ZrC` | Basic Nuclear Propulsion → Improved Nuclear Propulsion | 39.03-40.88 | 1350-1414 | LqdHydrogen+EnrichedUranium+CoreModerator |
| `ROE-NERVA` | NERVA I | 3 | `NERVA-I` | Basic Nuclear Propulsion | 334-648.8 | 439-900 | LqdHydrogen+EnrichedUranium · LqdAmmonia+EnrichedUranium · LqdAmmonia+LqdMethane+EnrichedUranium |
| `ROE-RS25` | RS-25 (SSME) | 4 | `RS-25` | 1981-1985 FRSC Engines → 1998-2008 FRSC Engines | 2090-2364.5 | 452.3-455.2 | LqdHydrogen+LqdOxygen |
| `RD0410MID` | RD-0410 | 4 | `RD-0410MID-Hydrogen` | Improved Nuclear Propulsion | 35.3-72.84 | 438-910 | LqdHydrogen+EnrichedUranium · LqdAmmonia+EnrichedUranium · LqdMethane+EnrichedUranium · LqdAmmonia+LqdMethane+EnrichedUranium |
| `RO-KA-LRCNTR` | Lewis Research Center LNTR | 1 | `LRCLNTR` | Improved Nuclear Propulsion | 145.6 | 1400 | LqdHydrogen+EnrichedUranium+CoreModerator+TungstenPowder |
| `ROE-AJ10-transtar` | AJ23 Transtar | 4 | `AJ10-151-OMS` | 1986-1991 Orbital Rocketry → 1992-1997 Orbital Rocketry | 13.3-26.7 | 328-483 | MMH+MON3 · LqdHydrogen+LqdOxygen |
| `ROE-LE5` | LE-5 | 5 | `LE-5` | 1986-1991 Hydrolox Engines → 2019-2028 Hydrolox Engines | 102.9-137.2 | 446.8-452 | LqdHydrogen+LqdOxygen |
| `ROE-NERVAII` | NERVA II | 1 | `NERVA-II` | Improved Nuclear Propulsion | 867 | 850 | LqdHydrogen+EnrichedUranium |
| `ROE-RD0120` | RD-0120 | 3 | `RD-0120` | 1986-1991 FRSC Engines → 1998-2008 FRSC Engines | 1961-2313 | 454.5-460.7 | LqdHydrogen+LqdOxygen |
| `restock-engine-cherenkov` | RD-0410 | 4 | `RD-0410MID-Hydrogen` | Improved Nuclear Propulsion | 35.3-72.84 | 438-910 | LqdHydrogen+EnrichedUranium · LqdAmmonia+EnrichedUranium · LqdMethane+EnrichedUranium · LqdAmmonia+LqdMethane+EnrichedUranium |
| `rmm_arenysaurus` | LRBE | 2 | `LRBE` | 1986-1991 FRSC Engines → 1998-2008 FRSC Engines | 2429-2473.5 | 352.7-355 | LqdMethane+LqdOxygen |
| `rmm_ishtar` | RS-25-50X (SSME-50X) | 2 | `RS-25A-50X` | 1986-1991 FRSC Engines → 1998-2008 FRSC Engines | 2066-2293.2 | 447.1-450 | LqdHydrogen+LqdOxygen |
| `ROE-LE7` | LE-7 | 3 | `LE-7` | 1992-1997 FRSC Engines → 1998-2008 FRSC Engines | 996.4-1098 | 438-446.5 | LqdHydrogen+LqdOxygen |
| `ROE-RL10A4N` | RL-10A-4N Series (46" Extendable Nozzle) | 2 | `RL10A-4N` | 1992-1997 Hydrolox Engines | 92.5-99.2 | 448.9-450.5 | LqdHydrogen+LqdOxygen |
| `YF77_Engine` | YF-77 | 1 | `YF-77` | 1992-1997 Hydrolox Engines | 700 | 428 | LqdHydrogen+LqdOxygen |
| `YF77_Engine-double-withShell` | YF-77 with CZ-5 Boattail | 1 | `YF-77` | 1992-1997 Hydrolox Engines | 1400 | 428 | LqdHydrogen+LqdOxygen |
| `nflv-engine-stbe-kero-1` | STBE (Pratt & Whitney) | 3 | `STBE-1A` | 1992-1997 Orbital Rocketry → 1998-2003 Orbital Rocketry | 3172-3275 | 316-341.5 | RP-1+LqdOxygen · LqdMethane+LqdOxygen |
| `rmm_dugong` | SSBE | 2 | `SSBE` | 1992-1997 FRSC Engines → 1998-2008 FRSC Engines | 2265-2306 | 358.7-361 | RP-1+LqdOxygen+LqdHydrogen |
| `rmm_rainier` | Space Transportation Main Engine (STME) | 1 | `STME` | 1992-1997 Hydrolox Engines | 2891.3 | 428.5 | LqdHydrogen+LqdOxygen |
| `rmm_turiasaurus` | STBE (Pratt & Whitney) | 3 | `STBE-1A` | 1992-1997 Orbital Rocketry → 1998-2003 Orbital Rocketry | 3172-3275 | 316-341.5 | RP-1+LqdOxygen · LqdMethane+LqdOxygen |
| `ROE-RD0146` | RD-0146 | 2 | `RD-0146` | 1998-2003 Hydrolox Engines → 2014-2018 Hydrolox Engines | 73.5-98.1 | 463-470 | LqdHydrogen+LqdOxygen |
| `ROE-RL10B2` | RL-10B/C Series (84.1" Extendable Nozzle) | 4 | `RL10B-2` | 1998-2003 Hydrolox Engines → 2019-2028 Hydrolox Engines | 110-110.1 | 465-465.6 | LqdHydrogen+LqdOxygen |
| `ROE-RS68` | RS-68 | 5 | `RS-68` | 1998-2003 Hydrolox Engines → 2019-2028 Hydrolox Engines | 3380.1-4192.2 | 410-435 | LqdHydrogen+LqdOxygen |
| `ROE-SNTPPFE100` | SNTP-PFE100 Atomic Rocket Motor | 4 | `SNTPPFE100-Prototype` | Advanced Nuclear Propulsion → Efficient Nuclear Propulsion | 206-503.06 | 465-954 | LqdHydrogen+EnrichedUranium · LqdAmmonia+EnrichedUranium · LqdAmmonia+LqdMethane+EnrichedUranium |
| `cryoengine-allosaur-1` | STBE-3 | 1 | `STBE-3` | 1998-2003 Orbital Rocketry | 3172 | 341.5 | LqdMethane+LqdOxygen |
| `cryoengine-vesuvius-1` | Vulcain 2 | 1 | `Vulcain-2` | 1998-2003 Hydrolox Engines | 1350 | 433 | LqdHydrogen+LqdOxygen |
| `nflv-engine-rd701-1` | RD-701 | 1 | `RD-701` | 1998-2008 FRSC Engines | 4004 | 415 | RG-1+LqdHydrogen+LqdOxygen |
| `nflv-engine-rd704-1` | RD-704 | 1 | `RD-704` | 1998-2008 FRSC Engines | 2002 | 407 | RG-1+LqdHydrogen+LqdOxygen |
| `ntr-gc-25-1` | Low-Pressure NTR | 2 | `LPNTR-3200HP` | Advanced Nuclear Propulsion → Efficient Nuclear Propulsion | 47.596 | 1037-1183 | LqdHydrogen |
| `ROE-J2X` | J-2X | 1 | `J-2X` | 2009-2013 Hydrolox Engines | 1308 | 448 | LqdHydrogen+LqdOxygen |
| `ROE-MB35` | MB-35 | 1 | `MB-35` | 2009-2013 Hydrolox Engines | 155.7 | 468 | LqdHydrogen+LqdOxygen |
| `ROE-MB60` | MB-60 | 1 | `MB-60` | 2009-2013 Hydrolox Engines | 266.9 | 467 | LqdHydrogen+LqdOxygen |
| `rmm_arsia` | RS-25-650 (SSME-650) | 1 | `RS-25-650` | 2009-2013 FRSC Engines | 2093 | 478 | LqdHydrogen+LqdOxygen |
| `ROE-BE3` | BE-3PM | 1 | `BE3` | 2014-2018 Hydrolox Engines | 511.3 | 360 | LqdHydrogen+LqdOxygen |
| `ROE-BE4` | BE-4 | 1 | `BE-4` | 2019-2028 ORSC Engines | 2647.5 | 341 | LqdMethane+LqdOxygen |
| `ROE-BNTR` | Bimodal NTR | 3 | `BNTR` | Bimodal Nuclear Propulsion | 66.72-135.05 | 457-925 | LqdHydrogen · LqdAmmonia · LqdAmmonia+LqdMethane |
| `cryoengine-buzzard-1` | M10 | 1 | `M10` | 2019-2028 Orbital Rocketry | 98.1 | 362 | LqdMethane+LqdOxygen |
| `cryoengine-fuji-1` | LE-9 | 1 | `LE-9` | 2019-2028 Hydrolox Engines | 1471 | 425 | LqdHydrogen+LqdOxygen |
| `cryoengine-pavonis-1` | RL60/Vinci | 2 | `RL60` | 2019-2028 Hydrolox Engines | 180-289.1 | 465 | LqdHydrogen+LqdOxygen |
| `cryoengine-tharsis-1` | RL60/Vinci | 2 | `RL60` | 2019-2028 Hydrolox Engines | 360-578.2 | 465 | LqdHydrogen+LqdOxygen |
| `fft-ffre-plasma-1` | Dusty Plasma Afterburning Fission Fragment Rocket Engine | 1 | `FissionFragment` | Near Future Nuclear Propulsion | 0.043 | 527000 | FissionParticles |
| `RO-LifeSupport-DummyEngine` | Life Support Config Engine | 2 | `Kerbalism-Engine` | — | 0.01 | 0.01 | Food+Water+Oxygen · LqdOxygen+LqdHydrogen |
| `cryoengine-eagle-1` | Raptor-Vacuum | 3 | `Raptor-1V` | — | 1961.33-3000.83 | 378-380 | CooledLqdMethane+CooledLqdOxygen |

## Other (nuclear, electric, exotic, jets) — 71 parts

| Part | Title | Var | Base config | Tech span | Thrust kN (vac) | IspVac | Propellants |
|---|---|---:|---|---|---|---|---|
| `sputnik2` | Sputnik 2 | 1 | `(single config)` | Early Avionics and Probes | 0.16 | 2 | LqdOxygen |
| `ROE-Algol1` | Algol IB | 1 | `Algol-I` | 1959-1960 Solid Rocket Engines | 493.644 | 241.4 | PUPE |
| `ROE-Algol1_Inline` | Algol IB | 1 | `Algol-I` | 1959-1960 Solid Rocket Engines | 493.644 | 241.4 | PUPE |
| `ROE-Antares1` | Antares I X-254 | 1 | `Antares-I` | 1959-1960 Solid Rocket Engines | 62.2751 | 256 | PBAA |
| `ROE-Algol2` | Algol II | 1 | `Algol-II` | 1962-1963 Solid Rocket Engines | 449.021 | 258.88 | PUPE |
| `ROE-Algol2_Inline` | Algol II | 1 | `Algol-II` | 1962-1963 Solid Rocket Engines | 449.021 | 258.88 | PUPE |
| `ROE-AltairII` | Altair II X-258 | 1 | `Altair-II` | 1962-1963 Solid Rocket Engines | 35 | 279 | PBAA |
| `ROE-Antares2` | Antares IIA X-259 | 1 | `Antares-II` | 1962-1963 Solid Rocket Engines | 93.0746 | 281.4 | PBAA |
| `ROE-M55` | M55 (Minuteman) | 1 | `M55` | 1962-1963 Solid Rocket Engines | 876 | 262 | PBAA |
| `ROE-NK9` | NK-9 | 4 | `NK-9` | 1963 ORSC Engines → 2009-2013 ORSC Engines | 426.6-603 | 328-331.6 | RG-1+LqdOxygen · CooledRG-1+CooledLqdOxygen · CooledRP-1+CooledLqdOxygen |
| `ROE-NK9V` | NK-9V/21/19/39/31 | 5 | `NK-9V` | 1963 ORSC Engines → 1972-1975 ORSC Engines | 402.1-451.1 | 340-353 | RG-1+LqdOxygen · CooledRG-1+CooledLqdOxygen |
| `ROE-AltairIII` | Altair III FW-4S | 1 | `Altair-III` | 1964-1965 Solid Rocket Engines | 29.36 | 284.22 | PBAN |
| `ROE-Castor2` | Castor 2 | 2 | `Castor-2-SL` | 1964-1965 Solid Rocket Engines | 318.1-369.23 | 260.7-282.2 | PBAA |
| `ROE-SR73` | SR73 | 1 | `SR73-AJ-1` | 1964-1965 Solid Rocket Engines | 152 | 296.9 | CTPB |
| `ROE-UA1204` | UA1204 | 1 | `UA1204` | 1964-1965 Solid Rocket Engines | 4151.3 | 266 | PBAN |
| `ROE-UA1205` | UA1205 | 1 | `UA1205` | 1964-1965 Solid Rocket Engines | 5338 | 266 | PBAN |
| `ROE-AJ260SLA` | AJ-260 SL Radial Solid Rocket Booster | 2 | `AJ260-SL1` | 1966 Solid Rocket Engines → 1969-1971 Solid Rocket Engines | 17741-26708 | 263 | PBAN |
| `ROE-AJ260SLF` | AJ-260 SL | 2 | `AJ260-SL1` | 1966 Solid Rocket Engines → 1969-1971 Solid Rocket Engines | 17741-26708 | 263 | PBAN |
| `ROE-Star13` | STAR 13 | 1 | `Star-13` | 1966 Solid Rocket Engines | 5.68 | 275.2 | PUPE |
| `ROE-Star13A` | STAR 13A | 1 | `Star-13A` | 1966 Solid Rocket Engines | 5.87 | 288.3 | CTPB |
| `ROE-Star37` | STAR 37 | 1 | `STAR-37` | 1966 Solid Rocket Engines | 43.5 | 289 | PBAN |
| `ROC-D2Block2LES` | D-2 Block II Launch Escape System | 1 | `(single config)` | Mature Capsules | 620 | 205 | PBAN |
| `ROE-Star17` | STAR 17 | 1 | `STAR-17` | 1967-1968 Solid Rocket Engines | 10.94 | 286.2 | CTPB |
| `ROE-UA1206` | UA1206 | 1 | `UA1206` | 1967-1968 Solid Rocket Engines | 6227 | 265 | PBAN |
| `ROE-NK33` | NK-15/33 | 7 | `NK-15` | 1969 ORSC Engines → 2009-2013 ORSC Engines | 1543.6-1815 | 318-331.9 | CooledRG-1+CooledLqdOxygen · CooledRP-1+CooledLqdOxygen |
| `ROE-NK43` | NK-15V/43 | 5 | `NK-15V` | 1969 ORSC Engines → 2004-2008 ORSC Engines | 1647.5-1823.9 | 325-346 | CooledRG-1+CooledLqdOxygen |
| `ROE-Star17A` | STAR 17A | 1 | `Star-17A` | 1969-1971 Solid Rocket Engines | 17.4 | 286.7 | CTPB |
| `ROE-UA1207` | UA1207 | 1 | `UA1207` | 1969-1971 Solid Rocket Engines | 7450 | 269.5 | PBAN |
| `SXTNK21BlockV` | N1 Block V | 2 | `4x_NK-21` | 1969 ORSC Engines → 1972-1975 ORSC Engines | 1608-1628 | 353 | CooledRG-1+CooledLqdOxygen |
| `RO-SPT50` | SPT-50 Hall Effect Thruster | 2 | `SPT-50` | Early Electric Propulsion → 1986-1997 Electric Propulsion | 1.4e-05-1.8e-05 | 860-1200 | XenonGas+ElectricCharge |
| `RO-SPT60` | SPT-60 Hall Effect Thruster | 1 | `SPT-60` | Early Electric Propulsion | 3e-05 | 1185 | XenonGas+ElectricCharge |
| `RO-fftorion12` | 12 Meter Orion Drive | 1 | `FissionPulse` | Early Nuclear Propulsion | 4320 | 3670 | FissionPulses |
| `RO-fftorion8` | 8 Meter Orion Drive | 1 | `FissionPulse` | Early Nuclear Propulsion | 2360 | 2720 | FissionPulses |
| `RO-ionSPT60` | SPT-60 Hall Effect Thruster | 1 | `SPT-60` | Early Electric Propulsion | 3e-05 | 1185 | XenonGas+ElectricCharge |
| `ROE-AJ260FLA` | AJ-260 FL Radial Solid Rocket Booster | 1 | `AJ260-FL` | 1972-1975 Solid Rocket Engines | 35391 | 263 | PBAN |
| `ROE-AJ260FLF` | AJ-260 FL | 1 | `AJ260-FL` | 1972-1975 Solid Rocket Engines | 35391 | 263 | PBAN |
| `ROE-Algol3` | Algol III | 1 | `Algol-III` | 1972-1975 Solid Rocket Engines | 530.259 | 260.289 | PBAN |
| `ROE-Algol3_Inline` | Algol III | 1 | `Algol-III` | 1972-1975 Solid Rocket Engines | 530.259 | 260.289 | PBAN |
| `ROE-Castor4` | Castor 4 | 1 | `Castor-4` | 1972-1975 Solid Rocket Engines | 460 | 261 | PBAN |
| `fft-fission-orion-5-1` | 10 Meter Orion Drive | 1 | `FissionPulse` | Early Nuclear Propulsion | 3470 | 3300 | FissionPulses |
| `ROE-RD301` | RD-301 | 1 | `RD-301` | 1976-1980 FRSC Engines | 97.67 | 400 | LqdAmmonia+LqdFluorine |
| `RO-SPT70` | SPT-70 Hall Effect Thruster | 3 | `SPT-70` | 1981-1985 Electric Propulsion → 2019-2028 Electric Propulsion | 3.13e-05-4.13e-05 | 1460-1580 | XenonGas+ElectricCharge · KryptonGas+ElectricCharge |
| `ROE-RD120` | RD-120 | 3 | `RD-120` | 1981-1985 ORSC Engines → 1998-2003 ORSC Engines | 833.56-912.02 | 330-350 | RG-1+LqdOxygen |
| `ROE-RD8` | RD-8 | 1 | `RD-8` | 1981-1985 ORSC Engines | 19.61 | 342 | RG-1+LqdOxygen |
| `RO-SPT100` | SPT-100 Hall Effect Thruster | 4 | `SPT-100` | 1986-1997 Electric Propulsion → 2009-2018 Electric Propulsion | 8e-05-9.02e-05 | 1600-1740 | XenonGas+ElectricCharge |
| `ROE-RD170` | RD-170 | 4 | `RD-171` | 1986-1991 ORSC Engines → 2004-2008 ORSC Engines | 7904-8316 | 337.1-337.4 | RG-1+LqdOxygen |
| `ROE-UA1208` | UA1208 | 1 | `UA1208` | 1986-1991 Solid Rocket Engines | 7450 | 269.5 | PBAN |
| `RO-457M` | 457M 72kW Hall Effect Thruster | 3 | `457M-V1` | 1998-2008 Electric Propulsion → 2009-2018 Electric Propulsion | 0.0019864-0.00295 | 2740-3817 | XenonGas+ElectricCharge · KryptonGas+ElectricCharge |
| `RO-SPT140` | SPT-140 Hall Effect Thruster | 2 | `SPT-140` | 1998-2008 Electric Propulsion → 2009-2018 Electric Propulsion | 0.000193-0.00029 | 1680-1770 | XenonGas+ElectricCharge |
| `ionEngine` | NSTAR Gridded Ion Thruster | 1 | `NSTAR` | 1998-2008 Electric Propulsion | 9.2e-05 | 3100 | XenonGas+ElectricCharge |
| `ROE-RD0124` | RD-0124 | 1 | `RD-0124` | 2004-2008 ORSC Engines | 294.3 | 359 | RG-1+LqdOxygen |
| `RO-nupit` | NuPIT Pulsed Inductive Thruster | 2 | `NuPIT-6000` | 2009-2018 Electric Propulsion | 0.0043-0.0049 | 6000-7000 | LqdAmmonia+ElectricCharge |
| `ROE-RD0110R` | RD-0110R | 2 | `RD-0110R` | 2009-2013 Orbital Rocketry | 68.3 | 298 | RG-1+LqdOxygen · CooledRG-1+CooledLqdOxygen |
| `ionArgon-0625-2` | P5 5kW Hall Effect Thruster | 2 | `P5-1` | 2009-2018 Electric Propulsion | 0.000239-0.000245 | 2390-2420 | ElectricCharge+XenonGas |
| `ionArgon-0625-3` | X3 Hall-Effect Thruster | 3 | `X3` | 2009-2018 Electric Propulsion → 2019-2028 Electric Propulsion | 0.00542-0.008 | 2340-4370 | XenonGas+ElectricCharge · KryptonGas+ElectricCharge |
| `ionXenon-0625-2` | HiPEP Gridded Ion Thruster | 1 | `HiPEP` | 2009-2018 Electric Propulsion | 0.00067 | 9620 | ElectricCharge+XenonGas |
| `ionXenon-0625-3` | DS4G Gridded Ion Thruster | 5 | `DS4G-25-low` | 2009-2018 Electric Propulsion → 2019-2028 Electric Propulsion | 0.00031-0.00109 | 5000-15000 | XenonGas+ElectricCharge |
| `pit-0625` | FARAD Pulsed Inductive Thruster | 1 | `FARAD` | 2009-2018 Electric Propulsion | 0.00147 | 2500 | ArgonGas+ElectricCharge |
| `RO-ID500` | ID-500 Gridded Ion Thruster | 1 | `ID-500` | 2019-2028 Electric Propulsion | 0.00075 | 7140 | XenonGas+ElectricCharge |
| `RO-fftdustyplasmaffre` | Dusty Plasma Fission Fragment Rocket Engine | 1 | `FissionFragment` | Bimodal Nuclear Propulsion | 0.043 | 527000 | FissionParticles |
| `ionArgon-0625` | HERMeS Hall Effect Thruster | 2 | `HERMeS` | 2019-2028 Electric Propulsion | 0.000589 | 2820-2900 | XenonGas+ElectricCharge |
| `ionXenon-0625` | NEXT Gridded Ion Thruster | 2 | `NEXT` | 2019-2028 Electric Propulsion | 0.000118-0.000236 | 4190 | ElectricCharge+XenonGas |
| `mpdt-125` | SX3 MPD Thruster | 1 | `SX3` | 2019-2028 Electric Propulsion | 0.00275 | 4665 | ArgonGas+ElectricCharge |
| `vasimr-0625` | VX-200SS VASIMR | 2 | `VX-200SS-Ar` | 2019-2028 Electric Propulsion | 0.005-0.007 | 3850-6000 | ArgonGas+ElectricCharge · KryptonGas+ElectricCharge |
| `vasimr-125` | VF-200 VASIMR | 2 | `VF-200-Ar` | 2019-2028 Electric Propulsion | 0.006-0.0084 | 3210-5000 | ArgonGas+ElectricCharge · KryptonGas+ElectricCharge |
| `RO-fft20mMMO` | 20 m "Mini-Mag" Orion Drive | 1 | `FissionPulse` | Near Future Nuclear Propulsion | 1870 | 16000 | FissionPellets |
| `fft-fission-zpinch-1` | 10 m "Mini-Mag" Orion Drive | 1 | `FissionPulse` | Near Future Nuclear Propulsion | 642 | 9500 | FissionPellets |
| `fft-nswr-2` | 20 m Nuclear Salt Water Rocket | 1 | `nswr` | Near Future Nuclear Propulsion | 8696.9 | 8000 | NuclearSaltWater |
| `RO-PPS1350` | PPS-1350 Hall Effect Thruster | 2 | `PPS-1350-S` | — | 9e-05-0.00014 | 1660-1800 | XenonGas+ElectricCharge |
| `ROE-Raptor` | Raptor (Surface Variant) | 3 | `Raptor-1` | — | 1814.23-2745.86 | 347-350 | CooledLqdMethane+CooledLqdOxygen |
| `ROE-RaptorVac` | Raptor-Vacuum | 3 | `Raptor-1V` | — | 1961.33-3000.83 | 378-380 | CooledLqdMethane+CooledLqdOxygen |

## Airbreathing / hybrid — no RealFuels config path

These curated `engine:*` parts use jet/propeller/ramjet modules (AJE) or are integrated effect parts, so they have no CONFIG-based upgrade path. Their stats live in a different module system (thrust vs. mach/altitude curves).

| Part | Type | Engine module |
|---|---|---|
| `RAPIER` | engine:cryo | ModuleEnginesAJEJet+ModuleEnginesRF |
| `SXTJ213` | engine:other | ModuleEnginesAJEPropeller |
| `SXTKO211Dprop` | engine:other | ModuleEnginesAJEPropeller |
| `SXTMerlin46Prop` | engine:other | ModuleEnginesAJEPropeller |
| `SXTMerlin66prop` | engine:other | ModuleEnginesAJEPropeller |
| `SXTMiniJet` | engine:kerolox | ModuleEnginesAJEJet |
| `SXTPWR2800` | engine:other | ModuleEnginesAJEPropeller |
| `SXTR280018WProp` | engine:other | ModuleEnginesAJEPropeller |
| `SXTR280021Prop` | engine:other | ModuleEnginesAJEPropeller |
| `SXTTinyprop` | engine:other | ModuleEnginesAJEPropeller |
| `SXT_Jumo213A` | engine:other | ModuleEnginesAJEPropeller |
| `aje_ramjet` | engine:kerolox | ModuleEnginesAJERamjet |
