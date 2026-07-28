using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace RPAxe
{
    /// <summary>
    /// The inline 3-segment battery/hardware/empty-space bar itself, procedurally built from plain Unity UI
    /// primitives (no prefab/asset bundle) and parented into the PAW by <see cref="AxeAllocationBarHook"/>.
    /// Two draggable handles (battery/hardware boundary, hardware/empty boundary) write the module's real
    /// battVolume/hwVolume every drag-move frame via <see cref="ModuleAxeAvionics.LiveUpdateSplit"/> --
    /// whatever the last dragged position is IS the state, so every readout (mass, cost, capacity, EC draw,
    /// penalty, endurance, even the actual RealFuels battery pool) updates in real time through the normal
    /// update pipeline, with no separate preview/pending shadow copy to keep in sync. Only the (comparatively
    /// expensive) symmetry sync + onEditorShipModified event are deferred to release, via
    /// <see cref="ModuleAxeAvionics.CommitAllocationDrag"/>.
    ///
    /// Unguided cores have no adjustable hardware size (RP-1: Science-Core mass is a flat per-tier number,
    /// not volume-derived) — the second handle is hidden and only the battery/hardware boundary is
    /// draggable; the hardware segment's WIDTH stays constant while its start position tracks the battery
    /// boundary (LiveUpdateSplit substitutes the fixed tier value for hardware regardless of what's dragged
    /// in that case).
    /// </summary>
    public class AxeAllocationBarItem : MonoBehaviour
    {
        const float HandleWidth = 18f;
        const float HandleHalfWidth = HandleWidth / 2f;

        public ModuleAxeAvionics Module { get; private set; }

        RectTransform _track;
        RectTransform _battRect, _hwRect, _emptyRect;
        RectTransform _handleBH, _handleHE;
        Text _label;

        public static GameObject Create(Transform parent, ModuleAxeAvionics module, string name)
        {
            var root = new GameObject(name, typeof(RectTransform));
            root.transform.SetParent(parent, false);
            var rt = (RectTransform)root.transform;
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.sizeDelta = new Vector2(0f, 58f);

            var le = root.AddComponent<LayoutElement>();
            le.minHeight = 58f;
            le.preferredHeight = 58f;
            le.flexibleWidth = 1f;

            var item = root.AddComponent<AxeAllocationBarItem>();
            item.Module = module;
            item.BuildUI(rt);
            return root;
        }

        void BuildUI(RectTransform root)
        {
            var labelGO = new GameObject("Label", typeof(RectTransform));
            labelGO.transform.SetParent(root, false);
            var labelRT = (RectTransform)labelGO.transform;
            labelRT.anchorMin = new Vector2(0f, 1f);
            labelRT.anchorMax = new Vector2(1f, 1f);
            labelRT.pivot = new Vector2(0.5f, 1f);
            // Two lines now (volumes, then masses), so the rect is tall enough for both and vertical
            // overflow is allowed rather than truncated -- a clipped mass readout would be worse than a
            // slightly crowded one.
            labelRT.sizeDelta = new Vector2(0f, 32f);
            _label = labelGO.AddComponent<Text>();
            _label.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            _label.fontSize = 11;
            _label.alignment = TextAnchor.UpperCenter;
            _label.verticalOverflow = VerticalWrapMode.Overflow;
            _label.color = Color.white;

            // Inset the track by half the handle width on each side (pixels, not a % anchor) so a handle
            // sitting at fraction 0 or 1 -- e.g. the hw/empty handle under the spec-locked 25/75/0 default
            // split, which computes to fraction 1.0 exactly -- is always fully inside the widget's own
            // bounds instead of overhanging past the edge.
            var trackGO = new GameObject("Track", typeof(RectTransform));
            trackGO.transform.SetParent(root, false);
            _track = (RectTransform)trackGO.transform;
            _track.anchorMin = new Vector2(0f, 0f);
            _track.anchorMax = new Vector2(1f, 1f);
            _track.offsetMin = new Vector2(HandleHalfWidth, 4f);
            _track.offsetMax = new Vector2(-HandleHalfWidth, -34f); // leave room for the 2-line label above

            _battRect = MakeSegment(_track, "Batt", new Color(0.25f, 0.75f, 0.35f));
            _hwRect = MakeSegment(_track, "Hw", new Color(0.45f, 0.55f, 0.95f));
            _emptyRect = MakeSegment(_track, "Empty", new Color(0.35f, 0.35f, 0.35f));

            // Distinct shapes for the two handles (battery/hardware boundary hangs a triangle from the top,
            // hardware/empty boundary rises a triangle from the bottom) rather than two identical lines --
            // makes both markers unmistakable even if they land at the same horizontal position.
            _handleBH = MakeHandle(_track, "HandleBH", fromTop: true);
            _handleHE = MakeHandle(_track, "HandleHE", fromTop: false);
            _handleBH.gameObject.AddComponent<AxeAllocationDragHandle>().Init(this, isFirstHandle: true);
            _handleHE.gameObject.AddComponent<AxeAllocationDragHandle>().Init(this, isFirstHandle: false);

            RefreshFromModule();
        }

        static RectTransform MakeSegment(Transform parent, string name, Color color)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            var rt = (RectTransform)go.transform;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            go.AddComponent<Image>().color = color;
            return rt;
        }

        // A wide (18px) near-transparent hit zone spanning the full track height (easy to grab), with a
        // small triangular visual marker (raycastTarget = false, so it doesn't shadow the parent's own
        // raycast hit) -- hanging from the top pointing down for the battery/hardware handle, rising from
        // the bottom pointing up for the hardware/empty handle.
        static RectTransform MakeHandle(Transform parent, string name, bool fromTop)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);
            var rt = (RectTransform)go.transform;
            rt.anchorMin = new Vector2(0f, 0f);
            rt.anchorMax = new Vector2(0f, 1f);
            rt.sizeDelta = new Vector2(HandleWidth, 0f);
            go.AddComponent<Image>().color = new Color(1f, 1f, 1f, 0.12f);

            var triGO = new GameObject("Triangle", typeof(RectTransform));
            triGO.transform.SetParent(go.transform, false);
            var triRT = (RectTransform)triGO.transform;
            triRT.anchorMin = new Vector2(0.5f, fromTop ? 1f : 0f);
            triRT.anchorMax = new Vector2(0.5f, fromTop ? 1f : 0f);
            triRT.pivot = new Vector2(0.5f, fromTop ? 1f : 0f);
            triRT.sizeDelta = new Vector2(HandleWidth - 4f, 14f);
            var tri = triGO.AddComponent<AxeTriangleGraphic>();
            tri.PointDown = fromTop;
            tri.color = Color.white;
            tri.raycastTarget = false;

            return rt;
        }

        // Module's own state is the single live source of truth (even while dragging -- see
        // LiveUpdateSplit), so this can refresh unconditionally every frame, no dragging-flag gate needed.
        void Update()
        {
            if (Module == null) { Destroy(gameObject); return; }
            RefreshFromModule();
        }

        void RefreshFromModule()
        {
            float v = Module.CachedVolumeLiters;
            if (v <= 0f) return;
            float battFrac = Mathf.Clamp01(Module.battVolume * 1000f / v);
            float hwFrac = Mathf.Clamp01(Module.hwVolume * 1000f / v);
            SetFractions(battFrac, hwFrac);
            float emptyL = Mathf.Max(0f, v - Module.battVolume * 1000f - Module.hwVolume * 1000f);
            // "other" is whatever the part weighs beyond the two segments this bar controls (Kerbalism's
            // HardDrive, ProceduralPart hollow mass): shown so the line reconciles to the total instead of
            // looking like an arithmetic error. Clamped at 0 -- it can go very slightly negative on rounding.
            float otherT = Mathf.Max(0f, Module.totalPartMass - Module.batteryMass - Module.avionicsMass);
            _label.text = $"{Module.battVolume * 1000f:0} L batt | {Module.hwVolume * 1000f:0} L hw | {emptyL:0} L empty" +
                          $"   cap {Module.capacityTons:0.##} t   pen {Module.penaltyPercent:0}%\n" +
                          $"{Module.batteryMass:0.000} t batt | {Module.avionicsMass:0.000} t hw | {otherT:0.000} t other" +
                          $"   total {Module.totalPartMass:0.000} t";
        }

        void SetFractions(float battFrac, float hwFrac)
        {
            battFrac = Mathf.Clamp01(battFrac);
            float heBoundary = Mathf.Clamp01(battFrac + Mathf.Clamp01(hwFrac));
            _battRect.anchorMin = new Vector2(0f, 0f); _battRect.anchorMax = new Vector2(battFrac, 1f);
            _hwRect.anchorMin = new Vector2(battFrac, 0f); _hwRect.anchorMax = new Vector2(heBoundary, 1f);
            _emptyRect.anchorMin = new Vector2(heBoundary, 0f); _emptyRect.anchorMax = new Vector2(1f, 1f);
            _handleBH.anchorMin = new Vector2(battFrac, 0f); _handleBH.anchorMax = new Vector2(battFrac, 1f);
            _handleHE.anchorMin = new Vector2(heBoundary, 0f); _handleHE.anchorMax = new Vector2(heBoundary, 1f);
            _handleHE.gameObject.SetActive(Module.guidanceEnabled);
        }

        // Called by AxeAllocationDragHandle every drag-move frame with the INCREMENTAL screen-space delta
        // (not an absolute reprojected position) -- robust to the cursor leaving the track's own bounds
        // (e.g. dragging past the PAW window edge), since a delta is always well-defined regardless of
        // where the cursor physically is. Writes straight through to the module every frame.
        public void OnHandleDrag(bool isFirstHandle, float deltaFrac)
        {
            float v = Module.CachedVolumeLiters;
            if (v <= 0f) return;
            float battFrac = Mathf.Clamp01(Module.battVolume * 1000f / v);
            float hwFrac = Mathf.Clamp01(Module.hwVolume * 1000f / v);
            if (isFirstHandle)
            {
                if (Module.guidanceEnabled)
                {
                    // battery/hardware boundary: the hardware/empty boundary stays fixed while dragging
                    // this handle -- hardware absorbs the change (grows/shrinks to compensate).
                    float heBoundary = battFrac + hwFrac;
                    battFrac = Mathf.Clamp(battFrac + deltaFrac, 0f, heBoundary);
                    hwFrac = heBoundary - battFrac;
                }
                else
                {
                    // Unguided: hardware's width is fixed (flat per-tier mass, not volume-derived), so
                    // battery can occupy at most (1 - hwFrac) -- otherwise the two could be dragged to sum
                    // past 100% of the box, since hardware never gives up any of its reserved share.
                    battFrac = Mathf.Clamp(battFrac + deltaFrac, 0f, Mathf.Clamp01(1f - hwFrac));
                }
            }
            else
            {
                float heBoundary = Mathf.Clamp((battFrac + hwFrac) + deltaFrac, battFrac, 1f);
                hwFrac = heBoundary - battFrac;
            }
            Module.LiveUpdateSplit(battFrac * v / 1000f, hwFrac * v / 1000f);
            // Re-read from the module rather than trusting our own battFrac/hwFrac -- LiveUpdateSplit may
            // have further clamped (e.g. the endurance floor), and this keeps a single source of truth.
            RefreshFromModule();
        }

        // Called on drag release: values are already live-correct, just commit (symmetry sync + the one
        // onEditorShipModified event).
        public void OnHandleDragEnd(bool isFirstHandle) => Module.CommitAllocationDrag();
    }

    /// <summary>Tiny drag-input adapter: translates pointer drag movement into a 0-1 fraction-per-frame
    /// delta along the bar's track and forwards it to the owning <see cref="AxeAllocationBarItem"/>.
    /// Implements IPointerDownHandler/IBeginDragHandler (even as no-ops) so THIS object -- not the PAW
    /// window itself, which also implements IDragHandler to let the player reposition the whole window --
    /// claims the ensuing drag gesture.</summary>
    public class AxeAllocationDragHandle : MonoBehaviour, IPointerDownHandler, IBeginDragHandler, IDragHandler, IEndDragHandler
    {
        AxeAllocationBarItem _owner;
        bool _isFirst;
        RectTransform _track;
        float _canvasScale = 1f;

        public void Init(AxeAllocationBarItem owner, bool isFirstHandle)
        {
            _owner = owner;
            _isFirst = isFirstHandle;
            _track = transform.parent as RectTransform;
            Canvas canvas = GetComponentInParent<Canvas>();
            if (canvas != null && canvas.scaleFactor > 0f) _canvasScale = canvas.scaleFactor;
        }

        public void OnPointerDown(PointerEventData eventData) { }
        public void OnBeginDrag(PointerEventData eventData) { }

        public void OnDrag(PointerEventData eventData)
        {
            if (_track == null || _track.rect.width <= 0f) return;
            // eventData.delta is raw screen pixels; the track's rect is in canvas-local units, which differ
            // from screen pixels whenever the player's UI Scale setting isn't 1 -- correct for it so drag
            // speed feels consistent regardless of that setting.
            float deltaFrac = (eventData.delta.x / _canvasScale) / _track.rect.width;
            _owner.OnHandleDrag(_isFirst, deltaFrac);
        }

        public void OnEndDrag(PointerEventData eventData) => _owner.OnHandleDragEnd(_isFirst);
    }

    /// <summary>A small procedurally-drawn triangle (no sprite/asset needed): PointDown hangs from the top
    /// edge pointing down, !PointDown rises from the bottom edge pointing up. Purely decorative
    /// (raycastTarget left false by callers) -- the wider parent handle rect is what's actually clickable.</summary>
    public class AxeTriangleGraphic : MaskableGraphic
    {
        public bool PointDown;

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            Rect r = GetPixelAdjustedRect();
            UIVertex v = UIVertex.simpleVert;
            v.color = color;
            float xMid = (r.xMin + r.xMax) / 2f;

            if (PointDown)
            {
                v.position = new Vector3(r.xMin, r.yMax, 0f); vh.AddVert(v);
                v.position = new Vector3(r.xMax, r.yMax, 0f); vh.AddVert(v);
                v.position = new Vector3(xMid, r.yMin, 0f); vh.AddVert(v);
            }
            else
            {
                v.position = new Vector3(r.xMin, r.yMin, 0f); vh.AddVert(v);
                v.position = new Vector3(r.xMax, r.yMin, 0f); vh.AddVert(v);
                v.position = new Vector3(xMid, r.yMax, 0f); vh.AddVert(v);
            }
            vh.AddTriangle(0, 1, 2);
        }
    }
}
