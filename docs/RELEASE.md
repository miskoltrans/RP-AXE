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
- [x] `RP-AXE.netkan` `depends` = the full `RP-AXE-deps.ckan` set (114 incl. `SCANsat`), with the
      `-default` Scatterer aliases (a bare virtual name is silently dropped by a headless resolver),
      `$vref` reading the AVC file for KSP compatibility.
- [x] Shipped `_README.md`s describe the folders as they are; `design/` no longer cites deleted docs.
- [x] Version 1.0.0 in `RP-AXE.version`; changelog in-game and in the repo.
- [x] `tools/package_release.py` builds the archive from git-tracked files + the fresh DLL and
      refuses LFS pointers, stale DLLs and dev artifacts (`craft-prices.csv`, `.gitkeep`).

Still needs you (each is outward-facing or needs credentials):

- [ ] **GitHub.** `gh auth login`; create `miskoltrans/RP-AXE` (public); `git remote add origin
      git@github.com:miskoltrans/RP-AXE.git`; `git lfs push --all origin main` then `git push -u origin
      main`. The `.version` `URL` and the netkan `$kref` both assume that owner/repo and branch `main`.
      **Before the first push**, decide about history: commits `0117cd3` and `77d534a` added the Squad
      icon PNGs, and they stay reachable in history after `3ab97d1` removed them. Shipping the release
      zip is clean either way; if you want the repo itself free of them, that is a `git filter-repo`
      before anyone has cloned — a history rewrite, so coordinate with any other session on `main`.
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

## Dependency notes

- `depends` lists every module the environment installs by request — the RP-1 Express set minus
  RP-1, the 21 curated expansion part mods, and `SCANsat`. Transitive deps (Kopernicus, FAR, AJE,
  DynamicBatteryStorage, KerbalKonstructs, SystemHeat, …) are left to CKAN.
- `Scatterer-config-default` / `Scatterer-sunflare-default`, never the bare virtual names: a
  metapackage `depends` on a name with many providers is dropped silently, exit 0 (A/B-verified on
  ckan 1.36.4; the result is a Scatterer that renders no atmosphere at all).
- SCANsat: the dev instance runs the `miskoltrans/SCANsat-GPU` fork (not on CKAN); the public
  dependency is stock CKAN `SCANsat`, which carries the same part names the tree places.
- `RP-1` → `conflicts`. Both DLCs are hard deps (parts from both are placed in the tree).
- `RP-AXE-deps.ckan` is the dev-instance metapackage and deliberately omits `SCANsat` (the rebuild
  script installs the fork instead); keep the two lists otherwise identical.

## AutoTest harness

Ships **disabled** (`Plugins/PluginData/AutoTest.cfg` `enabled = false`); the `-axe-autotest` launch
flag force-enables it. The localhost bridge (`Bridge.cfg`) is written on first run with
`enabled = false` and is gitignored, so a player never gets a listener unless they turn it on.
