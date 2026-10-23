#!/usr/bin/env python3
"""Generate RP-AXE.netkan's relationship lists (+ the two graphics metapackages) from ONE classification,
and prove the classification covers the dev environment.

    python tools/gen_netkan.py

The classification lives here, not in the JSON, so the reasoning travels with it:

  depends    = the stack AXE's configs and plugin bind to directly, PLUS every mod the tree places parts
               from (manifest/curated-parts.tsv). The tree is balanced against exactly that part set; a
               missing one leaves nodes you pay science for and get nothing from.
  recommends = tools AXE integrates with when present and runs without (installed by default, untickable).
  suggests   = the author's graphics preset (heavy; RP-AXE-Graphics-High.ckan / -Low.ckan import one in
               a go) and the DLCs, which CKAN cannot install.
  conflicts  = what RP-AXE replaces (RP-1's career layer, other trees, other simulators, other RTG models).

Coverage check: every module in RP-AXE-deps.ckan (the dev environment) must be listed here or reachable
through `depends` edges of a listed module, read from the live CKAN registry -- otherwise the player
install silently differs from the one the tree was built against.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
REGISTRY = os.path.normpath(os.path.join(REPO, "..", "Instance", "CKAN", "registry.json"))

# Sol-Core (RSS-Reborn's planet pack, its own CKAN repo) `provides: RealSolarSystem` and ships its own
# textures, so it closes this choice too. Without it a GUI player on Sol is asked to pick an RSS texture
# pack, which then loads gigabytes of textures for bodies that do not exist. Unknown on the default
# registry, where it is simply never chosen. docs/SOL.md.
RSS_TEXTURES = {"any_of": [{"name": "RSSTextures4096"}, {"name": "RSSTextures8192"}, {"name": "RSSTextures16K"},
                           {"name": "RSSTextures2048"}, {"name": "Sol-Core"}]}
DEPENDS = [
    # the stack AXE's configs and plugin bind to directly
    "ModuleManager", "Harmony2", "ROUtils", "ModularFlightIntegrator", "KerbalChangelog",
    "RealismOverhaul", "RealSolarSystem", "Kerbalism", "Kerbalism-Config-RO", "ContractConfigurator",
    "CustomBarnKit", "ClickThroughBlocker", "ToolbarController", "KSCSwitcher", "RealAntennas", "Skopos",
    # FAR and RealAntennas hard-depend on the virtual `KSPBurst`, which has two providers: KSPBurst-Lite
    # (the Burst runtime) and the full KSPBurst (runtime + the Burst compiler package, 392 MB, depends on
    # Lite). A headless resolver dropped the virtual (clean-room run 2026-10-11): no Unity.Burst, FAR dead,
    # RealAntennas' types unloadable, Skopos down with it. Name a provider. The full one: it is what the
    # dev instance and RP-1 Express run, and Burst-compiled FAR / RealAntennas / KSPTextureLoader are a
    # real performance win on an RO part count.
    "KSPBurst",
    # RSS needs a texture pack and declares it as the virtual `RSSTextures`. A headless CKAN resolver DROPS a
    # virtual dependency that has several providers (exit 0, no planet textures -- clean-room run 2026-10-11),
    # so the choice is named here: an any_of, light pack first (the headless default; the GUI prompts).
    RSS_TEXTURES,
    # every mod the tree places parts from (manifest/curated-parts.tsv)
    "SXTContinued", "VenStockRevamp-NewParts", "ROEngines", "ROCapsules", "ROTanks", "ROSolar", "ROHeatshields",
    "ProceduralParts", "ProceduralFairings", "B9-PWings-Fork", "ReStock", "ReStockPlus", "ModularLaunchPads",
    "KSPWheel", "KerbalFoundriesContinued", "ConformalDecals", "SCANsat", "StationPartsExpansionRedux",
    "UniversalStorage2", "Coatl-Aerospace-Redux", "RN-USProbesPack", "RN-SovietProbes", "NewTantares",
    "KerwisChinaAerospacePack", "HullcamVDSContinued", "NearFutureAeronautics", "NearFutureConstruction",
    "NearFutureElectrical", "NearFutureExploration", "NearFutureLaunchVehicles", "NearFuturePropulsion",
    "NearFutureSolar", "FarFutureTechnologies", "KerbalAtomics", "CryoEngines", "RocketMotorMenagerie",
]
RECOMMENDS = [
    "MechJeb2", "TestFlight", "KerbalAlarmClock", "StockAlarmClockDisabler", "TransferWindowPlannerFork",
    "TargetInterceptPlanner", "BetterTimeWarpCont", "RSSDateTimeFormatter", "KerbalRenamer", "TextureReplacer",
    "AtmosphereAutopilot", "RCSBuildAid", "EditorExtensionsRedux", "HangerExtenderExtended", "Waterfall",
    "TexturesUnlimited", "Shabby", "Resurfaced", "Firefly", "ZTheme", "ROLoadingImages",
    "KSPTextureLoader",
]
GRAPHICS_HIGH = [
    "Parallax", "Parallax-StockTextures", "RSSTextures16K", "RSSVE-HR",
    # Scatterer belongs WITH RSSVE, not on its own. Its `-config` is StockScattererConfigs, a planet list of
    # STOCK bodies; it is RSSVE's patch (@Scatterer_planetsList:FOR[RSSVE]) that retargets the list to RSS.
    # Without RSSVE it logs "ScattererCelestialBody Kerbin not found" for every stock body and renders
    # nothing (clean-room run 5, 2026-10-12, the first unlocked boot). Recommending it alone (runs 2-4)
    # bought a 7 MB no-op, so it sits next to RSSVE-HR here and the Low preset mirrors RP-1 Express
    # Graphics-Low: textures only. The `-default` aliases, never the bare virtual names: a headless resolver
    # drops a many-provider virtual silently (run 2026-10-11).
    "Scatterer", "Scatterer-config-default", "Scatterer-sunflare-default",
    "DistantObject", "PlanetShine", "CanaveralPads", "PoodsMilkyWaySkybox",
]
GRAPHICS_LOW = ["RSSTextures4096", "DistantObject", "PlanetShine"]
# Sol instead of RSS (docs/SOL.md). Every pack NAMED: Sol-Core depends on virtual per-system packs
# (Sol-EarthSystem has 4k/8k/16k providers) and on the virtual ParallaxContinued, all of which a headless
# resolver drops; and the three ParallaxContinued texture packs, hard deps of ParallaxContinued-KTL that
# Sol's Parallax configs read ~2,500 times, were dropped too, exit 0 (Sol run, 2026-10-23). Scatterer and
# EVE arrive through Sol-Visuals, which also provides their Sol configs.
SOL_PACKS = ["Sol-Core", "Sol-Configs", "Sol-Visuals", "Sol-Launchsites-256x"] + [
    "Sol-%s-4k" % s for s in ("Sun", "Mercury", "Venus", "EarthSystem", "MarsSystem", "JupiterSystem",
                              "SaturnSystem", "UranusSystem", "NeptuneSystem", "AsteroidBelt", "KuiperBelt")]
GRAPHICS_SOL = SOL_PACKS + [
    "ParallaxContinued-KTL", "ParallaxContinued-Terrain-Textures", "ParallaxContinued-Scatter-Textures",
    "ParallaxContinued-Planet-Textures", "DistantObject", "PlanetShine"]
# identifiers that live only in the Sol repository (https://github.com/RSS-Reborn/CKAN-meta)
SOL_REPO_ONLY = set(SOL_PACKS) | {"ParallaxContinued-KTL"}
# (the texture pack is already offered through the any_of in DEPENDS)
SUGGESTS = [g for g in GRAPHICS_HIGH if not g.startswith("RSSTextures")] + ["BreakingGround-DLC", "MakingHistory-DLC"]
CONFLICTS = [
    "RP-1", "RP-0", "RONoCareer", "KerbalConstructionTime", "CommunityTechTree", "HideEmptyTechNodes",
    "MechJebForAll", "KRASH", "NearFutureElectrical-DecayingRTGs", "CrowdSourcedScience",
    # The curated part set is ReStock + VenStockRevamp-NewParts. The full VenStockRevamp (stock-model
    # replacement) conflicts with ReStock, and VenStockRevamp-Core RECOMMENDS it -- a headless CKAN install
    # of RP-AXE adds the recommends of every dependency and then fails on that pair (clean-room run,
    # 2026-10-11). Declaring the conflict here keeps the resolver from reaching for it.
    "VenStockRevamp",
]
# `provides` aliases the registry records under the provider's own name
ALIAS = {"Scatterer-config-default": "Scatterer-config", "Scatterer-sunflare-default": "Scatterer-sunflare",
         }

# `description` is the long text CKAN shows in the mod's info panel BEFORE install -- the one place a
# registry-path player reads anything of ours. It has to explain the recommendations dialog, because
# CKAN relays every dependency's own recommends (ModularLaunchPads -> BDB, RSS -> Parallax, the capsule
# mods -> IVAs) with no way for us to annotate or suppress them.
DESCRIPTION = (
    "RP-AXE is a career for the Realism Overhaul stack that replaces RP-1's career plugin: a tech tree of about "
    "530 nodes built from scratch and organised by engineering discipline, science as the only gate, no build "
    "times, facility upkeep, tooling or crew training. It conflicts with RP-1; install one or the other.\n\n"
    "INSTALLING. The easy path is an RP-AXE Express preset (High or Low graphics; on the GitHub release page "
    "until the presets reach the CKAN registry): it carries the recommended tools and a graphics set as hard "
    "dependencies. Install the preset first, then RP-AXE. Every mod the tree places parts from is a hard "
    "dependency of RP-AXE, so nothing in the recommendations CKAN offers afterwards is needed: those come from "
    "the dependencies themselves (ModularLaunchPads recommends Bluedog Design Bureau, RSS recommends Parallax, "
    "the capsule mods recommend IVAs) and the tree places nothing from them. Untick them and continue unless "
    "you want them for your own building. Then start a new Career."
)
EXPRESS_DESCRIPTION = (
    "Install this preset FIRST, then RP-AXE-<version>.ckan, both from the RP-AXE release page until RP-AXE is on "
    "the CKAN registry (CKAN -> File -> Install from .ckan file, one file per install). Everything RP-AXE needs is "
    "a hard dependency of the preset or of the mod. The further recommendations CKAN offers come from the "
    "dependencies themselves (Bluedog Design Bureau via ModularLaunchPads, Parallax via RSS, IVA mods via the "
    "capsules) and the tree places nothing from them: untick them and press Continue. Do not press Cancel, "
    "which aborts the whole install."
)

EXPRESS_SOL_DESCRIPTION = (
    "RP-AXE on Sol instead of Real Solar System. FIRST add Sol's metadata repository to CKAN (Settings -> "
    "Metadata Repositories -> New -> Sol, or the URL https://github.com/RSS-Reborn/CKAN-meta/archive/main.tar.gz) "
    "and refresh. Then install this preset, then RP-AXE-<version>.ckan (CKAN -> File -> Install from .ckan file, "
    "one file per install). The preset names Sol's 4K packs and every texture pack Sol reads, so no choice is "
    "left for CKAN to skip. Decline the further recommendations CKAN offers; do not press Cancel. Full notes: "
    "docs/SOL.md in the RP-AXE repository."
)

EXPRESS_DESCRIPTION_REGISTRY = (
    "A one-click RP-AXE install: the mod, the Realism Overhaul stack and every part mod the tree places, the "
    "recommended tools, and a graphics set, all as hard dependencies. Everything RP-AXE needs is in here. The "
    "recommendations CKAN offers on top come from the dependencies themselves (Bluedog Design Bureau via "
    "ModularLaunchPads, Parallax via RSS, IVA mods via the capsules) and the tree places nothing from them: "
    "untick them and press Continue. Do not press Cancel, which aborts the whole install. Then start a new Career."
)

COMMENT = (
    "RELATIONSHIPS (generated by tools/gen_netkan.py; edit the lists there). depends = the stack AXE's configs "
    "and plugin bind to directly (RO/RSS/Kerbalism/ContractConfigurator/CustomBarnKit/RealAntennas/KSCSwitcher/Skopos, "
    "ROUtils+Harmony+MFI for AXE.dll) plus EVERY mod the tree places parts from (manifest/curated-parts.tsv): the "
    "tree is balanced against exactly that part set, and a missing one leaves nodes you pay science for and get "
    "nothing from. recommends = tools AXE integrates with when present and runs without. suggests = the author's "
    "RP-1-Express-High graphics preset (heavy; RP-AXE-Express-High.ckan / -Low.ckan import one in a go) and the "
    "DLCs, which CKAN cannot install (Breaking Ground carries the 28 robotics parts the tree places). Transitive "
    "deps are left to CKAN. Scatterer is in suggests, with RSSVE-HR: its default config lists stock bodies and only "
    "RSSVE's patch retargets it to RSS, so alone it renders nothing. 'Scatterer-config-default'/'-sunflare-default' "
    "on purpose: the bare virtual names have many providers and a headless resolver silently drops them. "
    "SCANsat = stock CKAN SCANsat. RP-AXE-deps.ckan is "
    "the author's full dev environment (everything here as hard deps, High graphics). Conflicts: RP-AXE replaces "
    "the RP-1 career layer and ships its own tree, simulator and RTG model."
)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)
        f.write("\n")


def dep_names(reg, m):
    out = []
    for d in reg.get(m, {}).get("source_module", {}).get("depends", []):
        if "name" in d:
            out.append(d["name"])
        elif "any_of" in d:
            out.extend(x["name"] for x in d["any_of"] if "name" in x)
    return out


def check_coverage(reg, env):
    plain = [d for d in DEPENDS if isinstance(d, str)]
    anyof = [x["name"] for d in DEPENDS if isinstance(d, dict) for x in d["any_of"]]
    listed = set(plain) | set(anyof) | set(RECOMMENDS) | set(SUGGESTS)
    assert len(listed) == len(plain) + len(anyof) + len(RECOMMENDS) + len(SUGGESTS), "an identifier is in two lists"
    reach, stack = set(), list(listed)
    while stack:
        m = stack.pop()
        if m in reach:
            continue
        reach.add(m)
        stack.extend(dep_names(reg, m))
    # a module satisfies every virtual name it `provides` (FAR -> FerramAerospaceResearchContinued, ...)
    provides = {}
    for m, v in reg.items():
        for pv in v.get("source_module", {}).get("provides", []):
            provides.setdefault(pv, set()).add(m)
    for name in list(reach):
        reach |= provides.get(name, set())
    reach |= {ALIAS[a] for a in ALIAS if a in reach}
    missing = sorted(env - reach - {"RP-AXE-deps"})
    extra = sorted(listed - env - set(ALIAS) - {"RSSTextures4096"} - SOL_REPO_ONLY)
    unknown = sorted(x for x in listed | set(CONFLICTS)
                     if x not in reg and x not in ALIAS and not x.endswith("-DLC") and x != "RSSTextures4096"
                     and x not in SOL_REPO_ONLY)
    print("dev-environment modules neither listed nor reachable through depends edges:", missing or "none")
    print("listed but not in the dev environment:", extra or "none")
    print("identifiers not installed here (must exist on CKAN -- verify by hand):", unknown or "none")
    return not missing


def meta(ident, name, abstract, deps, conflicts, description=EXPRESS_DESCRIPTION):
    return collections.OrderedDict([
        ("spec_version", "v1.26"), ("identifier", ident), ("name", name), ("abstract", abstract),
        ("description", description), ("author", ["miskoltrans"]), ("version", "0.9.0"), ("kind", "metapackage"), ("license", "CC-BY-NC-SA-4.0"),
        ("ksp_version_min", "1.12.0"), ("ksp_version_max", "1.12.5"),
        ("depends", [{"name": n} for n in deps]), ("conflicts", [{"name": n} for n in conflicts]),
    ])


def main():
    reg = load(REGISTRY)["installed_modules"]
    nk = load(os.path.join(REPO, "RP-AXE.netkan"))
    deps_ckan = load(os.path.join(REPO, "RP-AXE-deps.ckan"))
    env = {d["name"] for d in deps_ckan["depends"]}
    ok = check_coverage(reg, env)

    out = collections.OrderedDict()
    for k in ["spec_version", "identifier", "name", "abstract", "author", "license", "$kref", "$vref", "tags"]:
        out[k] = nk[k]
        if k == "abstract":
            out["description"] = DESCRIPTION
    out["spec_version"] = "v1.26"   # any_of in depends
    # GitHub pre-releases: netkan's `x_netkan_github.prereleases` is a FILTER -- true = skip regular releases,
    # false = skip pre-releases, ABSENT = use both (Spec.md). Absent is right for a beta that becomes a release;
    # the earlier `{"prerelease": true}` was a misspelt key netkan would have ignored.
    # The release carries three zips (the mod + the two Express markers), so each netkan must say which
    # asset is its download. Regex against the asset NAMES; `zip$` keeps the .sha256 out.
    out["$kref"] = "#/ckan/github/miskoltrans/RP-AXE/asset_match/RP-AXE-v.*zip$"
    out["comment"] = COMMENT
    out["depends"] = [d if isinstance(d, dict) else {"name": d} for d in DEPENDS]
    out["recommends"] = [{"name": n} for n in RECOMMENDS]
    out["suggests"] = [{"name": n} for n in SUGGESTS]
    out["conflicts"] = [{"name": n} for n in CONFLICTS]
    out["install"] = nk["install"]
    out["resources"] = nk["resources"]
    dump(os.path.join(REPO, "RP-AXE.netkan"), out)
    print("RP-AXE.netkan: depends %d (+1 any_of), recommends %d, suggests %d, conflicts %d"
          % (len(DEPENDS) - 1, len(RECOMMENDS), len(SUGGESTS), len(CONFLICTS)))

    # One-click presets in the RP-1 Express mould: RP-AXE + its recommends + a graphics set, all as hard
    # deps. Installed WITH --no-recommends (CLI) or by declining the dependencies' own recommendations
    # (GUI), they give exactly the curated environment and nothing the tree never placed.
    # They do NOT depend on "RP-AXE": a local .ckan passed with -c is an install target, not a
    # registry entry, so a metapackage naming it fails "Unsatisfied dependency RP-AXE" until the
    # mod is on the CKAN registry (clean-room run 4, 2026-10-11). Install both files together.
    express = RECOMMENDS
    dump(os.path.join(REPO, "RP-AXE-Express-High.ckan"), meta(
        "RP-AXE-Express-High", "RP-AXE Express (High graphics)",
        "The recommended tools for RP-AXE plus the author's graphics set (RP-1 Express High: Parallax, 16K RSS "
        "textures, RSSVE-HR with Scatterer, DistantObject, PlanetShine, CanaveralPads, Pood's Milky Way skybox) as "
        "one hard set. "
        "About 8 GB more than Low. CKAN -> File -> Install from .ckan file, together with RP-AXE-<ver>.ckan until "
        "RP-AXE is on the registry; decline the further recommendations CKAN offers.",
        express + GRAPHICS_HIGH,
        ["RP-AXE-Express-Low", "RP-AXE-Express-Sol", "RSSTextures4096", "RSSTextures8192", "RSSTextures2048", "Sol-Core"]))
    dump(os.path.join(REPO, "RP-AXE-Express-Low.ckan"), meta(
        "RP-AXE-Express-Low", "RP-AXE Express (Low graphics)",
        "The recommended tools for RP-AXE plus a light graphics set (4K RSS textures, DistantObject, PlanetShine; "
        "no Scatterer or clouds, like RP-1 Express Graphics-Low) as one hard set. CKAN -> File -> Install from "
        ".ckan file, together with RP-AXE-<ver>.ckan; "
        "decline the further recommendations CKAN offers.",
        express + GRAPHICS_LOW,
        ["RP-AXE-Express-High", "RP-AXE-Express-Sol", "RSSTextures16K", "RSSTextures8192", "RSSTextures2048", "Sol-Core"]))
    # Sol: a release asset only, never a registry netkan -- its packs live in Sol's own CKAN repository,
    # which the default registry cannot resolve. RSSVE would stack a second EVE/Scatterer config on
    # Sol-Visuals' own.
    dump(os.path.join(REPO, "RP-AXE-Express-Sol.ckan"), meta(
        "RP-AXE-Express-Sol", "RP-AXE Express (Sol)",
        "The recommended tools for RP-AXE plus the Sol planet pack (4K) instead of Real Solar System, with every "
        "Sol texture pack named. Needs Sol's CKAN repository added first. CKAN -> File -> Install from .ckan file, "
        "then RP-AXE-<ver>.ckan; decline the further recommendations CKAN offers.",
        express + GRAPHICS_SOL,
        ["RP-AXE-Express-High", "RP-AXE-Express-Low", "RSSTextures4096", "RSSTextures8192", "RSSTextures16K",
         "RSSTextures2048", "RSSVE-HR", "RSSVE-LR"],
        description=EXPRESS_SOL_DESCRIPTION))
    print("wrote RP-AXE-Express-High.ckan (%d), RP-AXE-Express-Low.ckan (%d), RP-AXE-Express-Sol.ckan (%d)"
          % (len(express) + len(GRAPHICS_HIGH), len(express) + len(GRAPHICS_LOW), len(express) + len(GRAPHICS_SOL)))

    # Registry variants, submitted to KSP-CKAN/NetKAN the way RP-1 does it: a one-line stub there
    # (`$kref: #/ckan/netkan/<raw URL of this file>`) and the full metadata here. These DO depend on
    # RP-AXE, so one tick in CKAN installs everything -- possible only on the registry, where RP-AXE is
    # a known identifier. Same lists as the .ckan files otherwise. NOT metapackages: the indexer refuses
    # a netkan with neither $kref nor download ("required when no download url is specified"), so, like
    # RP-1-ExpressInstall-Graphics, each preset is a 1 KB marker zip (package_release.py writes them,
    # they ride on the mod's release) selected by `asset_match`, with the version read from its AVC
    # file and `x_netkan_force_v` so it shows as "v0.9.0" like the mod.
    for ident, tier in (("RP-AXE-Express-High", "High (RP-1 Express High: Parallax, 16K textures, RSSVE-HR, Scatterer)"),
                        ("RP-AXE-Express-Low", "Low (4K textures only)")):
        m = load(os.path.join(REPO, ident + ".ckan"))
        r = collections.OrderedDict()
        r["spec_version"] = "v1.26"
        r["identifier"] = ident
        r["name"] = m["name"]
        r["abstract"] = "One-click RP-AXE: the mod, its stack and tools, and the %s graphics set." % tier
        r["description"] = EXPRESS_DESCRIPTION_REGISTRY
        r["author"] = m["author"]
        r["license"] = m["license"]
        r["tags"] = ["config", "career", "graphics"]   # the indexer warns on a tagless module
        r["$kref"] = "#/ckan/github/miskoltrans/RP-AXE/asset_match/%s.zip" % ident.rsplit("-", 1)[1].join(("Express-", ""))
        r["$vref"] = "#/ckan/ksp-avc"
        r["x_netkan_force_v"] = True
        r["resources"] = nk["resources"]
        r["depends"] = [{"name": "RP-AXE"}] + m["depends"]
        r["conflicts"] = m["conflicts"]
        r["install"] = [{"find": ident, "install_to": "GameData"}]
        dump(os.path.join(REPO, ident + ".netkan"), r)
    print("wrote RP-AXE-Express-High.netkan and RP-AXE-Express-Low.netkan (registry variants, depend on RP-AXE)")

    deps_ckan["abstract"] = (
        "The author's complete RP-AXE development environment as ONE hard-dependency set: every module "
        "RP-AXE.netkan lists under depends/recommends/suggests (High graphics included), so a clean CKAN instance "
        "reproduces the test install verbatim. Players normally install RP-AXE itself and choose graphics at the "
        "prompts. SCANsat is deliberately absent here (the dev instance runs a fork); RP-AXE.netkan depends on "
        "CKAN SCANsat.")
    deps_ckan["version"] = "0.9.0"
    dump(os.path.join(REPO, "RP-AXE-deps.ckan"), deps_ckan)
    print("RP-AXE-deps.ckan: abstract + version updated")
    if not ok:
        raise SystemExit("coverage FAILED -- classify the modules above")


if __name__ == "__main__":
    main()
