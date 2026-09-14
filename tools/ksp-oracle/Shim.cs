// Construct enough of KSP's world to run its own orbit code, with no Unity runtime.
//
// Orbit and PatchedConics are pure managed arithmetic. What stops them running outside the
// game is not the maths, it is that CelestialBody, OrbitDriver and Planetarium derive from
// MonoBehaviour, so they cannot be constructed and they read as "destroyed" to Unity's own
// null checks. Three moves get past that, and all three are load-bearing:
//
//   1. GetUninitializedObject allocates them without running a constructor.
//   2. Their SETTERS reach into Unity (CelestialBody.position writes bodyTransform.position and
//      throws); their GETTERS are pure. So write the backing fields directly.
//   3. UnityEngine.Object's liveness test is only `m_CachedPtr != IntPtr.Zero`, and the
//      both-non-null branch of CompareBaseObjects is plain reference equality. A non-zero fake
//      pointer therefore makes an object read as alive with no native call and nothing ever
//      dereferencing it. Without this, `if (!orbitDriver.celestialBody)` inside
//      PatchedConics._CalculatePatch skips every body and no encounter is ever found.
//
// Never call GetInstanceID() on one of these: that one DOES dereference m_CachedPtr.

using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.Serialization;

namespace RPAxe.KspOracle
{
    internal static class Shim
    {
        const BindingFlags AnyInstance =
            BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly;

        static int _fakePtr = 0x4000;

        internal static T Raw<T>()
        {
            return (T)FormatterServices.GetUninitializedObject(typeof(T));
        }

        internal static void SetField(object target, string name, object value)
        {
            for (Type t = target.GetType(); t != null; t = t.BaseType)
            {
                FieldInfo f = t.GetField(name, AnyInstance);
                if (f != null) { f.SetValue(target, value); return; }
            }
            throw new InvalidOperationException(
                "no field '" + name + "' on " + target.GetType().FullName +
                " -- the KSP build may differ from the one this was written against");
        }

        // Make a Unity object pass `if (obj)` without a native peer. See note 3 above.
        internal static void MakeAlive(UnityEngine.Object o)
        {
            _fakePtr += 0x100;
            SetField(o, "m_CachedPtr", new IntPtr(_fakePtr));
        }

        // Planetarium supplies the clock and the Zup frame that Orbit converts through.
        //
        // inverseRotAngle is deliberately ZERO. In game it tracks the inverse-rotating body's
        // spin, and it is the reason getRelativePositionAtUT does not return the same frame the
        // elements are stated in -- the trap that made crosscheck report a rotation as an epoch
        // error. At zero, Zup is the identity and the two frames coincide, so a state vector
        // handed in comes back out unrotated and the element frame IS the working frame.
        internal static void BootPlanetarium()
        {
            Planetarium pl = Raw<Planetarium>();
            MakeAlive(pl);
            pl.time = 0.0;
            pl.orbits = new List<OrbitDriver>();
            pl.inverseRotAngle = 0.0;
            Planetarium.fetch = pl;
            // PlanetaryFrame, NOT SetFrame: SetFrame takes radians, and the 90 here is degrees.
            // The game builds Zup as PlanetaryFrame(0, 90, InverseRotAngle); at zero that works
            // out to exactly the identity, which is the whole reason the element frame and the
            // frame getRelativePositionAtUT returns can be made to coincide here.
            Planetarium.CelestialFrame.PlanetaryFrame(0.0, 90.0, 0.0, ref Planetarium.Zup);
        }

        internal static CelestialBody MakeBody(string name, double mu, double radius, double soi)
        {
            CelestialBody b = Raw<CelestialBody>();
            MakeAlive(b);
            b.bodyName = name;
            b.gravParameter = mu;
            b.Radius = radius;
            b.sphereOfInfluence = soi;                 // +Infinity for the root, which KSP tests for
            b.orbitingBodies = new List<CelestialBody>();
            b.atmosphereDepth = 0.0;
            SetField(b, "_position", Vector3d.zero);   // the setter would write bodyTransform
            return b;
        }

        // Give `child` an orbit about `parent` and register it where PatchedConics looks.
        //
        // CelestialBody.orbit is read-only and returns orbitDriver.orbit, so the driver is not
        // optional bookkeeping -- it is the only way to hang an orbit on a body. And the driver
        // must be in Planetarium.Orbits, because _CalculatePatch iterates exactly that list to
        // decide which bodies can be encountered.
        internal static void Attach(CelestialBody child, CelestialBody parent, Orbit orbit)
        {
            OrbitDriver od = Raw<OrbitDriver>();
            MakeAlive(od);
            SetField(od, "orbit", orbit);
            od.celestialBody = child;
            od.referenceBody = parent;
            od.updateMode = OrbitDriver.UpdateMode.UPDATE;
            child.orbitDriver = od;
            parent.orbitingBodies.Add(child);
            Planetarium.fetch.orbits.Add(od);
        }
    }
}
