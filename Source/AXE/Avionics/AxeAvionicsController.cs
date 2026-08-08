using System.Collections;
using System.Collections.Generic;
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

        // A3 regime callouts. Remembering the previous capacity is what lets "mass rose past capacity" be
        // told apart from "capacity fell because you staged the primary unit" -- both land in the degraded
        // regime, both look identical from the cockpit, and they have different remedies.
        bool _wasDegraded;
        float _lastCapacity = -1f;
        float _nextReminder;
        const float ReminderInterval = 30f;
        bool _requested;
        bool _started;
        readonly ScreenMessage _message = new ScreenMessage("", 6f, ScreenMessageStyle.UPPER_CENTER);

        // MechJeb deactivation (reflected once; same approach as RP-1 ControlLocker / AXE FreePartUnlock).
        static bool _mjResolved;
        static MethodInfo _getMasterMechJeb;
        static PropertyInfo _mjDeactivate;
        object _masterMechJeb;

        // Star-tracker consequence for MechJeb (docs/AVIONICS_SPEC.md, Axis 2). MechJeb ignores
        // SASServiceLevel entirely -- no reference to it, AvailableAtLevel, CanEngageSAS or AutopilotSkill
        // anywhere in its binary -- so the stock-SAS half of the mechanic does nothing to it and it has to
        // be closed separately.
        static MethodInfo _mjGetModule;       // MechJebCore.GetComputerModule(string)
        static PropertyInfo _mjModuleEnabled; // ComputerModule.Enabled

        // Disabling the client modules is NOT sufficient on its own, which in-flight testing proved:
        //   1. MechJebModuleSmartASS is a DisplayModule, and DisplayModule.Enabled is WINDOW VISIBILITY.
        //      It is persisted as EnabledEditor/EnabledFlight and restored on load, so clearing it just
        //      closes a window the player reopens.
        //   2. SmartASS commands via Core.Attitude.attitudeTo(target, ref, this), registering itself in the
        //      attitude controller's `Users` pool. The CONTROLLER then flies the attitude. Disabling the
        //      client afterwards leaves that registration — and the hold — completely untouched.
        // So the real lever is the controller's own user pool: pull the disallowed clients out of Users,
        // continuously. UserPool.Remove is already exactly scoped -- it drops that one user and disables
        // the controller only if the pool is left empty.
        //
        // attitudeDeactivate() is deliberately NOT resolved or called. It is `Users.Clear()`, a BLANKET
        // wipe that also evicts MechJebModuleAscentBaseAutopilot and shuts the controller down; calling it
        // killed ascent guidance mid-launch whenever SmartASS happened to be in the pool at the same time.
        static MemberInfo _mjUsersMember;          // .Users (UserPool : List<object>)
        static MethodInfo _mjUsersRemove;          // UserPool.Remove(object) -- the DECLARED one, see below

        // Gate the CLIENTS of the attitude service, never MechJebModuleAttitudeController itself. That is
        // the shared service (Core.Attitude, with a Users list that NodeExecutor, SmartASS and the ASCENT
        // autopilot all register into); disabling it would also kill ascent guidance -- which is near-Earth
        // technology, a pitch program flown on gyros and local vertical that never needs a star. Ascent
        // stays available to everyone, always, by design. Only these two need an inertial frame.
        static readonly string[] MjAttitudeClients = { "MechJebModuleSmartASS", "MechJebModuleNodeExecutor" };
        bool _mjClientsAllowed = true;
        // Callout throttle: a still-selected SmartASS mode re-asserts every frame, so the eviction --
        // and therefore the message -- would otherwise repeat at frame rate.
        const float AttitudeNagInterval = 8f;
        float _nextAttitudeNag;

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
                // MechJebCore.GetComputerModule has a STRING overload, so the attitude clients can be
                // reached without AXE referencing any MuMech type. ComputerModule.Enabled is a plain public
                // property, and MechJebCore.Drive gates on `if (computerModule.Enabled)` before calling each
                // module's Drive(s) -- verified, so clearing it really does stop the module flying.
                if (core != null)
                    _mjGetModule = core.GetMethod("GetComputerModule", BindingFlags.Public | BindingFlags.Instance,
                                                  null, new System.Type[] { typeof(string) }, null);
                System.Type cm = a.assembly.GetType("MuMech.ComputerModule");
                if (cm != null) _mjModuleEnabled = cm.GetProperty("Enabled", BindingFlags.Public | BindingFlags.Instance);

                System.Type att = a.assembly.GetType("MuMech.MechJebModuleAttitudeController");
                if (att != null)
                {
                    _mjUsersMember = (MemberInfo)att.GetField("Users", BindingFlags.Public | BindingFlags.Instance)
                                  ?? att.GetProperty("Users", BindingFlags.Public | BindingFlags.Instance);
                }
                System.Type pool = a.assembly.GetType("MuMech.UserPool");
                if (pool != null)
                    _mjUsersRemove = pool.GetMethod("Remove",
                                                    BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly,
                                                    null, new System.Type[] { typeof(object) }, null);
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
                // Disarmed passes sigma = 0 rather than skipping Apply: every stateful move still advances,
                // so re-arming cannot read a stale delay buffer or a cold EMA and jump. Zero sigma is a
                // no-op inside every penalty by construction.
                float sigma = AxeControlLockerUtils.ComputeArmed(st) ? _noise : 0f;
                float y0 = st.yaw, p0 = st.pitch, r0 = st.roll;
                AxeControlPenalties.Current.Apply(ref st.pitch, ref st.yaw, ref st.roll, sigma);
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
                // Reset to MechJeb's own default for a freshly-loaded vessel. Without this, switching
                // between two craft that BOTH lack a reference sees no transition and the new vessel's
                // modules (separate objects) are never disabled.
                _mjClientsAllowed = true;
                _requested = true;
                // Per-vessel state for modes 3/4: coupling coefficients are seeded from the vessel so the
                // misalignment is a stable characteristic of THIS craft, and the delay buffer must not carry
                // another vessel's commands across the switch.
                AxeControlPenalties.Current.Reset(_vessel);
            }
            if (_requested) { _requested = false; Recompute(); }
            // Every frame, not at Recompute's 1 Hz: a vector hold commanded between polls would otherwise
            // stand for up to a second. Cheap, and a no-op whenever the vessel has an attitude reference.
            EnforceAttitudeClients();
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
                lvl = AxeControlLockerUtils.ShouldLock(_vessel.Parts, out float maxCap, out float vesselMass, out _noise);
                AnnounceRegime(maxCap, vesselMass, lvl);
                // Each vehicle is perturbed at its OWN attitude-response frequency (Hz ~ m^-1/3), which is
                // what keeps the effect comparable between a 5 t probe and a 300 t stack instead of being
                // accidentally tuned to whatever was last flown.
                AxeControlLockerUtils.EffectiveNoiseHz = AxeControlLockerUtils.HzForMass(vesselMass);
            }
            SetLevel(lvl);
            UpdateMechJeb();
        }

        // Called once per recompute (1 Hz). Announces entry to and exit from the degraded regime, naming
        // WHY -- and re-posts periodically while degraded, because a player in map view during staging
        // misses the entry message and then has no persistent indicator short of opening a PAW. A missed
        // callout is the difference between "my avionics is undersized" and "this mod is broken".
        void AnnounceRegime(float maxCapacity, float vesselMass, AxeControlLockerUtils.LockLevel lvl)
        {
            // "Guided" means a unit is actually flying the vessel right now. Staging onto an unguided stage
            // also leaves the degraded regime, but that is a LOSS of guidance, not a return to it.
            bool guided = lvl == AxeControlLockerUtils.LockLevel.Unlocked && maxCapacity > 0f;
            bool degraded = _noise > 0f && guided;

            if (degraded && !_wasDegraded)
            {
                bool capacityFell = _lastCapacity >= 0f && maxCapacity < _lastCapacity - 0.01f;
                Announce(capacityFell
                    ? $"Primary avionics staged — remaining unit rated {maxCapacity:N1} t, vessel {vesselMass:N1} t. Guidance degraded."
                    : $"Avionics over capacity — {vesselMass:N1} t vs {maxCapacity:N1} t rated. Guidance degraded.");
                _nextReminder = Time.time + ReminderInterval;
            }
            else if (!degraded && _wasDegraded)
            {
                // Only claim nominal if the vessel really is guided again. Dropping to an unguided stage
                // exits the degraded regime too, and announcing "nominal control" there is actively wrong --
                // SetLevel already posts the correct message for that transition.
                if (guided) Announce("Vessel within avionics rating. Guidance nominal.");
            }
            else if (degraded && Time.time >= _nextReminder)
            {
                Announce($"Avionics still over capacity — {vesselMass:N1} t vs {maxCapacity:N1} t rated.");
                _nextReminder = Time.time + ReminderInterval;
            }

            _wasDegraded = degraded;
            _lastCapacity = maxCapacity;
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
            if (_masterMechJeb == null) return;
            _mjDeactivate.SetValue(_masterMechJeb, _level != AxeControlLockerUtils.LockLevel.Unlocked, null);
            UpdateMechJebAttitudeClients();
        }

        // Whether ANY unit aboard supplies an inertial attitude reference. This is the vessel MAX -- one
        // Deep-Space Bus anywhere in the stack covers the whole stack, matching how stock SAS already
        // resolves through part.PartValues.AutopilotSkill. Crew are exempt outright.
        //
        // Stock SAS gets both of those free from KSP's own MAX; MechJeb resolves per VESSEL through the
        // master core, so both have to be applied by hand here.
        //
        // Fails OPEN (returns true) on a null/empty vessel: mid-scene-change reads see a live-but-empty
        // Parts list, and answering "no reference" there would disable MechJeb on a craft that has one.
        bool VesselHasAttitudeReference()
        {
            Vessel v = _vessel;
            if (v == null || v.Parts == null || v.Parts.Count == 0) return true;
            if (v.GetCrewCount() > 0) return true;
            for (int i = 0; i < v.Parts.Count; i++)
            {
                PartModuleList mods = v.Parts[i].Modules;
                for (int j = 0; j < mods.Count; j++)
                {
                    if (mods[j] is ModuleAxeAvionics a && a.ProvidesAttitudeReference) return true;
                    if (mods[j] is ModuleAxeFixedAvionics f && f.ProvidesAttitudeReference) return true;
                }
            }
            return false;
        }

        // Enable/disable only the two frame-dependent clients. Everything else MechJeb offers -- ascent
        // guidance, docking, rendezvous, landing, throttle, warp helper, every readout window -- is
        // untouched, because none of it needs to know absolute attitude.
        void UpdateMechJebAttitudeClients()
        {
            if (_mjGetModule == null || _mjModuleEnabled == null) return;
            bool allowed = VesselHasAttitudeReference();
            if (allowed != _mjClientsAllowed)
            {
                _mjClientsAllowed = allowed;
                // Window visibility only -- a clear signal that the capability is gone, but never the
                // enforcement. See the note in EnforceAttitudeClients.
                for (int i = 0; i < MjAttitudeClients.Length; i++)
                {
                    object mod = _mjGetModule.Invoke(_masterMechJeb, new object[] { MjAttitudeClients[i] });
                    if (mod != null) _mjModuleEnabled.SetValue(mod, allowed, null);
                }
                if (!allowed)
                    Announce("No attitude reference — vector holds and node execution unavailable. Deep-Space Bus required.");
            }
        }

        /// <summary>
        /// THE actual enforcement, run every frame rather than on transitions: evict SmartASS and the node
        /// executor from the attitude controller's user pool and release the hold.
        ///
        /// Every frame because a player can command prograde at any moment, and a 1 Hz check would let the
        /// hold stand for up to a second. Cheap: one reflected read plus a type-name test per registered
        /// user, and the pool is normally empty or has one entry.
        ///
        /// The ASCENT autopilot is a user of the same pool and is deliberately left alone — it needs no
        /// star tracker, and killing the controller outright (the first attempt) took ascent guidance with
        /// it. Only the two frame-dependent clients get evicted.
        /// </summary>
        void EnforceAttitudeClients()
        {
            if (_mjClientsAllowed || _masterMechJeb == null) return;
            if (_mjGetModule == null || _mjUsersMember == null || _mjUsersRemove == null) return;

            object att = _mjGetModule.Invoke(_masterMechJeb, new object[] { "MechJebModuleAttitudeController" });
            if (att == null) return;

            object pool = _mjUsersMember is FieldInfo f ? f.GetValue(att)
                        : ((PropertyInfo)_mjUsersMember).GetValue(att, null);
            if (!(pool is System.Collections.IEnumerable users)) return;

            List<object> evict = null;
            foreach (object u in users)
            {
                if (u == null) continue;
                string n = u.GetType().Name;
                for (int i = 0; i < MjAttitudeClients.Length; i++)
                    if (n == MjAttitudeClients[i]) { (evict ??= new List<object>()).Add(u); break; }
            }
            if (evict == null) return;

            // UserPool.Remove is ALREADY correctly scoped -- it drops just this user and only disables the
            // attitude controller if the pool is left empty:
            //     if (user != null && Contains(user)) base.Remove(user);
            //     if (base.Count == 0) _controlledModule.Enabled = false;
            // So other users survive, which is exactly what we want.
            //
            // DO NOT add attitudeDeactivate() back here. It is `Users.Clear(); attitudeChanged = true;` --
            // a BLANKET wipe that also evicts MechJebModuleAscentBaseAutopilot and shuts the controller
            // down. Calling it killed ascent guidance mid-launch whenever SmartASS happened to be in the
            // pool at the same time, which made it look like a random ascent failure rather than a bug.
            for (int i = 0; i < evict.Count; i++) _mjUsersRemove.Invoke(pool, new[] { evict[i] });

            // TELL THE PLAYER WHY. Without this the craft simply drifts off the commanded vector and the
            // mod looks broken -- the one thing this whole avionics redesign set out to avoid (RP-1's
            // "silent hard-lock cliff", docs/AVIONICS_SPEC.md). Stock SAS needs no equivalent callout
            // because at level 0 KSP just doesn't draw the vector-hold buttons; MechJeb's stay clickable.
            //
            // Fires on the ATTEMPT, not on the transition, because that is the moment the player is
            // actually confused. Throttled: a still-selected SmartASS mode re-asserts every frame, so an
            // unthrottled message would be a solid wall of text.
            if (Time.time < _nextAttitudeNag) return;
            _nextAttitudeNag = Time.time + AttitudeNagInterval;
            bool node = false;
            for (int i = 0; i < evict.Count; i++)
                if (evict[i].GetType().Name == "MechJebModuleNodeExecutor") { node = true; break; }
            Announce(node
                ? "No attitude reference — this bus cannot execute a maneuver node. Fit a Deep-Space Bus, or burn it by hand."
                : "No attitude reference — this bus cannot hold a vector. Fit a Deep-Space Bus, or fly it by hand.");
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
