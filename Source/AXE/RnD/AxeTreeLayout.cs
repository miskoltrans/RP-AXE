using System;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe.RnD
{
    /// <summary>
    /// KSP-free port of the HTML rendering prototype's layout + edge routing
    /// (tree/render/prototype/renderer.js): layoutBands + computeSlots + buildLaneRoutes + chamfer/
    /// roundPolyline. Operates on plain LNode/LEdge over UnityEngine.Vector2 — no KSP.UI / Harmony /
    /// RDNode dependency — so it mirrors the prototype 1:1 and is easy to reason about in isolation.
    /// All coordinates are the cfg px "pos space" (x = marginX + tier*tierWidth, y = layout row), the
    /// same space RDNode.pos lives in; the caller converts to world for the arrow hook.
    /// Constants match renderer.js: LANE_PITCH=13, HGAP=6, FAN=[0.18,0.82], CORNER_R=15, CORNER_SEGS=3.
    /// </summary>
    internal static class AxeTreeLayout
    {
        internal class LNode { public string Id; public string Discipline; public int Tier; public int Cost; public float X, Y; }
        internal class LEdge { public string From, To; public List<Vector2> Waypoints; public float TF = 0.5f, TT = 0.5f; public List<Vector2> LaneGeom; }

        private const float HGAP = 6f, FAN_LO = 0.18f, FAN_HI = 0.82f, CORNER_R = 15f;   // lane pitch is now a param (config)
        private const int CORNER_SEGS = 3;

        // ---- discipline-banded layout: each discipline is a horizontal band (by order); x=tier;
        // nodes stacked within their (discipline,tier) cell. Bands grow with mean cost when diffspread.
        internal static void LayoutBands(List<LNode> nodes, List<LEdge> edges, Dictionary<string, LNode> byId,
            Dictionary<string, int> discOrder, float tierWidth, float marginX, float marginY, float nodeH,
            float spacingF, bool diffspread)
        {
            float med = MedianCost(nodes);
            var discs = new List<string>();
            foreach (var n in nodes) if (!discs.Contains(n.Discipline)) discs.Add(n.Discipline);
            discs.Sort((a, b) => Ord(discOrder, a).CompareTo(Ord(discOrder, b)));

            var byDisc = new Dictionary<string, List<LNode>>();
            foreach (var n in nodes) Bucket(byDisc, n.Discipline).Add(n);

            float TH = nodeH;                                   // size the stack to the tile so tiles never overlap
            float SUBH = TH + 26f * spacingF, BANDH = TH + 96f * spacingF;   // scale the GAP, not the tile
            var bandCy = new Dictionary<string, float>();
            float acc = 0f;
            foreach (var d in discs)
            {
                var ns = byDisc.TryGetValue(d, out var lst) ? lst : new List<LNode>();
                var perTier = new Dictionary<int, int>();
                foreach (var n in ns) { perTier.TryGetValue(n.Tier, out int c); perTier[n.Tier] = c + 1; }
                int maxStack = 1;
                foreach (var kv in perTier) if (kv.Value > maxStack) maxStack = kv.Value;
                float h = Mathf.Max(BANDH, maxStack * SUBH + 40f * spacingF);
                if (diffspread && ns.Count > 0)
                {
                    float sum = 0f; foreach (var n in ns) sum += n.Cost;
                    float mc = sum / ns.Count;
                    h *= 0.7f + 0.9f * Mathf.Min(2f, mc / med);
                }
                bandCy[d] = acc + h / 2f; acc += h;
            }

            var cell = new Dictionary<string, List<LNode>>();
            foreach (var n in nodes) Bucket(cell, n.Discipline + "|" + n.Tier).Add(n);
            foreach (var kv in cell)
            {
                var arr = kv.Value;
                arr.Sort((a, b) => { int c = a.Cost.CompareTo(b.Cost); return c != 0 ? c : string.CompareOrdinal(a.Id, b.Id); });
                for (int i = 0; i < arr.Count; i++)
                {
                    var n = arr[i];
                    n.X = marginX + n.Tier * tierWidth;
                    n.Y = marginY + bandCy[n.Discipline] + (i - (arr.Count - 1) / 2f) * SUBH;
                }
            }

            // per-edge through-tier waypoints (one point per spanned tier; straight if non-forward)
            foreach (var e in edges)
            {
                if (!byId.TryGetValue(e.From, out var p) || !byId.TryGetValue(e.To, out var c)) { e.Waypoints = null; continue; }
                int tp = p.Tier, tc = c.Tier;
                var wp = new List<Vector2>();
                if (tc <= tp) { wp.Add(new Vector2(p.X, p.Y)); wp.Add(new Vector2(c.X, c.Y)); }
                else
                    for (int t = tp; t <= tc; t++)
                    {
                        float f = (float)(t - tp) / (tc - tp);
                        float y = t == tp ? p.Y : (t == tc ? c.Y : p.Y + (c.Y - p.Y) * f);
                        wp.Add(new Vector2(marginX + t * tierWidth, y));
                    }
                e.Waypoints = wp;
            }
        }

        // ---- endpoint fan: spread each node's incident edges along its side, ordered by the other
        // end's Y, so they don't converge/cross. fan off (or single edge) -> 0.5 (stock convergence).
        internal static void ComputeSlots(List<LEdge> edges, Dictionary<string, LNode> byId, bool fan)
        {
            var outB = new Dictionary<string, List<LEdge>>();
            var inB = new Dictionary<string, List<LEdge>>();
            foreach (var e in edges)
            {
                if (!byId.ContainsKey(e.From) || !byId.ContainsKey(e.To)) continue;
                Bucket(outB, e.From).Add(e); Bucket(inB, e.To).Add(e);
            }
            foreach (var kv in outB) Spread(kv.Value, e => byId[e.To].Y, (e, t) => e.TF = t, fan);   // source RIGHT side
            foreach (var kv in inB) Spread(kv.Value, e => byId[e.From].Y, (e, t) => e.TT = t, fan);  // target LEFT side
        }

        private static void Spread(List<LEdge> list, Func<LEdge, float> cyOf, Action<LEdge, float> setT, bool fan)
        {
            list.Sort((a, b) => cyOf(a).CompareTo(cyOf(b)));
            int n = list.Count;
            for (int i = 0; i < n; i++)
                setT(list[i], (!fan || n <= 1) ? 0.5f : FAN_LO + (FAN_HI - FAN_LO) * (i / (float)(n - 1)));
        }

        // ---- lane routing: one flat polyline per edge; vertical legs spread into per-gutter lanes
        // (interval-graph colouring) + lane-order by barycentre + horizontal-track separation + rounding.
        internal static void BuildLaneRoutes(List<LNode> nodes, List<LEdge> edges, float nodeW, float nodeH, float lanePitch)
        {
            var xsSet = new SortedSet<float>();
            foreach (var n in nodes) xsSet.Add(n.X);
            var xs = new List<float>(xsSet);
            float X0 = xs.Count > 0 ? xs[0] : 0f;
            float TW = xs.Count > 1 ? xs[1] - xs[0] : 430f;
            Func<float, int> tierOf = x => Mathf.RoundToInt((x - X0) / TW);
            Func<int, float> tierX = t => X0 + t * TW;

            var seg = new Dictionary<int, List<Seg>>();
            var chains = new List<Chain>();
            foreach (var e in edges)
            {
                if (e.Waypoints == null || e.Waypoints.Count < 2) { e.LaneGeom = null; continue; }
                var wps = e.Waypoints; int m = wps.Count;
                var ts = new int[m]; var ys = new float[m];
                for (int i = 0; i < m; i++)
                {
                    ts[i] = tierOf(wps[i].x);
                    float slot = i == 0 ? e.TF : (i == m - 1 ? e.TT : 0.5f);
                    ys[i] = wps[i].y + slot * nodeH;
                }
                chains.Add(new Chain { E = e, Ts = ts, Ys = ys });
                for (int i = 0; i < m - 1; i++)
                    Bucket(seg, ts[i]).Add(new Seg { Lo = Mathf.Min(ys[i], ys[i + 1]), Hi = Mathf.Max(ys[i], ys[i + 1]), Key = e.From + ">" + e.To + "#" + i });
            }

            // greedy interval colouring per gutter -> lane index
            var lane = new Dictionary<string, int>();
            var lanesN = new Dictionary<int, int>();
            foreach (var kv in seg)
            {
                var s = kv.Value; s.Sort((a, b) => a.Lo.CompareTo(b.Lo));
                var ends = new List<float>();
                foreach (var iv in s)
                {
                    int l = -1;
                    for (int j = 0; j < ends.Count; j++) if (ends[j] <= iv.Lo + 1e-6f) { l = j; break; }
                    if (l < 0) { l = ends.Count; ends.Add(iv.Hi); } else ends[l] = iv.Hi;
                    lane[iv.Key] = l;
                }
                lanesN[kv.Key] = ends.Count;
            }

            // reorder lanes by barycentre so tracks run monotonically top->bottom (fewer connector crossings)
            var laneRank = new Dictionary<int, int[]>();
            foreach (var kv in seg)
            {
                int g = kv.Key, nL = lanesN[g];
                var sum = new float[nL]; var cnt = new int[nL];
                foreach (var iv in kv.Value) { int l = lane[iv.Key]; sum[l] += (iv.Lo + iv.Hi) / 2f; cnt[l]++; }
                var order = new List<int>(); for (int i = 0; i < nL; i++) order.Add(i);
                order.Sort((a, b) => (sum[a] / Mathf.Max(1, cnt[a])).CompareTo(sum[b] / Mathf.Max(1, cnt[b])));
                var map = new int[nL];
                for (int newL = 0; newL < nL; newL++) map[order[newL]] = newL;
                laneRank[g] = map;
            }

            Func<int, int, float> laneX = (g, l) =>
            {
                int n = lanesN[g]; float gw = TW - nodeW;
                float pitch = Mathf.Min(lanePitch, gw * 0.8f / Mathf.Max(1, n));   // clamp only if a busy gutter overflows
                float cx = tierX(g) + nodeW + gw / 2f;
                return cx + (l - (n - 1) / 2f) * pitch;
            };

            var built = new List<List<Vector2>>();
            foreach (var ch in chains)
            {
                var ts = ch.Ts; var ys = ch.Ys; var e = ch.E;
                var pts = new List<Vector2> { new Vector2(tierX(ts[0]) + nodeW, ys[0]) };   // right edge of source
                for (int i = 0; i < ts.Length - 1; i++)
                {
                    int g = ts[i];
                    float lx = laneX(g, laneRank[g][lane[e.From + ">" + e.To + "#" + i]]);
                    pts.Add(new Vector2(lx, ys[i]));
                    pts.Add(new Vector2(lx, ys[i + 1]));
                }
                pts.Add(new Vector2(tierX(ts[ts.Length - 1]), ys[ys.Length - 1]));           // left edge of target
                built.Add(pts);
                e.LaneGeom = pts;
            }

            // horizontal-track separation: interior horizontal runs overlapping on a row get bumped to
            // separate tracks (offset y on BOTH endpoints -> adjoining verticals just change length).
            var rows = new Dictionary<int, List<HRun>>();
            foreach (var pts in built)
                for (int i = 1; i < pts.Count - 2; i++)
                    if (Mathf.Abs(pts[i].y - pts[i + 1].y) < 0.5f && Mathf.Abs(pts[i].x - pts[i + 1].x) > 0.5f)
                        Bucket(rows, Mathf.RoundToInt(pts[i].y)).Add(new HRun { Lo = Mathf.Min(pts[i].x, pts[i + 1].x), Hi = Mathf.Max(pts[i].x, pts[i + 1].x), Pts = pts, I = i });
            foreach (var kv in rows)
            {
                var runs = kv.Value; runs.Sort((a, b) => a.Lo.CompareTo(b.Lo));
                var ends = new List<float>();
                foreach (var s in runs)
                {
                    int tk = -1;
                    for (int j = 0; j < ends.Count; j++) if (ends[j] <= s.Lo + 1e-6f) { tk = j; break; }
                    if (tk < 0) { tk = ends.Count; ends.Add(s.Hi); } else ends[tk] = s.Hi;
                    if (tk > 0)
                    {
                        float off = tk * HGAP;
                        s.Pts[s.I] = new Vector2(s.Pts[s.I].x, s.Pts[s.I].y + off);
                        s.Pts[s.I + 1] = new Vector2(s.Pts[s.I + 1].x, s.Pts[s.I + 1].y + off);
                    }
                }
            }

            foreach (var ch in chains)
                if (ch.E.LaneGeom != null) ch.E.LaneGeom = RoundPolyline(ch.E.LaneGeom, CORNER_R, CORNER_SEGS);
        }

        // ---- stock RDNode.chamferCorner: iterative corner-cutting -> 2^segs tessellated points.
        internal static List<Vector2> Chamfer(Vector2 inP, Vector2 cor, Vector2 outP, float r, int segs)
        {
            var pts = new List<Vector2> { cor };
            for (int it = 0; it < segs; it++)
            {
                var np = new List<Vector2>(pts.Count * 2);
                float d = r / Mathf.Pow(2.5f, it + 1);
                for (int k = 0; k < pts.Count; k++)
                {
                    Vector2 v = pts[k];
                    Vector2 prev = k > 0 ? pts[k - 1] : inP;
                    Vector2 next = k < pts.Count - 1 ? pts[k + 1] : outP;
                    np.Add(v + (prev - v).normalized * d);
                    np.Add(v + (next - v).normalized * d);
                }
                pts = np;
            }
            return pts;
        }

        // round every interior corner of an orthogonal polyline, clamping the radius to the shorter
        // adjacent segment so tight lane jogs don't self-overlap. Stays a flat point list.
        internal static List<Vector2> RoundPolyline(List<Vector2> pts, float r, int segs)
        {
            if (pts.Count < 3) return pts;
            var outp = new List<Vector2> { pts[0] };
            for (int i = 1; i < pts.Count - 1; i++)
            {
                Vector2 a = pts[i - 1], v = pts[i], b = pts[i + 1];
                float rr = Mathf.Min(r, 0.45f * Mathf.Min((a - v).magnitude, (b - v).magnitude));
                if (rr < 0.5f) { outp.Add(v); continue; }
                foreach (var p in Chamfer(a, v, b, rr, segs)) outp.Add(p);
            }
            outp.Add(pts[pts.Count - 1]);
            return outp;
        }

        private static float MedianCost(List<LNode> nodes)
        {
            var cs = new List<int>();
            foreach (var n in nodes) if (n.Cost > 0) cs.Add(n.Cost);
            cs.Sort();
            return cs.Count > 0 ? cs[cs.Count / 2] : 1f;
        }

        private static int Ord(Dictionary<string, int> m, string k) => m.TryGetValue(k, out int v) ? v : 99;

        private static List<T> Bucket<K, T>(Dictionary<K, List<T>> d, K key)
        {
            if (!d.TryGetValue(key, out var l)) { l = new List<T>(); d[key] = l; }
            return l;
        }

        private struct Seg { public float Lo, Hi; public string Key; }
        private struct HRun { public float Lo, Hi; public List<Vector2> Pts; public int I; }
        private class Chain { public LEdge E; public int[] Ts; public float[] Ys; }
    }
}
