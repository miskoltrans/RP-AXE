using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// The lightweight replacement for RP-1's ProgramHandler: just remembers which "programs" the
    /// player has started. A program is started by accepting its "Begin Program" charter contract
    /// (see the ActivateProgram behaviour); contracts gated by `ProgramActive` then become offerable.
    /// No funding curves, confidence, slots, or deadlines — that economy is intentionally gone.
    /// </summary>
    [KSPScenario(
        ScenarioCreationOptions.AddToNewCareerGames | ScenarioCreationOptions.AddToExistingCareerGames |
        ScenarioCreationOptions.AddToNewScienceSandboxGames | ScenarioCreationOptions.AddToExistingScienceSandboxGames,
        GameScenes.SPACECENTER, GameScenes.FLIGHT, GameScenes.TRACKSTATION, GameScenes.EDITOR)]
    public class AxeProgramHandler : ScenarioModule
    {
        public static AxeProgramHandler Instance { get; private set; }

        private readonly HashSet<string> _active = new HashSet<string>();

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

        public void Activate(string program)
        {
            if (!string.IsNullOrEmpty(program) && _active.Add(program))
                Debug.Log("[AXE] Program activated: " + program);
        }

        public override void OnSave(ConfigNode node)
        {
            foreach (string p in _active)
                node.AddValue("activeProgram", p);
        }

        public override void OnLoad(ConfigNode node)
        {
            _active.Clear();
            foreach (string p in node.GetValues("activeProgram"))
                _active.Add(p);
        }
    }
}
