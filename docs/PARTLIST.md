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

## Next
- Understand RP-1's decisions on the **expanded candidate packs** (what it cuts from Tantares / NearFuture
  / probes / Coatl / etc., and why) → feeds the ahistorical/future curation.
