using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;
using UnityEngine;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = RP1ReturnHome }` — simplified: vessel is landed or splashed on the home
    // body. (RP-1 also checked a max speed and an optional named facility; per project direction we
    // drop those nuances.) Normally grouped with a "reach space/orbit" parameter, so it isn't
    // trivially satisfied on the pad.
    public class RP1ReturnHomeFactory : ParameterFactory
    {
        public override ContractParameter Generate(Contract contract) => new RP1ReturnHome(title);
    }

    public class RP1ReturnHome : VesselParameter
    {
        public RP1ReturnHome() : base(null) { }

        public RP1ReturnHome(string title) : base(title)
        {
            this.title = string.IsNullOrEmpty(title) ? GetParameterTitle() : title;
        }

        protected override string GetParameterTitle() => "Return home and land safely";

        protected override void OnParameterSave(ConfigNode node) { base.OnParameterSave(node); }
        protected override void OnParameterLoad(ConfigNode node) { base.OnParameterLoad(node); }

        protected override void OnUpdate()
        {
            base.OnUpdate();
            if (FlightGlobals.ActiveVessel != null)
                CheckVessel(FlightGlobals.ActiveVessel);
        }

        protected override bool VesselMeetsCondition(Vessel vessel)
        {
            return vessel != null && vessel.mainBody != null && vessel.mainBody == FlightGlobals.GetHomeBody()
                && (vessel.situation == Vessel.Situations.LANDED || vessel.situation == Vessel.Situations.SPLASHED);
        }
    }
}
