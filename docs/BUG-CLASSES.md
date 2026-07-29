# RP-AXE — Bug Classes

What keeps breaking, why it keeps breaking, and the detector for each. Written 2026-07-29 from a
sweep of the 608-commit history plus a fresh hunt against the live instance.

The point of this document is not the list of past bugs — it is that **almost every bug this
project has shipped belongs to one of three families**, and each family has a mechanical detector.
Anything found by eye that a detector could have found is a gap in the detectors, not bad luck.

---

## The three families

### A. Silent binding failure — a string that resolves to nothing

The dominant family. RP-AXE is a total conversion assembled out of ModuleManager patches, and
essentially every cross-reference in that system is an **unvalidated string**: a tech-node id, a
part name, a PartModule type name, a top-level config-node name. When the string names something
that does not exist, ModuleManager merges the patch anyway, KSP loads it anyway, and **nothing
logs**. The failure is an *absence* — a node that grants no part, an experiment that never runs,
a setting that reverts to stock — and absences are invisible until someone plays far enough to
look for the thing that is missing.

This family is worse in AXE than in a normal mod for a structural reason: **AXE deleted RP-1's
tech tree.** Every one of the ~400 RP-1 node ids is now a dangling reference somewhere, and they
are scattered across vendored `seed/` configs *and* third-party mod files that RP-1 used to
satisfy. The re-homing overlays in `design/` are what keep them alive, so any gap in an overlay
is a silent break.

| Sub-class | How it bites | Past instances | Detector |
|---|---|---|---|
| **A1** Config node with no reader | A top-level `NODE {}` does nothing unless some DLL calls `GetConfigNodes("NODE")`. RP-1's readers live in `RP0.dll`, which AXE does not ship. | `GAMEPARAMETERS` (dead until `9cb4afe`/`dc5b7a7`); `IGNORED_EXPERIMENTS`; `AVIONICSCONFIGS` | `check_liveness.py` check C |
| **A2** Part module with no class | `MODULE { name = X }` where no assembly defines `X`. KSP drops the module and logs one line among thousands. Anything keyed on it — a Kerbalism `requirements = Module:X`, a contract `PartValidation` — can then never match. | the 16 `*LabExperimentPackage` markers (**open**, see below) | `check_liveness.py` check B |
| **A3** Dangling tech-node id | Fails **closed**: `GetTechnologyState(unknown)` → `Unavailable`, so the gated thing is locked forever. | `autoStrutTechRequired = generalConstruction` (`4708e6c`); 4 orphaned stock/CTT ids (`c3e6620`); HDD-Upgrade gates (`1d0f3db`); US2 wedge `Configure` gates (`1d5472c`); 702 RCS engine CONFIGs (**open**) | `check_tech_refs.py --cache` |
| **A4** Placed part that isn't there | The tree places a part that another AXE config deletes, that a missing mod owns, or that fails to compile. The node still costs science and grants nothing. | `ca_GRS`, the 5 `dmUS2*` wedges (**open**) | `check_liveness.py` check A |
| **A5** Global setting that reverts to stock | RP-1 was the *only* source of a CustomBarnKit section or difficulty key; dropping RP-1 resurrected the stock value nobody chose. | the 7-item punch-list (`5c12181`, `4708e6c`, `25e2b80`, `7e3b58f`); 17 more found 2026-07-29 | `check_settings_parity.py` |

### B. Semantic misread — the API does not mean what the field name says

Second family, much smaller in count but expensive per instance, because the wrong belief gets
built on: a balance pass, a shipped price curve, a plugin predicate.

| Instance | The misread | Corrected by |
|---|---|---|
| CustomBarnKit `upgrades[0]` | Read as the first price. KSP charges `upgradeLevels[level+1]`, so slot 0 is **never charged**; every step was one slot off (~4× on R&D). | `0263d36` |
| `STRATEGY requiredReputationMin/Max` | Read as an availability window. It is a **lerp over the commitment slider** — widening it to ±1e6 made full commitment cost a million rep and halved Channel 2. | `883508d`, then `fc0d025` (delete the override) |
| `PartModelPurchased` / `PartTechAvailable` | Read as "consults `protoTechNodes`". Both fall through to `experimentalPartsStock`, so marking a part experimental makes stock call it *purchased* — a self-destructing predicate. | `41122cd` |
| Kerbalism `baseValue` | Read as the payout. Kerbalism pays `scienceCap × situationMultiplier`; `baseValue` only sizes the data stream. Invalidated a whole lab balance pass. | `babd387`, `fffa2d0` |
| `CONTRACT_TYPE rewardFunds` | Read as what the player receives. Stock multiplies by prestige (1/1.25/1.5) × the difficulty gain multiplier — ×1.529 on funds. | `cef220c`, `ecc8e41` |
| `GameEvents.*.Add(staticMethod)` | Assumed legal. `EvtDelegate..ctor` derefs `evt.Target` with no null guard → deterministic boot NRE. | `9010107` |
| `DifficultyPresetChanger` at MainMenu | Assumed sufficient. `MainMenu.Start` caches `GetDefaultParameters` in the same scene load and wins the race. | `dc5b7a7` |

**The rule that would have prevented all seven: decompile, don't infer.** `ilspycmd` is installed
globally; a stock-semantics question is one command and about a minute:

```
ilspycmd -t <Namespace.Type> Instance/KSP_x64_Data/Managed/Assembly-CSharp.dll
```

There is no detector for this family. There is a **trigger**: any time a claim about the economy,
the science budget, or an unlock rule rests on what a config field *appears* to say, read the
consumer's code before building on it.

### C. Verification failure — the check that could not have caught it

The reason a bug in family A or B survives long enough to reach playtesting.

| Instance | Why the check was worthless |
|---|---|
| `check_tech_refs.py` "EXTERNAL MODS" bucket | Classified by **file provenance**. The 702 dangling RCS configs are written in Coatl/ROEngines files, so they were filed as somebody else's problem — printed on every run, exit 0. But AXE is what deleted the node; the ids are AXE's to re-home. *Fixed 2026-07-29: in `--cache` mode nothing is external.* |
| Engine-config gate layer 2 | Its own docstring says it covers "~123/126 of the RP-1 nodes the walker uses" and it never logs the other 3. A bounded pass that does not report what it dropped reads as complete coverage. |
| The `-axe-autotest` difficulty check | Seeded its career from `GetDefaultParameters(Normal)`, which was the *exact* thing that was broken. Written off as a harness limitation; it was the bug. |
| The `RSSRP1` save that "proved" `GAMEPARAMETERS` worked | Made in `ksp_rp1_clean`, where RP-1's own plugin was doing the work. **A save from an RP-1 instance can never prove an AXE mechanism.** |
| Contract Configurator's `Loaded N out of N` | CC reads the pre-patch database on the run that regenerates the MM cache: 338/338 is printed while 34 new types are silently missing. Always validate on a **second** run. |
| Hand-authored test fixtures (FTO) | Inputs built from the mental model under test can only confirm it. Sprang three times. |

**Rules, in order of how often they would have helped:**
1. Prove it against the **merged `ModuleManager.ConfigCache`** and the **save the game actually
   wrote**, never against the repo, the log line, or another instance's save.
2. Any bounded pass must `log()` what it dropped. Silent truncation reads as coverage.
3. A gate that reports and exits 0 is documentation, not a gate.
4. New `CONTRACT_TYPE` configs need two runs before a verdict.

---

## Detectors

| Tool | Covers | Needs |
|---|---|---|
| `tools/check_liveness.py` | A1, A2, A4 + A3 (folds in `check_tech_refs --cache`) | a booted instance (`ConfigCache` + `KSP.log`) |
| `tools/check_tech_refs.py --cache <ConfigCache>` | A3 alone, with fuller output | a booted instance |
| `tools/check_settings_parity.py` | A5 | RP-1 checked out; a cache sharpens it |
| `tools/check_forks.py`, `check_ladder_collapse` (in `build_tree.py`) | tree-design invariants | repo only |
| `tools/check_nonreentry.py` | reentry-rating coverage | repo only |

`rebuild-instance.ps1` step 6 boots the instance with `-axe-autotest` and runs `check_liveness.py`
+ `check_settings_parity.py` against the cache that boot produced, so a rebuild that reaches the
end is a rebuild somebody checked. `-NoVerify` opts out and says so loudly.

`check_liveness.py` opens with a **staleness check**: if the merged cache predates any shipped
`.cfg`/`.dll`, it refuses to answer rather than describing the previous boot. That check is
deliberately judged on the cache's mtime and never the log's — a running KSP writes to the log
continuously, so a log-based check calls every stale verdict fresh. It is check 0 because without
it every other verdict in the file is a family-C failure.

`check_settings_parity.py` carries a checked-in **disposition table**: every RP-1 settings key AXE
does not match must be recorded as CUT / STOCK-deliberate / DEFERRED / OPEN, with a reason. A
settled decision stays quiet; an undispositioned one fails the gate. That is what makes it survive
an RP-1 update — new keys arrive undispositioned instead of silently joining the noise. It also
compares **values against the live cache**, so a key RO supplies anyway is not reported at all.

---

## Open findings (2026-07-29 hunt)

Severity is "what a playtester hits", not "how wrong the config looks".

### 1. Every hypergolic RCS propellant is permanently locked — A3 · **high**

702 RealFuels engine `CONFIG` blocks across **82 parts (66 of them placed in the tree)** still
carry RP-1 tech ids that AXE deleted:

- `techRequired = earlyDocking` ×468 — MMH+NTO, MMH+MON3, MMH+MON10, UDMH+NTO, Aerozine50+NTO, Cavea-B
- `techRequired = reusableControl` ×234 — CH4+O2, H2+O2, ASCENT
- `techRequired = orbitalRocketry1962` ×4 / `orbitalRocketry1965` ×2 — LR101, LR105, LR89 uprates

`EngineConfigTechLevels.CanConfig()` returns true only for `GetTechnologyState(tech) == Available`,
and an unknown id returns `Unavailable`, so these can never be selected — and AXE's own
`AxeEngineConfigPurchaseGate` correctly refuses the switch, with a null tech title. Net effect:
**the standard spacecraft-RCS propellants of the entire Apollo/Soyuz era do not exist in AXE.**
Only HTP, hydrazine monoprop, N2O, cold gas, and the kerolox/ethanol families are reachable.

Root cause is in `build_tree.py::emit_engine_config_gates`: the layer-2 catch-all key set `r2a`
is built only from the *residual* `pairs`, so an RP-1 node whose only carriers are curated parts
(all of which layer 0 already re-homed) never gets a catch-all row — and the 66 uncurated RCS
parts keep the dead value. The intent is unambiguous and already written down for the curated
parts: `earlyDocking → pc_storableRcsPropellants` / `pc_caveaB`.

Fix: derive the catch-all key set from **every** RP-1 node the walker touches, not just the
residual, and hard-fail the build when an RP-1 node has no catch-all target.

### 2. The whole KerbalismLab science suite is uncollectable — A2 · **high**

`design/Science/KerbalismLab/InstrumentTagging.cfg` tags parts with 16 `*LabExperimentPackage`
marker modules. Those classes live in the upstream fork's own assembly
(`KerbalismLabExperimentsExpandedContinued/src/LabExperimentPackage.cs`), which **AXE does not
ship**. KSP logs one `Cannot find a PartModule of typename` error per tagged part — 57 of the
current log's 154 — and drops every tag.

`ExperimentRequirements` evaluates `Require.Module` as
`Lib.FindModules(v.protoVessel, name).Count > 0`, so **60 of the 65 lab experiments can never
run** — 58 via `Module:<pkg>`, plus two that name a *module* in a *part-name* requirement
(`SLAC-LCLS.cfg:30` and `SOLAR-WISPR.cfg:30` say `Part:RadioLabExperimentPackage` /
`Part:VisualLabExperimentPackage`, both upstream defects inherited verbatim and unsatisfiable
either way). That includes every experiment the 2026-07-28 balance pass tuned.

Fix options: (a) define the 16 markers as empty `PartModule`s in AXE.dll — cheapest, mirrors
`ModuleAxeMarker`, and `InstrumentTagging.cfg`'s re-pointing work then starts mattering;
(b) rewrite the requirements onto something AXE already has.

**(a) is a complete fix for the module half — checked, not assumed.** All 16 packages resolve to
at least one live host part in the merged cache: 14 by explicit name, `Materials`/`Biology` via
their `experiment_id` HAS-filters (10 hosts each), and `Drill` via `@PART[*Drill*]`, which matches
`kerbalism-drill` and `kerbalism-large-drill` because ModuleManager's name wildcards are
case-insensitive. The two `Part:`-instead-of-`Module:` experiments need their own two-line fix and
are unaffected by (a).

### 3. Four tree nodes grant nothing — A4 · **medium**

| Node | Title | Missing part | Why |
|---|---|---|---|
| `mic_boomMagnetometry` | Boom-Deployed Magnetometry | `dmUS2MagBoom` | **not in the curated manifest** — the part belongs to DMagic Orbital Science, which AXE does not install |
| `opt_precisionOptics` | Precision Orbital Optics | `dmUS2Scope` | ” |
| `opt_multiSpectralImaging` | Multi-Spectral Imaging | `dmUS2ImagingPlatform` | ” |
| `coatl_scienceSandbox` | Gamma-Ray Spectrometer (Sandbox) | `ca_GRS` | **AXE deletes it itself** — `seed/Science/CleanupParts/RemoveScienceParts.cfg:23` |

Three more nodes are thinned rather than emptied: `opt_irRadiometry` (`dmUS2GoreSat`),
`mic_plasmaWave` (`dmUS2RPWS`), `elec_deployablePanelII` (`aje_solarPanels`, which fails to
compile because Restock replaced the stock `radialFlatSolarPanel` model it clones).

**Do not confuse the two US2 sets.** RP-1's `Parts/Science/US2.cfg` `@`-patches ten parts it does
not create: five `US*Wedge` from **UniversalStorage2** and five `dmUS2*` from **DMagic Orbital
Science**. The `US*Wedge` five are curated, installed, live, placed, and AXE owns their Kerbalism
`Configure` gates in `design/Science/US2.cfg` (commit `1d5472c`) — that work is **done**. Only the
`dmUS2*` five are absent, and their mod was never in the manifest, so nothing was "not ported":
five parts were placed in the tree that the curated part list never contained.

Which is its own finding: **nothing checks that a placed part is in `manifest/curated-parts.tsv`.**
`build_tree.py` validates plenty about placement but not membership, so a part name that entered
`nodes.yaml` from a partlist extraction rather than the manifest is never questioned.

`coatl_scienceSandbox` is the other flavour of the same thing: a self-contradiction entirely
inside AXE, placing and deleting the same part in the same shipped mod.

### 4. Three parts fail to compile — A4 · **low**

`B10_APASv2` (clones a Bluedog_DB model that is not installed), `aje_solarPanels` (see above),
`RO-Castor30B` (`ConfigNode.ParseVector3` — a malformed vector in the RO config). Only
`aje_solarPanels` is placed. `ca_hera` also fails to clone its model but still compiles.

### 5. Two inert vendored config nodes — A1 · **low**

`IGNORED_EXPERIMENTS` (known; RP-1 reads it in `RP0/Singletons/Database.cs` to pre-complete
body/experiment/situation combos — in AXE they stay collectible, mostly overlapped by
`EarthScienceRemoval.cfg`) and `AVIONICSCONFIGS` in `seed/Parts/_RP-AXE-extra/ProceduralAvionics.cfg`,
which is dead weight now that `proceduralAvionics` carries `ModuleAxeAvionics`.

### 6. Seventeen settings AXE never re-authored — A5 · **medium**

`check_settings_parity.py` diffs RP-1's 1,954 settings keys against AXE's 478 and reports only
where the **live merged value** actually differs. 1,564 are settled decisions (RP-1's
SpaceCenterManagement economy, crew progression, KCT, Programs — all cut on purpose). 17 are not:

**EVA rides on the Astronaut Complex, not on the crew system.** Cutting crew progression handed
these to stock without anyone choosing them:

| key | live | RP-1 | consequence |
|---|---|---|---|
| `ASTRONAUTS/unlockedEVA` | 2 | 4 | EVA needs Astronaut Complex L2 — a **75,000-fund** upgrade AXE never designed |
| `ASTRONAUTS/homebodyAtmoEVA` | false | true | no EVA inside Earth's atmosphere at all |
| `ASTRONAUTS/unlockedEVAChute` | 3 | 1 | EVA chutes only at a maxed Astronaut Complex |
| `ASTRONAUTS/unlockedEVAClamber`, `unlockedEVAFlags` | 3, 2 | 5, 5 | ride along |

AXE ships EVA science, an EVA flight log and crewed contracts, so this is the same shape as the
autostrut and on-orbit-fuel-transfer items from the original punch-list.

**Two reputation faucets nobody modelled:** `MISSION/reputationKerbalRecovery` is live at **25 per
kerbal** × `RepGainMultiplier` on every recovered crewed vessel, against RP-1's 1 — and
`tools/rep_budget.py` does not model it. It does not convert to funds directly, but reputation is
what the strategy commitment slider is measured against, so it still moves Channel 2.
`reputationKerbalDeath` is live at 10 against RP-1's 200: killing a crew is nearly free.

**Five kerbal G-tolerance keys** (`PHYSICSGLOBALS/kerbalGThresholdLOC` 60000 vs RP-1's 90000, plus
Warn/Offset/BadMult/BraveMult) are at stock. The earlier audit cleared "G/pressure **part** limits"
as intact — these are the **kerbal** limits, a different set, never checked.

**Five KSPCommunityFixes patches** RP-1 turns on and AXE leaves at the mod's default `false`. Two
are more relevant here than in RP-1: `PartTooltipUpgradesApplyToSubstituteParts` (AXE ships 603
PARTUPGRADEs) and `StrategyDuration` (AXE uses stock strategies as a funds channel). The other
three — `OnSymmetryFieldChanged`, `FewerSaves`, `DisableNewGameIntro` — are QoL.

### 7. NOT A BUG CLASS — "a node that grants no NEW capability", investigated and dropped

Proposed 2026-07-29 and **abandoned the same day, on evidence.** Recorded so nobody re-proposes it.

The premise came from one instance: `mic_atmoSounding` granted a part whose two experiments were
already available at `start`. Generalising to "find all nodes like this" felt obvious. The
enumeration below was built to test the generalisation, and it came back essentially negative — so
the enumeration *is* the deliverable, and the detector was never worth building.

**What the population actually turned out to be:**

- **Declared form-factor variants: 2 install-wide.** `identicalParts` is an RP-1 convention used
  almost only in `US2.cfg`; both surviving declarations sit on the *same node* as their twin, so
  they read as deliberate. And a wedge that mounts in a US2 service module is real value even when
  the experiment is not new — that is a design choice, not a defect (user call).
- **De-facto duplicates: dominated by VEHICLES, not instruments.** After filtering the 44
  near-universal experiments, what remains is 9 lab modules sharing an identical 72-experiment set,
  11 cockpits sharing 4 supersonic experiments, probe buses, station habitats. Those are not
  variants of an instrument; they are complete craft whose science comes with the craft.
- **Genuinely hollow nodes: one, already fixed.**

**Why the correctness half needs no new gate:** the dangerous version of "a node grants nothing" is
*its parts do not exist*, and `check_liveness.py` check A already gates exactly that — it found four
and now finds zero. What was left over is "the parts exist but add nothing new", which is a
**design** question (is a form factor worth a node?), not a correctness one. A detector cannot answer
it, and the audit had been treating it as a bug class only because it sat next to real ones.

A "sole-source experiment" variant was floated as a salvage — find where science is thin rather than
duplicated — and does not survive either: 17 experiments have one placed source, but one instrument
per measurement is normal design, and the one odd row (`_WasteProcessor` only on `USWaterPurifier`
in the sandbox) is reachable and functionally covered by `_WaterRecycler`, which is on 14 parts.

Two passes, cheapest first.

**Pass 1 — the `identicalParts` sweep (nearly free, zero false positives).** RO/RP-1 already declare
which parts are the same instrument in a different mounting: `%identicalParts = RO-IonMassSpectrometer`
on `USFluidSpectroWedge`, `= BioCapsule` on `USGooBayWedge`, and so on. It is an *authored* claim, so
acting on it is not inference. Flag any node whose parts are all `identicalParts` twins of parts
already reachable from its ancestors.

**Pass 2 — experiment reachability over the DAG.** For each node N, compute the `experiment_id`s it
introduces versus those reachable from N's ancestors, and report:

- **STRICT hollow** — nothing new versus N's own ancestors. Guaranteed dead: every prerequisite of N
  already gave the player everything N grants.
- **LOOSE redundant** — nothing new versus every node at or below N's tier. Probably dead, but a
  player on a different branch might reach N first, so this is a design question, not a defect.

The unit must be the **(part, SETUP) pair with its own `tech =` gate**, not the part: a Kerbalism
`Configure` SETUP carries its own gate, so a part placed at node N routinely holds experiments that
unlock at other nodes — which is exactly why reading part placement alone missed this for so long.

Scope it to nodes that grant at least one experiment-carrying part. A node granting a fuel tank is
not hollow for granting no science. And be clear about the limit: this answers "is it new", never
"is it interesting".

### 8. Known-and-accepted, re-confirmed

- 14 `PARTUPGRADE`s still strand on the `parking` catch-all, including `RFUpgrade_30x_NK-33`,
  `RFUpgrade_8x_NK-43`, `RFUpgrade_RD-0108`.
- `RP0LiquidsMicrogravity` has `baseValue = 16` / `scienceCap = 8`, so it pays 8. Inherited
  verbatim from RP-1 — flagged only because any budget line that reads 16 is wrong.
- The tracking-station ladder is copied verbatim from RP-1 and does **not** carry the
  `upgrades[0]`-is-dead note that `AxeFacilities.cfg` carries. `docs/ECONOMY.md` already accounts
  for it correctly ("11 levels, 10 purchases", 2.53M); the comment is what is missing.
