using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using System;
using UnityEngine;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = HorizontalLanding; descentAngle = N }` — satisfied if the vessel came down
    // like an aircraft (a shallow glide: horizontal speed > |vertical speed| * cot(descentAngle)),
    // latched from the last airborne sample so it holds through touchdown. Optional maxSrfVel gate.
    // Pure stock physics; meaningful for X-plane / spaceplane contracts. (Ported from RP-1's logic.)
    public class HorizontalLandingFactory : ParameterFactory
    {
        protected double descentAngle;
        protected double? maxSrfVel;
        protected float updateFrequency;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<double>(configNode, "descentAngle", x => descentAngle = x, this, 2.0, x => Validation.GT(x, 0.0));
            valid &= ConfigNodeUtil.ParseValue<double?>(configNode, "maxSrfVel", x => maxSrfVel = x, this, (double?)null);
            valid &= ConfigNodeUtil.ParseValue<float>(configNode, "updateFrequency", x => updateFrequency = x, this,
                HorizontalLanding.DEFAULT_UPDATE_FREQUENCY, x => Validation.GT(x, 0.0f));
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new HorizontalLanding(title, descentAngle, maxSrfVel, updateFrequency);
    }

    public class HorizontalLanding : VesselParameter
    {
        internal const float DEFAULT_UPDATE_FREQUENCY = 0.5f;
        private double glideRatio;
        private double? maxSrfVel;
        private bool wasPreviouslyMet;
        private float updateFrequency = DEFAULT_UPDATE_FREQUENCY;
        private float lastUpdate;

        public HorizontalLanding() : base(null) { }

        public HorizontalLanding(string title, double descentAngle, double? maxSrfVel, float updateFrequency) : base(title)
        {
            this.title = string.IsNullOrEmpty(title) ? $"Land horizontally (descent angle below {descentAngle:0.##}°)" : title;
            this.glideRatio = 1.0 / Math.Tan(Mathf.Deg2Rad * descentAngle);
            this.maxSrfVel = maxSrfVel;
            this.updateFrequency = updateFrequency;
        }

        protected override string GetParameterTitle() => title;

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("updateFrequency", updateFrequency);
            node.AddValue("glideRatio", glideRatio);
            node.AddValue("wasPreviouslyMet", wasPreviouslyMet);
            if (maxSrfVel.HasValue) node.AddValue("maxSrfVel", maxSrfVel.Value);
        }

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            updateFrequency = ConfigNodeUtil.ParseValue<float>(node, "updateFrequency", DEFAULT_UPDATE_FREQUENCY);
            glideRatio = ConfigNodeUtil.ParseValue<double>(node, "glideRatio");
            wasPreviouslyMet = ConfigNodeUtil.ParseValue<bool>(node, "wasPreviouslyMet");
            maxSrfVel = ConfigNodeUtil.ParseValue<double?>(node, "maxSrfVel", (double?)null);
        }

        protected override bool VesselMeetsCondition(Vessel vessel)
        {
            if (vessel == null) return wasPreviouslyMet;
            if (!vessel.LandedOrSplashed && !vessel.packed)
            {
                wasPreviouslyMet = vessel.horizontalSrfSpeed > Math.Abs(vessel.verticalSpeed) * glideRatio;
                if (maxSrfVel.HasValue)
                    wasPreviouslyMet &= maxSrfVel.Value < vessel.srfSpeed;
            }
            return wasPreviouslyMet;
        }

        protected override void OnUpdate()
        {
            base.OnUpdate();
            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null) return;
            if (Time.fixedTime - lastUpdate > updateFrequency)
            {
                lastUpdate = Time.fixedTime;
                CheckVessel(v);
            }
        }
    }
}
