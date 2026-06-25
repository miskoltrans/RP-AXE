using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using System;
using UnityEngine;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = DownrangeDistance; distance = N }` — completes when the vessel has flown
    // the given great-circle surface distance (metres) from where it lifted off. Pure stock
    // geometry; meaningful for sounding-rocket / early downrange contracts.
    public class DownrangeDistanceFactory : ParameterFactory
    {
        protected double distance;
        protected float updateFrequency;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<double>(configNode, "distance", x => distance = x, this, 1d, x => Validation.GT(x, 0.0));
            valid &= ConfigNodeUtil.ParseValue<float>(configNode, "updateFrequency", x => updateFrequency = x, this,
                DownrangeDistance.DEFAULT_UPDATE_FREQUENCY, x => Validation.GT(x, 0.0f));
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new DownrangeDistance(title, distance, updateFrequency);
    }

    public class DownrangeDistance : VesselParameter
    {
        internal const float DEFAULT_UPDATE_FREQUENCY = 0.5f;
        private double distance;
        private float updateFrequency = DEFAULT_UPDATE_FREQUENCY;
        private float lastUpdate;
        private bool hasStart;
        private double startLat, startLon;

        public DownrangeDistance() : base(null) { }

        public DownrangeDistance(string title, double distance, float updateFrequency) : base(title)
        {
            this.distance = distance;
            this.updateFrequency = updateFrequency;
            this.title = string.IsNullOrEmpty(title) ? GetParameterTitle() : title;
        }

        protected override string GetParameterTitle() => $"Fly {distance / 1000.0:0.#} km downrange";

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("distance", distance);
            node.AddValue("updateFrequency", updateFrequency);
            node.AddValue("hasStart", hasStart);
            node.AddValue("startLat", startLat);
            node.AddValue("startLon", startLon);
        }

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            distance = ConfigNodeUtil.ParseValue<double>(node, "distance", 1d);
            updateFrequency = ConfigNodeUtil.ParseValue<float>(node, "updateFrequency", DEFAULT_UPDATE_FREQUENCY);
            bool.TryParse(node.GetValue("hasStart"), out hasStart);
            double.TryParse(node.GetValue("startLat"), out startLat);
            double.TryParse(node.GetValue("startLon"), out startLon);
        }

        protected override void OnUpdate()
        {
            base.OnUpdate();
            if (Time.fixedTime - lastUpdate <= updateFrequency) return;
            lastUpdate = Time.fixedTime;

            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null) return;
            if (!hasStart && v.LandedOrSplashed)
            {
                startLat = v.latitude;
                startLon = v.longitude;
                hasStart = true;
            }
            CheckVessel(v);
        }

        protected override bool VesselMeetsCondition(Vessel vessel)
        {
            if (!hasStart || vessel == null || vessel.mainBody == null) return false;
            double R = vessel.mainBody.Radius;
            double lat1 = startLat * Math.PI / 180.0;
            double lat2 = vessel.latitude * Math.PI / 180.0;
            double dLat = (vessel.latitude - startLat) * Math.PI / 180.0;
            double dLon = (vessel.longitude - startLon) * Math.PI / 180.0;
            double a = Math.Sin(dLat / 2) * Math.Sin(dLat / 2) +
                       Math.Cos(lat1) * Math.Cos(lat2) * Math.Sin(dLon / 2) * Math.Sin(dLon / 2);
            double d = 2.0 * R * Math.Asin(Math.Min(1.0, Math.Sqrt(a)));
            return d >= distance;
        }
    }
}
