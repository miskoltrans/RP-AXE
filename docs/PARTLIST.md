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
| RN_US_Probes | 106 | **72** | Inherit 34 component cuts: 11 std solar panels (redundant), 3 scanners (→DMagic), 12-part KH-9 spy-sat family, 8 part-specific decouplers/RCS/legs. Reverse the 13 iconic whole-probes (Mariner-Mars 3/4–10, LRO, LADEE, LCROSS, Juno, Helios, Mars Observer, Sphinx, TDRS A-G). Prune RaiderNick's 3 internal `DEPRECATED` dupes regardless. |
| RN_Soviet_Probes | 27 | **23** | Reverse 15 whole probes + integral sub-parts (Luna 2/3/10/11/13, Venera 1, Molniya-1, Polyot, Proton 1-4 sats, Strela bus + astro/radio/vernier). Inherit 4 redundant cuts: `molniya_asas` (deprecated), 2 RCS blocks (Venera/Strela → generic), 1 payload decoupler. Corrects RP-1's US-centric bias (kept only 8/27). |
| CoatlAerospace | 123 | **74** | Inherit RP-1's 49 cuts: all **29 dedicated instruments** (redundant with RP-1's RO-* set, per Science section) + 8 solar panels + 4 batteries + 2 tanks + RCS/misc. Keep the **hardware** (buses, antennas, RTGs, reaction wheels, EDL aeroshells). Optional adds flagged: SSTL-150 bus, STAR-24C motor. |

## Next
- Continue mod-by-mod **hardware** curation: Tantares, NearFuture suite, US2, SSPX, SXT/VenStock, the rest.
