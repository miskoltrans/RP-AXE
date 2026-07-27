using KSP.UI.Screens;
using KSP.UI.Screens.Editor;
using UnityEngine;

namespace RPAxe.DevParts
{
    /// <summary>
    /// Editor half of dev parts: an app-launcher TOGGLE (VAB/SPH) that flips
    /// <see cref="AxeDevParts"/> on and off, mirroring RP-1's top-right dev-parts button.
    ///
    /// While off, an <c>EditorPartListFilter</c> hides the parts we marked experimental so the list
    /// looks exactly like stock. The filter is deliberately narrow — it only hides parts that are BOTH
    /// experimental and researched-but-unpaid — so parts a contract lends you stay visible either way.
    /// </summary>
    [KSPAddon(KSPAddon.Startup.EditorAny, false)]
    public class AxeDevPartsEditor : MonoBehaviour
    {
        private static Texture2D _icon;
        private static readonly EditorPartListFilter<AvailablePart> _hideDevParts =
            new EditorPartListFilter<AvailablePart>("axeDevPartsFilter",
                p => !(ResearchAndDevelopment.IsExperimentalPart(p) && AxeDevParts.IsUnlockedButNotPurchased(p)));

        private ApplicationLauncherButton _button;
        private bool _filterAdded;

        private void Start()
        {
            if (!AxeDevParts.IsCareer) return;

            GameEvents.onGUIApplicationLauncherReady.Add(AddButton);
            // Instance handler, never a static one: GameEvents' EvtDelegate ctor dereferences
            // evt.Target unguarded and NREs on a static method.
            GameEvents.OnPartPurchased.Add(OnPartPurchased);

            if (ApplicationLauncher.Ready) AddButton();

            // Re-sync on every editor entry: nodes researched since the last visit need marking, and a
            // save made with the toggle on must come back with its parts still placeable.
            ApplyState(AxeDevParts.Enabled);
        }

        private void OnDestroy()
        {
            GameEvents.onGUIApplicationLauncherReady.Remove(AddButton);
            GameEvents.OnPartPurchased.Remove(OnPartPurchased);
            RemoveButton();
        }

        /// <summary>A part bought the normal way is no longer a dev part.</summary>
        private void OnPartPurchased(AvailablePart ap)
        {
            if (ap != null && ResearchAndDevelopment.IsExperimentalPart(ap))
                ResearchAndDevelopment.RemoveExperimentalPart(ap);
        }

        private void ApplyState(bool on)
        {
            if (on) AxeDevParts.MarkAllUnpaidExperimental();
            else AxeDevParts.UnmarkAllUnpaidExperimental();

            SetFilter(!on);
            EditorPartList.Instance?.Refresh();
        }

        private void SetFilter(bool hide)
        {
            if (EditorPartList.Instance == null) return;

            if (hide && !_filterAdded)
            {
                EditorPartList.Instance.ExcludeFilters.AddFilter(_hideDevParts);
                _filterAdded = true;
            }
            else if (!hide && _filterAdded)
            {
                EditorPartList.Instance.ExcludeFilters.RemoveFilter(_hideDevParts);
                _filterAdded = false;
            }
        }

        // --- App launcher button ---

        private void AddButton()
        {
            if (_button != null || ApplicationLauncher.Instance == null) return;

            _button = ApplicationLauncher.Instance.AddModApplication(
                () => Toggle(true), () => Toggle(false), null, null, null, null,
                ApplicationLauncher.AppScenes.VAB | ApplicationLauncher.AppScenes.SPH,
                Icon());

            if (AxeDevParts.Enabled) _button.SetTrue(false);
        }

        private void RemoveButton()
        {
            if (_button != null && ApplicationLauncher.Instance != null)
                ApplicationLauncher.Instance.RemoveModApplication(_button);
            _button = null;
        }

        private void Toggle(bool on)
        {
            if (on == AxeDevParts.Enabled) return;

            AxeDevParts.SetEnabled(on);
            SetFilter(!on);
            EditorPartList.Instance?.Refresh();

            ScreenMessages.PostScreenMessage(
                on ? "Dev parts ON — unresearched-cost parts can be used; you pay when you launch."
                   : "Dev parts OFF — only purchased parts are available.",
                5f, ScreenMessageStyle.UPPER_CENTER);
        }

        /// <summary>Procedural icon (no texture asset): a dashed outline box — a part on approval.</summary>
        private static Texture2D Icon()
        {
            if (_icon != null) return _icon;

            const int N = 38;
            _icon = new Texture2D(N, N, TextureFormat.ARGB32, false);
            Color clear = new Color(0, 0, 0, 0);
            Color line = new Color(0.95f, 0.80f, 0.30f);   // unpaid: amber
            Color fill = new Color(0.95f, 0.80f, 0.30f, 0.18f);

            var px = new Color[N * N];
            const int lo = 8, hi = 29;
            for (int y = 0; y < N; y++)
                for (int x = 0; x < N; x++)
                {
                    bool inBox = x >= lo && x <= hi && y >= lo && y <= hi;
                    bool onEdge = inBox && (x == lo || x == hi || y == lo || y == hi);
                    // Dash the outline: 3 on, 2 off along whichever axis runs the edge.
                    bool dash = ((x == lo || x == hi) ? y : x) % 5 < 3;

                    px[y * N + x] = onEdge && dash ? line : (inBox ? fill : clear);
                }

            _icon.SetPixels(px);
            _icon.Apply();
            return _icon;
        }
    }
}
