using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using KERBALISM;
using System.Linq;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = RP1HasExperiment; experiment = <expId> }` — satisfied while the vessel carries
    // an enabled Kerbalism experiment module whose experiment (or one it includes) matches expId.
    // Ported from RP-1's RP1HasExperiment; AXE ships Kerbalism, so this is a hard-referenced check
    // (KSPCommunityFixes' FindModulesImplementingReadOnly swapped for the stock FindModulesImplementing;
    // RP-1's localized/ScienceDB title replaced with a plain fallback). Previously a no-op stand-in.
    public class RP1HasExperimentFactory : ParameterFactory
    {
        protected string experiment;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<string>(configNode, "experiment", x => experiment = x, this);
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new RP1HasExperiment(experiment, title);
    }

    public class RP1HasExperiment : VesselParameter
    {
        protected string experiment { get; set; }

        public RP1HasExperiment() : base(null) { }

        public RP1HasExperiment(string experiment, string title) : base(title)
        {
            this.experiment = experiment;
            this.title = string.IsNullOrEmpty(title) ? $"Carry a {experiment} experiment" : title;
        }

        protected override string GetParameterTitle() => title;

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            experiment = ConfigNodeUtil.ParseValue<string>(node, "experiment");
        }

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("experiment", experiment);
        }

        protected override bool VesselMeetsCondition(Vessel vessel)
        {
            if (vessel == null) return false;
            foreach (Part p in vessel.Parts)
                foreach (Experiment exp in p.FindModulesImplementing<Experiment>())
                    if (exp.isEnabled && IncludesExperiment(exp.ExpInfo, experiment))
                        return true;
            return false;
        }

        // Does exp include an experiment with id `id`? (Kerbalism guarantees no loops in the traversal.)
        private bool IncludesExperiment(ExperimentInfo exp, string id)
        {
            return exp.ExperimentId == id || exp.IncludedExperiments.Any(info => IncludesExperiment(info, id));
        }
    }
}
