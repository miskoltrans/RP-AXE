using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Helpers for marking science subjects as already fully collected (science == scienceCap, so no
    /// more is recoverable). Ported from RP-1's ScienceUtils (RP0Debug -> Debug). No caller yet — this
    /// is the tool for granting/settling science when AXE wires milestone/program rewards or a
    /// configurable start that pre-completes early experiments.
    /// </summary>
    public static class AxeScienceUtils
    {
        public static void MarkExperimentsAsDone(Dictionary<string, Dictionary<string, HashSet<ExperimentSituations>>> bodyExperimentDict)
        {
            foreach (var bodyKVP in bodyExperimentDict)
                foreach (var expKVP in bodyKVP.Value)
                    foreach (var sit in expKVP.Value)
                        MarkExperimentAsDone(expKVP.Key, sit, bodyKVP.Key);
        }

        public static void MarkExperimentAsDone(string experimentID, ExperimentSituations situation, string bodyName)
        {
            ScienceExperiment experiment = ResearchAndDevelopment.GetExperiment(experimentID);
            if (experiment == null)
            {
                Debug.LogError($"[AXE] MarkExperimentAsDone: invalid experiment {experimentID}");
                return;
            }
            CelestialBody body = FlightGlobals.GetBodyByName(bodyName);

            if (experiment.BiomeIsRelevantWhile(situation))
            {
                List<string> allBiomes = ResearchAndDevelopment.GetBiomeTags(body, false);
                foreach (string biomeName in allBiomes)
                {
                    string biomeTitle = ScienceUtil.GetBiomedisplayName(body, biomeName);
                    MarkAsDone(experiment, situation, body, biomeName, biomeTitle);
                }
            }
            else
            {
                MarkAsDone(experiment, situation, body, string.Empty, string.Empty);
            }
        }

        public static void MarkAsDone(ScienceExperiment experiment, ExperimentSituations situation, CelestialBody body, string biomeName, string biomeTitle)
        {
            ScienceSubject subj = ResearchAndDevelopment.GetExperimentSubject(experiment, situation, body, biomeName, biomeTitle);
            subj.scientificValue = 0;
            subj.science = subj.scienceCap;
        }
    }
}
