using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RP-AXE unified avionics core, V2. A VAB-chosen MODEL (guided/unguided) selects between two RP-1
    /// hardware curves:
    ///   * NEAR-EARTH (guided) — RP-1's Near-Earth mass polynomial, now run in the INVERSE direction: the
    ///     player sizes the box (a 3-way battery/hardware/empty-space split of the procedural volume), the
    ///     hardware segment's volume x density gives the hardware MASS, and that mass is run back through
    ///     the inverse of RP-1's polynomial to yield a CAPACITY ("how much vessel mass this core can steer").
    ///     A live ratio of actual vessel mass to the vessel's effective capacity (MAX across active cores,
    ///     RP-1's own anti-cheese rule) drives a smooth EC-draw PENALTY when over capacity — no hard lock.
    ///   * SCIENCE-CORE (unguided) — RP-1's Science-Core flat per-tier mass (unchanged): no steering
    ///     (axial-thrust spin-stabilization from improvedAvionics up), a fraction of the mass + power, and
    ///     no capacity concept (RP-1: Science-Core always contributes 0 to controllable mass).
    /// A second, Guided-only axis picks UNSHIELDED vs SHIELDED (RP-1's Deep-Space): its own full per-tier
    /// mass/cost ladder (not a multiplier), unlocked ~10 tiers late of Guided's own ladder, plus a deeper/
    /// earlier-available hibernation depth. Both mass AND cost are computed in the editor and FROZEN at
    /// launch (persisted); the model/shielding/split all freeze with them.
    ///
    /// The EC DRAW runs LIVE off the vehicle's DRY mass (steady as fuel burns, steps down as stages drop),
    /// gets cheaper per researched tier, and auto-drops to the hibernate-equivalent rate while on rails
    /// (timewarp), independent of the manual Hibernate toggle. Control is gated by guidance/axial being
    /// active (see <see cref="AxeAvionicsController"/>/<see cref="AxeControlLockerUtils"/>, both untouched
    /// by this redesign — they read only <see cref="GuidanceActive"/>/<see cref="AxialActive"/>, never the
    /// capacity penalty) and by HIBERNATE (Guided only; Unshielded needs a late tier to unlock a shallow
    /// depth, Shielded gets a deep depth from its own tier 0). Running the battery flat is NOT tracked by
    /// this module at all — the computed draw is fed live into stock ModuleCommand's own EC input resource,
    /// so an empty battery loses control the same way any vanilla probe does (matches RP-1; no custom
    /// brownout/hysteresis check).
    ///
    /// Science storage (ModuleScienceContainer) is tier-gated like RP-1 (on from basicAvionics, both
    /// models) — the seed part carries the module statically; this checks it off at flight start if the
    /// as-built tier doesn't have it yet (matches RP-1's own Start()-only gating).
    ///
    /// kOS integration (disk space / EC-per-instruction / cost / mass, all per tier) is reflected onto a
    /// kOSProcessor module if one is present on the part — same duck-typed pattern as the RealFuels/
    /// ProceduralPart bridge below. kOS isn't currently an AXE dependency, so today this is a no-op.
    ///
    /// A "Set to Debris: Never/On Stage" toggle (ported from RP-1's ModuleAvionics) lets a spent stage that
    /// happened to carry avionics not clutter the tracking station as a permanent "Ship" after separating.
    ///
    /// Kerbalism's radiation-reliability wiring described in docs/AVIONICS_SPEC.md is deliberately NOT part
    /// of this pass (Kerbalism's Reliability feature is off instance-wide; that is a separate, later,
    /// game-wide balance task).
    ///
    /// The per-tier ladders (mass/power/cost, Near-Earth + Science-Core + Shielded, plus kOS + science-
    /// container gating + hibernate-depth gating) live in config as TIER nodes (single source of truth,
    /// mirrored by tools/avionics_compare.py); a hardcoded copy of the required fields is kept as a
    /// fallback.
    /// </summary>
    public class ModuleAxeAvionics : PartModule, IPartMassModifier, IPartCostModifier
    {
        internal const string PAWGroup = "AxeAvionics";
        const string GroupDisplay = "Avionics Core";
        const string EcName = "ElectricCharge";

        // ---- tech that unlocks attitude guidance ----
        [KSPField] public string guidanceTech = "gnc_postWarAvionics";

        // ---- EC draw curve (Unshielded / Near-Earth): watts = (dryMass^exp + const) * powerFactor(tier) ----
        [KSPField] public float powerExponent = 0.57853f;
        [KSPField] public float powerConstant = 1.035f;
        [KSPField] public float idleFactor = 0.1f;          // draw multiplier while guidance is inactive (dumb)
        [KSPField] public float hibernationFactor = 0.05f;  // Shielded hibernate depth (tier-invariant, RP-1 Deep-Space)

        // ---- hardware MASS curve exponent/constant (Unshielded / Near-Earth) ----
        [KSPField] public float massExponent = 0.46172f;
        [KSPField] public float massConstant = 0.96f;

        // ---- hardware COST curve exponent/constant (Unshielded / Near-Earth) ----
        [KSPField] public float costExponent = 0.46172f;
        [KSPField] public float costConstant = 3.034f;

        // ---- Shielded axis: own constants (ground-truthed against RP-1's real Deep-Space AVIONICSCONFIG) ----
        [KSPField] public float shMassConstant = 1.043f;
        [KSPField] public float shCostConstant = 9.1f;
        [KSPField] public float shPowerConstant = 1.096f;
        // Extra surface-area-scaled shielding mass RP-1 adds on top of the curve mass for Deep-Space
        // (ModuleProceduralAvionics.GetShieldingMass: avionicsMass^(2/3) * shieldingMassFactor), tier-invariant.
        // No cost equivalent -- RP-1's cost polynomial has no shielding add-on, mass only.
        [KSPField] public float shieldingMassFactor = 0.1f;

        // ---- volume: hardware occupies part of the box; density converts volume<->mass ----
        [KSPField] public float avionicsDensity = 0.5f;   // t/m^3

        // ---- persistent player state ----
        // The as-built avionics MODEL, chosen in the VAB and frozen at launch:
        //   true  = Near-Earth  (guided — full 3-axis control, capacity-derived hardware)
        //   false = Science-Core (unguided — light flat-mass sequencer, axial thrust only at high tiers)
        [KSPField(isPersistant = true)] public bool guidanceEnabled = true;
        // Guided-only second axis, VAB-frozen: Shielded uses its own full ladder (mass/cost/hibernate-depth),
        // not a multiplier on Unshielded. Blocked until at least one Shielded tier is researched.
        [KSPField(isPersistant = true)] public bool shieldedEnabled = false;
        // Flight-only deep sleep: cuts EC draw to the current hibernate depth and suspends control until woken.
        [KSPField(isPersistant = true)] public bool hibernating = false;
        // Per-part "Set to Debris" preference (RP-1 ModuleAvionics): a spent stage with this off (any one
        // command-capable part vetoes) never gets force-renamed to Debris on staging.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Set to Debris",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "Never", enabledText = "On Stage", affectSymCounterparts = UI_Scene.Editor)]
        public bool setToDebrisOnStage = false;

        // ---- 3-segment volume split (battery / hardware / empty) ----
        // The LIVE, current-box-clamped volumes (m^3) -- what everything else (mass, cost, capacity,
        // RealFuels) actually reads. On every resize these are re-derived from desiredBattVolume/
        // desiredHwVolume below, NOT from their own previous values -- otherwise a shrink-then-grow cycle
        // would permanently lose whatever got clamped away by the shrink (growing back up would only ever
        // enlarge "empty," never restore the original split).
        [KSPField(isPersistant = true)] public float battVolume = 0f;
        [KSPField(isPersistant = true)] public float hwVolume = 0f;
        // The REMEMBERED explicit intent (m^3) -- the last values the player actually dragged to, never
        // clamped themselves. A resize always tries to re-fit these first: battery gets priority (fit it
        // first), then hardware gets whatever room is left, then empty absorbs anything remaining --
        // matching the reverse order for shrinking (empty gives way first, then hardware, battery last).
        [KSPField(isPersistant = true)] public float desiredBattVolume = 0f;
        [KSPField(isPersistant = true)] public float desiredHwVolume = 0f;
        // The box's total volume at the moment the split above was last explicitly committed. Any
        // volume the box GAINS since then (a resize bigger, not a drag) flows to the player-adjustable
        // segment (hardware for Guided, battery for Unguided) by default -- otherwise growing the box
        // without re-dragging would silently balloon "empty" instead of giving usable capacity/charge,
        // and the player would have to re-drag every single time after a resize for it to do anything.
        // A deliberately-left empty gap (dragging a handle short of the box's far edge) is unaffected --
        // only volume PAST this remembered total counts as new growth.
        [KSPField(isPersistant = true)] public float desiredTotalVolume = 0f;
        // False until the player applies a manual split via the allocation window; while false, every
        // resize uses the default 25% battery / 75% hardware / 0% empty proportion.
        [KSPField(isPersistant = true)] public bool hasExplicitSplit = false;

        // ---- readouts (VAB-visible) ----
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Avionics Power",
                  guiFormat = "N1", guiUnits = " W", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float currentWatts = 0f;

        // Frozen hardware mass: recomputed in the editor from hwVolume, persisted with the craft, held
        // fixed in flight. IPartMassModifier returns this; the battery mass is RealFuels' (below).
        // Renamed in the PAW from "Avionics Mass" to "Hardware Mass" because it never was the part's
        // mass -- it is only the hardware SEGMENT, and reading it as the whole box understates a
        // battery-heavy core by more than the hardware itself weighs.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Hardware Mass",
                  guiFormat = "F3", guiUnits = " t", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float avionicsMass = 0f;

        // The battery segment's mass, read live off RealFuels' own ModuleFuelTanks.mass: the tankage base
        // mass for the volume this module pushed into it plus the cells themselves (Battery-I: 0.00007 t/L
        // + 0.0045 t/L). Pure READOUT -- RF reports this mass to KSP itself (as `mass - prefabMass`, i.e.
        // non-additive: it REPLACES the part's prefab mass), so it must never be folded into this module's
        // IPartMassModifier or it would be counted twice.
        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Battery Mass",
                  guiFormat = "F3", guiUnits = " t", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float batteryMass = 0f;

        // What the whole box actually weighs, by KSP's own accounting -- see UpdateMassReadouts(). Hardware
        // + battery don't quite sum to this: a little structural/module mass (Kerbalism's HardDrive, any
        // hollow-volume mass from ProceduralPart) rides along, which is why this is measured, not added up.
        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Total Mass",
                  guiFormat = "F3", guiUnits = " t", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float totalPartMass = 0f;

        // Frozen hardware cost (funds): same hwVolume basis + freeze-at-launch as avionicsMass.
        [KSPField(isPersistant = true, guiActiveEditor = true, guiName = "Avionics Cost",
                  guiFormat = "F0", guiUnits = " f", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float avionicsCost = 0f;

        // ---- A1/A2: Engage / Disengage Guidance (docs/AVIONICS_PLAN.md) --------------------------
        // Capacity-only. Disengaged, this unit contributes nothing to the vessel's steerable-mass budget
        // and provides no guidance -- so the vessel falls to the passive Axial/Locked ladder instead of
        // having its controls corrupted by a unit that cannot fly it anyway.
        //
        // Deliberately NOT the same thing as Shutdown Avionics (`hibernating`), which is RP-1's power
        // feature and is gated at tier index 9 -- useless for the early career where a capsule riding a
        // dumb stage is the common configuration. No tier gate here, and no effect on EC draw.
        [KSPField(isPersistant = true)]
        public bool guidanceEngaged = true;

        // Auto: engage once the vessel is light enough for THIS unit, disengage on docking if it is not.
        // Build-time state is the player's decision and carries its consequences; only run-time surprises
        // are protected.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "Guidance auto",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "manual", enabledText = "auto", scene = UI_Scene.All)]
        public bool autoGuidance = true;

        // Guided only: how much vessel mass this core can steer, derived from hwVolume via the inverse of
        // the mass polynomial. 0 for Unguided (matches RP-1: Science-Core always contributes 0).
        // Data field, not a readout -- capacityDisplay below is what the PAW shows, because the two states
        // that produce a zero here mean different things and "0.00 t" tells the player neither.
        [KSPField(isPersistant = true)]
        public float capacityTons = 0f;

        // Capacity as the PAW reports it. Zero has two distinct causes worth naming: Unguided has no
        // capacity concept at all (RP-1's Science-Core contributes 0 by design, it is not undersized), and a
        // Guided core whose hardware sits under the tier's floor -- the inverse polynomial only goes positive
        // above massConstant * massFactor kg, i.e. 169 L of hardware at `start` falling to 22 L by the last
        // tier. That second case is common on the Probe Bus, whose stock core models range from a 28 L OGO
        // to a 3090 L Hera, so the fix ("make it bigger, or advance the ladder") has to be legible.
        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Capacity",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string capacityDisplay = "";

        // How much of the current draw is "penalty" from being over capacity (MAX across active cores).
        // PROTOTYPE: stood down while the authority model is being flown -- PenaltyMultiplier() returns 1,
        // so this reads 0. Hidden rather than deleted; the whole penalty path is still here to revert to.
        [KSPField(guiActive = false, guiActiveEditor = false, guiName = "Overload Penalty",
                  guiFormat = "F0", guiUnits = "%", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public float penaltyPercent = 0f;

        // PROTOTYPE (docs/AVIONICS_AUTHORITY.md): what the overload penalty is being replaced with. Over
        // capacity the craft keeps control but authority decays as q = e^(-k(r-1)) until RatioCut, past
        // which it is genuinely unguided. Shown as a percentage so an overloaded design is visible in the
        // VAB rather than discovered in flight -- "silent" was the real complaint about RP-1's cliff.
        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Control Noise",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string authorityDisplay = "";

        // PROTOTYPE TEST RIG -- remove with the rest of the prototype. Every tunable is live in BOTH scenes,
        // so the curve can be felt and changed mid-flight without a rebuild. None of these numbers has a
        // physical anchor (KSP models no bending modes), so feel is the only way to find them.
        // PROTOTYPE DIAGNOSTIC. Distinguishes the two failure modes that look identical from the cockpit:
        // "the hook is not running" and "the hook is running but the noise is too small to notice".
        // Ticks must advance every second; the p/y/r figures are what was actually added to the stick.
        [KSPField(guiActive = true, guiActiveEditor = false, guiName = "DEBUG: injected",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string noiseDebug = "";

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: pin noise",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "off", enabledText = "on", scene = UI_Scene.All)]
        public bool noiseOverride = false;

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: noise amount",
                  guiFormat = "F2", groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_FloatRange(minValue = 0f, maxValue = 1f, stepIncrement = 0.05f, scene = UI_Scene.All)]
        public float noiseOverrideValue = 0.3f;

        // THE critical knob. Vessel rotational inertia low-passes control noise, so frequency decides whether
        // this is felt at all: too fast and a heavy rocket averages it away (the same trap that killed v1 in a
        // different guise), too slow and the autopilot simply trims it out as a steady bias.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: noise Hz (C)",
                  guiFormat = "F1", groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_FloatRange(minValue = 0.1f, maxValue = 20f, stepIncrement = 0.1f, scene = UI_Scene.All)]
        public float noiseHz = 2f;

        // With auto-scale on, the knob above is C in Hz = C / mass^(1/3) rather than a frequency, so each
        // vehicle is perturbed at its own attitude-response frequency. Off = flat Hz, for A/B comparison.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: Hz scaling",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "flat", enabledText = "by vessel mass", scene = UI_Scene.All)]
        public bool noiseHzAuto = true;

        // White vs correlated: a direct test of the inertia-filtering theory. If white is invisible and
        // correlated is felt, that confirms the vessel is acting as a low-pass filter.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: white noise",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "correlated", enabledText = "white", scene = UI_Scene.All)]
        public bool noiseWhite = false;

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: ramp k",
                  guiFormat = "F1", groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_FloatRange(minValue = 0.5f, maxValue = 25f, stepIncrement = 0.5f, scene = UI_Scene.All)]
        public float noiseK = 11.5f;   // anchored: sigma(1.2)=0.9

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: noise ceiling",
                  guiFormat = "F2", groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_FloatRange(minValue = 0.1f, maxValue = 1f, stepIncrement = 0.05f, scene = UI_Scene.All)]
        public float noiseMax = 1f;   // 1 = ceiling off; the curve saturates on its own

        // Roll is by far the most perceptible axis, so it is separable -- if roll noise alone dominates the
        // feel, that is worth knowing before tuning anything else.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: noise roll",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "pitch/yaw only", enabledText = "all axes", scene = UI_Scene.All)]
        public bool noiseRoll = true;

        // Off by default: a hard flip to unguided past some ratio is the same arbitrary cliff this design
        // exists to remove, only relocated, and it is redundant because the noise curve already asymptotes
        // to unflyable. Kept as a toggle purely so the two can be compared.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: hard cutoff",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "noise only", enabledText = "unguided past cut", scene = UI_Scene.All)]
        public bool hardCutoff = false;

        // Three genuinely different mechanics, not three tunings of one.
        //   0 uncommanded -- noise added regardless of input; the craft wanders on its own.
        //   1 on input    -- noise scales the command; a null stick stays null, small commands survive.
        //   2 overgain    -- no noise at all: the command is AMPLIFIED, so the loop overcontrols and
        //                    oscillates by itself. Models the mechanism rather than the symptom, and makes
        //                    noise Hz / white / correlated irrelevant.
        //   3 coupling    -- commanding one axis bleeds into the others, coefficients fixed per vessel. The
        //                    loop fights itself: correcting induced yaw induces pitch. Learnable, so it
        //                    reads as a characteristic of the craft rather than a malfunction.
        //   4 delay       -- the command is held for N ticks. Eats phase margin, which a fixed-gain
        //                    controller can do nothing about. Expected to be the sharpest and possibly a
        //                    cliff; built to find out.
        //
        // 0 and 1 are DISTURBANCES, which a feedback loop exists to reject -- hence their weakness. 2, 3 and
        // 4 are the three classical ways to destabilise a loop (gain margin, decoupling, phase margin) and
        // are not rejectable in the same way.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: mode",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_ChooseOption(options = new[] { "none", "lock (RP-1)", "uncommanded", "on input", "overgain", "coupling", "delay" }, scene = UI_Scene.All)]
        public int noiseMode = 3;

        // Physics ticks of lag at sigma = 1. KSP runs 50 Hz, so 10 ticks = 200 ms -- already past what
        // destabilises most controllers.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: delay ticks",
                  guiFormat = "F0", groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_FloatRange(minValue = 1f, maxValue = 40f, stepIncrement = 1f, scene = UI_Scene.All)]
        public float delayTicksMax = 10f;

        // Slope in G = 1 + slope*(r-1). Anchored like k: typical loop gain margin is 2-4x, so G = 3 should
        // push most controllers unstable, and G(1.2) = 3 gives slope 10.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: overgain slope",
                  guiFormat = "F1", groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_FloatRange(minValue = 1f, maxValue = 40f, stepIncrement = 1f, scene = UI_Scene.All)]
        public float overgainSlope = 10f;   // on-input: preserves small commands

        // RCS responds instantly and has no inertia to filter anything, so the sigma that gently wallows a
        // launcher makes fine attitude work impossible. Scaled rather than merely switched off.
        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: RCS noise scale",
                  guiFormat = "F2", groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_FloatRange(minValue = 0f, maxValue = 1f, stepIncrement = 0.05f, scene = UI_Scene.All)]
        public float noiseRcsScale = 1f;   // on-input mode removed the need to cut RCS

        [KSPField(isPersistant = true, guiActive = true, guiActiveEditor = true, guiName = "DEBUG: noise on RCS",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay),
         UI_Toggle(disabledText = "gimbal only", enabledText = "gimbal + RCS", scene = UI_Scene.All)]
        public bool noiseOnRcs = true;

        [KSPField(guiActiveEditor = true, guiName = "Split",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string allocationSummary = "";

        [KSPField(guiActive = true, guiActiveEditor = true, guiName = "Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public string guidanceStatus = "";

        // ---- runtime ----
        float _massFactor = 87.99f;   // current tier's Unshielded mass factor
        float _powerFactor = 56.415f; // current tier's power factor (shared by Unshielded/Shielded)
        float _costFactor = 48.12f;   // current tier's Unshielded cost factor
        float _scMassFactor = 33f;    // current tier's Science-Core flat mass factor (kg)
        float _scPowerFactor = 50f;   // current tier's Science-Core flat power (W)
        float _scCostFactor = 6f;     // current tier's Science-Core flat cost factor (funds)
        float _scDensity = 2.4f;      // current tier's Science-Core hardware density (t/m^3)
        bool _scAllowAxial = false;   // current tier: Science-Core permits axial-thrust control
        bool _hasScienceContainer = false; // current tier: RP-1 gates science storage on from basicAvionics
        float _unshHibernateFactor = -1f;  // current tier's Unshielded hibernate depth; <=0 = can't hibernate
        // current tier's kOS ladder (applied to a kOSProcessor module if present; no-op otherwise)
        float _kosDiskSpace = 500f;
        float _kosSpaceCostFactor = 0.1f;
        float _kosSpaceMassFactor = 0.0001f;
        float _kosEcPerInstruction = 0.000001f;
        // Shielded axis: best-researched Shielded tier's factors, and which ladder index it is (-1 = none
        // researched yet — unlike the Unshielded ladder, Shielded has no unconditional tier-0 floor).
        float _shMassFactor = 0f;
        float _shCostFactor = 0f;
        int _bestShieldedIdx = -1;
        KeyValuePair<string, double> _ecConsumption = new KeyValuePair<string, double>(EcName, 0);
        ModuleResource _commandEC;
        float _nextFlightRecalc;
        bool _onRails;                  // transient, not persisted — forces hibernate-depth draw while on rails
        static bool? _kerbalismPresent;

        // RealFuels bridge (reflected — AXE.dll doesn't reference RealFuels, same as the MechJeb/Kerbalism
        // reflection elsewhere). Used to read the box's total volume and push the battery segment into RF.
        PartModule _rfPM;
        MethodInfo _rfCalcMass;
        FieldInfo _rfMassField;          // ModuleFuelTanks.mass (t) — the battery segment's own mass
        PartModule _procPM;
        PropertyInfo _procVolumeProp;    // ProceduralPart.Volume (m^3)
        FieldInfo _procMinVolumeField;   // ProceduralPart.volumeMin — pinned to enforce a minimum box size
        PropertyInfo _procCurShapeProp;  // ProceduralPart.CurrentShape — for refreshing the slider bounds
        MethodInfo _procSeekVolumeMethod;// ProceduralPart.SeekVolume(target[, dir]) — nudge box to a volume
        bool _enforcingFloor;            // re-entrancy guard: SeekVolume can re-fire onEditorShipModified
        // The OTHER procedural shape driver: ROTanks' ModuleROTank, which drives the Probe Bus (ROT-ProbeCore)
        // and reDIRECT's avionics. Volume-read ONLY -- ROLib exposes no volumeMin and no SeekVolume, so the
        // box floor and the auto-grow-to-fit nudge simply don't exist on those parts (RP-1 is in the same
        // position: its GetSeekVolumeMethod() returns null unless ProceduralParts is the driver, and its
        // Configure window prints "ROTanks does not currently support automatic resizing"). The overload
        // penalty is the guardrail there instead of a geometric floor -- shrink the box and capacity falls
        // visibly rather than the box refusing to shrink.
        PartModule _rotPM;
        PropertyInfo _rotVolumeProp;     // ModuleROTank.Volume (m^3, same units as ProceduralPart.Volume)
        bool _sendingVolume;             // re-entrancy guard: we both send and listen for OnPartVolumeChanged
        float _cachedVolume = -1f;       // m^3 — the procedural part's total volume

        // kOS bridge (reflected — AXE.dll doesn't reference kOS, same duck-typed pattern as RealFuels above).
        PartModule _kosPM;
        FieldInfo _kosDiskSpaceField;
        FieldInfo _kosBaseDiskSpaceField;
        FieldInfo _kosDiskSpaceCostFactorField;
        FieldInfo _kosDiskSpaceMassFactorField;
        FieldInfo _kosEcPerInstructionField;

        // ---- config-driven tier ladder, with a hardcoded fallback ----
        // Tier 0 ("start") is the unconditional floor for the Guided/Unguided axis — no tech required,
        // ApplyTier always starts there. The Shielded axis has NO floor: its first rung is at basicAvionics.
        static string[] _ladTech =
        {
            "start", "gnc_postWarAvionics", "gnc_avionicsPrototypes", "gnc_earlyAvionics", "gnc_basicAvionics",
            "gnc_interplanetaryAvionics", "comp_digitalGuidanceComputer", "comp_realTimeFlightComputer", "comp_networkedAvionics",
            "comp_multiplyRedundantFlightComputer", "comp_distributedAvionicsBus", "comp_softwareDefinedFlightControl", "comp_interoperableAvionicsStandard", "comp_commercialOffTheShelfAvionics"
        };
        static float[] _ladMass =
        { 87.99f, 87.99f, 69.712f, 59.13f, 50.153f, 42.54f, 36.082f, 30.605f, 25.959f, 22.018f, 18.675f, 15.84f, 13.436f, 11.396f };
        static float[] _ladPower =
        { 56.415f, 56.415f, 47.851f, 40.587f, 34.426f, 29.2f, 24.767f, 21.007f, 17.818f, 15.113f, 12.819f, 10.873f, 9.222f, 7.822f };
        static float[] _ladCost =
        { 48.12f, 48.12f, 51.56f, 54.13f, 56.84f, 59.68f, 62.67f, 65.8f, 58.85f, 47.08f, 37.67f, 30.13f, 24.11f, 19.29f };
        static float[] _ladScMass =
        { 48f, 33f, 17f, 4f, 1.5f, 1f, 0.81f, 0.73f, 0.66f, 0.59f, 0.53f, 0.48f, 0.43f, 0.39f };
        static float[] _ladScPower =
        { 100f, 50f, 25f, 0.15f, 0.1f, 0.09f, 0.081f, 0.073f, 0.066f, 0.059f, 0.053f, 0.048f, 0.043f, 0.039f };
        static float[] _ladScCost =
        { 3f, 6f, 8f, 10f, 12f, 12f, 12f, 12f, 10f, 9f, 8.1f, 7.3f, 6.6f, 5.9f };
        static float[] _ladScDensity =
        { 3.35f, 2.4f, 1.4f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f };
        static bool[] _ladScAxial =
        { false, false, false, false, false, false, true, true, true, true, true, true, true, true };
        static bool[] _ladHasSci =
        { false, false, false, false, true, true, true, true, true, true, true, true, true, true };
        static float[] _ladKosDisk =
        { 500f, 500f, 500f, 500f, 500f, 5120f, 10240f, 20480f, 51200f, 102400f, 204800f, 307200f, 409600f, 512000f };
        static float[] _ladKosCostFactor =
        { 0.1f, 0.1f, 0.1f, 0.1f, 0.1f, 0.01f, 0.005f, 0.0025f, 0.001f, 0.0005f, 0.00025f, 0.0001f, 0.0001f, 0.0001f };
        static float[] _ladKosMassFactor =
        { 0.0001f, 0.0001f, 0.0001f, 0.0001f, 0.0001f, 0.0000005f, 0.0000002f, 0.0000001f, 0.00000005f, 0.000000005f, 0.000000002f, 0.000000001f, 0.0000000005f, 0.0000000002f };
        static float[] _ladKosEcPerInstr =
        { 0.000001f, 0.000001f, 0.000004f, 0.000002f, 0.000001f, 0.0000004f, 0.0000002f, 0.0000001f, 0.00000008f, 0.00000004f, 0.00000001f, 0.00000001f, 0.00000001f, 0.00000001f };
        // Shielded axis (ground-truthed against RP-1's real Deep-Space AVIONICSCONFIG for indices 4-13,
        // "basicAvionics" on -- RP-1 has no Deep-Space data before that). Indices 0-3 ("start" through
        // "earlyAvionics") have no RP-1 equivalent to port; reused from the Unshielded ladder verbatim
        // (matches _ladMass/_ladCost at the same indices) so the ladder has no gaps for tree/tooling
        // symmetry. The Shielded TOGGLE itself stays gated behind ShieldedUnlocked (gnc_basicAvionics),
        // same as before this fill-in -- see ShieldedUnlocked below.
        static float[] _ladShMass =
        { 87.99f, 87.99f, 69.712f, 59.13f, 55.168f, 46.794f, 39.69f, 33.665f, 28.554f, 24.22f, 20.543f, 17.424f, 14.779f, 12.536f };
        static float[] _ladShCost =
        { 48.12f, 48.12f, 51.56f, 54.13f, 85.26f, 89.52f, 94.0f, 98.7f, 88.28f, 70.62f, 56.5f, 45.2f, 36.16f, 28.93f };
        // The tree node that gates each Shielded rung (2026-07-14): the Shielded axis is its OWN research
        // investment on the shd_* lane, NOT free with the guided gnc_/comp_ tier at the same index. Indices
        // 0-3 have no shd_ node ("" = no real Shielded rung here; their _ladShMass is reused-for-symmetry only
        // and is never selectable without an shTech). Parsed from TIER{shTech=...} in AxeAvionicsCore.cfg;
        // this is the in-code fallback. Must stay index-aligned with _ladShMass/_ladShCost.
        static string[] _ladShTech =
        {
            "", "", "", "", "shd_basicAvionics",
            "shd_interplanetaryAvionics", "shd_digitalGuidanceComputer", "shd_realTimeFlightComputer", "shd_networkedAvionics",
            "shd_multiplyRedundantFlightComputer", "shd_distributedAvionicsBus", "shd_softwareDefinedFlightControl", "shd_interoperableAvionicsStandard", "shd_commercialOffTheShelfAvionics"
        };
        // Unshielded hibernate depth: <=0 sentinel = can't hibernate. First 9 tiers can't; the last 5
        // (advancedAvionics-equivalent on) reach a shallow 0.1 — ground-truthed against RP-1's real
        // disabledPowerFactor boundary.
        static float[] _ladUnshHibernate =
        { -1f, -1f, -1f, -1f, -1f, -1f, -1f, -1f, -1f, 0.1f, 0.1f, 0.1f, 0.1f, 0.1f };

        public bool GuidanceUnlocked => Researched(guidanceTech);
        public bool GuidanceActive => GuidanceUnlocked && guidanceEnabled && !hibernating && guidanceEngaged;
        public bool ScienceCoreMode => !guidanceEnabled;
        public bool AxialActive => ScienceCoreMode && _scAllowAxial && !hibernating;
        float EffectiveDensity() => guidanceEnabled ? avionicsDensity : (_scDensity > 0f ? _scDensity : avionicsDensity);
        public string GuidanceTech => guidanceTech;

        // Guided only: can this core hibernate at all right now, and how deep. Shielded needs a researched
        // Shielded tier (any of them — depth is tier-invariant); Unshielded needs the late tier that
        // unlocks the shallow depth.
        public bool CanHibernate => guidanceEnabled && (shieldedEnabled ? _bestShieldedIdx >= 0 : _unshHibernateFactor > 0f);
        public float CurrentHibernateFactor => (shieldedEnabled && _bestShieldedIdx >= 0) ? hibernationFactor : _unshHibernateFactor;

        // This is RP-1's "Shutdown Avionics" (ModuleAvionics.systemEnabled), NOT stock probe hibernation --
        // RP-1 disables that outright on every ModuleCommand (Avionics.cfg:1) and AXE's config does the same.
        // A shut-down core in RP-1 returns 0 from CurrentMassLimit, i.e. it leaves the vessel's steerable-mass
        // MAX entirely (EffectiveCapacityTons reproduces that below), and draws GetEnabledkW() *
        // disabledPowerFactor. The availability gate is RP-1's GetToggleable() => disabledPowerFactor > 0,
        // which its configs author per family: Near-Earth only from advancedAvionics (index 9 here) at 0.1,
        // Deep-Space at EVERY tier from its first at 0.05, Science-Core never (nothing to shut down -- it is
        // already a flat sub-watt draw with no capacity). CanHibernate/CurrentHibernateFactor are that gate.
        //
        // _onRails is included because RP-1 drops a toggleable core to the disabled rate on rails regardless
        // of the manual switch (ModuleAvionics.UpdateRate: currentlyEnabled = systemEnabled && !(toggleable
        // && onRails)). It deliberately does NOT feed EffectiveCapacityTons, unlike `hibernating`: capacity
        // is a build-time property the player reads in the VAB, and having it blink to zero on entering
        // timewarp would be noise. Nothing steers while unloaded anyway, so the distinction is inert.
        bool Asleep => guidanceEnabled && CanHibernate && (hibernating || _onRails);

        static bool KerbalismPresent
        {
            get
            {
                if (_kerbalismPresent == null)
                {
                    _kerbalismPresent = false;
                    foreach (var a in AssemblyLoader.loadedAssemblies)
                        if (a.name == "Kerbalism") { _kerbalismPresent = true; break; }
                }
                return _kerbalismPresent.Value;
            }
        }

        static bool Researched(string tech)
        {
            if (string.IsNullOrEmpty(tech)) return true;
            if (HighLogic.CurrentGame == null || HighLogic.CurrentGame.Mode == Game.Modes.SANDBOX) return true;
            return ResearchAndDevelopment.GetTechnologyState(tech) == RDTech.State.Available;
        }

        // Parse the per-tier ladder from config TIER nodes (single source of truth). Craft-instance loads
        // carry no TIER children, so the prefab-parsed values (or the hardcoded fallback) stay in force.
        public override void OnLoad(ConfigNode node)
        {
            base.OnLoad(node);
            ConfigNode[] tiers = node?.GetNodes("TIER");
            if (tiers == null || tiers.Length == 0) return;

            int dropped = 0;   // tiers rejected below; a non-zero count with nothing kept means the
                               // config was unreadable, not absent -- see the log line at the end.
            var tech = new List<string>();
            var mass = new List<float>();
            var power = new List<float>();
            var cost = new List<float>();
            var scMass = new List<float>();
            var scPower = new List<float>();
            var scCost = new List<float>();
            var scDensity = new List<float>();
            var scAxial = new List<bool>();
            var hasSci = new List<bool>();
            var kosDisk = new List<float>();
            var kosCostFactor = new List<float>();
            var kosMassFactor = new List<float>();
            var kosEcPerInstr = new List<float>();
            var shMass = new List<float>();
            var shCost = new List<float>();
            var shTechs = new List<string>();
            var unshHib = new List<float>();
            foreach (ConfigNode t in tiers)
            {
                string tn = t.GetValue("tech");
                if (string.IsNullOrEmpty(tn)) { dropped++; continue; }
                float mf = 0f, pf = 0f, scm = 0f, scp = 0f, scd = 0f;
                bool sca = false;
                t.TryGetValue("massFactor", ref mf);
                t.TryGetValue("powerFactor", ref pf);
                t.TryGetValue("scMassFactor", ref scm);
                t.TryGetValue("scPowerFactor", ref scp);
                t.TryGetValue("scDensity", ref scd);
                t.TryGetValue("scAllowAxial", ref sca);
                if (mf <= 0f || pf <= 0f || scm <= 0f || scp <= 0f || scd <= 0f) { dropped++; continue; } // all-or-nothing per tier
                tech.Add(tn); mass.Add(mf); power.Add(pf);
                scMass.Add(scm); scPower.Add(scp); scDensity.Add(scd); scAxial.Add(sca);

                // Cost/kOS/science-container/Shielded/hibernate-gate are optional per tier (default to
                // 0/false/-1, not tier-dropping).
                float cf = 0f, scc = 0f, kd = 0f, kcf = 0f, kmf = 0f, kec = 0f, shm = 0f, shc = 0f, uh = -1f;
                bool hsc = false;
                t.TryGetValue("costFactor", ref cf);
                t.TryGetValue("scCostFactor", ref scc);
                t.TryGetValue("hasScienceContainer", ref hsc);
                t.TryGetValue("kosDiskSpace", ref kd);
                t.TryGetValue("kosSpaceCostFactor", ref kcf);
                t.TryGetValue("kosSpaceMassFactor", ref kmf);
                t.TryGetValue("kosECPerInstruction", ref kec);
                t.TryGetValue("shMassFactor", ref shm);
                t.TryGetValue("shCostFactor", ref shc);
                t.TryGetValue("unshHibernateFactor", ref uh);
                string sht = t.GetValue("shTech") ?? "";   // shd_* node gating this Shielded rung ("" = none)
                cost.Add(cf); scCost.Add(scc); hasSci.Add(hsc);
                kosDisk.Add(kd); kosCostFactor.Add(kcf); kosMassFactor.Add(kmf); kosEcPerInstr.Add(kec);
                shMass.Add(shm); shCost.Add(shc); shTechs.Add(sht); unshHib.Add(uh);
            }
            // A SILENT FALLBACK IS HOW THIS SYSTEM HID A BUG FOR ITS ENTIRE LIFE. The TIER blocks were
            // authored several `key = value` per line; KSP's ConfigNode keeps only the first assignment on
            // a line, so every factor below read as absent, every tier was dropped here, and the module
            // quietly used the in-code ladder -- which is identical, so the game behaved perfectly and
            // nothing ever surfaced it. Falling back is fine; falling back in silence is not.
            if (tech.Count == 0)
            {
                Debug.LogError($"[AXE][Avionics] {tiers.Length} TIER node(s) present but NONE parsed -- "
                    + "using the in-code fallback ladder. The config is being ignored. Most likely cause: "
                    + "more than one 'key = value' on a line (KSP keeps only the first). "
                    + "See design/Tree/AxeAvionicsCore.cfg and build_tree.py's config format gate.");
                return;
            }
            if (dropped > 0)
                Debug.LogWarning($"[AXE][Avionics] {dropped} of {tiers.Length} TIER node(s) were incomplete "
                    + "and dropped; the ladder is running on the remaining "
                    + $"{tech.Count}. Every tier needs massFactor/powerFactor/scMassFactor/scPowerFactor/scDensity.");
            _ladTech = tech.ToArray();
            _ladMass = mass.ToArray();
            _ladPower = power.ToArray();
            _ladCost = cost.ToArray();
            _ladScMass = scMass.ToArray();
            _ladScPower = scPower.ToArray();
            _ladScCost = scCost.ToArray();
            _ladScDensity = scDensity.ToArray();
            _ladScAxial = scAxial.ToArray();
            _ladHasSci = hasSci.ToArray();
            _ladKosDisk = kosDisk.ToArray();
            _ladKosCostFactor = kosCostFactor.ToArray();
            _ladKosMassFactor = kosMassFactor.ToArray();
            _ladKosEcPerInstr = kosEcPerInstr.ToArray();
            _ladShMass = shMass.ToArray();
            _ladShCost = shCost.ToArray();
            _ladShTech = shTechs.ToArray();
            _ladUnshHibernate = unshHib.ToArray();
        }

        // RP-1 parity (ModuleAvionics.OnSave: "Too many ways to exit a scene, so always write the Disabled
        // power draw"). BackgroundUpdate below reads currentWatts straight out of the module snapshot for an
        // UNLOADED vessel, so whatever is persisted here is the rate Kerbalism bills that vessel for the
        // entire time it sits unloaded. Persisting the live active-guidance figure -- which for an overloaded
        // core carries the penalty multiplier -- would charge that rate across the whole gap, draining a
        // parked craft that was merely over capacity while attached to a booster it has long since dropped.
        // KSP writes the persistent KSPFields before calling OnSave, so this overwrites rather than adds.
        public override void OnSave(ConfigNode node)
        {
            base.OnSave(node);
            node.SetValue(nameof(currentWatts), ComputeWatts(true), true);
        }

        public override void OnStartFinished(StartState state)
        {
            _commandEC = FindCommandEC();
            ResolveTankBridge();
            ApplyTier();
            ApplyShieldedTier();

            if (HighLogic.LoadedSceneIsEditor)
            {
                GameEvents.onEditorShipModified.Add(OnShipModified);
                // ProceduralPart's own shape/volume isn't necessarily settled the same frame this part
                // starts (its shape application can run across a frame boundary) -- reading volume
                // synchronously here can catch it before that settles, producing a near-zero cached
                // volume that then sticks (near-zero capacity -> tripped overload penalty) until the
                // next onEditorShipModified event, e.g. the player's first resize -- matches "broken
                // right after placing the part, fine after the first resize." One frame's delay mirrors
                // the same idiom AxeAllocationBarHook already uses for onPartActionUICreate/CreatePartList.
                StartCoroutine(EditorFirstFrameSetup());
            }
            else
            {
                _cachedVolume = ReadProceduralVolume();
                // Flight: hardware mass/cost/capacity are frozen (persisted). Legacy craft (mass 0) get one
                // fallback compute from whatever hwVolume was persisted (0 for pre-redesign saves).
                if (avionicsMass <= 0f) UpdateHardwareMass();
                GameEvents.onStageActivate.Add(OnStage);
                GameEvents.onPartCouple.Add(OnCouple);
                GameEvents.onVesselGoOnRails.Add(GoOnRails);
                GameEvents.onVesselGoOffRails.Add(GoOffRails);

                // Science storage is tier-gated (RP-1: on from basicAvionics). Checked once at flight start,
                // same as RP-1's own Start()-only gating.
                if (!_hasScienceContainer)
                {
                    ModuleScienceContainer sci = part.FindModuleImplementing<ModuleScienceContainer>();
                    if (sci != null) part.RemoveModule(sci);
                }
            }

            UpdateRate();
            SetGui();
        }

        // See the comment at its call site in OnStartFinished: gives ProceduralPart's own shape/volume
        // a frame to settle before this module's first read of it.
        IEnumerator EditorFirstFrameSetup()
        {
            yield return null;
            _cachedVolume = ReadProceduralVolume();
            EnforceBoxFloor();
            RecomputeSplit(_cachedVolume);
            UpdateHardwareMass();
            PushBatteryToTank();
            UpdateRate();
            SetGui();
        }

        void OnDestroy()
        {
            GameEvents.onEditorShipModified.Remove(OnShipModified);
            GameEvents.onStageActivate.Remove(OnStage);
            GameEvents.onPartCouple.Remove(OnCouple);
            GameEvents.onVesselGoOnRails.Remove(GoOnRails);
            GameEvents.onVesselGoOffRails.Remove(GoOffRails);
        }

        // Editor: tier, split, hardware mass/cost/capacity, and the battery push all track the build.
        void OnShipModified(ShipConstruct _)
        {
            if (!HighLogic.LoadedSceneIsEditor) return;
            ApplyTier();
            ApplyShieldedTier();
            _cachedVolume = ReadProceduralVolume();
            EnforceBoxFloor();
            RecomputeSplit(_cachedVolume);
            UpdateHardwareMass();
            PushBatteryToTank();
            UpdateRate();
        }

        // The authoritative "the box changed size" signal, and the ONLY one ROTanks gives us.
        //
        // onEditorShipModified is not enough. ProceduralParts fires it on a resize, so polling volume from
        // OnShipModified was sufficient while that was the only driver -- but ModuleROTank's resize path
        // (ModelChangedHandler -> UpdateDimensions/UpdateTankVolume/...) never fires it, verified against
        // ROLib.dll's IL. On a Probe Bus that left _cachedVolume frozen at whatever EditorFirstFrameSetup()
        // read, so every bus reported the same volume and resizing changed nothing.
        //
        // Both drivers DO send this: ROLib's UpdateTankVolume sets its Volume property and then calls
        // SendVolumeChangedEvent -> part.SendEvent("OnPartVolumeChanged", {newTotalVolume}), which is fired
        // at exactly the moment the volume changes. Same event ProceduralParts and RealFuels already speak,
        // and the same hook RP-1's ModuleProceduralAvionics uses.
        //
        // REENTRANCY: this module SENDS the same event from PushBatteryToTank (with the battery segment's
        // volume, to size the RealFuels tank). Listening without a guard would feed that back in as the new
        // box volume and shrink the part to nothing over a few frames. RP-1 guards the identical hazard by
        // toggling Events[...].active around its own send; _sendingVolume does the same job and also covers
        // the RF-side echo.
        [KSPEvent]
        public void OnPartVolumeChanged(BaseEventDetails data)
        {
            if (!HighLogic.LoadedSceneIsEditor || _sendingVolume) return;

            // ProceduralParts and RealFuels set this as a double; don't assume ROLib agrees.
            float newVolume;
            try { newVolume = (float)data.Get<double>("newTotalVolume"); }
            catch { try { newVolume = data.Get<float>("newTotalVolume"); } catch { return; } }
            if (newVolume <= 0f || Mathf.Approximately(newVolume, _cachedVolume)) return;

            _cachedVolume = newVolume;
            EnforceBoxFloor();
            RecomputeSplit(_cachedVolume);
            UpdateHardwareMass();
            PushBatteryToTank();
            UpdateRate();
        }

        void OnStage(int _)
        {
            UpdateRate();
            // onStageActivate is a GLOBAL GameEvent -- it fires once per staging on EVERY loaded avionics
            // module in the scene, not just on the vessel that staged. StageManager.ActivateStage() fires it
            // against FlightGlobals.ActiveVessel and only afterwards force_activate()s that stage's parts, so
            // at this instant a part that is about to be left behind is still aboard the active vessel.
            // Anything not aboard it is watching someone else's staging and must not arm the check at all.
            if (!setToDebrisOnStage || _debrisCheckRunning) return;
            if (!FlightGlobals.ready || vessel == null || vessel != FlightGlobals.ActiveVessel) return;
            StartCoroutine(CheckRenameDebris());
        }

        // Ported from RP-1's ModuleAvionics.CheckRenameDebris(): once staging has left this piece behind,
        // scan it for any command-capable part whose avionics is explicitly set to "Never" (any one vetoes)
        // — otherwise mark it Debris. Pure tracking-station hygiene; no funds/recovery/science effect.
        //
        // RP-1 decides this exactly once, 1s after the stage fires, reading FlightGlobals.ActiveVessel and
        // vessel.Parts raw. Both are legitimately null/empty for a while around a scene load or a vessel
        // split, and read raw they fail toward the wrong answer in BOTH directions: a null ActiveVessel
        // reads as "I am not the active vessel", and an empty part list reads as "no part vetoed" — which
        // together type a fully-assembled stack Debris — while a piece that has not finished separating at
        // the 1s mark is judged still-attached and then never looked at again. So: never conclude from
        // unreadable state, keep looking until it IS readable, and give up quietly if it never is.
        IEnumerator CheckRenameDebris()
        {
            _debrisCheckRunning = true;
            try
            {
                for (int tries = 0; tries < DebrisCheckTries; tries++)
                {
                    yield return new WaitForSeconds(1f);

                    if (part == null) yield break;      // part destroyed: nothing left to judge
                    Vessel v = part.vessel;
                    if (v == null) yield break;

                    // Unreadable — retry rather than conclude. An unloaded/mid-split vessel reports zero
                    // parts, which is not the same fact as "no part objected".
                    if (!FlightGlobals.ready || FlightGlobals.ActiveVessel == null) continue;
                    if (!v.loaded || v.parts.Count == 0) continue;
                    // Still aboard the vessel being flown — a later stage may yet separate us.
                    if (v == FlightGlobals.ActiveVessel) continue;
                    // Nothing sitting on the pad has been staged away from anything.
                    if (v.situation == Vessel.Situations.PRELAUNCH) continue;

                    foreach (Part p in v.Parts)
                    {
                        if (p.FindModuleImplementing<ModuleCommand>() == null) continue;
                        ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
                        if (!(axe?.setToDebrisOnStage ?? true)) yield break;   // an explicit "Never" vetoes
                    }
                    v.vesselType = VesselType.Debris;
                    yield break;
                }
            }
            finally { _debrisCheckRunning = false; }
        }

        // One in-flight debris check at a time per module: MechJeb's autostage can fire onStageActivate
        // many times in a second, and each firing used to queue its own independent verdict.
        bool _debrisCheckRunning;
        const int DebrisCheckTries = 10;

        void GoOnRails(Vessel v) => RailChange(v, true);
        void GoOffRails(Vessel v) => RailChange(v, false);

        // Ported from RP-1's ModuleAvionics: while on rails (unloaded/timewarping), draw auto-drops to the
        // current hibernate-equivalent rate regardless of the manual toggle, and reverts the instant it's
        // back off rails.
        void RailChange(Vessel v, bool onRails)
        {
            if (vessel != v) return;
            _onRails = onRails;
            UpdateRate();
        }

        // Flight only: recompute EC draw ~1 Hz so it tracks fuel burn / staging / on-rails state. Hardware
        // mass/cost/capacity are frozen and never change in flight. The editor-side allocation bar is driven
        // entirely by AxeAllocationBarHook reacting to PAW open/close events, not polled here.
        void Update()
        {
            if (HighLogic.LoadedSceneIsEditor) { PushDebugKnobs(); return; }
            if (!HighLogic.LoadedSceneIsFlight) return;
            PushDebugKnobs();   // knob changes must reach the controller without waiting for the 1 Hz tick
            if (Time.time < _nextFlightRecalc) return;
            _nextFlightRecalc = Time.time + 1f;
            EvaluateAutoGuidance();
            UpdateRate();
        }

        ModuleResource FindCommandEC()
        {
            ModuleCommand cmd = part.FindModuleImplementing<ModuleCommand>();
            if (cmd?.resHandler?.inputResources == null) return null;
            foreach (ModuleResource r in cmd.resHandler.inputResources)
                if (r != null && r.id == PartResourceLibrary.ElectricityHashcode) return r;
            return null;
        }

        // Resolve RealFuels' ModuleFuelTanks + the ProceduralPart volume property by reflection (RealFuels
        // and ProceduralParts aren't referenced by AXE.dll). Missing either => degrade gracefully. Also
        // resolves a kOSProcessor module, if present, for the kOS tier bridge below.
        void ResolveTankBridge()
        {
            const BindingFlags F = BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy;
            foreach (PartModule m in part.Modules)
            {
                string n = m.GetType().Name;
                if (_rfPM == null && n == "ModuleFuelTanks")
                {
                    _rfPM = m;
                    _rfCalcMass = m.GetType().GetMethod("CalculateMass", BindingFlags.Public | BindingFlags.Instance);
                    _rfMassField = m.GetType().GetField("mass", F);
                }
                else if (_procPM == null && n == "ProceduralPart")
                {
                    _procPM = m;
                    _procVolumeProp = m.GetType().GetProperty("Volume", F);
                    _procMinVolumeField = m.GetType().GetField("volumeMin", F);
                    _procCurShapeProp = m.GetType().GetProperty("CurrentShape", F);
                    _procSeekVolumeMethod = m.GetType().GetMethod("SeekVolume",
                        BindingFlags.Public | BindingFlags.Instance);
                }
                else if (_rotPM == null && n == "ModuleROTank")
                {
                    _rotPM = m;
                    _rotVolumeProp = m.GetType().GetProperty("Volume", F);
                }
                else if (_kosPM == null && n == "kOSProcessor")
                {
                    _kosPM = m;
                    Type kt = m.GetType();
                    _kosDiskSpaceField = kt.GetField("diskSpace", F);
                    _kosBaseDiskSpaceField = kt.GetField("baseDiskSpace", F);
                    _kosDiskSpaceCostFactorField = kt.GetField("diskSpaceCostFactor", F);
                    _kosDiskSpaceMassFactorField = kt.GetField("diskSpaceMassFactor", F);
                    _kosEcPerInstructionField = kt.GetField("ECPerInstruction", F);
                }
            }
        }

        // Push the current tier's kOS ladder onto the resolved kOSProcessor (no-op if kOS isn't installed).
        void ApplyKosTier()
        {
            if (_kosPM == null) return;
            try
            {
                int floor = Mathf.RoundToInt(_kosDiskSpace);
                _kosBaseDiskSpaceField?.SetValue(_kosPM, floor);
                if (_kosDiskSpaceField != null && (int)_kosDiskSpaceField.GetValue(_kosPM) < floor)
                    _kosDiskSpaceField.SetValue(_kosPM, floor);
                _kosDiskSpaceCostFactorField?.SetValue(_kosPM, _kosSpaceCostFactor);
                _kosDiskSpaceMassFactorField?.SetValue(_kosPM, _kosSpaceMassFactor);
                _kosEcPerInstructionField?.SetValue(_kosPM, _kosEcPerInstruction);
            }
            catch { }
        }

        // Total box volume, from whichever procedural driver owns this part -- ProceduralParts on the grey
        // Avionics Core, ROTanks on the Probe Bus.
        //
        // This is the INITIAL/fallback read only. Live changes arrive through OnPartVolumeChanged above,
        // because polling here is not sufficient: it runs from OnShipModified, and ModuleROTank's resize
        // path never fires onEditorShipModified (checked against ROLib.dll's IL -- ModelChangedHandler
        // calls UpdateDimensions/UpdateTankVolume/UpdateMass/... and nothing that reaches
        // ROLStockInterop.FireEditorUpdate). Relying on the poll alone froze a Probe Bus at its
        // first-frame volume: identical for every core model, unmoved by the diameter slider.
        float ReadProceduralVolume()
        {
            PartModule pm = _procPM ?? _rotPM;
            PropertyInfo prop = _procPM != null ? _procVolumeProp : _rotVolumeProp;
            if (pm == null || prop == null) return _cachedVolume;
            try { return Convert.ToSingle(prop.GetValue(pm, null)); }
            catch { return _cachedVolume; }
        }

        // Editor only: pin ProceduralPart's minimum volume so the box can't be sized below what the current
        // model actually needs — the flat Unguided hardware volume plus the reserved battery (Guided: just
        // the reserved battery, since its hardware can legitimately size all the way to zero capacity). Both
        // mass AND cost stay flat for Unguided regardless of box size; this floor only stops the box from
        // reading as physically too small to hold the hardware it's already paying full freight for.
        // Mirrors RP-1's ModuleProceduralAvionics.SetProcPartVolumeLimit: set volumeMin, refresh the shape's
        // own dimension-slider bounds (AdjustDimensionBounds, so the player can't drag back under it), and if
        // the box is ALREADY under the new floor — after a model switch, a tier change, or on an old craft —
        // SeekVolume it back up. No-op if ProceduralParts isn't the shape driver. The _enforcingFloor guard
        // is because SeekVolume can synchronously re-fire onEditorShipModified (re-entering this).
        void EnforceBoxFloor()
        {
            if (!HighLogic.LoadedSceneIsEditor || _enforcingFloor) return;
            if (_procPM == null || _procMinVolumeField == null) return;
            float floor = (guidanceEnabled ? 0f : FixedUnguidedHwVolume()) + EnduranceFloorVolume();
            _enforcingFloor = true;
            try
            {
                _procMinVolumeField.SetValue(_procPM, floor);
                // AdjustDimensionBounds lives on the CURRENT shape instance (its type varies by shape), so
                // resolve it per-call the same way RP-1 does rather than caching a single MethodInfo.
                object shape = _procCurShapeProp?.GetValue(_procPM, null);
                if (shape != null)
                {
                    MethodInfo adjust = shape.GetType().GetMethod("AdjustDimensionBounds",
                        BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy);
                    adjust?.Invoke(shape, Array.Empty<object>());
                }
                // Only nudge the box up when it's genuinely under the floor (spare a resize otherwise).
                if (_procSeekVolumeMethod != null && floor - _cachedVolume > 0.0001f)
                {
                    SeekVolume(floor);
                    _cachedVolume = ReadProceduralVolume();
                }
            }
            catch { }
            finally { _enforcingFloor = false; }
        }

        // Invoke ProceduralPart.SeekVolume, handling both the 1-arg and the newer 2-arg (target, direction)
        // signatures — direction 1 = Ceil, so a box that can't fit the floor exactly lands just above it,
        // never a hair below. Reflected; AXE.dll doesn't reference ProceduralParts.
        void SeekVolume(float targetVolume)
        {
            try
            {
                object[] args = _procSeekVolumeMethod.GetParameters().Length == 1
                    ? new object[] { targetVolume }
                    : new object[] { targetVolume, 1 };
                _procSeekVolumeMethod.Invoke(_procPM, args);
            }
            catch { }
        }

        // Pick the best researched Guided/Unguided tier (lowest-or-tied NE mass factor; tier 0 "start" if
        // none researched — the unconditional floor). <= (not <) so a researched tier tying the floor on NE
        // mass (start vs postWarAvionics) still advances, letting Science-Core step down off the tied floor.
        void ApplyTier()
        {
            int best = 0;
            for (int i = 1; i < _ladTech.Length; i++)
                if (Researched(_ladTech[i]) && _ladMass[i] <= _ladMass[best]) best = i;
            _massFactor = _ladMass[best];
            _powerFactor = _ladPower[best];
            _costFactor = _ladCost[best];
            _scMassFactor = _ladScMass[best];
            _scPowerFactor = _ladScPower[best];
            _scCostFactor = _ladScCost[best];
            _scDensity = _ladScDensity[best];
            _scAllowAxial = _ladScAxial[best];
            _hasScienceContainer = _ladHasSci[best];
            _kosDiskSpace = _ladKosDisk[best];
            _kosSpaceCostFactor = _ladKosCostFactor[best];
            _kosSpaceMassFactor = _ladKosMassFactor[best];
            _kosEcPerInstruction = _ladKosEcPerInstr[best];
            _unshHibernateFactor = _ladUnshHibernate[best];
            ApplyKosTier();
        }

        // Shielded axis: pick the best-researched tier among only those carrying a Shielded rung
        // (shMassFactor > 0 AND an shTech shd_* node). Gated on shTech (the shd_* lane), NOT on the guided
        // gnc_/comp_ tech at the same index — the Shielded axis is its own research investment (2026-07-14),
        // matching the tree's shd_* serial chain + Deep-Space-* grants. No floor — -1 means "not available yet."
        void ApplyShieldedTier()
        {
            int best = -1;
            for (int i = 0; i < _ladTech.Length; i++)
            {
                if (_ladShMass[i] <= 0f) continue;
                string shTech = (_ladShTech != null && i < _ladShTech.Length) ? _ladShTech[i] : null;
                if (string.IsNullOrEmpty(shTech)) continue;   // no shd_ node gates this rung -> not a real Shielded tier
                if (!Researched(shTech)) continue;
                if (best == -1 || _ladShMass[i] <= _ladShMass[best]) best = i;
            }
            _bestShieldedIdx = best;
            if (best >= 0)
            {
                _shMassFactor = _ladShMass[best];
                _shCostFactor = _ladShCost[best];
            }
        }

        // Smoke-test accessor (AutoTest): reports which shd_* node gates each Shielded rung, straight from the
        // parsed static ladder (populated by the prefab's OnLoad). Confirms the config's TIER{shTech=...} wired
        // through to the plugin. Expect 10 gates, shd_basicAvionics .. shd_commercialOffTheShelfAvionics.
        internal static string ShieldedLadderReport()
        {
            var gates = new List<string>();
            for (int i = 0; i < _ladShTech.Length && i < _ladShMass.Length; i++)
                if (_ladShMass[i] > 0f && !string.IsNullOrEmpty(_ladShTech[i]))
                    gates.Add(i + ":" + _ladShTech[i]);
            return "shieldedTiers=" + gates.Count + " gates=[" + string.Join(", ", gates.ToArray()) + "]";
        }

        // Smoke-test accessor (AutoTest): where the avionics-shutdown capability (RP-1's Shutdown Avionics,
        // gated by its disabledPowerFactor > 0) actually starts on each axis, read from the parsed static
        // ladder rather than assumed. Confirms the config's TIER{unshHibernateFactor=...} wired through.
        // Expect Unshielded to start at index 9 (comp_multiplyRedundantFlightComputer = RP-1's
        // advancedAvionics, the first NE tier carrying disabledPowerFactor) at depth 0.1, and Shielded at
        // index 4 (shd_basicAvionics), matching RP-1's Deep-Space having the field on every rung.
        internal static string HibernateLadderReport()
        {
            int firstUnsh = -1;
            float unshDepth = 0f;
            for (int i = 0; i < _ladUnshHibernate.Length; i++)
                if (_ladUnshHibernate[i] > 0f) { firstUnsh = i; unshDepth = _ladUnshHibernate[i]; break; }
            int firstSh = -1;
            for (int i = 0; i < _ladShTech.Length && i < _ladShMass.Length; i++)
                if (_ladShMass[i] > 0f && !string.IsNullOrEmpty(_ladShTech[i])) { firstSh = i; break; }
            string unshTech = (firstUnsh >= 0 && firstUnsh < _ladTech.Length) ? _ladTech[firstUnsh] : "none";
            string shTech = (firstSh >= 0 && firstSh < _ladShTech.Length) ? _ladShTech[firstSh] : "none";
            return "shutdownStarts unshielded=" + firstUnsh + " (expect 9, " + unshTech + ") depth=" + unshDepth.ToString("0.###")
                 + " | shielded=" + firstSh + " (expect 4, " + shTech + ")"
                 + " | scienceCore=never";
        }

        bool ShieldedActive => shieldedEnabled && _bestShieldedIdx >= 0;
        // Whether the Shielded TOGGLE itself is unlocked. Now that each Shielded rung gates on its own shd_*
        // node (see ApplyShieldedTier + _ladShTech), _bestShieldedIdx becomes >= 0 exactly when the player has
        // researched a real Shielded tier -- so the toggle tracks that directly (first appears once
        // shd_basicAvionics is researched). No separate hardcoded tech gate needed.
        public bool ShieldedUnlocked => _bestShieldedIdx >= 0;
        float EffectiveMassFactor() => ShieldedActive ? _shMassFactor : _massFactor;
        float EffectiveCostFactor() => ShieldedActive ? _shCostFactor : _costFactor;
        float EffectiveMassConstant() => ShieldedActive ? shMassConstant : massConstant;
        float EffectiveCostConstant() => ShieldedActive ? shCostConstant : costConstant;
        float EffectivePowerConstant() => ShieldedActive ? shPowerConstant : powerConstant;

        // Editor only: how much box volume Unguided's flat per-tier hardware mass occupies. Not player-
        // adjustable (Unguided's mass doesn't scale with box size) — pinned every recompute.
        float FixedUnguidedHwVolume() => EffectiveDensity() > 0f ? (_scMassFactor / 1000f) / EffectiveDensity() : 0f;

        // Editor only: split total box volume V into battery/hardware/empty. If the player hasn't
        // explicitly set a split, use the default 25% battery / 75% hardware (Unguided: hardware is pinned,
        // battery gets the rest). If they have, re-fit toward the REMEMBERED desired values (not whatever
        // battVolume/hwVolume happened to be clamped to on the last resize) -- battery gets priority (fit
        // it first), then hardware gets whatever room is left. Any volume the box has GAINED since the
        // split was last explicitly committed (desiredTotalVolume) flows to the player-adjustable segment
        // (hardware for Guided, battery for Unguided) -- growing the box is how you get more capacity/
        // charge; without this, a resize bigger would only ever balloon "empty," and the player would have
        // to re-drag the handle every single time after a resize for it to do anything. Volume the box has
        // LOST (a shrink) still re-fits toward the remembered values exactly as before.
        void RecomputeSplit(float v)
        {
            float growth = hasExplicitSplit ? Mathf.Max(0f, v - desiredTotalVolume) : 0f;
            if (!guidanceEnabled)
            {
                hwVolume = FixedUnguidedHwVolume();
                battVolume = hasExplicitSplit ? Mathf.Min(desiredBattVolume + growth, Mathf.Max(0f, v - hwVolume))
                                               : Mathf.Max(0f, v - hwVolume);
            }
            else if (!hasExplicitSplit)
            {
                battVolume = 0.25f * v;
                hwVolume = 0.75f * v;
            }
            else
            {
                battVolume = Mathf.Min(desiredBattVolume, v);
                hwVolume = Mathf.Min(desiredHwVolume + growth, Mathf.Max(0f, v - battVolume));
            }
            battVolume = Mathf.Max(battVolume, EnduranceFloorVolume());
            battVolume = Mathf.Min(battVolume, v);
            hwVolume = Mathf.Max(0f, Mathf.Min(hwVolume, v - battVolume));
        }

        // Minimum battery volume — ground-truthed verbatim against RP-1's real reservedRFTankVolume
        // (ProceduralAvionics.cfg): a small FIXED constant, identical at every tier, not runtime/draw-based.
        // RP-1 has NO equivalent floor on the hardware side at all — hardware volume there is purely
        // GetAvionicsMass()/avionicsDensity, whatever the player's rating computes, with nothing enforced
        // as a minimum. This matches both facts: only battVolume gets a floor, hwVolume never does.
        const float GuidedReservedVolume = 0.003f;    // 3 L — RP-1's Near-Earth/Deep-Space, every tier
        const float UnguidedReservedVolume = 0.0015f; // 1.5 L — RP-1's Science-Core, every tier
        float EnduranceFloorVolume() => guidanceEnabled ? GuidedReservedVolume : UnguidedReservedVolume;

        // Editor only: hardware mass/cost/capacity, all derived from hwVolume (frozen at launch, persisted).
        //   Guided   = hwVolume * density -> mass; capacity = inverse mass-polynomial of that mass; cost is
        //              the (forward) cost-polynomial of that capacity — mirrors RP-1's real
        //              GetAvionicsCost(controllableMass), which takes the rating, not the mass, as input.
        //   Unguided = RP-1's flat per-tier mass (scMassFactor/1000 t); no capacity concept.
        void UpdateHardwareMass()
        {
            if (guidanceEnabled)
            {
                // avionicsMass is the HONEST mass the player actually built (box volume -> mass) -- this
                // is what IPartMassModifier reports and must never be adjusted down.
                avionicsMass = hwVolume * EffectiveDensity();
                // Shielded: RP-1 adds an extra surface-area-scaled shielding mass ON TOP of the curve's
                // own mass (GetShieldedAvionicsMass = curveMass + curveMass^(2/3)*shieldingMassFactor) --
                // i.e. part of avionicsMass is "spent" on shielding rather than contributing to capacity.
                // AXE's box-first model runs the opposite direction (physical mass -> capacity, not
                // capacity -> mass), so recover the equivalent "curve mass" that capacity should be
                // derived from by inverting that relation: curveMass = avionicsMass - curveMass^(2/3)*
                // shieldingMassFactor. A few fixed-point iterations converge to well under 0.05% error
                // (shieldingMassFactor is a ~10-20% term).
                float curveMass = avionicsMass;
                if (ShieldedActive)
                {
                    for (int i = 0; i < 4; i++)
                        curveMass = avionicsMass - Mathf.Pow(curveMass, 2f / 3f) * shieldingMassFactor;
                    curveMass = Mathf.Max(0f, curveMass);
                }
                capacityTons = GetInversePolynomial(curveMass * 1000f, massExponent, EffectiveMassConstant(), EffectiveMassFactor());
                avionicsCost = Poly(capacityTons, costExponent, EffectiveCostConstant(), EffectiveCostFactor());
            }
            else
            {
                avionicsMass = _scMassFactor / 1000f;
                avionicsCost = _scCostFactor;
                capacityTons = 0f;
            }
        }

        // Push the battery segment's volume into RealFuels (RF then sizes the EC tank + recomputes its
        // mass/cost). Driven from OnShipModified/OnStartFinished, after RecomputeSplit/UpdateHardwareMass.
        void PushBatteryToTank()
        {
            if (!HighLogic.LoadedSceneIsEditor || _rfPM == null) return;
            SendVolumeChangedEvent(battVolume);
            try { _rfCalcMass?.Invoke(_rfPM, null); } catch { }
        }

        // Sends the battery segment's volume to RealFuels. This is the SAME event this module now listens
        // for (OnPartVolumeChanged), so _sendingVolume must be held for the duration: without it our own
        // broadcast comes straight back as "the box is now battery-sized" and the part collapses.
        void SendVolumeChangedEvent(double newVolume)
        {
            var data = new BaseEventDetails(BaseEventDetails.Sender.USER);
            data.Set<string>("volName", "Tankage");
            data.Set("newTotalVolume", newVolume);     // m^3 — RealFuels' ModuleFuelTanks listens for this
            _sendingVolume = true;
            try { part.SendEvent("OnPartVolumeChanged", data, 0); }
            finally { _sendingVolume = false; }
        }

        // Called every drag-move frame by the allocation bar: writes the live split directly, so every
        // other readout (mass, cost, capacity, EC draw, penalty, endurance, and the actual RealFuels
        // battery pool via PushBatteryToTank) updates in real time as the player drags -- whatever the
        // last position is IS the state, no separate preview/pending shadow copy to keep in sync (that
        // duplication was the likely source of the "doesn't update" / "snaps back" bugs). Clamped by the
        // same endurance floor as everywhere else, so the floor's effect is visible live, not just on
        // release. Symmetry sync and the comparatively expensive onEditorShipModified event are deliberately
        // NOT fired here every frame -- see CommitAllocationDrag(), called once on release.
        public void LiveUpdateSplit(float battVolumeM3, float hwVolumeM3)
        {
            float v = _cachedVolume;
            if (v <= 0f) return;
            // Remember the RAW dragged-to values (pre-floor) as the desired intent -- a resize re-fits
            // toward these, not toward whatever the floor/clamp forced the live battVolume/hwVolume to.
            desiredBattVolume = Mathf.Max(0f, battVolumeM3);
            desiredHwVolume = Mathf.Max(0f, hwVolumeM3);
            float floor = EnduranceFloorVolume();
            battVolume = Mathf.Clamp(Mathf.Max(desiredBattVolume, floor), 0f, v);
            hwVolume = Mathf.Clamp(desiredHwVolume, 0f, v - battVolume);
            UpdateHardwareMass();
            PushBatteryToTank();
            UpdateRate();
        }

        // Called once when the drag ends: the values are already live-correct (LiveUpdateSplit clamps
        // continuously), so this just marks the split explicit, syncs symmetry counterparts to match, and
        // fires the one onEditorShipModified other systems need to react to.
        public void CommitAllocationDrag()
        {
            hasExplicitSplit = true;
            desiredTotalVolume = _cachedVolume;
            foreach (Part p in part.symmetryCounterparts)
            {
                ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
                if (axe == null) continue;
                axe.battVolume = battVolume; axe.hwVolume = hwVolume;
                axe.desiredBattVolume = desiredBattVolume; axe.desiredHwVolume = desiredHwVolume;
                axe.desiredTotalVolume = axe._cachedVolume;
                axe.hasExplicitSplit = true;
            }
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
        }

        // Called by the allocation window's Reset button.
        public void ResetAllocationToDefault()
        {
            foreach (Part p in part.symmetryCounterparts)
            {
                ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
                if (axe != null) axe.hasExplicitSplit = false;
            }
            hasExplicitSplit = false;
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
        }

        public float CachedVolumeLiters => _cachedVolume * 1000f;
        public float FixedUnguidedHwVolumeLiters => FixedUnguidedHwVolume() * 1000f;

        float VesselMassTons()
        {
            if (HighLogic.LoadedSceneIsEditor)
                return EditorLogic.fetch?.ship != null ? EditorLogic.fetch.ship.GetTotalMass() : 0f;
            return vessel != null ? (float)vessel.totalMass : 0f;
        }

        // Live DRY mass (tons) — vessel mass excluding propellant/resources, so EC draw is independent of
        // fuel load and steps down only when stages/parts are dropped.
        float VesselDryMassTons()
        {
            float t = 0f;
            List<Part> parts = HighLogic.LoadedSceneIsEditor ? EditorLogic.fetch?.ship?.parts : vessel?.parts;
            if (parts == null) return 0f;
            for (int i = 0; i < parts.Count; i++)
            {
                Part p = parts[i];
                if (p == null) continue;
                t += p.mass + p.GetModuleMass(p.mass);
            }
            return t;
        }

        static float Poly(float value, float exponent, float constant, float factor)
            => (Mathf.Pow(value, exponent) + constant) * factor;

        // RP-1's GetInversePolynomial (ModuleProceduralAvionics.cs), ground-truthed verbatim: given a mass,
        // solve for the "load"/capacity that would produce it under the forward polynomial. Clamps to 0 on
        // NaN/Infinity, reproducing RP-1's own "hard minimum box size for any positive capacity" floor.
        static float GetInversePolynomial(float value, float exponent, float constant, float factor)
        {
            if (factor <= 0f) return 0f;
            float res = Mathf.Pow(value / factor - constant, 1f / exponent);
            if (float.IsNaN(res) || float.IsInfinity(res)) return 0f;
            return res;
        }

        // MAX across the vessel's active Guided cores (RP-1's own 2021 anti-cheese rule — SUM lets a
        // stack of cheap small cores cheese capacity). Ground-truthed against RP-1's real
        // ControlLockerUtils.ShouldLock(): it aggregates every ModuleAvionics' CurrentMassLimit
        // unconditionally (gated only on having EC connected, or being in the editor) -- there is NO
        // "is guidance tech researched" gate on whether a core's mass counts. A core's tier (and
        // therefore capacityTons) is ALWAYS valid -- ApplyTier()'s tier-0 floor guarantees that -- so
        // "dumb" avionics (guidance not yet researched) still needs to not overload for its own rated
        // mass; GuidanceUnlocked only gates whether the vessel can actively STEER (GuidanceActive),
        // a separate concern handled elsewhere. Previously this method also excluded un-researched
        // cores here, which meant EVERY Guided core showed max overload penalty from the moment it was
        // placed until guidanceTech was researched, regardless of how it was sized -- a real bug, not
        // RP-1 parity. Hibernating cores still don't contribute (asleep, not actively protecting the
        // vessel's overload budget).
        float EffectiveCapacityTons()
        {
            List<Part> parts = HighLogic.LoadedSceneIsEditor ? EditorLogic.fetch?.ship?.parts : vessel?.parts;
            if (parts == null) return capacityTons;
            float max = 0f;
            for (int i = 0; i < parts.Count; i++)
            {
                Part p = parts[i];
                if (p == null) continue;
                ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
                if (axe != null && axe.guidanceEnabled && !axe.hibernating && axe.guidanceEngaged
                    && axe.capacityTons > max)
                    max = axe.capacityTons;
                // Fixed-capacity units (ModuleAxeFixedAvionics) count toward the same MAX. A vessel already
                // covered by, say, a 16 t Agena bus is not overloaded just because a small procedural core
                // rides along, and shouldn't pay this module's penalty for it -- RP-1 took one vessel-wide
                // MAX across every avionics unit, whichever module supplied it.
                ModuleAxeFixedAvionics fix = p.FindModuleImplementing<ModuleAxeFixedAvionics>();
                if (fix != null && fix.CapacityTons > max) max = fix.CapacityTons;
            }
            return max;
        }

        // r = live vessel mass / effective capacity. r<=1 -> no penalty. Past that, a smooth exponential
        // penalty (spec-locked k=8) — gentle at small overages, prohibitive past ~25-50% over.
        //
        // CEILING on the multiplier, set to e^8 = 2981 -- exactly the r=2 point, so the curve runs its full
        // natural course out to TWICE capacity and only stops climbing past that. Everything below 2x over
        // is completely untouched (1.1x -> 2.2, 1.25x -> 7.4, 1.5x -> 54.6).
        //
        // Sized against measured craft, not the spec's reference burn. RealFuels' ElectricCharge tank holds
        // 500 EC/L (measured off saved craft: 41 L battery -> 20496 EC), and draw is watts/1000 EC/s, so a
        // representative guided core (31.7 t capacity, 146 W, 41 L battery) carries ~39 HOURS of normal
        // operation. An ascent takes 6-10 minutes. For overload to actually cost that vehicle its guidance
        // mid-ascent the multiplier has to exceed ~390 (6 min) / ~234 (10 min); at the previous 54.6 ceiling
        // it survived 43 minutes and sailed through ascent untouched. NOTE this means docs/AVIONICS_SPEC.md's
        // own k=8 calibration ("50% over = 89% of vessel mass in battery") is out by orders of magnitude
        // against the shipped EC economy -- the whole curve is arguably under-tuned, not just its ceiling.
        //
        // The ceiling still exists because the raw curve reaches e^80 (~5.5e34 W) by r=11, which flattens any
        // battery inside a single physics tick -- that drops ModuleCommand and takes staging and throttle
        // with it, which is both harsher than the attitude lock this penalty replaced and unrecoverable. At
        // e^8 the worst case measured here (a 3 L battery) still lasts ~3 s: fatal, but the vehicle stays
        // commandable long enough to stage. A KSPField so it can be retuned without a rebuild.
        [KSPField] public float penaltyMultiplierCap = 2981f;

        // Pushed every frame in BOTH scenes. These are UI_ knobs, and changing one does not fire
        // onEditorShipModified, so an editor-only push tied to the recompute never saw the change until the
        // player happened to move a part.
        void PushDebugKnobs()
        {
            if (!HighLogic.LoadedSceneIsEditor && (vessel == null || !vessel.isActiveVessel)) return;
            AxeControlLockerUtils.NoiseOverrideEnabled = noiseOverride;
            AxeControlLockerUtils.NoiseOverrideValue = noiseOverrideValue;
            AxeControlLockerUtils.NoiseHz = noiseHz;
            AxeControlLockerUtils.NoiseHzAutoScale = noiseHzAuto;
            AxeControlLockerUtils.NoiseWhite = noiseWhite;
            AxeControlLockerUtils.NoiseK = noiseK;
            AxeControlLockerUtils.NoiseMax = noiseMax;
            AxeControlLockerUtils.NoiseRoll = noiseRoll;
            AxeControlLockerUtils.NoiseOnRcs = noiseOnRcs;
            AxeControlPenalties.Index = noiseMode;
            AxeControlLockerUtils.OvergainSlope = overgainSlope;
            AxeControlLockerUtils.DelayTicksMax = delayTicksMax;
            AxeControlLockerUtils.NoiseRcsScale = noiseRcsScale;
            AxeControlLockerUtils.HardCutoff = hardCutoff;
        }

        // PROTOTYPE readout. In flight the controller's value is authoritative (it is what actually scales
        // ctrlState); in the editor there is no controller, so recompute from the same numbers. Unguided has
        // no capacity concept and therefore no authority concept.
        void UpdateAuthorityDisplay()
        {
            // Test rig: only the focused vessel's (or the editor's) core drives the statics, so a core on an
            // unfocused vessel can't clobber the value being flown. Multiple cores on one craft: last wins.
            PushDebugKnobs();

            if (ScienceCoreMode) { authorityDisplay = "n/a — unguided"; return; }

            AxeAvionicsController ctl = AxeAvionicsController.Instance;
            if (HighLogic.LoadedSceneIsFlight)
            {
                if (ctl == null) noiseDebug = "no controller";
                else
                {
                    Vector3 n = ctl.LastNoise;
                    noiseDebug = $"ticks {ctl.ModifierTicks}  p{n.x:+0.00;-0.00}  y{n.y:+0.00;-0.00}  r{n.z:+0.00;-0.00}";
                }
            }

            if (noiseOverride)
            {
                authorityDisplay = $"{Mathf.Clamp01(noiseOverrideValue) * 100f:F0}% noise — DEBUG pinned";
                return;
            }

            float sigma;
            if (HighLogic.LoadedSceneIsFlight && AxeAvionicsController.Instance != null
                && vessel != null && vessel.isActiveVessel)
            {
                sigma = AxeAvionicsController.Instance.ControlNoise;
            }
            else
            {
                float capacity = EffectiveCapacityTons();
                float mass = VesselMassTons();
                sigma = (capacity <= 0f || mass <= 0f)
                    ? (mass > 0f ? AxeControlLockerUtils.NoiseMax : 0f)
                    : AxeControlLockerUtils.NoiseFor(mass / capacity);
            }

            authorityDisplay = AxeControlPenalties.Current.Describe(sigma);
        }

        float PenaltyMultiplier()
        {
            // A shut-down (or on-rails) core has already left EffectiveCapacityTons and is not running a
            // guidance loop, so there is nothing to penalise -- RP-1's disabled rate is likewise a plain
            // fraction of the enabled rate with no overload term. Without this guard a lone sleeping core
            // excluded ITSELF from the vessel MAX, capacity fell to 0, r went to +Infinity, and the
            // advertised "5% depth" was 5% of e^80 -- which is why shutting an overloaded core down never
            // saved it, and why hibernation could not be used as an escape from overload at all.
            // PROTOTYPE (docs/AVIONICS_AUTHORITY.md): the EC overload penalty is STOOD DOWN while the
            // control-authority model is being flown, so the two do not stack and the feel being judged is
            // one mechanic. Everything below is left intact -- k, the cap, the curve -- so reverting is
            // deleting this line. Delete the rest only once the authority model is actually chosen.
            return 1f;
#pragma warning disable CS0162 // unreachable while stood down -- deliberate, see above
            if (!guidanceEnabled || Asleep) return 1f;
            float mass = VesselMassTons();
            if (mass <= 0f) return 1f;
            float capacity = EffectiveCapacityTons();
            float r = mass / capacity;   // capacity 0 => +Infinity => pinned at the cap below, never NaN
            return r <= 1f ? 1f : Mathf.Min(Mathf.Exp(8f * (r - 1f)), penaltyMultiplierCap);
#pragma warning restore CS0162
        }

        // Operating EC draw (watts) for the current model, before idle/hibernation reduction, WITH the
        // overload penalty already folded in (so both the editor preview and the flight readout show it):
        //   Guided draws off live DRY mass and gets lighter per researched tier, then scaled by the
        //   overload penalty; Science-Core draws a flat per-tier rate (no capacity concept, no penalty).
        float ComputeBaseWatts() => TierWatts() * (guidanceEnabled ? PenaltyMultiplier() : 1f);

        // The tier/mass-based draw BEFORE the overload penalty is applied (ComputeBaseWatts() multiplies
        // this by PenaltyMultiplier()) -- kept separate since some callers need the unpenalized figure.
        float TierWatts()
        {
            if (!guidanceEnabled) return _scPowerFactor;
            float m = VesselDryMassTons();
            if (m <= 0f) return 0f;
            return Poly(m, powerExponent, EffectivePowerConstant(), _powerFactor);
        }

        // Actual live draw: forced to the current hibernate depth while shut down OR on rails (matches
        // RP-1's auto-drop-on-warp, independent of the manual toggle); otherwise Science-Core stays flat,
        // Guided draws full when guiding and idleFactor when dumb.
        float ComputeWatts() => ComputeWatts(_onRails);

        // RP-1 parity (ModuleAvionics.GetPowerDraw / ModuleProceduralAvionics.GetDisabledkW): the disabled
        // rate is GetEnabledkW() * disabledPowerFactor, and RP-1's enabled kW carries no overload term at
        // all -- RP-1 locks attitude instead of taxing power. So the sleeping rate here is built from
        // TierWatts(), the raw tier/mass draw, NOT from ComputeBaseWatts(), which folds the penalty in.
        float ComputeWatts(bool onRails)
        {
            if (guidanceEnabled && CanHibernate && (hibernating || onRails))
                return TierWatts() * CurrentHibernateFactor;
            float b = ComputeBaseWatts();
            if (!guidanceEnabled) return b;
            return GuidanceActive ? b : b * idleFactor;
        }

        void UpdateRate()
        {
            currentWatts = HighLogic.LoadedSceneIsEditor ? ComputeBaseWatts() : ComputeWatts();
            penaltyPercent = (PenaltyMultiplier() - 1f) * 100f;
            UpdateAuthorityDisplay();
            _ecConsumption = new KeyValuePair<string, double>(EcName, -currentWatts / 1000.0);
            if (_commandEC != null) _commandEC.rate = KerbalismPresent ? 0f : currentWatts / 1000f;
            UpdateAllocationSummary();
            UpdateMassReadouts();
            SetGui();
        }

        void UpdateAllocationSummary()
        {
            float empty = Mathf.Max(0f, _cachedVolume - battVolume - hwVolume);
            allocationSummary = $"{battVolume * 1000f:F0} L batt / {hwVolume * 1000f:F0} L hw / {empty * 1000f:F0} L empty";
        }

        // Battery mass + the part's true total. Called from UpdateRate(), which every editor path already
        // reaches AFTER PushBatteryToTank() has re-run RealFuels' CalculateMass() — so RF's `mass` is fresh
        // for the split the player just dragged, not one frame stale. In flight both are static: RF's mass
        // is persisted and this module's hardware mass is frozen at launch.
        //
        // The total is deliberately MEASURED through KSP's own dry-mass path rather than summed from
        // hardware + battery: both of those land in it as IPartMassModifier contributions, but so does
        // anything else on the part (Kerbalism's HardDrive data/sample capacity, ProceduralPart's
        // hollow-volume mass), and RealFuels reports itself NON-ADDITIVELY (`mass - prefabMass`, replacing
        // the part's 1 t prefab mass rather than adding to it). Adding our own two numbers would quietly
        // disagree with the mass KSP actually flies.
        void UpdateMassReadouts()
        {
            batteryMass = ReadTankMass();
            totalPartMass = part.mass + part.GetModuleMass(part.mass) + part.GetResourceMass();
        }

        // RealFuels' own computed tank mass for the battery segment (tankage base + cells). 0 if RealFuels
        // isn't driving this part — same graceful degradation as the rest of the RF bridge.
        float ReadTankMass()
        {
            if (_rfPM == null || _rfMassField == null) return 0f;
            try { return Convert.ToSingle(_rfMassField.GetValue(_rfPM)); }
            catch { return 0f; }
        }

        [KSPEvent(guiActive = true, guiActiveEditor = true, guiName = "Disengage Guidance",
                  groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleGuidanceEngaged() => SetEngaged(!guidanceEngaged, manual: true);

        [KSPAction("Engage Guidance")]
        public void EngageAction(KSPActionParam _) => SetEngaged(true, manual: true);

        [KSPAction("Disengage Guidance")]
        public void DisengageAction(KSPActionParam _) => SetEngaged(false, manual: true);

        void SetEngaged(bool value, bool manual)
        {
            if (value == guidanceEngaged) return;
            guidanceEngaged = value;

            if (HighLogic.LoadedSceneIsFlight)
            {
                float mass = VesselMassTons();
                if (value)
                    AxeAvionicsController.Announce(mass > capacityTons && capacityTons > 0f
                        ? "Guidance engaged over capacity — control will be unreliable."
                        : "Vessel within rating. Guidance engaged.");
                else
                    AxeAvionicsController.Announce(manual
                        ? "Guidance disengaged — attitude control lost, staging and throttle retained."
                        : $"Docked mass {mass:N1} t exceeds {capacityTons:N1} t rating. Guidance disengaged — attitude locked.");
            }

            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
            else if (vessel != null)
                GameEvents.onVesselWasModified.Fire(vessel);
            UpdateRate();
        }

        // AUTO-ENGAGE tests THIS UNIT'S capacity, never the vessel MAX. A disengaged unit contributes 0, so
        // if it is the only avionics aboard the MAX is 0 and r is infinite -- a MAX-based condition could
        // never become true again and the unit would be stuck off forever.
        //
        // AUTO-DISENGAGE fires on COUPLING EVENTS only, never on a mass watch: r also rises when CAPACITY
        // falls (staging away the primary unit), which a mass watch misses entirely, and ISRU raises mass
        // continuously, which a mass watch would trip on mid-run.
        void EvaluateAutoGuidance()
        {
            if (!autoGuidance || !HighLogic.LoadedSceneIsFlight || ScienceCoreMode) return;
            if (capacityTons <= 0f) return;
            float mass = VesselMassTons();
            if (mass <= 0f) return;

            if (!guidanceEngaged && mass <= capacityTons) SetEngaged(true, manual: false);
            else if (guidanceEngaged && _coupledThisTick && mass > capacityTons) SetEngaged(false, manual: false);
            _coupledThisTick = false;
        }

        bool _coupledThisTick;
        void OnCouple(GameEvents.FromToAction<Part, Part> _) { _coupledThisTick = true; }

        void SetGui()
        {
            // Model selector: VAB-only (model + mass are frozen at launch).
            BaseEvent mt = Events[nameof(ToggleGuidance)];
            mt.guiActive = false;
            mt.guiActiveEditor = true;
            mt.guiName = guidanceEnabled ? "Switch to Unguided" : "Switch to Guided";

            // Shielding selector: VAB-only, Guided-only, blocked until ShieldedUnlocked (gnc_basicAvionics).
            BaseEvent sh = Events[nameof(ToggleShielding)];
            sh.guiActive = false;
            sh.guiActiveEditor = guidanceEnabled && ShieldedUnlocked;
            sh.guiName = shieldedEnabled ? "Switch to Unshielded" : "Switch to Shielded";

            // Shutdown/Activate: RP-1's own avionics toggle. Available in the EDITOR as well as in flight --
            // RP-1 sets guiActive and guiActiveEditor alike from GetToggleable() -- so a stage's avionics can
            // be BUILT already shut down instead of only being switched off after launch. Guided only, gated
            // by CanHibernate (Unshielded needs index 9; Shielded from its own first tier).
            BaseEvent ge = Events[nameof(ToggleGuidanceEngaged)];
            ge.guiName = guidanceEngaged ? "Disengage Guidance" : "Engage Guidance";
            ge.guiActive = ge.guiActiveEditor = !ScienceCoreMode;

            BaseEvent hb = Events[nameof(ToggleHibernation)];
            hb.guiActive = CanHibernate;
            hb.guiActiveEditor = CanHibernate;
            hb.active = CanHibernate;
            hb.guiName = hibernating ? "Activate Avionics" : "Shutdown Avionics";
            // RP-1 exposes all three (Toggle / Shutdown / Activate) and hides whichever is a no-op in the
            // current state -- except in the editor, where both directions stay listed so either can be
            // bound to an action group regardless of the state the craft is saved in.
            Actions[nameof(HibernateAction)].active = CanHibernate;
            Actions[nameof(ShutdownAction)].active = CanHibernate && (!hibernating || HighLogic.LoadedSceneIsEditor);
            Actions[nameof(ActivateAction)].active = CanHibernate && (hibernating || HighLogic.LoadedSceneIsEditor);

            capacityDisplay = ScienceCoreMode ? "n/a — unguided"
                            : hibernating     ? "none — shut down"
                            : capacityTons > 0f ? $"{capacityTons:N2} t"
                            : "none — box too small for this tier";

            guidanceStatus = hibernating ? "shut down — no guidance, out of the steerable-mass budget"
                           : ScienceCoreMode ? (_scAllowAxial ? "Unguided — axial thrust only (spin-stabilized)"
                                                              : "Unguided — no steering")
                           : !GuidanceUnlocked ? "Guided — guidance not yet researched (dumb)"
                           : shieldedEnabled ? "Guided — Shielded — guidance active"
                           : "Guided — Unshielded — guidance active";
        }

        // VAB-only: pick the as-built model. Firing onEditorShipModified re-runs the full editor recompute;
        // mass/cost/capacity are then frozen at launch.
        [KSPEvent(guiActive = false, guiActiveEditor = true, guiName = "Switch to Unguided", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleGuidance()
        {
            guidanceEnabled = !guidanceEnabled;
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
            else
                UpdateRate();
            SetGui();
        }

        // VAB-only, Guided-only: pick Shielded vs Unshielded. Blocked (no-op) until ShieldedUnlocked.
        [KSPEvent(guiActive = false, guiActiveEditor = true, guiName = "Switch to Shielded", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleShielding()
        {
            if (!guidanceEnabled || !ShieldedUnlocked) return;
            shieldedEnabled = !shieldedEnabled;
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
            else
                UpdateRate();
            SetGui();
        }

        // Editor and flight: shut the avionics down / bring it back up. Guarded on CanHibernate (Guided only;
        // Unshielded needs index 9, Shielded is available from its own first tier).
        [KSPEvent(guiActive = true, guiActiveEditor = true, guiName = "Shutdown Avionics", groupName = PAWGroup, groupDisplayName = GroupDisplay)]
        public void ToggleHibernation()
        {
            if (!CanHibernate) return;
            hibernating = !hibernating;
            // Shutting down removes this core from EffectiveCapacityTons, which moves the vessel-wide
            // steerable-mass MAX -- so EVERY other core's penalty has to be recomputed, not just this one's.
            // In the editor onEditorShipModified re-runs the whole ship; in flight the 1 Hz Update() tick
            // and the controller's onVesselWasModified handler both pick it up.
            if (HighLogic.LoadedSceneIsEditor && EditorLogic.fetch?.ship != null)
                GameEvents.onEditorShipModified.Fire(EditorLogic.fetch.ship);
            else
                UpdateRate();
            if (vessel != null) GameEvents.onVesselWasModified.Fire(vessel);
            SetGui();
        }

        [KSPAction("Toggle Avionics")]
        public void HibernateAction(KSPActionParam _) => ToggleHibernation();

        // RP-1 pairs the toggle with two one-way actions, so an avionics state change can be dropped into a
        // staging sequence without depending on what the state happens to be when the stage fires.
        [KSPAction("Shutdown Avionics")]
        public void ShutdownAction(KSPActionParam _) { if (!hibernating) ToggleHibernation(); }

        [KSPAction("Activate Avionics")]
        public void ActivateAction(KSPActionParam _) { if (hibernating) ToggleHibernation(); }

        // ---- IPartMassModifier: the frozen hardware mass (battery mass is RealFuels') ----
        public float GetModuleMass(float defaultMass, ModifierStagingSituation sit) => avionicsMass;
        public ModifierChangeWhen GetModuleMassChangeWhen() => ModifierChangeWhen.CONSTANTLY;

        // ---- IPartCostModifier: the frozen hardware cost (battery funds cost is RealFuels') ----
        public float GetModuleCost(float defaultCost, ModifierStagingSituation sit) => avionicsCost;
        public ModifierChangeWhen GetModuleCostChangeWhen() => ModifierChangeWhen.CONSTANTLY;

        public override string GetInfo()
        {
            return "Unified avionics core: command, guidance, electric power, science storage and flight computer.\n\n"
                 + "<b>Model</b> (chosen in the VAB, fixed at launch):\n"
                 + "• <b>Guided</b> — full 3-axis control; size the box's hardware segment for the vessel "
                 + "mass you want to steer (shown as Capacity). Going over capacity doesn't lock control, it "
                 + "costs a smoothly rising power penalty instead. Needs the guidance tech to steer; until "
                 + "then the craft flies dumb.\n"
                 + "• <b>Unguided</b> — no steering, but a fraction of the mass and almost no power; "
                 + "from improved avionics it permits axial-thrust spin-stabilization.\n\n"
                 + "<b>Shielded</b> (Guided only, unlocked later): its own heavier/pricier hardware ladder, "
                 + "in exchange for being able to shut down from its own first tier, and more deeply — "
                 + "Unshielded only earns a shallower shutdown late in the ladder.\n\n"
                 + "A crewed pod or a separate probe core always restores full control regardless of model.\n\n"
                 + "<b>Power draw</b> runs live off the vehicle's <i>dry</i> mass, drawn through the vessel's "
                 + "normal electric charge system — an empty battery loses control the same way it would for "
                 + "any uncrewed probe. Draw auto-drops during timewarp for any core that can shut down.\n\n"
                 + "<b>Shutdown Avionics</b> (in the VAB or in flight, once the ladder unlocks it): powers the "
                 + "unit down to a fraction of its draw and takes it out of the vessel's steerable-mass "
                 + "budget entirely — it stops steering, stops counting, and stops being charged for "
                 + "overload. Command, staging and throttle keep working. Build an upper stage's avionics "
                 + "shut down and switch it on after separation, or bind it to a staging action group.\n\n"
                 + "<b>Battery/hardware/empty split</b>: drag the bar in the Avionics Core PAW section to "
                 + "divide the box's volume between battery and hardware; the rest is legitimately unused.\n\n"
                 + "<b>Set to Debris</b>: mark a stage's avionics so, once it separates, an otherwise-idle "
                 + "spent stage doesn't clutter the tracking station.\n\n"
                 + "<b>Science storage</b> is unlocked from Basic Avionics on; earlier tiers are pure "
                 + "sequencers with no onboard data storage.";
        }

        #region Kerbalism (duck-typed; invoked by reflection only if Kerbalism is present)
        public string PlannerUpdate(List<KeyValuePair<string, double>> resources, CelestialBody _, Dictionary<string, double> environment)
        {
            resources.Add(_ecConsumption);
            return "avionics";
        }

        public string ResourceUpdate(Dictionary<string, double> availableResources, List<KeyValuePair<string, double>> resourceChangeRequest)
        {
            resourceChangeRequest.Add(_ecConsumption);
            return "avionics";
        }

        public static string BackgroundUpdate(Vessel v,
            ProtoPartSnapshot partSnapshot, ProtoPartModuleSnapshot moduleSnapshot,
            PartModule protoPartModule, Part protoPart,
            Dictionary<string, double> availableResources, List<KeyValuePair<string, double>> resourceChangeRequest,
            double elapsed_s)
        {
            if (availableResources.ContainsKey(EcName))
            {
                float cw = 0f;
                if (moduleSnapshot.moduleValues.TryGetValue("currentWatts", ref cw) && cw > 0f)
                    resourceChangeRequest.Add(new KeyValuePair<string, double>(EcName, -cw / 1000.0));
            }
            return "avionics";
        }
        #endregion
    }
}
