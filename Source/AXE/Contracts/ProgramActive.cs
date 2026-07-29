using ContractConfigurator;
using System.Collections.Generic;

namespace RPAxe.Contracts
{
    /// <summary>
    /// `REQUIREMENT { type = ProgramActive }` — RP-1's gate that only offers a contract while its
    /// Program is active (~368 uses across the contract set).
    ///
    /// M4: met only when all named program(s) have been started in AxeProgramHandler (via a
    /// "Begin Program" charter contract) and not yet concluded. Before any handler exists (e.g.
    /// evaluated with no game loaded) it is not met.
    /// </summary>
    public class ProgramActiveRequirement : ContractRequirement
    {
        protected List<string> programs = new List<string>();

        /// <summary>Read-only views for AxeEconomySelfTest, which asserts every completion contract
        /// closes the same program it gates on, and that nothing re-enables the penalty path below.</summary>
        public List<string> Programs => programs;
        public bool ChecksOnActiveContract => checkOnActiveContract;

        public override bool LoadFromConfig(ConfigNode configNode)
        {
            bool valid = base.LoadFromConfig(configNode);
            // DIVERGES FROM RP-1, which defaults this to true. Contract Configurator re-checks
            // requirements on contracts that are already ACTIVE when this is true, and
            // ContractRequirement.RequirementsMet responds to a now-unmet requirement by calling
            // `Contract.Fail()` — which in stock runs PenalizeFailure() and posts a red failure
            // message. Since AxeProgramHandler gained a Conclude() path, a program CAN stop being
            // active mid-career, so with RP-1's default, collecting a program's completion bonus
            // would fail every member contract the player had in flight — including any of the 66
            // repeatable ones — and charge them for it.
            //
            // false means concluding a program stops it being OFFERED new work (an offered contract
            // that stops meeting requirements is Withdrawn, which has no penalty path) while
            // anything already accepted stays flyable. "Finish what you signed up for" is also the
            // kinder reading. A contract that genuinely must die with its program can still opt in
            // by writing `checkOnActiveContract = true` itself.
            checkOnActiveContract = configNode.HasValue("checkOnActiveContract") ? checkOnActiveContract : false;
            valid &= ConfigNodeUtil.ParseValue(configNode, "program", x => programs = x, this, new List<string>());
            return valid;
        }

        public override void OnLoad(ConfigNode configNode)
        {
            programs = ConfigNodeUtil.ParseValue(configNode, "program", new List<string>());
        }

        public override void OnSave(ConfigNode configNode)
        {
            foreach (string p in programs)
                configNode.AddValue("program", p);
        }

        public override bool RequirementMet(ConfiguredContract contract)
        {
            return AxeProgramHandler.Instance != null && AxeProgramHandler.Instance.AllActive(programs);
        }

        protected override string RequirementText()
        {
            string list = programs != null && programs.Count > 0 ? string.Join(", ", programs.ToArray()) : "";
            return invertRequirement ? $"Must not have active program: {list}" : $"Program: {list}";
        }
    }
}
