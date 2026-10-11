# RP-AXE — Packaging & Release

Artifacts: `RP-AXE.netkan` (CKAN metadata), `GameData/RP-AXE/RP-AXE.version` (KSP-AVC, the **single
place the version number lives**), `GameData/RP-AXE/RP-AXE-Changelog.cfg` + `CHANGELOG.md`,
`LICENSE.md` (CC-BY-NC-SA-4.0). Target: **KSP 1.12.0–1.12.5**. Only `GameData/RP-AXE/` ships.

## Release checklist

Repo-side, done for 0.9.0 (2026-10-11):

- [x] `AxeDbsToolbarNreFix.cs` reverted (`dead7bf`) — AXE ships no patches for other mods' bugs.
- [x] No Squad assets in the payload: the 16 `RDicon_*.png` node icons were extracted stock glyphs;
      nodes now use the current stock icon names and the atlas resolves them (`3ab97d1`).
- [x] `tools/check_liveness.py` green (the empty `nuc_fuelReprocessing` node is gone), the other three
      gates green, `build_tree.py`'s own gates green.
- [x] `RP-AXE.netkan` split into depends / recommends / suggests / conflicts by `tools/gen_netkan.py`
      (see "Dependency model" below), with the `-default` Scatterer aliases and `$vref` reading the
      AVC file for KSP compatibility. Graphics are no longer forced on the player.
- [x] Personal one-off mission scripts removed from `tools/mission/`; the general planner stays.
- [x] Shipped `_README.md`s describe the folders as they are; `design/` no longer cites deleted docs.
- [x] Version 0.9.0 (public beta) in `RP-AXE.version`; changelog in-game and in the repo.
- [x] `tools/package_release.py` builds the archive from git-tracked files + the fresh DLL and
      refuses LFS pointers, stale DLLs and dev artifacts (`craft-prices.csv`, `.gitkeep`).

Still needs you (each is outward-facing or needs credentials):

- [x] History rewritten and `main` swapped onto it; backups stay until the push has succeeded.
- [x] **Pushed** 2026-10-11: `origin = git@github.com:miskoltrans/RP-AXE.git`, `main` + tags `v0.9.0`, `pre-restart-mvp`, `tree-v2-spine`; old history and the LFS store dropped locally afterwards (`.git` = 55 MB).
- [ ] **GitHub release.** `gh auth login`, then `gh release create v0.9.0 dist/RP-AXE-v0.9.0.zip dist/RP-AXE-v0.9.0.zip.sha256 --prerelease --title "RP-AXE 0.9.0 (beta)" --notes-file CHANGELOG.md` (or upload the zip to the v0.9.0 tag in the web UI, ticking *pre-release*). CKAN's `$kref` needs that asset.
- [x] Tagged `v0.9.0` (annotated) and pushed; `dist/RP-AXE-v0.9.0.zip` + `.sha256` built from it.
- [x] **Clean-room install test, install half** (below): the published 0.9.0 asset + Express-Low
      resolve headless into 125 modules, 54/54 depends, 25/25 recommends, GameData as shipped
      (`tools/check_cleanroom.py` OK on `../ksp_instance_cleanroom3`).
- [ ] **Clean-room boot** — needs an unlocked session (see the last finding below):
      `..\ksp_instance_cleanroom3\KSP_x64.exe -axe-autotest`, then
      `python tools\check_liveness.py --instance ..\ksp_instance_cleanroom3`. `../ksp_instance_cleanroom_gui`
      is a fresh copy for the GUI run (*Manage instances → Add*, then the two `.ckan` installs).
- [ ] **CKAN listing** (optional): run the netkan through the inflator (`netkan.exe RP-AXE.netkan`, or
      the NetKAN-bot on a PR) and submit it to https://github.com/KSP-CKAN/NetKAN. Until then players
      add it locally via *CKAN → Settings → Add netkan*.
- [x] R&D screen eyeballed via the AutoTest screenshot (`Instance/axe-shot-RD.png`, 2026-10-11): every node shows its stock discipline glyph.

## History rewrite (2026-10-11, before the first push)

Done with `git filter-repo` + `git lfs migrate export` in a scratch clone, then fetched back as
`main-rewritten` (backups: branch `main-prepurge`, `refs/backup/tags/*`, and a bundle in the
session scratchpad). 965 commits kept, every tree identical to the old one except the two
gitignored renders. The repository went from 700 MB to 55 MB.

| purged from every commit | why |
|---|---|
| `GameData/RP-AXE/design/Tree/icons/*.png`, `tree/render/prototype/icons/*.png` | Squad's own R&D glyphs (EULA) |
| `tree/render/prototype/axe-tree-standalone.html` (106 versions) | base64-embedded the same icons; regenerated and re-added |
| `tree/render/axe-tree.png` / `.svg` (162 versions each) | generated renders, 390 MB of a 430 MB repo; now gitignored |
| git-lfs pointers → plain blobs | RP-1 ships its assets in-repo too; GitHub's LFS bandwidth quota would throttle clones |

**Swap — DONE 2026-10-11 (`main` = `d698839`; `main-prepurge` = the old `1288c63` line). For the record:**

```
git log --oneline main-prepurge..main        # anything here was committed after the rewrite: cherry-pick it after the swap
git update-ref refs/heads/main refs/heads/main-rewritten
git reset -q
git checkout HEAD -- .gitattributes .gitignore docs/TREE.md docs/RELEASE.md
git lfs uninstall --local
git update-ref refs/tags/pre-restart-mvp refs/rewritten/tags/pre-restart-mvp
git update-ref refs/tags/tree-v2-spine refs/rewritten/tags/tree-v2-spine
git status --short                            # expect clean
```

**After the push has succeeded**, drop the old history locally:

```
git update-ref -d refs/heads/main-prepurge
git update-ref -d refs/heads/main-rewritten
git update-ref -d refs/backup/tags/pre-restart-mvp;  git update-ref -d refs/backup/tags/tree-v2-spine
git update-ref -d refs/rewritten/tags/pre-restart-mvp; git update-ref -d refs/rewritten/tags/tree-v2-spine
git reflog expire --expire=now --all && git gc --prune=now
git lfs prune                                 # the 512 MB .git/lfs store, incl. the 16 icon objects, is unreferenced
```

## Build the release payload

```powershell
python tools/package_release.py          # dotnet build -> dist/RP-AXE-v<ver>.zip, archive root GameData/RP-AXE/
python tools/package_release.py --no-build
```

The script zips **git-tracked** files under `GameData/RP-AXE` plus `Plugins/AXE.dll`, so runtime
droppings (`@thumbs/`, `Bridge.cfg`, MM caches) can never leak in. Bump the version only in
`RP-AXE.version` (and add the matching `VERSION {}` block to `RP-AXE-Changelog.cfg`).

## Clean-room install test (the release "prove")

Goal: a stranger installs from metadata with **zero manual steps** and gets a working, RP-1-free,
RP-1-conflicting install.

The CKAN client cannot read a netkan; it installs `.ckan` files. `tools/package_release.py` writes
`dist/RP-AXE-<ver>.ckan` (the netkan inflated against the release asset) and that is what both the
player and this test feed to CKAN. Run as of 0.9.0 (2026-10-11), twice, headless:

```
robocopy ..\ksp_instance_clean ..\ksp_instance_cleanroom /E          # fresh stock 1.12.5 + DLCs, no CKAN registry
# the snapshot is not pristine: B9PWings and ModularLaunchPads left 29 example craft in Ships\, and
# CKAN refuses to overwrite a file it did not install -- delete every .craft without a .loadmeta twin
..\ckan.exe install -c RP-AXE-Express-Low.ckan --no-recommends --gamedir ..\ksp_instance_cleanroom --headless
..\ckan.exe install -c dist\RP-AXE-0.9.0.ckan   --no-recommends --gamedir ..\ksp_instance_cleanroom --headless
python tools\check_cleanroom.py --instance ..\ksp_instance_cleanroom   # depends / recommends / conflicts / GameData vs the netkan
..\ksp_instance_cleanroom\KSP_x64.exe -axe-autotest                   # career, R&D, Mission Control, quit
python tools\check_liveness.py --instance ..\ksp_instance_cleanroom
```

The GUI path is the same `.ckan` through *File → Install from .ckan file* on a fresh instance added
under *Manage instances* (`../ksp_instance_cleanroom_gui` is prepared for it); it shows what headless
decides silently: the texture-pack chooser and the recommendations dialog.

What the first two runs found, and fixed (`99ddd29`, `98e7fad`):
- **VenStockRevamp** — the resolver failed outright: VenStockRevamp-Core *recommends* the full
  VenStockRevamp, which conflicts with ReStock. Now in `conflicts`.
- **No planet textures, exit 0** — RSS's virtual `RSSTextures` was dropped by the headless resolver.
  An `any_of` in `depends` gives the GUI a proper chooser, but the third run showed headless drops
  the `any_of` just the same: a choice it cannot ask about is skipped, exit 0. So the CLI path is
  either an Express preset (which names the pack) or `ckan install RSSTextures4096` afterwards, and
  `check_cleanroom.py` fails the install until a pack is present.
- **Scatterer without config** — same mechanism, via RSS → Parallax → Scatterer. Now `recommends`
  Scatterer + its `-default` config aliases.
- **164 modules installed, 86 not named by the netkan** — the recommends closure of the dependencies
  (BDB, KSCExtended, KerbinSide, the RN rocket packs, CLS, RPM/ASET IVAs, Trajectories, …). Not a bug,
  but the Express presets exist so a player can decline it in one go.
- **FAR dead, RealAntennas types unloadable, Skopos down with them** (third run, the boot) — both
  hard-depend on the virtual `KSPBurst`, which has two providers, so the headless resolver dropped it
  and nothing shipped `Unity.Burst`. The full `KSPBurst` (runtime + compiler, what the dev instance and
  RP-1 Express run) is now a named hard dependency; it co-installs with the real Harmony2.
- **A boot launched on a locked Windows session never leaves the first frames.** Unity stops
  presenting frames when the session is locked (`LogonUI.exe` running), and KSP's asset loader only
  advances per frame — so KSP.log and Player.log go silent right after the addon `Awake`s while
  ModuleManager's background thread still finishes and the process burns two cores. Three runs were
  spent on that before it was recognised. **Run the boot step from an unlocked session**, and check
  `Get-Process LogonUI` before believing a "hang".
- **One local file per `ckan install -c`** — passing two `-c` files installs only the last one, and a
  metapackage naming `RP-AXE` failed "Unsatisfied dependency RP-AXE" because a local file is an
  install target, not a registry entry. The presets now list only the recommends + graphics, and the
  documented path is two installs (preset first, then `RP-AXE-<ver>.ckan`), GUI and CLI alike.

> The dev `Instance/` is the reference working set: its installed modules are captured verbatim in
> `RP-AXE-deps.ckan`, and `tools/rebuild-instance.ps1` proves that list installs headless with
> `--no-recommends`. The clean-room run is the other half: the *player's* resolution of the netkan,
> recommends on, from the published asset.

## Dependency model

`RP-AXE.netkan` is **generated by `tools/gen_netkan.py`** from one classification; edit the lists
there, never the JSON. The script also proves coverage: every module in the dev environment
(`RP-AXE-deps.ckan`) must be listed or reachable through `depends` edges in the live CKAN registry,
so a player's install cannot silently differ from the one the tree was built against.

| list | rule | count |
|---|---|---|
| `depends` | the stack AXE's configs and plugin bind to directly (RO, RSS, Kerbalism + RO config, Contract Configurator, CustomBarnKit, RealAntennas, KSCSwitcher, Skopos; ROUtils, Harmony, MFI for `AXE.dll`) **plus every mod the tree places parts from** (`manifest/curated-parts.tsv`), plus an `any_of` over the four RSS texture packs, light one first. The tree is balanced against exactly that part set; a missing one leaves nodes you pay science for and get nothing from. | 52 + 1 |
| `recommends` | tools AXE integrates with when present and runs without: MechJeb, TestFlight, alarm clock, transfer planners, editor QoL, visual polish, and Scatterer **with** its config. CKAN installs them by default, untickable. | 26 |
| `suggests` | the author's graphics preset (RP-1 Express High) and the two DLCs, which CKAN cannot install. Breaking Ground matters: 28 robotics parts are placed. | 9 |
| `conflicts` | what RP-AXE replaces: RP-1 / RP-0 / RONoCareer (career layer), KCT, CommunityTechTree and HideEmptyTechNodes (tree), KRASH (simulator), NFE-DecayingRTGs (RTG model), MechJebForAll, CrowdSourcedScience; and the full VenStockRevamp, which ReStock conflicts with and VenStockRevamp-Core recommends. | 11 |

- **Graphics are not forced.** The texture pack is an `any_of` (4K is the headless default; the GUI
  asks). `RP-AXE-Express-High.ckan` / `RP-AXE-Express-Low.ckan` are the one-click presets in the RP-1
  Express mould: RP-AXE + its recommends + a graphics set as hard deps; they conflict with each other
  and ship on the release page.
- **A headless resolver silently drops any virtual dependency with several providers — of a
  dependency too, not just of a metapackage.** Clean-room run 2026-10-11: RSS installed with no
  texture pack (exit 0), and Scatterer (pulled in by RSS → Parallax → Scatterer) with no config.
  Hence the `any_of` and the `-default` Scatterer aliases above; never the bare virtual names.
- **The recommends closure is large.** CKAN also offers the recommendations of every dependency:
  ModularLaunchPads recommends Bluedog Design Bureau and KSCExtended, which recommends KerbinSide
  and Tundra, RN-SovietProbes recommends the RN rocket packs, US2 recommends CLS, and so on — ~50
  part mods the tree never placed, ~10 GB. A headless "yes" takes them all. The Express presets with
  `--no-recommends` give exactly the curated set; GUI users decline the second dialog.
- SCANsat: the dev instance runs the `miskoltrans/SCANsat-GPU` fork (to be merged upstream); the
  public dependency is stock CKAN `SCANsat`, which carries the same part names the tree places.
- Transitive deps (Kopernicus, FAR, AJE, RealFuels, DynamicBatteryStorage, KerbalKonstructs,
  SystemHeat, …) are left to CKAN; listing them would only make the file harder to read.
- `RP-AXE-deps.ckan` stays the dev-instance "perfect environment" (everything as hard deps, High
  graphics, no SCANsat because the rebuild script installs the fork). It is what
  `tools/rebuild-instance.ps1` consumes.
- Upstream RP-1 is at v4.5.0.0 on CKAN; the seed is vendored from v4.4.0.0. Not a release blocker
  (the seed is self-contained), but a `tools/sync-seed.ps1` pass is due.

## AutoTest harness

Ships **disabled** (`Plugins/PluginData/AutoTest.cfg` `enabled = false`); the `-axe-autotest` launch
flag force-enables it. The localhost bridge (`Bridge.cfg`) is written on first run with
`enabled = false` and is gitignored, so a player never gets a listener unless they turn it on.

## Publishing

**CKAN.** The listing is a pull request, not an upload: fork https://github.com/KSP-CKAN/NetKAN, copy
`RP-AXE.netkan` to `NetKAN/RP-AXE.netkan`, open the PR. The NetKAN bot inflates it within minutes and
comments with any error (unresolvable `depends`, a bad `install` stanza, a license outside CKAN's list);
a CKAN team member then reviews the first submission of a new mod. What it needs from our side is
already there: a GitHub release with the zip attached (`$kref`), the AVC file (`$vref`), a listed
license, and no Squad assets in the archive. While the mod is a GitHub *pre-release*, the netkan's
`x_netkan_github.prerelease = true` is what lets the bot see it; remove it at 1.0. The graphics
presets can go in the same PR as `NetKAN/RP-AXE-Graphics-High.netkan` / `-Low.netkan` (they are
metapackages with a static `version`, like `RP-1-ExpressInstall-Graphics-*`). `RP-AXE-deps.ckan` is a
dev tool and is not submitted. Once merged, a new GitHub release is picked up automatically.

**SpaceDock** (optional, https://spacedock.info): upload the same zip under the same license and
KSP 1.12.5. Many players browse it directly, and it gives the mod a page with screenshots.

**Where to post.**
- KSP Forum, *Kerbal Space Program 1 → Add-on Releases*: the canonical announcement. Title in the
  house style, e.g. `[1.12.x] RP-AXE 0.9 beta — a science-first career on the RO stack`. Forum rules
  require the license and a source link in the post; include 3–4 screenshots (the R&D tree, a program
  charter, the simulator) and the one-paragraph pitch from the README.
- The KSP-RO Discord (the RO / RP-1 community) in its mod-releases channel: this is the audience that
  already runs the dependency stack. Expect the sharpest questions there (what exactly diverges from
  RP-1 — `docs/CHANGES-VS-RP1.md` answers that).
- r/KerbalSpaceProgram (Mod flair) and r/RealSolarSystem: screenshots first, link second.
- Link all of them to the GitHub Issues page; that is where the beta feedback should land.
