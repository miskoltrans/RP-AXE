using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using System.Collections.Generic;
using System.Linq;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = RP1CollectScience }` — completes once enough of an experiment's science has
    // been banked in R&D for the matching subject(s).
    //
    // This POLLS `ScienceSubject.science / scienceCap` rather than listening to
    // `GameEvents.OnScienceRecieved`, and that is not a style choice: Kerbalism writes
    // `RnDSubject.science` directly (SubjectData.RetrieveScience) and only fires OnScienceRecieved
    // from OnSubjectCompleted — i.e. exactly once, when the subject crosses 100%. An event-driven
    // parameter therefore ignores `fractionComplete` entirely and silently sits Incomplete until a
    // subject is fully mined. RP-1 polls for the same reason; so do we.
    public class RP1CollectScienceFactory : ParameterFactory
    {
        protected string biome;
        protected ExperimentSituations? situation;
        protected BodyLocation? location;
        protected List<ScienceExperiment> experiment;
        protected List<ScienceSubject> subjects;
        protected double fractionComplete;
        protected int? minSubjectsToComplete;
        protected double? fractionCompleteBiome;
        protected float updateFrequency;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            // Fold the parse results into `valid` so a renamed/missing experiment or subject id fails
            // the factory loudly at load, instead of silently degrading to "never completes".
            valid &= ConfigNodeUtil.ParseValue(configNode, "biome", x => biome = x, this, "");
            valid &= ConfigNodeUtil.ParseValue(configNode, "situation", x => situation = x, this, (ExperimentSituations?)null);
            valid &= ConfigNodeUtil.ParseValue(configNode, "location", x => location = x, this, (BodyLocation?)null);
            valid &= ConfigNodeUtil.ParseValue(configNode, "experiment", x => experiment = x, this, new List<ScienceExperiment>(),
                x => x.All(Validation.NotNull));
            valid &= ConfigNodeUtil.ParseValue(configNode, "subject", x => subjects = x, this, new List<ScienceSubject>());
            valid &= ConfigNodeUtil.ParseValue(configNode, "fractionComplete", x => fractionComplete = x, this, 1d);
            valid &= ConfigNodeUtil.ParseValue(configNode, "minSubjectsToComplete", x => minSubjectsToComplete = x, this, (int?)null);
            valid &= ConfigNodeUtil.ParseValue(configNode, "fractionCompleteBiome", x => fractionCompleteBiome = x, this, (double?)null);
            valid &= ConfigNodeUtil.ParseValue(configNode, "updateFrequency", x => updateFrequency = x, this,
                RP1CollectScience.DefaultUpdateFrequency, x => Validation.GT(x, 0f));
            // Leftover from stock CC's CollectScience in the vendored RP-1 configs. Kerbalism banks
            // recovered and transmitted science into the same subject, so there is nothing to branch
            // on — read it only to keep it out of the "unexpected attribute" warning spam.
            ConfigNodeUtil.ParseValue(configNode, "recoveryMethod", x => { }, this, "");
            return valid;
        }

        public override ContractParameter Generate(Contract contract)
        {
            List<string> expIds = subjects != null && subjects.Count > 0
                ? subjects.Select(s => ContractConfigurator.Util.Science.GetExperiment(s).id).ToList()
                : (experiment ?? new List<ScienceExperiment>()).Where(e => e != null).Select(e => e.id).ToList();

            ExperimentSituations? sit = situation;
            string bio = biome;
            if (subjects != null && subjects.Count > 0)
            {
                sit = ContractConfigurator.Util.Science.GetSituation(subjects[0]);
                var b = ContractConfigurator.Util.Science.GetBiome(subjects[0]);
                if (b != null) bio = b.biome;
            }

            return new RP1CollectScience(targetBody, bio, sit, location, expIds, fractionComplete,
                minSubjectsToComplete, fractionCompleteBiome, title, updateFrequency);
        }
    }

    public class RP1CollectScience : ContractConfiguratorParameter
    {
        internal const float DefaultUpdateFrequency = 2.5f;
        // Subjects cap out a hair under 100% because of float rounding in the science ledger; RP-1
        // uses the same nudge so a "transmit 100%" parameter can actually be satisfied.
        private const float FractionErrorMargin = 0.00025f;

        protected string biome;
        protected ExperimentSituations? situation;
        protected BodyLocation? location;
        protected List<string> experiment = new List<string>();
        protected double fractionComplete = 1d;
        protected int? minSubjectsToComplete;
        protected double? fractionCompleteBiome;
        protected float updateFrequency = DefaultUpdateFrequency;

        // Saves written by the previous event-driven implementation carry only `expId`/`bodyName`, so
        // the fraction and situation are unrecoverable. Those parameters fall back to the old
        // semantics — "any banked science on a matching subject completes it" — which is what the
        // player's in-flight contract was promised when they accepted it.
        private bool legacy;
        private string legacyBodyName;

        private List<ScienceSubject> subjects;
        private float lastUpdate;
        private float progress;

        public RP1CollectScience() : base(null) { }

        public RP1CollectScience(CelestialBody targetBody, string biome, ExperimentSituations? situation, BodyLocation? location,
            List<string> experiment, double fractionComplete, int? minSubjectsToComplete, double? fractionCompleteBiome,
            string title, float updateFrequency) : base(title)
        {
            this.targetBody = targetBody;
            this.biome = biome ?? "";
            this.situation = situation;
            this.location = location;
            this.experiment = experiment ?? new List<string>();
            this.fractionComplete = fractionComplete;
            this.minSubjectsToComplete = minSubjectsToComplete;
            this.fractionCompleteBiome = fractionCompleteBiome;
            this.updateFrequency = updateFrequency;
            lastUpdate = UnityEngine.Time.fixedTime;
        }

        protected override string GetParameterTitle()
        {
            string text = string.IsNullOrEmpty(title) ? "Collect and transmit science" : title;
            // The parameter is otherwise a black box: without a readout there is no way to tell
            // "not enough science yet" from "the check is broken".
            if (state == ParameterState.Incomplete && progress > 0f)
                text = $"{text} ({progress:P0})";
            return text;
        }

        protected override void OnParameterSave(ConfigNode node)
        {
            if (targetBody != null) node.AddValue("targetBody", targetBody.name);
            if (!string.IsNullOrEmpty(biome)) node.AddValue("biome", biome);
            if (situation.HasValue) node.AddValue("situation", situation.Value);
            if (location.HasValue) node.AddValue("location", location.Value);
            node.AddValue("fractionComplete", fractionComplete);
            if (minSubjectsToComplete.HasValue) node.AddValue("minSubjectsToComplete", minSubjectsToComplete.Value);
            if (fractionCompleteBiome.HasValue) node.AddValue("fractionCompleteBiome", fractionCompleteBiome.Value);
            node.AddValue("updateFrequency", updateFrequency);
            foreach (string exp in experiment)
                if (!string.IsNullOrEmpty(exp)) node.AddValue("experiment", exp);
        }

        protected override void OnParameterLoad(ConfigNode node)
        {
            targetBody = ConfigNodeUtil.ParseValue(node, "targetBody", (CelestialBody)null);
            biome = ConfigNodeUtil.ParseValue(node, "biome", "");
            situation = ConfigNodeUtil.ParseValue(node, "situation", (ExperimentSituations?)null);
            location = ConfigNodeUtil.ParseValue(node, "location", (BodyLocation?)null);
            experiment = ConfigNodeUtil.ParseValue(node, "experiment", new List<string>(0));
            fractionComplete = ConfigNodeUtil.ParseValue(node, "fractionComplete", 1d);
            minSubjectsToComplete = ConfigNodeUtil.ParseValue(node, "minSubjectsToComplete", (int?)null);
            fractionCompleteBiome = ConfigNodeUtil.ParseValue(node, "fractionCompleteBiome", (double?)null);
            updateFrequency = ConfigNodeUtil.ParseValue(node, "updateFrequency", DefaultUpdateFrequency);

            if (experiment.Count == 0 && node.HasValue("expId"))
            {
                legacy = true;
                experiment = node.GetValues("expId").ToList();
                legacyBodyName = node.GetValue("bodyName");
            }
        }

        protected override void OnUpdate()
        {
            base.OnUpdate();

            if (state != ParameterState.Incomplete) return;
            if (UnityEngine.Time.fixedTime - lastUpdate <= updateFrequency) return;
            lastUpdate = UnityEngine.Time.fixedTime;

            if (legacy)
            {
                UpdateLegacy();
                return;
            }

            if (subjects == null) LoadScienceSubjects();
            if (subjects == null || subjects.Count == 0) return;

            int numToComplete = minSubjectsToComplete ?? 1;
            int completeSubjCount = 0;
            float totalFrac = 0f;
            double perSubjectTarget = fractionCompleteBiome ?? fractionComplete;
            foreach (ScienceSubject subj in subjects)
            {
                float curFraction = GetCompletedFraction(subj);
                totalFrac += curFraction;
                if (curFraction >= perSubjectTarget) ++completeSubjCount;
            }
            totalFrac /= subjects.Count;
            progress = totalFrac;

            if (totalFrac >= fractionComplete && completeSubjCount >= numToComplete)
                SetState(ParameterState.Complete);
        }

        // Old event-driven behaviour, re-expressed as a poll: any banked science on a subject whose id
        // matches the experiment (and body, if one was recorded) completes the parameter.
        private void UpdateLegacy()
        {
            if (ResearchAndDevelopment.Instance == null) return;
            foreach (ScienceSubject subj in ResearchAndDevelopment.GetSubjects())
            {
                if (subj == null || subj.science <= 0f) continue;
                if (!experiment.Any(e => subj.id.StartsWith(e))) continue;
                if (!string.IsNullOrEmpty(legacyBodyName) && !subj.id.Contains(legacyBodyName)) continue;
                SetState(ParameterState.Complete);
                return;
            }
        }

        private static float GetCompletedFraction(ScienceSubject subj)
        {
            if (subj == null || subj.scienceCap <= 0f) return 0f;
            return subj.science / subj.scienceCap + FractionErrorMargin;
        }

        private void LoadScienceSubjects()
        {
            if (ResearchAndDevelopment.Instance == null) return;

            var list = new List<ScienceSubject>(experiment.Count);
            foreach (string exp in experiment)
            {
                ScienceExperiment se = ResearchAndDevelopment.GetExperiment(exp);
                if (se == null) continue;

                if (situation.HasValue)
                {
                    AddSubjectsForSituation(list, se, situation.Value);
                }
                else if (location.HasValue && location.Value == BodyLocation.Surface)
                {
                    AddSubjectsForSituation(list, se, ExperimentSituations.SrfLanded);
                    AddSubjectsForSituation(list, se, ExperimentSituations.SrfSplashed);
                }
                else
                {
                    AddSubjectsForSituation(list, se, ExperimentSituations.InSpaceLow);
                    AddSubjectsForSituation(list, se, ExperimentSituations.InSpaceHigh);
                }
            }
            subjects = list;
        }

        private void AddSubjectsForSituation(List<ScienceSubject> list, ScienceExperiment se, ExperimentSituations sit)
        {
            bool hasBiomes = se.BiomeIsRelevantWhile(sit);

            // No biome asked for on a biome-relevant experiment: the target is the average across every
            // biome, matching RP-1 — otherwise one lucky pass over one biome would finish the contract.
            if (hasBiomes && string.IsNullOrEmpty(biome))
            {
                foreach (string biomeName in ResearchAndDevelopment.GetBiomeTags(targetBody, false))
                    list.Add(ResearchAndDevelopment.GetExperimentSubject(se, sit, targetBody, biomeName,
                        ScienceUtil.GetBiomedisplayName(targetBody, biomeName)));
                return;
            }

            string bName = hasBiomes ? biome : string.Empty;
            string bTitle = hasBiomes ? ScienceUtil.GetBiomedisplayName(targetBody, biome) : string.Empty;
            list.Add(ResearchAndDevelopment.GetExperimentSubject(se, sit, targetBody, bName, bTitle));
        }
    }
}
