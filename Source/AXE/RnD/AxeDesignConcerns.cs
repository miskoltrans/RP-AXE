using HarmonyLib;
using KSP.UI.Screens;
using PreFlightTests;

namespace RPAxe
{
    /// <summary>
    /// Registers extra stock pre-flight design-concern tests that KSP ships but doesn't enable by
    /// default — real engineering validators with no economy coupling, ported from the useful half of
    /// RP-1's EngineersReport patch:
    ///   * NoControlSources      — catches the classic "no probe core / no crew = uncontrollable" build.
    ///   * ParachuteOnEngineStage — a chute set to deploy on a stage that still fires an engine.
    ///   * KerbalSeatCollision   — external command seat that would clip on launch.
    /// A postfix (not a method replacement) so it simply appends to stock's default test set; these
    /// three are not in that set, so there's no duplication.
    ///
    /// NOT ported: RP-1's per-resource ResourceContainers/ConsumersReachable tests, which need RP-1's
    /// LCResourceType fuel taxonomy (a sacked system) to avoid flagging non-fuel resources like EC.
    /// </summary>
    [HarmonyPatch(typeof(EngineersReport))]
    internal static class AxeDesignConcerns
    {
        [HarmonyPostfix]
        [HarmonyPatch("CreateStockDesignConcern")]
        internal static void Postfix_CreateStockDesignConcern(EngineersReport __instance)
        {
            __instance.AddTest(new NoControlSources());
            __instance.AddTest(new ParachuteOnEngineStage());
            __instance.AddTest(new KerbalSeatCollision());
        }
    }
}
