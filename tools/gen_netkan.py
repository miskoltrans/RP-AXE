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

RSS_TEXTURES = {"any_of": [{"name": "RSSTextures4096"}, {"name": "RSSTextures8192"}, {"name": "RSSTextures16K"},
                           {"name": "RSSTextures2048"}]}
DEPENDS = [
    # the stack AXE's configs and plugin bind to directly
    "ModuleManager", "Harmony2", "ROUtils", "ModularFlightIntegrator", "KerbalChangelog",
    "RealismOverhaul", "RealSolarSystem", "Kerbalism", "Kerbalism-Config-RO", "ContractConfigurator",
    "CustomBarnKit", "ClickThroughBlocker", "ToolbarController", "KSCSwitcher", "RealAntennas", "Skopos",
    # FAR and RealAntennas hard-depend on the virtual `KSPBurst`, which has two providers (KSPBurst-Lite,
    # and the full KSPBurst that also provides Harmony2). A headless resolver dropped it (clean-room run
    # 2026-10-11): no Unity.Burst, FAR dead, RealAntennas' types unloadable, Skopos down with it. Name
    # the Lite provider: it takes the real Harmony2 we already depend on.
    "KSPBurst-Lite",
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
    # Scatterer comes in regardless (RealSolarSystem recommends Parallax, Parallax recommends Scatterer) and
    # then renders NOTHING, because `Scatterer-config` is a many-provider virtual that a headless resolver
    # drops silently (clean-room run 2026-10-11). Recommending the `-default` aliases keeps it coherent.
    "Scatterer", "Scatterer-config-default", "Scatterer-sunflare-default",
]
GRAPHICS_HIGH = [
    "Parallax", "Parallax-StockTextures", "RSSTextures16K", "RSSVE-HR", "DistantObject", "PlanetShine",
    "CanaveralPads", "PoodsMilkyWaySkybox",
]
GRAPHICS_LOW = ["RSSTextures4096", "DistantObject", "PlanetShine"]
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
         # the dev instance carries the full KSPBurst as well; Lite satisfies the same virtual name
         "KSPBurst-Lite": "KSPBurst"}

COMMENT = (
    "RELATIONSHIPS (generated by tools/gen_netkan.py; edit the lists there). depends = the stack AXE's configs "
    "and plugin bind to directly (RO/RSS/Kerbalism/ContractConfigurator/CustomBarnKit/RealAntennas/KSCSwitcher/Skopos, "
    "ROUtils+Harmony+MFI for AXE.dll) plus EVERY mod the tree places parts from (manifest/curated-parts.tsv): the "
    "tree is balanced against exactly that part set, and a missing one leaves nodes you pay science for and get "
    "nothing from. recommends = tools AXE integrates with when present and runs without. suggests = the author's "
    "RP-1-Express-High graphics preset (heavy; RP-AXE-Graphics-High.ckan / -Low.ckan import one in a go) and the "
    "DLCs, which CKAN cannot install (Breaking Ground carries the 28 robotics parts the tree places). Transitive "
    "deps are left to CKAN. 'Scatterer-config-default'/'-sunflare-default' on purpose: the bare virtual names have "
    "many providers and a headless resolver silently drops them. SCANsat = stock CKAN SCANsat. RP-AXE-deps.ckan is "
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
    extra = sorted(listed - env - set(ALIAS) - {"RSSTextures4096"})
    unknown = sorted(x for x in listed | set(CONFLICTS)
                     if x not in reg and x not in ALIAS and not x.endswith("-DLC") and x != "RSSTextures4096")
    print("dev-environment modules neither listed nor reachable through depends edges:", missing or "none")
    print("listed but not in the dev environment:", extra or "none")
    print("identifiers not installed here (must exist on CKAN -- verify by hand):", unknown or "none")
    return not missing


def meta(ident, name, abstract, deps, conflicts):
    return collections.OrderedDict([
        ("spec_version", "v1.26"), ("identifier", ident), ("name", name), ("abstract", abstract),
        ("author", ["miskoltrans"]), ("version", "0.9.0"), ("kind", "metapackage"), ("license", "CC-BY-NC-SA-4.0"),
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
    out["spec_version"] = "v1.26"   # any_of in depends
    # Beta: GitHub releases are marked pre-release, which netkan skips unless told to use them. Drop this at 1.0.
    out["x_netkan_github"] = {"prerelease": True}
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
    express = ["RP-AXE"] + RECOMMENDS
    dump(os.path.join(REPO, "RP-AXE-Express-High.ckan"), meta(
        "RP-AXE-Express-High", "RP-AXE Express (High graphics)",
        "RP-AXE with its recommended tools and the author's graphics set (RP-1 Express High: Parallax, 16K RSS "
        "textures, RSSVE-HR, DistantObject, PlanetShine, CanaveralPads, Pood's Milky Way skybox) as one hard set. "
        "About 8 GB more than Low. CKAN -> File -> Install from .ckan file, together with RP-AXE-<ver>.ckan until "
        "RP-AXE is on the registry; decline the further recommendations CKAN offers.",
        express + GRAPHICS_HIGH, ["RP-AXE-Express-Low", "RSSTextures4096", "RSSTextures8192", "RSSTextures2048"]))
    dump(os.path.join(REPO, "RP-AXE-Express-Low.ckan"), meta(
        "RP-AXE-Express-Low", "RP-AXE Express (Low graphics)",
        "RP-AXE with its recommended tools and a light graphics set (4K RSS textures, Scatterer, DistantObject, "
        "PlanetShine) as one hard set. CKAN -> File -> Install from .ckan file, together with RP-AXE-<ver>.ckan "
        "until RP-AXE is on the registry; decline the further recommendations CKAN offers.",
        express + GRAPHICS_LOW, ["RP-AXE-Express-High", "RSSTextures16K", "RSSTextures8192", "RSSTextures2048"]))
    print("wrote RP-AXE-Express-High.ckan (%d) and RP-AXE-Express-Low.ckan (%d)"
          % (len(express) + len(GRAPHICS_HIGH), len(express) + len(GRAPHICS_LOW)))

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
