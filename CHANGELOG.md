# Journal des modifications

Format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnement semantique.

> Regle propre au projet : tout changement de comportement de l'oracle (`lmo`) ou du
> certificat (`certify`) est une **version majeure**. Un certificat produit en `1.2.0`
> doit rester reproductible en `1.2.x`.

## [Non publie]

### Changed — PLAN.md phase 4, block 13 (`export`): IFC entity split, diagnose under CC 10, SVG at 100% branch coverage

- `_ecrire_spf_minimal` (`export/ifc.py`, was CC 17) split into `_SpfWriter` (the shared STEP-entity buffer, now explicit state instead of closures) and one function per IFC entity block (`_write_header`, `_write_project`, `_write_spatial_hierarchy`, `_write_spaces`, `_write_walls`, `_write_openings`, `_write_certificate_annex`). Verified byte-identical output via a SHA-256 comparison before/after the split.
- `diagnose` (`export/pathologie.py`, was CC 19) split into `_room_pathologies`, `_wall_pathologies`, `_orphan_opening_pathologies`, `_outline_pathologies`, `_overlap_pathologies`. **Scoped down from the plan's own wording**: does not read overlaps from an attached `Plan.certificate` instead of recomputing them — nothing ties a certificate to having actually been computed from the plan it is attached to, and trusting it would reintroduce the "believe a prior computation on its word" pattern the project forbids for the solver, here for BIM export. See `docs/plans/phase-4-design-patterns.md`.
- `export/svg.py`'s branch coverage gap (98.1%, `_etendue`'s empty-extent fallback) closed with a new test; now 100%.
- The complexity ratchet (`tests/test_complexity.py::MAX_VIOLATIONS`) moves from 20 to 18.

### Changed — PLAN.md phase 4, block 12 (`active`): `Batch` value object, `Adjustable` protocol, `Loop.run` under CC 10

- `Batch(x, orientations)` (`active/boucle.py`): replaces the parallel `xs`/`orientations` lists `Loop` passed to its own helpers. Scoped to internal use: `Loop.run`'s public parameter list is unchanged, since merging it into `Batch` too would break every existing caller.
- `light.protocole.Adjustable` (`Surrogate` + `fit`, `@runtime_checkable`): `Loop` now checks `isinstance(surrogate, Adjustable)` instead of `getattr(surrogate, "fit", None)`. The legacy `ajuster` fallback (pre-English-rename surrogates) stays attribute-based.
- `Loop.run` (was CC 29) split into `_validate_run_inputs`, `_seed_calibration`, `_run_cycle`, `_fit_cycle`, `_recalibrate_cycle`; now CC 6. `Loop`'s own class-aggregate complexity drops from 11 to 5.
- **Found stale, not applicable**: deriving `active`'s seeds through `bench.graines.derive` — `active` may not import `bench`, and `bench.graines.derive` is itself a thin wrapper around `archlux.seeds.derive`, which `active` already calls directly.
- New tests in `tests/unit/test_actif.py`.
- The complexity ratchet (`tests/test_complexity.py::MAX_VIOLATIONS`) moves from 22 to 20.

### Changed — PLAN.md phase 4, block 10 (`feasibility`): business logic moved to `verdict.py`

- `FeasibilityCertificate`, `Verdict`, `is_feasible` and `_legalize_any_dimensions` moved from `feasibility/__init__.py` to `feasibility/verdict.py`; the package root is now a four-line re-export plus the existing deprecated-alias shim, the same shape as every other package. No import-cost change: `feasibility` is already imported lazily by the root package.
- New `tests/unit/test_feasibility_package.py`.
- **Found stale, not applicable**: item 30, sharing `_solve_l1` between `feasibility` and `api`. No such function, or any solving logic at all, exists in `feasibility` — `is_feasible` delegates entirely to `archlux.api.legalize`. Nothing to deduplicate.

### Audited — PLAN.md phase 4, block 11 (`api`): both items already closed, no code change

- Item 31 (merge two tiling-related booleans into one `TilingMode`): `legalize` has exactly one tiling parameter, `tiling: bool` (`pavage` is only its deprecated alias) — already resolved by the earlier `pavage` → `tiling` rename. No second boolean exists to merge.
- Item 32 (confirm `legalize`'s pipeline stayed under CC 10 through blocks 2-10): confirmed, `radon cc api.py -n C -s` is empty; the highest function is CC 7.

### Changed — PLAN.md phase 4, block 9 (`certify`): three functions under CC 10

- `verify_infeasibility` (`certify/farkas.py`, was CC 20) split into `_accumulate` (the inequality/equality row-weighting loop, previously duplicated almost verbatim) and `_lowest_over_box`; now CC 10.
- `rational_tiling` (`certify/proof.py`, was CC 23) split into `_identified_boxes`, `_box_violations`, `_pairwise_overlaps`, `_coverage_violation`; now CC 7.
- `verify_exactly` (`certify/proof.py`, was CC 22) split into `_malformed_rooms` and `_overlap_and_gaps`; now CC 6.
- The complexity ratchet (`tests/test_complexity.py::MAX_VIOLATIONS`) moves from 25 to 22.
- **Skipped by design, confirmed with the maintainer first**: item 27, turning `GeometricProof`'s fixed boolean fields into a tuple of named predicates. No schema change this phase; `GeometricProof` and `io/json_io.py`'s migration machinery are unchanged. See `docs/plans/phase-4-design-patterns.md`.
- Blocks 8 (`uq`) closed with no code change: both its items were already satisfied by earlier work or, on audit, found nothing to fix. See the plan doc.

### Added — PLAN.md phase 4, block 7 (`orient`), item 24: shared `sector()`

- `orient.circulaire.sector(deg, n_secteurs, *, center=True)`: the centered (compass-rose) or edge-aligned sector index of one or many azimuths, vectorized. `stratify` now calls it instead of repeating the formula; `light.analytique.sector_factor` (was a hand-rolled, scalar-only formula with no wraparound past 360°) calls it too. `bench.rapport` already delegated to `stratify`.
- **Found infeasible, documented, not done**: `uq.fiabilite.stratify_by_orientation` keeps its own copy of the edge-aligned half of the formula, because `uq` may not import `orient` (`ARCHITECTURE.md` §5) and the exemption this would need exceeds the project's cap of 3, already spent. The two were already documented as intentionally different partitions (centered vs edge-aligned). See `docs/plans/phase-4-design-patterns.md`.
- New tests in `tests/unit/test_circulaire.py`.

### Added — PLAN.md phase 4, block 6 (`light`), item 23: `Fingerprintable` protocol

- `types.Fingerprintable` (`@runtime_checkable Protocol`, one property: `weights_fingerprint: str`), implemented on `DenseSurrogate`. `uq.gestion._model_fingerprint` already checked for this attribute before guessing at `W1`/`b1`/... by name; `DenseSurrogate` now takes that explicit path and survives an internal rename the guessing would silently miss. The guessing fallback stays for third-party models (e.g. a raw `torch` module) that cannot implement an archlux protocol.
- Lives in `types.py`, not `light/protocole.py`, because `uq` may import `types` but not `light`.
- **Skipped, found premature, item 22**: splitting `DenseSurrogate` into model/trainer/serializer objects. A cohesive class, one consumer, no caller blocked by the coupling; the split would move coupling around, not remove it. See `docs/plans/phase-4-design-patterns.md`.
- New tests in `tests/unit/test_substitut_dense.py`.

### Added — PLAN.md phase 4, block 6 (`light`), item 21: `INDICATOR_SENSE` registry

- `types.INDICATOR_SENSE` (`Indicator -> "<=" | ">="`) and `types.indicator_sign` (`-1.0`/`1.0`): replace six `indicator == "ASE"` sign flips (`light/analytique.py`, `light/simulateur.py`, `light/protocole.py`, `uq/conforme.py`) and two comparison-direction branches (`certify/rapport.py`, `uq/conforme.py`), plus two spots that separately repeated the four-indicator-name list (`light/base.py`).
- Scoped down from the plan's own wording: no `unit`/`range` fields, since nothing in the codebase reads either today. Add them when a real caller needs one.
- New tests in `tests/unit/test_shared_types.py` cover the registry and grep `src` for any remaining `== "ASE"` outside `types.py`.

### Changed — PLAN.md phase 4, block 5 (`solve`): dead legacy path removed, `frank_wolfe` under CC 10, injectable step strategy

- Removed `frank_wolfe`'s legacy `cuts`/`rooms`/`ctx` parameters and `_add_cuts` (unreferenced by any source file or test, confirmed by a repo-wide grep before deleting): brought `frank_wolfe` from CC 32 to CC 28 by deleting dead branches alone.
- `frank_wolfe` (`solve/frank_wolfe.py`) split into `_step_away`, `_line_search`, `_update_weights` and `_final_diagnostics`; now CC 9. Every function in the file is under CC 10.
- New `StepStrategy` protocol (one method, `propose`) and `AwayStepStrategy`, the built-in default: `frank_wolfe` gains an optional `strategy: StepStrategy | None = None` parameter, so a new step rule plugs in without editing `frank_wolfe` itself. The existing `away_steps` flag keeps working unchanged (`None` uses `AwayStepStrategy(enabled=away_steps)`).
- New tests in `tests/unit/test_frank_wolfe.py`: an injected `AwayStepStrategy` matches the `away_steps=` flag bit-for-bit, and a minimal custom strategy is consulted every iteration.
- The complexity ratchet (`tests/test_complexity.py::MAX_VIOLATIONS`) moves from 26 to 25.

### Changed — PLAN.md phase 4, block 4 (`lmo`): injectable cache, two functions under CC 10

- `CacheLP` (new, `lmo/solveur.py`): replaces the module-global `_CACHE` dict (keyed by `id(poly)`, no locking) with an explicit, thread-safe (`threading.Lock`), injectable object (`get`/`put`/`clear`). `solve()` gains an optional `cache: CacheLP | None = None` parameter; a module-level `_DEFAULT_CACHE` keeps existing call sites and `clear_cache()` working unchanged.
- `solve` (`lmo/solveur.py`, was CC 16) split into `_cached_model` and `_infeasible_solution`; both under CC 10.
- `_solve_with_area_cuts` (`lmo/cuts.py`, was CC 12) split off `_tighten_if_short`; now under CC 10.
- New `tests/unit/test_cache_lp.py`: `CacheLP` in isolation (empty-start, put/get, clear, eviction beyond `maxsize`, two independent instances not seeing each other), `solve` giving the identical answer regardless of which cache serves it, and a `threading.Thread`-based concurrency test.
- The complexity ratchet (`tests/test_complexity.py::MAX_VIOLATIONS`) moves from 28 to 26.

### Changed — PLAN.md phase 4, block 3 (`geom`): five functions under CC 10

- `deduce_grid` (`geom/pavage.py`, was CC 31) split into `_deduce_lines` (+ `_anchor_outline_vertices`), `_room_bounds`, `_verify_partition`; now an orchestrator, under CC 10.
- `deduce_order` (`geom/graphe.py`, was CC 33) split into `_pairwise_order`, `_outline_envelope`, `_wall_sides_and_groups` (itself split into `_assign_group_sides`, `_group_members`, `_bounding_hull`, `_assign_wall_side_for_group`); now under CC 10.
- `freeze_contacts` (`geom/polytope.py`, was CC 16) split off `_frozen_bounds`; now under CC 10.
- `_coupe_verticale`/`_coupe_horizontale` (`geom/rectilineaire.py`, were CC 14 each): their duplicated GEOS-geometry-type branch and collinear-piece-joining loop factored into shared `_line_pieces`/`_chord_through_pivot` helpers instead of split in place. Both now under CC 10.
- The complexity ratchet (`tests/test_complexity.py::MAX_VIOLATIONS`) moves from 33 to 28.
- **Found infeasible, documented, not done**: moving `diagnostic.py` to `data/` (PLAN.md's own block-3 item) hits the same wall as block 2's `ModelTrace`/`Manifest` move — a deprecated shim would need `geom` to import `data`, the wrong direction, and the exemption this needs exceeds the project's cap of 3. Splitting `pavage.py` into `trame.py` is also not done: superseded by the CC-reduction extractions, which already meet the exit-gate's concrete requirement; the file-organization half stays open. See `docs/plans/phase-4-design-patterns.md`.

### Added — PLAN.md phase 4, block 2 (`types`): `legalize_trace`, `vectorize`

- `legalize_trace(plan, ctx, ...) -> (Plan, Trace | None)`: the Frank-Wolfe trace as a return value instead of `Plan.trace`. `legalize(..., trace=True)` still works, now deprecated (warns, points at `legalize_trace`); `None` in classic mode (no Frank-Wolfe pass).
- `archlux.types.vectorize(plan)` and `FIELDS_VECTOR`: the plain `(x, y, w, h)`-per-room encoding, no solver index needed, next to (not replacing) `geom.polytope.vectorize`. `light.jetons.plan_to_vector` now delegates to it instead of duplicating the computation.
- Migrated four internal test call sites from `legalize(trace=True)` to `legalize_trace(...)`.
- **Found infeasible, documented, not done**: moving `ModelTrace`/`Manifest` into `bench` (PLAN.md's own block-2 item) would need `io.json_io` and `certify.rapport` to import `bench`, a leaf nobody may import; the two nominal exemptions that would require exceed the project's existing cap of 3 (already spent on `types`'s own three). See `docs/plans/phase-4-design-patterns.md`.

### Added — PLAN.md phase 4, block 1 (imports and layers): dynamic dependency check

- `tests/test_dependances.py` gets `test_a_fresh_import_loads_only_the_declared_layers`: for every top-level package, a fresh subprocess import is checked against `sys.modules`, a dynamic complement to the existing static AST walk (which cannot see a computed `importlib.import_module` call). Covers `api` like every other package, through a transitive closure of the existing `AUTORISE` declarations.
- `__version__`'s import path confirmed already correct (`_version.py` is a genuine leaf); no change needed.
- This closes PLAN.md phase 4, block 1.

### Added — PLAN.md phase 4, block 1 (imports and layers): lazy certify and light facades

- `archlux.light` and `archlux.certify` are now lazy facades: asking for one name (e.g. `light.Daylight` or `certify.render`) imports only the module that defines it, not every sibling submodule. Verified empirically (`tests/unit/test_lazy_facades.py`, fresh-interpreter subprocess checks) — `light.Daylight` no longer loads `analytique`/`simulateur`; `certify.render` no longer loads `proof`/`borne`.
- `tests/test_dependances.py`'s leaf allow-list gets `importlib` for `_deprecation` (needed by the new lazy resolution, added below).

### Added — PLAN.md phase 4, block 0: complexity and coverage tooling

- `radon` added as a dev dependency; a ratchet test (`tests/test_complexity.py`) tracks the number of functions above cyclomatic complexity 10 (33 today), lowered block by block until it reaches zero (phase 4's exit gate). Not wired into CI as a hard gate yet — that would fail on every commit until the whole phase is done.
- Branch coverage enabled (`--cov-branch`); the coverage ratchet floor moves from 87.9% to 88.8% (measured with branches counted).
- `docs/plans/phase-4-design-patterns.md`: the phase-4 refactor plan, block by block, with `graphify` (call-graph mapping before an extraction) and `ponytail` (`lite` intensity, a design-time check against over-applying a pattern) verified compatible and scoped for this phase; every block now also sweeps its own files for remaining French-named private helpers (19 found so far) ahead of its structural commits.

### Changed — old keyword names of public functions accepted again, deprecated

- **Renamed keyword parameters of public functions stay accepted** with a
  `DeprecationWarning` until 1.0.0 (ADR 0001 rule 6, applied to parameters; this closes
  the "open decision" of wave 5). Fifty-one functions renamed a keyword with no alias, and
  an old call failed with a bare `TypeError`: `to_ifc(plan, chemin=...)`,
  `verify_exactly(..., fusions=...)`, `snap_to_grid(plan, trame=...)`,
  `render_svg(plan, contour=...)`, `bench.run(..., repertoire=...)`, `holm(p_valeurs=...)`...
  The table was built by comparing every public signature of `b35a3c8` (before the
  rename) with the current one; `tests/unit/test_parameter_aliases.py` pins it. Passing
  the old and the new keyword together raises `TypeError`. Fields and methods of classes
  stay renamed without alias, as stated below. New helper:
  `archlux._deprecation.renamed_parameters`.
- **`legalize(fusions=, pavage=, budget_reparation=)` become `merges=`, `tiling=` and
  `repair_budget=`** (and `deduce_grid(budget_reparation=)` becomes `repair_budget=`),
  old names deprecated. `merges`, not the glossary's former `merged_rooms`: it is the name
  `verify_exactly` and `minimum_area_shares` already give the same tuple. The `pavage`
  column of the published raw CSVs is unchanged; `results/` is byte-identical.
  `InvalidInput.field` for a negative budget now reads `repair_budget`, whichever name the
  caller used.
- The `tiling grid` branch of `Infeasible.relaxable` is tested; `_Problem.minima` is
  read-only; about 200 references to French names in docstrings (Sphinx roles that no
  longer resolved, numpydoc parameter names) and in the current docs name the English
  objects; `CLAUDE.md` no longer lists the `agent-skills` rows both as "routed
  automatically" and "not auto-dispatched", and says the plugin is not in the repository.

### Fixed — review of the English-API stack (PRs #3 to #16)

- **CI was red on every PR of the stack**, and its `qualite` job stopped at mypy, hiding
  the later steps: the surrogates declared `indicator -> str` against the protocol's
  literal; numpy 2.5 changed the arguments of `NDArray[float64]`; the rename tool needs
  Python 3.12 (its tests now run on 3.12+ and check the refusal on 3.11); doctests and
  the guarantee benchmark still used renamed names; `scripts/neutrality.py` was not
  formatted; the identifier guard failed on the export batch. Fixed where each defect
  was introduced, and merged up the stack.
- **Calibration lock**: freezing a `LearnedSurrogate` raised "no hashable weights": the
  fingerprint looked up `weights_fingerprint` only; it also reads `empreinte_poids`.
- **Active learning**: the loop looked up `fit` only, so a surrogate that still defines
  `ajuster` was silently never retrained; it is now retrained, with a
  `DeprecationWarning`.
- `from archlux.export import diagnostiquer` works again (deprecated alias); 16 aliases
  that no test covered are now in `test_function_aliases.py`, and the old
  `archlux.lmo.coupes` module has its own test.
- A malformed schema v1 file raised a bare `TypeError` from the v1 upgrade; it raises
  `InvariantViolation` again, as before schema v2.
- `legalize` names the members to rename when given a surrogate with the pre-0.10 French
  ones (`evaluer -> evaluate`, ...): the protocol methods have no alias.
- Input door: a flat outline is an `InvalidInput`, no longer an internal error; a numpy
  integer is a valid `budget_reparation`; a non-numeric opening position is an
  `InvalidInput`; a `Context` built positionally (whose fields shifted) is refused with
  a hint.
- The non-strict `xfail` on `test_a_saturated_budget_is_not_an_internal_error` is
  removed: it passed everywhere (XPASS) and hid the test's result either way.
- **IFC GlobalIds are stable across renames**: their per-plan salt hashed `repr` of the
  dataclasses, so renaming a class or a field changed every GlobalId of the same plan;
  it now hashes the values only, and a test pins one GlobalId.
- `from archlux.bench import ModeleTrace` works again (deprecated alias).
- `experiments/j7_sd_etiquettes.py` and `j8_visuels.py` read fields renamed in wave 3
  (`plan.murs`, `certificat`, `Glazing.ouvertures`) and would have crashed on the
  corpus.
- The input door reports `regulation.min_width`, not the French field name.
- `json_io.__all__` listed `SCHEMA_VERSION` twice; `.gitignore` follows `results/`.
- **Behaviour change, documented**: the guarantee bench labels methods by class name,
  and derives its bootstrap seed from that label; the rename of the surrogate classes
  therefore changes the `method` column of `raw_results.csv` and the bootstrap
  intervals of `archlux.bench` (no published figure depends on them).
- `results/` regenerated after the renames (statuses `GapNeedsTiling`, English room
  types in the figures) and `SHA256SUMS` updated.

### Remediation — PLAN.md phase 3.9, wave 6 (final step): rename experiences/ and resultats/

- `experiences/` becomes `experiments/`, `resultats/` becomes `results/`; `scripts/resultats.py` becomes `scripts/results.py`, and the Makefile targets follow (`results`, `check-results`, `results-corpus`).
- `src/archlux/bench/run.py`'s output filename `resultats_bruts.csv` becomes `raw_results.csv` (not asserted by any test).
- Historical, dated documents (`AUDIT.md`, `PLAN.md`, `docs/revues/*.md`, `docs/specification/MILESTONE-2.md`, and the older `CHANGELOG.md` entries) keep their old path mentions, as a record of what was written at the time.
- `docs/plans/phase-3-9-english-api.md` marks waves 0–6 done; the parameter-alias question stays open.
- **This closes PLAN.md 3.9's wave 6 and the whole English-API rename plan** (waves 0 to 6). Phase 4 (the design-pattern restructuring) is next.

### Remediation — PLAN.md phase 3.9, wave 6: rename tests/unites and tests/proprietes

- `tests/unites` becomes `tests/unit` (the glossary's own documented target, not `tests/units`); `tests/proprietes` becomes `tests/properties`. Every Python import, doc reference and the `pyproject.toml` comment are updated. `tests/references` needs no rename: the name already reads correctly in English.
- Historical, dated documents (`AUDIT.md`, `PLAN.md`, `docs/revues/*.md`, `docs/specification/MILESTONE-2.md`) are left untouched, as agreed for those tracks.
- Found and fixed along the way: a stale `RapportExport` reference in `src/archlux/types.py` (predates this wave — batch 7 renamed the class but missed this cross-module forward reference), and two glossary table rows whose parenthetical asides put `Plan`/`Manifest`/`Corruption` in backticks in the French column, which made `test_identifiers.py` treat them as banned; reworded without backticks.

### Remediation — PLAN.md phase 3.9, wave 5, seventh batch: export, data and bench

- `archlux.export`, `archlux.data` and `archlux.bench` are English: `ExportReport`, `MSDApartment`, `LoadStatistics`, `Split`, `Corruption.corrupt`, `BenchReport`, `Result`, `Interval`... Old names stay importable with a `DeprecationWarning` until 1.0.0.
- `Corruption`'s Mode values keep their French names (`deplacer`/`elargir`/`retrecir`/`aplatir`): they are recorded in raw results and seeds, so renaming them would change published figures. `Split`'s and `Corruption`'s fields are renamed without alias (fields, not classes — ADR 0001 rule 6).
- Prose of all twenty modules is translated to English and enrolled in the language and identifier guards. `legalize`'s own `fusions`/`pavage`/`budget_reparation` parameters are untouched (still the open decision; since renamed, see above).

### Remediation — PLAN.md phase 3.9, wave 5, sixth batch: uncertainty, active learning and orientation

- `archlux.uq`, `archlux.active` and `archlux.orient.circulaire` are English: `ConformalCalibrator`, `DriftReport`, `DataManagement`, `CalibrationToken`, `ActiveReport`, `RandomStrategy`, `RegressionResult`, `dominant_direction`... Old names stay importable with a `DeprecationWarning` until 1.0.0.
- `CalibrationToken` fields (`empreinte_poids`, `horodatage_gel`) and its `verifier` method, and `DataManagement`'s `pour_entrainement`/`pour_test`/`pour_calibration` methods, are renamed without alias (fields and methods, not classes/functions — ADR 0001 rule 6).
- Prose (docstrings, comments, messages) of all eight modules is translated to English and enrolled in the language and identifier guards.

### Remediation — PLAN.md phase 3.9, wave 5, fifth batch: light modules (rename only)

- `SubstitutAnalytique`, `SubstitutAppris`, `SubstitutDense`, the token helpers, `facteur_lumiere_jour`, `valider_gradient`, `Indicateur`... are English (`AnalyticSurrogate`, `plan_to_tokens`, `daylight_factor`, `validate_gradient`, `Indicator`). Old names stay importable with a `DeprecationWarning` until 1.0.0. Methods `ajuster`, `sauver`, `n_parametres` become `fit`, `save`, `n_parameters` without alias.
- `test_a_saturated_budget_is_not_an_internal_error` is marked `xfail(strict=False)`: renaming inside it changed its derandomized seed and exposed a latent defect (a saturated budget can leave a 4e-9 m² overlap that the exact proof rejects after an earlier test warmed the LP cache). Not caused by the rename; to fix in phase 4.

### Remediation — PLAN.md phase 3.9, wave 5, fourth batch (part 2): English prose of geometry and LMO

- Docstrings, comments and messages of `geom.{graphe,polytope,pavage,rectilineaire,diagnostic}`, `lmo.solveur` and `lmo.cuts` are English, and the seven modules are enrolled in the language and identifier guards.
- `SolutionLP` becomes `LPSolution` (deprecated alias kept). Parameters `duaux`, `pieces` and `a_min` become `duals`, `rooms` and `min_area` in the solver and cut functions (no alias, as for fields; deprecated keyword aliases added since, see above).
- Runtime labels of the `origins` (`separation horizontale…`, `trame x#…`) stay French for now: `certify.dual` parses them.

### Remediation — PLAN.md phase 3.9, wave 5, fourth batch: geometry and LMO names (rename only)

- Public functions, classes and fields of `geom` (`graphe`, `polytope`, `pavage`, `rectilineaire`, `diagnostic`), `lmo.solveur`, `lmo.cuts` and `export.pathologie` are English (`solve`, `build_polytope`, `RelativeOrder`, `Cut`, `Polytope.bounds`, ...).
- The French function and class names stay importable with a `DeprecationWarning` until 1.0.0; `archlux.lmo.coupes` is a module shim for `archlux.lmo.cuts`. Fields are renamed without alias.
- The prose of these modules is translated in the next commit. Neutrality fingerprints are unchanged.

### Remediation — PLAN.md phase 3.9, wave 4, step 2: JSON schema v2

#### Changed — file format (pre-1.0)
- **`Plan.to_json` writes schema v2**: English keys (`outline`, `rooms`, `walls`,
  `openings`, `certificate`, `load_bearing`, `wall_id`, `relative_width`, `geometry`,
  `valid`, `gaps`, `duals`, `manifest`, `seed`...) and English room types.
  `SCHEMA_VERSION` is `"2"`. **A file written by this release cannot be read by an older
  one**: v1 files are still read, v2 files are not readable before this release.
- **`Plan.from_json` reads v1 and v2.** A v1 file is converted by the explicit
  `archlux.io.json_io.upgrade_v1` (keys and the six French room types), then read as v2;
  loading and saving a v1 file converts it. An unknown version is refused and the message
  says `'2'` or `'1'` are accepted.
- New `archlux/io/plan-v2.schema.json` (the v1 schema stays, for reading tests); the
  reference page `docs/reference/schema-json.md` is rewritten in English for v2, with the
  v1 to v2 key table. Reader error messages that named French keys now name the v2 keys.
- The `json` neutrality fingerprint was recorded again (the text changed on purpose); the
  `geometry` fingerprint did not move: the plans mean the same.

### Remediation — PLAN.md phase 3.9, wave 4, step 1: English room types

#### Changed — data values (pre-1.0)
- The room types are English in memory: `sejour` is `living_room`, `chambre` is `bedroom`,
  `cuisine` is `kitchen`, `sdb` is `bathroom`, `wc` is `toilet`, `couloir` is `corridor`.
  `Regulation.min_areas` keys, the surrogate token encoder, the synthetic corpus and the SVG
  palette follow. **Code that builds `Room(type="sejour")` or a `Regulation` keyed by the
  French names must change**: an unknown type gets no minimum area (a warning says so).
- Schema v1 files are unchanged: the reader maps the six French values to the English ones
  and any other type passes through, the writer maps them back, so the written JSON is
  byte-identical (neutrality fingerprints unchanged). Schema v2 comes in the next step.

### Remediation — PLAN.md phase 3.9, wave 5, third batch: the surrogate protocol and the JSON module

#### Changed — API (pre-1.0)
- **Surrogate protocol**, deprecated aliases until 1.0.0 for the classes: `Substitut` is
  `Surrogate`, `Baies` is `Glazing`, `SubstitutParPiece` is `PerRoomSurrogate`. **The
  methods and the keyword of the protocol change, with no alias**: `evaluer()` is
  `evaluate()`, `incertitude()` is `uncertainty()`, `indicateur` is `indicator`,
  `evaluer_pieces()` is `evaluate_rooms()`, the keyword `baies=` is `glazing=`,
  `Glazing.murs`, `ouvertures`, `vide` are `walls`, `openings`, `empty`, and
  `WrapsSurrogate.substitut` is `surrogate`. A user-written surrogate must rename its
  methods: `isinstance(x, Surrogate)` checks them, and `legalize` raises `TypeError` for an
  object that still has the French ones.
- **`archlux.io.json_io`**, aliases until 1.0.0: `charger` is `load`, `ecrire` is `write`,
  `vers_dict` is `to_dict`, `depuis_dict` is `from_dict`, `manifeste_vers_dict` is
  `manifest_to_dict`, `VERSION_SCHEMA` is `SCHEMA_VERSION`. The messages of the reader
  and the writer are in English.
- The JSON keys stay those of schema v1 and, deliberately, so does the key `indicateur`
  inside the `.npz` archives of saved surrogates: models saved before this change still
  load. (A token rename had changed it silently; a test caught it.)

### Remediation — PLAN.md phase 3.9, wave 5, second batch: English prose of the public core

#### Changed
- `types`, `api`, the package root, `feasibility`, `certify.rapport` and `certify.borne`
  are fully in English: docstrings, comments, error messages.
- **The text of the certificate report is in English**: `GEOMETRY`, `Overlap`, `Gaps`,
  `verified`, `NOT EVALUABLE`, `[PREDICTION: coverage 90 %]`, decimal point instead of
  decimal comma. Code that matches the French text of `Certificate.report()` must change;
  documentation and tests were updated.
- Parameters: `build_bound(value, calibration, drift, *, uncertainty, regime)` (was
  `valeur`, `derive`, `incertitude`), `is_feasible(program, ...)` (was `programme`),
  `Plan.to_svg(path, title=...)`, `translate_duals(..., threshold=...)`.
- `tests/test_doctests.py` runs the `>>>` examples of every module: six examples had
  rotted after the renames (`Piece(...)`, `pieces=`) and were repaired.

### Remediation — PLAN.md phase 3.9, wave 5, first batch: public methods and functions

#### Changed — API (pre-1.0)
- Functions and one class, deprecated aliases until 1.0.0: `rendre` is `render`,
  `construire_borne` is `build_bound`, `traduire_duaux` is `translate_duals`,
  `CertificatFaisabilite` is `FeasibilityCertificate` (method `expliquer()` is `explain()`,
  no alias).
- Methods and fields, **no alias**: `Room.aire` and `centre` are `area` and `center`,
  `Wall.longueur` is `length`, `Opening.segment_absolu()` is `absolute_segment()`,
  `Plan.ids_pieces` is `room_ids`, `Certificate.rapport()` is `report()`,
  `Verdict.faisable` and `certificat` are `feasible` and `certificate`, and
  `FeasibilityCertificate.origines`, `certificat_farkas` are `origins`, `farkas_certificate`.

### Review follow-ups (after waves 0 to 3)

#### Fixed
- `python -W error::DeprecationWarning` no longer crashes when importing `legalize`: the
  OR-Tools import, whose SWIG bindings emit their own `DeprecationWarning`s and crash the
  interpreter when they are errors, is shielded in `lmo.solveur`. archlux's own modules
  raise no `DeprecationWarning`.

#### Changed — internal, no behaviour change
- `legalize` (cyclomatic complexity 22, 69 statements) is split into a private `_Problem`
  (the plan, its context and its domain) and five steps: options check, problem building,
  refusal, classic result and light optimization. `legalize` itself is now a short pipeline
  (PLAN.md phase 4, block `api`, done early). The neutrality fingerprints are unchanged.

### Remediation — PLAN.md phase 3.9, wave 3: English field names (in progress, no alias)

#### Changed — API break (pre-1.0, clean break: no deprecated alias for fields)
- Batch 3a, the 16 field names that no other class shares: `Wall.porteur` is
  `load_bearing` and `epaisseur` is `thickness`; `Opening.mur_id`, `largeur_rel`,
  `hauteur_allege`, `hauteur_linteau` are `wall_id`, `relative_width`, `sill_height`,
  `head_height`; `Structure.murs_porteurs` and `poteaux` are `load_bearing_walls` and
  `columns`; `Regulation.aires_min` is `min_areas`; `GeometricProof.chevauchement`, `jours`,
  `surfaces_ok`, `structure_preservee`, `deplacement_max` are `overlap`, `gaps`,
  `areas_ok`, `structure_kept`, `max_displacement`; `PerformanceBound.borne_sup` is `upper`;
  `Certificate.geometrie` is `geometry`. Constructor keywords change with them.
- Batch 3b, type-guided (`scripts/rename_field.py`): `Plan.pieces`, `murs`, `ouvertures`,
  `contour`, `certificat` are `rooms`, `walls`, `openings`, `outline`, `certificate`;
  `Context.referentiel`, `programme`, `contour` are `regulation`, `program`, `outline`.
  `InvalidInput.field` labels follow (`rooms[a].w`, `context.outline`...).
- Batch 3c, type-guided: `Regulation.largeur_min` and `a_min()` are `min_width` and
  `min_area()`; `GeometricProof.valide` is `valid`; `PerformanceBound.indicateur`, `valeur`,
  `borne_inf`, `couverture` are `indicator`, `value`, `lower`, `coverage`;
  `Certificate.duaux`, `manifeste` are `duals`, `manifest`; `Manifest.horodatage`, `graine`,
  `empreinte_donnees`, `decoupage`, `environnement`, `parametres`, `modele` are
  `timestamp`, `seed`, `data_fingerprint`, `split`, `environment`, `parameters`, `model`;
  `ModelTrace.poids` is `weights_fingerprint` (also the key of `ModelTrace["..."]`).
  Wave 3 is complete: no French field name is left on the model types.
- The JSON files keep their schema v1 keys (`"porteur"`, `"jours"`...): only the Python
  names moved, so old files still load and the written JSON is byte-identical.

### Remediation — PLAN.md phase 3.9, wave 2: English model classes

#### Changed — API (pre-1.0; the old names keep working, deprecated until 1.0.0)
- `Piece` to `Room`, `Mur` to `Wall`, `Ouverture` to `Opening`, `Contexte` to `Context`,
  `Referentiel` to `Regulation`, `Certificat` to `Certificate`, `PreuveGeometrique` to
  `GeometricProof`, `BornePerformance` to `PerformanceBound`, `Manifeste` to `Manifest`,
  `ModeleTrace` to `ModelTrace`. The old names are the same objects, served with a
  `DeprecationWarning` by `archlux.types` and (for the eight it exports) by `archlux`.
- `archlux.bench.Manifest` was an alias of the manifest class: it is now that class itself
  under its new name, and the duplicate is gone.
- Fields keep their French names until wave 3 (`Plan.pieces`, `Wall.porteur`...).
- The output of `legalize` on the neutrality corpus is byte-identical to before.

### Remediation — PLAN.md phase 3.9, wave 1: English exceptions

#### Changed — API (pre-1.0; the old names keep working, deprecated until 1.0.0)
- Exception classes: `OrdreIncoherent` to `InconsistentOrder`, `SeparationManquante` to
  `MissingSeparation`, `Infaisable` to `Infeasible`, `InvariantViole` to
  `InvariantViolation`, `CalibrationVerrouillee` to `CalibrationLocked`, `ModeleModifie` to
  `ModelModified`, `SubstitutInvalide` to `InvalidSurrogate`. The old names are the same
  objects (`except Infaisable` still catches), served with a `DeprecationWarning` by
  `archlux` and `archlux.erreurs`.
- Module `archlux.erreurs` is now `archlux.errors`; the old path is a shim that forwards
  every name, old and new, with a warning.
- **Attributes, no alias** (clean break): `InconsistentOrder.axe` is `axis`,
  `MissingSeparation.paire` is `pair`, `Infeasible.certificat_farkas` is
  `farkas_certificate` and `Infeasible.origines` is `origins` (constructor keywords too).
- Exception messages and docstrings are in English (`invariant violated: ...`,
  `horizontal cycle: a -> b`, `no separation between a and b`).
- The output of `legalize` on the neutrality corpus is byte-identical to before.

### Remediation — PLAN.md phase 3.9, wave 0: tooling for the English API (no rename yet)

#### Added (development tooling, no change for library users)
- `archlux._deprecation.lazy_aliases`: one helper builds the lazy deprecated aliases of a
  module; the four hand-written copies (`certify`, `certify.preuve`, `light`,
  `light.simulateur`) use it, with unchanged messages and behaviour.
- `scripts/rename_identifiers.py`: renames identifiers by token (strings and comments
  untouched), refuses names several classes define, and proves each rename by swapping the
  names back and comparing the syntax trees.
- `scripts/neutrality.py` and `tests/test_neutrality.py`: 240 legalizations of a fixed
  corpus, fingerprinted (schema v1 JSON, and a name-free geometry fingerprint); a rename
  must keep them identical. Strict on the platform that recorded the reference.
- `tests/test_identifiers.py`: migrated modules contain no French identifier; the banned
  terms are read from `docs/glossary.md`.
- Glossary: exception names, the fields of the model types and three parameters.
- Plan: `docs/plans/phase-3-9-english-api.md`.

### Remediation — PLAN.md phase 3, slice G: keyword-only types and light defaults (3.6)

#### Changed — API break (pre-1.0)
- `Piece`, `Mur` and `Ouverture` are keyword-only: `Piece("a", "sejour", 0, 0, 6, 9)`
  swapped `x, y, w, h` without a word. Use `Piece(id="a", type="sejour", x=0, y=0, w=6,
  h=9)`. `Plan` keeps its positional order.
- `Contexte.contour` is keyword-only and optional. **Positional `Contexte(structure,
  orientation, contour, referentiel)` calls break**: `referentiel` is now the third
  positional field; pass `contour=` by keyword.

#### Added
- `Plan(pieces=...)` is enough: `murs`, `ouvertures` and `contour` default to `()`.
- The outline no longer has to be given twice: `legalize` uses `Contexte.contour`, or the
  plan's when the context has none (the context's wins when both are given). Neither:
  `InvalidInput` naming `contour` and saying to give `Contexte.contour` or `Plan.contour`.
- Migration: about 270 constructions in `src/`, tests, `experiences/` and the docs were
  named mechanically (an AST rewrite, then the full suite).

### Remediation — PLAN.md phase 3, slice F: shared types (3.8)

#### Added
- `archlux.types.Indicateur`: the `Literal["sDA", "ASE", "UDI", "vue"]` written in seven
  places, now defined once. `Substitut.indicateur` returns it instead of a bare `str`.
- `archlux.arrays.VecteurF` (`NDArray[np.float64]`), a leaf module, used in place of
  `np.ndarray` in the numerical core: `geom.polytope`, `lmo`, `solve`, `light.protocole`,
  `api`, `certify.dual` and `certify.farkas`. **Limit**: mypy 1.19 with numpy 2.4 does not
  compare dtypes, so it documents the intent and is enforced only by dtype-aware checkers.
  The other ~120 `np.ndarray` of `src/` are left as they are: converting them buys nothing
  until a checker enforces the alias.

#### Fixed
- Type checkers now see `archlux.light`, `archlux.feasibility` and `archlux.legalize`
  (`TYPE_CHECKING` imports in `archlux/__init__.py`); `archlux.bench` stays dynamic, because
  no module may import it (ARCHITECTURE.md §5). Since the lazy `legalize` (slice E),
  `archlux.__getattr__` was typed `object`, which made `ax.feasibility.is_feasible` a mypy
  error: this restores it.

### Remediation — PLAN.md phase 3, slice E2: readable dual diagnostic (3.12)

#### Changed — the DIAGNOSTIC section of the certificate (`Certificat.duaux`)
- The rows of the L1 epigraph (`ecart plus/moins ...`) are no longer reported: they are
  solver artefacts, not constraints of the brief.
- Labels are business wording (`load-bearing wall p1 at x = 6 m: room chambre stays to the
  right of it`) instead of internal ones (`load-bearing p1: chambre right of 6`); a label
  that is not recognised is shown unchanged.
- The price is given for a 10 cm relaxation, with its unit: metres of total displacement in
  classic mode; in performance mode (`objective=` given) a change of the **predicted**
  indicator, said to be a surrogate prediction and not a guarantee. `traduire_duaux` takes
  `objective` and `step_m`. The stored raw price and the JSON schema are unchanged.
- Known limit: the area cuts and the tiling equalities are still not dualised, so a price
  is never given in m² (AUDIT.md §3 n°9 asked for it): it needs those rows in the
  duals, which is a solver change.

### Remediation — PLAN.md phase 3, slice D2: no bare `ValueError` (3.3)

#### Changed — error types (behaviour change, refusals only)
- The remaining `ValueError`s raised by the library are `InvalidInput` (still catchable as
  `ValueError`), with the offending `field` and English messages: `orient.circulaire`
  (`encode`, `regression_circulaire_lineaire`, `stratifier`, empty orientation lists),
  `export.svg.planche`, `geom.diagnostic.diagnostiquer` and `light.jetons.permuter_pieces`.
- `data.chargeurs` no longer swallows every exception when reading a WKT: an unreadable
  WKT (`shapely.errors.ShapelyError`, `TypeError`) rejects the apartment, anything else
  is a bug and propagates.
- `tests/unit/test_typed_errors.py` fails on any new `raise ValueError`, `raise Exception`
  or `except Exception` in `src/archlux`.

### Remediation — PLAN.md phase 3, slice E: lazy `legalize` (3.13)

#### Changed — import time
- `import archlux` takes about 45 ms instead of 1.1 s: `archlux.legalize` is resolved on
  first use (module `__getattr__`, like `light`, `bench` and `feasibility`), so the import
  of `numpy`, `scipy.sparse`, `shapely` and `ortools` moves to the first `legalize` call or
  attribute access. `from archlux import legalize` and `archlux.legalize` are unchanged.
  The cost of *using* the library is the same; only merely importing it got cheaper.
  Covered by `tests/unit/test_import_cost.py` (no solver dependency loaded, under 0.5 s).

### Remediation — PLAN.md phase 3, slice D: exports on the model (3.11)

#### Added
- `Plan.to_dxf(path)`, `Plan.to_ifc(path, validate=True)` and `Plan.to_svg(path, titre=,
  walls=)`, taking `str` or `Path`. `archlux.export.render_svg` exposes the SVG renderer.
  ADR-9: a third nominal exemption for `types` (local import of `archlux.export`).

#### Fixed
- `export.to_dxf(plan, "a.dxf")` failed on a `str` (`'str' object has no attribute
  'write_text'`): the path is now coerced, as `to_ifc` already did.

### Remediation — PLAN.md phase 3, slice C (started): `is_feasible` and import time (3.10, 3.13)

#### Fixed
- `is_feasible` no longer raises on a feasible program whose proposal has a gap (it retries
  with the rooms forced to tile the outline, and answers with a `Verdict`); a malformed
  program raises `InvalidInput`. `CertificatFaisabilite.scope` carries the restrictions
  beyond the relative order (load-bearing sides, tiling grid), as `Infaisable.scope` does.

#### Changed — import time
- `import archlux` takes about 1.1 s instead of 2.8 s: `networkx`, `scipy.stats`,
  `scipy.special` and `structlog` are imported on first use. The remaining cost is
  `numpy`, `scipy.sparse`, `shapely` and `ortools`, moved out of the import by slice E.
- The OR-Tools `MPSOLVER_ABNORMAL` lines on stderr came from non-finite inputs reaching the
  LP; those are now refused at the door. An LP-infeasible probe (70 m² asked of a 108 m²
  outline split 8 + 8 m wide) printed nothing; other cases were not searched.

### Remediation — PLAN.md phase 3, slice B: coherent types (3.2, 3.7)

#### Changed — construction now refuses incoherent values (`InvalidInput`)
- `PreuveGeometrique`: `valide=True` with an overlap, a gap, a failed area or structure
  check or any violation; a negative or NaN `deplacement_max` (`inf` stays allowed).
- `Ouverture`: `s` outside `[0, 1]` or `largeur_rel` outside `]0, 1]`.
- Not in `Piece`, `Mur` or `Orientation`: they are built in loops of the solver, and the
  proof must be able to *report* a malformed room (ADR-6). Their values are checked once,
  at the door of `legalize`.
- The JSON reader checks ranges on the raw data before building, so a file with several
  out-of-range values still reports all of them together.
- `Plan.trace` is excluded from equality and hash: `hash(plan)` no longer fails on a
  traced plan, and two plans differing only by their trace are equal.

### Remediation — PLAN.md phase 3, slice A: the door of `legalize` (3.1, 3.3, 3.4, 3.5)

#### Added
- `InvalidInput` (subclass of `ArchluxError` and `ValueError`, exported by `archlux`):
  a malformed argument, with the offending `field` and a hint. New leaf module
  `archlux.validation.validate_inputs`, called once at the top of `legalize`.
- `UserWarning` when a room type is absent from `referentiel.aires_min` (only when the
  regulation lists thresholds): a typo such as `"sejuor"` silently removed the minimum
  area of the room.

#### Changed — error types (behaviour change, refusals only)
- Before, a negative or `nan` width, duplicate room ids, a plan without room, a negative
  or `nan` budget all surfaced as `InvariantViole` (an internal-bug exception) or as an
  LP status; a string coordinate raised a bare `TypeError`. All raise `InvalidInput`.
  A plan with a gap and `pavage=False` now raises `GapNeedsTiling` (subclass of
  `UnsupportedInput`, exported with `GridNotRecoverable`): its message says to rerun with
  `pavage=True`; the gap is read from the proof's flags, never from its text. Valid
  inputs are unaffected. The two `ValueError`s about `calibration` are now `InvalidInput`
  (still catchable as `ValueError`).

### Remediation — PLAN.md phase 2 (in progress): milestone reviews

#### Fixed — IFC export (export behaviour change)
- **No IFC reader had ever opened an exported file**, and ifcopenshell's validator
  rejected every one: GlobalIds written as 22 hexadecimal characters instead of IFC
  base 64, `IfcOwnerHistory` with `ChangeAction = ADDED` and no date, `Curve2D`
  footprints made of 3D points, openings voiding no element. `validate=True` only meant
  that archlux's own pathology check passed.
- **Every wall was drawn shifted by its first end** (placed at `a`, axis from `a` to
  `b` in that frame).
- All fixed: GUIDs are IFC base 64 (still deterministic, labels prefixed by entity kind
  so a room and a wall of the same id no longer share one), `IfcRelVoidsElement` links
  each opening to its wall, and an opening on a wall absent from the plan is a new
  pathology, `ouverture_orpheline`. 90 of 90 repaired plans pass ifcopenshell (0 of 90
  before). `ifcopenshell` joins the `dev` extra; `tests/unit/test_ifc_validation.py`.
- After review: GlobalIds are salted with the plan geometry, so two different plans
  never share one (labels alone gave two flats with the same room ids the same
  `IfcSpace` ids); one plan still always gets the same ids.

#### Fixed — correlated seeds in active learning (AUDIT.md Q-M5)
- `active.Loop` drew selection and training seeds as `seed + cycle`: the campaign of
  seed 17 at cycle 1 replayed the campaign of seed 18 at cycle 0. It now uses named
  sub-seeds (`selection/k`, `fit/k`, `split`). Campaign results change.
- New leaf module `archlux.seeds` (`derive`), importable by every layer;
  `bench.graines.deriver` and `data.synthese` use it (same derivation, same values).

#### Added — published JSON schema and library functions from the experiments
- `archlux/io/plan-v1.schema.json` (JSON Schema 2020-12), shipped in the wheel, tested
  against the writer and the reader; documented on the schema page.
- `geom.polytope.decision_vector`, `data.synthese.two_room_vectors` and
  `two_room_plan`, `uq.fiabilite.measure_coverage` and `CoverageReport` (AUDIT.md M12:
  code the experiment scripts had to repeat). A coverage comes with its Clopper-Pearson
  interval (`ARCHITECTURE.md` §7: never a bare scalar); inputs are validated up front.
- `SubstitutInvalide.report`: the failed `RapportGradient`, so a failed check is
  recorded instead of parsed from the message.

#### Changed — milestone reviews (docs/revues, ADR 0002)
- Nine reports, criterion as written → replayed → result → decision. Milestone 4's
  gradient checkpoint is **reopened** (it passed at south only, where it was measured);
  milestone 5 gets a width criterion it does not meet (4 to 5 target standard
  deviations); "enough for a first paper" (J2) and "active loses" (J6) are withdrawn;
  milestone 9 is suspended until phase 6.1. `MILESTONE-2` to `-6.md` point to them.
- Acceptance criteria replayed as written: `test_milestone2_as_written.py`,
  `test_milestone3_as_written.py`, and the milestone 4 checkpoint as a strict `xfail`.
- Experiments rewritten in English, under 50 lines, byte-stable (no timing column):
  `j2_validity`, `j3_orientation`, `j4_gradient`, `j5_coverage`, `j6_active`,
  `j6_ifc`, `j7_msd_repair`, `j7_msd_summary`, `j7_msd_idempotence`; the scripts and
  results they replace are removed. `make resultats` (or `python scripts/resultats.py`)
  regenerates the synthetic figures and `resultats/SHA256SUMS`; `make check-resultats`
  compares; `make resultats-corpus MSD=... HD=...` runs the corpora.
  `tests/test_experiments.py` runs every script.
- The published 93.9 % of milestone 7 falls back on plain `legalize` after **any**
  refusal of `pavage=True`; the rule its text described gives 93.5 %.
- The published milestone 4 MAEs (0.0175 and 6.4007) do not reproduce with the shipped
  code: the same script gives 0.3272 and 41.8926 today.
- Experiments derive every seed by name (`archlux.seeds.derive`), no more `seed + k`.
- The JSON schema no longer requires non-empty ids, as the reader does not (phase 3.1).

### Remediation — PLAN.md phase 1 (exit gate passed on 2026-09-25)

#### Fixed — final review of phase 1 (certificate behaviour change)
- **A refusal proved more than it said.** The Farkas certificate is about the domain
  `legalize` built, with the load-bearing sides, the fused-room seams, the tiling grid
  and the budget, not about the relative order alone. `Infaisable.scope` names these
  restrictions; `Infaisable.relaxable` names the tiling grid or the budget when
  `legalize` without it finds a plan that passes the exact proof for the same order.
  The message is now in English: "infeasible for this relative order with ...".
  After review, an optimal LP without the restriction is no longer enough: it could
  keep a gap or miss an area (70 false "without budget" claims in 134 refusals).
- `certify.proof.verify_exactly` establishes nothing on a room with a non-finite or
  non-positive dimension (every predicate reported as not holding, with the room
  named), and `max_displacement` returns `inf` when a difference is NaN: `max()`
  dropped it and a budget was reported kept against an undefined reference.
- `geom.graphe.deduire_ordre(..., groups=)`: each member of a fused room keeps its own
  side of a load-bearing wall unless two of them take opposite sides; only then does
  the group share the side of its bounding box (`OrdreRelatif.shared_sides`). Forcing
  the bounding-box side on every member moved a foot that did not touch the wall. A U
  wrapped around the end of a partial wall may still be refused, never accepted across.
- Lint, mypy (1.x and 2.x) and the `Substitut` protocol test pass on Python 3.11 to
  3.13 (`__protocol_attrs__` only exists from 3.12).

#### Added — phase 1 exit gate
- `ARCHLUX_GATE_EXAMPLES=2000` runs the guarantee properties on 2000 Hypothesis
  examples (60 by default); the central property also draws a budget and checks it
  with the independent checker. At 2000 examples, Frank-Wolfe closed the 1 cm step of
  an L: allowed by the non-strict order of `overlap_constraints`, the property now
  says so, and the case is pinned by a unit test.

#### Changed — documentation in English (batch 1.8, track E batch E3)
- `ARCHITECTURE.md`, `CONTRIBUTING.md`, `AGENTS.md` and `CLAUDE.md` translated; they
  join the English allowlist of `tests/test_language.py`.

#### Fixed — load-bearing walls (batch 1.1, certificate behaviour change)
- **The structure predicate verified nothing.** It compared each load-bearing wall with
  itself; walls are not decision variables, so it was always true and a room could
  cross a load-bearing wall under a certificate reading "structure preserved: yes"
  (benchmark baseline: 35 false certificates out of 200 in performance mode).
  `certify.preuve` now rejects any room whose interior contains a stretch of a
  load-bearing wall, oblique walls included.
- **The solver now keeps every room on its side of every load-bearing wall**, treated
  as a fixed obstacle: `deduire_ordre(plan, structure=...)` reads the side from the
  proposed plan (`OrdreRelatif.porteurs`, `WallSide`) and `construire_polytope` adds one
  linear row per room and wall. Classic, tiling and performance modes all inherit it.
- A plan no longer has to repeat the structure in `plan.murs`; a declared wall of the
  same id must still match it.
- After review: the side kept is the half-plane the room penetrates **least** among
  those with room before the outline. A room overflowing the end of a partial wall by
  1 cm is moved 1 cm past the end, no longer sent across the wall (false refusals:
  7 of 200 in the partial-wall benchmark mode). Zero-length walls are ignored and
  nearly axis-aligned walls (noise below 1e-7 m) are accepted.
- `export.svg.rendre/comparer/planche` take `walls=` to draw the load-bearing structure
  even when the plan does not repeat it.

#### Fixed — minimum areas in performance mode (batch 1.2)
- **Frank-Wolfe went below minimum areas.** It mixed a valid start with vertices of an
  *outer* approximation of `w h >= a` (tangent cuts), so iterates could break the
  minimum; `legalize` then raised `InvariantViole` (benchmark: 167 of 200 in
  performance mode). It now works on an **inner** polyhedral approximation
  (`lmo.coupes.inner_area_constraints`: chords of the hyperbola around the start),
  included in `{w h >= a}`: every iterate keeps every minimum area. Nodes follow
  1.1^k, k = -24..24 (width 0.10 to 9.85 times the start), so each chord asks for at
  most (r-1)^2/(4r) = 0.23 % of extra area. Against a 235-node reference grid on the
  200 benchmark scenarios: median 0.9985 of the reference gain, >= 0.95 of it in 96 %
  of scenarios, +4 ms median.
- After review: nodes are no longer filtered by the variable bounds, which froze the
  width of a room whose height a contact had fixed (no gain in 7 of 120 scenarios); a
  start below a minimum area by more than the proof tolerance is refused.
- Frank-Wolfe no longer needs tangent cuts, which disabled the LP warm start.
- New performance budget with tight minimum areas (15 rooms: about 50 ms of 500), and a
  scaling test at 15, 50 and 100 rooms (all used to raise `InvariantViole`).
- Property test: every Frank-Wolfe iterate passes the independent checker.
- `api._coupes_surface_plan` removed: no longer needed. The tangent-cut path of
  `frank_wolfe` has no caller left and is documented as legacy.

#### Fixed — infeasibility is named, checked, and never inferred from tightened bounds (batch 1.5c)
- The Farkas auxiliary problem relaxes the equalities of `A_eq` too, and every equality
  carries a label (`Polytope.origines_eq`): 68 of 200 noisy benchmark plans were
  refused with "origines non renseignees"; they now name their conflicting constraints
  (tiling rows, frozen contacts). New `SolutionLP.certificat_farkas_eq`.
- `certify.farkas.verify_infeasibility` checks a certificate in exact rational
  arithmetic; `Infaisable.verified` and `CertificatFaisabilite.verified` report it, and
  the messages say "infeasible for this relative order". 88 of 89 benchmark
  certificates verify; a forged or feasible one never does.
- The area cutting loop no longer concludes "infeasible" on bounds it tightened itself
  (8 benchmark cases); it solves the original domain first.
- Without a certificate, `legalize` no longer lists every constraint as conflicting.

#### Changed — typed refusal for an unrecoverable tiling grid (batch 1.5c)
- `deduire_trame` raises `GridNotRecoverable` (an `UnsupportedInput`) instead of
  `InvariantViole` when the plan is too far from a tiling: an input limit, not an
  internal error. Experiments classified it by reading the message text; they now
  catch the type. The benchmark separates `refused_unsupported` from
  `refused_invariant`.

#### Changed — documentation aligned with the code (batch 1.8, track E batch E2)
- `README.md` rewritten in English. Its first paragraph states the regime: 93.9 % of
  corrupted MSD plans repaired (`resultats/j7_reparation.md`), about 20 % of
  HouseDiffusion outputs (`resultats/j8_generation.md`), figures measured before batch
  1.1 and to be measured again. Every example uses the current API and is executed by
  `tests/docs/test_examples.py`; every README line of the AUDIT.md §5.8 table is fixed.
  The Pareto front and non-Manhattan geometry move to the roadmap. A short,
  non-normative `README.fr.md` is added.
- `ARCHITECTURE.md` §1, 2, 3, 9, 11 match the code (one relative order, shipped
  surrogates, deterministic but not pure layers, what the budget tests measure, current
  tree); false statements of `Project_Architecture_Blueprint.md` are fixed.
- `light.SimulateurExact` is renamed `light.SplitFluxOracle`: a frozen closed-form
  split-flux oracle, neither a simulation nor ground truth. `SimulateurExact` and
  `ExactSimulator` remain as deprecated aliases (`DeprecationWarning`) until 1.0.0.

#### Fixed — L-shaped rooms keep their shape and their area (batch 1.7)
- Fusion equalities used to glue only the shared edge line, so the sub-rectangles of
  an L could slide along it and the L could become a T, a Z, or split.
  `geom.rectilineaire.etendre_fusions` now also keeps, on the orthogonal axis, the
  order of the sub-rectangle ends (aligned ends stay aligned) and a minimum
  shared-edge length (`overlap_constraints`; `legalize` passes
  `referentiel.largeur_min`).
- The minimum area of a fused room applies to the union of its sub-rectangles, not to
  each of them: `certify.proof.verify_exactly(..., fusions=)` checks it on the
  edge-connected union, and the solver gives each sub-rectangle a proportional share of
  the room minimum (`minimum_area_shares`, new `minima=` keyword of
  `lmo.coupes.resoudre_avec_surfaces`, `surfaces_violees` and
  `inner_area_constraints`). The shares are conservative: a false refusal is possible,
  a false certificate is not. New keyword-only parameters, defaults unchanged.

#### Fixed — review of batches 1.7 and 1.8
- **A load-bearing wall on the seam of an L room was certified.** The proof and the
  checker tested each sub-rectangle alone, and the order gave each sub-rectangle its own
  side of every wall, so the solver could widen the bar of an L until its seam sat on
  the wall: the kitchen was cut in two under a valid certificate. The proof tests a
  fused room as one interior (union of its parts), the checker tests the seams, and
  `geom.graphe.deduire_ordre(..., groups=)` gives all the parts of a fused room the side
  of their bounding box (exact for the union; it may refuse an L wrapped around the end
  of a partial wall, never accept a crossing).
- The proof checks every recorded seam of a fused room with the solver's minimum
  contact (`largeur_min`), as the checker does; connectivity alone accepted a neck of
  1e-7 m or a foot that slid to another edge.
- `minimum_area_shares` adds the proof tolerance to every share (k parts could miss the
  minimum by k * 1e-9) and raises `UnsupportedInput` for a fused room without area.
- `from archlux.light import SimulateurExact` (and `certify.verifier_exactement`) warns
  once, not twice; the tiling refusal names the chained grouping of outline edges.

#### Fixed — tiling mode anchors its grid on the outline
- The outer grid lines are anchored exactly on the outline. They used to take the mean
  of the room edges grouped with them, so a few millimetres of noise left an uncovered
  strip that the proof rejected as `InvariantViole`. The relative order and the
  load-bearing sides are now read from the plan snapped onto its recovered grid (new
  `geom.pavage.snap_to_grid`), so they can no longer contradict the tiling equalities.
  Guarantee benchmark: `classic_noisy` 1 → 118 ok (the other 82 are
  `GridNotRecoverable`), `partial_one_fault` 198 → 200 ok, no false certificate.
- `deduire_trame` raises `UnsupportedInput` instead of `InvariantViole` for an empty
  plan, an empty or invalid outline, a degenerate grid, a room flat after grouping,
  and outline edges closer than the grouping tolerance.

#### Changed — a probabilistic bound states its regime (batch 1.6, breaking)
- `BornePerformance.regime` is mandatory: `"exchangeable"` (plan exchangeable with the
  calibration set, coverage guaranteed) or `"selected"` (plan chosen by the optimizer,
  coverage **not** guaranteed: winner's curse). New property `coverage_guaranteed`.
  An inverted interval (`borne_inf > borne_sup`) is refused.
- The report no longer prints `[PREDICTION — couverture 90 %]` for a selected plan;
  it prints `couverture NON garantie` and asks for a re-evaluation by the oracle.
- `legalize(..., objective=..., calibration=...)` fills `Certificat.performance`, in
  the selected regime, centred on the surrogate's prediction `mu` (not on the
  pessimistic objective `mu - q sigma`, which would subtract the margin twice; new
  `light.protocole.WrapsSurrogate` and `point_prediction`). Without `calibration`,
  `performance` stays `None`; a calibration without objective or of another
  indicator raises `ValueError`.
- `borner`, `construire_borne` and `CalibrateurConforme.borne` take `incertitude`
  (no more default of 1.0, wrong for normalized scores) and `regime` as mandatory
  keywords.
- `Calibration.empreinte_jeu` hashes the calibration **data set** (predictions,
  truths, uncertainties) with `uq.conforme.dataset_fingerprint`, not the scores: two
  data sets can share their scores.
- JSON: `performance.regime` is written, and a bound without it is refused on read;
  `couverture` is documented as nominal.
- Review of the batch: an ASE bound was published negative (`ASE <= -28,92`), because
  surrogates return ASE negated for maximization; `point_prediction` now gives it back
  positive and removes every wrapping layer. The calibration is checked before any
  solving (`certify.borne.check_calibration`); a surrogate without a positive `σ̂` at
  the returned plan gives `performance=None` instead of losing the proved plan.
  `ajuster` refuses negative or non-finite uncertainties and fingerprints the raw
  data. The `experiences/` scripts pass `regime="exchangeable"` (held-out plans).

#### Fixed — review of batch 1.5
- **Tight programs were refused.** The area margin of batch 1.5a (targets 1e-6 m²
  above the minimum) left no room when the minimum areas fill the outline exactly;
  `legalize` raised `InvariantViole` on 37 of 40 such programs. The cutting loop now
  retries at the exact minimum when the margin fails: 0 of 40 refused at any slack.
- `verify_exactly`: `jours` no longer contradicts the violations when rooms overlap.
- `verify_infeasibility` answers "not verified" on a NaN or infinite multiplier
  instead of raising `ValueError`.
- `certify.proof` imports its tolerances from `archlux.tolerances`.

#### Changed — the tiling is proved in exact rational arithmetic (batch 1.5b)
- For an axis-aligned rectangular outline, `verify_exactly` decides overlaps and gaps
  with `certify.proof.rational_tiling`: edges closer than `SNAP_M` (1e-7 m) are
  identified (the only tolerance, on lengths), then inclusion, pairwise disjoint
  interiors and the area sum are checked with `Fraction`, no tolerance. Theorem and
  proof in `docs/formules/preuve-exacte.md`. Other outlines keep the GEOS checks.
- The raw plan is then bounded as well (raw pairwise overlaps <= `OVERLAP_M2`, raw
  overhang and a Bonferroni bound of the raw uncovered area <= `GAP_M2`), so that edge
  identification cannot accept a plan the GEOS path or the checker rejects. Without
  this bound, batch 1.5b accepted a gap of 9e-6 m² along a 100 m edge and a 3e-8 m²
  sliver overlap (fixed in the review of batch 1.5). Certification of 15 rooms 0.8 ms
  instead of 1.5 ms.

#### Changed — `certify.preuve` migrated to English (track E, batch E10; same verdicts, messages now in English)
- New module `archlux.certify.proof`: `verify_exactly`, `GAP_TOLERANCE_M2`,
  `max_displacement`; violation messages in English (`overlap a|b: ...`,
  `gap: uncovered area ...`, `area r: ... < ...`, four decimals instead of two, which
  had displayed a real deficit as "10,35 m² < 10,35 m²").
- `archlux.certify.preuve.verifier_exactement`, `preuve.TOLERANCE_JOUR_M2` and
  `archlux.certify.verifier_exactement` remain as deprecated aliases until 1.0.0.
- `PreuveGeometrique` field names are unchanged (JSON schema, batch E5). Proof
  verdicts and legalized plans are identical (SHA-256 over 360 checks and 120 runs).

#### Fixed — the solver is never looser than the proof (batch 1.5a)
- The cutting-plane loop accepted a room 1e-6 m² short of its minimum area, the proof
  only 1e-9 m²: plans were refused with messages such as "surface r4 : 10,35 m² <
  10,35 m²" (3 of the 1,600 benchmark cases). The loop now accepts with the proof
  tolerance and, for a room found in deficit, aims `AREA_TARGET_MARGIN_M2` (1e-6 m²)
  above the minimum, beyond the LP noise. Rooms that meet their minimum are never
  pushed: outer tangents stay at the exact minimum.
- `tolerances.AREA_CUTS_M2` replaced by `AREA_TARGET_MARGIN_M2`; the strict xfail
  "the solver is never looser than the proof" now passes as a plain test.

#### Fixed — Frank-Wolfe reports what it achieved (batch 1.4)
- The gap started at 0, so a run whose first LP failed read as "optimum reached"; it
  now starts at infinity.
- On a run ending at `max_iter`, the gap described the previous point; it is now
  computed at the returned point (one extra LP, which also gives the duals).
- New `FrankWolfeResult.status` and `Trace.status`: `converged`, `line_search_failed`,
  `lp_not_optimal` or `max_iter`. `iterations` counts iterations, not the initial entry.
- The gap is documented as a stationarity measure: no shipped surrogate is concave, so
  it never bounds the distance to the optimum.
- **The displacement budget was spent twice**: the Frank-Wolfe box was centred on the
  L1 point, so the total move from the proposal reached up to twice the budget
  (measured: 0.55 m for 0.3 m). It is now centred on the proposed plan
  (`solve.frank_wolfe.restrict_to_budget`), and `verifier_exactement(..., budget=)`
  makes a plan moved beyond it invalid; `legalize` passes the budget to the proof.
- The certification budget of ARCHITECTURE.md §9 (5 ms, 15 rooms) is measured at last:
  about 1.5 ms.
- After review: the Frank-Wolfe budget box always contains the classic result, which a
  saturated budget meets only up to the LP tolerance (it raised `InvariantViole` in 15
  of 40 probes); a real budget conflict raises `Infaisable` naming the variable. The gap
  is `inf` whenever it is unknown (an LP failing after a step, or at the returned
  point); `Trace.final_gap` exposes the gap at the returned point; duals are computed
  once. `Iteration.valeur`, `pas`, `temps_lp_ms`, `n_coupes` are deprecated aliases too.
- **Breaking for direct construction only**: `Trace` now requires `status` and
  `final_gap` (it is built by `frank_wolfe`, not by users).

#### Changed — `solve` migrated to English (track E, batch E9; no behaviour change)
- `ResultatFW` -> `FrankWolfeResult` (`valeur` -> `value`, `duaux` -> `duals`);
  `frank_wolfe(poly, surrogate, orientation, start, ..., cuts=, rooms=, glazing=)`;
  `Iteration` fields `value`, `step`, `lp_ms`, `n_cuts`; `Trace.iterates`, `gaps`,
  `values`, `total_lp_ms`. The French names of `Trace` (reachable through
  `Plan.trace`) remain as deprecated aliases until 1.0.0. Outputs are byte-for-byte
  identical (SHA-256 over 200 Frank-Wolfe runs and all their iterates).

#### Fixed — `Daylight` objective (batch 1.3)
- `legalize(objective=Daylight(...))` raised `TypeError`: `Daylight` did not accept the
  `baies` keyword of the `Substitut` protocol, which Frank-Wolfe always passes, yet
  `isinstance(..., Substitut)` was true (it only checks method names). `Daylight` now
  accepts and forwards `baies` in `evaluer`, `gradient`, `incertitude`, `__call__` and
  the finite-difference gradient of the uncertainty; it is also frozen, like every
  type. A conformance test compares the signatures of all five surrogates with the
  protocol. Benchmark: 200 crashes out of 200 before.

#### Added
- `export.svg` draws walls: load-bearing walls thick and dark (class
  `wall-load-bearing`), other walls thin and grey (class `wall`). A room crossing a
  load-bearing wall is now visible. First tests of `export.svg` (it had none).
- `UnsupportedInput` (`ArchluxError`): raised for an oblique load-bearing wall instead of
  ignoring it.
- `tests/test_hygiene.py`: no invisible control character in tracked text files.
- `benchmarks/guarantees/`: a before/after benchmark of the exact guarantees, measured by
  the independent checker of `tests/checkers.py` on 200 deterministic scenarios and five
  modes; it counts false certificates (plans certified valid that break a guarantee).

### Remediation — PLAN.md phase 0 (new entries are written in English)

#### Changed
- **Development version `0.10.0.dev0`.** `1.0.0` (never published) is withdrawn: it
  promised a stable, usable API while the README quick start did not run and the
  performance mode failed on realistic plans (see `AUDIT.md`). `0.9.0` is not reused
  either, since it already names an earlier state. 1.0.0 will be tagged at the end of
  PLAN.md phase 5.
- **Single source of truth for the version**: `src/archlux/_version.py`, read by hatch
  (`dynamic = ["version"]`). The certificate header used installed metadata and could
  print a stale `0.0.0`; it now prints the source version.
- **English-first project** (ADR 0001, `docs/glossary.md`): new code is English; the
  existing French code is migrated batch by batch.

#### Fixed
- `export.ifc` and `bench.manifeste` imported the root package, which loaded the whole
  legalization chain; they now import `archlux._version`.
- `tests/test_dependances.py` ignored `from archlux import ...`; it now rejects it,
  rejects relative imports, and checks that the leaf modules import nothing.
- Seven `docs/donnees/` pages were never versioned (an unanchored ignore pattern);
  `mkdocs build --strict` failed on a clean checkout.
- Budget tests crashed under `--benchmark-disable`; an unmeasured budget is now skipped.

#### Added
- `LICENSE` (Apache-2.0), `.gitattributes` (LF), git history, pre-commit hooks.
- CI: `ruff format --check`, pre-commit hooks, coverage ratchet (84 %); ruff and
  hypothesis versions pinned.
- `archlux/tolerances.py`: registry of the numerical tolerances in use (usages are
  migrated in phase 1.5).
- Tests that execute the user-facing documentation examples (6 pages broken today,
  recorded as strict xfails).
- Property tests under realistic contexts (load-bearing wall, tight minimum areas)
  with an independent checker. They reproduce three audit defects, recorded as strict
  xfails: performance mode goes below minimum areas, crosses load-bearing walls
  unnoticed, and rejects `Daylight`.
- A strict xfail pinning an inconsistency found while building the registry: the
  cutting-plane loop tolerates 1e-6 m² under a minimum area, the proof only 1e-9 m².
- Language check on files already migrated to English.

### RUPTURE — le protocole `Substitut` recoit les baies

`evaluer`, `gradient` et `incertitude` prennent un argument **nomme et optionnel**
`baies: Baies | None = None`. Toute implementation tierce doit l'accepter : c'est une
rupture de contrat public, donc une **version 2.0** au sens de la regle du projet.

**Pourquoi.** Le vecteur de decision ne porte que `(x, y, w, h)` par piece. Il ne dit
rien des ouvertures — or ce sont elles qui determinent l'eclairement. Mesure sur 369
appartements suisses, cible = irradiance simulee par lancer de rayons, decoupage par
site : analytique `R2 = -0,000`, perceptron `R2 = -0,557`. Au niveau, ou sous, la
simple moyenne. Ce n'etait pas un defaut de capacite mais **un defaut d'entree** : le
tokeniseur produisait deja des jetons de baie que le protocole ne laissait pas passer.

`Baies` est volontairement pauvre — murs et ouvertures relatives — et **invariante
pendant l'optimisation** : seules les cloisons bougent sous Frank-Wolfe, les baies
suivent sans synchronisation. Elle se construit une fois et se transmet inchangee.

`None` signifie « information absente » : l'implementation se rabat sur son hypothese
par defaut, exactement comme avant. `SubstitutAnalytique` et `SimulateurExact`
l'ignorent d'ailleurs — leur WWR est une constante du modele.

### Ajoute

- `light.protocole.Baies`.
- `light.jetons.vecteur_vers_jetons(x, orientation, baies)` : les jetons de baie,
  jusqu'ici produits par `plan_vers_jetons` seulement, sont desormais accessibles
  depuis un vecteur de decision.
- `light.base.descripteurs(x, orientation, baies)` : six descripteurs de fenestration
  en fin de vecteur (82 -> 88 composantes). Les 82 premieres sont **inchangees**, et
  les six dernieres sont nulles sans baies : un modele entraine sans reste lisible.
- `SubstitutDense.ajuster(..., baies=...)`.
- `api.legalize` construit les `Baies` du plan corrige et les transmet a Frank-Wolfe.
- `data.chargeurs` : `charger_etiquettes_sd`, `etiqueter`, `decouper_par_site`,
  `COLONNE_SOLEIL_DEFAUT`. `AppartementMSD` porte `site_id` et `aires_sources`.
- `experiences/j7_sd_etiquettes.py`, `resultats/j7_sd_etiquettes.md`.

### Corrige

- `light.base.SubstitutDense` apprenait le residu a l'analytique **en supposant les
  deux a la meme echelle**. Vrai contre `SimulateurExact`, construit sur la meme base ;
  faux contre une simulation reelle, ou l'analytique rend ~300 en unites arbitraires
  quand la cible vaut ~0,7. Le reseau depensait sa capacite a annuler une constante.
  Recalage affine `y ~= a.f(x) + b` ajuste par moindres carres sur le train, persiste
  dans le `npz`. Des poids anterieurs se relisent avec `a = 1, b = 0`, comportement
  inchange. **MAE sur donnees reelles : 1810 -> 0,367.**

### Mesure — substitut contre simulations reelles

Cible `sun_201803211200_mean` (Swiss Dwellings v3.0.0, CC BY 4.0), moyenne ponderee
par surface. Decoupage **par site** — 133 / 44 / 45 sites disjoints, jamais par
appartement : deux logements d'un meme site partagent masque urbain et orientation.

| modele | MAE | MAE relative | R2 |
|---|--:|--:|--:|
| constante (moyenne du train) | 0,267 | 39,5 % | 0,000 |
| analytique recale | 0,268 | 39,6 % | **-0,000** |
| perceptron sans baies | 0,353 | 52,2 % | -0,557 |
| perceptron **avec baies** | 0,307 | 45,4 % | **-0,220** |

Conforme a alpha = 0,10 : **couverture mesuree 90,2 %** pour 90 % vises, largeur
moyenne 1,534, n_calibration 426.

Trois lectures. **L'analytique n'a aucun pouvoir predictif** : la pente du recalage
tombe a -0,0000, les moindres carres l'ecrasent en constante. La regle de profondeur
CIBSE et la table a huit secteurs n'expliquent rien de l'irradiance simulee.

**Les baies comblent 60 % de l'ecart** (R2 -0,557 -> -0,220) sans qu'aucun autre
parametre change : meme modele, memes hyperparametres, meme graine. L'entree etait
bien le goulot. Elle ne suffit pas : le masque urbain, que Swiss Dwellings simule et
qu'`archlux` ne represente pas, reste absent.

**La garantie conforme tient** — 90,2 % pour 90 % — et le dit honnetement par la
largeur : 1,534 pour une cible de moyenne 0,677, soit un intervalle 2,3 fois la
valeur. Quand le substitut ne sait rien, la borne le declare au lieu de pretendre.
C'est la validation empirique de la these du projet, obtenue par la negative.

### Limites

Une colonne sur 126, 2 000 appartements parcourus, une irradiance a instant fixe qui
**n'est pas un sDA**. Le champ `indicateur` doit se lire comme le nom de la cible
apprise, jamais comme la metrique IES.


### Ajoute — contrainte de pavage exact (jalon 7)

`geom.pavage` et `legalize(..., pavage=True)`. Defaut `False` : contrat 1.x inchange.

**Le probleme.** Les separations du polytope sont des inegalites : elles interdisent
le chevauchement, jamais le trou. Un plan troue est deja le point le plus proche de
lui-meme, donc l'optimum L1 le laisse tel quel et `certify.preuve` le rejette.
Mesure : 68,1 % de chevauchements repares contre **9,8 % de jours**.

**Le resultat.** Dans une dissection rectangulaire, tout bord est porte par une
ligne de trame ; la piece i s'ecrit `[v_l, v_r] x [h_b, h_t]` et couvre les cellules
`l <= a < r`, `b <= B < t`. **La condition de pavage ne porte que sur les indices**,
jamais sur les coordonnees : si ces familles partitionnent les cellules interieures
au contour, alors toute suite croissante de lignes donne un pavage exact. Il suffit
donc d'imposer « ces bords partagent une ligne » — des egalites affines dans les
variables existantes. Un jour cesse d'etre representable.

Deux proprietes en decoulent : le systeme **reste faisable** (les positions de trame
de reference sont toujours admissibles ; aucun LP infaisable observe), et la garantie
est structurelle, pas numerique.

**Recuperer la trame d'un plan fautif** se fait par le **support** d'une ligne — le
nombre de bords qu'elle porte — et non par une tolerance metrique, qui echoue dans
les deux sens (3,8 % de reparation). Une ligne orpheline est resorbee dans sa voisine,
sauf si cela ecrase une piece. Aucun seuil en metres : un jour de 2 m se rattrape
comme un jour de 5 cm, une cloison de 40 cm survit.

Fiche : `docs/formules/pavage.md`. Sources : Otten (1982), Lengauer (1990) ch. 10.

### Mesure — 3 597 corruptions de 300 appartements MSD reels

| Faute | `legalize` | `pavage=True` | repli |
|---|--:|--:|--:|
| jour | 10,0 % | 97,6 % | **98,0 %** |
| sous-dimension | 4,8 % | 96,0 % | **96,3 %** |
| chevauchement | 68,2 % | 90,3 % | **91,2 %** |
| decalage | 60,8 % | 88,1 % | **90,0 %** |
| **toutes** | **35,9 %** | 93,0 % | **93,9 %** [93,2 - 94,5] |

0,0 % de plans valides avant correction. Temps median 6,5 ms, sous le budget §9.
Par amplitude : 96,8 % a 10 cm, 96,9 % a 25 cm, 93,2 % a 50 cm, 88,6 % a 1 m.

**Reparation bornee de la partition.** Apres resorption des lignes orphelines, il
subsiste des defauts locaux — une cellule vide ou doublement couverte, cas dominant
sur MSD. On agrandit ou retrecit une piece **d'un cran**, ce qui la laisse
rectangulaire par construction, et seulement si les cellules concernees sont toutes
manquantes ou toutes en exces. Le budget (defaut 4) distingue la reparation de la
reconstruction ; il sature a 4 (recuperation de trame : 77,8 % a budget 0, 98,5 % a
2, 99,2 % a 4 et 8).

Consequence semantique documentee : fermer un jour, c'est agrandir quelqu'un. La
reparation peut **absorber une piece manquante dans sa voisine**, et le plan sort
avec une piece de moins que prevu. `budget_reparation=0` verifie sans retoucher.

### Corrige

- `geom.pavage._consolider` : la ligne voisine la plus proche pouvant se trouver de
  l'autre cote du bord deplace, tester l'egalite des indices ne suffisait pas. Une
  piece pouvait ressortir avec ses bords **inverses** (`gauche > droite`) et passer
  silencieusement en LP. Ordre strict exige, plus un filet final sur les incidences.
  Trouve par le test de propriete « toute trame rendue est une partition valide ».

### Ajoute — modele de corruption

`data.corruption.corrompre` : quatre familles de fautes (`deplacer`, `elargir`,
`retrecir`, `aplatir`), graine obligatoire, amplitude **reellement appliquee**
rapportee comme verite terrain. Ces perturbations ne modelisent aucun generateur
particulier : elles reproduisent les familles de fautes de la litterature sans en
calibrer les frequences, et doivent etre completees par un generateur public.


### Ajoute — corpus reel (jalon 7)

- `data.chargeurs.charger_msd` : CSV MSD (WKT) -> `Plan` + `Contexte`. Redressement
  par direction dominante, calage sur les axes, recollage sur trame commune,
  decomposition rectilineaire, baies projetees en relatif. Retention mesuree
  32,1 % sur MSD, mediane 10 sous-rectangles.
- `orient.circulaire.direction_dominante` : moyenne directionnelle d'ordre *p*
  pour donnees axiales (Mardia & Jupp §2.3.3), ponderee par les longueurs. Une
  moyenne circulaire ordinaire annule les axes a 90 deg les uns des autres.
- `geom.rectilineaire.MAX_RECTANGLES` et `decomposer(..., max_rectangles=)` :
  le plafond de 4 sous-rectangles devient un parametre. Defaut inchange.
- `ARCHITECTURE.md` §5 : `data` peut lire `geom` et `orient` (chargeurs de corpus
  uniquement), jamais `lmo`, `solve` ni `light`. Aucun cycle : `geom` et `orient`
  n'importent pas `data`.
- `uq.conforme.n_minimal_conforme(alpha)` : plus petite taille de calibration
  admissible, `n >= ceil(1/alpha) - 1`, soit 9 a 90 % et 19 a 95 %. Remplace un
  seuil `>= 8` code en dur qui echouait systematiquement au premier cycle.
- `active.boucle.Loop.run(..., calibration=)` : jeu de calibration **independant**.
  A defaut, `part_calibration` reserve une fraction des points acquis, qui n'entre
  jamais dans `ajuster`. `RapportActif.calibration_independante` dit si la
  couverture est publiable. Corrige l'anti-pattern §10 commis par le module.
- `experiences/j7_msd_idempotence.py` et `resultats/j7_msd_idempotence.md`.

### Corrige

- `geom.rectilineaire._coupe_verticale` : GEOS rend l'intersection en morceaux
  colineaires (arete de bord et corde interieure, jointives au sommet reflexe).
  Le premier morceau etait retenu, c'est-a-dire une arete du polygone, qui ne
  separe rien. **1 219 pieces MSD sur 4 456** echouaient sur ce seul defaut.
  Les morceaux touchant le pivot sont desormais reunis.
- `geom.rectilineaire._decouper` : repli sur coupe horizontale quand aucune
  verticale ne separe (U couche, T couche, Z). La convention verticale garde la
  priorite, donc les decompositions anterieures sont inchangees.
  **Taux de decomposition sur MSD : 44,8 % -> 80,8 %.**

### Mesure

Sur 400 appartements MSD reels (mediane 10 sous-rectangles, max 15) :
398/400 valides avant `legalize`, **400/400 apres**, 0 echec, deplacement maximal
median **0,000000 m** (idempotence), 7,1 ms median et 10,7 ms au p90 — sous le
budget de 20 ms du §9, sur geometrie reelle.

### Piege documente

`Referentiel.largeur_min` vaut 1,80 m par defaut et s'applique a **chaque
sous-rectangle**, y compris aux bandes issues d'une decomposition en L — or un
sous-rectangle est un artefact de decoupe, pas une piece. Herite en silence sur un
corpus sans reglementation, il fait sortir le plan de son propre polytope :
`legalize` elargit les bandes, le pavage se dechire, `certify.preuve` rejette pour
« jour ». Mesure : **87 % d'echecs avec le defaut, 0 % avec `largeur_min=0`**.
`charger_msd` neutralise donc le seuil par defaut.


Passe de revue et refactor (agents `review-and-refactor`), documentation technique et
mathematique mise a jour.

### Corrige (comportement du certificat)

> **Ces trois points changent ce que `certify` affirme.** Au sens de la regle du
> projet, la publication qui les embarque est une **version majeure** : un certificat
> emis avant ces correctifs n'est pas comparable a un certificat emis apres.

- `certify.preuve` : `_jours` comparait `aire(union) == aire(contour)`. L'egalite des
  aires est **necessaire mais pas suffisante** : un trou interieur de *a* m2 compense
  par une piece de *a* m2 situee entierement hors du contour laissait les aires egales
  et le test de chevauchement vide. Une piece flottant a 8 m du batiment etait
  certifiee `[EXACT]` valide. Les deux differences ensemblistes sont desormais testees
  separement (`aire non couverte`, `debord hors contour`).
- `uq.conforme` : `borner` et `CalibrateurConforme.borne` acceptaient une incertitude
  nulle ou negative, publiant un intervalle de largeur nulle assorti d'une couverture
  de 90 %, ou un intervalle inverse (`borne_inf > borne_sup`). Refuse desormais par
  `InvariantViole`.
- `lmo.solveur` : `_certificat_farkas` lisait les duaux du probleme auxiliaire sans
  verifier son statut. Quand l'infaisabilite venait des bornes ou de `A_eq`, un vecteur
  sans signification etait presente comme certificat de Farkas. Rend un vecteur nul.

### Corrige (autres)

- `geom.polytope` : une enveloppe plus etroite que `referentiel.largeur_min` produisait
  des bornes inversees, donc `InvariantViole` (« bogue interne ») au lieu d'`Infaisable`
  avec ses origines lisibles.
- `export.wilson` : en `p = 0` / `p = 1`, l'arrondi flottant sortait des bornes hors de
  `[0, taux]` (24 cas pour n <= 60). Extremites posees exactement.
- `export.ifc` : trois ecarts au schema IFC4, dont `IfcSpace` place dans
  `IfcRelContainedInSpatialStructure` (interdit) et des murs rattaches a aucune
  structure spatiale. Le champ `moteur` n'annonce plus `ifcopenshell` quand aucune ligne
  n'en provient (nouveau champ `ifcopenshell_disponible`).
- `light.base` : `sauver()` calculait l'empreinte d'un chemin sans suffixe alors que
  `numpy.savez` ecrit `.npz` — `FileNotFoundError` sur le chemin de reproductibilite.
  `assert` d'invariant remplace par `InvariantViole` (§7).
- `io.json_io`, `data.synthese`, `data.dedup`, `bench.protocole` : quatre exceptions
  nues (`UnicodeDecodeError`, `IndexError`, `ValueError`) et une mesure fabriquee sur
  corpus vide, toutes hors du contrat d'erreurs §7.
- `bench.rapport` : 199 replications bootstrap ecrasaient le defaut de 9 999 ; l'erreur
  Monte-Carlo dominait la largeur publiee. Porte a 2 000.
- `active.boucle.Loop` : `seed` avait une valeur par defaut, en violation du §7.

### Ajoute

- `light.analytique.facteur_secteur` et `light.analytique.FACTEURS_SECTEUR` : la table
  a 8 secteurs devient une fonction de module (elle etait atteinte depuis `simulateur`
  en construisant une instance jetable pour appeler une methode privee). L'alias
  `SubstitutAnalytique.FACTEURS_SECTEUR` est conserve : contrat public inchange.
- `bench.stats.holm` : correction de Holm-Bonferroni (FWER, sans hypothese
  d'independance). **Pas encore branchee** dans le pipeline de table.
- `uq.fiabilite.diagramme_fiabilite(..., scores_calibration=)` : permet de mesurer la
  couverture hors echantillon. Le mode par defaut est une tautologie et ne doit fonder
  aucune figure publiee.
- `data.synthese.TAILLE_MAX` : plafond explicite du generateur (90 coupes).
- `docs/donnees/verite-terrain.md` : d'ou viennent reellement les etiquettes
  d'eclairement, et les trois sources possibles.

### Documente (sans changement de comportement)

- `Certificat.duaux` est **structurellement vide en mode performantiel** :
  `figer_contacts` deplace les lignes saturees vers `A_eq`, dont les duaux ne sont
  jamais collectes. Le diagnostic dual ne fonctionne qu'en legalisation classique.
- `active.boucle.Loop` calibre le conforme **sur les points d'entrainement** : c'est
  l'anti-pattern `ARCHITECTURE.md` §10. La largeur d'intervalle rendue n'est pas
  publiable.
- `light.analytique.FACTEURS_SECTEUR` ne vient d'aucune source citee : CIBSE LG10 donne
  une profondeur limite independante de l'azimut, et le split-flux BRE travaille sous
  ciel couvert CIE, donc sans azimut. A presenter comme un a priori de modelisation.
- `light.simulateur` : `wwr` n'est pas un window-to-wall ratio (hauteur de bandeau
  comptee deux fois) ; `ECHELLE_DF = 100` annule exactement la division par 100 et
  n'est pas un reglage libre ; `theta = 65` est une hypothese d'obstruction non mesuree.
- `light.base.gradient` : differences finies, **18,4 ms par gradient a 15 pieces**, soit
  ~920 ms pour 50 iterations Frank-Wolfe contre un budget §9 de 500 ms. Le benchmark de
  CI passe parce qu'il cable `SubstitutAnalytique`, jamais le substitut appris.
- `light.appris._charger_torch` leve **inconditionnellement** : le transformeur du
  jalon 4 n'existe pas.
- `uq.gestion` : le verrou de calibration est une discipline avec somme de controle,
  pas une barriere cryptographique. Cinq contournements d'une ligne sont documentes.
- `lmo.coupes._resserrer_bornes` restreint le domaine : le statut `"optimal"` porte sur
  un domaine plus petit que le vrai.
- `data.decoupage` : l'empreinte couvre les identifiants et leur ordre, jamais la
  geometrie des plans.
- `feasibility` : le certificat de Farkas n'est jamais verifie contre les conditions du
  lemme ; c'est un certificat par confiance envers le solveur.

## [1.0.0] — 2026-09-09 — WITHDRAWN, never published

> Withdrawn on 2026-09-23: the README quick start did not run and several announced
> guarantees did not hold (AUDIT.md). The number is not reused; development continues
> as `0.10.0.dev0` and 1.0.0 will be a new release.

Gel de l'API publique (jalon 6, étape 7). Toute rupture devient `2.0`.

### Ajoute
- `archlux.feasibility.is_feasible` / `Verdict` / `CertificatFaisabilite`
  (Farkas exact, sans lumière).
- Exports paresseux : `ax.light`, `ax.bench`, `ax.feasibility`
  (`import archlux` ne charge toujours pas `torch`).
- `light` : `SubstitutAnalytique`, `SimulateurExact` (`ExactSimulator`),
  `Daylight`, `Substitut` — sans importer `appris`.
- `test_api_publique_stable` ; `CITATION.cff` ; `docs/publication-1.0.md`.

### Garanties
- Géométrie : exacte (inchangé).
- Performance : probabiliste / `NON EVALUABLE` (inchangé).

### Non inclus (processus)
- Tag Git / DOI Zenodo, upload PyPI, preuve d'usage tiers, historique ≥ 6 mois.

## [0.9.0] — 2026-09-09

Jalon 6, étape 5 : documentation complète (galerie, tutoriels, contribution).

### Ajoute
- `CONTRIBUTING.md` : dépendances `ARCHITECTURE.md`, gouvernance, revue, semver.
- `docs/tutoriels/premiers-pas.md` (remplace le stub).
- `docs/limites.md` enrichi (échangeabilité, NON EVALUABLE, hors périmètre auto).

### Change
- Tutoriel performantiel et galerie 01 : enveloppe corpus 12×9 m explicite.
- Checklist `MILESTONE-6.md` §6 cochée.

## [0.8.0] — 2026-09-09

Jalon 6, étape 4 : banc d'essai reproductible (manifeste, bruts, stats).

### Ajoute
- `types.ModeleTrace` (poids, calibration_n, alpha) sur `Manifeste.modele`.
- `bench.run` : manifeste puis `resultats_bruts.csv`, puis `Resultat`.
- `bench.report` : stratification par orientation imposée (8 secteurs).
- `bench.stats` : bootstrap apparié, TOST, analyse de puissance.
- `compare(..., evaluate_by=)` sans défaut (TypeError si omis).
- Tests `test_manifeste_complet`, `test_evaluate_by_obligatoire`.

### Change
- Sérialisation JSON du champ `modele` (rétrocompatible si absent).

## [0.7.0] — 2026-09-09

Jalon 6, étape 3 : export IFC / DXF et taux de survie (Wilson).

### Ajoute
- `export.pathologie` : taxonomie bloquante avant écriture.
- `export.to_ifc` : SPF IFC4 minimal (CI) ; extra `bim` optionnel.
- `export.to_dxf` : LWPOLYLINE ASCII sans dépendance.
- `export.survival_rate` / `intervalle_wilson`.
- Tests Hypothesis `plans_valides` → export valide ; Wilson dans `[0, 1]`.
- `docs/formules/export-bim.md`, `experiences/j6_survie_ifc.py`.

### Change
- `ARCHITECTURE.md` / `tests/test_dependances.py` : couche `export`
  ← `types`, `erreurs`.

## [0.6.0] — 2026-09-09

Jalon 6, étape 2 : apprentissage actif. Priorité = incertitude × densité
optimiseur (produit). Recalibrage conforme après chaque cycle.

### Ajoute
- `active.selection` : `UncertaintyTimesDensity`, `Aleatoire`.
- `active.densite.densite_noyau` (Scott).
- `active.boucle.Loop` / `RapportActif`.
- Tests : produit nul, actif bat l'aléatoire (oracle synthétique contrôlé).
- `docs/formules/apprentissage-actif.md`, `experiences/j6_actif.py`.

### Change
- `ARCHITECTURE.md` / `tests/test_dependances.py` : couche `active`
  ← `types`, `light.protocole`, `uq`.

## [0.5.0] — 2026-09-09

Jalon 6, étape 1 : géométries rectilinéaires (pièces en L). Convention de coupe
**verticale à gauche d'abord**, documentée et testée.

### Ajoute
- `geom.rectilineaire` : `decomposer`, `recomposer`, `etendre_fusions`,
  `PieceRectilineaire`.
- `legalize(..., fusions=)` : égalités de solidarisation dans ``A_eq``.
- `docs/formules/rectilineaire.md`.

### Garanties
- Géométrie : exacte (partition + fusions linéaires).
- Performance : inchangée (jalon 5).

## [0.4.0] — 2026-09-09

Garantie **probabiliste** sur l'oracle gelé (`SimulateurExact`, split-flux) :
quantile conforme à échantillon fini, certificat à deux natures, diagnostic dual.
(Radiance) reste hors chemin critique.

### Ajoute
- `uq.conforme` : `quantile_conforme` (rang \(\lceil(n+1)(1-\alpha)\rceil\)),
  `CalibrateurConforme`, `borner`.
- `uq.fiabilite` : CRPS gaussien, diagramme `(nominal, empirique)`, stratification
  à 8 orientations.
- `uq.derive` : test d'échangeabilité (permutation), `mesurer_derive` sur tableaux.
- `uq.gestion.geler_et_emettre` / `ModeleModifie` si les poids bougent après le gel.
- `light.objectif.Daylight` : \(J=\hat\mu-q̂\hat\sigma\), sans importer `uq`.
- `certify.borne.construire_borne` : `None` si la dérive invalide l'échangeabilité.
- `certify.dual.traduire_duaux` : phrases avec intervalle de validité locale.
- `certify.rapport.rendre` : `[EXACT]` / `[PREDICTION]`, `NON EVALUABLE` toujours présent.
- Docs : `concepts/deux-garanties.md`, `prediction-conforme.md`, galerie 04–05,
  tutoriel de calibration, `formules/statistique.md`.

### Change
- `BornePerformance` refuse `n_calibration < 1`.
- `legalize` traduit les duaux via `certify.dual` ; `performance` reste `None`
  (`api` n'importe pas `uq`).

### Garanties
- Géométrie : inchangée (exacte).
- Performance : couverture \(\ge 1-\alpha\) **sous échangeabilité** avec le jeu
  de calibration, contre l'oracle split-flux — pas un sDA LM-83.

## [0.3.1] — 2026-09-09

Oracle `SimulateurExact` : le terme d'aire \(\times\sin 2\theta\) (jouet) est
remplacé par un **facteur de lumière du jour split-flux** (BRE / Littlefair).
(Radiance) reste hors chemin critique.

### Ajoute
- `light.simulateur.facteur_lumiere_jour` : DF moyen, WWR sur la façade sud.
- Tests métier : profondeur, sud/nord, WWR ; pièce canonique 6 m × 4 m (1–5 %).
- `docs/formules/split-flux.md`.

### Change
- `SimulateurExact.evaluer` / `.gradient` : analytique CIBSE + \(\sum 100\cdot\mathrm{DF}\cdot\mathrm{aire}\).
- Champ `wwr` (défaut \(0{,}30\)), sans élargir le protocole `Substitut`.

## [0.3.0] — 2026-09-09

Substitut **appris** (perceptron numpy, transformeur derrière `torch` paresseux)
et **point de contrôle du gradient**. Vérité terrain = `SimulateurExact`
(forme fermée). (Radiance) est hors chemin critique : extra `sim` vide, jamais
exigé par la CI ni par les jalons 5–6.

### Ajoute
- `data` : dédup Hausdorff \(0{,}02\,\mathrm{m}\), corpus synthétique, imputation
  de baies, `splits/v1/` (54 / 18 / 18).
- `uq.gestion` : jeton de calibration après gel ; `GestionDonnees`.
- `light.jetons` : ensemble continu, test anti-image (2 cm).
- `light.simulateur.SimulateurExact` : déterministe, protocole `Substitut`.
- `light.base.SubstitutDense` : 3 couches, Huber, sans `torch`.
- `light.appris.SubstitutAppris` : `npz` dense ; `.pt` charge `torch` localement.
- `light.validation.valider_gradient` : accord de signe, seuil 0,80 bloquant.
- `bench.compare(..., evaluate_by=)` obligatoire.
- `scripts/{preparer_donnees,simuler,valider_gradient}.py`,
  `experiences/j4_gradient.py`, `docs/donnees/`,
  `docs/concepts/pourquoi-pas-une-image.md`.

### Garanties
- Géométrie : inchangée (exacte).
- Score du réseau : **sans couverture** jusqu'au jalon 5.
- Le jeu de calibration n'est pas lu à l'entraînement.

## [0.2.0] — 2026-09-09

Légalisation performantielle **sans apprentissage** : le même oracle LP, un autre \(c\).

### Ajoute
- `orient.circulaire` : harmoniques, moyenne / variance, Rayleigh, régression, 8 secteurs.
- `light.analytique.SubstitutAnalytique` : profondeur utile saturée, 8 secteurs, sud géographique.
- `solve.frank_wolfe` : `depart=x`, pas \(2/(k+2)\), écartement, gap, coupes Kelley, duaux.
- `geom.polytope.figer_contacts` : contacts L1 saturés → égalités, et collage
  \(x,y\) au contour ; les largeurs min restent libres.
- `api.legalize(..., objective=Substitut, trace=True)` ; `objective=None` inchangé.
  Sortie FW revérifiée : un itéré invalide lève `InvariantViole`, sans repli L1.
- Expérience `experiences/j3_orientation.py`, `resultats/j3_orientation.csv` / `.svg`.
- Fiches `docs/formules/{circulaire,substitut-analytique,frank-wolfe}.md`, galerie 02,
  `docs/concepts/oracle-partage.md`.

## [0.1.0] — 2026-09-09

Premier livrable publiable : un plan entre, un plan valide et sa preuve exacte sortent.

### Ajoute — jalon 2, etapes 4–7
- `lmo.coupes` : tangentes d'appui a `{wh ≥ a_min}` (Boyd–Vandenberghe §3.1.5–3.1.6,
  AM-GM Hardy–Littlewood–Polya th. 16, Kelley 1960). Projection sur l'hyperbole avant
  d'ecrire la coupe, sinon un point infaisable exclut des rectangles admissibles.
- `geom.polytope.etendre_ecarts_l1` : epigraphe de `‖x − x̂‖₁` (Bertsimas–Tsitsiklis §1.3).
  Les `x̂_i` sont dans les contraintes, `c = (0_n, 1_n)`.
- `certify.preuve.verifier_exactement` : chevauchement, jours, surfaces, structure —
  independant du solveur. `valide` est la conjonction, sans aucun champ probabiliste.
- `api.legalize` / `api.gradient_distance` : legalisation classique. `objective` non nul
  reste le jalon 3. Infaisabilite = `Infaisable` avec certificat de Farkas et origines.
- `experiences/j2_taux_validite.py` et `resultats/j2_brut.csv` : protocole de mesure.
- Galerie 01 et 03, `docs/concepts/polytope.md`.
- `docs/formules/` : énoncé, dérivation, source et cas d'usage de chaque résultat
  du jalon 2 (ordre, polytope, L1, coupes, Farkas, preuve).

### Ajoute — jalon 1
- `types.Referentiel.a_min` : seuil reglementaire par type de piece ; un type inconnu
  rend `0.0` plutot que de lever.
- `types.Ouverture.segment_absolu` : la position d'une baie est **derivee** de son mur.
  Une baie suit desormais sa cloison quand le solveur la deplace.
- `io.json_io` : schema JSON versionne (`VERSION_SCHEMA = "1"`), aller-retour sans perte
  certificat compris, ecriture deterministe (cles triees, UTF-8, fin de ligne `\n`).
- `bench.graines.deriver` : sous-graines nommees, stables d'une machine a l'autre
  (BLAKE2b, jamais `hash()` qui est randomise par processus). Valeurs epinglees par test.
- `bench.manifeste.emettre` : manifeste de reproductibilite, graine obligatoire.
- `tests/properties/strategies.py` : `plans_quelconques` operationnelle, partagee par
  les jalons suivants.
- `docs/reference/schema-json.md` : le format d'echange documente.

### Ajoute
- Squelette du projet : arborescence, configuration qualite, CI, contrats de modules.
- `tests/test_dependances.py` : les regles de dependance de `ARCHITECTURE.md` §5 sont
  verifiees automatiquement des le premier commit, `__init__.py` compris.
- `tests/unit/test_protocole_substitut.py` : verifie que chaque implementation de
  `Substitut` respecte le protocole, signatures comprises.

### Modifie
- API publique : le chargement et le rendu passent par `Plan.from_json`, `Plan.to_json`
  et `Certificat.rapport()`, conformement a `DOCUMENTATION.md` §3 et §5. Les fonctions
  libres `charger` / `ecrire` ne sont plus exportees (voir ADR-5 du blueprint).
- Les documents contraignants sont regroupes dans `docs/specification/` et publies avec
  le site. `AGENTS.md` et `CLAUDE.md` restent a la racine : les outils les y decouvrent.

### Ajoute — jalon 2, etape 3 : oracle lineaire
- `lmo.solveur.resoudre` : backend OR-Tools GLOP, signature du §4 respectee a la lettre
  (`depart`, `coupes`, `duaux`). Le module **ignore toujours d'ou vient `c`**.
- Demarrage a chaud par reutilisation du modele GLOP, indexee par le polytope. Mesure :
  **0,206 ms a chaud contre 0,746 ms a froid, soit x3,6** — le facteur annonce au §10.
- Certificat de Farkas par probleme auxiliaire, multiplicateurs rendus sous forme
  canonique positive. Sur un cas reel, il designe `separation horizontale A|B` et
  `contour droit B` : deux pieces de 2 m ne tiennent pas dans 3 m.
- Prix duaux extraits sur demande, dans l'ordre des lignes de `A` — c'est cet ordre qui
  les rend appariables avec `origines`.
- `lmo.solveur.vider_cache` : garantit un depart a froid pour les mesures.
- Budgets du §9 actives : LP a froid **0,75 ms** (budget 10 ms), a chaud **0,21 ms**
  (budget 3 ms).

### Corrige — GLOP confond « infaisable » et « non borne »
- GLOP rend le code `INFEASIBLE` pour un probleme non borne. `resoudre` aurait donc leve
  « le programme ne tient pas dans l'enveloppe » sur un domaine ouvert. Un LP de
  faisabilite a objectif nul tranche desormais : il ne peut pas etre non borne, donc s'il
  trouve un point, l'echec venait de l'objectif.
- Le probleme auxiliaire relache aussi les coupes. Sans cela, une coupe impossible le
  rendait lui-meme infaisable et ses duaux ne voulaient plus rien dire.
- `test_warm_start_est_plus_rapide` echouait environ une fois sur sept : une somme de
  mesures laissait un seul pic d'ordonnancement decider. Mesures desormais entrelacees et
  comparees par leur mediane. Un test instable est pire qu'un test qui echoue.

### Ajoute — jalon 2, etape 2 : polytope
- `geom.polytope.construire_polytope` : assemblage `A x <= b`, bornes, `index` et
  `origines`. Graphe **reduit transitivement** avant assemblage.
- `Polytope.contient` : verification naive et directe, independante de tout solveur.
- `geom.polytope.vectoriser` / `devectoriser` : les ouvertures traversent la
  devectorisation intactes, sans resynchronisation a ecrire.
- Premier budget du §9 active : construction du polytope **1,08 ms** pour 15 pieces,
  contre 5 ms autorisees.
- `A_eq` reste vide, de forme correcte — voir ADR-7, question ouverte.

### Corrige — `deduire_ordre` choisissait le mauvais axe
- L'axe retenu est desormais celui sur lequel les pieces sont **reellement disjointes**,
  et non celui du plus grand ecart entre centres. Deux pieces separees en x mais
  recouvrantes en y recevaient une contrainte verticale que le plan d'origine violait :
  `legalize` aurait deplace des murs sur un plan sans defaut. Defaut trouve par le test
  de propriete du polytope, pas par relecture.
- Tolerance de contact `1e-9 m` : `1.0 + 3.47` vaut `4.470000000000001`, si bien que deux
  pieces jointives passaient pour recouvrantes de 1e-16 et basculaient dans le cas
  degrade. Le cas survient des qu'un mur separe deux pieces adjacentes.

### Ajoute — jalon 2, etape 1 : graphe de contraintes
- `geom.graphe.deduire_ordre` : extrait l'ordre relatif d'un plan propose en comparant
  les centres, axe du plus grand ecart. **Acyclique par construction** — sur chaque axe
  l'arete suit l'ordre total de la cle `(coordonnee, identifiant)`.
- `geom.graphe.construire_graphe` : deux `DiGraph` valides, cycles rejetes par
  `OrdreIncoherent` (avec l'axe et le cycle), paires non separees par
  `SeparationManquante`.
- `geom.graphe.reduction_transitive` : retire les aretes impliquees, conserve les noeuds
  isoles que `networkx.transitive_reduction` laisse tomber.
- `GrapheContraintes.fermeture()` : information d'ordre reelle, qui permet de prouver que
  la reduction ne perd rien.
- `tests/properties/strategies.ordres_valides` : ordres construits **sans reutiliser**
  `deduire_ordre`, pour que les tests de propriete ne soient pas tautologiques.

### Ajoute — validation a la frontiere (ADR-6)
- `io.json_io.depuis_dict` verifie les plages de `ARCHITECTURE.md` §6 : `s` dans
  `[0, 1]`, `largeur_rel` dans `]0, 1]`, dimensions et epaisseurs strictement positives.
  **Toutes** les violations sont rapportees ensemble, pas seulement la premiere.
- Les valeurs non finies sont refusees a la lecture : `json.loads` accepte les litteraux
  `NaN` et `Infinity`, ce qui aurait injecte des `NaN` dans le solveur depuis un fichier
  produit par un autre outil.
- La validation reste **a la frontiere** : les constructeurs ne verifient rien, pour que
  `solve` puisse traverser des etats intermediaires sans payer une verification par
  construction dans une boucle de Frank-Wolfe.

### Corrige — revue du jalon 1
- `io.json_io.ecrire` laissait remonter un `ValueError` de la bibliotheque standard sur
  une valeur non finie ; il leve desormais `InvariantViole`, conformement a
  `ARCHITECTURE.md` §7. `NaN` est precisement ce que produit un solveur bogue.
- `tests/properties/strategies.py` ne generait jamais de `violations` non vides ni de
  `performance` non nulle : la moitie probabiliste de la serialisation du certificat
  n'etait **jamais executee**, malgre 200 exemples Hypothesis. Generateur elargi.
- Couverture des modules du jalon 1 portee a 100 % (`types`, `erreurs`, `io`, `bench`).

### Corrige
- `pyproject.toml` declarait `readme = "README.md"` alors que le fichier s'appelait
  `README (2).md` : le paquet ne se construisait pas du tout.
- `testpaths` omettait `benchmarks/` : le job « budgets » de la CI ne collectait aucun
  test et passait au vert sans rien mesurer.
- `python_version = "3.11"` cote mypy faisait echouer l'analyse sur les stubs de numpy
  avant d'atteindre le code du projet.
