#!/usr/bin/env python3
"""Generate AXE's funds income: capstone rewards + program-completion bonuses.

WHY THIS EXISTS
---------------
AXE has no funds income at all. RP-1 had two taps and AXE removed both on purpose: the program
funding drip (a calendar Hermite curve in RP0.dll's ProgramHandler -- unportable, because free
unlimited timewarp turns any per-time payment into infinite money) and the Skopos maintenance
contracts (deleted by design/Contracts/DisableSkoposMaintenance.cfg for the same reason). What
remained pays reputation only, so the player hits the 19,000-fund launchpad upgrade before first
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
    """name -> (declared type, title). The CAPSTONE/REQUIRED/OPTIONAL label lives in the
    description markup RP-1 renders in Mission Control -- there is no config field for it."""
    out = {}
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
                out[name] = ((m.group(1).strip().upper() if m else ""), val(b, "title"))
    return out


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
        if not caps or funding <= 0:
            continue
        progs.append(dict(name=val(b, "name"), title=val(b, "title"),
                          funding=funding, objectives=list(dict.fromkeys(caps))))
    return progs


def esc(s):
    """KSP config is line-based; keep any authored text on one line."""
    return re.sub(r'\s+', ' ', (s or "")).strip()


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    if not os.path.exists(src):
        sys.exit(f"Programs.cfg not found at {src}")
    seed = scan_seed()
    progs = load_programs(src)
    if not progs:
        sys.exit("no chartered programmes parsed")

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
// objectives plus the programme being active. It auto-accepts and completes instantly (AXEInstant),
// so it reads as a payout for finishing the programme rather than a mission to fly.
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
            f.write(f"\ttitle = Programme Complete: {esc(p['title'])}\n")
            f.write(f"\tdescription = Every objective of the {esc(p['title'])} programme has been met. "
                    "The programme is discharged and its remaining budget is released to the agency.\n")
            f.write(f"\tsynopsis = Complete the {esc(p['title'])} programme.\n")
            f.write(f"\tcompletedMessage = {esc(p['title'])} is complete.\n")
            f.write("\tprestige = Significant\n\tmaxCompletions = 1\n\tmaxSimultaneous = 1\n")
            f.write("\tminExpiry = 0\n\tmaxExpiry = 0\n\tdeadline = 0\n")
            f.write("\tautoAccept = true\n\tdeclinable = false\n\tcancellable = false\n")
            f.write(f"\trewardFunds = {round(p['completion']):d}\n")
            f.write("\trewardScience = 0\n\trewardReputation = 0\n\tadvanceFunds = 0\n\tfailureFunds = 0\n")
            f.write("\n\tPARAMETER\n\t{\n\t\tname = done\n\t\ttype = AXEInstant\n"
                    "\t\ttitle = Discharge the programme\n\t}\n")
            f.write("\n\tREQUIREMENT\n\t{\n\t\tname = ProgramActive\n\t\ttype = ProgramActive\n"
                    f"\t\tprogram = {p['name']}\n\t}}\n")
            for o in p["objectives"]:
                f.write(f"\n\tREQUIREMENT\n\t{{\n\t\tname = Complete_{o}\n\t\ttype = CompleteContract\n"
                        f"\t\tcontractType = {o}\n\t}}\n")
            f.write("}\n\n")

    paid_caps = sum(a for a, _ in cap_pay.values())
    paid_done = sum(p["completion"] for p in progs)
    print(f"scalar = {channel1:,.0f} / {total:,.0f} = {k:.5f}")
    print(f"  {len(cap_pay)} capstone rewards   {paid_caps:>12,.0f}")
    print(f"  {len(progs)} completion bonuses {paid_done:>12,.0f}")
    print(f"  Channel 1 total               {paid_caps + paid_done:>12,.0f}"
          f"  (target {channel1:,.0f})")
    print(f"  Channel 2 (Administration)    {TARGET_LIFETIME - channel1:>12,.0f}")
    print(f"\nwrote {os.path.relpath(OUT_CAPS, REPO)}\n      {os.path.relpath(OUT_DONE, REPO)}")
    early = sorted(progs, key=lambda q: q["funding"])[:2]
    print("\nearly-game check (the launchpad problem):")
    for p in early:
        cap = f", capstone {p['capstone_pot']:,.0f}" if p["caps"] else ""
        print(f"  {p['name']:<24} budget {p['budget']:>8,.0f}  (completion {p['completion']:,.0f}{cap})")
    print(f"  combined {sum(p['budget'] for p in early):,.0f} vs 15,000 start + 19,000 pad L2")


if __name__ == "__main__":
    main()
