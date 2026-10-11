# License & Attribution

## RP-AXE

RP-AXE (Ahistorical Xploration & Engineering) — configuration, tree data, tools and the `AXE.dll`
plugin source — is licensed under
**Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC-BY-NC-SA-4.0)**.

- Human-readable summary: https://creativecommons.org/licenses/by-nc-sa/4.0/
- Full legal code: https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

You are free to share and adapt this material for non-commercial purposes, provided you give
appropriate credit and license your derivatives under the same terms.

## Attribution — this is a derivative work

RP-AXE is built on, vendors, and adapts work from the projects below. Every one of them is
CC-BY-NC-SA-4.0 or more permissive, so the whole ships under CC-BY-NC-SA-4.0.

- **Realistic Progression One (RP-1)** — © the RP-0/RP-1 contributors
  (https://github.com/KSP-RO/RP-0/graphs/contributors), CC-BY-NC-SA-4.0.
  https://github.com/KSP-RO/RP-1
  - `GameData/RP-AXE/seed/` is imported pristine from RP-1 v4.4.0.0 (Tree, Contracts, Science
    and Parts — including the part models and textures under `seed/Parts/`, some of which RP-1
    itself derives from **Bluedog Design Bureau** by CobaltWolf and team, CC-BY-NC-SA-4.0) and
    transformed by the ModuleManager patches in `GameData/RP-AXE/design/`.
  - `AXE.dll` does **not** ship or wrap RP-1's compiled plugins (`RP0.dll`, `CC_RP0.dll`, KCT), but
    several of its modules are ported or adapted from the RP-1 plugin **source**: the airlaunch
    routine and envelopes, the avionics control-locker and debris rules, range safety, the
    non-reentry-rated thermal hook, the dev-parts toggle, the Kerbalism EC→SI unit patches, the
    engine-upgrade tooltip, the F7 clear-input-locks key, the first-EVA log transpiler, the ΔV
    settings and the science-value helper. Each file names its origin in its header. RP-1's
    source in turn includes code from magico13's FlightSchool and from KerbalConstructionTime
    (magico13 and Linuxgurugamer, relicensed CC-BY-NC-SA-4.0 by permission).
- **ROUtils** — © KSP-RO Group, CC-BY-NC-SA-4.0. https://github.com/KSP-RO/ROUtils
  The vessel-teleport primitive (`AxeVesselTeleport.cs`) is ported self-contained from ROUtils'
  `HyperEdit_Utilities`, itself descended from the HyperEdit lander by khyperia and Ezriilc, via
  KerbalConstructionTime.
- **Kerbalism Lab Experiments Expanded Continued** — © John Absher, CC-BY-NC-SA-4.0, continuing
  RoadWarrior9's *Kerbalism Lab Experiments Expanded*.
  https://github.com/johnabsher/KerbalismLabExperimentsExpandedContinued
  The 65 crewed-station experiments under `design/Science/KerbalismLab/Experiments/` are vendored
  as authored, with only their tech gates remapped to AXE nodes.
- **KerbalismScienceOnly** — by gotmachine and the Kerbalism contributors, released into the public
  domain (Unlicense). https://github.com/Kerbalism/KerbalismScienceOnly
  The minimal lab-science framework under `design/Science/KerbalismLab/Framework-*.cfg` is taken
  from it.
- **Less Real Than Real (LRTR)** — © pehvbot, CC-BY-NC-SA-4.0. https://github.com/pehvbot/LRTR
  Used as a reference for per-part entry-cost values.

No Squad / Private Division game assets are redistributed: the tech-tree node icons are the stock
`RDicon_*` names, resolved from the game's own icon atlas at run time.

RP-AXE is not affiliated with or endorsed by the RP-1 Group, the KSP-RO Group, pehvbot or any of
the authors above. Dependency mods retain their own respective licenses.
