using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// A primary (non-rechargeable) battery: each frame the resource's maxAmount is ratcheted down to
    /// its current amount, so once drained it can never refill — the finite-power constraint that made
    /// early satellites (Sputnik, Explorer 1, Vanguard) a race against the battery. Ported verbatim from
    /// RP-1 (RP0Debug -> Debug). Pairs with AXE's live-EC avionics draw.
    ///
    /// Available as opt-in infrastructure: add `MODULE { name = ModuleNonRecharge }` (optionally
    /// `resourceName = ...`) to a part config. RP-1 itself ships this module untagged; AXE's natural
    /// home for it is the probe subtree (roadmap P5), so no parts carry it yet.
    /// </summary>
    public class ModuleNonRecharge : PartModule
    {
        [KSPField]
        public string resourceName = "ElectricCharge";

        protected PartResource res;

        public override string GetInfo() =>
            "This module has non-rechargeable " + resourceName + ". Once depleted it cannot be replenished.";

        public override void OnAwake()
        {
            base.OnAwake();
            res = part.Resources.Get(resourceName);
            if (res == null)
                Debug.LogError("[AXE] ModuleNonRecharge: cannot find resource " + resourceName);
        }

        protected void FixedUpdate()
        {
            if (!HighLogic.LoadedSceneIsFlight || vessel == null)
                return;

            if ((object)res != null)
            {
                double target = 0.0001d;
                if (res.amount > target)
                    target = res.amount;

                if (res.maxAmount > target)
                    res.maxAmount = target;
            }
        }
    }
}
