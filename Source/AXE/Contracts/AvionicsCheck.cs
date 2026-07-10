using Contracts;
using ContractConfigurator;
using ContractConfigurator.Parameters;

namespace RPAxe.Contracts
{
    // `PARAMETER { type = AvionicsCheck; continuousControlRequired = false }` — satisfied while the
    // vessel has enough avionics for control, i.e. AXE's avionics control-lock is NOT engaged.
    // Ported from RP-1's AvionicsCheckParameter, retargeted from RP-1's "RP0ControlLocker" lock id
    // to AXE's own "AxeAvionicsLock" (set by AxeAvionicsController whenever guidance is insufficient,
    // covering both the fully-locked and axial-only states). This was previously a no-op stand-in
    // (NoOpFactories.cs) mislabelled "avionics removed" — AXE rewrote avionics, it did not remove it,
    // so this now really gates the ~dozen contracts that use it.
    public class AvionicsCheckFactory : ParameterFactory
    {
        protected bool continuousControlRequired;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<bool>(configNode, "continuousControlRequired", x => continuousControlRequired = x, this, false);
            return valid;
        }

        public override ContractParameter Generate(Contract contract) => new AvionicsCheckParameter(title, continuousControlRequired);
    }

    public class AvionicsCheckParameter : VesselParameter
    {
        // The control lock AxeAvionicsController sets when the vessel lacks sufficient guidance.
        private const string AvionicsLockId = "AxeAvionicsLock";

        protected bool parameterIsSatisified { get; set; } = true;
        protected bool controlHasLapsed { get; set; }
        protected bool continuousControlRequired { get; set; }

        public AvionicsCheckParameter() : base(null) { }

        public AvionicsCheckParameter(string title, bool continuousControlRequired) : base(title)
        {
            this.continuousControlRequired = continuousControlRequired;
            this.title = GetParameterTitle();
        }

        protected override void OnParameterSave(ConfigNode node)
        {
            base.OnParameterSave(node);
            node.AddValue("continuousControlRequired", continuousControlRequired);
        }

        protected override void OnParameterLoad(ConfigNode node)
        {
            base.OnParameterLoad(node);
            continuousControlRequired = ConfigNodeUtil.ParseValue<bool>(node, "continuousControlRequired");
        }

        protected override void OnRegister()
        {
            base.OnRegister();
            // Re-check only when input locks change (cheap and exactly when avionics sufficiency flips).
            GameEvents.onInputLocksModified.Add(OnInputLocksModified);
        }

        protected override void OnUnregister()
        {
            base.OnUnregister();
            GameEvents.onInputLocksModified.Remove(OnInputLocksModified);
        }

        protected override string GetParameterTitle()
        {
            return continuousControlRequired
                ? controlHasLapsed
                    ? "Maintain sufficient avionics (failed, control was lost)"
                    : "Maintain sufficient avionics (do not lose control)"
                : "Have sufficient avionics for control";
        }

        private void OnInputLocksModified(GameEvents.FromToAction<ControlTypes, ControlTypes> data)
        {
            bool controlIsLocked = InputLockManager.GetControlLock(AvionicsLockId) != 0;

            // Track whether control was ever lost (for the continuous-control variant).
            controlHasLapsed |= controlIsLocked;

            parameterIsSatisified = continuousControlRequired ? !controlHasLapsed && !controlIsLocked : !controlIsLocked;

            // Refresh the contracts-screen title (state may have changed) and re-evaluate.
            GetTitle();
            CheckVessel(FlightGlobals.ActiveVessel);
        }

        protected override bool VesselMeetsCondition(Vessel vessel) => parameterIsSatisified;
    }
}
