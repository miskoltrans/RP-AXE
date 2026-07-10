namespace RPAxe
{
    // ModuleNonReentryRated and ModuleUnpressurizedCockpit are no longer empty stubs — they carry
    // real behaviour again (Source/AXE/PartModules/), and the tagging that puts them on parts lives
    // in GameData/RP-AXE/design/Parts/AxeReentryPressurization.cfg. The contract PartValidation
    // checks that reference them (NONE { partModule = ... }) now enforce something.

    /// <summary>
    /// Empty marker added by RP-AXE's tree patches to every part we place or re-route, so our
    /// changes are distinguishable from base RO/RP-1 in-game: a Filter Extensions subcategory
    /// "RP-AXE" filters on this module (type = moduleName), and we also append a `rp-axe` search
    /// tag + a "[RP-AXE]" description note. No behaviour.
    /// </summary>
    public class ModuleAxeMarker : PartModule { }
}
