namespace RPAxe.Simulation
{
    /// <summary>
    /// The 2-rung capability gate. Simulation expresses progression as "what you can simulate expands
    /// with tech", not an on/off wall:
    ///   * Rung A (always): the home world — you can already fly here, the sim just saves the trip.
    ///   * Rung B (<see cref="RungBNode"/>): every other body + arbitrary time. The digital-computer era
    ///     is the era you can model the Moon and beyond — the tech that lets you *simulate* an unreached
    ///     world is the tech that historically let you *go*.
    ///
    /// Uses the same idiom as the rest of AXE (see <see cref="RPAxe.AxeTrackingStationGate"/>,
    /// <c>ModuleAxeAvionics</c>): <c>ResearchAndDevelopment.GetTechnologyState(node) == Available</c>.
    /// </summary>
    internal static class AxeSimulationGate
    {
        /// <summary>Verified tech id in the built tree (AxeTechTree.cfg). Digital Guidance Computer.</summary>
        internal const string RungBNode = "comp_digitalGuidanceComputer";

        public static bool CanSimulate(CelestialBody b)
        {
            if (b == null) return false;
            if (Planetarium.fetch != null && b == Planetarium.fetch.Home) return true;
            return NodeResearched(RungBNode);
        }

        /// <summary>True if <paramref name="node"/> is researched — or if we're in sandbox (no R&amp;D),
        /// where everything is available.</summary>
        public static bool NodeResearched(string node)
        {
            if (HighLogic.CurrentGame != null && HighLogic.CurrentGame.Mode == Game.Modes.SANDBOX)
                return true;
            return ResearchAndDevelopment.GetTechnologyState(node) == RDTech.State.Available;
        }

        public static string RungBTitle()
        {
            string t = ResearchAndDevelopment.GetTechnologyTitle(RungBNode);
            return string.IsNullOrEmpty(t) ? RungBNode : t;
        }
    }
}
