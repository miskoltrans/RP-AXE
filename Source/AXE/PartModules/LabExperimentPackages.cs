using System.Text.RegularExpressions;

namespace RPAxe
{
    /// <summary>
    /// Marker modules that say "this part carries instrument class X". They have no behaviour: the
    /// only thing that reads them is Kerbalism, which evaluates an experiment's
    /// <c>requirements = Module:XLabExperimentPackage</c> as
    /// <c>Lib.FindModules(vessel.protoVessel, name).Count &gt; 0</c>. Carrying the tag is the whole job.
    ///
    /// WHY THESE LIVE HERE. The KerbalismLab suite came from KerbalismLabExperimentsExpandedContinued,
    /// and AXE vendored its configs -- the experiment definitions and the InstrumentTagging patches that
    /// put these MODULEs on parts -- without its assembly, which is where the classes were. KSP drops a
    /// MODULE whose type it cannot resolve (one "Cannot find a PartModule of typename" line per part,
    /// 57 of them, among thousands), so every tag silently failed to apply and 58 of the 65 lab
    /// experiments could never satisfy their requirement. Nothing errored at the point of use: the
    /// experiments simply never became available. See docs/BUG-CLASSES.md family A2.
    ///
    /// Re-pointing the tags onto AXE's actual instruments is already done in
    /// design/Science/KerbalismLab/InstrumentTagging.cfg (RO magnetometers, the RO TV-camera ladder,
    /// the SSPX telescope dome, and so on). Defining the classes is what makes that work reach the game.
    ///
    /// Names must match the config strings exactly -- KSP resolves a MODULE by CLASS name only
    /// (AssemblyLoader.GetClassByName), so the namespace differing from upstream's is fine.
    /// </summary>
    public abstract class BaseLabExperimentPackage : PartModule
    {
        /// <summary>"MultispectralLabExperimentPackage" -> "Multispectral Lab Experiment Package".</summary>
        public override string GetInfo() =>
            Regex.Replace(GetType().Name, "(?<=[a-z])(?=[A-Z])", " ");
    }

    public class AtmosphereLabExperimentPackage : BaseLabExperimentPackage { }
    public class BiologyLabExperimentPackage : BaseLabExperimentPackage { }
    public class DrillLabExperimentPackage : BaseLabExperimentPackage { }
    public class FluidLabExperimentPackage : BaseLabExperimentPackage { }
    public class GravityLabExperimentPackage : BaseLabExperimentPackage { }
    public class HighEnergyLabExperimentPackage : BaseLabExperimentPackage { }
    public class MagnetometerLabExperimentPackage : BaseLabExperimentPackage { }
    public class MaterialsLabExperimentPackage : BaseLabExperimentPackage { }
    public class MultispectralLabExperimentPackage : BaseLabExperimentPackage { }
    public class PlasmaLabExperimentPackage : BaseLabExperimentPackage { }
    public class RadarLabExperimentPackage : BaseLabExperimentPackage { }
    public class RadioLabExperimentPackage : BaseLabExperimentPackage { }
    public class SpectrometerLabExperimentPackage : BaseLabExperimentPackage { }
    public class SurfaceLabExperimentPackage : BaseLabExperimentPackage { }
    public class TelescopeLabExperimentPackage : BaseLabExperimentPackage { }
    public class VisualLabExperimentPackage : BaseLabExperimentPackage { }
}
