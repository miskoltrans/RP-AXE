using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using KERBALISM;
using UnityEngine;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = RP1HasSamples; experiment = <expId> }` — satisfied while any Kerbalism HardDrive
    // on the vessel holds a stored SAMPLE of the given experiment (as opposed to transmissible data).
    // Ported from RP-1's RP1HasSamples (localized/ScienceDB title replaced with a plain fallback).
    // AXE ships Kerbalism, so this is a hard-referenced check. Previously a no-op stand-in.
    public class RP1HasSamplesFactory : ParameterFactory
    {
        protected string experiment;
        protected float updateFrequency;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<string>(configNode, "experiment", x => experiment = x, this);
            valid &= ConfigNodeUtil.ParseValue<float>(configNode, "updateFrequency", x => updateFrequency = x, this,
                RP1HasSamples.DEFAULT_UPDATE_FREQUENCY, x => Validation.GT(x, 0.0f));
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new RP1HasSamples(experiment, title);
    }

    public class RP1HasSamples : VesselParameter
    {
        internal const float DEFAULT_UPDATE_FREQUENCY = 2.5f; // shouldn't change often

        protected string experiment { get; set; }

        private float lastUpdate = 0.0f;
        private float updateFrequency = DEFAULT_UPDATE_FREQUENCY;

        public RP1HasSamples() : base(null) { lastUpdate = Time.fixedTime; }

        public RP1HasSamples(string experiment, string title) : base(title)
        {
            lastUpdate = Time.fixedTime;
            this.experiment = experiment;
            this.title = string.IsNullOrEmpty(title) ? $"Hold a {experiment} sample" : title;
        }

        protected override string GetParameterTitle() => title;

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            updateFrequency = ConfigNodeUtil.ParseValue<float>(node, "updateFrequency", DEFAULT_UPDATE_FREQUENCY);
            experiment = ConfigNodeUtil.ParseValue<string>(node, "experiment");
        }

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("updateFrequency", updateFrequency);
            node.AddValue("experiment", experiment);
        }

        protected override void OnUpdate()
        {
            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null) return;

            base.OnUpdate();

            if (Time.fixedTime - lastUpdate > updateFrequency)
            {
                lastUpdate = Time.fixedTime;
                CheckVessel(v);
            }
        }

        protected override bool VesselMeetsCondition(Vessel vessel)
        {
            if (vessel == null) return false;
            foreach (Part p in vessel.Parts)
                foreach (HardDrive hd in p.FindModulesImplementing<HardDrive>())
                    foreach (SubjectData subject in hd.GetDrive().samples.Keys)
                        if (subject.ExpInfo.ExperimentId == experiment)
                            return true;
            return false;
        }
    }
}
