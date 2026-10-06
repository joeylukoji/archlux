# Technical debt

Work deliberately deferred, with the measurement taken when it was deferred. Each item
names how to know it is paid off. Settle it before phase 7 (general review), at the
latest.

## Phase 4 exit gate (deferred 2026-10-07)

Phase 4 was closed with its exit gate partly unmet, by the maintainer's decision, so that
phase 5 could start. Measured on 2026-10-07, branch `phase4-block16-experiments`:

### D1. Modules over 400 lines (gate: none)

19 modules, against 12 at the start of phase 4. Part of the growth is the numpydoc
`Parameters`/`Returns` sections added in block 17, which count as lines.

| Lines | Module |
|--:|---|
| 1225 | `data/loaders.py` |
| 1084 | `api.py` |
| 986 | `certify/proof.py` |
| 920 | `lmo/cuts.py` |
| 886 | `geom/rectilinear.py` |
| 785 | `geom/graph.py` |
| 778 | `io/json_io.py` |
| 741 | `active/loop.py` |
| 729 | `types.py` |
| 695 | `geom/polytope.py` |
| 692 | `lmo/solver.py` |
| 676 | `solve/frank_wolfe.py` |
| 666 | `export/ifc.py` |
| 573 | `light/base.py` |
| 569 | `bench/generation.py` |
| 480 | `uq/conformal.py` |
| 455 | `orient/circular.py` |
| 434 | `export/svg.py` |
| 410 | `errors.py` |

Open question first: does the 400-line rule count docstrings? Measure without them before
splitting anything.

### D2. Functions over cyclomatic complexity 10 (gate: `radon cc src -n C` empty)

17 left, frozen by the ratchet `tests/test_complexity.py` (`MAX_VIOLATIONS = 17`): lower
the constant each time one is split.

- `geom/grid_repair.py`: `_consolidate` (24), `_repair_partition` (14)
- `light/validation.py`: `validate_gradient` (18)
- `geom/diagnostic.py`: `diagnose` (16)
- `data/loaders.py`: `split_by_site` (14), `_opening_from_window` (12), `_stitch` (11)
- `geom/tiling.py`: `tiling_constraints` (13)
- `uq/reliability.py`: `measure_coverage` (13)
- `geom/rectilinear.py`: `overlap_constraints` (12), `extend_merges` (12), `_cut_up` (11),
  `_detect_merges` (11), `minimum_area_shares` (11)
- `certify/proof.py`: `_interiors` (12), `_areas` (11)
- `geom/graph.py`: `_compatible_sides` (12)

### D3. Experiment scripts over 50 lines (`ARCHITECTURE.md` §11)

`j8_visuals.py` (170), `j9_orientation.py` (161), `j7_sd_labels.py` (139),
`j7_sd_per_room.py` (134), `j3_orientation.py` (54), `j5_coverage.py` (54),
`j6_ifc.py` (52), `j2_validity.py` (51). Move their report code into the library, as
`archlux.bench.generation` did for `j8_generation.py`, and check the outputs
byte for byte against the real data (`D:/archlux-donnees`).

### D4. Not measured at closure

- Coverage: gate ≥ 95 % lines and ≥ 90 % branches; last measured 92 % lines
  (2026-10-02), branches never.
- Fresh `python-design-patterns` and `review-and-refactor` review: gate 0 Critical,
  0 Major; not run.

### D5. mypy on `experiments/`

`mypy src` is clean; `mypy src experiments` reports 29 errors in 10 files (all
pre-existing in the scripts).
