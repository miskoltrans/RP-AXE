using System.Collections;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Per-flight controller that locks ATTITUDE control (yaw/pitch/roll + RCS translation) when the
    /// active vessel has no guidance — i.e. it's a "dumb rocket": throttle and staging still work, but
    /// you can't steer (fly it spin/fin-stabilized). The lock decision is <see cref="AxeControlLockerUtils"/>.
    ///
    /// Adapted from RP-1's ControlLocker (a Flight-scene MonoBehaviour following the active vessel),
    /// stripped to a binary lock and to attitude-only (no throttle/wheel locks, no mass logic).
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Flight, false)]
    public class AxeAvionicsController : MonoBehaviour
    {
        const ControlTypes LockMask = ControlTypes.YAW | ControlTypes.PITCH | ControlTypes.ROLL | ControlTypes.SAS;
        const string LockID = "AxeAvionicsLock";
        const float UpdateFrequency = 1f;

        Vessel _vessel;
        bool _locked;
        bool _requested;
        bool _started;
        readonly ScreenMessage _message = new ScreenMessage("", 6f, ScreenMessageStyle.UPPER_CENTER);

        // MechJeb deactivation (reflected once; same approach as RP-1 ControlLocker / AXE FreePartUnlock).
        static bool _mjResolved;
        static MethodInfo _getMasterMechJeb;
        static PropertyInfo _mjDeactivate;
        object _masterMechJeb;

        void Awake()
        {
            if (_mjResolved) return;
            _mjResolved = true;
            for (int i = 0; i < AssemblyLoader.loadedAssemblies.Count; i++)
            {
                AssemblyLoader.LoadedAssembly a = AssemblyLoader.loadedAssemblies[i];
                if (a.assembly.GetName().Name != "MechJeb2") continue;
                System.Type core = a.assembly.GetType("MuMech.MechJebCore");
                System.Type ext = a.assembly.GetType("MuMech.VesselExtensions");
                if (core != null) _mjDeactivate = core.GetProperty("DeactivateControl", BindingFlags.Public | BindingFlags.Instance);
                if (ext != null) _getMasterMechJeb = ext.GetMethod("GetMasterMechJeb", BindingFlags.Public | BindingFlags.Static);
                break;
            }
        }

        void Start()
        {
            GameEvents.onVesselWasModified.Add(OnVesselModified);
            GameEvents.onVesselCrewWasModified.Add(OnVesselModified);
            GameEvents.onVesselSwitching.Add(OnVesselSwitching);
            GameEvents.onStageActivate.Add(OnStage);
            _vessel = FlightGlobals.ActiveVessel;
            if (_vessel != null && _vessel.loaded) _vessel.OnPostAutopilotUpdate += FlightInputModifier;
            StartCoroutine(CheckLoop());
        }

        void OnVesselModified(Vessel v) { if (_started) _requested = true; }
        void OnStage(int s) { if (_started) _requested = true; }

        void OnVesselSwitching(Vessel from, Vessel to)
        {
            if (to != null && to.loaded) to.OnPostAutopilotUpdate += FlightInputModifier;
        }

        // Hard guarantee: zero steering every physics frame while locked; leave throttle & staging alone.
        void FlightInputModifier(FlightCtrlState st)
        {
            if (_locked)
            {
                st.yaw = st.pitch = st.roll = 0f;
                st.X = st.Y = st.Z = 0f;
            }
        }

        IEnumerator CheckLoop()
        {
            int i = 0;
            while ((FlightGlobals.ActiveVessel == null || FlightGlobals.ActiveVessel.packed) && i++ < 250)
                yield return new WaitForFixedUpdate();
            _started = true;
            Recompute();
            while (HighLogic.LoadedSceneIsFlight)
            {
                yield return new WaitForSeconds(UpdateFrequency);
                Recompute();
            }
        }

        void Update()
        {
            if (!HighLogic.LoadedSceneIsFlight || !FlightGlobals.ready)
            {
                InputLockManager.RemoveControlLock(LockID);
                return;
            }
            if (_vessel != FlightGlobals.ActiveVessel)
            {
                _vessel = FlightGlobals.ActiveVessel;
                _masterMechJeb = null;
                _requested = true;
            }
            if (_requested) { _requested = false; Recompute(); }
        }

        void Recompute()
        {
            if (_vessel == null) { SetLocked(false); return; }
            bool shouldLock = !CheatOptions.InfiniteElectricity && AxeControlLockerUtils.ShouldLock(_vessel.Parts);
            SetLocked(shouldLock);
            UpdateMechJeb();
        }

        void SetLocked(bool locked)
        {
            if (locked == _locked) return;
            _locked = locked;
            if (locked)
            {
                InputLockManager.SetControlLock(LockMask, LockID);
                _vessel.Autopilot.Disable();
                _vessel.ActionGroups.SetGroup(KSPActionGroup.SAS, false);
                _message.message = "Avionics: no guidance — attitude locked (throttle & staging only)";
            }
            else
            {
                InputLockManager.RemoveControlLock(LockID);
                _message.message = "Avionics: guidance online — controls unlocked";
            }
            ScreenMessages.PostScreenMessage(_message);
        }

        void UpdateMechJeb()
        {
            if (_getMasterMechJeb == null || _mjDeactivate == null) return;
            if (_masterMechJeb == null)
                _masterMechJeb = _getMasterMechJeb.Invoke(null, new object[] { FlightGlobals.ActiveVessel });
            if (_masterMechJeb != null)
                _mjDeactivate.SetValue(_masterMechJeb, _locked, null);
        }

        void OnDestroy()
        {
            InputLockManager.RemoveControlLock(LockID);
            GameEvents.onVesselWasModified.Remove(OnVesselModified);
            GameEvents.onVesselCrewWasModified.Remove(OnVesselModified);
            GameEvents.onVesselSwitching.Remove(OnVesselSwitching);
            GameEvents.onStageActivate.Remove(OnStage);
        }
    }
}
