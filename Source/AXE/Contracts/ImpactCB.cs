using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using System.Collections.Generic;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = ImpactCB; targetBody = X; minSrfVel = N }` — satisfied when the vessel is
    // destroyed on the target body, below 100 m radar altitude, having been travelling at least
    // minSrfVel (m/s) into the surface. Pure stock events; powers the iconic Ranger/Luna-style
    // LunarImpactor contracts. Ported from RP-1's ImpactCB (RP0Debug logging dropped); previously a
    // no-op stand-in in NoOpFactories.cs.
    public class ImpactCBFactory : ParameterFactory
    {
        protected double minSrfVel;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<double>(configNode, "minSrfVel", x => minSrfVel = x, this, 0, x => Validation.GE(x, 0));
            valid &= ConfigNodeUtil.ParseValue(configNode, "targetBody", x => _targetBody = x, this, (CelestialBody)null);
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new ImpactCB(title, minSrfVel, _targetBody);
    }

    public class ImpactCB : VesselParameter
    {
        private const int VelQueueSize = 50;

        protected double minSrfVel { get; set; }

        private readonly Queue<double> srfVelQueue = new Queue<double>(VelQueueSize);
        private readonly Dictionary<Vessel, bool> destroyedVessels = new Dictionary<Vessel, bool>();

        public ImpactCB() : base(null) { }

        public ImpactCB(string title, double minSrfVel, CelestialBody targetBody) : base(title)
        {
            this.minSrfVel = minSrfVel;
            this.targetBody = targetBody;
        }

        protected override bool VesselMeetsCondition(Vessel vessel)
        {
            bool isDestroyed = destroyedVessels.ContainsKey(vessel) || vessel.state == Vessel.State.DEAD;
            bool isCorrectBody = vessel.mainBody == targetBody;
            bool isValidVel = srfVelQueue.Count > 0 && srfVelQueue.Peek() >= minSrfVel;
            bool isValidAlt = vessel.radarAltitude < 100;
            return isDestroyed && isCorrectBody && isValidVel && isValidAlt;
        }

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("minSrfVel", minSrfVel);
            if (targetBody != null)
                node.AddValue("targetBody", targetBody.name);
        }

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            minSrfVel = ConfigNodeUtil.ParseValue<double>(node, "minSrfVel");
            targetBody = ConfigNodeUtil.ParseValue<CelestialBody>(node, "targetBody", null);
        }

        protected override void OnRegister()
        {
            base.OnRegister();
            GameEvents.onCollision.Add(OnVesselAboutToBeDestroyed);
            GameEvents.onCrash.Add(OnVesselAboutToBeDestroyed);
            GameEvents.onVesselDestroy.Add(OnVesselDestroy);
            GameEvents.onVesselWillDestroy.Add(OnVesselDestroy);
        }

        protected override void OnUnregister()
        {
            base.OnUnregister();
            GameEvents.onCollision.Remove(OnVesselAboutToBeDestroyed);
            GameEvents.onCrash.Remove(OnVesselAboutToBeDestroyed);
            GameEvents.onVesselDestroy.Remove(OnVesselDestroy);
            GameEvents.onVesselWillDestroy.Remove(OnVesselDestroy);
        }

        protected override void OnUpdate()
        {
            Vessel v = FlightGlobals.ActiveVessel;
            if (v == null) return;

            base.OnUpdate();

            if (srfVelQueue.Count == VelQueueSize) srfVelQueue.Dequeue();
            srfVelQueue.Enqueue(v.srfSpeed);
        }

        protected virtual void OnVesselAboutToBeDestroyed(EventReport report)
        {
            Vessel v = report.origin.vessel;
            if (v == null) return;
            destroyedVessels[v] = true;
            CheckVessel(v);
        }

        protected virtual void OnVesselDestroy(Vessel v)
        {
            destroyedVessels[v] = true;
            CheckVessel(v);
        }
    }
}
