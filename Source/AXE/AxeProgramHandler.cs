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
                Debug.Log("[AXE] Program activated: " + program);
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
            // no such keys and loads as "nothing concluded yet", which is correct. No migration.
            _active.Clear();
            _concluded.Clear();
            foreach (string p in node.GetValues("activeProgram"))
                _active.Add(p);
            foreach (string p in node.GetValues("concludedProgram"))
            {
                _concluded.Add(p);
                _active.Remove(p);
            }
        }
    }
}
