using Contracts;
using ContractConfigurator.Parameters;
using UnityEngine;

namespace RPAxe.Contracts
{
    /// <summary>
    /// A vessel parameter that is always satisfied. Used as the MVP stand-in for RP-1 contract
    /// checks we deliberately don't implement yet (tied to removed systems, or low value): they
    /// keep the contract loading and don't block completion. Being a VesselParameter, it is valid
    /// both standalone and inside a VesselParameterGroup. Upgrade individual ones to real checks
    /// later (see Source/AXE/_CCTYPES.md).
    /// </summary>
    public class AxeAlwaysComplete : VesselParameter
    {
        public AxeAlwaysComplete() : base(null) { }

        public AxeAlwaysComplete(string title) : base(title)
        {
            this.title = string.IsNullOrEmpty(title) ? "(no-op)" : title;
        }

        protected override string GetParameterTitle() => string.IsNullOrEmpty(title) ? "(no-op)" : title;

        protected override bool VesselMeetsCondition(Vessel vessel) => true;

        protected override void OnUpdate()
        {
            base.OnUpdate();
            if (FlightGlobals.ActiveVessel != null)
                CheckVessel(FlightGlobals.ActiveVessel);
        }

        protected override void OnParameterSave(ConfigNode node) { base.OnParameterSave(node); }
        protected override void OnParameterLoad(ConfigNode node) { base.OnParameterLoad(node); }
    }

    /// <summary>
    /// Completes one tick AFTER its contract becomes Active (i.e. just after the player accepts the
    /// "Begin Program" charter), regardless of scene or vessel. We deliberately do NOT complete on
    /// register/offered: a parameter already complete at accept makes the contract finish *inside*
    /// MissionControl's accept-click handler, which NREs in ContractConfigurator's MissionControlUI.
    /// Completing a frame later lets the accept finish normally, then the contract completes cleanly.
    /// </summary>
    public class AxeInstantComplete : ContractParameter
    {
        private string _title;

        public AxeInstantComplete() { }
        public AxeInstantComplete(string title) { _title = title; }

        protected override string GetTitle() => string.IsNullOrEmpty(_title) ? "Authorise the program" : _title;

        protected override void OnUpdate()
        {
            base.OnUpdate();
            if (State != ParameterState.Complete && Root != null && Root.ContractState == Contract.State.Active)
                SetComplete();
        }

        protected override void OnSave(ConfigNode node) { node.AddValue("title", _title ?? ""); }
        protected override void OnLoad(ConfigNode node) { _title = node.GetValue("title"); }
    }
}
