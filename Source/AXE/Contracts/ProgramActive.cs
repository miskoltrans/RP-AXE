using ContractConfigurator;
using System.Collections.Generic;

namespace RPAxe.Contracts
{
    /// <summary>
    /// `REQUIREMENT { type = ProgramActive }` — RP-1's gate that only offers a contract while its
    /// Program is active (~368 uses across the contract set).
    ///
    /// M2: always met, so the program-gated contracts load and are offered. M4 (the program
    /// switcher) will make this real — return true only when the named program(s) have been
    /// started in our AxeProgramHandler. The `program` values are parsed now so configs are
    /// preserved verbatim and the M4 change is a one-method edit.
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
            // M2 stub: always available. M4 wires this to AxeProgramHandler.IsActive(programs).
            return true;
        }

        protected override string RequirementText()
        {
            string list = programs != null && programs.Count > 0 ? string.Join(", ", programs.ToArray()) : "";
            return invertRequirement ? $"Must not have active program: {list}" : $"Program: {list}";
        }
    }
}
