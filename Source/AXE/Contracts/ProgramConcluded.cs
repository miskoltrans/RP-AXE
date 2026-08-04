using ContractConfigurator;
using System.Collections.Generic;

namespace RPAxe.Contracts
{
    /// <summary>
    /// `REQUIREMENT { type = ProgramConcluded }` — met once the named program(s) have been CLOSED
    /// OUT, i.e. their "Conclude Program: X" contract has been completed. The gate the successor
    /// charters in design/Programs/ActivatePrograms.cfg use.
    ///
    /// WHY THIS EXISTS RATHER THAN ProgramActive. The charters originally gated on the predecessor
    /// being ACTIVE, which made progression a trap: `AxeProgramHandler.Conclude()` moves a program
    /// out of `_active`, conclusion is one-way, and every charter is `maxCompletions = 1`. So
    /// collecting a program's completion bonus permanently withdrew the charters that depended on
    /// it — 16 of the 35 programs could brick a branch that way, and concluding EarlySatellites
    /// alone killed seven successors with no warning. Gating on conclusion instead makes the
    /// dependency monotonic: it goes unmet -> met exactly once and never comes back, so there is no
    /// state in which a successor becomes unreachable.
    ///
    /// It also makes conclusion mean something. Concluding a program stops its own missions being
    /// offered (that is `ProgramActive` on the member contracts, unchanged); what it now buys is the
    /// next tier of programs. Conclusion is the hand-off, not just a payout.
    ///
    /// Reachability was checked before the swap: every objective of every program is gated on that
    /// same program, so no program's objectives sit behind an ancestor that would already be closed
    /// by the time it charters, and no seed contract requires two programs active at once (which
    /// this change would have made unsatisfiable, since a predecessor is always concluded by the
    /// time its successor starts).
    ///
    /// Registration is by convention: Contract Configurator reflects over loaded assemblies for
    /// ContractRequirement subclasses and registers each under its class name minus the
    /// "Requirement" suffix (see Source/AXE/_CCTYPES.md), so `ProgramConcludedRequirement` is what
    /// makes `type = ProgramConcluded` resolve. Renaming this class silently breaks the config.
    /// </summary>
    public class ProgramConcludedRequirement : ContractRequirement
    {
        protected List<string> programs = new List<string>();

        /// <summary>Read-only view for AxeEconomySelfTest, which asserts every charter gates on a
        /// program some completion contract actually closes.</summary>
        public List<string> Programs => programs;

        public override bool LoadFromConfig(ConfigNode configNode)
        {
            bool valid = base.LoadFromConfig(configNode);
            // Matches ProgramActiveRequirement's divergence from RP-1 for consistency, though the
            // penalty path it guards cannot fire here: this requirement is monotonic, so a contract
            // that was offered or accepted under it can never see it go unmet, and CC's
            // Contract.Fail() -> stock PenalizeFailure() route is unreachable either way.
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
            if (programs == null || programs.Count == 0) return true; // not program-gated
            if (AxeProgramHandler.Instance == null) return false;
            foreach (string p in programs)
                if (!AxeProgramHandler.Instance.IsConcluded(p)) return false;
            return true;
        }

        protected override string RequirementText()
        {
            string list = programs != null && programs.Count > 0 ? string.Join(", ", programs.ToArray()) : "";
            return invertRequirement ? $"Must not have completed program: {list}" : $"Completed program: {list}";
        }
    }
}
