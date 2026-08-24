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

        // ---- CONTROL NOISE, the shipped overload consequence (docs/AVIONICS_AUTHORITY.md) ---------
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
        //     away by vessel rotational inertia and would be invisible on anything heavy. (Both modes went
        //     with the drift cell; NoiseHz survives because the regime EMA window is measured in
        //     attitude-response cycles and reads it -- see AdversarialTau.)
        // EVERY TUNABLE BELOW IS NOW A CONST. They were live statics driven from DEBUG PAW knobs for the
        // whole prototype, because none of them has a physical anchor (KSP models no bending modes) and feel
        // was the only way to find them. That search is over; the rig is gone and the values it found are
        // frozen here. Changing one now needs a rebuild, which is the correct cost for a shipped balance
        // number. Where a number has an ARGUMENT behind it rather than a feel, the argument is recorded with
        // it -- argue with the sentence, not the digits.
        // k is ANCHORED, not tuned: it falls out of one design statement -- "at 20% over its rated mass a
        // unit is hopeless" -- i.e. sigma(1.2) = 0.9, which solves to k = 11.5. Argue about the sentence,
        // not the number.
        //   2% over -> 0.21    5% -> 0.44    10% -> 0.68    15% -> 0.82    20% -> 0.90
        // A deliberately narrow tolerance band: a few percent of grace, then it goes away fast. Rated
        // capacity is close to a hard constraint, which is how real vehicles treat their control design
        // margin -- nobody flies 20% over what the control system was characterised for.
        public const float NoiseK = 11.5f;

        // C in Hz = C / mass^(1/3). NOT a frequency itself -- see HzForMass.
        public const float NoiseHz = 2f;

        // Live per-vessel state, not a knob: the controller writes this each recompute from HzForMass.
        public static float EffectiveNoiseHz = 2f;

        // A FIXED frequency cannot be right for both a 5 t probe and a 300 t launcher: the vehicle low-passes
        // the noise according to its own rotational response, so a big stack filters 2 Hz heavily while a
        // small probe barely does. Perturbing each vehicle at its OWN response frequency is what makes the
        // effect comparable across sizes instead of accidentally tuned to whatever was last flown.
        //
        // Rigid-body attitude response time scales with linear dimension: I ~ m*L^2 and torque roughly ~ m,
        // so timescale ~ L and natural frequency ~ 1/L ~ m^(-1/3). At C = 2 a 1 t probe gets 2 Hz and a 100 t
        // stack gets 0.43 Hz.
        public static float HzForMass(float massTons)
            => NoiseHz / Mathf.Pow(Mathf.Max(0.1f, massTons), 1f / 3f);

        // ALL THREE AXES. Roll was separable while the modes were being compared -- it is by far the most
        // perceptible axis, so "is roll alone carrying the whole feel?" was worth being able to answer. It
        // is answered; roll is degraded like the other two and the switch is gone.

        // ZERO IN, ZERO OUT -- an invariant of the whole mechanic, and the reason NO move is additive.
        // Additive noise on a command that is already small is not degradation, it is replacement: docking
        // runs commands around 0.05, so +/-0.3 of noise is six times the signal and the input becomes
        // garbage rather than degraded -- which is what made an additive-everywhere mode unusable on RCS,
        // where small commands live. The DRIFT cell used to be the one deliberate exception, injecting on a
        // null stick so that "fly gently and you are safe" had an answer.
        //
        // IT WAS REMOVED, and the loophole is taken back knowingly. That cell was selected precisely when
        // there was no command to be proportional TO, so its amplitude was set by sigma alone -- and sigma
        // saturates at 1.0 for any ratio past ~1.5 (see NoiseFor). An assembled station sits at r = 2-10,
        // not the 1.0-1.3 a launch vehicle lives in, so the cell delivered a FULL-DEFLECTION random command
        // on all three axes to a vessel that was merely holding attitude. SAS then fought it, the fight kept
        // the mechanic armed, and the loop sustained itself: uncommanded RCS and gimbal activity that no
        // player action could quiet. A penalty you cannot stop by stopping is not a cost, it is a fault.
        //
        // So the rule is now simply: no command, no corruption. Every remaining move is proportional to the
        // command or a pure time shift of it, and the misdirection layer rotates it -- all of them are
        // exactly zero at zero input, at any sigma. What is given up is the counter to minimal input; what
        // is bought is a mechanic that is always attributable to something the player just did.

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
        public const float OvergainSlope = 10f;

        // sigma = 1 - e^(-k(r-1)) inverted, so gain can be derived from sigma without plumbing the ratio
        // through: every move takes sigma and nothing else.
        public static float RatioFromSigma(float sigma)
            => 1f + (-Mathf.Log(Mathf.Max(1e-4f, 1f - sigma)) / Mathf.Max(0.01f, NoiseK));

        public static float GainFor(float sigma)
            => sigma <= 0f ? 1f : 1f + OvergainSlope * (RatioFromSigma(sigma) - 1f);

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
        //   holding little   | IDLE (no-op)         | OVERGAIN
        //   holding a lot    | WASHOUT              | DELAY
        //
        //   * IDLE for the empty cell. It was an additive disturbance -- the one move that read no input at
        //     all, and so the only answer to "fly gently and you are safe". It is now a no-op; see the
        //     zero-in-zero-out note above for why. The cell is KEPT rather than folded into its neighbours
        //     because the regime split still has to classify a quiet vessel somewhere, and because "idle"
        //     is then the honest thing for the PAW to report.
        //   * OVERGAIN where commands are SMALL -- amplification needs headroom below the clamp, and a
        //     x3 on 0.3 is a different event from a x3 on 0.9, which merely saturates.
        //   * WASHOUT where the command is mostly DC. Its standalone weakness (the loop compensates by
        //     commanding 1/(1-sigma) harder, which is the authority scalar AVIONICS_AUTHORITY.md killed)
        //     is exactly what makes it work HERE: commanding harder moves you into another cell.
        //   * DELAY where the command is changing. Pure lag does nothing at all to a constant command, and
        //     is the sharpest thing in the set against one that is moving.
        //
        // THERE IS NOW ONE ABSORBING STATE -- doing nothing -- and that is a deliberate retreat from the
        // property the shape was built for. The original cycle ran: do nothing -> drift forces a correction
        // -> you are holding or twitching; hold it -> it decays -> you re-command -> the transient rises ->
        // lag; fight it -> it destabilises -> you back off -> drift. With the drift cell gone the loop is
        // open at the top. Everything from "hold it" onward is unchanged, so there is still no escape
        // available WHILE FLYING, which is where the constraint has to bind: an undersized unit still
        // cannot fly its vehicle, and the only real remedy is still a unit rated for it. What it no longer
        // does is punish a vessel that nobody is flying.
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
        public const float AdversarialAcGain = 3f;         // maps |c - m| onto 0..1; the balance knob
        public const float AdversarialDwellSec = 2f;       // minimum time in a regime, so it can be read
        public const float AdversarialMargin = 0.15f;      // lead needed to switch, so it cannot flap

        // The regime EMA window, in attitude-response cycles rather than seconds, so it rides the same
        // m^(-1/3) law as noise Hz and needs no scaling switch of its own: 3 cycles is ~1.5 s on a 1 t probe
        // and ~7 s on a 100 t stack. It has to be SLOWER than the vehicle's own response, or the split just
        // tracks the instantaneous command and every cell reads as "moving it".
        public const float RegimeTauCycles = 3f;

        static float _advDc, _advAc, _advHold;
        static int _advRegime = -1;

        public static readonly string[] AdversarialNames = { "idle", "overgain", "washout", "lag" };
        public static int AdversarialRegime => _advRegime;
        public static string AdversarialRegimeName
            => _advRegime < 0 ? "settling" : AdversarialNames[_advRegime];

        /// <summary>PAW one-liner: the live regime, the strength, and the base layer's bound if it is on.
        /// The layer is named separately because it is not one of the regimes and does not switch with
        /// them -- reading "drift" while the craft is also pointing 40° wrong is otherwise misleading.</summary>
        public static string DescribePenalty(float sigma)
            => sigma <= 0f ? "clean"
             : $"{AdversarialRegimeName} {sigma * 100f:F0}% +{sigma * MisdirectMaxDeg:F0}° off-axis — degraded on input";

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
                    // IDLE: nothing is written. This cell is selected when there is neither something being
                    // held nor something being moved, so under the zero-in-zero-out rule there is nothing
                    // here to corrupt. The misdirection layer that runs after it is a rotation and is
                    // likewise identity on a zero vector, so a null stick really does stay null.
                    break;
            }
        }

        // ================ BASE LAYER: MISDIRECTION (gyro drift) ====================================
        // NOT a move in the policy, and that is the point. The four cells all corrupt the MAGNITUDE of a
        // command (or its timing), and three of the four are PROPORTIONAL to it -- which was a deliberate
        // fix (additive-everywhere made RCS unusable at any sigma) and is also their shared loophole: make
        // your inputs small and you buy a proportionally small error. Autopilots are very good at exactly
        // that. Misdirection has no such loophole, because it rotates rather than scales: the fraction that
        // reaches the intended axis is cos(theta) regardless of magnitude, so a smaller input buys a smaller
        // amount of the wrong thing and nothing more. It is also the only mechanic here that survives NEAR
        // BINARY actuators, where scaling 0.7 vs 1.0 fires the same thrusters but changing which AXIS the
        // command lands on changes which thrusters fire.
        //
        // It therefore runs ALWAYS, underneath whichever cell the policy has selected, instead of competing
        // for a cell. The two do different jobs: the policy decides how badly you are punished for what you
        // are doing, misdirection decides that you cannot get the direction right at all. It is deliberately
        // paired with the arming gate -- a base layer with no safe harbour would be corruption with no off
        // switch, and `any input incl throttle` is what makes "stop asking for anything" the answer.
        //
        // THE ROTATION PRECESSES; it is not a fixed offset. A static rotation is a fixed linear transform,
        // and a fixed transform is exactly what integral terms trim out over a few seconds -- MechJeb would
        // simply learn "pitch needs a bit of yaw" and stop caring. So the offset wanders continuously: you
        // get one configuration for a while, adapt to it, and it has moved.
        //
        // Three independent Perlin channels form a ROTATION VECTOR -- its direction is the axis, its length
        // the angle. Because the channels evolve independently the axis precesses rather than the angle
        // merely pulsing on a fixed axis. Bounded by sigma * MisdirectMaxDeg, so overload sets how far wrong
        // it can get while the rate knob sets how fast it moves.
        //
        // WHAT THE FIRST CUT GOT WRONG, from flying it: the precession was too slow and too SMOOTH to read
        // as a failing gyro -- a slow sweep you could sit and wait out. Three fixes, all aimed at the same
        // property:
        //   * RATE. 0.08 Hz is a ~12 s wander, well inside what both an integral term and a player track.
        //     0.6 Hz re-arranges the configuration every second or two: too fast to be worth adapting to,
        //     still an order of magnitude below the vehicle's own attitude response, so it is not simply
        //     low-passed away the way the white-noise mode was.
        //   * OCTAVES. One Perlin lane is a smooth curve -- it has a rate but no texture, so the axis sweeps
        //     rather than jumps. Three octaves at half amplitude each lay fast structure over the slow
        //     wander, which is what makes it read as random instead of as a slow oscillation.
        //   * DECORRELATED CHANNELS. All three were sampled at the SAME x with only a lane offset in y, so
        //     they crossed the noise lattice in lockstep and the axis re-arranged on a common beat.
        //     Mutually incommensurate per-channel rates remove the beat.
        // The channels are also gained: Unity's Perlin is bell-shaped rather than uniform -- it clusters
        // near 0.5 and rarely approaches 0 or 1 -- so the raw vector was typically only ~0.43 long and the
        // angle actually flown ran at well under half what the PAW advertised. Typical is now ~0.7 of the bound, with excursions that clamp at it.
        //
        // 90 is the edge case on purpose: at exactly 90 the intended-axis component is zero and everything
        // commanded lands somewhere else, and past it control would REVERSE. The layer used to be switchable
        // off (0) for A/B against the bare policy; that comparison is settled and the switch is gone.
        public const float MisdirectMaxDeg = 90f;
        public const float MisdirectRateHz = 0.6f;   // ~1.5 s to noticeably change character

        // Octave structure is a SHAPE choice, not a feel knob, so it stays out of the PAW -- the rig already
        // has enough sliders, and rate is the one number that actually needs flying to find.
        const int MisdirectOctaves = 3;
        const float MisdirectLacunarity = 2.7f;   // non-integer, so octaves never re-align on the lattice
        const float MisdirectGain = 2.4f;         // Perlin bell-shape correction (see above)

        // Per-channel base rates, mutually incommensurate so the three axes never come back into phase, and
        // separate y lanes so they sample unrelated noise to begin with.
        static readonly float[] _mdRate = { 1.00f, 1.37f, 1.79f };
        static readonly float[] _mdLane = { 0.0f, 7.3f, 13.9f };

        // Per-vessel, so two craft drift differently. Seeded on vessel switch.
        static int _mdSeed = int.MinValue;
        public static void SeedMisdirect(int seed) { _mdSeed = seed; }

        static float MisdirectFbm(int ch, float t, float seed)
        {
            float sum = 0f, amp = 1f, norm = 0f, f = _mdRate[ch];
            for (int i = 0; i < MisdirectOctaves; i++)
            {
                sum += amp * (Mathf.PerlinNoise(t * f, seed + _mdLane[ch] + i * 4.7f) * 2f - 1f);
                norm += amp;
                amp *= 0.5f;
                f *= MisdirectLacunarity;
            }
            return Mathf.Clamp(sum / norm * MisdirectGain, -1f, 1f);
        }

        /// <summary>
        /// The wrong reference frame, as a rotation. Identity when the layer is off or clean.
        ///
        /// A PURE FUNCTION OF Time.time, which is what makes it usable from both the post-autopilot hook and
        /// the ModuleRCS patch: those run on different Unity phases and the RCS one runs once PER THRUSTER,
        /// so anything stateful would advance several times a frame and anything freshly random would point
        /// each thruster somewhere different. Here every caller in a frame gets the SAME rotation, which is
        /// also the correct fiction -- there is one drifting IMU, and every command it issues, rotational or
        /// translational, is referred to that same wrong frame.
        /// </summary>
        public static Quaternion MisdirectRotation(float sigma)
        {
            if (sigma <= 0f) return Quaternion.identity;
            float t = Time.time * MisdirectRateHz;
            float seed = _mdSeed == int.MinValue ? 0f : (_mdSeed % 977) * 0.31f;
            Vector3 rot = new Vector3(MisdirectFbm(0, t, seed),
                                      MisdirectFbm(1, t, seed),
                                      MisdirectFbm(2, t, seed));
            float mag = rot.magnitude;
            if (mag < 1e-5f) return Quaternion.identity;
            return Quaternion.AngleAxis(Mathf.Clamp01(sigma) * MisdirectMaxDeg * Mathf.Clamp01(mag), rot / mag);
        }

        /// <summary>Rotate one command triple into the wrong frame. Axis-agnostic on purpose: the same call
        /// serves pitch/yaw/roll in the hook and X/Y/Z in the RCS patch.</summary>
        public static void ApplyMisdirect(ref float a, ref float b, ref float c, float sigma)
        {
            Vector3 v = new Vector3(a, b, c);
            if (v.sqrMagnitude < 1e-8f) return;   // nothing commanded, nothing to misdirect
            Quaternion q = MisdirectRotation(sigma);
            if (q == Quaternion.identity) return;
            Vector3 outv = q * v;
            a = Mathf.Clamp(outv.x, -1f, 1f);
            b = Mathf.Clamp(outv.y, -1f, 1f);
            c = Mathf.Clamp(outv.z, -1f, 1f);
        }

        // ---- ARMING: WHEN the penalty is live at all ----------------------------------------------
        // Orthogonal to the policy, which is why it is one gate in front of it rather than three near-copies
        // of the mechanic. It is really a question about SAFE HARBOUR -- how much of the flight envelope the
        // player can retreat into and be certain nothing is being done to them:
        //
        //   always              no safe harbour. A craft over capacity is corrupted whatever it is doing,
        //                       including sitting still doing nothing.
        //   any input+throttle  safe harbour = FULLY IDLE. Not burning and not steering.
        //   steering only       safe harbour = NOT STEERING. You may burn freely.
        //
        // THIS GATE MATTERS MUCH LESS THAN IT DID. It was the only thing standing between a coasting vessel
        // and the additive drift cell; with that cell a no-op, zero-in-zero-out already gives a null stick a
        // clean flight structurally, whatever the mode. What the gate still decides is the MISDIRECTION
        // layer, which is a rotation and so bites any nonzero command including an autopilot's -- so
        // "am I burning?" still changes whether a hands-off vessel is being interfered with.
        //
        // The middle one is the interesting design claim: a flight computer that is not being ASKED for
        // anything should not fail, which is also the cleanest answer to the 4a objection that noise is
        // active sabotage against a capsule riding a stage it is not flying. Under `always` that objection
        // needs the Engage/Disengage toggle to answer it; under either gate it mostly answers itself.
        //
        // DEADBAND, not `> 0`. This hook runs POST-autopilot, so what it reads is the vehicle's program,
        // not a human stick -- and MechJeb and SAS emit small nonzero commands continuously. A strict
        // zero test would read "armed" essentially always and the three variants would be one variant.
        //
        // LOCKED TO `any input incl throttle`. The three modes existed to be A/B'd; that comparison is
        // settled and the other two are gone. The design claim wins -- a flight computer that is not being
        // ASKED for anything should not fail -- and it is also what pays for the misdirection base layer,
        // which runs under every cell and therefore needs a safe harbour: "stop asking for anything" rather
        // than "ask quietly". Throttle counts, so a hands-off burn is still armed.
        public const float ArmDeadband = 0.01f;

        static bool _armed = true;
        /// <summary>Last computed arming state. Read by the RCS patch, which cannot see ctrlState first.</summary>
        public static bool Armed => _armed;

        public static bool ComputeArmed(FlightCtrlState st)
        {
            if (st == null) return _armed = true;
            const float d = ArmDeadband;
            bool steering = Mathf.Abs(st.pitch) > d || Mathf.Abs(st.yaw) > d || Mathf.Abs(st.roll) > d
                         || Mathf.Abs(st.X) > d || Mathf.Abs(st.Y) > d || Mathf.Abs(st.Z) > d;
            return _armed = steering || st.mainThrottle > d;
        }

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
        public const float DelayTicksMax = 10f;   // at sigma = 1, in 50 Hz physics ticks

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

        /// <summary>Noise amplitude as a fraction of control range: 0 under capacity, rising with overload.
        /// Asymptotes to 1 on its own -- there is no separate ceiling, because a cap on a self-capping curve
        /// only ever hid the shape.</summary>
        public static float NoiseFor(float ratio)
            => ratio <= 1f ? 0f : 1f - Mathf.Exp(-NoiseK * (ratio - 1f));

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
        /// <param name="noise">Control-noise amplitude in [0..1]; 0 unless over capacity.</param>
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
                        // A guided core CONTRIBUTES ITS CAPACITY instead of unlocking the
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
                // Was `hasFixed &&` -- procedural cores feed the same MAX.
                if ((hasFixed || guided) && partCapacity > maxCapacity) maxCapacity = partCapacity;
                // crewed pod OR a probe core with no avionics at all (an avionics unit's own command never
                // bypasses; neither does a launch clamp's, or every pad stand would unlock the rocket).
                if (cmd && !isCore && !isClamp) bypass = true;
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
