#!/usr/bin/env python3
"""experiment_index -- map each tech node to the SCIENCE EXPERIMENTS it unlocks.

Why this exists: an experiment is not a part. Kerbalism experiments are `Configure` SETUP
entries grafted onto probe cores, labs and EVA kits and gated by `tech = <node id>`, and
RP-AXE's crewed science is EXPERIMENT_DEFINITIONs gated by `techRequired`. None of that is
in tree/nodes.yaml, none of it shows in R&D, and none of it showed in the tree viewer -- so
a node could carry real, sizeable payload and still render "-- no parts assigned --".
tel_minitrackInterferometry (T3) is the case that surfaced it: it unlocks the whole Orbital
Perturbation experiment, the largest single science source in the T3-T5 stretch, and looked
empty everywhere.

Three authoring forms carry a tech gate:
  1. Kerbalism Configure SETUP, literal gate:   SETUP { name = X   tech = <node> }
  2. the same SETUP via an MM variable:         @SETUP:HAS[#name[X]] { %tech = #$../..$ }
     (design/Science/KerbalismLab/* -- the literal lives in KERBALISM_GROUP_SETTINGS)
  3. a gated definition:                        EXPERIMENT_DEFINITION { techRequired = <node> }

Consumed by tools/build_tree.py (the viewer's Experiments section). Standalone:
  python tools/experiment_index.py                 # every node that unlocks an experiment
  python tools/experiment_index.py --node tel_minitrackInterferometry
  python tools/experiment_index.py --orphans       # gates that name no node in the tree
"""
import argparse, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(ROOT, ".."))
DEFAULT_ROOT = os.path.join(REPO, "GameData", "RP-AXE")

MM_OPS = "@%!+&|*-$"
MM_REF = re.compile(r"^#\$(.+)\$$")
SKIP_DIR = re.compile(r"[\\/](Localization|Flags|Textures?|Sounds?|PluginData)[\\/]", re.I)
# MM writes a space inside a [] selector as '?', so #name[Materials?Bay?Study] is one title.
HAS_NAME = re.compile(r"#name\[([^\]]+)\]")
HAS_TITLE = re.compile(r"#title\[([^\]]+)\]")
PART_FILTER = re.compile(r"^[" + re.escape(MM_OPS) + r"]?PART\[([^\]]*)\]")


def _norm(tok):
    """Strip MM operator prefixes and `:NEEDS[]` / `[filter]` suffixes off a name."""
    return re.split(r"[:\[,]", tok.strip().lstrip(MM_OPS), maxsplit=1)[0].strip()


class Blk:
    __slots__ = ("raw", "name", "fields", "kids")

    def __init__(self, raw=""):
        self.raw, self.name, self.fields, self.kids = raw, _norm(raw), {}, []


def parse(txt):
    """Minimal .cfg -> block tree that KEEPS the raw header (check_tech_refs._parse_cfg
    normalises it away, which would lose the `@SETUP:HAS[#name[NICER]]` name). Any line with
    `=` is a field, so braces inside values can't break the structure."""
    root = Blk()
    stack, pending = [root], None
    for raw in txt.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if "=" in line and line[0] not in "{}":
            key, val = line.split("=", 1)
            key = _norm(key.rstrip("+-*/^!"))
            if key:
                stack[-1].fields.setdefault(key, val.strip())
            continue
        while line:
            if line[0] == "{":
                blk = Blk(pending or "")
                stack[-1].kids.append(blk)
                stack.append(blk)
                pending, line = None, line[1:].strip()
            elif line[0] == "}":
                if len(stack) > 1:
                    stack.pop()
                line = line[1:].strip()
            else:
                cut = min([i for i in (line.find("{"), line.find("}")) if i >= 0] or [len(line)])
                pending, line = line[:cut].strip(), line[cut:].strip()
    return root


def iter_cfgs(root):
    for dirpath, _, files in os.walk(root):
        if SKIP_DIR.search(dirpath + os.sep):
            continue
        for f in files:
            low = f.lower()
            if low.endswith(".cfg") and ".cfg." not in low:
                yield os.path.join(dirpath, f)


def _rel(p):
    return p.replace(REPO + os.sep, "").replace(os.sep, "/")


def _carriers(chain):
    """How many parts the nearest enclosing @PART[a|b|c] filter names ('*' -> 0 = all)."""
    for blk in reversed(chain):
        m = PART_FILTER.match(blk.raw)
        if m:
            names = [p for p in m.group(1).split("|") if p and p != "*"]
            return len(names)
    return 0


def _group(chain):
    """The Configure module's player-facing title ('Experiments', 'Laboratory Experiments',
    'EVA Astronaut') -- which dialog the setup shows up in."""
    for blk in reversed(chain):
        if blk.name != "MODULE":
            continue
        m = HAS_TITLE.search(blk.raw)
        if m:
            return m.group(1).replace("?", " ")
        if blk.fields.get("title"):
            return blk.fields["title"]
    return ""


def _definitions(root):
    """id -> EXPERIMENT_DEFINITION fields, so a SETUP can be joined to the science it pays."""
    out = {}

    def walk(blk):
        for kid in blk.kids:
            if kid.name == "EXPERIMENT_DEFINITION" and kid.fields.get("id"):
                out.setdefault(kid.fields["id"], kid.fields)
            walk(kid)

    for path in iter_cfgs(root):
        try:
            walk(parse(open(path, encoding="utf-8", errors="replace").read()))
        except (OSError, RecursionError):
            continue
    return out


def _int(val):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _merge(dst, src):
    for k in ("id", "title", "sci", "group", "cost", "minCrew"):
        if not dst.get(k) and src.get(k):
            dst[k] = src[k]
    dst["carriers"] = max(dst["carriers"], src["carriers"])
    dst["srcs"] = sorted(set(dst["srcs"]) | set(src["srcs"]))


def _apply_overlays(found, valid):
    """A design/ overlay can re-gate a SETUP that seed/ vendored verbatim -- `tech =
    surfaceScience` (an RP-1 node AXE deleted) rewritten to `@tech = fd_deepThrottleLanding`.
    A flat scan has no patch ordering, so the setup shows up under both. When exactly one of
    the gates names a real node, that is the one the game ends up with; fold the other in."""
    if not valid:
        return
    by_name = defaultdict(list)
    for tech, name, kind in found:
        by_name[(name, kind)].append(tech)
    for (name, kind), techs in by_name.items():
        good = [t for t in techs if t in valid]
        bad = [t for t in techs if t not in valid]
        if not (good and bad):
            continue
        for b in bad:
            src = found.pop((b, name, kind))
            for g in good:
                _merge(found[(g, name, kind)], src)


def _fold_definitions(found):
    """RP-AXE's crewed science is authored twice over: an EXPERIMENT_DEFINITION gated on
    `techRequired`, and the Crew Science Configure SETUP that offers it. That is ONE unlock.
    Keep the setup -- its name is the one the player picks in the dialog -- and take whatever
    the definition knows that the setup does not (title, science cap, crew requirement)."""
    for tech in {t for t, _, _ in found}:
        setups = {r["id"]: r for (t, _, k), r in found.items()
                  if t == tech and k == "setup" and r["id"]}
        for key, rec in list(found.items()):
            if key[0] == tech and key[2] == "definition" and rec["id"] in setups:
                _merge(setups[rec["id"]], rec)
                found.pop(key)


def build(root=DEFAULT_ROOT, valid=None):
    """tech node id -> [experiment dicts]. Every dict has name/kind; setups also carry the
    experiment id, its scienceCap and how many parts offer it. `valid` (the tree's node ids)
    lets an MM overlay's re-gate win over the vendored seed value it replaces."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    import check_tech_refs as ctr

    defs = _definitions(root)
    index = ctr.build_index([root])       # for `%tech = #$..../UnlockTech$` (KerbalismLab)
    found = {}                            # (tech, name, kind) -> record; a setup is authored
                                          # once per carrier file (Configure.cfg AND US2.cfg)
    unresolved = []

    def record(tech, rec, path):
        key = (tech, rec["name"], rec["kind"])
        cur = found.get(key)
        if cur is None:
            rec["srcs"] = [_rel(path)]
            found[key] = rec
        else:
            cur["srcs"].append(_rel(path))
            cur["carriers"] = max(cur["carriers"], rec["carriers"])

    def visit(blk, chain, path):
        chain.append(blk)
        for kid in blk.kids:
            if kid.name == "SETUP":
                name = kid.fields.get("name", "")
                if not name:
                    m = HAS_NAME.search(kid.raw)
                    name = m.group(1).replace("?", " ") if m else ""
                tech = kid.fields.get("tech", "")
                ref = MM_REF.match(tech) if tech else None
                if ref:
                    tech = ctr.resolve_mm_ref(ref.group(1), index) or ""
                    if not tech:
                        unresolved.append((name, _rel(path)))
                if tech and name:
                    eid = ""
                    for sub in kid.kids:
                        if sub.fields.get("type") == "Experiment":
                            eid = sub.fields.get("id_value", "")
                            break
                    d = defs.get(eid, {})
                    record(tech, {
                        "name": name, "kind": "setup", "id": eid,
                        "title": d.get("title", ""), "sci": _int(d.get("scienceCap")),
                        "group": _group(chain), "carriers": _carriers(chain),
                        "cost": _int(kid.fields.get("cost")),
                    }, path)
            elif kid.name == "EXPERIMENT_DEFINITION" and kid.fields.get("techRequired"):
                f = kid.fields
                record(f["techRequired"], {
                    "name": f.get("title") or f.get("id", ""), "kind": "definition",
                    "id": f.get("id", ""), "title": f.get("title", ""),
                    "sci": _int(f.get("scienceCap")), "group": "",
                    "carriers": 0, "cost": _int(f.get("cost")),
                    "minCrew": _int(f.get("minCrew")),
                }, path)
            visit(kid, chain, path)
        chain.pop()

    for path in iter_cfgs(root):
        try:
            visit(parse(open(path, encoding="utf-8", errors="replace").read()), [], path)
        except (OSError, RecursionError):
            continue

    _apply_overlays(found, valid)
    _fold_definitions(found)

    out = defaultdict(list)
    for (tech, _, _), rec in found.items():
        out[tech].append(rec)
    for recs in out.values():
        recs.sort(key=lambda r: (r["kind"] != "setup", r["name"].lower()))
    return dict(out), unresolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--node", help="show only this tech node")
    ap.add_argument("--orphans", action="store_true",
                    help="only gates naming a node that is not in tree/nodes.yaml")
    args = ap.parse_args()

    valid = None
    try:
        import yaml
        with open(os.path.join(REPO, "tree", "nodes.yaml"), encoding="utf-8") as f:
            valid = {n["id"] for n in yaml.safe_load(f)["nodes"]}
    except Exception as e:
        print(f"(nodes.yaml unreadable, skipping the orphan check: {e})")

    idx, unresolved = build(args.root, valid)

    items = sorted(idx.items())
    if args.node:
        items = [kv for kv in items if kv[0] == args.node]
    if args.orphans and valid is not None:
        items = [kv for kv in items if kv[0] not in valid]

    for tech, recs in items:
        mark = "" if valid is None or tech in valid else "   << NOT A TREE NODE"
        print(f"\n{tech}  ({len(recs)}){mark}")
        for r in recs:
            bits = [r["kind"]]
            if r["sci"] is not None:
                bits.append(f"{r['sci']} sci")
            if r["carriers"]:
                bits.append(f"{r['carriers']} part" + ("s" if r["carriers"] != 1 else ""))
            if r["group"]:
                bits.append(r["group"])
            print(f"    {r['name']:<34} {r['id']:<32} [{' · '.join(bits)}]")

    total = sum(len(r) for r in idx.values())
    print(f"\n{total} experiment unlocks on {len(idx)} tech gates")
    if valid is not None:
        bad = sorted(t for t in idx if t not in valid)
        print(f"{len(bad)} gate(s) name no tree node" + (": " + ", ".join(bad) if bad else ""))
    if unresolved:
        print(f"{len(unresolved)} SETUP(s) with an unresolvable MM tech reference: "
              + ", ".join(n for n, _ in unresolved[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
