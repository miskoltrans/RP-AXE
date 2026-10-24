# RP-AXE on Sol

RP-AXE is built and balanced on Real Solar System. [Sol](https://github.com/RSS-Reborn/Sol-Configs/wiki)
(RSS-Reborn, by ballisticfox and Charon_S) is a newer replacement for RSS: the same real solar system
with new terrain, textures and visuals, plus 18 extra small bodies. RP-AXE runs on it, with a
compatibility layer that puts a Sol career back on the RSS numbers.

**Status (2026-10-24):** tested on Sol **0.9.5** (public CKAN release) with KSP 1.12.5. A new career
starts, R&D and Mission Control open, the editor loads, launch-site switching and the ground-station
network work, and the merged configuration matches the RSS install on everything listed under
"What RP-AXE adjusts" below. Not yet flown end to end. Needs **RP-AXE 0.9.1 or later**, the
first release with `GameData/RP-AXE/design/Sol/`. On 0.9.0, Sol installs and boots but plays with
Sol's own science values (see below).

> RP-1's own wiki says Sol "may cause issues with some aspects of RP-1" and the KSP-RO Discord does
> not support it. RP-AXE carries some of RP-1's configuration, so report Sol problems on the
> [RP-AXE issue tracker](https://github.com/miskoltrans/RP-AXE/issues), not to KSP-RO.

## Install

Use a fresh KSP 1.12.5 folder. Sol and RSS cannot be installed side by side, and a career started
on one cannot be moved to the other (the bodies are numbered differently, so every orbit in the
save points at the wrong body).

Sol's own guide is the [Installation page of its wiki](https://github.com/RSS-Reborn/Sol-Configs/wiki/Installation)
(marked as still in development). Its RP-1 path starts from `RP-1 Express Install`, which brings RP-1,
and RP-1 conflicts with RP-AXE, so follow the steps below instead. The RP-AXE Sol preset installs the
texture sizes Sol's guide recommends (step 2), and Blackrack's volumetric clouds are step 6.

### 1. Add Sol's CKAN repository

Sol is not on CKAN's default repository. In CKAN: **Settings → CKAN settings → Metadata
repositories → New**, choose **Sol** from the list (or enter the URL
`https://github.com/RSS-Reborn/CKAN-meta/archive/main.tar.gz`), then **Refresh**.

Command line:

```
ckan repo add --gamedir <KSP folder> Sol https://github.com/RSS-Reborn/CKAN-meta/archive/main.tar.gz
ckan update --gamedir <KSP folder>
```

### 2. Install two files, in this order

From the [release page](https://github.com/miskoltrans/RP-AXE/releases), download
`RP-AXE-Express-Sol.ckan` and `RP-AXE-<version>.ckan`. Install them one after the other with
**CKAN → File → Install from .ckan file**. Decline the further recommendations CKAN offers (they come
from the dependencies; the tree places nothing from them). Do not press Cancel, which aborts the whole
install.

The Sol preset is the RSS-Low tool set plus Sol at the texture sizes Sol's guide recommends for its
RP-1 preset: 16K for Earth and Mars, 8K for Mercury, Venus, Jupiter and Saturn, 4K for the rest (the
Sun, which Sol's table leaves out, is 4K). About 6 GB of planet textures. Every Sol and Parallax texture
pack is named. That matters: Sol's per-system packs are virtual (4K/8K/16K), and the three
ParallaxContinued texture packs that Sol's terrain reads were silently skipped by CKAN in testing, with
no error. For other sizes, swap the packs in CKAN afterwards (each system's sizes replace each other).

> **Magenta triangles on the ground** around the space center mean those Parallax texture packs are
> missing: the grass and rock scatters render without textures. `KSP.log` shows
> `Failed to load map Parallax_StockScatterTextures/...`. Install `ParallaxContinued-Terrain-Textures`,
> `ParallaxContinued-Scatter-Textures` and `ParallaxContinued-Planet-Textures`.

Command line, same order, **plus a third command**:

```
ckan install -c RP-AXE-Express-Sol.ckan --no-recommends --gamedir <KSP folder> --headless
ckan install -c RP-AXE-<version>.ckan   --no-recommends --gamedir <KSP folder> --headless
ckan install KSPBurst ParallaxContinued-Planet-Textures --no-recommends --gamedir <KSP folder> --headless
python tools/check_cleanroom.py --instance <KSP folder>     # optional, from a clone of this repo
```

With Sol's repository added, headless CKAN (1.36.4) skipped `KSPBurst` and
`ParallaxContinued-Planet-Textures` in testing. Both are named by the preset and by RP-AXE, and
CKAN still exited 0. Naming them on the command line installs them. Without KSPBurst, FAR and
RealAntennas cannot load. In the CKAN window, if it asks which mod should provide `KSPBurst`, pick
**KSPBurst Compiler**. Afterwards, check that `GameData/000_KSPBurst/` and
`GameData/Parallax_StockPlanetTextures/` exist.

Don't use `RP-AXE-Express-RSS-Low` or `-RSS-High` with Sol. They carry RSS textures and RSSVE, and they
conflict with Sol-Core.

### 3. Leave Sol's settings on "RSS"

`GameData/Sol-Configs/Sol-Configuration.cfg` ships with the RSS preset. Keep it:

- `SystemScale = Real`. Quarter and Stock scale break everything RP-AXE is tuned for.
- `SystemReferenceFrame = ICRF`. Like RSS, Earth's orbit is then inclined 23.4° and the equator is
  the reference plane. `Ecliptic` changes every launch-window and inclination figure in the docs.
- `LunaReferenceFrame = Equatorial`, the default.

### 4. First start

The first boot compiles and patches everything. A cold start took 8 to 14 minutes in testing. If loading seems to stop right after the shader lines, look for a KSPCommunityFixes
question ("cache PNG textures?") hidden behind the loading screen. Then start a **new Career**.

### 5. TransferWindowPlanner: switch it to Earth dates

TransferWindowPlanner turns on its Earth calendar only when it detects RSS's plugin, which Sol does not
have. Without the Earth calendar it prints dates in Kerbin days. Edit
`GameData/TriggerTech/TransferWindowPlanner/PluginData/settings.cfg` (KSP closed):

```
SelectedCalendar = Earth
ShowCalendarToggle = True
```

### 6. Optional: Blackrack's volumetric clouds (V5)

Sol's cloud configs (`GameData/Sol-Visuals/`) are written for Blackrack's volumetric clouds **V5**:
each cloud layer has a volumetric `layerRaymarchedVolumeV5` node and a flat `layer2D` fallback. The
EVE and Scatterer that CKAN installs (EVE 1.11.7.2 and Scatterer 0.0878 in testing) do not draw the
V5 layers, so a CKAN install has flat clouds. Sol's guide: "Install blackrack's volumetric clouds V5
manually, the V3 version on CKAN will not work." V5 is distributed on
[Blackrack's Patreon](https://www.patreon.com/c/blackrack/posts).

With KSP closed, after the install above:

1. From the V5 download, copy `EnvironmentalVisualEnhancements`, `Scatterer` and
   `StockVolumetricClouds` into `GameData`, replacing the folders CKAN installed. Sol's cloud configs
   load their textures and lightning sounds from `StockVolumetricClouds/`, so that folder is needed too.
2. Keep `Sol-Visuals` as it is: it already contains the V5 configs. Do not add RSSVE or another cloud
   pack on top of it.

CKAN still lists its own EVE and Scatterer as installed (`Sol-Visuals` depends on both), so a CKAN
upgrade of either can overwrite the V5 files. If one gets upgraded, copy V5 back. RP-AXE reads nothing
from EVE or Scatterer, so the clouds do not change a career, but volumetric clouds are heavy on the
GPU. This step is untested with RP-AXE (V5 is a paid download): report cloud problems to Sol or
Blackrack, and anything RP-AXE-related here.

## What RP-AXE adjusts on Sol

Sol satisfies CKAN's `RealSolarSystem` dependency (`provides`), but inside the game it is a different
mod. It registers the ModuleManager name `SolSystem`, never `RealSolarSystem`. It creates its planets
in the `:FOR[SolSystem]` pass, which runs after RP-AXE's own pass, so a patch written for RSS
reaches a planet before Sol has created it. It also ships its own copies of several RSS-side configs.
The result is a career that loads cleanly and is quietly different. `GameData/RP-AXE/design/Sol/` is
generated by `tools/gen_sol_compat.py`. All of it is gated on `SolSystem`, so on RSS it does nothing.

| | on Sol without the layer (0.9.0) | with it |
|---|---|---|
| **Science per body** (RP-AXE's multipliers and altitude thresholds) | Sol's own values on 32 of 33 bodies: Charon landed ×13 instead of ×50, Callisto ×8.5 instead of ×30, Pluto's "high space" starts at 100 km instead of 1,200 km, the Sun's at 1 million km instead of 15 million. The tree's ~420k science budget assumes RP-AXE's values, so outer-planet science would pay a third. | RP-AXE's values (RSS's for the Sun) |
| **Earth below 40 km** | farmable again (RP-AXE zeroes it) | ~0, as on RSS |
| **Saturn, Uranus, Neptune heat** | radiate as 1,000 K blackbodies: orbiters with low max temperature burn up (RP-AXE's fix never applies) | effective temperatures, as on RSS |
| **SCANsat scanners** | every altitude ×3 by Sol, on top of RealismOverhaul's tuning (HIRES best altitude 900 km instead of 300 km) | RSS values, 53 scanner modules |
| **Ground stations** | Sol's copy of the RealAntennas station table lacks the DSN Ka band at tracking level 10 and has older encoders at the three NIP stations | RealAntennas' current table |
| **Resources** | none at Jupiter, Io, Saturn, Titan, Uranus, Neptune, Pluto, Charon | RSS's maps (98 resource definitions, from RealSolarSystem, CC-BY-NC-SA) |

Already the same on both, no layer needed: tech tree, parts, contracts, the tracking-station ladder,
Kerbalism radiation belts (Sol ships its own copy), 56 RealAntennas ground stations, launch-site
switching (Sol has 34 sites; RP-AXE's default Cape Canaveral exists).

## Differences that remain

- **Earth's biomes** are Sol's own: climate zones (deserts, tundra, rainforest...) instead of RSS's
  11. Earth below 40 km pays nearly nothing in RP-AXE, so the effect is small. Moon and Mars biomes
  match RSS. Sol's guide mentions an "RP-1 Biomes Addon" that cuts the biomes to RSS's count. It is
  not part of Sol 0.9.5 on CKAN and has not been tried with RP-AXE.
- **18 extra bodies** (Pallas, Psyche, Eros, Ida and Dactyl, Ryugu, Arrokoth, Amalthea, Thebe,
  Hyperion, Phoebe, Puck, Proteus, Nereid, Nix, Hydra, Kerberos, Styx) keep Sol's science
  multipliers. They are extra places to do science that RSS does not have.
- **Ephemeris.** Sol positions the planets from J2000-era elements; RSS uses B1950. Launch windows
  fall on slightly different dates than RSS's.
- **Launch-site names.** Sol fixes two of RSS's misspelled site IDs (`us_vandenberg`,
  `ru_kapustin_yar`) and adds `us_edwards`, `us_guam`, `us_whitesands`, `no_andoya`,
  `ca_saint_lawrence` and `uk_shetland_island`. Sol's own tracker reports missing radios at some of
  the new sites.
- **Lunar impactor contract: may not complete on Sol 0.9.5.** `LunarImpactor` and
  `LunarImpactorOptional` only count the impact if the probe first registers within 3,500 m of the
  lunar terrain (`ReachMoonSurface`, `maxTerrainAltitude = 3500`). RP-1's wiki reports a Sol bug where
  the first lunar impactor does not complete, and Sol's development branch already raises the limit to
  8,500 m for these two contracts (`Sol-Configs/Patches/Sol-RP1.cfg`, after 0.9.5). RP-AXE's ported
  contracts have the same names and parameter structure, so that patch will apply to them once Sol
  releases it. Until then, on Sol 0.9.5: if the impact happens and the contract stays open, that is
  this bug, not your trajectory. Not yet reproduced with RP-AXE.
- **Mimas flyby is much tighter.** Sol's Mimas has a 250 km sphere of influence (RSS: 396 km),
  measured from its centre, and the `Mimas Flyby` contract only counts inside it. On Sol that means
  passing within about 50 km of the surface instead of about 200 km. Mimas is the only body whose
  sphere of influence differs from RSS by more than 2%. Every other body-specific contract loads and
  resolves its target on Sol (373 of 373 contract types, as on RSS); none requires a specific biome.
- **Gas giants are oblate** by default (`OblateGasGiants = True`). Sol warns this can make EVE
  clouds and Scatterer misbehave close up.
- **Cosmetic:** RealPlume's real-scale plume expansion (`atmDensityExp = 1`) and ZTheme's HUD colours
  key on RSS and fall back to stock behaviour. No gameplay effect.
- **Mirage** (Sol's GPU terrain, closed beta) has not been tested with RP-AXE.

## For maintainers

- `python tools/gen_sol_compat.py` regenerates `design/Sol/`. Re-run it after an RP-1 seed sync,
  after changing `BodyScienceParams.cfg`, `EarthScienceRemoval.cfg` or `AxeGasGiantEmissiveFix.cfg`,
  and after a dev-instance rebuild. `--check` fails if a file is stale.
- `python tools/gen_sol_compat.py --verify <Sol instance>/GameData/ModuleManager.ConfigCache`
  compares a booted Sol install against the RSS dev instance on every item in the table above.
  0.9.0 on Sol reported 103 mismatches; with the layer, see "Verification" below.
- When Sol updates, re-check three assumptions. (1) Its pass is still `SolSystem`, and its home body
  is `Body[Earth]`. (2) It still ships no resources for the bodies in `SOL_MISSING_RESOURCES`;
  otherwise they would be doubled. (3) Its Saturn, Uranus and Neptune temperature curves still start
  at the RSS datum.
- A new `@Kopernicus` patch anywhere in RP-AXE needs a Sol twin, for the reason above.
- Test install: copy `ksp_instance_clean` to a new folder, delete `Ships/*.craft` without a
  `.loadmeta` twin, add the Sol repo, install the two `.ckan` files, and boot with `-axe-autotest`
  (set `kscSwitchTest = true` in `PluginData/AutoTest.cfg` to also exercise launch sites and ground
  stations). `check_cleanroom.py` checks a Sol install by its own rules: Sol's packs, the Parallax
  texture folders, Sol-Visuals present, no RSS, RSSVE or RSS-Textures.

## Verification

Test instance `ksp_sol` (2026-10-23/24): KSP 1.12.5 with both DLCs, Sol 0.9.5 at 4K from Sol's CKAN
repository, RealFuels 15.16.1, CKAN 1.36.4, headless.

1. **Published 0.9.0, as a player would install it** (Sol, then the Sol preset, then
   `RP-AXE-0.9.0.ckan`): 141 modules, no RSS pulled in. `-axe-autotest` passed: new career, R&D,
   Mission Control, plus the launch-site test (switch to Kourou, co-located ground station found,
   56 stations, LastKSC persisted). The same boot surfaced:
   - `[AXE] Harmony PatchAll failed` against RealFuels 15.16 (not Sol-specific, fixed in `c4c1863`);
   - `--verify`: 103 mismatches (the table above);
   - `Failed to load map Parallax_StockScatterTextures/...`: the skipped Parallax packs, seen in
     game as magenta triangles around the space center.
2. **This repository + `design/Sol/` + the Parallax packs:** `Harmony patches applied: 21 class(es),
   0 failed`, ContractConfigurator `Loaded 373 out of 373`, autotest passed, zero Parallax errors.
   `--verify` matched everything except the Sun's high-space boundary, which the generator then
   started snapshotting. That last change has not been re-booted on Sol yet.
3. `check_cleanroom.py --instance ksp_sol`: OK in Sol mode.
4. **Published 0.9.1, fresh instance** (`ksp_sol_cleanroom`: the two release `.ckan` files, headless):
   both installs exited 0, but `KSPBurst` and `ParallaxContinued-Planet-Textures` were missing.
   Naming `KSPBurst` in the preset did not change that. The third command above completed the
   install: 144 modules, and `check_cleanroom.py` OK, including its new check that every dependency
   of every installed module is present.
5. **Biome maps** (2026-10-24, `-axe-autotest -axe-autotest-biomes` on `ksp_sol`, 4K packs): `RESULT
   PASS`. Every mapped body's `ScienceUtil` lookup, sampled on a 1-degree grid, resolves to the biomes
   its map defines (Earth 31 of 32; the 32nd, Cool Mediterranean, is smaller than the grid). The other
   32 RSS bodies carry exactly RSS's biome names. Earth's 16K biome map (the recommended pack) is the 4K
   map at four times the resolution: same 32 values, 98.25% pixel agreement when scaled down. All other
   biome maps are byte-identical across pack sizes. **Phobos and Deimos have no biome map, on RSS too:**
   RP-1's `seed/Science/BodyScienceParams.cfg` points them at `RP-1/PluginData/blankbiomes.dds`, which
   RP-AXE does not ship. Kerbalism then gives them one biome-agnostic subject per situation, the same
   payout RP-1's single real biome would give.
