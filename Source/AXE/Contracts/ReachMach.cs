using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using UnityEngine;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = ReachMach; mach = N }` — completes when the vessel exceeds the given Mach
    // number. Pure stock physics; meaningful for X-plane / sounding-rocket contracts.
    public class ReachMachFactory : ParameterFactory
    {
        protected double mach;
        protected float updateFrequency;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<double>(configNode, "mach", x => mach = x, this);
            valid &= ConfigNodeUtil.ParseValue<float>(configNode, "updateFrequency", x => updateFrequency = x, this,
                ReachMach.DEFAULT_UPDATE_FREQUENCY, x => Validation.GT(x, 0.0f));
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new ReachMach(title, mach, updateFrequency);
    }

    public class ReachMach : VesselParameter
    {
        internal const float DEFAULT_UPDATE_FREQUENCY = 0.25f;
        private double mach;
        private float updateFrequency = DEFAULT_UPDATE_FREQUENCY;
        private float lastUpdate;

        public ReachMach() : base(null) { }

        public ReachMach(string title, double mach, float updateFrequency) : base(title)
        {
            this.mach = mach;
            this.updateFrequency = updateFrequency;
            this.title = string.IsNullOrEmpty(title) ? GetParameterTitle() : title;
        }

        protected override string GetParameterTitle() => $"Reach Mach {mach:0.##}";

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("mach", mach);
            node.AddValue("updateFrequency", updateFrequency);
        }

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            mach = ConfigNodeUtil.ParseValue<double>(node, "mach");
            updateFrequency = ConfigNodeUtil.ParseValue<float>(node, "updateFrequency", DEFAULT_UPDATE_FREQUENCY);
        }

        protected override void OnUpdate()
        {
            base.OnUpdate();
            if (Time.fixedTime - lastUpdate > updateFrequency)
            {
                lastUpdate = Time.fixedTime;
                CheckVessel(FlightGlobals.ActiveVessel);
            }
        }

        protected override bool VesselMeetsCondition(Vessel vessel) => vessel != null && vessel.mach > mach;
    }
}
