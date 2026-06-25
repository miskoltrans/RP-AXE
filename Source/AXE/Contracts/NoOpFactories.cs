using Contracts;
using ContractConfigurator;

namespace RPAxe.Contracts
{
    // ContractConfigurator discovers factories by class name minus the "Factory" suffix, so each
    // class below registers the matching contract `type = ...`. These produce an always-complete
    // no-op (see AxeAlwaysComplete) for RP-1 checks we don't implement for the MVP:
    //   - tied to systems we removed (avionics, KCT build/launch-site tracking)
    //   - or low value / few uses for now (no-dock, rendezvous, Kerbalism sample/experiment, impact)
    // Extra config fields on these (descentAngle, builtAt, experiment, distance, ...) are simply
    // ignored. Promote any of these to a real check by giving it its own factory/parameter.

    public class HorizontalLandingFactory : ParameterFactory   // RP-1: glide-style landing
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class AvionicsCheckFactory : ParameterFactory       // avionics removed -> always passes
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class VesselBuiltAtFactory : ParameterFactory       // KCT removed -> always passes
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class RP1NoDockingFactory : ParameterFactory        // 1 use; revisit
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class RP1RendezvousFactory : ParameterFactory       // 3 uses; revisit (real proximity later)
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class ImpactCBFactory : ParameterFactory            // iconic but few uses; revisit
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class RP1HasSamplesFactory : ParameterFactory       // Kerbalism sample check; revisit
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    public class RP1HasExperimentFactory : ParameterFactory    // Kerbalism experiment check; revisit
    { public override ContractParameter Generate(Contract c) => new AxeAlwaysComplete(title); }

    // `type = AXEInstant` — completes immediately (used by the "Begin Program" charter contracts).
    public class AXEInstantFactory : ParameterFactory
    { public override ContractParameter Generate(Contract c) => new AxeInstantComplete(title); }
}
