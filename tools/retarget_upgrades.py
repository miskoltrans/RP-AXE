#!/usr/bin/env python3
"""retarget_upgrades — move `RFUpgrade_*` / `RFTech-*` tokens between nodes in tree/nodes.yaml.

The ladder pass (docs/UPGRADE-LADDERS.md) re-homes hundreds of engine-config tokens off the bucket
nodes they collapsed onto. Doing that by hand is error-prone: a token has to be removed from wherever
it currently sits AND added to exactly one target, across a 5000-line hand-authored YAML full of
comments that must survive untouched.

This edits nodes.yaml LINE-WISE rather than round-tripping through the YAML parser, because a
round-trip would strip every comment in the file — and in this tree the comments carry the design
rationale, which is the part worth keeping.

Usage:
    python tools/retarget_upgrades.py moves.tsv        # two columns: token <TAB> target_node
    python tools/retarget_upgrades.py moves.tsv --dry  # report only, write nothing

A target of `-` removes the token without re-homing it (the config then falls back to its part's own
node via AxeEngineConfigGates layer 1 — i.e. "comes free with the part").
"""
import os, re, sys, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
NODES = os.path.join(ROOT, "..", "tree", "nodes.yaml")
UPG = re.compile(r"^(\s*)upgrades:\s*\[(.*?)\](.*)$")
NID = re.compile(r"^\s*-\s+id:\s*(\S+)")
ANCHOR = re.compile(r"^\s*(parts|flavor|parents|tier|discipline|title):")


def load_moves(path):
    moves = {}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.split("#")[0].strip()
            if not ln: continue
            parts = ln.split("\t") if "\t" in ln else ln.split()
            if len(parts) < 2: continue
            moves[parts[0].strip()] = parts[1].strip()
    return moves


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    moves = load_moves(sys.argv[1])
    dry = "--dry" in sys.argv
    lines = open(NODES, encoding="utf-8").read().split("\n")

    # pass 1 — strip every targeted token from wherever it currently lives
    cur, removed, seen_nodes = None, collections.Counter(), {}
    for i, ln in enumerate(lines):
        m = NID.match(ln)
        if m: cur = m.group(1); seen_nodes[cur] = i
        m = UPG.match(ln)
        if not m or cur is None: continue
        indent, body, tail = m.groups()
        toks = [t.strip() for t in body.split(",") if t.strip()]
        keep = [t for t in toks if not (t in moves and moves[t] != cur)]
        for t in toks:
            if t in moves and moves[t] != cur:
                removed[t] += 1
        if keep != toks:
            lines[i] = (f"{indent}upgrades: [{', '.join(keep)}]{tail}" if keep
                        else f"{indent}# upgrades: [] — emptied by retarget_upgrades{tail}")

    # pass 2 — add each token to its target node (skip '-' = deliberate un-homing)
    targets = collections.defaultdict(list)
    for tok, node in moves.items():
        if node != "-": targets[node].append(tok)
    missing, added = [], collections.Counter()
    for node, toks in targets.items():
        if node not in seen_nodes: missing.append(node); continue
        start = seen_nodes[node]
        end = next((j for j in range(start + 1, len(lines)) if NID.match(lines[j])), len(lines))
        upi = next((j for j in range(start, end) if UPG.match(lines[j])), None)
        if upi is not None:
            m = UPG.match(lines[upi]); indent, body, tail = m.groups()
            cur_toks = [t.strip() for t in body.split(",") if t.strip()]
            new = cur_toks + [t for t in toks if t not in cur_toks]
            lines[upi] = f"{indent}upgrades: [{', '.join(new)}]{tail}"
        else:
            # no upgrades line yet — insert after the last structural key of the node
            anchor = max((j for j in range(start, end) if ANCHOR.match(lines[j])), default=start)
            indent = re.match(r"^(\s*)", lines[anchor]).group(1)
            lines.insert(anchor + 1, f"{indent}upgrades: [{', '.join(toks)}]")
            for k in list(seen_nodes):
                if seen_nodes[k] > anchor: seen_nodes[k] += 1
        added[node] += len(toks)

    unmoved = [t for t in moves if removed[t] == 0 and moves[t] != "-"]
    print(f"retarget: {len(moves)} token(s) -> {len(targets)} node(s); "
          f"{sum(removed.values())} removal(s), {sum(added.values())} addition(s)")
    if missing: print(f"  ! target node(s) not found: {', '.join(sorted(missing))}")
    if unmoved: print(f"  ~ not found at any source (new placement or typo): {', '.join(sorted(unmoved)[:12])}")
    if dry:
        print("  (dry run — nothing written)"); return
    if missing:
        print("  ABORTED: fix the missing target node(s) first"); sys.exit(1)
    open(NODES, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print(f"  wrote {NODES}")


if __name__ == "__main__":
    main()
