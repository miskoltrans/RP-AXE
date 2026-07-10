using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Blocks EVA from a part except when it's safe to actually climb out — landed / splashed /
    /// pre-launch on the home world, or flying below 20 km. Everywhere else the airlock colliders are
    /// un-tagged so the "EVA" prompt disappears. Models the reality that an X-plane pilot or an early
    /// capsule crew can't just step out at altitude or in space. Ported verbatim from RP-1. Class name
    /// kept so PartValidation / description patches resolve.
    /// </summary>
    public class ModuleNoEVA : PartModule
    {
        protected List<Collider> airlocks = new List<Collider>();
        protected Transform airlock = null;

        public override string GetInfo() =>
            "Cannot EVA from this part. Can still exit when landed on Earth or flying at low (20km) altitude.";

        public override void OnAwake()
        {
            base.OnAwake();
            airlocks.Clear();

            foreach (var c in part.GetComponentsInChildren<Collider>())
                if (c.gameObject.tag == "Airlock")
                    airlocks.Add(c);

            airlock = part.airlock;
        }

        protected void FixedUpdate()
        {
            if (!HighLogic.LoadedSceneIsFlight || vessel == null || vessel.mainBody == null || airlocks == null)
                return;

            bool evaOK = vessel.mainBody == Planetarium.fetch.Home &&
                (vessel.situation == Vessel.Situations.LANDED
                    || vessel.situation == Vessel.Situations.PRELAUNCH
                    || vessel.situation == Vessel.Situations.SPLASHED
                    || (vessel.situation == Vessel.Situations.FLYING && vessel.altitude < 20000));

            foreach (var c in airlocks)
            {
                if (evaOK)
                {
                    if (c.gameObject.tag != "Airlock")
                        c.gameObject.tag = "Airlock";
                }
                else if (c.gameObject.tag == "Airlock")
                {
                    c.gameObject.tag = "Untagged";
                }
            }

            if (evaOK)
            {
                if (part.airlock != airlock)
                    part.airlock = airlock;
            }
            else
            {
                part.airlock = null;
            }
        }
    }
}
