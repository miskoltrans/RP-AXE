using Experience.Effects;
using HarmonyLib;

namespace RPAxe
{
    /// <summary>
    /// An astronaut aboard always supplies FULL SAS (level 3 — target, anti-target and maneuver node),
    /// regardless of experience level.
    ///
    /// Stock feeds <c>part.PartValues.AutopilotSkill</c> from two places: a part's
    /// <c>ModuleSAS.SASServiceLevel</c>, and the crew's <c>AutopilotSkill</c> experience effect — whose
    /// value is the kerbal's XP level, nothing else. <c>AutopilotSkill.GetValue()</c> is literally
    /// <c>return Parent.CrewMemberExperienceLevel();</c>: it reads neither the EFFECT node's
    /// <c>level</c> nor its <c>modifiers</c>, so this is unreachable from config and has to be a patch.
    /// The other half of the change — giving Engineer and Scientist the effect at all, so every crewed
    /// trait is a contributor — IS config, and lives in design/Settings/AxeCrewAutopilot.cfg. That file
    /// carries the full rationale.
    ///
    /// Patching the effect's VALUE (rather than, say, <c>APSkillExtensions.AvailableAtLevel</c>, which
    /// is where stock finally compares it) keeps every consumer in agreement: the vessel really does
    /// report autopilot skill 3, so the mode buttons, the ModuleSAS PAW text and anything else reading
    /// <c>VesselValues.AutopilotSkill</c> all say the same thing. Scoping is tight in return —
    /// <c>GetValue</c> has exactly two callers, both of them the delegate registration in
    /// <c>OnRegister</c>, so nothing outside SAS mode availability can see this.
    ///
    /// Deliberately NOT <c>ExperienceTrait.CrewMemberExperienceLevel</c>, the tempting one-line target:
    /// that backs every skill a kerbal has (science return, repairs, G tolerance) and would silently
    /// max all of them.
    /// </summary>
    [HarmonyPatch(typeof(AutopilotSkill), "GetValue")]
    internal static class AxeCrewSasSkill
    {
        /// <summary>Highest skill any autopilot mode asks for — <c>Skills.Maneuver</c>, i.e. 3.</summary>
        internal const int FullSasLevel = (int)AutopilotSkill.Skills.Maneuver;

        private static void Postfix(ref int __result)
        {
            __result = FullSasLevel;
        }
    }

    /// <summary>
    /// Keeps the crew-info blurb honest about the above. <c>AutopilotSkill.GetDescription()</c> lists
    /// the modes the kerbal unlocks by walking <c>SkillsReadable</c> up to their XP level, so without
    /// this a rookie's Astronaut Complex entry would advertise "Stability Assist" for a kerbal who in
    /// fact flies maneuver nodes. Same list, no truncation.
    /// </summary>
    [HarmonyPatch(typeof(AutopilotSkill), "GetDescription")]
    internal static class AxeCrewSasSkillDescription
    {
        private static void Postfix(ref string __result)
        {
            string text = "";
            for (int i = 0; i < AutopilotSkill.SkillsReadable.Length; i++)
            {
                if (i != 0) text += "\n";
                text += AutopilotSkill.SkillsReadable[i];
            }
            __result = text;
        }
    }
}
