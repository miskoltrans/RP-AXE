using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace RPAxe.RnD
{
    /// <summary>
    /// Loads the render metadata + settings the in-game R&amp;D tree lacks:
    ///   RPAXE_TREEMETA (GameData/RP-AXE/design/Tree/AxeTreeMeta.cfg, emitted by tools/build_tree.py)
    ///     — per-node discipline/tier/cost + the discipline table + layout constants. Stock RDNode has
    ///       no discipline/tier field and icons collide across disciplines, so this is the only way to
    ///       recover them. Keyed by tech id (= RDNode.tech.techID = the cfg RDNode `id`).
    ///   RPAXE_RENDER (GameData/RP-AXE/RenderSettings.cfg) — layout / laneRouting / fan toggles.
    /// Read once via GameDatabase.Instance.GetConfigNodes; callers invoke EnsureLoaded() before use.
    /// No KSP.UI dependency — pure ConfigNode/GameDatabase so it is trivial to reason about + reuse.
    /// </summary>
    internal static class AxeTreeMeta
    {
        // Experiments is null when the node unlocks none (the common case) — see LoadMeta.
        internal struct NodeMeta { public string Discipline; public int Tier; public int Cost; public ExperimentMeta[] Experiments; }
        /// <summary>One science unlock that is NOT a part: a Kerbalism `Configure` SETUP (or a
        /// techRequired EXPERIMENT_DEFINITION) gated on this node. Stock R&amp;D only lists parts, so
        /// without this a node whose whole payload is science shows nothing at all.</summary>
        internal struct ExperimentMeta { public string Name; public int Sci; public string Group; }
        internal struct DiscMeta { public int Order; public Color Color; public string Icon; public string Title; }
        internal struct Settings
        {
            public string Layout; public bool LaneRouting; public bool Fan; public float LanePitch;
            public bool DiscColor; public bool Legend; public bool Hover;
            public string Routing;   // edge routing: lanes | ortho-late | ortho-early | junction | stock
            public bool FlipY;       // stock-mode routing: fan-side sign; flip if edges attach on the wrong side
            public bool Xfan;        // ortho elbows: stagger risers sharing a column on x (Fan X)
            public float XfanPitch;  // px between staggered risers
            public bool SolidBg;     // replace the stock R&D grid with a solid backdrop (matches the prototype)
            public bool Avoid;       // detour edges around node boxes they'd otherwise cross
            public bool OrDash;      // dash the edges into an anyToUnlock node (stock has no OR visual at all)
            // routing override is active (we replace stock elbows) for any non-stock style
            public bool RouteOverride => Routing == "lanes" || Routing == "ortho-late" || Routing == "ortho-early" || Routing == "junction";
        }

        // Layout constants (shared with build_tree.py; fallbacks match its X0/TIERW/MARGIN defaults).
        internal static float MarginX = -2568f, MarginY = 711f, TierWidth = 430f, NodeSize = 58f;
        internal static readonly Dictionary<string, NodeMeta> Nodes = new Dictionary<string, NodeMeta>();
        internal static readonly Dictionary<string, DiscMeta> Disciplines = new Dictionary<string, DiscMeta>();
        // Default = stock (feature off) so a missing/absent cfg can never brick the scene.
        internal static Settings Render = new Settings { Layout = "stock", LaneRouting = true, Routing = "lanes", FlipY = true, Xfan = true, XfanPitch = 10f, Fan = true, LanePitch = 13f, DiscColor = true, Legend = true, Hover = true, SolidBg = true, Avoid = true, OrDash = true };
        internal static bool Loaded { get; private set; }

        internal static void EnsureLoaded()
        {
            if (Loaded) return;
            Loaded = true;
            LoadMeta();
            LoadSettings();
            Debug.Log($"[AXE] tree meta: {Nodes.Count} nodes / {Disciplines.Count} disciplines; " +
                      $"render layout={Render.Layout} routing={Render.Routing} fan={Render.Fan}");
        }

        // Full (un-tinted) discipline colour for a tech id — used by the lineage highlight to pop the lineage.
        internal static bool TryDisciplineColor(string techID, out Color color)
        {
            color = Color.white;
            if (!string.IsNullOrEmpty(techID) && Nodes.TryGetValue(techID, out NodeMeta m)
                && Disciplines.TryGetValue(m.Discipline, out DiscMeta d)) { color = d.Color; return true; }
            return false;
        }

        private static void LoadMeta()
        {
            ConfigNode[] roots = GameDatabase.Instance.GetConfigNodes("RPAXE_TREEMETA");
            if (roots == null || roots.Length == 0)
            {
                Debug.LogWarning("[AXE][TreeMeta] no RPAXE_TREEMETA found -- falling back to compiled-in "
                    + "layout constants, which drift from build_tree.py's the moment either changes.");
                return;
            }
            ConfigNode root = roots[0];
            ParseFloat(root, "marginX", ref MarginX);
            ParseFloat(root, "marginY", ref MarginY);
            ParseFloat(root, "tierWidth", ref TierWidth);
            ParseFloat(root, "nodeSize", ref NodeSize);
            foreach (ConfigNode n in root.GetNodes("Node"))
            {
                string id = n.GetValue("id");
                if (string.IsNullOrEmpty(id)) continue;
                Nodes[id] = new NodeMeta
                {
                    Discipline = n.GetValue("discipline") ?? "",
                    Tier = ParseInt(n.GetValue("tier"), 0),
                    Cost = ParseInt(n.GetValue("cost"), 0),
                    Experiments = ParseExperiments(n.GetValues("experiment")),
                };
            }
            foreach (ConfigNode d in root.GetNodes("Discipline"))
            {
                string key = d.GetValue("key");
                if (string.IsNullOrEmpty(key)) continue;
                Disciplines[key] = new DiscMeta
                {
                    Order = ParseInt(d.GetValue("order"), 99),
                    Color = ParseHex(d.GetValue("color")),
                    Icon = d.GetValue("icon") ?? "",
                    Title = d.GetValue("title") ?? key,
                };
            }
        }

        private static void LoadSettings()
        {
            ConfigNode[] roots = GameDatabase.Instance.GetConfigNodes("RPAXE_RENDER");
            if (roots == null || roots.Length == 0)
            {
                Debug.LogWarning("[AXE][TreeMeta] no RPAXE_RENDER found -- keeping the stock R&D renderer.");
                return;   // no cfg -> keep the safe default (stock)
            }
            ConfigNode r = roots[roots.Length - 1];            // last wins (ModuleManager-friendly)
            string layout = r.GetValue("layout");
            Render.Layout = string.IsNullOrEmpty(layout) ? "bands" : layout.Trim().ToLowerInvariant();
            Render.LaneRouting = ParseBool(r.GetValue("laneRouting"), true);
            // `routing` selects the edge-routing style; if absent, derive from the legacy laneRouting bool.
            string routing = r.GetValue("routing");
            Render.Routing = !string.IsNullOrEmpty(routing) ? routing.Trim().ToLowerInvariant()
                                                            : (Render.LaneRouting ? "lanes" : "stock");
            Render.FlipY = ParseBool(r.GetValue("flipY"), true);
            Render.Xfan = ParseBool(r.GetValue("xfan"), true);
            if (float.TryParse(r.GetValue("xfanPitch"), NumberStyles.Float, CultureInfo.InvariantCulture, out float xp) && xp >= 0f)
                Render.XfanPitch = xp;
            Render.Fan = ParseBool(r.GetValue("fan"), true);
            if (float.TryParse(r.GetValue("lanePitch"), NumberStyles.Float, CultureInfo.InvariantCulture, out float lp) && lp >= 0f)
                Render.LanePitch = lp;   // 0 = all lanes collapse to the gutter centre (single line)
            Render.DiscColor = ParseBool(r.GetValue("discColor"), true);
            Render.Legend = ParseBool(r.GetValue("legend"), true);
            Render.Hover = ParseBool(r.GetValue("hover"), true);
            Render.SolidBg = ParseBool(r.GetValue("solidBg"), true);
            Render.Avoid = ParseBool(r.GetValue("avoid"), true);
            Render.OrDash = ParseBool(r.GetValue("orDash"), true);
        }

        /// <summary>`experiment = name|scienceCap|configureGroup` (repeated), as emitted by
        /// build_tree.py's emit_treemeta. Empty science / group fields are allowed and mean
        /// "unknown" — the tooltip just prints less. Null when the node unlocks no experiment,
        /// which keeps the common case allocation-free.</summary>
        private static ExperimentMeta[] ParseExperiments(string[] raw)
        {
            if (raw == null || raw.Length == 0) return null;
            var list = new List<ExperimentMeta>(raw.Length);
            foreach (string line in raw)
            {
                if (string.IsNullOrEmpty(line)) continue;
                string[] f = line.Split('|');
                string name = f[0].Trim();
                if (name.Length == 0) continue;
                list.Add(new ExperimentMeta
                {
                    Name = name,
                    Sci = f.Length > 1 ? ParseInt(f[1].Trim(), 0) : 0,
                    Group = f.Length > 2 ? f[2].Trim() : "",
                });
            }
            return list.Count > 0 ? list.ToArray() : null;
        }

        private static void ParseFloat(ConfigNode n, string key, ref float dst)
        {
            if (float.TryParse(n.GetValue(key), NumberStyles.Float, CultureInfo.InvariantCulture, out float v)) dst = v;
        }

        private static int ParseInt(string s, int dflt)
            => int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) ? v : dflt;

        private static bool ParseBool(string s, bool dflt)
            => bool.TryParse(s, out bool v) ? v : dflt;

        // Parse "#rrggbb" (manual, so we don't depend on ColorUtility being in the referenced modules).
        private static Color ParseHex(string s)
        {
            if (!string.IsNullOrEmpty(s) && s[0] == '#') s = s.Substring(1);
            if (!string.IsNullOrEmpty(s) && s.Length >= 6
                && int.TryParse(s.Substring(0, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out int r)
                && int.TryParse(s.Substring(2, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out int g)
                && int.TryParse(s.Substring(4, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out int b))
                return new Color(r / 255f, g / 255f, b / 255f, 1f);
            return Color.white;
        }
    }
}
