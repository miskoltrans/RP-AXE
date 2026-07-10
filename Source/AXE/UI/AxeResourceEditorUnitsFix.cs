using System;
using System.Reflection;
using HarmonyLib;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// RealismOverhaul re-formats resource amounts in the part action window as SI quantities — e.g.
    /// ElectricCharge reads as "43 MJ" (RO_Resources.cfg defines EC with <c>amountUnit = J</c>,
    /// <c>multiplierToUnit = 1000</c>, formatted by <c>ROUtils.ResourceUnits.PrintAmount</c>).
    ///
    /// RO patches the FLIGHT control (<c>UIPartActionResource.UpdateItem</c>) to keep BOTH the
    /// current-amount and max-amount labels formatted every frame. But its EDITOR patch
    /// (<c>PatchUIPartActionResourceEditor</c>) only formats <c>resourceMax</c> in <c>Setup()</c> and
    /// <c>resourceAmnt</c> during a slider drag (<c>onSliderChangeProcess</c>). The editor control's
    /// own per-frame <c>UIPartActionResourceEditor.UpdateItem()</c> is left unpatched, so it rewrites
    /// both labels with the raw number: you see "43298" at rest, and "43MJ / 43298" while dragging
    /// (amount formatted by the slider handler, max clobbered back to raw by UpdateItem).
    ///
    /// This mirrors RO's flight-side fix onto the editor control: a postfix on UpdateItem re-applies
    /// ROUtils formatting to both labels after stock writes them. ROUtils is reached by reflection so
    /// AXE keeps no compile-time dependency on it (and no TextMeshPro reference — the labels are set
    /// reflectively). If ROUtils is absent the postfix no-ops and stock formatting stands.
    /// </summary>
    [HarmonyPatch(typeof(UIPartActionResourceEditor), "UpdateItem")]
    internal static class AxeResourceEditorUnitsFix
    {
        private static bool _init;
        private static bool _active;                       // false => degrade to stock (ROUtils/labels not resolvable)
        private static MethodInfo _printAmount;            // ROUtils.ResourceUnits.PrintAmount(double,int,int,string,bool,bool)
        private static FieldInfo _fResource, _fAmnt, _fMax;   // declared on base UIPartActionResource
        private static PropertyInfo _tmpText;              // TMP_Text.text setter (resolved from a live label)

        private static void Init()
        {
            _init = true;

            const BindingFlags inst = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
            Type baseType = typeof(UIPartActionResource);
            _fResource = baseType.GetField("resource", inst);
            _fAmnt = baseType.GetField("resourceAmnt", inst);
            _fMax = baseType.GetField("resourceMax", inst);

            Type ru = AccessTools.TypeByName("ROUtils.ResourceUnits");
            if (ru != null)
            {
                _printAmount = ru.GetMethod("PrintAmount",
                    BindingFlags.Public | BindingFlags.Static, null,
                    new[] { typeof(double), typeof(int), typeof(int), typeof(string), typeof(bool), typeof(bool) },
                    null);
            }

            _active = _printAmount != null && _fResource != null && _fAmnt != null && _fMax != null;
            if (!_active)
                Debug.Log("[AXE] Editor resource-unit fix inactive (ROUtils.ResourceUnits.PrintAmount or PAW fields not found).");
        }

        [HarmonyPostfix]
        internal static void Postfix(UIPartActionResourceEditor __instance)
        {
            if (!_init) Init();
            if (!_active) return;

            if (!(_fResource.GetValue(__instance) is PartResource res) || res.info == null)
                return;

            object amntLabel = _fAmnt.GetValue(__instance);
            object maxLabel = _fMax.GetValue(__instance);
            if (amntLabel == null || maxLabel == null)
                return;

            if (_tmpText == null)
            {
                _tmpText = amntLabel.GetType().GetProperty("text", BindingFlags.Public | BindingFlags.Instance);
                if (_tmpText == null) { _active = false; return; }
            }

            int resID = res.info.id;   // public accessor for the private _id RO reads (this build isn't publicized)
            _tmpText.SetValue(amntLabel, Format(res.amount, resID), null);
            _tmpText.SetValue(maxLabel, Format(res.maxAmount, resID), null);
        }

        // Mirror RO's UIPartActionResource flight formatting exactly:
        // PrintAmount(amount, resID, sigFigs: 3, precision: amount < 100 ? "F2" : "F0"), SI on, short prefix.
        private static string Format(double amount, int resID)
        {
            string precision = amount < 100.0 ? "F2" : "F0";
            return (string)_printAmount.Invoke(null, new object[] { amount, resID, 3, precision, false, false });
        }
    }
}
