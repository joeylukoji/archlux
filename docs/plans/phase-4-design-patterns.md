# Refactor plan: design patterns, block by block (PLAN.md phase 4)

Status: **proposed, not started** (2026-09-27). Written with the `request-refactor-plan`
skill, from PLAN.md's own phase-4 table, after measuring the codebase with `radon` and
`coverage`. Nothing below has been implemented.

## Problem Statement

PLAN.md 3.9 (the English-API rename, waves 0–6) is merged: every public name is now
English. What it did not touch is *structure*. Measured on 2026-09-27:

- **12 modules exceed 400 lines**: `data/chargeurs.py` (861), `geom/pavage.py` (679),
  `lmo/cuts.py` (671), `geom/rectilineaire.py` (646), `geom/polytope.py` (617),
  `io/json_io.py` (613), `api.py` (608), `certify/proof.py` (605), `types.py` (573),
  `geom/graphe.py` (522), `lmo/solveur.py` (414), `uq/conforme.py` (408).
- **33 radon blocks exceed cyclomatic complexity 10** (32 functions/methods plus the class `Loop`) (`radon cc src -n C`), five of
  them past 30: `data/chargeurs.py::_convertir` (E, 38), `geom/graphe.py::deduce_order`
  (E, 33), `solve/frank_wolfe.py::frank_wolfe` (E, 32), `geom/pavage.py::deduce_grid`
  (E, 31), `active/boucle.py::Loop.run` (D, 29).
- **Line coverage is 92%** (4902 of 5323 statements; `pytest --cov=archlux
  --cov-report=term` with branch mode off, re-measured 2026-10-02), short of the 95% gate
  (branch coverage not measured yet: `pytest-cov`'s branch mode needs enabling — see
  Testing Decisions).
- A few modules mix unrelated responsibilities under one name: `types.py` carries both
  the pure model (`Room`, `Wall`, `Plan`...) and the run trace (`ModelTrace`, part of
  `Manifest`); `light/base.py`'s `DenseSurrogate` is model, training and serialization in
  one class; `feasibility/__init__.py` holds business logic that belongs in a dedicated
  module; `api.py`'s `legalize` already reads as a pipeline (PR #8 extracted `_Problem`)
  but still owns the tiling-grid decision as two booleans instead of one value.
- PLAN.md 3.9 renamed every **public** identifier a French term of the glossary matches;
  it did not reach every **private** helper, since the identifier guard only checks
  glossary-listed terms. A `graphify` call-graph scan (see Tooling) found at least 19
  still-French private functions/methods, e.g. `data/chargeurs.py`'s `_caler`,
  `_recoller`, `_murs_depuis_polygones`, `_ouverture_depuis_baie`, `_lire_groupes`,
  `_segment_du_mur`, `_angles_et_longueurs`, its nested `redresser`; `bench/run.py`'s
  `_ecrire_manifeste`/`_ecrire_bruts`; `export/ifc.py`'s `_ecrire_spf_minimal`;
  `geom/polytope.py`'s `_verifier_enveloppe_admissible`; `light/{analytique,simulateur}.py`'s
  `_score_et_gradient`; `light/appris.py`'s `_dense_depuis_disque`/`_charger_torch`;
  `lmo/solveur.py`'s `_construire_modele`. This phase is the natural place to finish
  that sweep, since every one of these sits inside a module phase 4 already opens.

None of this changes behaviour today, but it makes the next real feature (phase 5,
usability; phase 6, the scientific program) more expensive with every module it touches,
and a 38-CC function is not reviewable in one read.

## Solution

Refactor **one block at a time**, in the dependency order of `ARCHITECTURE.md` §5 (a
block is refactored only after the layers it depends on are done, so its own tests never
have to chase a moving foundation). For every block:

1. **Pin behaviour first** (Q-M8): confirm the block already has property tests and
   frozen reference cases; if not, add them before touching any code (`tdd`, seams
   confirmed with the maintainer first).
2. **Refactor** (`python-design-patterns` → `python-expert`), applying the pattern
   PLAN.md names for that block, as small commits that each leave the suite green.
3. **Review** (`review-and-refactor`, then `python-design-patterns` if the diff is
   structural).
4. **Verify no drift**: full suite, `ruff`, `mypy src`, the neutrality check
   (`tests/test_neutrality.py`) and `radon cc <touched files> -n C` all green; the
   reference cases in `results/` and `tests/references/` byte-identical.

A rename and a refactor still never share a commit (ADR 0001): phase 3.9 is over, so this
phase is refactor-only, but a stray French identifier or a leftover deprecated alias
found while restructuring a block gets its own tiny commit, not folded into the
structural change.

**French-identifier sweep, every block.** Before a block's structural commits, run
`scripts/rename_identifiers.py --dry-run` intent (or a plain grep against
`docs/glossary.md`'s terms plus common French verbs) over the files that block is about
to touch, and rename what it finds, in its own commit, ahead of the structural work:

- **Private names** (leading underscore, module-internal): pure rename, no alias, same
  as any other private helper — nothing outside the module can be importing them.
- **Public names** the tool or a manual read turns up (should be rare after PLAN.md 3.9):
  a deprecated alias via `archlux._deprecation.lazy_aliases`, exactly like every wave-5
  batch, with its entry in `docs/glossary.md` and `tests/unites/test_function_aliases.py`.

This is a rename commit, not a refactor commit, and follows the same proof (the tool's
inverse-rename AST-equality check) as PLAN.md 3.9. It is not a separate pass over the
whole codebase: doing it block by block means it only ever touches files already being
opened for that block's structural work, so no module is touched twice for unrelated
reasons.

### Tooling: graphify and ponytail

Checked for fit before adopting either, since "use the skill" is not the same as "use it
unmodified everywhere":

- **`graphify`** (`graphify update <path> --no-cluster`, local install verified working
  on this repo, 2026-09-27: 1594 nodes / 3389 edges extracted from `src/archlux` with tree-sitter,
  no LLM or API key needed for a code-only graph). Used **per block**, before the first
  structural commit: `graphify explain "<function>"` lists real callers and callees from
  the graph, not from memory or a grep that might miss a dynamic import. This is exactly
  what de-risks the five worst extractions (`_convertir`, `deduce_order`, `deduce_grid`,
  `frank_wolfe`, `Loop.run`): know every caller before moving code out from under it.
  The graph is regenerated (`graphify update`) after each block merges, since a stale
  graph would recommend against a caller that no longer exists. `graphify-out/` is
  generated, gitignored, never committed.
- **`ponytail`** (`.claude/skills` plugin, already installed; see `CLAUDE.md` for why it
  is not auto-dispatched project-wide). For phase 4 specifically, its **ladder** (steps
  1–5: does this need to exist, is it already here, does stdlib/a native feature/an
  installed dependency cover it) is a useful second opinion against over-applying a
  pattern PLAN.md names — e.g. block 6's registry or block 12's protocol should be the
  smallest thing that removes the `if name == "ASE"` branches or the `getattr` duck
  typing, not a speculative plugin system. Used at `lite` intensity only, as a design
  check during the `python-design-patterns` step, **never** for its output/prose rules:
  this repo's numpydoc `Parameters`/`Returns`/`Raises`/`Notes` sections and
  `ARCHITECTURE.md`'s explicit-over-terse convention stand as written (CLAUDE.md's own
  precedence rule: project convention overrides a skill's default when they conflict).
  Ponytail is never switched to `full`/`ultra` in this repo.

## Commits

Every commit leaves `pytest`, `ruff check`, `ruff format --check`, `mypy src/` and the
neutrality check green. Order follows the dependency graph; a block's number is not a
day count.

### 0. Tooling (before any block) — **done**

1. `radon` added to the `dev` extra in `pyproject.toml`, pinned like the other lint
   tools.
2. **Not a blocking CI step**: a zero-tolerance `radon cc src -n C` gate would turn CI
   red the moment this commit lands and keep it red for the whole multi-week refactor,
   blocking unrelated work. Used a **ratchet test** instead
   (`tests/test_complexity.py::test_no_new_function_above_complexity_ten`), the same
   shape as `test_identifiers.py`'s `MIGRATED` list: `MAX_VIOLATIONS = 33` (today's
   count, via radon's own Python API, not a subprocess), lowered in the same commit that
   brings a block under CC 10, never raised. It runs with the rest of the suite, no
   extra CI wiring needed. `make check-complexity` still exists for a manual, human-
   readable local check (prints every violation; not CI-blocking, like `make results`).
3. Branch coverage enabled (`[tool.coverage.run] branch = true`, CI's `Tests` step gets
   `--cov-branch`). Baseline re-measured with branches counted: **88.9%** combined
   (down from the line-only 92%, as expected — branches add denominator). The ratchet
   floor moved from 87.9 to 88.8; the true two-figure gate (95% lines / 90% branches)
   is checked with `coverage report --skip-covered` when a block's tests move it, not
   read off this single combined number.

### 1. Imports and layers — **done**

4. `light/__init__` and `certify/__init__` are now lazy facades: asking for one name
   (`light.Daylight`, `certify.render`) imports only the module that defines it. Not the
   same lazy-attribute code as the package root (that pattern serves whole submodules
   and top-level functions, a different shape) — instead, the root's helper itself grew
   two new pieces (`LazyAlias`, `lazy_module_attributes`, in `_deprecation.py`) so both
   the deprecated names and the current names of a facade resolve without importing
   anything until asked. Verified empirically (`tests/unit/test_lazy_facades.py`,
   fresh-interpreter checks): `light.Daylight` no longer loads `analytique`/
   `simulateur` (~0.33 s), `certify.render` no longer loads `proof`/`borne` (~1.34 s).
5. `__version__`'s import path was already correct: `_version.py` is a genuine leaf
   (imports nothing), read directly by every module that stamps an output, and nothing
   in the codebase or its docs re-imports the whole package just for the version.
   Confirmed, no change needed.
6. Added `test_a_fresh_import_loads_only_the_declared_layers` to
   `tests/test_dependances.py`: for every top-level package, import it in a fresh
   subprocess and read `sys.modules` back — a dynamic check the static AST walk cannot
   do (it cannot see a computed `importlib.import_module(...)` call, and it checks
   *declared* imports, not what actually loads transitively). `api` was in `AUTORISE`
   but missing from `ARCHITECTURE.md` §5 itself: PLAN.md was right that it needed adding,
   and §5 now has an `api ←` line. The dynamic check imports every submodule and every
   `__all__` name (a lazy facade loads almost nothing otherwise) and checks a `FORBIDDEN`
   table derived from §5 with no transitive closure; a closure of `AUTORISE` is used only
   for the separate "declared layers" check, where it would otherwise flag `api` reaching
   `uq` through `certify`. That closure hid a real gap: `feasibility` loads `light.protocole`
   and `uq` through `api`. §5 now states this as an explicit, justified exception.

### 2. `types` — **done, with one item skipped by design (see below)**

7. Existing property tests and reference cases for `Plan`/`Context`/`Manifest`/
   `ModelTrace` construction were already adequate; no gap found.
8. `legalize` gains a `legalize_trace` sibling returning `(Plan, Trace | None)`
   (`None` in classic mode: no Frank-Wolfe pass to trace). `legalize(..., trace=True)`
   still works, now with a `DeprecationWarning` pointing at the replacement — the
   maintainer's own choice over a clean break (2026-09-27). `Plan.trace` itself is
   **not** removed: converting it into a warn-on-access property is not practical on a
   `frozen, slots` dataclass without real engineering cost for a field that keeps
   working either way; `legalize_trace` builds a `Plan` with `trace=None` on its own
   return, which is what a new caller actually sees.
9. **Skipped, found infeasible as written**: `io.json_io` genuinely constructs
   `ModelTrace`/`Manifest` instances at runtime when deserializing a manifest, and
   `certify.rapport` type-hints on `Manifest`, so moving the classes into `bench`
   would make both import `bench`. The first blocker is `test_personne_n_importe_bench`
   (`tests/test_dependances.py`): it rejects any `archlux.bench` import from outside
   `bench` and never reads `EXEMPTIONS`, so no exemption entry could allow it. The
   static AST walk also sees imports under `if TYPE_CHECKING:`, so a hint-only import
   in `certify.rapport` is caught as well; and the dynamic
   `test_a_fresh_import_loads_no_bench_and_no_torch` forbids any package but `bench`
   from loading it at runtime. The move therefore needs a change to `bench`'s leaf
   rule in `ARCHITECTURE.md` §5 (with an ADR), not exemption budget: a bigger decision
   than block 2. Confirmed at the commit, not assumed: the classes stay in `types.py`.
10. `FIELDS_VECTOR` and `vectorize(plan)` added to `types.py` (local `numpy` import,
    since `types` is loaded eagerly by the package root and must not add to `import
    archlux`'s budget — caught by `test_import_cost.py` on the first attempt).
    `light.jetons.plan_to_vector` now delegates to it instead of duplicating the same
    four-line computation (its own comment explaining the duplication is gone with it).

### 3. `geom` — **CC reduction (12, 13, 15) and the `pavage.py` split (11) done; 14 not done; exit gate not yet met, see below**

11. **Done.** `pavage.py` (745 lines) split in three, English names per ADR 0001
    (glossary: trame → grid): `geom/grid.py` (`Grid`, `deduce_grid` and its inference
    helpers), `geom/grid_repair.py` (`_consolider`, `_couverture`, `_retouches`,
    `_reparer_partition`), and a slimmer `geom/pavage.py` keeping the tiling
    constraints (`snap_to_grid`, `tiling_constraints`, `extend_tiling`). Pure move:
    `geom.pavage` re-exports `Grid`/`deduce_grid` and keeps its `lazy_aliases` table
    for the French names; imports run `pavage → grid → grid_repair`, no cycle;
    `results/` unchanged. An earlier draft of this item claimed the CC extractions of
    item 12 "already bring every function in the file under CC 10" and met the exit
    gate — that was false. **Still open for later**: `_consolider` D(24),
    `_reparer_partition` C(14) and `tiling_constraints` C(13) remain above CC 10 (with other `geom` functions), and
    `graphe.py` (625), `polytope.py` (629), `rectilineaire.py` (656 lines) remain above
    the 400-line gate.
12. `deduce_grid` (`pavage.py`, was CC 31) split into `_deduce_lines` (grouping and
    outline anchoring, itself split further into `_anchor_outline_vertices`),
    `_room_bounds` (bounds + flatness check), `_verify_partition` (coverage/repair).
    `deduce_grid` itself is now an orchestrator, under CC 10.
13. `deduce_order` (`graphe.py`, was CC 33) split into `_pairwise_order` (the
    center-comparison loop), `_outline_envelope`, and `_wall_sides_and_groups` — the
    last one, still over CC 10 on its own, split again into `_assign_group_sides`,
    then `_group_members`/`_bounding_hull`/`_assign_wall_side_for_group`.
    `deduce_order` itself is now under CC 10.
14. **Skipped, found infeasible as written, same class of problem as block 2's item
    9**: a deprecated shim at the old `geom/diagnostic.py` path would need to import
    `archlux.data.diagnostic`, but `geom` may not import `data` (the layering is the
    other way round: `data` depends on `geom`, never the reverse). The nominal
    exemption this needs is one more than the project's cap of 3, already fully spent.
    Confirmed at the commit (tried the move, hit the same wall, reverted cleanly): stays
    in `geom/`, unmoved, until the exemption cap or `data`/`geom`'s relative layering is
    revisited — a bigger decision than block 3.
15. `freeze_contacts` (`polytope.py`, was CC 16) split off its bounds-freezing pass
    into `_frozen_bounds`; now under CC 10. `_coupe_verticale`/`_coupe_horizontale`
    (`rectilineaire.py`, were CC 14 each) were near-exact mirrors of each other (axes
    swapped) with the same three-way GEOS-geometry-type branch and the same
    collinear-piece-joining loop duplicated; factored into two shared helpers
    (`_line_pieces`, `_chord_through_pivot`, parametrized by axis) instead of just
    splitting each in place — removes the duplication PLAN.md's own pattern column
    names for this block (SRP) rather than only chasing the complexity number.

**Ratchet**: `MAX_VIOLATIONS` (block 0's `tests/test_complexity.py`) moved from 33 to
28 across items 12, 13, 15 — five named functions fixed, zero new violations.

### 4. `lmo` — done

16. Replaced the module-global cache dict (`_CACHE: OrderedDict[...]`, keyed by
    `id(poly)`, no locking) with `CacheLP`: an explicit, injectable, thread-safe
    (`threading.Lock`) object (`get`/`put`/`take`/`clear`; `maxsize >= 1` validated).
    It is still keyed by `id(poly)` — not a module global any more, but the key is kept
    deliberately: each entry holds a strong reference to its polytope, so that `id()`
    cannot be reused while the entry lives. Thread safety covers the whole solve, not
    only get/put: `solve` checks the model out of the cache (`take`) for the
    set-objective / `Solve()` / read-solution sequence and puts it back afterwards, so
    no two threads ever hold the same OR-Tools model (one that finds it checked out
    builds its own). A module-level `_DEFAULT_CACHE =
    CacheLP()` keeps the existing zero-argument call sites and `clear_cache()` working
    unchanged; `solve()` gained an optional `cache: CacheLP | None = None` parameter for
    callers that want an isolated cache (e.g. a test). Covered in isolation by `tests/unit/test_cache_lp.py` (empty-start,
    put/get round-trip, clear, eviction beyond `maxsize`, isolation between two
    instances, `solve` giving the identical answer regardless of which cache serves it,
    a warm solve through an injected cache, and a `threading.Barrier`-based test of
    concurrent warm solves with different objectives on one shared cache — which
    segfaulted before the check-out fix).
17. `solve` (`solveur.py`, was CC 16) split into `_cached_model` (the cache get/build/put
    sequence, now trivial once the cache is an object), `_solve_model` and
    `_infeasible_solution` (the GLOP infeasible/unbounded/Farkas-certificate branch);
    each at most CC 10 (rank B or better).
    `_solve_with_area_cuts` (`cuts.py`, was CC 12) split off its per-iteration
    tighten-or-give-up step into `_tighten_if_short`; under CC 10.

**Ratchet**: `MAX_VIOLATIONS` moved from 28 to 26 across items 16-17 (`solve` and
`_solve_with_area_cuts`). Verified: full suite green (no regressions), `mypy src`
clean, `radon cc solveur.py cuts.py -n C -s` empty, coverage 89.27% (ratchet 88.8%),
`mkdocs build --strict` clean.

### 5. `solve` — done

18. Removed the legacy `cuts`/`rooms`/`ctx` parameters and `_add_cuts` from
    `frank_wolfe` (`frank_wolfe.py`). Verified unreferenced by a repo-wide grep (not from
    memory) before deleting: no source file or test ever passed `cuts=`, `rooms=` or
    `ctx=` to `frank_wolfe` (the identically-named `cuts=` on `lmo.solveur.solve` is a
    different, still-used mechanism, untouched). The `active_cuts`/`n_cuts` bookkeeping
    that only existed to feed that dead path is gone too; `Iteration.n_cuts` now always
    reports `0` from this function (the field itself is unchanged, part of `Trace`'s
    public schema). This alone brought `frank_wolfe` from CC 32 to CC 28 by deleting
    dead branches, before any extraction.
19. Extracted `_step_away` (the away-direction decision, Lacoste-Julien & Jaggi 2015),
    `_line_search` (the backtracking loop) and `_update_weights` (mass transfer, pruning,
    renormalization) out of `frank_wolfe`'s main loop; also extracted `_final_diagnostics`
    (the post-loop gap/duals computation, previously two near-duplicate `if`/`elif`
    branches). `_step_away`, `_line_search` and `_update_weights` are
    independently tested (`tests/unit/test_frank_wolfe_steps.py`) against the formulas
    in `docs/formules/frank-wolfe.md`. `frank_wolfe` itself is now CC 9 (from 32); every
    function in the file is under CC 10 (`_update_weights` CC 8 and `_final_diagnostics`
    CC 7 are the highest of the new helpers).
20. Added `StepStrategy`, a `Protocol` with one method (`propose`: gradient, x, the LMO
    vertex, active vertices and weights → direction, its max step, and whether it is an
    away step), and `AwayStepStrategy` as the built-in default implementing the existing
    away/plain-FW choice. `frank_wolfe` gained an optional `strategy: StepStrategy | None
    = None` parameter (`None` uses `AwayStepStrategy(enabled=away_steps)`, so the
    existing `away_steps` flag keeps working unchanged); a new step rule is now a class
    satisfying the protocol, passed in, with no edit to `frank_wolfe` itself. Covered by
    `tests/unit/test_frank_wolfe.py::test_a_strategy_replaces_away_steps` (an injected
    `AwayStepStrategy` matches the `away_steps=` flag bit-for-bit) and
    `test_a_custom_strategy_is_consulted_every_iteration` (a minimal custom strategy is
    called and its choice honored).

**Ratchet**: `MAX_VIOLATIONS` moved from 26 to 25 across items 18-19. Verified: full
suite green (no regressions), `mypy src` clean, `radon cc frank_wolfe.py -n C -s` empty,
coverage 89.48% (ratchet 88.8%), `mkdocs build --strict` clean, `test_language.py` and
`test_neutrality.py` green.

### 6. `light` — done (21 done, 22 skipped, 23 done)

21. Added `types.INDICATOR_SENSE` (`Indicator -> "<=" | ">="`, `"ASE"` the only `"<="`)
    and `types.indicator_sign` (`-1.0`/`1.0`), next to the existing `REGIMES` registry —
    same shape, same file, no new pattern. Replaces the five `indicator == "ASE"` sign
    flips (`light/analytique.py` x2, `light/simulateur.py` x2, `light/protocole.py` x1)
    and two comparison-direction branches (`certify/rapport.py`,
    `uq/conforme.py`), plus two other spots that separately repeated the four-name list
    (`light/base.py`'s `_analytique` cache size and `DenseSurrogate.load`'s validation).
    **Scoped down from the plan's own wording**: no `unit`/`range` fields — nothing in
    the codebase reads a unit or a numeric range for an indicator today (grepped first);
    adding them now would be exactly the unrequested, unused abstraction
    `python-design-patterns`/ponytail's `lite` check exists to catch. Add them if and
    when a real caller needs one. Covered by `tests/unit/test_shared_types.py`:
    `test_the_indicator_registry_covers_every_indicator`,
    `test_ase_is_the_only_lower_is_better_indicator`, `test_indicator_sign_matches_the_sense`,
    `test_no_module_spells_out_the_ase_comparison_again` (greps `src` for `== "ASE"`
    outside `types.py`, the same style as the existing `test_the_indicator_literal_is_written_once`).
    Verified: full suite green, `mypy src` clean, coverage 89.53% (ratchet 88.8%),
    `mkdocs build --strict` clean. No complexity change (duplication removal, not a
    CC reduction); ratchet stays at 25.
22. **Skipped, found premature by design review (`python-design-patterns` +
    ponytail-lite gut check, confirmed with the user before touching code)**:
    splitting `DenseSurrogate` (`light/base.py`) into model/trainer/serializer objects.
    It is a cohesive ~260-line class (weights + `evaluate`/`gradient`/`fit`/`save`/
    `load`) with a single consumer (`LearnedSurrogate`) and no test or caller currently
    blocked by the coupling — nothing wants a different trainer or a different
    serializer for it, and the trainer would still need write access to the model's
    weights either way, so the split moves coupling around rather than removing it.
    Revisit if a second training strategy or a second serialization format is ever
    actually needed.
23. Added `types.Fingerprintable` (`@runtime_checkable Protocol`, one property:
    `weights_fingerprint: str`) and implemented it on `DenseSurrogate`
    (`light/base.py`), reusing the same SHA-256-over-weight-arrays computation
    `uq.gestion._model_fingerprint`'s fallback already did by guessing at `W1`/`b1`/...
    attribute names. `_model_fingerprint` already checked for a `weights_fingerprint`
    attribute first (added for third-party models), so no change was needed there:
    `DenseSurrogate` now takes that fast, explicit path instead of the by-name
    guessing, and survives an internal rename that the guessing would silently miss.
    The guessing fallback is kept for genuinely unknown third-party models (e.g. a raw
    `torch` module) that cannot be asked to implement an archlux protocol. Lives in
    `types.py` (not `light/protocole.py`) because `uq` may import `types` but not
    `light` (`ARCHITECTURE.md` §5 layering). Covered by
    `tests/unit/test_substitut_dense.py`:
    `test_dense_implements_fingerprintable`,
    `test_an_untrained_model_refuses_to_fingerprint`,
    `test_freeze_and_issue_uses_the_explicit_fingerprint`.
    Verified: full suite green, `mypy src` clean, coverage 89.38% (ratchet 88.8%),
    `mkdocs build --strict` clean. No complexity change; ratchet stays at 25.

### 7. `orient` — done

24. Added `orient.circulaire.sector(deg, n_sectors, *, center=True)`: the centered
    (compass-rose) or edge-aligned sector index of one or many azimuths, vectorized.
    `stratify` now calls it instead of repeating the formula; `light/analytique.py`'s
    `sector_factor` (was `int((azimut + 22.5) // 45.0) % 8`, hand-rolled,
    scalar-only) now calls `sector(azimut, 8)` too — same result, now shared. `bench/rapport.py` already delegated
    to `stratify`; nothing to change there.
    **`uq` found infeasible, documented, not done, same class of problem as blocks 2/3's
    skipped items**: `uq.fiabilite.stratify_by_orientation` keeps its own copy of the
    edge-aligned half of the formula, because `uq` may only import `types` and `errors`
    (`ARCHITECTURE.md` §5) — not `orient`, where `sector` lives — and the exemption this
    would need is one more than the project's cap of 3, already fully spent. The two
    functions were already documented as intentionally different partitions (centered
    vs edge-aligned), so this is a real, pre-existing architectural boundary, not new
    duplication created by this item.
    Covered by `tests/unit/test_circulaire.py`:
    `test_sector_centered_matches_stratify`, `test_sector_edge_aligned_starts_at_zero`,
    `test_sector_wraps_negative_and_over_360_degrees`, `test_sector_is_vectorized`.
    Verified: full suite green, `mypy src` clean, `tests/test_dependances.py` green
    (no new cross-layer import), coverage 89.41% (ratchet 88.8%), `mkdocs build
    --strict` clean, `test_language.py`/`test_neutrality.py` green. No complexity
    change; ratchet stays at 25.

### 8. `uq` — done

25. **Already satisfied by block 6, item 23**: `DenseSurrogate` implements
    `Fingerprintable` and `_model_fingerprint` already checked for that attribute
    first, so it takes the explicit path with no change needed here. The `W1..b3`
    guessing loop in `_model_fingerprint` is **not** removed — rereading this item
    against the actual code: that loop is the documented fallback for third-party
    models (a raw ``torch`` module, or anything else that cannot be asked to
    implement an archlux protocol), named explicitly in `freeze_and_issue`'s own
    docstring ("weights (numpy arrays `weights` / `W*`) are frozen. An already
    computed `weights_fingerprint` attribute is used as is."). Removing it would
    drop that documented support for no benefit to the one first-party caller, which
    already takes the fast path. Nothing further to do.
26. **Audited, one found and fixed.** Checked every `nan`/`isnan`/`isfinite`/`errstate`
    site in `uq`, `certify` and `light`. **Found**: `fiabilite.reliability_diagram`
    caught *every* `InvariantViolation` from `conformal_quantile` and wrote `nan`,
    although its docstring documented only the "level too demanding for `n`" case: a
    level outside `]0, 1[` or a single `nan` truth gave a silent `nan`. **Fixed**: both
    now raise `InvariantViolation`; the `nan` sentinel is kept only for the documented
    too-small-`n` case, detected by comparing the conformal rank with `n` rather than by
    catching the exception. Explicit, documented sites left as they are: every other
    `isfinite` check in `uq` (`conforme.py`, `derive.py`, `fiabilite.py`) raises
    `InvariantViolation`; `certify/farkas.py` returns a `nan` margin with reason
    "non-finite multiplier" (~l. 76) and a `-inf` margin with reason "unbounded variable"
    (~l. 108), both with `valid=False`; `certify/borne.py` returns `None` (`NOT
    EVALUABLE`) when `σ̂` is not positive and finite (~l. 113); `certify/proof.py`'s
    displacement computation turns a `NaN` gap into `inf` with a comment explaining why
    (`max()` would otherwise silently drop it).

### 9. `certify` — item 27 skipped by the maintainer, item 28 done

27. **Skipped, confirmed with the maintainer before starting.** Asked whether to do the
    `GeometricProof` schema change: no schema work (additive minor or a v3), CC
    reduction only. `GeometricProof` keeps its four fixed boolean fields; no change to
    `io/json_io.py`'s migration machinery.
28. Broke `verify_infeasibility` (`farkas.py`, was CC 20), `rational_tiling` and
    `verify_exactly` (`proof.py`, were CC 23 / 22) under CC 10 by pure extraction, the
    same method as blocks 3-5, with item 27 skipped: no predicate type to lean on, so
    each function's existing branches were named and extracted as-is.
    - `verify_infeasibility`: `_accumulate` (the inequality/equality row-weighting
      loop, shared by both, previously duplicated almost verbatim) and
      `_lowest_over_box` (the box-minimization loop, returning the name of the first
      unbounded variable instead of raising, since the caller needs the name for its
      message). Now exactly CC 10 (rank B).
    - `rational_tiling`: `_identified_boxes` (the raw-rooms-to-`Fraction`-boxes and
      edge-identification setup), `_box_violations` (thin-room / outside-outline),
      `_pairwise_overlaps`, `_coverage_violation`. Now CC 5.
    - `verify_exactly`: `_malformed_rooms` and `_overlap_and_gaps` (the
      rational-vs-GEOS branch, including the overlap-triggers-a-GEOS-gap-fallback
      case). Now CC 8.
    One caller each for all three (`api.py`'s `_refusal`/`.prove()`, and
    `rational_tiling`'s own caller `verify_exactly`), confirmed with `graphify explain`
    before touching them.
    **Caught by the test suite, not by review**: the first `verify_exactly` extraction
    moved `@renamed_parameters({"fusions": "merges"})` so it decorated the newly
    inserted `_malformed_rooms` instead of `verify_exactly` — an `Edit` whose anchor
    text didn't include the decorator line. `test_parameter_aliases.py` failed
    immediately (`KeyError: '__renamed_parameters__'`); fixed by moving the decorator
    back. Left here as the reason every block in this phase re-runs the full suite
    before committing, not just `mypy`/`ruff`/targeted tests.
    `_areas` (CC 11) and `_interiors` (CC 12) in the same file are **not** named by
    this item and were left alone — out of scope creep, not an oversight.

**Ratchet**: `MAX_VIOLATIONS` moved from 25 to 22 across the three named functions.
Verified: full suite green, `mypy src` clean, coverage 89.41% (ratchet 88.8%),
`mkdocs build --strict` clean, `test_language.py`/`test_neutrality.py` green.

### 10. `feasibility`

29. Move the business logic out of `feasibility/__init__.py` into `verdict.py`; the
    package root re-exports.
30. Share `_solve_l1` between `feasibility` and `api` (today likely duplicated or
    near-duplicated — confirm at the commit, not from memory).

### 11. `api`

31. Replace the two `pavage`/tiling-related booleans with one `pavage: TilingMode |
    None` (or equivalent single value), resolving the parameter-alias question left
    open by PLAN.md 3.9 (see PR #17, already merged) for this specific parameter pair.
32. Confirm `legalize`'s pipeline (`_Problem`, `_build_problem`, `_admits`, from PR #8)
    is still under CC 10 end to end after blocks 2–10 land; extract further only if a
    later block pushed it back up.

### 12. `active`

33. Add a `Batch(x, orientations)` value object replacing the positional tuples `Loop`
    passes around.
34. Add an `Adjustable` protocol for what `Loop.run` expects from a surrogate
    (`fit`/`evaluate`/`gradient`), replacing the `getattr(surrogate, "fit", None)` duck
    typing found and fixed during PLAN.md 3.9 wave 5 batch 5.
35. Derive every seed in `active` through `bench.graines.derive`, not a local scheme.
36. Break `Loop.run` (CC 29, the highest after `_convertir`) under CC 10 using the
    `Batch`/`Adjustable` types from the two commits above.

### 13. `export`

37. Split `_write_spf_minimal` (`ifc.py`, CC 17) by IFC entity (one function per
    `IFCBUILDINGSTOREY`/`IFCSPACE`/`IFCRELCONTAINEDINSPATIALSTRUCTURE`... block).
38. Make `pathologie.py`'s `diagnose` (CC 19) read overlaps from `Plan.certificate`
    when one is already attached, instead of recomputing them — verify the call sites
    that diagnose an uncertified plan still work standalone.
39. Add missing SVG rendering tests (`export/svg.py`) if the coverage gap from the
    branch-coverage baseline (block 0.3) shows one.

### 14. `data`

40. Split `chargeurs.py` into `msd.py` (`load_msd`, `MSDApartment`), `labels_sd.py`
    (`load_sd_labels`, `label`), `decoupage.py` (already separate — confirm no overlap
    remains after the split).
41. Add an `MSDSettings` parameter object replacing `load_msd`'s eight keyword
    parameters (`regulation`, `max_rooms`, `max_rectangles`, `snap_tolerance`,
    `merge_tolerance`, `excluded_types`, `stats`, `limit`).
42. Break `_convertir` (CC 38, the single worst function in the codebase) into its
    four named stages, already described in its own docstring: straighten, snap,
    decompose, attach openings. One stage per commit, each independently testable.
43. Decide `imputation.py`'s fate: wire it into a loader path that uses it, or remove
    it if it has no caller (confirm at the commit — PLAN.md flags this as open).

### 15. `bench`

44. Extract the generic Wilson-interval summary duplicated in `experiments/j8_generation.py`
    into `bench` (a reusable function, not a copy per experiment script).
45. Raise `bench/stats.py`'s test coverage past 90% if the branch-coverage baseline
    (block 0.3) shows a gap.

### 16. `experiments/`

46. Audit every script against §11 (`ARCHITECTURE.md`): under 50 lines, public API
    only, no import of another script's private function. Split or trim the ones that
    fail, one script per commit.

### 17. Cross-cutting (last, after every block above)

47. Add `structlog` events to `api`, `solve`, `data`, `export` at the points PLAN.md
    names (Frank-Wolfe iterations, load rejections, fallbacks) — additive, no behaviour
    change.
48. Fill the missing NumPy `Parameters`/`Returns` docstring sections (54 measured
    before phase 3.9; recount at this commit, since the English-API waves touched most
    of them) and wire `numpydoc validate` into CI.

## Decision Document

- **Order**: strictly the dependency order above (imports/layers → types → geom → lmo →
  solve → light → orient → uq → certify → feasibility → api → active → export → data →
  bench → experiments → cross-cutting). A block starts only once every block above it in
  this list is merged, so no block's tests chase a moving foundation.
- **Patterns**: exactly the ones PLAN.md's phase-4 table names per block (facade,
  entities, SRP, explicit cache, parameter object, strategy, registry/protocol,
  composite, pipeline, value object). No new pattern introduced without a specific CC or
  coupling problem it solves.
- **Schema**: block 9 (certify, predicates) is the only one that can touch the JSON
  schema. Everywhere else, a refactor commit changes internal structure only — the
  public function/class signatures from PLAN.md 3.9 do not move again in this phase.
- **Aliases**: a symbol relocated between modules (e.g. `ModelTrace`/`Manifest` to
  `bench`, `diagnostic.py` to `data/`) keeps a deprecated alias at its old import path
  until 1.0.0, the same helper and rule as PLAN.md 3.9 (ADR 0001).
- **Not touched**: no public function signature changes except the two named in block
  11 (`pavage`/tiling) and, if block 9 needs it, the certificate's `performance`/
  `geometry` shape — both flagged for an explicit decision before their commit, not
  assumed.

## Testing Decisions

- A good test here checks **external behaviour** (a function's output for a given
  input, a class's public contract) — never that a specific private helper was called,
  since block-internal helpers are exactly what a refactor commit is allowed to move,
  rename or merge.
- Entry condition per block (Q-M8): if the block's property tests or frozen reference
  cases are missing, add them **before** the first structural commit of that block, in
  their own commit, pinning current behaviour.
- Coverage: enable `pytest-cov --cov-branch` first (block 0.3) to get a real branch
  number; the 92.0% line coverage already measured is the floor to raise to 95%, not the
  final target on its own.
- `radon cc <path> -n C` runs on every touched file as part of that commit's own
  verification, not only at the end of the phase.
- Prior art: the neutrality check (`tests/test_neutrality.py`) already proves a
  rename/refactor commit changed zero bytes of output; the same corpus and comparison
  apply here. The property tests in `tests/properties/` are the reference for "tests
  external behaviour, not implementation" in this codebase.

## Out of Scope

- Any change to a public function or class **signature**, except the two explicitly
  named above (block 11's `pavage` parameter, and block 9's predicate type if the
  maintainer confirms the schema move).
- New features (CLI, DXF input — PLAN.md phase 5) and the scientific-program work
  (PLAN.md phase 6).
- Translating `AUDIT.md` and `PLAN.md` themselves (still out of scope per PLAN.md 3.9's
  own tracks E22/E23).
- Performance work beyond what a smaller function naturally gives; the LP cache
  (block 4) is about correctness (thread safety) and testability, not speed.

## Further Notes

- **Size**: roughly 48 commits across 16 blocks plus tooling and cross-cutting, similar
  order of magnitude to PLAN.md 3.9's ~60. Blocks are independent enough that they could
  be split across sessions or contributors once a block starts, but never reordered
  ahead of a block they depend on.
- **Risks**: `_convertir`'s split (block 14) and `deduce_grid`/`deduce_order`'s splits
  (block 3) are the riskiest — dense, already-optimized geometric code where an
  extraction can silently change a floating-point path. The neutrality check and the
  frozen reference cases are the safety net; do not merge a split of these three without
  both green.
- **Open question for the maintainer.** Block 9 (certify → predicates) is a schema
  question, not just a refactor: does `GeometricProof` becoming a tuple of named
  predicates bump the JSON schema to v3, or stay v2 with an additive field? This needs
  an answer before block 9's first commit, the same way PLAN.md 3.9 flagged the
  parameter-alias question before wave 5.
