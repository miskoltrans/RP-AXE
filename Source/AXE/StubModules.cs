namespace RPAxe
{
    // Empty stand-ins for two RP-1 PartModules we axed with the plugin. They carry no behaviour;
    // they exist only so the *type names* resolve. RP-1 contracts use them in PartValidation
    // checks (e.g. NONE { partModule = ModuleNonReentryRated } = "no parts that aren't reentry
    // rated"); ContractConfigurator rejects a PartValidation whose partModule type isn't loaded,
    // which was dropping several early crewed/test-flight contracts. No part carries these modules
    // now (RP-1's Avionics/part configs that added them aren't vendored), so the NONE checks pass
    // trivially — exactly right, since the underlying reentry/pressurisation system is gone.
    //
    // Class names MUST match RP-1's exactly (KSP/CC resolve PartModules by class name).
    public class ModuleNonReentryRated : PartModule { }

    public class ModuleUnpressurizedCockpit : PartModule { }

    /// <summary>
    /// Empty marker added by RP-AXE's tree patches to every part we place or re-route, so our
    /// changes are distinguishable from base RO/RP-1 in-game: a Filter Extensions subcategory
    /// "RP-AXE" filters on this module (type = moduleName), and we also append a `rp-axe` search
    /// tag + a "[RP-AXE]" description note. No behaviour.
    /// </summary>
    public class ModuleAxeMarker : PartModule { }
}
