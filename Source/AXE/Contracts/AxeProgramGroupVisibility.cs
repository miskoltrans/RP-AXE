using ContractConfigurator;
using ContractConfigurator.Util;
using HarmonyLib;
using KSP.UI.Screens;
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

        /// <summary>Raised by Sync() when a folder actually appeared or disappeared, consumed by
        /// RefreshIfPending() from AxeProgramHandler.Update(). Never acted on inline — see there.</summary>
        private static bool _refreshPending;

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
            bool changed = false;
            foreach (ContractType ct in all)
            {
                if (ct == null || ct.name == null) continue;
                if (!_loadable.Contains(ct.name)) continue;   // never resurrect a type that failed to load

                // A one-off that has already been flown can never be offered again, so its folder is
                // showing a dead entry. CC's own test, from MissionControlUI's "Completed" status
                // image: maxCompletions == 0 means unlimited, so repeatables are never exhausted.
                //
                // This is why concluding Suborbital Rocket Development did not remove its folder:
                // `first_FirstFlight` sits in that group but is gated on ANY starting program, and
                // X-Plane Research was still active — so the program test passed for a contract that
                // was already Completed with maxCompletions = 1 and could not be offered to anyone.
                bool exhausted = ct.maxCompletions != 0 && ct.ActualCompletions() >= ct.maxCompletions;

                programs.Clear();
                try { Collect(ct.Requirements, programs); }
                catch { continue; }                            // malformed requirement tree: leave it alone

                // ANY, not ALL. A contract naming several programs does so inside a `type = Any` OR
                // group — verified across all 292 program-gated seed contracts, none of which ANDs
                // two programs (an AND would be unsatisfiable anyway now that a predecessor is always
                // concluded before its successor starts). Flattening the tree and asking "is any of
                // them active" is therefore exactly the OR the config expresses. No programs named at
                // all (Records, HumanRecords, the charters) means nothing gates it, so it stays on
                // its own merits — exhaustion alone can still retire it.
                bool open = programs.Count == 0;
                for (int i = 0; i < programs.Count && !open; i++)
                    if (handler.IsActive(programs[i])) open = true;

                open &= !exhausted;
                if (ct.enabled != open)
                {
                    Traverse.Create(ct).Property("enabled").SetValue(open);
                    changed = true;
                }
                if (open) shown++; else hidden++;
            }
            Debug.Log("[AXE] Mission Control groups synced to program state: "
                      + shown + " contract type(s) visible, " + hidden + " hidden.");
            if (changed) _refreshPending = true;
        }

        /// <summary>
        /// Redraw Mission Control's grouped list if the last Sync() moved anything, so a program's
        /// folder appears the moment it is chartered and goes the moment it is concluded, instead of
        /// on the player's next visit to the screen. Cheap when nothing changed (one branch), which
        /// is why AxeProgramHandler can call it every frame.
        ///
        /// The redraw itself needs no patching: CC's OnClickAll rebuilds the tree from
        /// `ContractType.AllValidContractTypes`, which is a lazy iterator filtering on `enabled` at
        /// enumeration time, not a cached list — so it sees what Sync() just wrote.
        ///
        /// WHY DEFERRED, RATHER THAN CALLED FROM Sync() ITSELF. Sync() runs inside
        /// `contract.Accept()`, underneath ContractConfigurator's own accept-click handler. That
        /// handler carries on afterwards and does `((Component)selectedButton).GetComponent&lt;
        /// MCListItem&gt;()` on the very row the player clicked — a row this rebuild destroys. The
        /// same shape of trap AxeInstantComplete waits a tick to avoid. Consuming the flag from
        /// Update() puts the rebuild strictly after the accept has finished, and on conclusion after
        /// CC's own onFinished bookkeeping, whichever order Unity runs the two components in.
        ///
        /// Only the All tab is CC's grouped tree. The other three are flat lists of contract
        /// INSTANCES, and neither chartering nor concluding a program offers or withdraws a contract
        /// on the spot, so a redraw there would show the player exactly what is already on screen —
        /// and CC redraws them itself when a contract really does come or go.
        /// </summary>
        public static void RefreshIfPending()
        {
            if (!_refreshPending) return;

            // Cleared before every early return below, not held: each of them means the tree is
            // going to be built from scratch before the player sees it again (MissionControlUI's own
            // ticks == 1/2 pass re-runs OnClickAll off lastMCButton on entry), so a held flag would
            // do nothing here and then fire into an unrelated later visit.
            _refreshPending = false;

            MissionControlUI ui = MissionControlUI.Instance;
            // Screen closed, or we are in a scene that has none. Instance is a plain static that CC
            // never nulls, so in another scene this is a destroyed object — the Unity == overload is
            // what makes that read as null, and it is load-bearing.
            if (ui == null || MissionControl.Instance == null) return;
            if (ui.ticks < 2) return;              // CC is still wiring the screen up; its own pass covers us
            if (HighLogic.CurrentGame == null) return;
            if (HighLogic.CurrentGame.Parameters.CustomParams<ContractConfiguratorParameters>().lastMCButton
                != ContractConfiguratorParameters.MissionControlButton.All) return;

            // Drop the selection FIRST. OnClickAll destroys every row but leaves the info panel up
            // with a live Accept button and `selectedButton` pointing at a destroyed row, which CC's
            // AcceptContract dereferences with no null check. This is the same teardown CC does in
            // HandleRemovedContract; selectedButton is private, hence Traverse.
            MissionControl.Instance.ClearInfoPanel();
            MissionControl.Instance.panelView.gameObject.SetActive(false);
            MissionControl.Instance.selectedMission = null;
            Traverse.Create(ui).Field("selectedButton").SetValue(null);

            // Folders come back collapsed: `expanded` lives on the GroupContainer and this builds
            // new ones. Same as toggling Available -> All by hand, which is the only other way to
            // reach this method.
            ui.OnClickAll(true);
            Debug.Log("[AXE] Mission Control list rebuilt for a program state change.");
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
