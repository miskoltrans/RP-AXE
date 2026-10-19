# RP-AXE — Packaging & Release

Artifacts: `RP-AXE.netkan` (CKAN metadata), `GameData/RP-AXE/RP-AXE.version` (KSP-AVC, the **single
place the version number lives**), `GameData/RP-AXE/RP-AXE-Changelog.cfg` + `CHANGELOG.md`,
`LICENSE.md` (CC-BY-NC-SA-4.0). Target: **KSP 1.12.0–1.12.5**. Only `GameData/RP-AXE/` ships.

## Resume here (state as of 2026-10-12)

**0.9.0 public beta is live** at https://github.com/miskoltrans/RP-AXE/releases/tag/v0.9.0 (pre-release,
seven assets). The clean-room install and boot are proven. **The CKAN listing is waiting on a human:**
https://github.com/KSP-CKAN/NetKAN/pull/11689, opened 2026-10-12 from the fork `miskoltrans/NetKAN`,
branch `rp-axe` (three metanetkan stubs; the real metadata is `RP-AXE.netkan` and
`RP-AXE-Express-{High,Low}.netkan` on `main`). Expect weeks; nobody is polling it.

When something happens on the PR:
- **Reviewer asks for a change in a stub** → edit `NetKAN/RP-AXE*.netkan` on the fork's `rp-axe` branch
  and push; the PR updates itself.
- **Reviewer asks for a change in the metadata** (lists, install stanza, description) → edit
  `tools/gen_netkan.py`, run `python tools/gen_netkan.py`, re-inflate with netkan.exe (see "Publishing"),
  commit + push `main`, re-upload the `.ckan` assets (`gh release upload v0.9.0 ... --clobber`). No PR
  change needed: the stubs read `main`.
- **Merged** → (1) README "Install" becomes: *in CKAN, tick `RP-AXE Express High` or `RP-AXE Express Low`
  and install; untick the further recommendations* (keep the two-file path as the fallback for people
  who read old posts); (2) edit the forum thread and the SpaceDock description: "installing becomes a
  single tick" is now true; (3) tick the checklist below.
- **Closed / stalled** → ask in the PR; the fallback stays the release-page `.ckan` files, which work today.

**Promotion did not wait for the merge (decided 2026-10-19).** SpaceDock and the announcements go out
now, with the two-`.ckan`-file install. The working copy of every text (SpaceDock form values + long
description, forum thread, r/KerbalSpaceProgram, r/RealSolarSystem, KSP-RO Discord) and the posting
order is the launch kit: https://claude.ai/artifact/Fpc8vSDwqW7PjJAPApioGS (private to the owner; a
fresh session reads it with the Artifact tool). Once the SpaceDock and forum URLs exist: add them to
`resources` in `tools/gen_netkan.py` (`spacedock`, and `homepage` → the forum thread), regenerate,
push `main`, re-upload the `.ckan` assets; link both from the README.

Independent of the PR: delete `..\ksp_instance_cleanroom_gui` once the GUI run is done; RP-1 upstream is
v4.5.0.0 against seed v4.4.0.0 (a sync pass, not a blocker).

To pick this up in a fresh session: *"Resume the RP-AXE release: read docs/RELEASE.md 'Resume here',
then check https://github.com/KSP-CKAN/NetKAN/pull/11689 with `gh pr view 11689 --repo KSP-CKAN/NetKAN`."*

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
- [x] **GitHub release** v0.9.0 (pre-release) with `RP-AXE-v0.9.0.zip` + `.sha256`, `RP-AXE-0.9.0.ckan`
      and the two Express presets attached; the `.ckan` files are re-uploaded (`gh release upload --clobber`)
      whenever `gen_netkan.py` changes a list. CKAN's `$kref` reads the zip.
- [x] Tagged `v0.9.0` (annotated) and pushed; `dist/RP-AXE-v0.9.0.zip` + `.sha256` built from it.
- [x] **Clean-room install test, install half** (below): the published 0.9.0 asset + Express-Low
      resolve headless into 125 modules, 54/54 depends, 25/25 recommends, GameData as shipped
      (`tools/check_cleanroom.py` OK on `../ksp_instance_cleanroom3`).
- [x] **Clean-room boot** (run 5, 2026-10-12, unlocked session): `-axe-autotest` on
      `../ksp_instance_cleanroom3` reached the menu in 18 min cold, started a career, walked R&D and
      Mission Control, `SUCCESS`, quit itself; `check_liveness.py --instance` green; the `[ECON]` and
      exception lines are identical to the dev instance's. Only two log signatures were clean-room-only:
      Scatterer's stock planet list (fixed, see "Scatterer without config" below) and a benign
      `ADDON BINDER: Cannot resolve assembly: SCANsat.Unity` from stock SCANsat (the assembly loads).
      `../ksp_instance_cleanroom_gui` is a fresh copy for the GUI run (*Manage instances → Add*, then the
      two `.ckan` installs).
- [x] **Indexer dry run** (2026-10-12): all three netkans inflate with `netkan.exe v1.36.5`; the Express
      presets became marker zips on the release because a metapackage cannot be indexed (see "Publishing").
- [ ] **CKAN listing**: https://github.com/KSP-CKAN/NetKAN/pull/11689 (opened 2026-10-12 from the
      `miskoltrans/NetKAN` fork, branch `rp-axe`, the three metanetkan stubs); the bot validates on the PR. Until it is merged, players install the `.ckan` files from the release page.
      After the merge: README "Install" becomes "tick RP-AXE Express High or Low in CKAN".
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
- **Scatterer without config** — same mechanism, via RSS → Parallax → Scatterer. Runs 2–4 answered it by
  recommending Scatterer + its `-default` config aliases. Run 5 (2026-10-12, the first boot on an unlocked
  session) showed that is a no-op on RSS anyway: the default config is a list of *stock* bodies
  (`ScattererCelestialBody Kerbin not found` for each one) and only RSSVE's `@Scatterer_planetsList`
  patch retargets it. Scatterer now sits in `suggests` next to RSSVE-HR and in the High preset; Low
  mirrors RP-1 Express Graphics-Low, textures only.
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
| `recommends` | tools AXE integrates with when present and runs without: MechJeb, TestFlight, alarm clock, transfer planners, editor QoL, visual polish. CKAN installs them by default, untickable. | 22 |
| `suggests` | the author's graphics preset (RP-1 Express High, Scatterer included: it only works on RSS through RSSVE) and the two DLCs, which CKAN cannot install. Breaking Ground matters: 28 robotics parts are placed. | 12 |
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

**CKAN.** The listing is a pull request to https://github.com/KSP-CKAN/NetKAN, done the way RP-1 does
it (the *metanetkan* pattern): the NetKAN repo holds a three-line YAML stub per module whose `$kref`
is `#/ckan/netkan/<raw URL of our netkan on main>`, and the full metadata stays in this repo, so later
list changes are a push here, not another PR. Three stubs: `RP-AXE`, `RP-AXE-Express-High`,
`RP-AXE-Express-Low`. The bot inflates them on the PR and comments with any error; a CKAN team member
reviews a new mod's first submission. Once merged, every new GitHub release is picked up automatically.

What the indexer taught us (netkan.exe is at https://ksp-ckan.s3-us-west-2.amazonaws.com/netkan.exe,
run `netkan.exe --verbose --outputdir <dir> --github-token $(gh auth token) <file>.netkan` before any PR):
- **A metapackage cannot be indexed**: "has no $kref field, this is required when no download url is
  specified". So the registry presets are not the local `kind: metapackage` files but 700-byte marker
  zips (`package_release.py --express-only` writes `dist/RP-AXE-Express-{High,Low}.zip`: a folder with an
  AVC file and a README) that ride on the mod's release, exactly like `RP-1-ExpressInstall-Graphics`.
  `gen_netkan.py` writes their netkans with `$kref .../asset_match/Express-High.zip`, `$vref ksp-avc`
  and `x_netkan_force_v`, and with **`RP-AXE` as a hard dependency**, so one tick installs everything.
- With three zips on one release, every netkan names its asset: the mod's `$kref` ends in
  `asset_match/RP-AXE-v.*zip$` (the `zip$` keeps the `.sha256` out).
- The version the registry shows is the GitHub tag's `v0.9.0`, and CKAN orders `v0.9.0` above `0.9.0`,
  so the local `RP-AXE-<ver>.ckan` now says `v0.9.0` too.
- `x_netkan_github.prereleases` is a filter (true = skip regular releases); absent = use both, which
  is what a beta that becomes a release wants. The earlier `prerelease` key was a misspelling.
- Warnings left as they are: `No plugin matching the identifier` (CKAN detects manual installs by a DLL
  named after the identifier; ours is `AXE.dll`), harmless.
`RP-AXE-deps.ckan` is a dev tool and is not submitted.

**Release assets, seven of them**: `RP-AXE-v<ver>.zip` + `.sha256`, `RP-AXE-<ver>.ckan`,
`RP-AXE-Express-{High,Low}.ckan` (pre-registry presets, no RP-AXE dependency) and
`RP-AXE-Express-{High,Low}.zip` (the registry markers). Re-upload with `gh release upload v<ver> ... --clobber`
after any `gen_netkan.py` change.

**SpaceDock** (https://spacedock.info): upload the same zip (byte-identical to the GitHub asset) as
version `0.9.0`, KSP 1.12.5, license `CC-BY-NC-SA`. **Leave "Request addition to CKAN" unticked**:
SpaceDock's bot would open a second NetKAN PR for the `RP-AXE` identifier with a SpaceDock `$kref`,
colliding with ours (GitHub kref). A new mod is private until *Publish*; SpaceDock refuses to create
one from a private profile. Later versions: *Update* on the mod page (version, KSP version,
changelog, zip, notify followers).

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
