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
    /// MASS RULE — applies to BOTH module types now. Every unit that provides guidance contributes its
    /// capacity to one vessel-wide MAX and is judged against it, procedural or named alike. The old split
    /// (procedural cores answered overload in watts, named parts locked) is gone: the EC penalty it rested
    /// on was proven inert against a ~39-hour battery in a 6-10 minute ascent, and its two recorded
    /// justifications both collapsed — the exp(80) hazard was removed by its own cap 19 hours after it was
    /// written, and "a fixed part has no sizing decision to get wrong" is false, since r = mass/capacity has
    /// two terms and the player sets both (choosing a 0.875 t Voyager bus for a 2 t spacecraft is a sizing
    /// decision made in the VAB).
    ///
    /// What happens over capacity is now a selectable <see cref="AxeControlPenalty"/> — including
    /// <see cref="PenaltyLock"/>, which reproduces RP-1's original rule exactly. See docs/AVIONICS_PLAN.md.
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
        // k is ANCHORED, not tuned: it falls out of one design statement -- "at 20% over its rated mass a
        // unit is hopeless" -- i.e. sigma(1.2) = 0.9, which solves to k = 11.5. Argue about the sentence,
        // not the number.
        //   2% over -> 0.21    5% -> 0.44    10% -> 0.68    15% -> 0.82    20% -> 0.90
        // A deliberately narrow tolerance band: a few percent of grace, then it goes away fast. Rated
        // capacity is close to a hard constraint, which is how real vehicles treat their control design
        // margin -- nobody flies 20% over what the control system was characterised for.
        public static float NoiseK = 11.5f;

        // Ceiling defaults to 1 = OFF. sigma = 1 - e^(-k(r-1)) already asymptotes to 1, which is the natural
        // saturation (the command is fully swamped), so a separate cap was capping a curve that caps itself.
        // Kept only as a debug knob.
        public static float NoiseMax = 1f;

        // C in Hz = C / mass^(1/3). NOT a frequency itself -- see HzForMass.
        public static float NoiseHz = 2f;
        public static bool NoiseHzAutoScale = true;
        public static float EffectiveNoiseHz = 2f;   // set per-vessel by the controller

        // A FIXED frequency cannot be right for both a 5 t probe and a 300 t launcher: the vehicle low-passes
        // the noise according to its own rotational response, so a big stack filters 2 Hz heavily while a
        // small probe barely does. Perturbing each vehicle at its OWN response frequency is what makes the
        // effect comparable across sizes instead of accidentally tuned to whatever was last flown.
        //
        // Rigid-body attitude response time scales with linear dimension: I ~ m*L^2 and torque roughly ~ m,
        // so timescale ~ L and natural frequency ~ 1/L ~ m^(-1/3). At C = 2 a 1 t probe gets 2 Hz and a 100 t
        // stack gets 0.43 Hz.
        public static float HzForMass(float massTons)
            => NoiseHzAutoScale ? NoiseHz / Mathf.Pow(Mathf.Max(0.1f, massTons), 1f / 3f) : NoiseHz;
        public static bool NoiseWhite;        // white instead of correlated: tests the inertia-filter theory
        public static bool NoiseRoll = true;  // roll is the most perceptible axis; separable for that reason
        public static bool NoiseOnRcs = true;

        // ADDITIVE vs ON-INPUT. Defaults to ON-INPUT. The deciding argument turned out not to be the fiction
        // but signal-to-noise: RCS was reported unusable at any sigma, and that is not an inertia problem, it
        // is a SMALL-COMMAND problem. Docking uses commands around 0.05, so additive noise of +/-0.3 is six
        // times the signal and the input is pure garbage; RCS is simply where small commands live. Scaling
        // the command instead preserves the ratio at any magnitude -- 0.05 becomes 0.035-0.065, degraded
        // rather than destroyed -- which removes the need for a separate RCS scale.
        //
        // The fiction argument (real rockets fly themselves, so the program should be corrupted even with no
        // pilot input) is still true but weaker, and mostly moot: MechJeb and SAS command continuously during
        // any active flight, so on-input noise still fires. The only time it does not is when nothing is
        // flying, which is exactly when nothing should be corrupted.
        //
        // Two genuinely different mechanics, not two tunings of one:
        //   additive  -- noise is added regardless of what the pilot commands, so a craft wanders on its own.
        //                Reads as a vehicle that will not sit still.
        //   on-input  -- noise SCALES the command, so a null stick stays null and only what you ask for comes
        //                out wrong. Reads as controls you cannot trust. No uncommanded drift.
        // The second is the better fit for "the computer is mis-executing your guidance", the first for "the
        // loop is unstable". Which one is right is a feel question, hence the toggle.

        // RCS was reported unusable at any penalty: thrusters respond instantly and have no inertia to filter
        // anything, so the same sigma that gently wallows a launch vehicle makes fine attitude work
        // impossible and burns monopropellant doing it. Scaled separately rather than just on/off.
        public static float NoiseRcsScale = 1f;   // on-input mode preserves small commands, so no longer needs cutting

        // Kept only so the two can be compared in flight. Off by default -- see the note at the cutoff site.
        public static bool HardCutoff = false;

        // ---- MODE 2: OVERGAIN ---------------------------------------------------------------------
        // Models the failure mechanism instead of its symptom. An undersized control system does not make
        // RANDOM errors -- it has TOO MUCH GAIN for the vehicle it is flying. Insufficient phase margin,
        // unfiltered bending modes, overcontrol. That is what the first flight already showed from the other
        // side: cutting gimbal authority flew BETTER, because it raised the stability margin.
        //
        // Why it should beat noise, and this is the whole argument: a feedback loop is DESIGNED to reject
        // disturbances -- that is its job -- so injected noise gets averaged out, which is exactly what
        // happened to the authority scalar. Gain is not a disturbance. It modifies the PLANT the controller
        // is closing around, so the controller's own corrections are amplified too. It cannot counter-steer
        // its way out, because the counter-steer is also too big. Past the loop's gain margin it oscillates
        // by itself, with no randomness supplied by us.
        //
        // Consequences that fall out for free:
        //   * the oscillation FREQUENCY emerges from the vehicle's own dynamics, so no Hz parameter and no
        //     m^(-1/3) scaling law is needed at all;
        //   * it saturates the command SOONER rather than being clipped by the clamp, so unlike additive and
        //     on-input it does not go soft exactly when the vehicle is working hardest;
        //   * it is deterministic, so NoiseHz / white / correlated have no effect in this mode.
        //
        // Anchored on the same sentence as k. Typical loop gain margin is 2-4x, so G = 3 should push most
        // controllers unstable: G(1.2) = 3 gives slope 10.
        public static float OvergainSlope = 10f;

        // sigma = 1 - e^(-k(r-1)) inverted, so gain can be derived from sigma without plumbing the ratio
        // through -- and so the DEBUG pin drives overgain consistently with the other two modes.
        public static float RatioFromSigma(float sigma)
            => 1f + (-Mathf.Log(Mathf.Max(1e-4f, 1f - sigma)) / Mathf.Max(0.01f, NoiseK));

        public static float GainFor(float sigma)
            => sigma <= 0f ? 1f : 1f + OvergainSlope * DriftFor(0) * (RatioFromSigma(sigma) - 1f);

        // ---- MODE 3: CROSS-AXIS COUPLING ----------------------------------------------------------
        // Commanding one axis bleeds into the others. A feedback loop closes each axis assuming they are
        // independent, so correcting the induced yaw induces pitch, correcting that induces roll: the loop
        // ends up fighting itself rather than fighting us. That is an attack on the DECOUPLING assumption,
        // the third of the three ways to destabilise a loop (gain margin, phase margin, coupling) -- and
        // like the other two it is not a disturbance, so there is nothing to average out.
        //
        // Physically this is what a control system that was never characterised for its vehicle looks like:
        // misaligned IMU axes, gimbal cross-talk, a decoupling matrix nobody tuned.
        //
        // Coefficients are FIXED PER VESSEL, not re-rolled. That makes it a systematic misalignment -- this
        // particular rocket pulls left when you pitch up -- which is learnable, and reads as a characteristic
        // of the vehicle rather than as random malfunction. Inherits on-input's best property for free: it
        // is proportional to command, so no uncommanded drift and small commands stay proportionally intact.
        static int _coupleSeed = int.MinValue;
        static readonly float[] _cc = new float[6];

        public static void SeedCoupling(int seed)
        {
            if (seed == _coupleSeed) return;
            _coupleSeed = seed;
            System.Random rng = new System.Random(seed);
            for (int i = 0; i < 6; i++) _cc[i] = (float)(rng.NextDouble() * 2.0 - 1.0);
        }

        public static void ApplyCoupling(ref float pitch, ref float yaw, ref float roll, float sigma)
        {
            float p0 = pitch, y0 = yaw, r0 = roll;
            pitch = Mathf.Clamp(p0 + sigma * (_cc[0] * DriftFor(0) * y0 + _cc[1] * DriftFor(1) * r0), -1f, 1f);
            yaw   = Mathf.Clamp(y0 + sigma * (_cc[2] * DriftFor(2) * p0 + _cc[3] * DriftFor(3) * r0), -1f, 1f);
            roll  = Mathf.Clamp(r0 + sigma * (_cc[4] * DriftFor(4) * p0 + _cc[5] * DriftFor(5) * y0), -1f, 1f);
        }

        // ---- MODE 7: RANDOM DROPOUTS -------------------------------------------------------------
        // The answer to "anything that is not random can be learned by the player and by MechJeb".
        //
        // Every other candidate fails one of two tests. Deterministic ones (overgain, coupling, delay) are
        // LEARNABLE -- MechJeb has adaptive gain, a player just flies gently, and in a mod where the
        // autopilot flies the ascent "learnable" means learned by software in seconds. Random ones (both
        // noise modes) are REJECTABLE, because rejecting disturbances is exactly what a feedback loop is
        // for. Deterministic gets learned; random gets averaged out.
        //
        // Dropouts escape both by randomising AVAILABILITY rather than VALUE. A loop rejects a disturbance
        // by commanding against it -- which assumes it can command at all. During a dropout there is
        // nothing to reject and nothing to command with; the loop integrates up blind and then
        // over-corrects when control returns. And the timing is random, so it cannot be anticipated.
        //
        // It is also the better fiction: an overloaded flight computer MISSES CYCLES. Not wrong output --
        // no output. That is literally what insufficient throughput does.
        //
        // ZERO-ORDER HOLD, not zeroing. When no new command arrives an actuator keeps its last position,
        // which is both the correct model and the more interesting failure: the vehicle carries on doing
        // whatever it was doing, so a dropout mid-correction over-rotates rather than merely pausing.
        //
        // Bursts, not per-tick coin flips: per-tick randomness is averaged away by vessel inertia, the same
        // trap that made white noise invisible. Gap length is solved so the long-run duty cycle equals
        // sigma -- at sigma 0.05 that is a ~120 ms dropout every ~2.3 s, at 0.5 it is half the time.
        public static float DropoutMs = 120f;
        static int _dropTicksLeft;
        static float _holdP, _holdY, _holdR;

        public static void ResetDropout() { _dropTicksLeft = 0; }

        public static void ApplyDropout(ref float pitch, ref float yaw, ref float roll, float sigma)
        {
            float dt = Time.fixedDeltaTime > 0f ? Time.fixedDeltaTime : 0.02f;
            int lenTicks = Mathf.Max(1, Mathf.RoundToInt((DropoutMs / 1000f) / dt));

            if (_dropTicksLeft > 0)
            {
                _dropTicksLeft--;
                pitch = _holdP; yaw = _holdY; roll = _holdR;
                return;
            }

            float duty = Mathf.Clamp(sigma, 0f, 0.95f);
            float gapTicks = lenTicks * (1f - duty) / Mathf.Max(0.0001f, duty);
            if (Random.value < 1f / Mathf.Max(1f, gapTicks))
            {
                _dropTicksLeft = lenTicks;   // hold values already captured below on the previous tick
                pitch = _holdP; yaw = _holdY; roll = _holdR;
                return;
            }

            _holdP = pitch; _holdY = yaw; _holdR = roll;
        }

        // ---- DRIFT: make the deterministic attacks non-stationary ---------------------------------
        // The other escape from "deterministic gets learned". Overgain and coupling are learnable only
        // because their parameters are FIXED; a slow random walk means adaptive tuning is always chasing a
        // target that has moved. Very low frequency (~20 s period) so it reads as a system that will not
        // settle rather than as noise.
        public static bool NoiseDrift;
        public static float DriftHz = 0.05f;

        public static float DriftFor(int idx)
            => NoiseDrift ? 0.5f + Mathf.PerlinNoise(Time.time * DriftHz, idx * 13.1f) : 1f;

        // ---- MODE 4: TRANSPORT DELAY --------------------------------------------------------------
        // Hold the command for N physics ticks, N rising with overload. Pure delay is the classic loop
        // killer: it eats PHASE margin, and unlike gain there is nothing a fixed-gain controller can do
        // about it at all. 100-200 ms of unexpected lag destabilises most controllers, and at KSP's 50 Hz
        // that is only 5-10 ticks.
        //
        // Expected to be the sharpest of the five and quite possibly a cliff wearing a gradient's clothes.
        // Built to find out rather than because it is predicted to win.
        const int DelayBufferMax = 64;
        static readonly float[] _dp = new float[DelayBufferMax];
        static readonly float[] _dy = new float[DelayBufferMax];
        static readonly float[] _dr = new float[DelayBufferMax];
        static int _dIdx;
        public static float DelayTicksMax = 10f;   // at sigma = 1, in 50 Hz physics ticks

        public static void ResetDelay()
        {
            System.Array.Clear(_dp, 0, DelayBufferMax);
            System.Array.Clear(_dy, 0, DelayBufferMax);
            System.Array.Clear(_dr, 0, DelayBufferMax);
            _dIdx = 0;
        }

        public static void ApplyDelay(ref float pitch, ref float yaw, ref float roll, float sigma)
        {
            int n = Mathf.Clamp(Mathf.RoundToInt(DelayTicksMax * sigma), 0, DelayBufferMax - 1);
            _dp[_dIdx] = pitch; _dy[_dIdx] = yaw; _dr[_dIdx] = roll;
            int read = (_dIdx - n + DelayBufferMax) % DelayBufferMax;
            _dIdx = (_dIdx + 1) % DelayBufferMax;
            if (n == 0) return;
            pitch = _dp[read]; yaw = _dy[read]; roll = _dr[read];
        }

        // Mode selection now lives in AxeControlPenalties; these helpers stay as the shared maths the
        // individual penalties call into.


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
                : Mathf.Clamp((Mathf.PerlinNoise(Time.time * EffectiveNoiseHz, axis * 37.7f) * 2f - 1f) * PerlinGain, -1f, 1f);
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

        // A4. Mass this vessel would have with every tank full. The KSP editor shows tanks full by default,
        // so the configured figure is normally already the worst case -- but a player who deliberately
        // EMPTIES tanks to launch light and refuel on site (or assembles in orbit, or launches dry) gets a
        // warning computed against a craft that never flies. One extra line closes that generally, with no
        // ISRU-specific machinery.
        public static float FullTankMassTons(List<Part> parts)
        {
            if (parts == null) return 0f;
            float t = 0f;
            for (int i = 0; i < parts.Count; i++)
            {
                Part p = parts[i];
                if (p == null) continue;
                t += p.mass + p.GetModuleMass(p.mass);
                for (int j = 0; j < p.Resources.Count; j++)
                {
                    PartResource r = p.Resources[j];
                    if (r?.info == null) continue;
                    t += (float)(r.maxAmount * r.info.density);
                }
            }
            return t;
        }

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
                noise = NoiseFor(ratio);

                // PenaltyLock is RP-1's original rule as a selectable option: over capacity locks outright
                // instead of degrading. Kept both as the A/B baseline and as the fallback if no perturbation
                // survives testing, so choosing it needs no code change.
                if (AxeControlPenalties.Current.LocksInstead)
                    return (coreAxial || fixedAxial) ? LockLevel.Axial : LockLevel.Locked;

                // NO CUTOFF by default. A hard flip to unguided past some ratio is the same arbitrary cliff
                // this design exists to remove, just relocated -- and it is redundant, because the noise
                // curve already asymptotes to unusable: at sigma near 1 the command is close to random, so
                // the vehicle cannot be flown regardless. The limit enforces itself, continuously, and the
                // only thing a threshold adds is a jarring change to a DIFFERENT failure mode at a number
                // nothing physical picked.
                //
                // Discrete "unguided" survives only where it is a PROPERTY OF THE PART rather than a
                // threshold crossing: an Unguided/Science-Core core, a capacity-0 named part, or no avionics
                // at all. Those fall through below with maxCapacity == 0 and are unaffected.
                if (!HardCutoff || ratio < RatioCut) return LockLevel.Unlocked;
            }
            return (coreAxial || fixedAxial) ? LockLevel.Axial : LockLevel.Locked;
        }

        static bool IsValidCommand(ModuleCommand mc) =>
            mc.ModuleState == ModuleCommand.ModuleControlState.Nominal ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialProbe ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialManned;
    }
}
