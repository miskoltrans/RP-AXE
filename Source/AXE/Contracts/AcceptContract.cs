using Contracts;
using ContractConfigurator;
using System;
using System.Linq;

namespace RPAxe.Contracts
{
    // `BEHAVIOUR { type = AcceptContractBehaviour; contractType = X; eventType = Completed }` —
    // auto-accepts the offered contract named X when this contract hits the given lifecycle event.
    // Used by RP-1 for graduated/onboarding contract chains. Self-contained CC plumbing.
    public enum ContractEventType
    {
        Offered = 0, Accepted = 1, Completed = 2, Failed = 3, Cancelled = 4,
        Finished = 5, Declined = 6, DeadlineExpired = 7, OfferExpired = 8, Withdrawn = 9
    }

    public class AcceptContractBehaviourFactory : BehaviourFactory
    {
        protected string ccType;
        protected ContractEventType eventType;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<string>(configNode, "contractType", x => ccType = x, this);
            valid &= ConfigNodeUtil.ParseValue<ContractEventType>(configNode, "eventType", x => eventType = x, this);
            return valid;
        }

        public override ContractBehaviour Generate(ConfiguredContract contract) => new AcceptContractBehaviour(ccType, eventType);
    }

    public class AcceptContractBehaviour : ContractBehaviour
    {
        private string _ccType;
        private ContractEventType _evt;

        public AcceptContractBehaviour() { }
        public AcceptContractBehaviour(string ccType, ContractEventType evt) { _ccType = ccType; _evt = evt; }

        protected override void OnOffered() { if (_evt == ContractEventType.Offered) TryAccept(); }
        protected override void OnAccepted() { if (_evt == ContractEventType.Accepted) TryAccept(); }
        protected override void OnCompleted() { if (_evt == ContractEventType.Completed) TryAccept(); }
        protected override void OnFailed() { if (_evt == ContractEventType.Failed) TryAccept(); }
        protected override void OnCancelled() { if (_evt == ContractEventType.Cancelled) TryAccept(); }

        protected override void OnLoad(ConfigNode node)
        {
            base.OnLoad(node);
            node.TryGetValue("contractType", ref _ccType);
            string s = null;
            node.TryGetValue("eventType", ref s);
            if (!string.IsNullOrEmpty(s)) _evt = (ContractEventType)Enum.Parse(typeof(ContractEventType), s);
        }

        protected override void OnSave(ConfigNode node)
        {
            base.OnSave(node);
            node.AddValue("contractType", _ccType ?? "");
            node.AddValue("eventType", _evt.ToString());
        }

        private void TryAccept()
        {
            ConfiguredContract c = ConfiguredContract.CurrentContracts.FirstOrDefault(
                x => x != null && x.contractType != null && x.contractType.name == _ccType && x.ContractState == Contract.State.Offered);
            c?.Accept();
        }
    }
}
