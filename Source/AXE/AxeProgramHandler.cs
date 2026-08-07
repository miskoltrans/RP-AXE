using ContractConfigurator;
using Contracts;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// The lightweight replacement for RP-1's ProgramHandler: remembers which "programs" the player
    /// has started, and which have been concluded. A program is started by accepting its
    /// "Begin Program" charter contract (see the ActivateProgram behaviour); contracts gated by
    /// `ProgramActive` then become offerable. No funding curves, confidence, slots, or deadlines —
    /// that economy is intentionally gone.
    ///
    /// Programs have three states, mirroring RP-1 (Program.IsActive => !IsComplete &amp;&amp;
    /// acceptedUT != 0): Inactive -> Active -> Concluded. Only Active satisfies `ProgramActive`, so
    /// concluding a program is what stops its member contracts being offered. The transition is
    /// one-way and earned: the only route is the generated "Conclude Program: X" contract, which is
    /// not offered until every one of the program's objectives has been completed. There is
    /// deliberately no way to abandon a program you have started — of the 35 chartered programs, 34
    /// can be finished by flying their objectives, so an abandon path would exist for one config bug
    /// (see tools/build_economy.py's reachability gate).
    /// </summary>
    [KSPScenario(
        ScenarioCreationOptions.AddToNewCareerGames | ScenarioCreationOptions.AddToExistingCareerGames |
        ScenarioCreationOptions.AddToNewScienceSandboxGames | ScenarioCreationOptions.AddToExistingScienceSandboxGames,
        GameScenes.SPACECENTER, GameScenes.FLIGHT, GameScenes.TRACKSTATION, GameScenes.EDITOR)]
    public class AxeProgramHandler : ScenarioModule
    {
        public static AxeProgramHandler Instance { get; private set; }

        private readonly HashSet<string> _active = new HashSet<string>();
        private readonly HashSet<string> _concluded = new HashSet<string>();

        public override void OnAwake()
        {
            base.OnAwake();
            Instance = this;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        public bool IsActive(string program) => !string.IsNullOrEmpty(program) && _active.Contains(program);

        public bool AllActive(List<string> programs)
        {
            if (programs == null || programs.Count == 0) return true; // not program-gated
            foreach (string p in programs)
                if (!_active.Contains(p)) return false;
            return true;
        }

        public bool IsConcluded(string program) =>
            !string.IsNullOrEmpty(program) && _concluded.Contains(program);

        public void Activate(string program)
        {
            if (!string.IsNullOrEmpty(program) && _active.Add(program))
            {
                Debug.Log("[AXE] Program activated: " + program);
                AxeProgramGroupVisibility.Sync();
            }
        }

        /// <summary>
        /// Close a program out: it stops satisfying `ProgramActive`, so its member contracts stop
        /// being offered. Called from the ConcludeProgram behaviour on the "Conclude Program: X"
        /// contract, which cannot be offered until every objective is done.
        ///
        /// Contracts of this program that are already ACCEPTED are unaffected and stay flyable —
        /// that is what `checkOnActiveContract = false` in ProgramActiveRequirement buys, and it is
        /// load-bearing here rather than cosmetic: Contract Configurator calls `Contract.Fail()` on
        /// an Active contract whose requirements stop holding, and stock's Fail() runs
        /// PenalizeFailure(). Without it, collecting the bonus while any of the 66 repeatable member
        /// contracts was in flight would hand the player a failure penalty for finishing a program.
        /// </summary>
        public void Conclude(string program)
        {
            if (string.IsNullOrEmpty(program)) return;
            _active.Remove(program);
            if (_concluded.Add(program))
                Debug.Log("[AXE] Program concluded: " + program);
            // The program's Mission Control folder goes away with it — see
            // AxeProgramGroupVisibility. Its already-accepted missions are unaffected.
            AxeProgramGroupVisibility.Sync();
        }

        // --- Reconciliation against the contract log -------------------------------------------
        //
        // A "Conclude Program: X" contract that COMPLETED is the authoritative record that X is
        // closed, and it is a stronger record than this scenario node: the contract log is written
        // by stock, while the Conclude() call that updates this node depends on the ConcludeProgram
        // BEHAVIOUR being attached to that contract at the moment it completed.
        //
        // It was not always attached. Saves exist in which AXE_Complete_SuborbRocketDev,
        // AXE_Complete_SuborbRocketResearch and AXE_Complete_EarlySatellites are all state =
        // Completed with NO BEHAVIOUR block at all — generated before the behaviour shipped. The
        // money paid, the contract closed, and the program stayed active forever. It cannot be
        // repaired by replaying the contract either: maxCompletions = 1, so it is never re-offered.
        //
        // That was cosmetic while charters gated on ProgramActive. It stopped being cosmetic when
        // they moved to ProgramConcluded: a program stuck Active is now one whose successors can
        // never be chartered, which is the exact softlock that change existed to remove. So the
        // handler reconciles instead of trusting its own node.
        //
        // The prefix has to match tools/build_economy.py's `AXE_Complete_{name}`.
        private const string CompletePrefix = "AXE_Complete_";
        private bool _reconcilePending;

        private void Update()
        {
            Reconcile();
            // A program that just started or ended changes which Mission Control folders exist. The
            // redraw has to happen a frame later than the change that caused it, off a flag, rather
            // than inside Activate()/Conclude() — see AxeProgramGroupVisibility.RefreshIfPending.
            AxeProgramGroupVisibility.RefreshIfPending();
        }

        private void Reconcile()
        {
            if (!_reconcilePending) return;
            // Readiness is TESTED, never latched: ContractSystem.loaded is set false in its OnAwake
            // and true at the end of its OnLoad, so a scenario that loads before it reads a live but
            // EMPTY contract list. Answering "nothing is finished" from that frame would silently
            // decline to repair anything. Staying pending until the list is really there costs one
            // branch per frame.
            if (!ContractSystem.loaded || ContractSystem.Instance == null) return;
            List<Contract> finished = ContractSystem.Instance.ContractsFinished;
            if (finished == null) return;

            _reconcilePending = false;
            foreach (Contract c in finished)
            {
                if (c == null || c.ContractState != Contract.State.Completed) continue;
                ConfiguredContract cc = c as ConfiguredContract;
                if (cc == null) continue;
                // subType is read straight off the save node in ConfiguredContract.OnLoad and
                // survives a contractType that failed to resolve; contractType.name is the fallback.
                string sub = !string.IsNullOrEmpty(cc.subType) ? cc.subType : cc.contractType?.name;
                if (string.IsNullOrEmpty(sub) || !sub.StartsWith(CompletePrefix)) continue;

                string program = sub.Substring(CompletePrefix.Length);
                if (_concluded.Contains(program)) continue;
                Debug.LogWarning("[AXE] Program " + program + " has a completed conclusion contract "
                                 + "but was not recorded as concluded — repairing. (Save predates the "
                                 + "ConcludeProgram behaviour.)");
                Conclude(program);
            }

            // Unconditional, not just when the repair loop changed something: `enabled` is static
            // per KSP session, so a save loaded after another one carries the previous career's
            // hidden folders until this runs. Conclude() also calls it, but only for programs it
            // actually closed.
            AxeProgramGroupVisibility.Sync();
        }

        public override void OnSave(ConfigNode node)
        {
            foreach (string p in _active)
                node.AddValue("activeProgram", p);
            foreach (string p in _concluded)
                node.AddValue("concludedProgram", p);
        }

        public override void OnLoad(ConfigNode node)
        {
            // `concludedProgram` is additive: a save written before program conclusion existed has
            // no such keys and loads as "nothing concluded yet", which is correct.
            _active.Clear();
            _concluded.Clear();
            foreach (string p in node.GetValues("activeProgram"))
                _active.Add(p);
            foreach (string p in node.GetValues("concludedProgram"))
            {
                _concluded.Add(p);
                _active.Remove(p);
            }
            // What the node says is only a starting point — see Update(). Re-armed on every load
            // rather than run once per career: it is idempotent, and a scene that loads before the
            // contract system has to get its chance in a later frame.
            _reconcilePending = true;
        }
    }
}
