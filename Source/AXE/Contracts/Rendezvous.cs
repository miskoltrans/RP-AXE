using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using UnityEngine;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = RP1Rendezvous; distance = N; relativeSpeed = M }` — completes when the
    // active vessel comes within `distance` metres of ANY other loaded vessel with a relative
    // (orbital) speed below `relativeSpeed` (0 = ignore speed). Serves the Gemini-era rendezvous /
    // proximity-operations contracts. Ported from RP-1's RP1Rendezvous; RP-1 excluded same-launch
    // craft via a KCT vessel id — AXE has no KCT, so the plain `v2 != v1` guard suffices (each loaded
    // vessel is a distinct craft). Previously a no-op stand-in in NoOpFactories.cs.
    public class RP1RendezvousFactory : ParameterFactory
    {
        protected double distance;
        protected double relativeSpeed;
        protected float updateFrequency;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<double>(configNode, "distance", x => distance = x, this, 100);
            valid &= ConfigNodeUtil.ParseValue<double>(configNode, "relativeSpeed", x => relativeSpeed = x, this, 0);
            valid &= ConfigNodeUtil.ParseValue<float>(configNode, "updateFrequency", x => updateFrequency = x, this,
                RP1Rendezvous.DEFAULT_UPDATE_FREQUENCY, x => Validation.GT(x, 0.0f));
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new RP1Rendezvous(distance, relativeSpeed, title, updateFrequency);
    }

    public class RP1Rendezvous : VesselParameter
    {
        internal const float DEFAULT_UPDATE_FREQUENCY = 0.50f;

        protected double distance { get; set; }
        protected double relativeSpeed { get; set; }
        protected float updateFrequency { get; set; }

        private float lastUpdate = 0.0f;

        public RP1Rendezvous() : base(null) { }

        public RP1Rendezvous(double distance, double relativeSpeed, string title, float updateFrequency) : base(title)
        {
            this.distance = distance;
            this.relativeSpeed = relativeSpeed;
            this.title = title;
            this.updateFrequency = updateFrequency;
            disableOnStateChange = true;
        }

        protected override string GetParameterTitle() => string.IsNullOrEmpty(title) ? "Rendezvous with another vessel" : title;

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("updateFrequency", updateFrequency);
            node.AddValue("distance", distance);
            node.AddValue("relativeSpeed", relativeSpeed);
        }

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            updateFrequency = ConfigNodeUtil.ParseValue<float>(node, "updateFrequency", DEFAULT_UPDATE_FREQUENCY);
            distance = ConfigNodeUtil.ParseValue<double>(node, "distance");
            relativeSpeed = ConfigNodeUtil.ParseValue<double>(node, "relativeSpeed");
        }

        protected override void OnUpdate()
        {
            base.OnUpdate();

            if (Time.fixedTime - lastUpdate < updateFrequency) return;
            lastUpdate = Time.fixedTime;

            if (FlightGlobals.VesselsLoaded.Count < 2) return;

            Vessel v1 = FlightGlobals.ActiveVessel;
            if (!IsValidVessel(v1)) return;

            bool forceStateChange = false;
            bool rendezvous = false;
            foreach (Vessel v2 in FlightGlobals.VesselsLoaded)
            {
                if (v2 != v1 && IsValidVessel(v2))
                {
                    float dist = Vector3.Distance(v1.transform.position, v2.transform.position);
                    double relSpeed = (v1.obt_velocity - v2.obt_velocity).magnitude;
                    if (dist < this.distance && (this.relativeSpeed <= 0 || relSpeed < this.relativeSpeed))
                    {
                        rendezvous = true;
                        forceStateChange |= SetState(v1, ParameterState.Complete);
                        forceStateChange |= SetState(v2, ParameterState.Complete);
                    }
                }
            }

            if (rendezvous)
                CheckVessel(FlightGlobals.ActiveVessel, forceStateChange);
        }

        protected override bool VesselMeetsCondition(Vessel vessel) => GetState(vessel) == ParameterState.Complete;

        private static bool IsValidVessel(Vessel v)
        {
            return v != null && !v.isEVA && v.vesselType != VesselType.Debris && v.vesselType != VesselType.Flag;
        }
    }
}
