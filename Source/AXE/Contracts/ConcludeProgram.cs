using ContractConfigurator;

namespace RPAxe.Contracts
{
    // `BEHAVIOUR { type = ConcludeProgram; program = X }` on the generated "Conclude Program: X"
    // contract (design/Programs/AxeProgramCompletion.cfg): closes program X out in
    // AxeProgramHandler, so it stops satisfying `ProgramActive { program = X }` and its member
    // contracts stop being offered. The mirror image of ActivateProgram, and the only way a program
    // ends — that contract is not offered until every one of the program's objectives is complete.
    //
    // Fires on COMPLETED, not accepted. ActivateProgram hooks OnAccepted because activating is
    // additive and harmless, but a closure has to wait: the contract sits Active for one frame while
    // AxeInstantComplete waits for `Root.ContractState == Active`, and pulling its own ProgramActive
    // requirement out from under it inside that window is exactly the state Contract Configurator
    // answers by failing the contract. By OnCompleted the contract is state Completed, which the
    // requirement re-check ignores outright.
    //
    // Registration is by convention, not by call: Contract Configurator reflects over every loaded
    // assembly for BehaviourFactory subclasses and registers each under its class name minus the
    // "Factory" suffix (see Source/AXE/_CCTYPES.md), so `ConcludeProgramFactory` is what makes
    // `type = ConcludeProgram` resolve. Renaming this class silently breaks the config.
    public class ConcludeProgramFactory : BehaviourFactory
    {
        protected string program;

        /// <summary>For AxeEconomySelfTest: proves this behaviour closes the same program its
        /// contract gates on, rather than a drifted or empty string.</summary>
        public string Program => program;

        public override bool Load(ConfigNode configNode)
        {
            bool valid = base.Load(configNode);
            valid &= ConfigNodeUtil.ParseValue<string>(configNode, "program", x => program = x, this);
            return valid;
        }

        public override ContractBehaviour Generate(ConfiguredContract contract) => new ConcludeProgram(program);
    }

    public class ConcludeProgram : ContractBehaviour
    {
        private string _program;

        public ConcludeProgram() { }
        public ConcludeProgram(string program) { _program = program; }

        protected override void OnCompleted()
        {
            base.OnCompleted();
            AxeProgramHandler.Instance?.Conclude(_program);
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
