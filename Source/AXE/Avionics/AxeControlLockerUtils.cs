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
    /// OVER CAPACITY NEVER LOCKS. RP-1's rule (over capacity = attitude locked outright) was one of eleven
    /// candidate consequences flown against each other in Phase D; the one that shipped is ADVERSARIAL
    /// REGIME MATCHING, below — the craft keeps control and the command is corrupted by the move that beats
    /// whatever the pilot is currently doing. The losing ten are deleted rather than parked behind a knob.
    /// Discrete "unguided" survives only where it is a PROPERTY OF THE PART (an Unguided/Science-Core core, a
    /// capacity-0 named part, or no avionics at all), never as a threshold crossing. See docs/AVIONICS_PLAN.md.
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

        // ALL THREE AXES. Roll was separable while the modes were being compared -- it is by far the most
        // perceptible axis, so "is roll alone carrying the whole feel?" was worth being able to answer. It
        // is answered; roll is degraded like the other two and the switch is gone.

        // WHY EXACTLY ONE MOVE IS ADDITIVE. Additive noise on a command that is already small is not
        // degradation, it is replacement: docking runs commands around 0.05, so +/-0.3 of noise is six times
        // the signal and the input becomes garbage rather than degraded -- which is what made an
        // additive-everywhere mode unusable on RCS, where small commands live. Every other move here is
        // proportional to the command or is a pure time shift, so it preserves the ratio at any magnitude.
        // The DRIFT cell is additive deliberately, and it is the only one: it is selected precisely when
        // there is no command to be proportional TO, it is the one mechanic that still bites a null stick,
        // and that is the whole answer to "fly gently and you are safe".

        // ---- MOVE: OVERGAIN -----------------------------------------------------------------------
        // Models the failure mechanism instead of its symptom. An undersized control system does not make
        // RANDOM errors -- it has TOO MUCH GAIN for the vehicle it is flying. Insufficient phase margin,
        // unfiltered bending modes, overcontrol. That is what the first flight already showed from the other
        // side: cutting gimbal authority flew BETTER, because it raised the stability margin.
        //
        // Why it beats a disturbance, and this is the whole argument: a feedback loop is DESIGNED to reject
        // disturbances -- that is its job -- so injected noise gets averaged out, which is exactly what
        // happened to the authority scalar. Gain is not a disturbance. It modifies the PLANT the controller
        // is closing around, so the controller's own corrections are amplified too. It cannot counter-steer
        // its way out, because the counter-steer is also too big. Past the loop's gain margin it oscillates
        // by itself, with no randomness supplied by us.
        //
        // Consequences that fall out for free:
        //   * the oscillation FREQUENCY emerges from the vehicle's own dynamics, so no Hz parameter and no
        //     m^(-1/3) scaling law is needed for this move;
        //   * it saturates the command SOONER rather than being clipped by the clamp, so unlike the additive
        //     drift move it does not go soft exactly when the vehicle is working hardest;
        //   * it is deterministic, so NoiseHz / white / correlated have no effect on it.
        // Which is also why the policy places it in a cell where commands are SMALL: amplification needs
        // headroom below the clamp, and a x3 on 0.3 is a different event from a x3 on 0.9.
        //
        // Anchored on the same sentence as k. Typical loop gain margin is 2-4x, so G = 3 should push most
        // controllers unstable: G(1.2) = 3 gives slope 10.
        public static float OvergainSlope = 10f;

        // sigma = 1 - e^(-k(r-1)) inverted, so gain can be derived from sigma without plumbing the ratio
        // through -- and so the DEBUG pin drives the overgain cell consistently with the rest.
        public static float RatioFromSigma(float sigma)
            => 1f + (-Mathf.Log(Mathf.Max(1e-4f, 1f - sigma)) / Mathf.Max(0.01f, NoiseK));

        public static float GainFor(float sigma)
            => sigma <= 0f ? 1f : 1f + OvergainSlope * DriftFor(0) * (RatioFromSigma(sigma) - 1f);

        // ================ THE MECHANIC: ADVERSARIAL REGIME MATCHING ================================
        // THE ONE THAT SHIPPED. Ten other consequences were built and flown against it (EC drain, authority
        // scaling, RP-1's outright lock, two noise modes, coupling, misdirect, dropouts, plain overgain, and
        // overgain scheduled on the loop's own effort); this is what survived, and the losers are deleted.
        //
        // The defect that killed the closest rival, and the reason this shape exists: gain scheduled on
        // effort is MONOTONE in effort, so "minimise effort" is a dominant strategy and the mechanic has a
        // loophole rather than a cost. A penalty with a dominant escape is not adversarial, it is a tax you
        // can route around. The fix is not a deeper penalty, it is to make every escape the ENTRANCE TO
        // ANOTHER ATTACK.
        //
        // So this adds no new corruption of its own. It is a POLICY over mechanics that already existed, and
        // the candidates that lost as modes stop being competitors and become its move set.
        //
        // The command is split into the two things it can be -- a sustained part (the EMA, m) and a
        // transient part (c - m) -- and each attack is placed where ITS OWN effect is largest:
        //
        //                    | not moving it        | moving it
        //   -----------------+----------------------+-------------------
        //   holding little   | UNCOMMANDED          | OVERGAIN
        //   holding a lot    | WASHOUT              | DELAY
        //
        //   * UNCOMMANDED for the empty cell, and this is the whole answer to "fly gently and you are
        //     safe": the counter to minimal input is the one mechanic that does not read input at all.
        //   * OVERGAIN where commands are SMALL -- amplification needs headroom below the clamp, and a
        //     x3 on 0.3 is a different event from a x3 on 0.9, which merely saturates.
        //   * WASHOUT where the command is mostly DC. Its standalone weakness (the loop compensates by
        //     commanding 1/(1-sigma) harder, which is the authority scalar AVIONICS_AUTHORITY.md killed)
        //     is exactly what makes it work HERE: commanding harder moves you into another cell.
        //   * DELAY where the command is changing. Pure lag does nothing at all to a constant command, and
        //     is the sharpest thing in the set against one that is moving.
        //
        // There is no absorbing state, which is the property being bought. Do nothing -> drift forces a
        // correction -> you are now holding or twitching. Hold it -> it decays -> you re-command -> the
        // transient rises -> lag. Fight it -> it destabilises -> you back off -> drift. Any fixed stick
        // policy walks into something, and the only real remedy is a unit rated for the vehicle -- which is
        // the constraint the whole design is trying to make binding.
        //
        // NOT IN THE POLICY, deliberately: dropouts, misdirect and coupling were strong in EVERY regime, so
        // there was no cell where they were the specific answer. That made them standalone candidates rather
        // than moves; a policy whose job is regime matching has nothing to gain from a move that does not
        // vary by regime. They lost as modes, so they are gone entirely.
        //
        // THE RISK IS LEGIBILITY, not strength: a failure that changes character is harder to attribute than
        // one that is always present. Three things hold it together -- a dwell time so a regime lasts long
        // enough to read, a margin so it does not flap on the boundary, and the regime NAMED in the PAW. The
        // player-facing statement has to stay learnable in one sentence per cell ("it wanders when I coast,
        // it lags when I fight it"); if it reads as one incoherent malfunction instead, the tuning is wrong.
        // That is why dwell and margin are live knobs rather than constants -- they are the two numbers that
        // decide whether the mechanic is legible, and legibility is what it has to be tuned for.
        //
        // The fiction is not a malicious computer -- it is a GAIN SCHEDULE characterised for a different
        // vehicle. Real control laws are scheduled per flight regime; an under-rated unit's table is wrong
        // in every cell, and wrong in a different way in each. The design is adversarial, the story is a
        // lookup table full of the wrong numbers.
        public static float AdversarialAcGain = 3f;        // maps |c - m| onto 0..1; the balance knob
        public static float AdversarialDwellSec = 2f;      // minimum time in a regime, so it can be read
        public static float AdversarialMargin = 0.15f;     // lead needed to switch, so it cannot flap

        // The regime EMA window, in attitude-response cycles rather than seconds, so it rides the same
        // m^(-1/3) law as noise Hz and needs no scaling switch of its own: 3 cycles is ~1.5 s on a 1 t probe
        // and ~7 s on a 100 t stack. It has to be SLOWER than the vehicle's own response, or the split just
        // tracks the instantaneous command and every cell reads as "moving it".
        public static float RegimeTauCycles = 3f;

        static float _advDc, _advAc, _advHold;
        static int _advRegime = -1;

        public static readonly string[] AdversarialNames = { "drift", "overgain", "washout", "lag" };
        public static int AdversarialRegime => _advRegime;
        public static string AdversarialRegimeName
            => _advRegime < 0 ? "settling" : AdversarialNames[_advRegime];

        // Tuning readouts. AC gain is set by watching these: the number to aim for is a SPREAD across the
        // four cells over a flight, not a value, and dc/ac are what say which way it is wrong.
        public static float AdversarialDc => _advDc;
        public static float AdversarialAc => _advAc;

        /// <summary>PAW one-liner for the current degradation.</summary>
        public static string DescribePenalty(float sigma)
            => sigma <= 0f ? "clean" : $"{AdversarialRegimeName} {sigma * 100f:F0}% — degraded";

        // The sustained component, shared by the washout move and by the regime split -- one EMA, so the
        // two can never disagree about what "holding" means.
        static float _wp, _wy, _wr;

        public static void ResetAdversarial()
        {
            _advDc = _advAc = _advHold = 0f;
            _advRegime = -1;
            _wp = _wy = _wr = 0f;
            ResetDelay();
        }

        static float AdversarialTau => Mathf.Max(0.05f, RegimeTauCycles / Mathf.Max(0.01f, EffectiveNoiseHz));

        // Subtract the sustained component: a held command decays toward nothing, a transient passes whole.
        // At sigma = 1 the DC gain is exactly zero, and an integrator cannot restore DC gain removed
        // DOWNSTREAM of it -- winding up further just produces more DC, which is what is being removed.
        static void ApplyWashout(ref float pitch, ref float yaw, ref float roll, float sigma)
        {
            pitch = Mathf.Clamp(pitch - sigma * _wp, -1f, 1f);
            yaw   = Mathf.Clamp(yaw   - sigma * _wy, -1f, 1f);
            roll  = Mathf.Clamp(roll  - sigma * _wr, -1f, 1f);
        }

        static void UpdateAdversarialRegime(float p, float y, float r)
        {
            float dt = Time.fixedDeltaTime > 0f ? Time.fixedDeltaTime : 0.02f;
            float a = Mathf.Clamp01(dt / AdversarialTau);
            _wp += (p - _wp) * a;
            _wy += (y - _wy) * a;
            _wr += (r - _wr) * a;

            // DC = what is being held, AC = what is being moved. Measured as deviation from the vessel's own
            // recent mean rather than as a per-tick delta: at 50 Hz a per-tick difference is dominated by
            // autopilot jitter and would read "moving it" during a dead-steady hold.
            float dc = Mathf.Clamp01(new Vector3(_wp, _wy, _wr).magnitude);
            float ac = Mathf.Clamp01(new Vector3(p - _wp, y - _wy, r - _wr).magnitude * AdversarialAcGain);
            _advDc += (dc - _advDc) * a;
            _advAc += (ac - _advAc) * a;

            // Membership products, so the boundaries are soft and a craft sitting between two regimes has a
            // genuinely close call rather than an arbitrary one.
            float wDrift    = (1f - _advDc) * (1f - _advAc);
            float wOvergain = (1f - _advDc) * _advAc;
            float wWashout  = _advDc * (1f - _advAc);
            float wLag      = _advDc * _advAc;

            int best = 0;
            float bestW = wDrift;
            if (wOvergain > bestW) { best = 1; bestW = wOvergain; }
            if (wWashout  > bestW) { best = 2; bestW = wWashout; }
            if (wLag      > bestW) { best = 3; bestW = wLag; }

            _advHold += dt;
            if (_advRegime < 0) { _advRegime = best; _advHold = 0f; return; }

            float currentW = _advRegime == 0 ? wDrift : _advRegime == 1 ? wOvergain
                           : _advRegime == 2 ? wWashout : wLag;
            if (best != _advRegime && _advHold >= AdversarialDwellSec && bestW > currentW + AdversarialMargin)
            {
                _advRegime = best;
                _advHold = 0f;
            }
        }

        public static void ApplyAdversarial(ref float pitch, ref float yaw, ref float roll, float sigma)
        {
            UpdateAdversarialRegime(pitch, yaw, roll);

            // ADVANCE EVERY STATEFUL MOVE, APPLY ONLY THE SELECTED ONE. Running just the winner leaves the
            // others' state stale, so a switch into lag reads a ring buffer full of an older flight and
            // jumps -- a switching artefact that would be indistinguishable from the mechanic working.
            // Delay is the only move that carries a buffer; the washout EMA advances in the regime update
            // above, and overgain and drift are memoryless.
            float dp = pitch, dy = yaw, dr = roll;
            ApplyDelay(ref dp, ref dy, ref dr, sigma);

            switch (_advRegime)
            {
                case 1:
                {
                    float g = GainFor(sigma);
                    pitch = Mathf.Clamp(pitch * g, -1f, 1f);
                    yaw   = Mathf.Clamp(yaw * g, -1f, 1f);
                    roll  = Mathf.Clamp(roll * g, -1f, 1f);
                    break;
                }
                case 2:
                    ApplyWashout(ref pitch, ref yaw, ref roll, sigma);
                    break;
                case 3:
                    pitch = dp; yaw = dy; roll = dr;
                    break;
                default:
                    // Drift: additive, so it is the only move that still bites a null stick -- which is the
                    // entire reason this cell exists. All three axes; roll is no longer separable.
                    yaw   = Mathf.Clamp(yaw + NoiseSample(0, sigma), -1f, 1f);
                    pitch = Mathf.Clamp(pitch + NoiseSample(1, sigma), -1f, 1f);
                    roll  = Mathf.Clamp(roll + NoiseSample(2, sigma), -1f, 1f);
                    break;
            }
        }

        // ---- ARMING: WHEN the penalty is live at all ----------------------------------------------
        // Orthogonal to the policy, which is why it is one gate in front of it rather than three near-copies
        // of the mechanic. It is really a question about SAFE HARBOUR -- how much of the flight envelope the
        // player can retreat into and be certain nothing is being done to them:
        //
        //   always              no safe harbour. A craft over capacity is corrupted whatever it is doing,
        //                       including sitting still doing nothing.
        //   any input+throttle  safe harbour = FULLY IDLE. Not burning and not steering. Any active flight
        //                       is armed, so the no-escape property survives intact: throttle alone arms it,
        //                       which means a straight burn still lands in the drift cell.
        //   steering only       safe harbour = NOT STEERING. You may burn freely. Note what this costs: it
        //                       makes the drift cell nearly unreachable, which hands back a version of the
        //                       dominant escape ("stop commanding") during any coast.
        //
        // The middle one is the interesting design claim: a flight computer that is not being ASKED for
        // anything should not fail, which is also the cleanest answer to the 4a objection that noise is
        // active sabotage against a capsule riding a stage it is not flying. Under `always` that objection
        // needs the Engage/Disengage toggle to answer it; under either gate it mostly answers itself.
        //
        // DEADBAND, not `> 0`. This hook runs POST-autopilot, so what it reads is the vehicle's program,
        // not a human stick -- and MechJeb and SAS emit small nonzero commands continuously. A strict
        // zero test would read "armed" essentially always and the three variants would be one variant.
        public static int ArmMode = 0;
        public const float ArmDeadband = 0.01f;
        public static readonly string[] ArmNames = { "always", "any input incl throttle", "steering only" };

        static bool _armed = true;
        /// <summary>Last computed arming state. Read by the RCS patch, which cannot see ctrlState first.</summary>
        public static bool Armed => _armed;

        public static bool ComputeArmed(FlightCtrlState st)
        {
            if (ArmMode <= 0 || st == null) return _armed = true;
            const float d = ArmDeadband;
            bool steering = Mathf.Abs(st.pitch) > d || Mathf.Abs(st.yaw) > d || Mathf.Abs(st.roll) > d
                         || Mathf.Abs(st.X) > d || Mathf.Abs(st.Y) > d || Mathf.Abs(st.Z) > d;
            return _armed = ArmMode == 1 ? (steering || st.mainThrottle > d) : steering;
        }

        // ---- NON-STATIONARITY: make the deterministic move un-learnable ---------------------------
        // The other escape from "deterministic gets learned". Overgain is learnable only because its slope
        // is FIXED; a slow random walk means adaptive tuning is always chasing a target that has moved. Very
        // low frequency (~20 s period) so it reads as a system that will not settle rather than as noise.
        //
        // The OVERGAIN cell is all it touches now (it is the only deterministic move left with a parameter
        // to walk), so this is a knob about that one cell, not about the mechanic as a whole.
        public static bool NoiseDrift;
        public static float DriftHz = 0.05f;

        public static float DriftFor(int idx)
            => NoiseDrift ? 0.5f + Mathf.PerlinNoise(Time.time * DriftHz, idx * 13.1f) : 1f;

        // ---- MOVE: TRANSPORT DELAY (the `lag` cell) -----------------------------------------------
        // Hold the command for N physics ticks, N rising with overload. Pure delay is the classic loop
        // killer: it eats PHASE margin, and unlike gain there is nothing a fixed-gain controller can do
        // about it at all. 100-200 ms of unexpected lag destabilises most controllers, and at KSP's 50 Hz
        // that is only 5-10 ticks.
        //
        // The sharpest thing in the set, which is why the policy spends it only where it bites: lag does
        // NOTHING to a constant command, so it is reserved for the cell where the command is moving.
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

        // Dry mass of one part, computed the way KSP itself computes it in Part.UpdateMass():
        //   mass = prefabMass + SUM(IPartMassModifier.GetModuleMass(prefabMass))
        //
        // NOT `p.mass + p.GetModuleMass(p.mass)`. Once UpdateMass() has run, `p.mass` ALREADY equals
        // prefabMass + moduleMass, so adding the module term again double-counts every mass modifier on
        // the part -- this module's own hardware mass, ProceduralPart's hull, and RealFuels' tank (which
        // reports NON-additively, as `mass - prefabMass`, so it gets double-counted too). On an avionics
        // box that is most of the part's mass, which is why the readouts built on it came out near 2x.
        //
        // Deriving from the prefab rather than reading `p.mass` also makes this independent of whether
        // UpdateMass() has already run this frame: in flight KSP keeps `p.mass` current, but in the editor
        // it is only refreshed when something calls ShipConstruct.GetShipMass(), so reading it directly
        // makes the answer depend on call order.
        public static float PartDryMassTons(Part p)
        {
            if (p == null) return 0f;
            float prefab = (p.partInfo != null && p.partInfo.partPrefab != null) ? p.partInfo.partPrefab.mass : p.mass;
            return prefab + p.GetModuleMass(prefab);
        }

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
                t += PartDryMassTons(p);
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
                        // allowAxial is authored data, not state, so it needs the dead check the
                        // capacity path already gets from CapacityTons.
                        if (fix.allowAxial && !fix.dead) fixedAxial = true;
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

            // THE DEGRADED BAND. Under capacity, clean control. Over it the craft still steers, but its
            // commands are corrupted by the regime-matching policy at a strength rising with overload.
            // A guided core does not short-circuit: it is judged on mass like everything else.
            //
            // NO CUTOFF, at any ratio. A hard flip to unguided past some threshold is the same arbitrary
            // cliff this design exists to remove, just relocated -- and it is redundant, because sigma
            // already asymptotes to unusable: near 1 the command is close to useless, so the vehicle cannot
            // be flown regardless. The limit enforces itself, continuously, and the only thing a threshold
            // adds is a jarring change to a DIFFERENT failure mode at a number nothing physical picked.
            //
            // Discrete "unguided" survives only where it is a PROPERTY OF THE PART: an Unguided/Science-Core
            // core, a capacity-0 named part, or no avionics at all. Those fall through below with
            // maxCapacity == 0 and are unaffected.
            if (maxCapacity > 0f)
            {
                float ratio = vesselMass / maxCapacity;
                if (ratio > 1f) noise = NoiseFor(ratio);
                return LockLevel.Unlocked;
            }
            return (coreAxial || fixedAxial) ? LockLevel.Axial : LockLevel.Locked;
        }

        static bool IsValidCommand(ModuleCommand mc) =>
            mc.ModuleState == ModuleCommand.ModuleControlState.Nominal ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialProbe ||
            mc.ModuleState == ModuleCommand.ModuleControlState.PartialManned;
    }
}
