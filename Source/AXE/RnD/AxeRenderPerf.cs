using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using KSP.UI.Screens;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace RPAxe.RnD
{
    /// <summary>
    /// Opt-in (<c>-axe-perf</c>) frame-time + per-bucket profiler for the in-game R&amp;D render port.
    /// Cost when disabled is a single bool read per hooked call site, so it's safe to leave compiled in
    /// (same pattern as DEBUG_DUMP / -axe-autotest). While R&amp;D is open it logs a rolling window of
    /// frame stats plus the cost of the always-on per-frame hooks the port adds on top of stock:
    ///   * <b>raycast</b>   — the extra EventSystem.RaycastAll we run each frame (NodeUnderPointer)
    ///   * <b>lateUpdate</b>— the zoom-to-cursor correction body
    ///   * <b>legendGUI</b> — the OnGUI legend draw (incl. its per-call list alloc + sort)
    /// and runs a one-shot synthetic hover-sweep so the lineage-highlight recolour cost is measured at the
    /// LIVE node count without needing a real mouse (the autotest can't hover). Read <c>[AXE][PERF]</c> in KSP.log.
    /// </summary>
    internal static class AxeRenderPerf
    {
        internal static readonly bool Enabled = HasArg("-axe-perf");

        private const float WINDOW = 2f;   // seconds of R&D-open time per summary line

        private static float _elapsed;
        private static int _frames;
        private static double _frameMaxMs;
        private static readonly List<double> _frameMs = new List<double>(256);
        private static double _rayMs, _lateMs, _guiMs;
        private static int _rayN, _lateN, _guiN;

        internal static long Ts() => Stopwatch.GetTimestamp();
        internal static double Ms(long start) => (Stopwatch.GetTimestamp() - start) * 1000.0 / Stopwatch.Frequency;

        internal static void AddRay(double ms) { _rayMs += ms; _rayN++; }
        internal static void AddLate(double ms) { _lateMs += ms; _lateN++; }
        internal static void AddGui(double ms) { _guiMs += ms; _guiN++; }

        // Once per R&D-open frame (from Update, after the RDController null-guard). Flushes a summary every WINDOW s.
        internal static void Frame()
        {
            double dt = Time.unscaledDeltaTime * 1000.0;
            _frames++; _elapsed += Time.unscaledDeltaTime;
            if (dt > _frameMaxMs) _frameMaxMs = dt;
            _frameMs.Add(dt);
            if (_elapsed >= WINDOW) Flush();
        }

        private static void Flush()
        {
            if (_frameMs.Count == 0) { Reset(); return; }
            double sum = 0; foreach (double m in _frameMs) sum += m;
            double avg = sum / _frameMs.Count;
            _frameMs.Sort();
            double p50 = _frameMs[_frameMs.Count / 2];
            double p95 = _frameMs[Mathf.Clamp((int)(_frameMs.Count * 0.95f), 0, _frameMs.Count - 1)];
            int nodes = RDController.Instance != null && RDController.Instance.nodes != null ? RDController.Instance.nodes.Count : 0;
            Debug.Log($"[AXE][PERF] {_frames}f/{_elapsed:F1}s | frame avg={avg:F2} p50={p50:F2} p95={p95:F2} max={_frameMaxMs:F2}ms (~{1000.0 / Math.Max(0.01, avg):F0}fps) " +
                      $"| raycast {Per(_rayMs, _rayN)} | lateUpdate {Per(_lateMs, _lateN)} | legendGUI {Per(_guiMs, _guiN)} " +
                      $"| routing={AxeTreeMeta.Render.Routing} hover={AxeTreeMeta.Render.Hover} nodes={nodes}");
            Reset();
        }

        private static void Reset()
        {
            _elapsed = 0; _frames = 0; _frameMaxMs = 0; _frameMs.Clear();
            _rayMs = _lateMs = _guiMs = 0; _rayN = _lateN = _guiN = 0;
        }

        private static string Per(double ms, int n)
            => n > 0 ? $"avg={ms / n:F3}ms n={n} ({ms:F1}ms/win)" : "—";

        // One-shot: sweep a synthetic hover across a spread of nodes, timing the lineage-highlight recolour
        // (Apply) + restore (Clear) at the live node count. Started from the host (needs a MonoBehaviour) when
        // the port is ready; ends on a Clear so the tree is left in its normal state. This is the exact path
        // that historically lagged (per AxeTreeRenderHost.TintTile's comment) — now it's a hard number.
        internal static IEnumerator HoverBench()
        {
            yield return new WaitForSecondsRealtime(4f);   // after content-fit + the autotest screenshot settle
            RDController ctrl = RDController.Instance;
            if (ctrl == null || ctrl.nodes == null || ctrl.nodes.Count == 0) { Debug.Log("[AXE][PERF] hover-sweep skipped (no nodes)."); yield break; }

            List<RDNode> nodes = ctrl.nodes;
            int count = nodes.Count;
            int step = Math.Max(1, count / 30);   // ~30 spread samples
            double applySum = 0, applyMax = 0, clearSum = 0, clearMax = 0;
            int nA = 0, nC = 0;
            try
            {
                for (int i = 0; i < count; i += step)
                {
                    RDNode node = nodes[i];
                    if (node == null || node.tech == null) continue;
                    long t0 = Ts(); AxeHighlighter.Apply(ctrl, node); double a = Ms(t0);
                    applySum += a; if (a > applyMax) applyMax = a; nA++;
                    long t1 = Ts(); AxeHighlighter.Clear(ctrl); double c = Ms(t1);
                    clearSum += c; if (c > clearMax) clearMax = c; nC++;
                }
            }
            catch (Exception e) { Debug.LogError("[AXE][PERF] hover-sweep threw: " + e); }
            Debug.Log($"[AXE][PERF] hover-sweep: Apply avg={applySum / Math.Max(1, nA):F3} max={applyMax:F3}ms (n={nA}) | " +
                      $"Clear avg={clearSum / Math.Max(1, nC):F3} max={clearMax:F3}ms (n={nC}) | nodes={count} edges~{EdgeCount(ctrl)}");
        }

        private static int EdgeCount(RDController ctrl)
        {
            int e = 0;
            if (ctrl != null && ctrl.nodes != null)
                foreach (RDNode n in ctrl.nodes)
                    if (n != null && n.parents != null) e += n.parents.Length;
            return e;
        }

        private static bool HasArg(string flag)
        {
            try
            {
                foreach (string a in Environment.GetCommandLineArgs())
                    if (string.Equals(a, flag, StringComparison.OrdinalIgnoreCase)) return true;
            }
            catch { /* args unavailable */ }
            return false;
        }
    }
}
