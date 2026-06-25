using ContractConfigurator;

namespace RPAxe.Contracts
{
    // `BEHAVIOUR { type = ActivateProgram; program = X }` on a "Begin Program" charter contract:
    // marks program X started in AxeProgramHandler when the contract is accepted, so contracts gated
    // by `ProgramActive { program = X }` start being offered. This is the M4 program switcher.
    public class ActivateProgramFactory : BehaviourFactory
    {
        protected string program;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<string>(configNode, "program", x => program = x, this);
            return valid;
        }

        public override ContractBehaviour Generate(ConfiguredContract contract) => new ActivateProgram(program);
    }

    public class ActivateProgram : ContractBehaviour
    {
        private string _program;

        public ActivateProgram() { }
        public ActivateProgram(string program) { _program = program; }

        protected override void OnAccepted()
        {
            base.OnAccepted();
            AxeProgramHandler.Instance?.Activate(_program);
        }

        protected override void OnLoad(ConfigNode node)
        {
            base.OnLoad(node);
            node.TryGetValue("program", ref _program);
        }

        protected override void OnSave(ConfigNode node)
        {
            base.OnSave(node);
            node.AddValue("program", _program ?? "");
        }
    }
}
