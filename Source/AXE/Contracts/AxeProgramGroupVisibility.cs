using ContractConfigurator;
using HarmonyLib;
using System.Collections.Generic;
using UnityEngine;

namespace RPAxe
{
    /// <summary>
    /// Makes a program's Mission Control folder exist only while that program is active.
    ///
    /// THE PROBLEM. Contract Configurator's Mission Control tree decides whether to draw a group at
    /// all with `ContractType.AllValidContractTypes.Any(ct =&gt; g.BelongsToGroup(ct))` — at both the
    /// root (MissionControlUI.GetGroups) and the child level (MissionControlUI.CreateGroupItem).
    /// `AllValidContractTypes` filters on `ContractType.enabled`, which is a LOAD-TIME flag: it is
    /// set once when the CONTRACT_TYPE parses and never consulted against requirements. So a folder
    /// is drawn for every program from the first minute of a career to the last, whether or not the
    /// program has been chartered and whether or not it was concluded years ago. All that changes on
    /// conclusion is that the count next to it goes grey and reads "Offered 0". By the late game
    /// that is roughly thirty dead folders, which is exactly the clutter conclusion was supposed to
    /// clear away.
    ///
    /// THE LEVER. `enabled` is the same predicate the tree already asks about, so nothing needs
    /// patching: flipping it for the contract types of an inactive program removes their folder, and
    /// flipping it back brings it straight back. The setter is private, hence Traverse.
    ///
    /// WHY THIS IS SAFE for the three things that could plausibly break:
    ///   - Accepted contracts keep working. The grouped tree is only built for the Available view
    ///     (`displayModeAll &amp;&amp; displayMode == 0`); the Active and Archive tabs return early and fall
    ///     through to stock's flat list. A mission you already signed up for from a program you have
    ///     since concluded stays listed and stays flyable, which is what `checkOnActiveContract =
    ///     false` on ProgramActiveRequirement promises.
    ///   - Save loading is untouched. `ContractType.GetContractType(name)` reads the dictionary
    ///     directly and does NOT filter on `enabled`, so a finished contract of a disabled type still
    ///     resolves its type when the save loads.
    ///   - The only other readers of AllValidContractTypes are contract GENERATION (skipping types
    ///     whose program is not active is correct — their ProgramActive requirement would reject them
    ///     anyway) and one display-title lookup that falls back to the raw name.
    ///
    /// A type that failed to parse also has `enabled == false`, and re-enabling one of those would
    /// resurrect a broken contract. So the load-time value is snapshotted before anything is touched
    /// and treated as a ceiling: this can only ever narrow what CC already accepted, never widen it.
    /// </summary>
    internal static class AxeProgramGroupVisibility
    {
        /// <summary>Names of contract types CC accepted at load. Captured once per KSP session,
        /// BEFORE the first flip, so our own edits can never pollute the baseline.</summary>
        private static HashSet<string> _loadable;

        /// <summary>Re-derive `enabled` for every program-gated contract type from the current
        /// program states. Idempotent and cheap enough to call on any state change.</summary>
        public static void Sync()
        {
            AxeProgramHandler handler = AxeProgramHandler.Instance;
            if (handler == null) return;
            IEnumerable<ContractType> all = ContractType.AllContractTypes;
            if (all == null) return;

            if (_loadable == null)
            {
                _loadable = new HashSet<string>();
                foreach (ContractType ct in all)
                    if (ct != null && ct.name != null && ct.enabled)
                        _loadable.Add(ct.name);
            }

            var programs = new List<string>();
            int shown = 0, hidden = 0;
            foreach (ContractType ct in all)
            {
                if (ct == null || ct.name == null) continue;
                if (!_loadable.Contains(ct.name)) continue;   // never resurrect a type that failed to load

                programs.Clear();
                try { Collect(ct.Requirements, programs); }
                catch { continue; }                            // malformed requirement tree: leave it alone
                if (programs.Count == 0) continue;             // not program-gated (Milestones, Records, the charters)

                // ANY, not ALL. A contract naming several programs does so inside a `type = Any` OR
                // group — verified across all 292 program-gated seed contracts, none of which ANDs
                // two programs (an AND would be unsatisfiable anyway now that a predecessor is always
                // concluded before its successor starts). Flattening the tree and asking "is any of
                // them active" is therefore exactly the OR the config expresses.
                bool open = false;
                for (int i = 0; i < programs.Count; i++)
                    if (handler.IsActive(programs[i])) { open = true; break; }

                if (ct.enabled != open) Traverse.Create(ct).Property("enabled").SetValue(open);
                if (open) shown++; else hidden++;
            }
            Debug.Log("[AXE] Mission Control groups synced to program state: "
                      + shown + " contract type(s) visible, " + hidden + " hidden.");
        }

        private static void Collect(IEnumerable<ContractRequirement> reqs, List<string> into)
        {
            if (reqs == null) return;
            foreach (ContractRequirement r in reqs)
            {
                if (r == null) continue;
                // Only ProgramActive decides visibility. ProgramConcluded is deliberately ignored:
                // it gates the "Begin Program" charters, and those must stay visible precisely when
                // their program is NOT yet active — that is the whole point of a charter.
                if (r is Contracts.ProgramActiveRequirement pa && pa.Programs != null)
                {
                    foreach (string p in pa.Programs)
                        if (!string.IsNullOrEmpty(p) && !into.Contains(p)) into.Add(p);
                }
                Collect(r.ChildRequirements, into);
            }
        }
    }
}
