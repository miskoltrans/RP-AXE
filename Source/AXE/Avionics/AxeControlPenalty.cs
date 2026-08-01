using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// One pluggable consequence of flying over an avionics unit's rated mass.
    ///
    /// WHY THIS EXISTS. The consequence is the only part of the avionics overload design that is still
    /// undecided, and it has already been wrong twice — an EC power penalty that a 39-hour battery
    /// swallowed, and an authority scalar that a control loop absorbed (docs/AVIONICS_AUTHORITY.md).
    /// Everything AROUND it — engage/disengage, the auto rules, the regime callouts, the editor readouts —
    /// is settled and does not care which one wins. Putting the consequence behind an interface lets that
    /// surrounding work be built, shipped and tested while the mechanic stays a runtime choice, and lets the
    /// losers be deleted afterwards by removing files rather than by unpicking branches.
    ///
    /// The candidates split into two families, and the split predicts their strength:
    ///   * DISTURBANCES (noise, in either mode) — a feedback loop exists to reject disturbances, which is
    ///     precisely why they keep getting absorbed.
    ///   * MARGIN ATTACKS (overgain, coupling, delay) — the three classical ways to destabilise a loop:
    ///     gain margin, the decoupling assumption, phase margin. None is rejectable, because each modifies
    ///     what the controller is closing around rather than adding a signal to it.
    /// <see cref="PenaltyLock"/> is RP-1's original rule, kept selectable so it is both an A/B baseline and
    /// the fallback if no perturbation survives testing.
    /// </summary>
    public abstract class AxeControlPenalty
    {
        public abstract string Id { get; }

        /// <summary>RP-1's rule: over capacity locks attitude outright rather than degrading it.
        /// The locker checks this instead of handing the frame to <see cref="Apply"/>.</summary>
        public virtual bool LocksInstead => false;

        /// <summary>Stateful or cross-axis, so it must be applied exactly once per frame. The RCS patch
        /// skips these — the post-autopilot hook has already transformed ctrlState, and pushing a delay
        /// buffer or running a coupling pass twice would double it.</summary>
        public virtual bool Stateful => false;

        /// <summary>Transform the rotation commands. <paramref name="sigma"/> is 0..1, rising with overload.</summary>
        public abstract void Apply(ref float pitch, ref float yaw, ref float roll, float sigma);

        /// <summary>Vessel switch: drop any per-vessel state.</summary>
        public virtual void Reset(Vessel v) { }

        /// <summary>PAW one-liner.</summary>
        public virtual string Describe(float sigma)
            => sigma <= 0f ? "clean" : $"{sigma * 100f:F0}% — degraded";
    }

    // ---------------------------------------------------------------------------------------------
    // 0 — nothing. Overload has no consequence at all. Only useful as a control in the A/B.
    public sealed class PenaltyNone : AxeControlPenalty
    {
        public override string Id => "none";
        public override void Apply(ref float p, ref float y, ref float r, float sigma) { }
        public override string Describe(float sigma) => sigma <= 0f ? "clean" : "over capacity (no penalty)";
    }

    // ---------------------------------------------------------------------------------------------
    // 1 — RP-1's rule. Handled by the locker, so Apply is never called.
    public sealed class PenaltyLock : AxeControlPenalty
    {
        public override string Id => "lock";
        public override bool LocksInstead => true;
        public override void Apply(ref float p, ref float y, ref float r, float sigma) { }
        public override string Describe(float sigma) => sigma <= 0f ? "clean" : "over capacity — attitude locked";
    }

    // ---------------------------------------------------------------------------------------------
    // 2 — noise added regardless of input. The craft wanders on its own; reads as a vehicle that will not
    // sit still. A disturbance, so expect the loop to reject much of it.
    public sealed class PenaltyNoiseUncommanded : AxeControlPenalty
    {
        public override string Id => "uncommanded";
        public override void Apply(ref float p, ref float y, ref float r, float sigma)
        {
            y = Mathf.Clamp(y + AxeControlLockerUtils.NoiseSample(0, sigma), -1f, 1f);
            p = Mathf.Clamp(p + AxeControlLockerUtils.NoiseSample(1, sigma), -1f, 1f);
            if (AxeControlLockerUtils.NoiseRoll)
                r = Mathf.Clamp(r + AxeControlLockerUtils.NoiseSample(2, sigma), -1f, 1f);
        }
    }

    // ---------------------------------------------------------------------------------------------
    // 3 — noise SCALES the command, so a null stick stays null and small commands survive proportionally.
    // Fixes the "RCS unusable at any sigma" report at its root: that was never an inertia problem, it was a
    // small-command problem (docking commands run ~0.05, so additive +/-0.3 is six times the signal).
    public sealed class PenaltyNoiseOnInput : AxeControlPenalty
    {
        public override string Id => "on input";
        public override void Apply(ref float p, ref float y, ref float r, float sigma)
        {
            y = Mathf.Clamp(y * (1f + AxeControlLockerUtils.NoiseSample(0, sigma)), -1f, 1f);
            p = Mathf.Clamp(p * (1f + AxeControlLockerUtils.NoiseSample(1, sigma)), -1f, 1f);
            if (AxeControlLockerUtils.NoiseRoll)
                r = Mathf.Clamp(r * (1f + AxeControlLockerUtils.NoiseSample(2, sigma)), -1f, 1f);
        }
    }

    // ---------------------------------------------------------------------------------------------
    // 4 — GAIN MARGIN. The command is amplified, so the loop overcontrols and oscillates by itself. Not a
    // disturbance: it modifies the plant the controller is closing around, so the controller's own
    // corrections are amplified too and it cannot counter-steer out. Frequency emerges from the vehicle's
    // dynamics, so no Hz term is needed, and it drives the command INTO the clamp rather than being clipped
    // by it — so unlike the noise modes it does not go soft when the vehicle is working hardest.
    public sealed class PenaltyOvergain : AxeControlPenalty
    {
        public override string Id => "overgain";
        public override void Apply(ref float p, ref float y, ref float r, float sigma)
        {
            float g = AxeControlLockerUtils.GainFor(sigma);
            p = Mathf.Clamp(p * g, -1f, 1f);
            y = Mathf.Clamp(y * g, -1f, 1f);
            r = Mathf.Clamp(r * g, -1f, 1f);
        }
        public override string Describe(float sigma)
            => sigma <= 0f ? "clean" : $"gain x{AxeControlLockerUtils.GainFor(sigma):F2} — degraded";
    }

    // ---------------------------------------------------------------------------------------------
    // 5 — DECOUPLING. Commanding one axis bleeds into the others, so the loop fights itself: correcting the
    // induced yaw induces pitch. Coefficients are fixed per vessel, which makes it a systematic misalignment
    // ("this rocket pulls left when you pitch up") rather than randomness — learnable, and it reads as a
    // characteristic of the craft. Proportional to command, so it inherits on-input's small-command safety.
    public sealed class PenaltyCoupling : AxeControlPenalty
    {
        public override string Id => "coupling";
        public override bool Stateful => true;
        public override void Reset(Vessel v)
        {
            if (v != null) AxeControlLockerUtils.SeedCoupling((int)v.persistentId);
        }
        public override void Apply(ref float p, ref float y, ref float r, float sigma)
            => AxeControlLockerUtils.ApplyCoupling(ref p, ref y, ref r, sigma);
    }

    // ---------------------------------------------------------------------------------------------
    // 6 — PHASE MARGIN. The command is held N ticks. Pure delay is the classic loop killer and a fixed-gain
    // controller can do nothing about it; at KSP's 50 Hz the 100-200 ms that destabilises most controllers
    // is only 5-10 ticks. Expected to be the sharpest of the set, quite possibly a cliff wearing a
    // gradient's clothes — built to find out, not because it is predicted to win.
    public sealed class PenaltyDelay : AxeControlPenalty
    {
        public override string Id => "delay";
        public override bool Stateful => true;
        public override void Reset(Vessel v) => AxeControlLockerUtils.ResetDelay();
        public override void Apply(ref float p, ref float y, ref float r, float sigma)
            => AxeControlLockerUtils.ApplyDelay(ref p, ref y, ref r, sigma);
        public override string Describe(float sigma)
            => sigma <= 0f ? "clean"
             : $"{Mathf.RoundToInt(AxeControlLockerUtils.DelayTicksMax * sigma) * 20} ms lag — degraded";
    }

    // ---------------------------------------------------------------------------------------------
    // 7 — AVAILABILITY. Randomly drops control cycles, holding the last command. The only candidate that
    // is neither learnable (timing is random) nor rejectable (there is nothing to command against during a
    // dropout). Models an overloaded flight computer missing cycles, which is what insufficient throughput
    // actually does. Self-scaling: irrelevant on a gentle coast, severe at max-Q or on final approach.
    public sealed class PenaltyDropout : AxeControlPenalty
    {
        public override string Id => "dropouts";
        public override bool Stateful => true;
        public override void Reset(Vessel v) => AxeControlLockerUtils.ResetDropout();
        public override void Apply(ref float p, ref float y, ref float r, float sigma)
            => AxeControlLockerUtils.ApplyDropout(ref p, ref y, ref r, sigma);
        public override string Describe(float sigma)
            => sigma <= 0f ? "clean" : $"{sigma * 100f:F0}% of cycles missed — degraded";
    }

    // ---------------------------------------------------------------------------------------------
    // 8 — MISDIRECTION. Rotates the command vector: ask for pitch, get yaw and roll, and at the limit
    // almost nothing on the axis you wanted. Not dodgeable by flying gently (the misdirected FRACTION is
    // constant), magnitude-preserving (weakness was already proven not to work), and the only mode that
    // survives binary actuators, since it changes WHICH thrusters fire rather than how hard.
    public sealed class PenaltyMisdirect : AxeControlPenalty
    {
        public override string Id => "misdirect";
        public override bool Stateful => true;   // cross-axis; must not be applied twice in a frame
        public override void Reset(Vessel v)
        {
            if (v != null) AxeControlLockerUtils.SeedCoupling((int)v.persistentId);
        }
        public override void Apply(ref float p, ref float y, ref float r, float sigma)
            => AxeControlLockerUtils.ApplyMisdirect(ref p, ref y, ref r, sigma);
        public override string Describe(float sigma)
            => sigma <= 0f ? "clean"
             : $"{sigma * AxeControlLockerUtils.MisdirectMaxDeg:F0}° off-axis — degraded";
    }

    // ---------------------------------------------------------------------------------------------
    /// <summary>The selectable set. Index is driven by the core's DEBUG mode knob; order is the PAW order.</summary>
    public static class AxeControlPenalties
    {
        public static readonly AxeControlPenalty[] All =
        {
            new PenaltyNone(),
            new PenaltyLock(),
            new PenaltyNoiseUncommanded(),
            new PenaltyNoiseOnInput(),
            new PenaltyOvergain(),
            new PenaltyCoupling(),
            new PenaltyDelay(),
            new PenaltyDropout(),
            new PenaltyMisdirect(),
        };

        public static readonly string[] Names =
            { "none", "lock (RP-1)", "uncommanded", "on input", "overgain", "coupling", "delay", "dropouts", "misdirect" };

        public static int Index = 3;   // on input

        public static AxeControlPenalty Current => All[Mathf.Clamp(Index, 0, All.Length - 1)];
    }
}
