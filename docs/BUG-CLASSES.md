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
| **A1** Config node with no reader | A top-level `NODE {}` does nothing unless some DLL calls `GetConfigNodes("NODE")`. RP-1's readers live in `RP0.dll`, which AXE does not ship. | `GAMEPARAMETERS` (dead until `9cb4afe`/`dc5b7a7`); `IGNORED_EXPERIMENTS` (deleted); `AVIONICSCONFIGS` (kept, allow-listed) | `check_liveness.py` check C |
| **A2** Part module with no class | `MODULE { name = X }` where no assembly defines `X`. KSP drops the module and logs one line among thousands. Anything keyed on it — a Kerbalism `requirements = Module:X`, a contract `PartValidation` — can then never match. | the 16 `*LabExperimentPackage` markers (`30c75ae`) | `check_liveness.py` check B |
| **A3** Dangling tech-node id | Fails **closed**: `GetTechnologyState(unknown)` → `Unavailable`, so the gated thing is locked forever. | `autoStrutTechRequired = generalConstruction` (`4708e6c`); 4 orphaned stock/CTT ids (`c3e6620`); HDD-Upgrade gates (`1d0f3db`); US2 wedge `Configure` gates (`1d5472c`); 702 RCS engine CONFIGs (`3d16480`) | `check_tech_refs.py --cache` |
| **A4** Placed part that isn't there | The tree places a part that another AXE config deletes, that a missing mod owns, or that fails to compile. The node still costs science and grants nothing. | `ca_GRS`, the 5 `dmUS2*` wedges (`93b9725`, `1bd9aeb`); `aje_solarPanels` (`AxeUpstreamPartFixes.cfg`) | `check_liveness.py` check A |
| **A5** Global setting that reverts to stock | RP-1 was the *only* source of a CustomBarnKit section or difficulty key; dropping RP-1 resurrected the stock value nobody chose. | the 7-item punch-list (`5c12181`, `4708e6c`, `25e2b80`, `7e3b58f`); 17 more found + decided 2026-07-29 | `check_settings_parity.py` |

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
| CBK `unlockedEVAChute` | Read as a facility level, like the four keys it sits next to. CBK only treats it as one when `EVAChuteOnBuilding = true` — false everywhere in this install — and otherwise tests raw crew **XP**. "EVA chutes at a maxed Astronaut Complex" was never true. | the settings pass, 2026-07-29 |
| `GameVariables.GetCrewLevelLimit` | Assumed enforced, and written off as harmless collateral of cutting crew progression. It has **two** references in all of Assembly-CSharp: its own definition and `KSCFacilityLevelText` — the upgrade **tooltip**. It caps nothing. | the settings pass, 2026-07-29 |

The last two are worth more than their severity: both wrong beliefs were **written down in `check_settings_parity.py`'s own disposition table**, i.e. in the detector. A disposition is a claim like any other, and "we looked at this" is not the same as "we read the consumer". Decompiling five keys took about ten minutes and overturned two of them.

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

## Findings (2026-07-29 hunt) — all closed

Severity is "what a playtester hits", not "how wrong the config looks". **Every finding below is
now fixed**; the entries stay as the reasoning trail, each with what closed it. Findings 1-3 were
fixed within hours of the hunt; 4-6 in the follow-up settings pass the same day.

| # | Finding | Severity | Closed by |
|---|---|---|---|
| 1 | Every hypergolic RCS propellant permanently locked | high | `3d16480` |
| 2 | The whole KerbalismLab science suite uncollectable | high | `30c75ae` |
| 3 | Four tree nodes grant nothing | medium | `93b9725`, `1bd9aeb` (+ a membership gate in `build_tree.py`) |
| 4 | Three parts fail to compile | low | `design/Parts/AxeUpstreamPartFixes.cfg` |
| 5 | Two inert vendored config nodes | low | one deleted, one allow-listed |
| 6 | Seventeen settings AXE never re-authored | medium | 4 configs + 13 recorded decisions |

### 1. Every hypergolic RCS propellant is permanently locked — A3 · **high** · ✅ FIXED `3d16480`

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

### 2. The whole KerbalismLab science suite is uncollectable — A2 · **high** · ✅ FIXED `30c75ae`

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

### 3. Four tree nodes grant nothing — A4 · **medium** · ✅ FIXED `93b9725`, `1bd9aeb`

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

### 4. Three parts fail to compile — A4 · **low** · ✅ FIXED

All three are **upstream** defects, in mods AXE only consumes. All three are now corrected by
minimal overrides in `design/Parts/AxeUpstreamPartFixes.cfg`, each carrying the provenance line
that says when to drop it. (`ca_hera` also fails to clone its model but still compiles — untouched.)

| Part | The upstream defect | Fix |
|---|---|---|
| `aje_solarPanels` | AJE clones `solarPanels5` and hardcodes `Squad/…/radialFlatSolarPanel/model` — a folder **ReStock blacklists**, so the mesh is not in the asset DB. ReStock re-points the original but not the clone. | Point it at ReStock's own `restock-solarpanel-static-small`, a dimensional drop-in, keeping AJE's 4.47× scale. |
| `RO-Castor30B` | `RO_Restock_Engines_SRB.cfg:94` writes `%scale = 1.1482. 1, 1.1482` — **a period where the first comma belongs**. `ParseVector3` throws `FormatException`. | Restate the vector. |
| `B10_APASv2` | ROCapsules guards it with `NEEDS[!Benjee10_sharedAssets]` but its MODEL points into `Bluedog_DB`. **The guard names the wrong mod**, so without BDB it can never compile. | `!PART[B10_APASv2]:NEEDS[!Bluedog_DB]` — what the guard was trying to say. |

Only `aje_solarPanels` was placed, and it is not redundant: same panel at 4.47× the area and 4× the
charge rate, sitting at `elec_deployablePanelII` next to the `solarPanels5` it clones.

### 5. Two inert vendored config nodes — A1 · **low** · ✅ RESOLVED

Split, because the two are not the same case:

- **`IGNORED_EXPERIMENTS` — deleted.** RP-1 reads it in `RP0/Singletons/Database.cs` to
  pre-complete body/experiment/situation combos; AXE ships no reader, so 280 lines looked authored
  and did nothing. AXE's equivalent intent already lives in `design/Science/EarthScienceRemoval.cfg`,
  which zeroes the situations rather than pre-completing them. Removed via **`sync-seed.ps1`'s
  `$designOwned` strip list**, not by hand — `seed/` is a wholesale re-vendor, so a hand deletion
  would have come straight back on the next sync.
- **`AVIONICSCONFIGS` — kept, and now allow-listed.** It is the implementation reference the
  avionics port is checked against (`UPGRADES.md` §C1, `AVIONICS_COMPARISON.md`). Deleting it would
  need a *partial-file* strip — the block is 893 lines inside a file whose other stanzas are live —
  which is not worth building for one dead node.

The mechanism matters more than either: **check C had no disposition table**, so it failed the gate
on two known-and-accepted items forever. `rebuild-instance.ps1` step 6 runs `check_liveness.py`, so
that was a permanent red light, which is the fastest way to teach everyone to ignore a gate. It now
carries `INERT_BY_DESIGN`, the same contract as check A's `INTENTIONALLY_EMPTY` and
`check_settings_parity`'s `DISPOSITIONS`: a listed node prints as `kept` with its reason, anything
unlisted still fails.

### 6. Seventeen settings AXE never re-authored — A5 · **medium**

`check_settings_parity.py` diffs RP-1's 1,954 settings keys against AXE's 478 and reports only
where the **live merged value** actually differs. 1,564 are settled decisions (RP-1's
SpaceCenterManagement economy, crew progression, KCT, Programs — all cut on purpose). 17 are not:

**All 17 are now decided** (user calls, 2026-07-29). Four things changed; the rest are recorded as
deliberate in `DISPOSITIONS`. The gate reports **0 OPEN, 0 undispositioned**.

**EVA rides on the Astronaut Complex, not on the crew system.** Cutting crew progression handed
these to stock without anyone choosing them. Decompiling first was worth it — three of the five keys
do not mean what their names suggest, and RP-1's numbers are not comparable to stock's because the
two ladders are different lengths (`normLevel > (value − 1.1)/(levels − 1)`).

| key | live | RP-1 | what it actually does | outcome |
|---|---|---|---|---|
| `homebodyAtmoEVA` | false | true | **the one that mattered.** `EVAIsPossible` falls back to `v.LandedOrSplashed` when false — so no LEO spacewalk and no orbital EVA science without the facility. True makes EVA free anywhere in Earth's SOI. | **→ true** |
| `unlockedEVAChute` | 3 | 1 | **not a facility level.** `EVAChuteOnBuilding` is false, so CBK tests raw crew **XP ≥ 3** (xpPerLevel is 2/8/16/32/64). | **→ 1** |
| `unlockedEVA` | 2 | 4 | L2 = 75,000 here; RP-1's 4 is L4 on a 5-level ladder = **480,000**. AXE is already 6× cheaper. | kept — the beyond-Earth gate |
| `unlockedEVAClamber` | 3 | 5 | 3-of-3 == 5-of-5. Both put it at the **top** level; no divergence in fact. | kept |
| `unlockedEVAFlags` | 2 | 5 | L2 vs RP-1's top level — AXE is the more permissive, and flags are cosmetic. | kept |

Net: **EVA in Earth's SOI now costs nothing**, and the 75,000 upgrade gates only EVA beyond Earth —
RP-1's shape at an eighth of RP-1's price. Shipped as `@ASTRONAUTS` in `AxeFacilities.cfg`.

**Two neighbours in the same block, checked while we were there — one inert, one already fine:**
`crewLevelLimit = 1, 3, -1` is **never enforced** (see family B), which is what closes the
KerbalismLab crew-star question in `KERBALISMLAB.md`: `Scientist:4+` is reachable at any Astronaut
Complex level, so those 36 experiments are a progression curve, not dead content. `activeCrewLimit =
5, 12, -1` *is* enforced (on hiring) — but RP-1's own first rung is **4**, so stock is the more
generous of the two and there was nothing to fix.

**Two reputation faucets nobody modelled — kept, deliberately.**
`MISSION/reputationKerbalRecovery` is live at 25/kerbal × `RepGainMultiplier` = **+30 on Normal** for
every recovered crew member, against RP-1's 1; `reputationKerbalDeath` is 10 × `RepLossMultiplier` =
**−7.5**, against RP-1's 200 (= −150). So recovering a crew pays 4× what killing one costs. Kept
anyway: AXE has no crew system for a loss to propagate through, so a heavy penalty would be purely
punitive. **Known gap it leaves:** `tools/rep_budget.py` models neither, so Channel 2's ceiling is
understated by roughly 30 × (crew recovered).

**Five kerbal G-tolerance keys** were at stock. The earlier audit cleared "G/pressure **part** limits"
as intact — these are the **kerbal** limits, a different set, never checked. All five now take RP-1's
values in `design/Settings/AxeCrewPhysics.cfg`. The dial that decides it: accumulation floor
`kerbalGOffset^0.25` rises 5.48 g → 6.50 g and LOC rises 60,000 → 90,000, so a sustained 8 g blacks a
kerbal out at **39 s instead of 19 s** — a ballistic Soyuz reentry becomes survivable, which it was
in reality. **The trait modifiers had to come too:** `GeeForceTolerance(level)` multiplies both the
floor and the threshold, and stock's 2.0× veteran pilot would have eaten most of the change. RP-1
flattens all three traits; so do we. That table is `EXPERIENCE_TRAIT`, which **this gate was not even
scanning** — added to `SETTINGS_NODES`, coarsely (the walker strips `[index]`, so all three traits
collapse to one path: it detects "never re-authored", not "re-authored one of three").

**Five KSPCommunityFixes patches** RP-1 turns on and AXE left at the mod's default `false`. Four
taken in `design/Settings/AxeCommunityFixes.cfg`: `PartTooltipUpgradesApplyToSubstituteParts` (AXE
ships 603 PARTUPGRADEs, so this matters more here than in RP-1), `OnSymmetryFieldChanged`,
`FewerSaves`, `DisableNewGameIntro`. **`StrategyDuration` refused**, and it is the only one with
teeth: the 7 live strategies carry `minLeastDuration` 60–100 and `maxLongestDuration` 1200–1600 days,
so honouring them would lock AXE's rep→funds channel after each commit and expire it every 3–4 years
— time pressure, which AXE cut with KCT.

**Provenance worth recording:** the G keys hid inside RP-1's `CrewSettings.cfg`, which `sync-seed.ps1`
excludes as *"RP0.dll crew retirement system"*. That reason was true of most of the file and false of
the part that mattered — **a file excluded on the strength of its name.** Two other exclusion reasons
had drifted the same way (`CustomBarnKit.cfg` still said "RP-AXE uses CBK defaults", six facility
ladders later; `KSPCommunityFixes.cfg` still read as an open option). All three rewritten, because
that list is where a future RP-1 bump gets triaged.

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
- ~~The tracking-station ladder is copied verbatim from RP-1 and does **not** carry the
  `upgrades[0]`-is-dead note that `AxeFacilities.cfg` carries.~~ ✅ **Comment added 2026-07-29.**
  The numbers were always right (`docs/ECONOMY.md`: 11 levels, 10 purchases, 2,525,000); the
  warning was the only thing missing, on the one array in the repo most likely to be misread twice.
