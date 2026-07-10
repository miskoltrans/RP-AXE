using HarmonyLib;
using System.Collections.Generic;
using System.Linq;
using System.Reflection.Emit;

namespace RPAxe
{
    /// <summary>
    /// Stops a home-world EVA below orbital velocity from being written to the crew flight log (and so
    /// from counting as the "first EVA" progress milestone). A quick ground/sub-orbital step-out
    /// shouldn't book the historic first-spacewalk. Ported verbatim from RP-1: a transpiler on
    /// FlightEVA.onGoForEVA that swaps the inline flightLog.AddEntryUnique(...) call for a gated
    /// version. Self-guarding — if the IL pattern isn't found (e.g. a future KSP), it returns the
    /// original instructions unchanged, so it can only ever no-op, never break EVA.
    /// </summary>
    [HarmonyPatch(typeof(FlightEVA))]
    internal class AxeFlightEvaLog
    {
        [HarmonyTranspiler]
        [HarmonyPatch("onGoForEVA")]
        internal static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions, ILGenerator il)
        {
            int startIndex = -1;
            int endIndex = -1;

            var codes = new List<CodeInstruction>(instructions);

            // Locate: this.pCrew.flightLog.AddEntryUnique(FlightLog.EntryType.ExitVessel, this.fromPart.vessel.orbit.referenceBody.name);
            for (int i = 0; i < codes.Count; i++)
            {
                if (codes[i].opcode == OpCodes.Callvirt &&
                    codes[i].operand.ToString() == "Void AddEntryUnique(EntryType, System.String)")
                {
                    endIndex = i;

                    for (int j = i - 1; j >= 0; j--)
                    {
                        if (codes[j].opcode == OpCodes.Ldfld &&
                            codes[j].operand.ToString() == "ProtoCrewMember pCrew")
                        {
                            startIndex = j - 1;    // include the ldarg.0 (this) before it
                            break;
                        }
                    }

                    break;
                }
            }

            if (startIndex > -1 && endIndex > -1)
            {
                codes.RemoveRange(startIndex + 1, endIndex - startIndex);
                CodeInstruction call = CodeInstruction.Call(typeof(AxeFlightEvaLog), "AddEntryUniquePatched");
                codes.Insert(startIndex + 1, call);
            }

            return codes.AsEnumerable();
        }

        public static void AddEntryUniquePatched(FlightEVA instance)
        {
            var fromPart = (Part)AccessTools.Field(typeof(FlightEVA), "fromPart").GetValue(instance);
            Vessel v = fromPart.vessel;
            if (!v.orbit.referenceBody.isHomeWorld ||
                (v.orbit.referenceBody.isHomeWorld && v.situation > Vessel.Situations.SUB_ORBITAL))
            {
                var pCrew = (ProtoCrewMember)AccessTools.Field(typeof(FlightEVA), "pCrew").GetValue(instance);
                pCrew.flightLog.AddEntryUnique(FlightLog.EntryType.ExitVessel, v.orbit.referenceBody.name);
            }
        }
    }
}
