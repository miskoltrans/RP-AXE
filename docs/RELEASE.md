# RP-AXE — Packaging & Release (M7)

Artifacts: `RP-AXE.netkan` (CKAN metadata), `GameData/RP-AXE/RP-AXE.version` (KSP-AVC), `LICENSE.md`
(CC-BY-NC-SA-4.0). Target: **KSP 1.12.0–1.12.5**.

## Before first release — remaining
- **Owner/author/URLs: DONE** — set to `miskoltrans` / repo `miskoltrans/RP-AXE` in `RP-AXE.netkan`
  and `GameData/RP-AXE/RP-AXE.version`.
- The `.version` raw URL assumes the default branch is **`main`** — if the repo uses `master`, fix it.
- No git remote yet (`git remote add origin git@github.com:miskoltrans/RP-AXE.git`) and the GitHub repo
  isn't created — both are prerequisites for tagging/release and the `$kref` to resolve.
- AutoTest harness ships **disabled** (`Plugins/PluginData/AutoTest.cfg` `enabled = false`); the
  `-axe-autotest` launch flag force-enables it for development.

## Build the release payload
1. Build the plugin into the shipped folder:
   `KSPRoot=<instance> dotnet build Source/AXE/AXE.csproj -c Release` → outputs `GameData/RP-AXE/Plugins/AXE.dll`.
2. Bump the version in `GameData/RP-AXE/RP-AXE.version` (and tag, below).
3. Zip the mod folder so the archive root is `GameData/RP-AXE/...`:
   `RP-AXE-vX.Y.Z.zip` containing `GameData/RP-AXE/` (seed + design + Plugins + PluginData + *.version).
   Exclude `Source/`, `docs/`, `tools/`, `.git` — only `GameData/RP-AXE` ships.
4. `git tag vX.Y.Z && git push --tags`; create a GitHub **Release** for that tag and attach the zip.
   CKAN's `#/ckan/github/<owner>/RP-AXE` `$kref` reads the release + the `.version` for KSP compat.

## Publish to CKAN (optional, when ready)
- Validate the netkan: run it through the [NetKAN inflator] (or `netkan RP-AXE.netkan`) and confirm it
  resolves all `depends` identifiers (the installed test instance proves they exist — see below).
- Submit `RP-AXE.netkan` to the CKAN-meta repo (PR). Until then, users add it locally.

## Clean-room install test (the M7 "prove")
Goal: a stranger installs from metadata with **zero manual steps** and gets a working, plugin-free,
RP-1-conflicting install.

1. New CKAN instance on a **fresh KSP 1.12.5** (no RO/RP-1 present).
2. Add `RP-AXE.netkan` locally; install `RP-AXE`.
3. Verify CKAN auto-pulls the realism stack + part packs and **refuses** if `RP-1` is selected
   (the `conflicts` rule).
4. Verify the install contains **`GameData/RP-AXE/`** and **no `GameData/RP-1/`**, no `RP0.dll`/`CC_RP0.dll`.
5. Launch; start a Career; confirm: tree renders, ~100k funds, `start` node has the basic parts,
   Mission Control offers contracts. (Mirrors what `-axe-autotest` checks, but from a clean CKAN install.)

> The current `Instance/` is the *reference* working set: its 104 CKAN modules (minus `RP-1`, `Skopos`,
> `TestFlight`, and pure tooling) are exactly the netkan `depends`. So the depends list is already
> proven to resolve and run together — the clean-room test confirms it installs from scratch unattended.

## Dependency notes (see docs/DEPENDENCIES.md)
- Transitive deps (Kopernicus, RealHeat, FAR, AJE, B9PartSwitch, CommunityResourcePack, ROLib's deps…)
  are **not** listed — CKAN resolves them from RealismOverhaul / the part packs.
- Tantares CKAN identifiers are `NewTantares` / `NewTantaresLV` (+ `TantaresSP`).
- `RP-1` → `conflicts`. `Skopos` (advanced comms contracts) and `TestFlight` (part failures) → `suggests`
  (off by default for the lightweight MVP). DLCs: `MakingHistory-DLC` is a hard dep (parts are placed);
  `BreakingGround-DLC` is `recommends`.
