# RP-AXE — Packaging & Release

Artifacts: `RP-AXE.netkan` (CKAN metadata), `GameData/RP-AXE/RP-AXE.version` (KSP-AVC, the **single
place the version number lives**), `GameData/RP-AXE/RP-AXE-Changelog.cfg` + `CHANGELOG.md`,
`LICENSE.md` (CC-BY-NC-SA-4.0). Target: **KSP 1.12.0–1.12.5**. Only `GameData/RP-AXE/` ships.

## Release checklist

Repo-side, done for 1.0.0 (2026-10-11):

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
- [x] Version 1.0.0 in `RP-AXE.version`; changelog in-game and in the repo.
- [x] `tools/package_release.py` builds the archive from git-tracked files + the fresh DLL and
      refuses LFS pointers, stale DLLs and dev artifacts (`craft-prices.csv`, `.gitkeep`).

Still needs you (each is outward-facing or needs credentials):

- [ ] **GitHub.** `gh auth login`; create `miskoltrans/RP-AXE` (public); `git remote add origin
      git@github.com:miskoltrans/RP-AXE.git`; `git lfs push --all origin main` then `git push -u origin
      main`. The `.version` `URL` and the netkan `$kref` both assume that owner/repo and branch `main`.
      History is already rewritten (see "History rewrite" below); push only `main` and the two tags,
      never `--all` / `--mirror`, or the pre-purge backup refs go up with it.
- [ ] **Tag + release.** `python tools/package_release.py` → `dist/RP-AXE-v1.0.0.zip` (+ `.sha256`).
      `git tag v1.0.0 && git push origin v1.0.0`, then
      `gh release create v1.0.0 dist/RP-AXE-v1.0.0.zip --title "RP-AXE 1.0.0" --notes-file CHANGELOG.md`.
      CKAN's `#/ckan/github/miskoltrans/RP-AXE` `$kref` reads that release asset.
- [ ] **Clean-room install test** (below) against the published release — the only prove that a
      stranger's CKAN resolves the metadata unattended.
- [ ] **CKAN listing** (optional): run the netkan through the inflator (`netkan.exe RP-AXE.netkan`, or
      the NetKAN-bot on a PR) and submit it to https://github.com/KSP-CKAN/NetKAN. Until then players
      add it locally via *CKAN → Settings → Add netkan*.
- [ ] Eyeball the R&D screen once: every node should show a discipline glyph, not the generic
      flask. (The names are the ones `Squad/Resources/TechTree.cfg` uses, and the decompiled
      `IconLoader.GetIcon` answers from the atlas first, but nothing in the log would say otherwise.)

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

**Swap (run once, while no other session is committing):**

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

1. New CKAN instance on a **fresh KSP 1.12.5** with both DLCs (`../ksp_instance_clean` is the snapshot).
2. *CKAN → Settings → Add netkan* → `RP-AXE.netkan`; install `RP-AXE`.
3. Verify CKAN pulls the realism stack + part packs and **refuses** if `RP-1` is selected.
4. Verify `GameData/RP-AXE/` exists, `GameData/RP-1/` does not, no `RP0.dll` / `CC_RP0.dll`, and
   `GameData/Scatterer/config/` is populated (the silent-drop symptom is an empty one).
5. Launch with `-axe-autotest`: it starts a career, walks R&D + Mission Control and quits. Then
   `python tools/check_liveness.py` against that install's cache (`--instance <path>`).

> The dev `Instance/` is the reference working set: its installed modules are captured verbatim in
> `RP-AXE-deps.ckan` and mirrored into the netkan `depends` (regeneration snippet in
> `docs/WORKFLOW.md`), and `tools/rebuild-instance.ps1` proves that list installs headless. The
> clean-room run adds only the `$kref` download of the published zip.

## Dependency model

`RP-AXE.netkan` is **generated by `tools/gen_netkan.py`** from one classification; edit the lists
there, never the JSON. The script also proves coverage: every module in the dev environment
(`RP-AXE-deps.ckan`) must be listed or reachable through `depends` edges in the live CKAN registry,
so a player's install cannot silently differ from the one the tree was built against.

| list | rule | count |
|---|---|---|
| `depends` | the stack AXE's configs and plugin bind to directly (RO, RSS, Kerbalism + RO config, Contract Configurator, CustomBarnKit, RealAntennas, KSCSwitcher, Skopos; ROUtils, Harmony, MFI for `AXE.dll`) **plus every mod the tree places parts from** (`manifest/curated-parts.tsv`). The tree is balanced against exactly that part set; a missing one leaves nodes you pay science for and get nothing from. | 52 |
| `recommends` | tools AXE integrates with when present and runs without: MechJeb, TestFlight, alarm clock, transfer planners, editor QoL, visual polish. CKAN installs them by default, untickable. | 23 |
| `suggests` | the author's graphics preset (RP-1 Express High) and the two DLCs, which CKAN cannot install. Breaking Ground matters: 28 robotics parts are placed. | 13 |
| `conflicts` | what RP-AXE replaces: RP-1 / RP-0 / RONoCareer (career layer), KCT, CommunityTechTree and HideEmptyTechNodes (tree), KRASH (simulator), NFE-DecayingRTGs (RTG model), MechJebForAll, CrowdSourcedScience. | 10 |

- **Graphics are not forced.** RSS hard-depends on a virtual `RSSTextures`, so CKAN prompts for the
  pack. `RP-AXE-Graphics-High.ckan` (the author's set, ~8 GB more) and `RP-AXE-Graphics-Low.ckan`
  (4K textures + Scatterer + DistantObject + PlanetShine) are importable metapackages for one-click
  presets; they conflict with each other.
- `Scatterer-config-default` / `Scatterer-sunflare-default`, never the bare virtual names: a
  metapackage `depends` on a name with many providers is dropped silently, exit 0 (A/B-verified on
  ckan 1.36.4; the result is a Scatterer that renders no atmosphere at all).
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
