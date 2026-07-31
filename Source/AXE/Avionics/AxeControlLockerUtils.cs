using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Decides whether a vessel's ATTITUDE control should be locked (the "dumb rocket" state).
    ///
    /// Three control levels (mirrors RP-1's LockLevel):
    ///   * Unlocked — full control, when any of: a crewed command part, a procedural Avionics Core with
    ///     guidance active, or a fixed-capacity unit rated for at least the vessel's mass.
    ///   * Axial    — axial-thrust only (rotation locked), when the only guidance available is axial:
    ///     a Science-Core whose tier permits axial thrust, or an over-capacity fixed unit with allowAxial
    ///     (both are the spin-stabilized kick-stage case).
    ///   * Locked   — fully dumb (throttle + staging only), otherwise.
    ///
    /// MASS RULE — applies to FIXED-capacity units only (<see cref="ModuleAxeFixedAvionics"/>), not to the
    /// procedural core. The procedural core deliberately has no mass gate: the player sizes its box, and
    /// going over its capacity costs a smooth EC-draw penalty rather than a lock, so a slightly-undersized
    /// box degrades instead of bricking the flight (docs/AVIONICS_SPEC.md). A fixed unit has no sizing
    /// decision to get wrong — its capacity is authored hardware — so it uses RP-1's original rule, which
    /// is both more faithful and far more legible than routing it through the penalty curve (a capacity-0
    /// part on the penalty path would draw exp(80) watts, flatten the battery and drop ModuleCommand
    /// altogether, losing staging and throttle too — RP-1 kept those and locked only attitude).
    ///
    /// Vessel mass is whole-vessel WET mass (part.mass + part.resourceMass), and the budget is the MAX
    /// across parts, never the sum — RP-1's own anti-cheese rule, matching the procedural core's
    /// EffectiveCapacityTons(). Bolting on a second bus does not double what you can steer.
    ///
    /// Launch clamps are excluded from vessel mass while in the editor or on the pad, and never grant the
    /// bypass, so a pad structure that happens to carry a ModuleCommand (the ModularLaunchPads stands all
    /// do) can neither make a rocket controllable nor eat its mass budget. RP-1 also zeroed parts tagged
    /// HasPadInfrastructure; AXE cut ModuleTagList entirely (design/StripAxedRP1Modules.cfg), so the clamp
    /// check is the whole of it here.
    ///
    /// Adapted from RP-1 ControlLockerUtils.ShouldLock.
    /// </summary>
    public static class AxeControlLockerUtils
    {
        public enum LockLevel { Locked, Axial, Unlocked }

        // ---- PROTOTYPE v2: control NOISE (docs/AVIONICS_AUTHORITY.md) -----------------------------
        // v1 scaled control authority down and was killed by test: at q=0.05 a medium craft ascended
        // normally, and flew BETTER, because reducing loop gain raises stability margin. Weakness is
        // the opposite of how an under-characterised control system actually fails.
        //
        // Noise is the version that survives that result. An autopilot can correct the AVERAGE of a
        // disturbance but cannot anticipate it, so unlike a gain change there is nothing to absorb.
        // It also matches the physical story: avionics sized for a vehicle means a control law
        // characterised for its bending modes and slosh; undersized, the loop is mistuned and the
        // vehicle jitters.
        //
        // TWO DESIGN POINTS DECIDE WHETHER THIS WORKS AT ALL, both learned from v1's failure:
        //   * Noise is a fraction of the CONTROL RANGE, not an absolute torque. A rocket with strong
        //     gimbals therefore gets strongly perturbed; otherwise big vehicles ignore it exactly as
        //     they ignored the authority cut.
        //   * Noise is LOW-FREQUENCY (correlated, ~NoiseHz). White noise per physics tick is averaged
        //     away by vessel rotational inertia and would be invisible on anything heavy.
        // All tunables are STATIC AND LIVE, driven from the core's DEBUG PAW knobs, so they can be changed
        // in flight without a rebuild. That is the whole point of the prototype: none of these numbers has a
        // physical anchor (KSP models no bending modes), so they can only be found by feel.
        public static float NoiseK = 2f;      // how fast noise ramps with overload
        public static float NoiseMax = 0.9f;  // ceiling, as a fraction of control range
        public static float NoiseHz = 2f;     // correlation frequency -- THE critical one, see above
        public static bool NoiseWhite;        // white instead of correlated: tests the inertia-filter theory
        public static bool NoiseRoll = true;  // roll is the most perceptible axis; separable for that reason
        public static bool NoiseOnRcs = true;

        public static float RatioCut => 1f + Mathf.Log(1f / Mathf.Max(0.01f, 1f - NoiseMax)) / NoiseK;

        /// <summary>Noise amplitude as a fraction of control range: 0 under capacity, rising with overload.</summary>
        public static float NoiseFor(float ratio)
            => ratio <= 1f ? 0f : Mathf.Min(NoiseMax, 1f - Mathf.Exp(-NoiseK * (ratio - 1f)));

        // Unity's Perlin is bell-shaped, not uniform: it clusters near 0.5 and rarely approaches 0 or 1, so
        // mapped to +/-1 its RMS is about 0.2-0.3 against uniform white's 0.577. Without this gain the
        // white/correlated toggle compares LOUDNESS rather than frequency content, and white looks worse for
        // the wrong reason. Roughly RMS-matched, then clamped.
        const float PerlinGain = 2.4f;

        /// <summary>Noise sample in [-sigma, sigma] for one control axis.</summary>
        public static float NoiseSample(int axis, float sigma)
        {
            if (sigma <= 0f) return 0f;
            float n = NoiseWhite
                ? Random.Range(-1f, 1f)
                : Mathf.Clamp((Mathf.PerlinNoise(Time.time * NoiseHz, axis * 37.7f) * 2f - 1f) * PerlinGain, -1f, 1f);
            return n * sigma;
        }

        // PROTOTYPE TEST RIG. Pins q to a chosen value and keeps the vessel flyable, so the SAME craft can
        // be flown the SAME profile at several values -- which is the only way to answer the question the
        // prototype exists for: does an autopilot simply absorb the reduction? A nominal gravity turn needs
        // a fraction of the available control authority, so MechJeb can be expected to compensate until it
        // saturates; if the traces at 1.0 / 0.6 / 0.35 are indistinguishable, the degraded band does not
        // exist in practice and no value of k will create it. Driven from the core's DEBUG PAW fields.
        public static bool NoiseOverrideEnabled;
        public static float NoiseOverrideValue = 0f;

        public static LockLevel ShouldLock(List<Part> parts) => ShouldLock(parts, out _, out _, out _);

        public static LockLevel ShouldLock(List<Part> parts, out float maxCapacity, out float vesselMass)
            => ShouldLock(parts, out maxCapacity, out vesselMass, out _);

        /// <param name="maxCapacity">Steerable-mass budget: MAX across ALL avionics units, in tons.</param>
        /// <param name="vesselMass">Whole-vessel wet mass measured against it, in tons.</param>
        /// <param name="noise">Control-noise amplitude in [0..NoiseMax]; 0 unless over capacity.</param>
        public static LockLevel ShouldLock(List<Part> parts, out float maxCapacity, out float vesselMass,
                                           out float noise)
        {
            noise = 0f;
            maxCapacity = 0f;
            vesselMass = 0f;
            if (parts == null || parts.Count == 0) return LockLevel.Unlocked;
            if (!HighLogic.LoadedSceneIsFlight && !HighLogic.LoadedSceneIsEditor) return LockLevel.Unlocked;

            Vessel vessel = parts[0].vessel;
            if (vessel != null && vessel.isEVA) return LockLevel.Unlocked;

            // Clamps only count as clamps in the editor or on the pad; once flying they are long gone.
            bool ignoreClamps = !HighLogic.LoadedSceneIsFlight
                                || vessel == null
                                || vessel.situation == Vessel.Situations.PRELAUNCH;

            bool bypass = false;      // a non-avionics command source grants control outright
            // (was `coreGuided`: a guided core used to grant full control outright, with no mass term. Under
            // the authority model it contributes capacity instead and is judged on r, so the flag is gone.)
            bool coreAxial = false;   // a Science-Core Avionics Core grants axial-thrust-only control
            bool fixedAxial = false;  // a fixed unit that keeps axial thrust when over capacity

            foreach (Part p in parts)
            {
                bool isCore = false;
                bool guided = false;
                bool axial = false;
                bool cmd = false;
                bool isClamp = false;
                bool hasFixed = false;
                float partCapacity = 0f;
                float partMass = p.mass + p.resourceMass;

                foreach (PartModule m in p.Modules)
                {
                    if (m is ModuleAxeAvionics axe)
                    {
                        isCore = true;
                        // PROTOTYPE: a guided core now CONTRIBUTES ITS CAPACITY instead of unlocking the
                        // vessel outright. It used to short-circuit to Unlocked with no mass term at all,
                        // because overload was answered in watts; under the authority model it is judged on
                        // r like every other unit. Still gated on GuidanceActive -- an un-researched or
                        // shut-down core provides no control, which is a separate concern from whether its
                        // rated mass counts toward the EC curve (see EffectiveCapacityTons, deliberately
                        // ungated there since 17009ce).
                        if (axe.GuidanceActive) { guided = true; partCapacity += axe.capacityTons; }
                        if (axe.AxialActive) axial = true;
                    }
                    else if (m is ModuleAxeFixedAvionics fix)
                    {
                        isCore = true;
                        hasFixed = true;
                        partCapacity += fix.CapacityTons;   // summed within a part, MAX across parts
                        if (fix.allowAxial) fixedAxial = true;
                    }
                    else if (m is ModuleCommand mc && (IsValidCommand(mc) || HighLogic.LoadedSceneIsEditor))
                    {
                        cmd = true;
                    }
                    else if (m is LaunchClamp)
                    {
                        isClamp = true;
                    }
                }

                if (isClamp && ignoreClamps) partMass = 0f;
                vesselMass += partMass;

                if (isCore && axial) coreAxial = true;
                // PROTOTYPE: was `hasFixed &&` -- procedural cores now feed the same MAX.
                if ((hasFixed || guided) && partCapacity > maxCapacity) maxCapacity = partCapacity;
                // crewed pod OR a probe core with no avionics at all (an avionics unit's own command never
                // bypasses; neither does a launch clamp's, or every pad stand would unlock the rocket).
                if (cmd && !isCore && !isClamp) bypass = true;
            }

            // PROTOTYPE TEST RIG: pin q and stay flyable, so one craft can be flown at several values.
            // Placed after the part walk so maxCapacity/vesselMass are still reported honestly.
            if (NoiseOverrideEnabled)
            {
                noise = Mathf.Clamp(NoiseOverrideValue, 0f, 1f);
                return LockLevel.Unlocked;
            }

            // A crewed pod / bare command source still bypasses everything, unconditionally (RP-1's rule).
            if (bypass) return LockLevel.Unlocked;

            // PROTOTYPE: the degraded band. Under capacity, clean control. Over it the craft still steers
            // but its control inputs are corrupted by noise rising with overload, up to RatioCut -- past
            // that it hands over to the existing ladder and is genuinely unguided. `coreGuided` no longer
            // short-circuits: a guided core is judged on mass like everything else.
            if (maxCapacity > 0f)
            {
                float ratio = vesselMass / maxCapacity;
                if (ratio <= 1f) return LockLevel.Unlocked;
                if (ratio < RatioCut)
                {
                    noise = NoiseFor(ratio);
                    return LockLevel.Unlocked;   // still controllable, just dirtily
                }
            }
            return (coreAxial || fixedAxial) ? LockLevel.Axial : LockLevel.Locked;
        }

        static bool IsValidCommand(ModuleCommand mc) =>
            mc.ModuleState == ModuleCommand.ModuleControlState.Nominal ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialProbe ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialManned;
    }
}
