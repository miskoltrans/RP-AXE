# Part entry costs (M3 Pass D reference)

> ⚠️ **SUPERSEDED / HISTORICAL (see DECISIONS D8, 2026-06-26).** RP-AXE **abandoned the part-entryCost
> funds sink**: parts now unlock **free** with science (`design/EntryCosts/ZeroEntryCost.cfg` +
> `Source/AXE/FreePartUnlock.cs`). The only buy-to-unlock kept is **RealFuels engine-config** charging;
> the only ongoing funds sink is **launch cost**. This document is retained as a record of the
> approach that was tried and dropped — do **not** treat it as current intent or reintroduce per-part
> entryCosts.

Rebuild a real **funds sink**: most RO/RP-1 part `entryCost` values are `1` because RP-1 put funds
pressure in its plugin (tooling/maintenance), which we removed. Pluginless, we set flat `entryCost`
directly via ModuleManager — exactly how **LRTR** does it.

> Balance note (invariant): the dominant RSS funds drain is **per-launch vehicle cost**, not entry
> cost. Tune contract income (M3 Pass C, see `PROGRAMS.md`) so each era's income comfortably covers
> that era's vehicle costs; entry cost is a one-time unlock tax on top.

## Two sources

### 1. LRTR `tree/parts/*.cfg` — lift per-part `entryCost` values (primary)
`C:\git\ksp\LRTR\GameData\LRTR\tree\parts\` patches external mods' parts pluginless:
```
@PART[B9_Aero_Wing_Procedural_TypeA]:FOR[zLRTR]:NEEDS[LRTRTechTree]
{
    %TechRequired = supersonicDev
    %entryCost   = 10000
}
```
**For Pass D we lift `%entryCost` only** (it's just funds — tree-independent). We do **not** take
`%TechRequired`: LRTR's node ids (e.g. `supersonicDev`, `matureSupersonic`) are LRTR's tree, not our
RP-1-derived tree. Part placement is **Pass F** (and RP-1 already places its covered parts).

Adaptation when porting into `design/EntryCosts/`: drop `:NEEDS[LRTRTechTree]`, retag `:FOR[RP-AXE]`
(or `:AFTER[RealismOverhaul]`), keep `%entryCost`, drop `%TechRequired`.

**Coverage (entryCost patch counts per mod):**

| Tier | Mods (LRTR entryCost counts) |
|---|---|
| Core / proc | RealFuels(4), ProceduralParts(8), ProceduralFairings(15), ReStockPlus(124), Squad(356), SquadExpansion/Making_History(69), Breaking_Ground(52) |
| Near-future (user wants these) | NFLaunchVehicles(78), NFExploration(69), NFPropulsion(57), NFConstruction(49), NFSpacecraft(39), NFSolar(33), NFAeronautics(31), NFElectrical(20) |
| Far-future / advanced | FarFutureTechnologies(46), CryoTanks(15), SystemHeat(3), DeepFreeze(5), htRobotics(6), WildBlueIndustries(7), SpaceDust(5) |
| Part packs | Bluedog_DB(968), Tantares(336)+LV(128)+SP(94), FASA(200), reDIRECT(44), ORANGES(33), CNAR(12), Benjee10 shuttle(22) |
| Misc | ModularLaunchPads(185), SCANsat(20), KerbalismConfig(28), MechJeb2(6), CryoEngines, B9 PWings, PlumeParty(5) |

~40 mods priced. (Whether we ship a given mod is the DEPENDENCIES decision; price only what we ship.)

### 2. `seed/Tree/EntryCostModifiers.cfg` — RO capability pricing guide (sanity / fill gaps)
264 capability→price entries RP-1's plugin used to *compute* engine/tank entry cost. Pluginless it's
inert, but it's the authoritative **pricing guide** for hand-setting RO core engine/tank `entryCost`
where LRTR's value is missing or feels off. Samples:
`HydroloxProp 50k`, `MethaloxProp 50k`, `StagedCombustion 40k`, `StagedHydrolox 100k`,
`StagedFullFlow 150k`, `SolidsAluminum 50k`, `SolidsTVC 100k`, `NTOOxidizer 5k`.
Use it to keep capability jumps meaningful (e.g. a staged-combustion hydrolox engine should cost
noticeably more than a pressure-fed kerolox one).

## Pass D plan
1. Decide the shipped part set (DEPENDENCIES.md) — only price what ships.
2. Port LRTR `tree/parts` `%entryCost` for those mods into `design/EntryCosts/<Mod>.cfg`
   (strip `LRTRTechTree` NEEDS, retag, entryCost only).
3. Hand-price RO core engines/tanks/capsules not covered by LRTR, using EntryCostModifiers as the
   guide (tier by capability).
4. Leave a sensible default so un-priced parts aren't free: e.g.
   `@PART:HAS[#TechRequired[*],~entryCost[]]:AFTER[RP-AXE] { %entryCost = <small default> }` — or
   a category-based default pass.
5. Validate in-game with funds on: early parts affordable, capability jumps felt, no `entryCost = 1`
   leftovers on shipped parts.

Depends on M2 (contracts/funds working) before balance can be judged.
