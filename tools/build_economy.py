#!/usr/bin/env python3
"""Generate AXE's funds income: capstone rewards + program-completion bonuses.

WHY THIS EXISTS
---------------
AXE has no funds income at all. RP-1 had two taps and AXE removed both on purpose: the program
funding drip (a calendar Hermite curve in RP0.dll's ProgramHandler -- unportable, because free
unlimited timewarp turns any per-time payment into infinite money) and the Skopos maintenance
contracts (deleted by design/Contracts/DisableSkoposMaintenance.cfg for the same reason). What
remained pays reputation only, so the player hits the launchpad's first paid upgrade before first
orbit with no way to earn it.

This tool re-provides the income LAUNCH-GATED instead of time-gated, which is the invariant
docs/PROGRAMS.md commits to: you earn by flying missions, never by waiting.

THE MODEL (docs/ECONOMY.md)
---------------------------
Each program gets a budget = its RP-1 `baseFunding` x a global scalar, so RP-1's own sense of which
programmes are big survives while the magnitudes are re-derived for AXE's much smaller sinks
(~22M of lumps, not RP-1's ~229M of program funding). That budget is split two ways:

  * CAPSTONE  -- RP-1 hand-marks 17 contracts `Type: <color=red>CAPSTONE</color>` in their
                 description text. That label is the ONLY place the distinction exists; it is not a
                 config field, which is why it has to be scraped. These are the crowning missions,
                 and they take half of their programme's budget.
  * COMPLETION -- a generated "Programme Complete" contract per programme, gated on every one of its
                 `complete_contract` objectives, paying the other half. Programmes with no capstone
                 (20 of 34 -- including CrewedLunar and CrewedMarsExp) put their whole budget here,
                 so no era pays nothing.

Emits (both regenerated wholesale; never hand-edit):
  design/Contracts/AxeCapstoneFunds.cfg     -- %rewardFunds on the capstone contracts
  design/Programs/AxeProgramCompletion.cfg  -- the completion contracts

Usage: python tools/build_economy.py [path-to-RP-1-Programs.cfg]
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(os.path.dirname(REPO), "RP-1", "GameData", "RP-1", "Programs", "Programs.cfg")
SEED = os.path.join(REPO, "GameData", "RP-AXE", "seed", "Contracts")
OUT_CAPS = os.path.join(REPO, "GameData", "RP-AXE", "design", "Contracts", "AxeCapstoneFunds.cfg")
OUT_DONE = os.path.join(REPO, "GameData", "RP-AXE", "design", "Programs", "AxeProgramCompletion.cfg")
OUT_VALUE = os.path.join(REPO, "GameData", "RP-AXE", "design", "Programs", "AxeProgramValue.cfg")
CHARTERS = os.path.join(REPO, "GameData", "RP-AXE", "design", "Programs", "ActivatePrograms.cfg")

# --- The dials (docs/ECONOMY.md §3). Lifetime funds a player who does everything can earn. -------
TARGET_LIFETIME = 40_000_000   # sinks: ~22M lumps (facilities + part unlocks) + ~20M vehicles
CHANNEL1_SHARE = 0.60          # direct contract funds; the rest is Administration rep->funds
CAPSTONE_SHARE = 0.50          # of a programme's budget, when it has a capstone


def blocks(txt, node):
    """Yield the body of each `node { ... }`, brace-matched."""
    for m in re.finditer(node + r'\s*\{', txt):
        start, depth, j = m.end(), 1, m.end()
        while depth and j < len(txt):
            if txt[j] == '{':
                depth += 1
            elif txt[j] == '}':
                depth -= 1
            j += 1
        yield txt[start:j - 1]


def val(block, key):
    m = re.search(r'^\s*(?:%|@)?' + key + r'\s*=\s*(.+?)\s*$', block, re.M)
    return m.group(1).strip() if m else ""


TYPE_RE = re.compile(r'Type:\s*<color=[^>]*>\s*([^<]+?)\s*</color>', re.I)


def scan_seed():
    """(labels, by_program).

    labels: name -> (declared type, title). The CAPSTONE/REQUIRED/OPTIONAL label lives in the
    description markup RP-1 renders in Mission Control -- there is no config field for it.

    by_program: program -> [contract name, ...], read from the `program = X` lines of each
    contract's ProgramActive requirement. This is the fallback source of objectives for a
    programme whose RP0_PROGRAM block has an empty OBJECTIVES (see derive_objectives)."""
    labels, by_program = {}, {}
    for root, _, files in os.walk(SEED):
        for fn in sorted(files):
            if not fn.endswith(".cfg"):
                continue
            txt = open(os.path.join(root, fn), encoding="utf-8", errors="replace").read()
            for b in blocks(txt, "CONTRACT_TYPE"):
                name = val(b, "name")
                if not name:
                    continue
                m = TYPE_RE.search(val(b, "description"))
                labels[name] = ((m.group(1).strip().upper() if m else ""), val(b, "title"))
                for prog in set(re.findall(r'^\s*program\s*=\s*(\S+)', b, re.M)):
                    by_program.setdefault(prog, []).append(name)
    return labels, by_program


def derive_objectives(prog, labels, by_program):
    """Objectives for a programme RP-1 funds but gives no OBJECTIVES.

    RP-1's Programs.cfg is upstream data we don't control, and a funded programme with an empty
    OBJECTIVES block silently earns NOTHING: load_programs used to drop it, so it got no completion
    contract, no capstone, and its whole baseFunding share was redistributed to everyone else.
    AsteroidExploration (baseFunding 8,400,000, the 4th richest of 35) sat in exactly that state.

    Fall back to the same source the capstone scrape already trusts -- the label in the description
    markup -- and gate on the programme's CAPSTONE contracts, else its REQUIRED ones. OPTIONAL is
    never used: those are side content, and the repeatable ones (maxCompletions = 0) would make the
    completion contract unreachable-by-design. Always announced on stdout, never silent."""
    members = by_program.get(prog, [])
    for want in ("CAPSTONE", "REQUIRED"):
        picked = [c for c in members if labels.get(c, ("", ""))[0] == want]
        if picked:
            return sorted(picked), want
    return [], ""


def load_programs(src):
    progs = []
    txt = open(src, encoding="utf-8", errors="replace").read()
    for b in blocks(txt, "RP0_PROGRAM"):
        if val(b, "isDisabled") == "true":
            continue  # AXE leaves RP-1's deprecated programmes un-chartered
        obj = next(blocks(b, "OBJECTIVES"), "")
        caps = [c for c in re.findall(r'^\s*complete_contract\s*=\s*(\S+)', obj, re.M) if c != "TODO"]
        try:
            funding = float(val(b, "baseFunding") or 0)
        except ValueError:
            funding = 0.0
        # An empty OBJECTIVES is NOT a reason to drop a funded programme -- main() recovers it via
        # derive_objectives(). Only unfunded programmes have nothing to pay out.
        if funding <= 0:
            continue
        progs.append(dict(name=val(b, "name"), title=val(b, "title"),
                          funding=funding, objectives=list(dict.fromkeys(caps))))
    return progs


def esc(s):
    """KSP config is line-based; keep any authored text on one line."""
    return re.sub(r'\s+', ' ', (s or "")).strip()


def ptitle(s):
    """A programme's title for PLAYER-FACING text.

    RP-1 marks five of its own programmes "(WIP)" in the title (Asteroid Exploration, the four
    outer-moon landing programmes). That is an upstream dev note, and the hand-authored
    "Begin Program: X" charters already drop it — so without this the two halves of the same
    programme disagree in the contract list."""
    return re.sub(r'\s*\((?:WIP|TODO)\)\s*$', '', esc(s), flags=re.I)


def scan_charters():
    """`AXE_Begin_X` contract name -> the programme its ActivateProgram behaviour switches on.

    Parsed, not derived: the charter names are hand-authored and do not transform cleanly into
    programme ids (`AXE_Begin_EarlySatellitesHeavy` charters `EarlySatellites-Heavy`). The
    behaviour's `program =` is the only authoritative link, and it is the same string the
    completion contract's ProgramActive requirement uses.
    """
    if not os.path.exists(CHARTERS):
        return {}
    txt = open(CHARTERS, encoding="utf-8").read()
    out = {}
    for body in blocks(txt, "CONTRACT_TYPE"):
        name, program = val(body, "name"), val(body, "program")
        if name and program:
            out[name] = program
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.exists(src):
        sys.exit(f"Programs.cfg not found at {src}")
    seed, by_program = scan_seed()
    progs = load_programs(src)
    if not progs:
        sys.exit("no chartered programmes parsed")

    # Recover funded programmes whose OBJECTIVES block is empty upstream (see derive_objectives).
    derived, dropped = [], []
    for p in list(progs):
        if p["objectives"]:
            continue
        objs, kind = derive_objectives(p["name"], seed, by_program)
        if objs:
            p["objectives"] = objs
            derived.append((p["name"], kind, objs))
        else:
            # No members at all = an RP-1 programme with nothing vendored into seed/ and no charter,
            # so it does not exist in AXE and skipping it is correct. Members but none usable is a
            # real gap worth shouting about.
            dropped.append((p["name"], len(by_program.get(p["name"], []))))
            progs.remove(p)

    total = sum(p["funding"] for p in progs)
    channel1 = TARGET_LIFETIME * CHANNEL1_SHARE
    k = channel1 / total

    for p in progs:
        p["budget"] = p["funding"] * k
        p["caps"] = [c for c in p["objectives"] if seed.get(c, ("", ""))[0] == "CAPSTONE"]
        if p["caps"]:
            p["capstone_pot"] = p["budget"] * CAPSTONE_SHARE
            p["completion"] = p["budget"] - p["capstone_pot"]
        else:
            p["capstone_pot"] = 0.0
            p["completion"] = p["budget"]

    # A capstone can serve more than one programme; pay it from the richest claim, once.
    cap_pay = {}
    for p in sorted(progs, key=lambda q: -q["budget"]):
        for c in p["caps"]:
            share = p["capstone_pot"] / len(p["caps"])
            if share > cap_pay.get(c, (0, ""))[0]:
                cap_pay[c] = (share, p["name"])

    os.makedirs(os.path.dirname(OUT_CAPS), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_DONE), exist_ok=True)

    with open(OUT_CAPS, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"""// ============================================================================
// RP-AXE — capstone contract funds. GENERATED by tools/build_economy.py; do not hand-edit.
//
// RP-1 hand-marks {len(cap_pay)} contracts as `Type: <color=red>CAPSTONE</color>` in their description —
// the crowning mission of a programme. That label is player-facing markup, not a config field, so
// it is scraped from seed/Contracts rather than derived. Each capstone pays
// {CAPSTONE_SHARE:.0%} of its programme's funds budget; the rest lands on the programme-completion
// contract (design/Programs/AxeProgramCompletion.cfg).
//
// Budget: programme funds = RP-1 baseFunding × {k:.5f}, sized so a player who does everything earns
// ~{TARGET_LIFETIME:,.0f} lifetime against ~22M of facility + part-unlock sinks. See docs/ECONOMY.md.
//
// Design overlay, not an edit to seed/ — that folder is re-vendored verbatim by tools/sync-seed.ps1
// and any in-place change would be clobbered. `%` = set-or-create.
// ============================================================================

""")
        for c, (amount, owner) in sorted(cap_pay.items()):
            title = seed.get(c, ("", ""))[1] or c
            f.write(f"// {esc(title)} — capstone of {owner}\n")
            f.write(f"@CONTRACT_TYPE[{c}]:NEEDS[ContractConfigurator]:FOR[RP-AXE]\n{{\n")
            f.write(f"\t%rewardFunds = {round(amount):d}\n}}\n\n")

    with open(OUT_DONE, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"""// ============================================================================
// RP-AXE — programme completion bonuses. GENERATED by tools/build_economy.py; do not hand-edit.
//
// One contract per chartered programme, gated on ALL of that programme's `complete_contract`
// objectives plus the programme being active. Accepting it completes it on the spot (AXEInstant),
// so it reads as a payout for finishing the programme rather than a mission to fly.
//
// It is DELIBERATELY not `autoAccept`. It used to be, and the money worked — but the contract was
// offered, accepted and completed inside one frame, so it never appeared in Mission Control's
// Available or Active list and the player only ever saw an unexplained funds bump (both instances in
// the 2026-07 playtest save finished `viewed = Unseen`). Sitting in Mission Control as an offer costs
// one click and buys two things: the payout is legible when it lands, and a programme you have
// finished but not yet collected advertises what it is worth. AxeInstantComplete self-completes only
// once the contract is Active, so an un-accepted offer just waits — which is the point.
//
// It is a BONUS, not an ending. AxeProgramHandler has no deactivate path, so a programme stays
// active for the rest of the career and its member contracts keep being offered — including the
// repeatable ones (docs/PROGRAMS.md "Repeatable is fine; idle income is not"). The player-facing
// wording says so out loud: an earlier "Programme Complete: X / the programme is discharged" read
// as a state change that does not exist.
//
// This is the half of the budget that reaches every programme. {sum(1 for p in progs if not p["caps"])} of {len(progs)} chartered
// programmes have no capstone at all — including CrewedLunar and CrewedMarsExp — so without this
// whole eras would earn nothing. Programmes WITH a capstone split their budget with it
// ({CAPSTONE_SHARE:.0%} / {1 - CAPSTONE_SHARE:.0%}); programmes without put all of it here.
//
// Never expires (minExpiry = maxExpiry = 0): Contract Configurator defaults to withdrawing an offer
// after 5–100 days, and AXE does not gate time. Same rule as the Begin Programme charters.
// ============================================================================

CONTRACT_GROUP
{{
\tname = AXEProgramCompletion
\tdisplayName = AXE Programme Completion
\tminVersion = 1.12.2
}}

""")
        for p in sorted(progs, key=lambda q: q["funding"]):
            f.write(f"// {p['name']} — RP-1 baseFunding {p['funding']:,.0f}"
                    f" -> AXE budget {p['budget']:,.0f}"
                    + (f" (capstone takes {p['capstone_pot']:,.0f})" if p["caps"] else " (no capstone)")
                    + f"; {len(p['objectives'])} objective(s)\n")
            f.write("CONTRACT_TYPE\n{\n")
            f.write(f"\tname = AXE_Complete_{p['name']}\n")
            f.write("\tgroup = AXEProgramCompletion\n")
            # "Program", not "Programme": matches the 35 hand-authored "Begin Program: X" charters
            # in design/Programs/ActivatePrograms.cfg, so the pair reads as one series in the
            # contract list. Docs and comments keep the British spelling.
            f.write(f"\ttitle = Program Bonus: {ptitle(p['title'])}\n")
            f.write(f"\tdescription = Every objective of the {ptitle(p['title'])} program has been met, "
                    "and the agency releases the program's remaining budget as a bonus. "
                    "The program stays active — its contracts remain available to fly.\n")
            f.write(f"\tsynopsis = Collect the remaining budget for the {ptitle(p['title'])} program.\n")
            f.write(f"\tcompletedMessage = Bonus awarded for {ptitle(p['title'])}.\n")
            f.write("\tprestige = Significant\n\tmaxCompletions = 1\n\tmaxSimultaneous = 1\n")
            f.write("\tminExpiry = 0\n\tmaxExpiry = 0\n\tdeadline = 0\n")
            # No autoAccept: this has to be visible in Mission Control (see the file header).
            # Not declinable/cancellable either — there is no reason to throw a bonus away, and a
            # declined offer would be gone for good (maxCompletions = 1).
            f.write("\tdeclinable = false\n\tcancellable = false\n")
            f.write(f"\trewardFunds = {round(p['completion']):d}\n")
            f.write("\trewardScience = 0\n\trewardReputation = 0\n\tadvanceFunds = 0\n\tfailureFunds = 0\n")
            f.write("\n\tPARAMETER\n\t{\n\t\tname = done\n\t\ttype = AXEInstant\n"
                    "\t\ttitle = Collect the bonus\n\t}\n")
            f.write("\n\tREQUIREMENT\n\t{\n\t\tname = ProgramActive\n\t\ttype = ProgramActive\n"
                    f"\t\tprogram = {p['name']}\n\t}}\n")
            for o in p["objectives"]:
                f.write(f"\n\tREQUIREMENT\n\t{{\n\t\tname = Complete_{o}\n\t\ttype = CompleteContract\n"
                        f"\t\tcontractType = {o}\n\t}}\n")
            f.write("}\n\n")

    # ---- what a programme is worth, stated on its charter -------------------------------------
    # The completion bonus and the capstone are both invisible until you have already done the work:
    # the bonus is not offered until every objective is met, and a capstone looks like any other
    # mission. So the one moment a player chooses between programmes -- accepting a "Begin Program"
    # charter -- was also the one moment nothing said what the choice was worth.
    charters = scan_charters()
    by_name = {p["name"]: p for p in progs}
    cap_of = {}
    for c, (amount, owner) in cap_pay.items():
        cap_of.setdefault(owner, []).append((c, amount))
    unpriced = sorted(n for n, pg in charters.items() if pg not in by_name)
    uncharted = sorted(set(by_name) - set(charters.values()))

    with open(OUT_VALUE, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"""// ============================================================================
// RP-AXE — programme value, shown on the charter. GENERATED by tools/build_economy.py; do not hand-edit.
//
// Adds a `notes` line to each hand-authored "Begin Program: X" contract in ActivatePrograms.cfg
// stating what that programme pays. Both of AXE's funds contracts are invisible until the work is
// already done — the completion bonus is not offered until every objective is met, and a capstone
// is not marked as anything special in the mission list — so accepting a charter, the one moment
// the player is actually choosing between programmes, told them nothing about the stakes.
//
// `notes` and not `description`: the flavour text is hand-authored and this file is regenerated, so
// appending to `description` would either need fragile MM regex surgery or would silently revert an
// edited line back to whatever the generator last saw. `notes` is a separate field that Contract
// Configurator copies to the contract at generation (`ConfiguredContract.notes = contractType.notes`)
// and stock renders under the briefing (`Contract.MissionNotes`), both verified by decompile.
//
// The figures are BASE `rewardFunds`. What is actually paid is scaled by contract prestige and the
// preset's FundsGainMultiplier (docs/ECONOMY.md §3) — 1.5x on Normal for the Significant-prestige
// completion bonus — so the note says "at least", which is true on every preset except Hard (0.8x
// gain, and 1.25 x 0.8 = 1.0x, still not less).
//
// Charter -> programme comes from each charter's own ActivateProgram behaviour, not from its name:
// AXE_Begin_EarlySatellitesHeavy charters EarlySatellites-Heavy.
// ============================================================================

""")
        for cname in sorted(charters, key=lambda n: -by_name[charters[n]]["budget"]
                            if charters[n] in by_name else 0):
            program = charters[cname]
            p = by_name.get(program)
            if p is None:
                f.write(f"// {cname} -> {program}: no funded programme upstream, nothing to state.\n\n")
                continue
            caps = cap_of.get(program, [])
            if caps:
                names = " and ".join(esc(seed.get(c, ("", ""))[1] or c) for c, _ in caps)
                paid = sum(a for _, a in caps)
                worth = (f"Worth at least {round(p['completion'] + paid):,d} funds: "
                         f"{round(paid):,d} on its capstone mission, {names}, and "
                         f"{round(p['completion']):,d} as a bonus once every objective is met.")
            else:
                worth = (f"Worth at least {round(p['completion']):,d} funds, paid as a single bonus "
                         f"once every objective is met — this program has no capstone mission.")
            f.write(f"// {program} — budget {p['budget']:,.0f}; {len(p['objectives'])} objective(s)\n")
            f.write(f"@CONTRACT_TYPE[{cname}]:NEEDS[ContractConfigurator]:FOR[RP-AXE]\n{{\n")
            f.write(f"\t%notes = {worth} Your difficulty settings scale rewards on top of that, so "
                    f"the funds that land run higher. Chartering is permanent: the program stays "
                    f"active for the rest of the career and its contracts remain available to fly."
                    f"\n}}\n\n")

    paid_caps = sum(a for a, _ in cap_pay.values())
    paid_done = sum(p["completion"] for p in progs)
    # Gate, same shape as the dangling-reference checks elsewhere: a charter whose programme is not
    # funded states nothing, and a funded programme with no charter can never be started at all.
    for n in unpriced:
        print(f"WARNING: charter {n} activates {charters[n]}, which is not a funded programme — "
              f"its value note is empty.")
    for n in uncharted:
        print(f"WARNING: programme {n} is funded but no charter activates it — unreachable.")
    for name, kind, objs in derived:
        print(f"note: {name} has no OBJECTIVES upstream — derived {len(objs)} objective(s) "
              f"from {kind} labels: {', '.join(objs)}")
    for name, n_members in dropped:
        if n_members == 0:
            print(f"note: {name} is funded upstream but has no contracts in seed/ — not an AXE "
                  f"programme, skipped")
        else:
            print(f"WARNING: {name} is funded and has {n_members} member contract(s) but no "
                  f"OBJECTIVES and none labelled CAPSTONE/REQUIRED — it pays NOTHING.")
    print(f"scalar = {channel1:,.0f} / {total:,.0f} = {k:.5f}")
    print(f"  {len(cap_pay)} capstone rewards   {paid_caps:>12,.0f}")
    print(f"  {len(progs)} completion bonuses {paid_done:>12,.0f}")
    print(f"  Channel 1 total               {paid_caps + paid_done:>12,.0f}"
          f"  (target {channel1:,.0f})")
    print(f"  Channel 2 (Administration)    {TARGET_LIFETIME - channel1:>12,.0f}")
    print(f"\nwrote {os.path.relpath(OUT_CAPS, REPO)}\n      {os.path.relpath(OUT_DONE, REPO)}"
          f"\n      {os.path.relpath(OUT_VALUE, REPO)}  ({len(charters) - len(unpriced)}"
          f"/{len(charters)} charters priced)")
    early = sorted(progs, key=lambda q: q["funding"])[:2]
    print("\nearly-game check (the launchpad problem):")
    for p in early:
        cap = f", capstone {p['capstone_pot']:,.0f}" if p["caps"] else ""
        print(f"  {p['name']:<24} budget {p['budget']:>8,.0f}  (completion {p['completion']:,.0f}{cap})")
    # The pad's first purchase is upgrades[1], NOT upgrades[0]: KSP charges
    # upgradeLevels[level+1].levelCost, so the leading array entry is the starting level's own cost
    # and is never paid. This check used to read 19,000 off that dead slot; the 25 t -> 75 t step
    # really costs 40,000 (it was 75,000 before the 2026-07-28 re-shape). Keep it in sync with
    # design/Settings/AxeFacilities.cfg by hand — CBK config is not importable from here.
    PAD_FIRST_STEP = 40_000
    combined = sum(p["budget"] for p in early)
    print(f"  combined {combined:,.0f} vs 15,000 start + {PAD_FIRST_STEP:,} pad 25t->75t"
          f"   -> {'OK' if 15_000 + combined >= PAD_FIRST_STEP else 'SHORT'}")


if __name__ == "__main__":
    main()
