namespace RPAxe.Simulation
{
    /// <summary>
    /// The player-chosen simulation scenario. Editor -> flight is one scene hop in a single session, so
    /// this rides along in <see cref="AxeSimulation"/>'s static state (no save persistence needed — the
    /// save-swap backbone handles "nothing persists").
    /// </summary>
    public class AxeSimulationParams
    {
        public CelestialBody Body;
        public bool InOrbit;         // false = leave on the launch pad (home only); true = teleport to orbit
        public double Periapsis;     // m ASL
        public double Apoapsis;      // m ASL (== Periapsis for a circular orbit)
        public double Inclination;   // degrees
        public double Lan;           // longitude of ascending node, degrees
        public double ArgPe;         // argument of periapsis, degrees
        public double WarpDays;      // rung B: advance time by this many days after reaching orbit (0 = now)
        public int DelaySeconds;     // hold on the pad before teleporting (lets the player watch the ascent first)
        public EditorFacility Facility = EditorFacility.VAB;  // which editor to revert back to

        public bool Moved;           // flight-side latch: has the teleport already run this launch?

        public void Reset() => Moved = false;
    }
}
