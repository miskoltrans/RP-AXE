# RP-AXE Tech-Tree Review Rubric

Spec for reviewing `tree/nodes.yaml` (the SSOT). Hand this + `docs/HANDOVER.md` (the 11
design rules + lane map) + the data files to each review agent. Distilled from the band-1
build/review pass (2026-07-03, 88 nodes).

## Inputs every reviewer needs
- `tree/nodes.yaml` — SSOT. Node = `{id, title, discipline, tier, parents, flavor, parts|upgrades|grants, anyToUnlock?}`.
- `manifest/curated-parts.tsv` — the REAL part titles (`mod⇥name⇥title`). **Read this. Never infer a part's function from its id.**
- `tools/build_tree.py` — the constraints it enforces (below). Run it; it must print `design checks: clean`.
- `docs/HANDOVER.md` — the 11 design rules + the current lane map.
- The **INTENTIONAL list** below — do NOT flag these as bugs.

## Method (how to review, not just what)
1. **Open the real part data.** For every part in a node, read its title. A part whose title names a function the node isn't about is misplaced. *(caught: `science_module` = "PH01 Early Film Camera" sitting in atmo-sounding.)*
2. **Read every parent→child edge aloud as a sentence:** "X led to Y" or "same family." If that sentence is false, it's a candidate finding. *(caught: piston→rocketplane; peroxide-Stentor→LOX-XLR25; orbital-monocoque→1950s-cockpit.)*
3. **Separate LINEAGE from GATING.** A semantically-weak edge may be an intentional economic tax (make stock/catalog parts costly to reach). Only flag it if it's weak AND unlabeled/unintended.
4. **Adversarially verify your own finding before reporting.** Try to REFUTE it — many "wrong" things are intentional. Report only what survives, with the part-data evidence.

## What to hunt (rubric)
| # | Failure mode | Tell |
|---|---|---|
| 1 | id-vs-title mismatch | a generic id (`science_module`, `sensor*`, `*_v2`, `*Wedge`, `*module`) hides a specific part in the wrong lane |
| 2 | False lineage | edge fails the sentence test, not labeled as a gating tax |
| 3 | Untriaged hub | >3 dependents with no split / re-home / accept decision (`start` exempt) |
| 4 | Tier fault | non-forward edge (build dies), or an unmotivated multi-tier jump |
| 5 | Naming drift | node named for an artifact ("cockpit") or capability ("orbital thrust") not the mechanism; "X & Y" compounds (unless a real field: GN&C) |
| 6 | Catalog leakage | a fixed-catalog part NOT sitting in an opt-in dead-end (procedural is always the default) |
| 7 | Orphan / dead weight | unreachable node, or a leaf that ought to gate something |
| 8 | Wrong parent (re-root) | a node stranded in a foreign lane because it hangs off a foreign parent when a same-family parent exists *(caught: rocketplane off the wing → re-rooted onto injectors)* |

## Build constraints (`design checks: clean` = zero warnings)
- Every parent tier **strictly <** child tier. Same-tier / backward = warning.
- No cycles; every node reachable from a root.
- No transitively-redundant edge (a parent that is also an ancestor of another parent).
- `anyToUnlock` needs ≥2 parents.

## INTENTIONAL — do NOT flag these as bugs
- **Gating taxes:** fixed-catalog dead-ends pushed DEEP on purpose to discourage stock parts (`Stamped Aerofoil Panels` behind boattail; the `Prefabricated *` decoupler/adapter/nosecone catalogs; `Interchangeable-Part Manufacture` RCS).
- **`cryo_hydrogen`:** an EMPTY T1 commitment gate (costs program time on purpose; do NOT dissolve).
- **Accepted hubs:** `elec_transistor` (~5, the honest solid-state gate), `aero_subsonicWing` (~5, discipline root), `str_structuralHardware` (4, foundation catch-all).
- **Utility catch-alls** exempt from the ≤6-parts / one-king rule: `str_structuralHardware`, the GroundSupport MLP line, the launch-clamp chain.
- **Real generational multi-tier jumps:** `aero_subsonicWing`→`aero_supersonicWing` (T1→T3); rocketplane `X-2`→`X-15` (T3→T5); the hydrolox and film-recon (T1→T3) gaps.
- **Placeholder grants:** avionics-tier + DSN nodes emit a `partUpgrade` STUB via `grants:` until the plugin/facility mechanism is wired (see memory `rp-axe-placeholder-parts`).
- **Parked / deferred (band-2, NOT bugs):** ladders, decals, deep-space instruments, probe-charter parts, the parked partlist tail.

## Fan-out shape for the review
- **Lane agents** — one per discipline (19). Deep lineage read of that lane vs. the part data; name every edge; flag id-vs-title within it.
- **Failure-mode sweeps** (cross-cutting) — id-vs-title across ALL placed parts; hub census; tier-jump census; naming-drift pass.
- **Verify** — each finding checked by an independent skeptic (refute-by-default).
- **Synthesis** — dedup, drop refuted, group by lane, rank by confidence.

## Output per finding
`{ node_or_edge, failure_mode(#), evidence (part title / tier / the failed sentence), proposed_fix, confidence, maybe_intentional? }`
