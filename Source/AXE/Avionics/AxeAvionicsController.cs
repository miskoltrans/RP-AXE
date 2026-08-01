using System.Collections;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Per-flight controller that locks ATTITUDE control (yaw/pitch/roll + RCS translation) when the active
    /// vessel lacks full guidance. Three levels (from <see cref="AxeControlLockerUtils"/>):
    ///   * Unlocked — full control.
    ///   * Axial    — rotation + lateral translation locked, but axial-thrust (Z) translation allowed, so a
    ///     spin-stabilized Science-Core kick stage can still fire along its axis.
    ///   * Locked   — "dumb rocket": throttle + staging only.
    ///
    /// Adapted from RP-1's ControlLocker (a Flight-scene MonoBehaviour following the active vessel),
    /// attitude-only (no throttle/wheel locks, no mass logic).
    /// </summary>
    [KSPAddon(KSPAddon.Startup.Flight, false)]
    public class AxeAvionicsController : MonoBehaviour
    {
        const ControlTypes LockMask = ControlTypes.YAW | ControlTypes.PITCH | ControlTypes.ROLL | ControlTypes.SAS;
        const string LockID = "AxeAvionicsLock";
        const float UpdateFrequency = 1f;

        /// <summary>The controller following the active vessel in the current Flight scene (null otherwise).</summary>
        public static AxeAvionicsController Instance { get; private set; }
        /// <summary>Current avionics lock level for the active vessel. Read by the RCS control-lock patch
        /// (<see cref="AxeRcsControlLock"/>), which the per-vessel <see cref="FlightInputModifier"/> can't reach
        /// because ModuleRCS reads ctrlState on its own Update, before the post-autopilot hook re-zeros it.</summary>
        public AxeControlLockerUtils.LockLevel Level => _level;

        /// <summary>PROTOTYPE: control-noise amplitude in [0..NoiseMax]. 0 unless over capacity.</summary>
        public float ControlNoise => _noise;

        // PROTOTYPE DIAGNOSTIC. FlightInputModifier is a callback registered on the vessel; if it is not
        // subscribed, or the branch is not reached, nothing happens and the symptom is identical to "the
        // noise is too small to see". Ticks proves the hook runs; LastNoise proves what it injected.
        public int ModifierTicks { get; private set; }
        public Vector3 LastNoise { get; private set; }

        Vessel _vessel;
        AxeControlLockerUtils.LockLevel _level = AxeControlLockerUtils.LockLevel.Unlocked;
        float _noise = 0f;
        bool _requested;
        bool _started;
        readonly ScreenMessage _message = new ScreenMessage("", 6f, ScreenMessageStyle.UPPER_CENTER);

        // MechJeb deactivation (reflected once; same approach as RP-1 ControlLocker / AXE FreePartUnlock).
        static bool _mjResolved;
        static MethodInfo _getMasterMechJeb;
        static PropertyInfo _mjDeactivate;
        object _masterMechJeb;

        // Shared regime callout. Screen messages are the only channel KSP gives us that does not need the
        // player to have a PAW open, and a missed transition is the difference between "my avionics is
        // undersized" and "this mod is broken".
        static readonly ScreenMessage _announce = new ScreenMessage("", 7f, ScreenMessageStyle.UPPER_CENTER);
        public static void Announce(string text)
        {
            _announce.message = text;
            ScreenMessages.PostScreenMessage(_announce);
        }

        void Awake()
        {
            Instance = this;   // set before the (static, one-shot) MechJeb-reflection guard below
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

        // Hard guarantee, every physics frame: while locked, zero steering + lateral translation; leave throttle
        // & staging alone. Axial level additionally permits Z (axial-thrust) translation for spin-stabilized stages.
        //
        // PROTOTYPE v2 (docs/AVIONICS_AUTHORITY.md): while UNLOCKED but over capacity, correlated NOISE is added
        // to the rotation commands rather than the axes being scaled. v1 scaled them and was killed by test --
        // at q=0.05 a craft ascended normally and flew BETTER, because lowering loop gain raises stability
        // margin. An autopilot can correct a disturbance's average but cannot anticipate it, so noise is the
        // one perturbation MechJeb has nothing to absorb it with.
        //
        // Rotation only: translation noise would mostly burn RCS without being felt on a launch vehicle.
        // This hook covers reaction wheels, engine gimbal and aerodynamic surfaces; ModuleRCS reads ctrlState
        // on its own Unity pass and is handled by AxeRcsControlLock.
        void FlightInputModifier(FlightCtrlState st)
        {
            ModifierTicks++;   // advances whenever the hook runs at all, noise or not
            if (_level == AxeControlLockerUtils.LockLevel.Unlocked)
            {
                if (_noise <= 0f) { LastNoise = Vector3.zero; return; }
                float y0 = st.yaw, p0 = st.pitch, r0 = st.roll;
                AxeControlPenalties.Current.Apply(ref st.pitch, ref st.yaw, ref st.roll, _noise);
                LastNoise = new Vector3(st.pitch - p0, st.yaw - y0, st.roll - r0);
                return;
            }
            LastNoise = Vector3.zero;
            st.yaw = st.pitch = st.roll = 0f;
            st.X = st.Y = 0f;
            if (_level == AxeControlLockerUtils.LockLevel.Locked) st.Z = 0f;
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
                // Per-vessel state for modes 3/4: coupling coefficients are seeded from the vessel so the
                // misalignment is a stable characteristic of THIS craft, and the delay buffer must not carry
                // another vessel's commands across the switch.
                AxeControlPenalties.Current.Reset(_vessel);
            }
            if (_requested) { _requested = false; Recompute(); }
        }

        void Recompute()
        {
            if (_vessel == null) { _noise = 0f; SetLevel(AxeControlLockerUtils.LockLevel.Unlocked); return; }
            AxeControlLockerUtils.LockLevel lvl;
            if (CheatOptions.InfiniteElectricity)
            {
                lvl = AxeControlLockerUtils.LockLevel.Unlocked;
                _noise = 0f;
            }
            else
            {
                lvl = AxeControlLockerUtils.ShouldLock(_vessel.Parts, out _, out float vesselMass, out _noise);
                // Each vehicle is perturbed at its OWN attitude-response frequency (Hz ~ m^-1/3), which is
                // what keeps the effect comparable between a 5 t probe and a 300 t stack instead of being
                // accidentally tuned to whatever was last flown.
                AxeControlLockerUtils.EffectiveNoiseHz = AxeControlLockerUtils.HzForMass(vesselMass);
            }
            SetLevel(lvl);
            UpdateMechJeb();
        }

        void SetLevel(AxeControlLockerUtils.LockLevel level)
        {
            if (level == _level) return;
            _level = level;
            if (level != AxeControlLockerUtils.LockLevel.Unlocked)
            {
                InputLockManager.SetControlLock(LockMask, LockID);
                _vessel.Autopilot.Disable();
                _vessel.ActionGroups.SetGroup(KSPActionGroup.SAS, false);
                _message.message = level == AxeControlLockerUtils.LockLevel.Axial
                    ? "Avionics: spin-stabilized — axial thrust only (no steering)"
                    : "Avionics: no guidance — attitude locked (throttle & staging only)";
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
                _mjDeactivate.SetValue(_masterMechJeb, _level != AxeControlLockerUtils.LockLevel.Unlocked, null);
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
            InputLockManager.RemoveControlLock(LockID);
            GameEvents.onVesselWasModified.Remove(OnVesselModified);
            GameEvents.onVesselCrewWasModified.Remove(OnVesselModified);
            GameEvents.onVesselSwitching.Remove(OnVesselSwitching);
            GameEvents.onStageActivate.Remove(OnStage);
        }
    }
}
