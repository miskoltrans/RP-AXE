using System;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe.RnD
{
    /// <summary>
    /// KSP-free port of the HTML rendering prototype's edge routing + (legacy) layout
    /// (tree/render/prototype/renderer.js): computeSlots + routeOrthoLate + buildLaneRoutes +
    /// chamfer/roundPolyline, plus the legacy in-C# layoutBands/layoutSugiyama. Node POSITIONS for the
    /// live tree come from the emitter (build_tree.py, incl. the Brandes–Köpf coordinate pass) — this
    /// file's job in-game is edge routing only. Operates on plain LNode/LEdge over UnityEngine.Vector2 —
    /// no KSP.UI / Harmony / RDNode dependency — so it mirrors the prototype 1:1 and is easy to reason
    /// about in isolation.
    /// All coordinates are the cfg px "pos space" (x = marginX + tier*tierWidth, y = layout row), the
    /// same space RDNode.pos lives in; the caller converts to world for the arrow hook.
    /// Constants match renderer.js: LANE_PITCH=13, HGAP=6, FAN=[0.18,0.82], CORNER_R=15, CORNER_SEGS=3.
    /// </summary>
    internal static class AxeTreeLayout
    {
        internal class LNode { public string Id; public string Discipline; public int Tier; public int Cost; public float X, Y; }
        internal class LEdge { public string From, To; public List<Vector2> Waypoints; public float TF = 0.5f, TT = 0.5f; public float XF, XFo; public List<Vector2> Geom; }   // Geom = routed polyline; XF/XFo = Fan-X index among in-/out-edges
        internal struct JunctionDot { public Vector2 Pos; public string From, To; }   // junction-bus branch dot (coloured by From's discipline; From/To = the owning edge, for lineage dimming)

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
            float SUBH = TH + 40f * spacingF, BANDH = TH + 96f * spacingF;   // scale the GAP, not the tile (room for the state ring)
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

        // ---- layered (Sugiyama) layout, a 1:1 port of renderer.js layoutSugiyama: tier = column;
        // long edges get DUMMY nodes on every spanned tier so they join the ordering; median sweeps cut
        // crossings; PAV/isotonic coordinate assignment straightens each rank under a min gap; edges are
        // routed through their dummy chain. Sets n.X/n.Y (pos px space) and e.Waypoints like LayoutBands.
        // colw only sets aspect (the caller re-fits X to the stock envelope); spacingY = px per rank unit.
        // NOTE: the Brandes–Köpf coordinate variant lives in the emitter (build_tree.py), not here — the
        // in-game port consumes emitted node positions; C# only re-routes edges. This stays for the
        // legacy in-C# sugiyama mode.
        internal static void LayoutSugiyama(List<LNode> nodes, List<LEdge> edges, Dictionary<string, LNode> byId,
            Dictionary<string, int> discOrder, float colw, float spacingY, float marginX, float marginY, bool diffspread)
        {
            float med = MedianCost(nodes);
            Func<string, float> wv = v => (diffspread && byId.TryGetValue(v, out var bn))
                ? 0.6f + 1.4f * Mathf.Min(2f, bn.Cost / med) : 1f;
            bool IsD(string v) => v.StartsWith("__d", StringComparison.Ordinal);

            // parents (from edges), restricted to modelled nodes
            var parents = new Dictionary<string, List<string>>();
            foreach (var e in edges)
                if (byId.ContainsKey(e.From) && byId.ContainsKey(e.To)) Bucket(parents, e.To).Add(e.From);

            // --- layered graph with dummy nodes on every >1-tier edge ---
            var vtier = new Dictionary<string, int>();
            var seed = new Dictionary<string, int>();
            var layers = new Dictionary<int, List<string>>();
            var prev = new Dictionary<string, List<string>>();
            var nxt = new Dictionary<string, List<string>>();
            var chains = new List<SChain>();
            foreach (var n in nodes)
            {
                vtier[n.Id] = n.Tier;
                seed[n.Id] = discOrder.TryGetValue(n.Discipline, out int o) ? o : 99;
                Bucket(layers, n.Tier).Add(n.Id);
            }
            void AddAdj(string a, string b) { Bucket(nxt, a).Add(b); Bucket(prev, b).Add(a); }
            int dc = 0;
            foreach (var n in nodes)
            {
                string cid = n.Id; int ct = n.Tier;
                if (!parents.TryGetValue(cid, out var ps)) continue;
                foreach (var pid in ps)
                {
                    if (!byId.TryGetValue(pid, out var pn)) continue;
                    int pt = pn.Tier;
                    if (pt >= ct) { AddAdj(pid, cid); chains.Add(new SChain { Pid = pid, Cid = cid, Nodes = new List<string> { pid, cid } }); continue; }
                    var chain = new List<string> { pid };
                    for (int t = pt + 1; t < ct; t++)
                    {
                        string dk = "__d" + (dc++);
                        vtier[dk] = t; seed[dk] = seed[pid];
                        Bucket(layers, t).Add(dk); chain.Add(dk);
                    }
                    chain.Add(cid);
                    for (int i = 0; i < chain.Count - 1; i++) AddAdj(chain[i], chain[i + 1]);
                    chains.Add(new SChain { Pid = pid, Cid = cid, Nodes = chain });
                }
            }

            var order = new List<int>(layers.Keys); order.Sort();
            var rank = new Dictionary<string, int>();
            void Reindex(int t, Comparison<string> key) { layers[t].Sort(key); for (int i = 0; i < layers[t].Count; i++) rank[layers[t][i]] = i; }
            foreach (var t in order) Reindex(t, (a, b) => { int d = seed[a] - seed[b]; return d != 0 ? d : string.CompareOrdinal(a, b); });

            Func<List<string>, double> median = ids =>
            {
                if (ids == null || ids.Count == 0) return -1;
                var vs = new List<int>(ids.Count); foreach (var w in ids) vs.Add(rank[w]); vs.Sort();
                int m = vs.Count >> 1;
                return (vs.Count % 2 == 1) ? vs[m] : (vs[m - 1] + vs[m]) / 2.0;
            };
            Func<int> crossings = () =>
            {
                int c = 0;
                for (int oi = 0; oi < order.Count - 1; oi++)
                {
                    int t = order[oi];
                    var es = new List<int[]>();
                    foreach (var u in layers[t])
                        if (nxt.TryGetValue(u, out var ws))
                            foreach (var w in ws) if (vtier[w] == t + 1) es.Add(new[] { rank[u], rank[w] });
                    es.Sort((a, b) => a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
                    for (int i = 0; i < es.Count; i++) for (int j = i + 1; j < es.Count; j++) if (es[i][1] > es[j][1]) c++;
                }
                return c;
            };

            var orderRev = new List<int>(order); orderRev.Reverse();
            int bestC = int.MaxValue; Dictionary<int, List<string>> bestOrd = null;
            for (int s = 0; s < 8; s++)
            {
                bool asc = s % 2 == 0;
                var adj = asc ? prev : nxt;
                var seq = asc ? order : orderRev;
                foreach (var t in seq)
                {
                    var keep = new Dictionary<string, int>(rank);
                    Reindex(t, (a, b) =>
                    {
                        double ma = (adj.TryGetValue(a, out var la) && la.Count > 0) ? median(la) : keep[a];
                        double mb = (adj.TryGetValue(b, out var lb) && lb.Count > 0) ? median(lb) : keep[b];
                        int cmp = ma < mb ? -1 : (ma > mb ? 1 : 0);
                        return cmp != 0 ? cmp : keep[a] - keep[b];
                    });
                }
                int c = crossings();
                if (bestOrd == null || c < bestC)
                {
                    bestC = c; bestOrd = new Dictionary<int, List<string>>();
                    foreach (var t in order) bestOrd[t] = new List<string>(layers[t]);
                }
            }
            foreach (var t in order) { layers[t] = bestOrd[t]; for (int i = 0; i < layers[t].Count; i++) rank[layers[t][i]] = i; }

            // --- coordinate assignment: isotonic (PAV) pull toward neighbour mean under a min gap ---
            Func<string, string, double> gap = (a, b) => (IsD(a) && IsD(b)) ? 0.12 : ((IsD(a) || IsD(b)) ? 0.45 : 1.0 * (wv(a) + wv(b)) / 2.0);
            Func<List<double>, List<double>> pav = arr =>
            {
                var vals = new List<double>(); var cnts = new List<int>();
                foreach (var x in arr)
                {
                    vals.Add(x); cnts.Add(1);
                    while (vals.Count > 1 && vals[vals.Count - 2] >= vals[vals.Count - 1])
                    {
                        double v2 = vals[vals.Count - 1]; int c2 = cnts[cnts.Count - 1]; vals.RemoveAt(vals.Count - 1); cnts.RemoveAt(cnts.Count - 1);
                        double v1 = vals[vals.Count - 1]; int c1 = cnts[cnts.Count - 1]; vals.RemoveAt(vals.Count - 1); cnts.RemoveAt(cnts.Count - 1);
                        vals.Add((v1 * c1 + v2 * c2) / (c1 + c2)); cnts.Add(c1 + c2);
                    }
                }
                var outp = new List<double>();
                for (int i = 0; i < vals.Count; i++) for (int k = 0; k < cnts[i]; k++) outp.Add(vals[i]);
                return outp;
            };
            var y = new Dictionary<string, double>();
            foreach (var t in order) foreach (var v in layers[t]) y[v] = rank[v];
            for (int it = 0; it < 30; it++)
            {
                var des = new Dictionary<string, double>();
                foreach (var t in order) foreach (var v in layers[t])
                {
                    double sum = 0; int cnt = 0;
                    if (prev.TryGetValue(v, out var pl)) foreach (var w in pl) { sum += y[w]; cnt++; }
                    if (nxt.TryGetValue(v, out var nl)) foreach (var w in nl) { sum += y[w]; cnt++; }
                    des[v] = cnt > 0 ? sum / cnt : y[v];
                }
                foreach (var t in order)
                {
                    var row = layers[t]; if (row.Count == 0) continue;
                    var c = new double[row.Count]; double acc = 0;
                    for (int i = 1; i < row.Count; i++) { acc += gap(row[i - 1], row[i]); c[i] = acc; }
                    var input = new List<double>(row.Count);
                    for (int i = 0; i < row.Count; i++) input.Add(des[row[i]] - c[i]);
                    var z = pav(input);
                    for (int i = 0; i < row.Count; i++) y[row[i]] = z[i] + c[i];
                }
            }
            double miny = double.PositiveInfinity;
            foreach (var kv in y) if (kv.Value < miny) miny = kv.Value;
            Func<string, float> Y = v => (float)((y[v] - miny) * spacingY);

            foreach (var n in nodes) { n.X = marginX + n.Tier * colw; n.Y = marginY + Y(n.Id); }
            var eByKey = new Dictionary<string, LEdge>();
            foreach (var e in edges) eByKey[e.From + ">" + e.To] = e;
            foreach (var ch in chains)
                if (eByKey.TryGetValue(ch.Pid + ">" + ch.Cid, out var e))
                {
                    var wp = new List<Vector2>(ch.Nodes.Count);
                    foreach (var v in ch.Nodes) wp.Add(new Vector2(marginX + vtier[v] * colw, marginY + Y(v)));
                    e.Waypoints = wp;
                }
            foreach (var e in edges)
                if (e.Waypoints == null)
                    e.Waypoints = (byId.ContainsKey(e.From) && byId.ContainsKey(e.To))
                        ? new List<Vector2> { new Vector2(byId[e.From].X, byId[e.From].Y), new Vector2(byId[e.To].X, byId[e.To].Y) }
                        : null;
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
            // Fan X indices (centred, in the sorted order above): XF among edges INTO the same target
            // (ortho-late risers), XFo among edges OUT of the same source (ortho-early risers).
            foreach (var kv in inB) { var l = kv.Value; int n = l.Count; for (int i = 0; i < n; i++) l[i].XF = n <= 1 ? 0f : i - (n - 1) / 2f; }
            foreach (var kv in outB) { var l = kv.Value; int n = l.Count; for (int i = 0; i < n; i++) l[i].XFo = n <= 1 ? 0f : i - (n - 1) / 2f; }
        }

        private static void Spread(List<LEdge> list, Func<LEdge, float> cyOf, Action<LEdge, float> setT, bool fan)
        {
            list.Sort((a, b) => cyOf(a).CompareTo(cyOf(b)));
            int n = list.Count;
            for (int i = 0; i < n; i++)
                setT(list[i], (!fan || n <= 1) ? 0.5f : FAN_LO + (FAN_HI - FAN_LO) * (i / (float)(n - 1)));
        }

        // ---- orthogonal-elbow routing (ortho-late / ortho-early): one flat polyline per edge, endpoint-based
        // (ignores the dummy chain). A 1:1 port of renderer.js routeOrthoLate/routeOrthoEarly. Node box:
        // n.X..n.X+nodeW horizontally; side anchors at n.Y + t*nodeH — nodeH is SIGNED by the caller (Y-flip).
        // Fan X staggers risers on x so edges sharing a riser column read as distinct (late: by target in-edge
        // index XF; early: by source out-edge index XFo). Writes e.Geom, consumed by the GetVectorArray hook.
        private const float BUS_STUB = 28f;   // junction-bus: px from a source's right edge to its shared bus

        private static List<Vector2> Elbow(LNode fn, LNode tn, LEdge e, float nodeW, float nodeH, bool early, bool xfan, float pitch)
        {
            Vector2 p = new Vector2(fn.X + nodeW, fn.Y + e.TF * nodeH);   // source RIGHT side (fan slot)
            Vector2 c = new Vector2(tn.X, tn.Y + e.TT * nodeH);          // target LEFT side (fan slot)
            if (Mathf.Abs(p.y - c.y) < 0.5f) return new List<Vector2> { p, c };   // same row -> straight
            float reach = Mathf.Max(18f, Mathf.Min(60f, (c.x - p.x) * 0.3f));
            float rx = early ? p.x + reach : c.x - reach;                // riser near the source (early) or target (late)
            if (xfan) rx = early ? Mathf.Min(c.x - 10f, Mathf.Max(p.x + 12f, rx + e.XFo * pitch))
                                 : Mathf.Max(p.x + 10f, Mathf.Min(c.x - 12f, rx - e.XF * pitch));
            Vector2 k1 = new Vector2(rx, p.y), k2 = new Vector2(rx, c.y);
            var pts = new List<Vector2> { p };
            pts.AddRange(Chamfer(p, k1, k2, CORNER_R, CORNER_SEGS));
            pts.AddRange(Chamfer(k1, k2, c, CORNER_R, CORNER_SEGS));
            pts.Add(c);
            return pts;
        }

        internal static void RouteOrthoLate(List<LEdge> edges, Dictionary<string, LNode> byId, float nodeW, float nodeH, bool xfan, float xfanPitch)
        {
            foreach (var e in edges)
                e.Geom = (byId.TryGetValue(e.From, out var fn) && byId.TryGetValue(e.To, out var tn))
                    ? Elbow(fn, tn, e, nodeW, nodeH, false, xfan, xfanPitch) : null;
        }

        internal static void RouteOrthoEarly(List<LEdge> edges, Dictionary<string, LNode> byId, float nodeW, float nodeH, bool xfan, float xfanPitch)
        {
            foreach (var e in edges)
                e.Geom = (byId.TryGetValue(e.From, out var fn) && byId.TryGetValue(e.To, out var tn))
                    ? Elbow(fn, tn, e, nodeW, nodeH, true, xfan, xfanPitch) : null;
        }

        // ---- junction-bus (hyperedge): edges leaving a multi-child source SHARE one vertical bus just right
        // of the node — they emanate from the node mid-right into a single trunk, run down it, and peel off at
        // each target row (a JUNCTION DOT is emitted per peel-off; the render draws them). Single-child sources
        // fall back to the ortho-late elbow. Each edge is still one flat polyline (they overlap on the bus).
        internal static void RouteJunctionBus(List<LEdge> edges, Dictionary<string, LNode> byId, float nodeW, float nodeH, List<JunctionDot> dotsOut)
        {
            dotsOut.Clear();
            var outB = new Dictionary<string, List<LEdge>>();
            foreach (var e in edges) if (byId.ContainsKey(e.From) && byId.ContainsKey(e.To)) Bucket(outB, e.From).Add(e);
            var busX = new Dictionary<string, float>();
            foreach (var kv in outB) if (kv.Value.Count >= 2) busX[kv.Key] = byId[kv.Key].X + nodeW + BUS_STUB;
            foreach (var e in edges)
            {
                if (!byId.TryGetValue(e.From, out var fn) || !byId.TryGetValue(e.To, out var tn)) { e.Geom = null; continue; }
                if (!busX.TryGetValue(e.From, out float bx)) { e.Geom = Elbow(fn, tn, e, nodeW, nodeH, false, false, 0f); continue; }   // single child -> elbow
                Vector2 p = new Vector2(fn.X + nodeW, fn.Y + 0.5f * nodeH);   // node mid-right -> clean trunk
                Vector2 c = new Vector2(tn.X, tn.Y + e.TT * nodeH);
                if (Mathf.Abs(p.y - c.y) < 0.5f && c.x <= bx + 2f) { e.Geom = new List<Vector2> { p, c }; continue; }
                dotsOut.Add(new JunctionDot { Pos = new Vector2(bx, c.y), From = e.From, To = e.To });
                e.Geom = RoundPolyline(new List<Vector2> { p, new Vector2(bx, p.y), new Vector2(bx, c.y), c }, CORNER_R, CORNER_SEGS);
            }
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
                if (e.Waypoints == null || e.Waypoints.Count < 2) { e.Geom = null; continue; }
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
                e.Geom = pts;
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
                if (ch.E.Geom != null) ch.E.Geom = RoundPolyline(ch.E.Geom, CORNER_R, CORNER_SEGS);
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
        private class SChain { public string Pid, Cid; public List<string> Nodes; }   // Sugiyama edge chain (pid->cid via dummies)
    }
}
