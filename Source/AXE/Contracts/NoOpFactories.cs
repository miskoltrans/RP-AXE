using Contracts;
using ContractConfigurator;

namespace RPAxe.Contracts
{
    // ContractConfigurator discovers factories by class name minus the "Factory" suffix, so each
    // class below registers the matching contract `type = ...`. These produce an always-complete
    // no-op (see AxeAlwaysComplete) for RP-1 checks we don't implement for the MVP:
    //   - tied to systems we removed (KCT build/launch-site tracking)
    //   - or low value / few uses for now (no-dock)
    // Extra config fields on these (builtAt, ...) are simply ignored. Promote any of these to a real
    // check by giving it its own factory/parameter.
    //
    // Promoted to REAL checks in their own files (no longer no-ops): HorizontalLanding.cs,
    // AvionicsCheck.cs, ImpactCB.cs, Rendezvous.cs (RP1Rendezvous), HasExperiment.cs, HasSamples.cs.

    public class VesselBuiltAtFactory : ParameterFactory       // KCT removed -> always passes
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class RP1NoDockingFactory : ParameterFactory        // 1 use; revisit
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    // `type = AXEInstant` — completes immediately (used by the "Begin Program" charter contracts).
    public class AXEInstantFactory : ParameterFactory
    { public override ContractParameter Generate(Contract c) => new AxeInstantComplete(title); }
}
