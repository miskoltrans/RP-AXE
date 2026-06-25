using ContractConfigurator;
using System.Collections.Generic;

namespace RPAxe.Contracts
{
    /// <summary>
    /// `REQUIREMENT { type = ProgramActive }` — RP-1's gate that only offers a contract while its
    /// Program is active (~368 uses across the contract set).
    ///
    /// M4: met only when all named program(s) have been started in AxeProgramHandler (via a
    /// "Begin Program" charter contract). Before any handler exists (e.g. evaluated with no game
    /// loaded) it is not met.
    /// </summary>
    public class ProgramActiveRequirement : ContractRequirement
    {
        protected List<string> programs = new List<string>();

        public override bool LoadFromConfig(ConfigNode configNode)
        {
            bool valid = base.LoadFromConfig(configNode);
            checkOnActiveContract = configNode.HasValue("checkOnActiveContract") ? checkOnActiveContract : true;
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
