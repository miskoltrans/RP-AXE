using HarmonyLib;

namespace RPAxe
{
    /// <summary>
    /// Forces the stock ΔV app + calculations OFF. Stock ΔV is computed for stock (vacuum-Isp,
    /// stock atmosphere) assumptions and is wrong under RealFuels / RO — it misleads players who
    /// should read ΔV from MechJeb / RealFuels instead. Ported verbatim from RP-1's GameSettings
    /// patch: the original values are captured once (FixDV) and re-applied only around WriteCfg so
    /// the user's settings.cfg round-trips unchanged, but at runtime both flags stay false.
    /// </summary>
    [HarmonyPatch(typeof(GameSettings))]
    internal static class AxeDeltaVSettings
    {
        private static bool _dvSet;
        private static bool _deltaVAppEnabled = true;
        private static bool _deltaVCalcEnabled = true;

        private static void FixDV()
        {
            if (_dvSet) return;
            _dvSet = true;

            _deltaVAppEnabled = GameSettings.DELTAV_APP_ENABLED;
            _deltaVCalcEnabled = GameSettings.DELTAV_CALCULATIONS_ENABLED;

            GameSettings.DELTAV_APP_ENABLED = false;
            GameSettings.DELTAV_CALCULATIONS_ENABLED = false;
        }

        [HarmonyPrefix]
        [HarmonyPatch("WriteCfg")]
        internal static void Prefix_WriteCfg()
        {
            FixDV();
            // Write the user's original preference back to disk, then restore false in the postfix.
            GameSettings.DELTAV_APP_ENABLED = _deltaVAppEnabled;
            GameSettings.DELTAV_CALCULATIONS_ENABLED = _deltaVCalcEnabled;
        }

        [HarmonyPostfix]
        [HarmonyPatch("WriteCfg")]
        internal static void Postfix_WriteCfg()
        {
            GameSettings.DELTAV_APP_ENABLED = false;
            GameSettings.DELTAV_CALCULATIONS_ENABLED = false;
        }

        [HarmonyPostfix]
        [HarmonyPatch("ParseCfg")]
        internal static void Postfix_ParseCfg() => FixDV();

        [HarmonyPostfix]
        [HarmonyPatch("SetDefaultValues")]
        internal static void Postfix_SetDefaultValues() => FixDV();
    }
}
