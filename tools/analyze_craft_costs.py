#!/usr/bin/env python3
"""Turn the in-game craft-price dump into the economy pass's "what does a vehicle cost" table.

Input  : GameData/RP-AXE/Plugins/PluginData/craft-prices.csv  (written by AxeCraftPricer in the VAB;
         enable `priceCraftTest` in AutoTest.cfg and run KSP with -axe-autotest)
Join   : manifest/part-capabilities.tsv -> the SAME costcat() taxonomy build_tree.py uses to price
         part entryCost, so "what you pay to unlock" and "what you pay to fly" are read on one axis.
Output : per-craft totals + a cost breakdown by part category, and the aggregate category shares.

The point is the denominator: every funds question downstream (contract rewards, facility pacing,
whether a 1,440-fund part unlock is texture or a wall) is meaningless until a vehicle has a price.
"""
import csv
import os
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

from build_tree import costcat  # noqa: E402  single source of truth for the category taxonomy

PRICES = os.path.join(REPO, "GameData/RP-AXE/Plugins/PluginData/craft-prices.csv")
CAPS = os.path.join(REPO, "manifest/part-capabilities.tsv")
SAVES = os.path.join(os.path.dirname(REPO), "Instance", "saves")


def craft_file_part_counts():
    """craft name -> how many parts its .craft file declares.

    A craft authored under RP-1/LRTR can reference parts this install doesn't have; KSP drops those
    silently on load, which would under-price the vehicle without any error. Comparing the file's
    declared part count against the rows we actually priced catches that.
    """
    out = {}
    if not os.path.isdir(SAVES):
        return out
    for save in os.listdir(SAVES):
        for sub in ("Ships/VAB", "Ships/SPH"):
            d = os.path.join(SAVES, save, sub)
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if not fn.endswith(".craft"):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding="utf-8", errors="replace") as f:
                        n = sum(1 for ln in f if ln.lstrip().startswith("part = "))
                except OSError:
                    continue
                out[save + "/" + os.path.splitext(fn)[0]] = n
    return out


def load_categories():
    """part name -> cost category, via the same classifier build_tree.py uses for entryCost."""
    out = {}
    if not os.path.exists(CAPS):
        return out
    with open(CAPS, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        ix = {h: i for i, h in enumerate(hdr)}
        for ln in f:
            c = ln.rstrip("\n").split("\t")
            if len(c) < len(hdr):
                c += [""] * (len(hdr) - len(c))
            g = lambda k: c[ix[k]] if k in ix else ""  # noqa: E731
            out[g("name")] = costcat(g("category"), g("disc"), g("modules"), g("mod"))
    return out


def money(x):
    return f"{x:,.0f}"


def main():
    if not os.path.exists(PRICES):
        sys.exit(f"no price dump at {PRICES}\n"
                 "Run KSP with -axe-autotest and priceCraftTest = true in AutoTest.cfg first.")

    cats = load_categories()
    declared = craft_file_part_counts()
    craft = defaultdict(lambda: {"parts": [], "dry": 0.0, "fuel": 0.0, "mass": 0.0,
                                 "bycat": defaultdict(float), "facility": ""})

    with open(PRICES, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["craft"]
            c = craft[name]
            c["facility"] = row["facility"]
            dry = float(row["dryCost"])
            fuel = float(row["fuelCost"])
            total = float(row["totalCost"])
            mass = float(row["massT"])
            part = row["part"]
            cat = cats.get(part, "UNKNOWN")
            c["parts"].append((part, row["title"], cat, dry, fuel, total, mass))
            c["dry"] += dry
            c["fuel"] += fuel
            c["mass"] += mass
            c["bycat"][cat] += total

    if not craft:
        sys.exit("price dump is empty.")

    agg = defaultdict(float)
    agg_total = 0.0

    for name in sorted(craft, key=lambda n: -craft[n]["dry"]):
        c = craft[name]
        total = c["dry"] + c["fuel"]
        agg_total += total
        want = declared.get(name)
        if want is not None and want != len(c["parts"]):
            warn = f"  <== UNTRUSTWORTHY: .craft declares {want} parts, priced {len(c['parts'])}"
        else:
            warn = ""
        print(f"\n=== {name}  [{c['facility']}]  {len(c['parts'])} parts ==={warn}")
        perT = f"{total / c['mass']:,.0f}" if c["mass"] > 0 else "n/a"
        print(f"  dry {money(c['dry'])}   fuel {money(c['fuel'])}   TOTAL {money(total)}"
              f"   mass {c['mass']:,.2f} t   funds/t {perT}")

        print("  by category:")
        for cat, v in sorted(c["bycat"].items(), key=lambda kv: -kv[1]):
            agg[cat] += v
            share = 100.0 * v / total if total else 0.0
            print(f"    {cat:<12} {money(v):>10}  {share:5.1f}%")

        print("  parts (most expensive first):")
        for part, title, cat, dry, fuel, tot, mass in sorted(c["parts"], key=lambda p: -p[5])[:12]:
            share = 100.0 * tot / total if total else 0.0
            print(f"    {money(tot):>9}  {share:5.1f}%  {cat:<11} {title[:44]:<44} ({part})")

    print(f"\n=== AGGREGATE across {len(craft)} craft — where the money goes ===")
    for cat, v in sorted(agg.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:<12} {money(v):>12}  {100.0 * v / agg_total:5.1f}%")


if __name__ == "__main__":
    main()
