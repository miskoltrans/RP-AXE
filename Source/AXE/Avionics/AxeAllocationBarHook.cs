using System.Collections;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Editor-only: inserts a live, draggable 3-segment battery/hardware/empty-space bar directly into the
    /// stock PAW for any part carrying <see cref="ModuleAxeAvionics"/>, next to its existing "Avionics Core"
    /// field group.
    ///
    /// There is no stock <c>UI_Control</c> for this — KSP's PAW field-control system (<c>UIPartActionWindow.
    /// AddFieldControl</c>) resolves a field's control type to a pre-built prefab registered with
    /// <c>UIPartActionController</c>, which we can't ship without Unity Editor asset-bundle tooling. Instead
    /// this hooks the stock <c>GameEvents.onPartActionUICreate</c> event (fired by <c>UIPartActionWindow.
    /// CreatePartList</c> every time a PAW is built or refreshed for a part) and parents a hand-built Unity
    /// UI element under the window's own <c>layoutGroup</c> — a plain <c>VerticalLayoutGroup</c> that lays
    /// out any child RectTransform correctly with zero extra registration.
    ///
    /// <c>onPartActionUICreate</c> fires BEFORE <c>CreatePartList</c>'s own field/group loop runs, so our
    /// "AxeAvionics" PAW group doesn't exist yet at the moment of the event — a one-frame coroutine delay
    /// lets that loop finish before we look up the group's content transform to parent into.
    ///
    /// <c>UIPartActionWindow.ClearList()</c> (run on a fresh window Setup) only destroys items it explicitly
    /// tracks, so an untracked widget we add ourselves would otherwise survive a window being recycled for a
    /// different part — every insert checks the existing widget's bound module against the current part and
    /// replaces it if the window was reused, rather than trusting ClearList to have cleaned it up.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EditorAny, false)]
    public class AxeAllocationBarHook : MonoBehaviour
    {
        const string BarName = "AxeAllocationBar";

        void Start() => GameEvents.onPartActionUICreate.Add(OnUICreate);
        void OnDestroy() => GameEvents.onPartActionUICreate.Remove(OnUICreate);

        void OnUICreate(Part p)
        {
            UIPartActionWindow window = p.PartActionWindow;
            if (window == null) return;
            ModuleAxeAvionics axe = p.FindModuleImplementing<ModuleAxeAvionics>();
            if (axe == null) { RemoveBar(window); return; }
            StartCoroutine(InsertNextFrame(window, axe));
        }

        IEnumerator InsertNextFrame(UIPartActionWindow window, ModuleAxeAvionics axe)
        {
            yield return null; // let CreatePartList finish adding fields + groups for this pass
            if (window == null) yield break;

            Transform parent = FindGroupParent(window) ?? window.layoutGroup.transform;
            Transform existing = parent.Find(BarName);
            AxeAllocationBarItem item = existing != null ? existing.GetComponent<AxeAllocationBarItem>() : null;
            if (item != null && item.Module == axe) yield break; // already correctly bound to this part

            if (existing != null) Destroy(existing.gameObject);
            AxeAllocationBarItem.Create(parent, axe, BarName);
        }

        static Transform FindGroupParent(UIPartActionWindow window)
        {
            foreach (UIPartActionItem it in window.ListItems)
            {
                if (it is UIPartActionFieldItem fi && fi.Field?.group?.name == ModuleAxeAvionics.PAWGroup)
                    return fi.transform.parent;
            }
            return null;
        }

        static void RemoveBar(UIPartActionWindow window)
        {
            Transform t = window.layoutGroup.transform.Find(BarName);
            if (t == null)
            {
                foreach (UIPartActionItem it in window.ListItems)
                {
                    Transform found = it.transform.parent?.Find(BarName);
                    if (found != null) { t = found; break; }
                }
            }
            if (t != null) Destroy(t.gameObject);
        }
    }
}
