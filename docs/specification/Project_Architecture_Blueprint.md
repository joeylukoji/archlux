# Architecture blueprint — archlux

> Derived document. `ARCHITECTURE.md` is authoritative; this blueprint **details** it and
> never contradicts it. In case of divergence, `ARCHITECTURE.md` wins.
>
> Scope: file structure, contracts of each module, data flows, extension points, and the
> mechanisms that make the rules executable rather than declarative.

---

## 1. The structuring decision

Everything else in this document follows from a single decision:

> **Geometry is exact. Daylight is probabilistic. The two never mix —
> not in a type, not in a module, not in a message.**

This separation is not a naming convention: it is **materialized** by
four independent mechanisms, each able to catch the mistake alone.

| Mechanism | Where | What it catches |
|---|---|---|
| Disjoint types | `GeometricProof` / `PerformanceBound` | A probability slipped into a proof |
| Invariant test | `tests/properties/test_architecture_invariants.py` | The addition of a probabilistic field to the proof |
| `Guarantees` section | Every docstring returning a `Plan` or `Certificate` | A guarantee asserted without its kind |
| Separate rendering | `certify/report.py` | A composite score aggregating the two |

A single mechanism would be enough to document the rule. Four are needed for it
to survive eighteen months of development.

---

## 2. Actual tree

Consistent with `ARCHITECTURE.md` §11, with the additions marked and justified in §7.

```
archlux/
├── pyproject.toml               # core without torch; torch in the [appris] extra
├── mkdocs.yml                   # fixed nav: the docs have a structure, not a heap
├── README.md · CHANGELOG.md
├── AGENTS.md · CLAUDE.md        # agent routing — stay at the root (discovery)
├── .github/workflows/ci.yml     # 3 jobs: quality · tests · budgets
│
├── docs/specification/          # the binding documents, published with the site
│   ├── ARCHITECTURE.md          #   authoritative
│   ├── Project_Architecture_Blueprint.md
│   ├── DOCUMENTATION.md
│   ├── MILESTONE-2.md
│   ├── MILESTONE-3.md … MILESTONE-6.md
│
├── src/archlux/
│   ├── __init__.py              # public interface ONLY (24 names)
│   ├── py.typed
│   ├── types.py                 # frozen data model — depends on nothing
│   ├── errors.py                # ★ typed exceptions — depends on nothing (erreurs.py: deprecated shim)
│   ├── api.py                   # legalize() + gradient_distance()
│   │
│   ├── geom/                    # [1] DETERMINISTIC
│   │   ├── graph.py             #     relative order → DAG, transitive reduction
│   │   └── polytope.py          #     DAG → (A, b, A_eq, b_eq, bounds, index, origins)
│   │
│   ├── lmo/                     # [2a] DETERMINISTIC (GLOP cache, ADR-8) — ignores the origin of c
│   │   ├── solver.py            #      min <c,x>; warm start, duals, Farkas
│   │   └── cuts.py              #      area tangents (wh ≥ a)
│   │
│   ├── light/                   # [2b] THE ONLY LEARNED LAYER
│   │   ├── protocol.py          #      Surrogate Protocol — 3 methods
│   │   ├── analytic.py          #      closed forms, no learning
│   │   ├── learned.py           #      LearnedSurrogate: refuses .pt weights, the transformer does not exist
│   │   └── validation.py        #      validate_gradient() — mandatory before use
│   │
│   ├── solve/                   # [3] DETERMINISTIC
│   │   ├── frank_wolfe.py       #     away steps, warm start, certified gap
│   │   └── trace.py             #     frozen trace = output data, not a log
│   │
│   ├── orient/circular.py       # (cos θ, sin θ) encoding + circular statistics
│   │
│   ├── uq/                      # uncertainty quantification
│   │   ├── conformal.py         #     quantile ceil((n+1)(1−α))/n
│   │   ├── registry.py          #     ★ access token to the calibration set
│   │   └── drift.py             #     exchangeability check
│   │
│   ├── certify/                 # [4] DETERMINISTIC
│   │   ├── proof.py             #     EXACT verification, independent of the solver (preuve.py: deprecated aliases)
│   │   ├── bound.py             #     assembly of the probabilistic guarantee
│   │   ├── dual.py              #     dual prices → architect's language
│   │   └── report.py            #     rendering, two separate sections
│   │
│   ├── bench/                   # leaf of the tree: nobody imports it
│   │   ├── protocol.py          #     ★ fixed 60/20/20 split
│   │   ├── manifest.py          #     ★ reproducibility manifest
│   │   └── seeds.py             #     ★ deterministic seed derivation
│   │
│   └── io/json_io.py            # versioned JSON schema, deterministic serialization
│
├── tests/
│   ├── conftest.py              # single seed, never implicit
│   ├── test_dependencies.py      # ★★ the dependency rules are executable
│   ├── unit/
│   ├── properties/
│   │   ├── strategies.py        #     Hypothesis strategies shared by all milestones
│   │   ├── test_architecture_invariants.py
│   │   └── test_milestone2_acceptance.py
│   └── references/              # frozen certificates, compared byte for byte
│
├── benchmarks/test_budgets.py   # the §9 budgets are contracts, not measurements
├── experiments/                 # throwaway scripts, < 50 lines, public API only
├── results/                     # raw, before any aggregation
└── docs/                        # gallery → tutorials → concepts → reference
```

★ = addition to §11 of `ARCHITECTURE.md`, justified in §7 of this document.

---

## 3. Data flows

### 3.1 Classic legalization — `objective=None`

```
Proposed plan ┬─► deduce_order ──► RelativeOrder
              │                          │
Context ──────┼──────────────────────────┼─► build_polytope ──► Polytope
              │                          │        (A, b, index, origins)
              │                          ▼
              │                   gradient_distance(x̂) ──► c
              │                          │
              │                          ▼
              │                   lmo.solve(poly, c, duals=True)
              │                          │
              │            infeasible ───┴──► raise Infeasible(farkas, origins)
              │                          │
              │                       optimal
              │                          ▼
              │                   devectorize ──► candidate Plan
              ▼                                        │
        certify.verify_exactly  ◄──────────────────────┘
                    │
          invalid ──┴──► raise InvariantViolation    (internal bug, never silent)
                    │
                  valid
                    ▼
        Plan + Certificate(geometry=proof, performance=None, duals=translated)
        (classic mode claims nothing about daylight: performance is always None)
```

**The non-negotiable point** is the feedback loop to `verify_exactly`: the
solver's output is never returned to the user without having been re-checked by a
**separate and naive** implementation. If GLOP has a bug, this check is what
catches it — and it raises, it does not correct.

### 3.2 Performance legalization — `objective=Surrogate`

The flow is **the same**, with a loop around the oracle:

```
Classically legalized plan ──► x₀
        │
        ▼
   ┌──► surrogate.gradient(x_k, orientation) ──► c = −∇
   │         │
   │         ▼
   │    lmo.solve(poly, c, start=x_k)   ← SAME solver, SAME polytope
   │         │
   │         ▼
   │    step + away step ──► x_{k+1}, gap
   └─────────┤
             │ gap < tol or k = max_iter
             ▼
        certify.verify_exactly  (identical)  +  certify.bound.bound_selected_plan
                                                (only if calibration=...)
             │
             ▼
   Plan + Certificate(geometry=EXACT proof,
                      performance=bound with regime 'selected' (coverage NOT guaranteed)
                                  if calibration, otherwise None)
```

What this diagram shows: **`lmo` has not changed by one line** between the two modes.
It is the property that the test `test_lmo_n_importe_jamais_light` protects.

---

## 4. Contracts per module

A module has a three-part contract: what it **returns**, what it **guarantees**, what
it is **forbidden** to know.

| Module | Returns | Guarantees | Must not know |
|---|---|---|---|
| `types` | Frozen structures | Immutability, derived opening position | Everything else |
| `errors` | Typed exceptions | No bare `Exception` in the project | Everything else |
| `geom.graph` | `ConstraintGraph` | Acyclic; every pair separated | Dimensions, costs |
| `geom.polytope` | `Polytope` | Every point ⇒ plan without overlap; without gap **only** with `tiling=True` | Objectives |
| `lmo.solver` | `LPSolution` | LP optimality, or Farkas if infeasible | **The origin of `c`** |
| `lmo.cuts` | `Cut` | Tangents: **outer** approximation, no feasible point excluded, the proof re-checks the areas; chords (`inner_area_constraints`): **inner** approximation, no point below a minimum area | Daylight |
| `light.protocol` | *(interface)* | Three methods, vector input | `geom`, `lmo`, `solve` |
| `light.learned` | value, ∇, σ | Nothing by itself — the guarantee comes from `uq` | The geometry |
| `solve` | `FrankWolfeResult` | Validity at every iterate; `status`; the gap is a stationarity measure, not a distance to the optimum (no shipped surrogate is concave) | The surrogate's implementation |
| `orient` | Encodings, statistics | Continuity at 0°/360° | The rest of the plan |
| `uq.conformal` | `PerformanceBound` | Coverage ≥ 1−α **under exchangeability** | The geometry |
| `certify.proof` | `GeometricProof` | Rational arithmetic on an axis-aligned rectangular outline (only tolerance `SNAP_M`), GEOS and declared tolerances otherwise | Any probability |
| `certify.dual` | `(label, cost)` | Faithful translation via `origins` | — |
| `bench` | Splits, manifests | Reproducibility | — |

### The three "deliberate ignorances"

These three rows of the table are not omissions; they are the **design choices
that carry the project**, and each is guarded by a dedicated test.

1. **`lmo` ignores the origin of `c`.** A single solver serves both modes. Teaching it
   daylight destroys this reuse and makes performance mode a second system
   to maintain in parallel.
2. **`solve` ignores which implementation of `Surrogate` it handles.** This is what
   makes it possible to run the complete chain at milestone 3, with closed formulas,
   **before spending a cent on simulation**. If the architecture is wrong, it is
   wrong at that moment.
3. **`light` ignores the geometry.** It only sees a vector and an azimuth. This is what
   confines `torch` to a single file and keeps `import archlux` light.

---

## 5. How the rules are made executable

An architecture rule written in a Markdown file has a half-life of six months.
Each of the binding rules is therefore doubled by an automatic mechanism.

| Rule (`ARCHITECTURE.md`) | Mechanism | File |
|---|---|---|
| §5 — layers and dependencies | AST analysis of the imports, one test per module | `tests/test_dependencies.py` |
| §5 — core without `torch` | Subprocess + inspection of `sys.modules` | same |
| §5 — `lmo` ⇏ `light` | Dedicated test | same |
| §5 — `solve` ⇒ `light.protocol` only | Dedicated test (the implementation is refused) | same |
| §5 — nobody imports `bench` | Dedicated test | same |
| §6 — frozen types | `is_dataclass` + `__dataclass_params__.frozen` | `tests/properties/test_architecture_invariants.py` |
| §6 — proof without probability | Blacklist of field names | same |
| §6 — bound with coverage | Whitelist of mandatory fields | same |
| §6 — opening without absolute position | Blacklist of field names | same |
| §7 — style, types | `ruff` + `mypy --strict` | `ci.yml`, *quality* job |
| §9 — performance budgets | `pytest -m budget --benchmark-only`, separate job | `benchmarks/test_budgets.py` |
| `DOCUMENTATION.md` §6 — doctests | `pytest --doctest-modules src/archlux` | `ci.yml` |
| `DOCUMENTATION.md` §6 — doc coverage | `interrogate -f 95` | `ci.yml` |

**The "tests" job runs `test_dependencies.py` in a separate, earlier step.**
A layer violation must be readable in the name of the failing step, not drowned
among three hundred tests.

Two clarifications, each of which cost a real defect:

- **the `__init__.py` files are scanned.** Excluding them leaves the most likely hole: a
  package that violates a layer from its own `__init__`;
- **exemptions are named and capped.** `EXEMPTIONS` lists three specific imports
  (ADR-5, ADR-9), and `test_les_exemptions_restent_rares_et_nommees` fails at the fourth.
  An uncapped exemption list is how a layer rule empties itself,
  one entry at a time.

The test count is no longer kept here (it was stale): CI is authoritative.
`ruff check .` and `mypy --strict` on `src/` are CI gates.

---

## 6. Extension points

Where to extend the system without breaking anything, and where **not** to extend it.

| Need | Extension point | Why it is the right one |
|---|---|---|
| New indicator (UDI, view) | New implementation of `Surrogate` | `solve` and `lmo` unchanged |
| Frozen split-flux oracle (`SplitFluxOracle`) | Same — third implementation of the protocol | Makes it possible to measure the surrogate's error on the same interface |
| New regulation | New `Regulation` (a **datum**) | No code of `geom` or `lmo` to touch |
| New kind of geometric constraint | Extra rows in `build_polytope` + entries in `origins` | The dual diagnostics stay readable |
| New corpus | Loader in `bench`, fixed `Split` | The three-set rule still holds |
| Non-rectangular rooms | `geom` only: L-shaped rooms by merging rectangles (`geom.rectilinear`); non-Manhattan is not shipped | The rest of the chain only sees a polytope |

**Not to do:** add an argument to `solve` to "pass a bit of daylight
context". That is how the ignorance of `lmo` gets lost — not all at once, but
one parameter at a time.

---

## 7. Architecture decisions — the additions to §11

Three files do not appear in the target tree of `ARCHITECTURE.md`. Here is
why they exist.

### ADR-1 — `errors.py` separate from `types.py`

`ARCHITECTURE.md` §7 requires typed exceptions without assigning them a file. Putting
them in `types.py` would raise a problem: `Infeasible` carries a Farkas certificate
and the labels of a `Polytope`, objects of the `lmo` and `geom` layers. An `errors`
module without any dependency, upstream like `types`, avoids the cycle. The fields there
are typed `object`, and the readable translation is done by the caller. (The module was
called `erreurs.py`; that name is now a deprecated shim.)

**Alternative rejected:** exceptions in each module. Rejected — the user would have to
import from four places to write an `except`.

### ADR-2 — `uq/registry.py`: access token to the calibration set

`ARCHITECTURE.md` §10 names "calibration set read during training" as the only
**silent** error able to invalidate a publication. A team rule is not enough
against a silent error: the file materializes the README's requirement ("access
to the calibration set requires a token issued after the model is frozen") in code, and
`CalibrationLocked` makes it loud.

### ADR-3 — `bench/{manifest,seeds}.py`

The README requires a manifest **at every run, without exception**, and §7 a mandatory
seed without default on every function that samples. `bench.seeds.derive`
gives a named stream per component from a root seed: two components never
share a stream, and a run replays exactly. Without this single point,
each module invents its own convention.

### ADR-4 — `tests/test_dependencies.py` written before any implementation

The test costs an hour today and a complete refactor at milestone 4. It is at the root
of `tests/`, not in a subdirectory, because it tests no behaviour: it
tests the **shape** of the project.

---

### ADR-9 — `Plan.to_dxf`, `to_ifc` and `to_svg`: a third nominal exemption

PLAN.md 3.11 makes the exports methods of the model, as `Plan.to_json` already is. `types`
must then reach `archlux.export`. Same decision as ADR-5: a **local import** inside the
three methods, which only delegate (the writing stays in `export`), so no cycle and no
cost at import. One `EXEMPTIONS` entry, `archlux.export`, not one per submodule: the
package facade is the only door `types` uses. The cap of
`test_les_exemptions_restent_rares_et_nommees` goes from 2 to 3.

### ADR-8 — A cache of GLOP models carries the warm start

`SetStartingLpBasis` **is not exposed** in the Python binding of OR-Tools: the only
real warm-start mechanism is the reuse of the `MPSolver` instance, which
lets GLOP restart from its current basis when only the objective changes.

Yet `solve(poly, c, *, start=…)` is stateless, and `MILESTONE-2.md` §4 forbids
changing its signature. The compromise chosen: a bounded cache of four models, keyed by
the `id` of the polytope, whose value **holds the polytope by strong reference** — as long
as it is there, its `id` cannot be reassigned, so the key stays correct.

`start` is not consumed as a numerical starting point: its **presence** is the
signal "I am in a loop on the same polytope, reuse the model". It is a
literal reading of the intent of §10 ("LP without `depart=` in the FW loop: ×3 to ×5
time lost"), and the measurement confirms it: **×3.6**.

A global state in a module that `ARCHITECTURE.md` §3 declares *pure* deserves a
justification: the cache changes **no result**, only the time. The purity aimed at
here — determinism, nothing learned — is intact, and a property test checks at every
run that cold and warm return the same solution. `clear_cache()` makes the cold
start explicit for measurements.

### ADR-7 — Load-bearing walls: side inequalities read from the proposed plan

- **Status:** decided (2026-09-23, PLAN.md batch 1.1). Supersedes the open question of
  milestone 2.

**Context.** `MILESTONE-2.md` §3 asked for `A_eq` rows tying rooms to load-bearing walls.
They were never written; the proof then compared each wall with itself — walls are not
decision variables — so `structure_kept` was always true, and rooms crossed
load-bearing walls under a valid certificate (AUDIT.md §3 n°1; 35 of 200 benchmark cases
in performance mode).

**Decision.**

1. A load-bearing wall is a **fixed obstacle**, not an equality. Each room keeps one
   side of each wall — `x + w <= c`, `x >= c`, `y + h <= c` or `y >= c` — read from the
   proposed plan by `deduce_order(plan, structure=...)` (`RelativeOrder.wall_sides`),
   the half-plane the room penetrates least among those with room before the outline.
   `build_polytope(order, ctx)` keeps its signature: the incidence travels in the
   order, like the relative order between rooms.
2. Equalities were rejected: they would pin rooms to walls and forbid a room from
   being bounded by a wall on one side only, or from not touching it at all.
3. The proof checks the guarantee directly: no room interior contains a stretch of a
   load-bearing wall (geometric test, oblique walls included).
4. Oblique load-bearing walls raise `UnsupportedInput`: no single linear side row
   describes them, and ignoring them silently is what this ADR removes.
5. **Columns** (`Structure.columns`) are fixed data and are not constrained: a column
   inside a room is normal in housing. Nothing about them is certified.
6. **Openings** are relative to walls (`Opening.wall_id`), and walls are not decision
   variables: an opening on a facade stays put (the outline is fixed), but an opening on
   an interior partition does **not** follow a moved room. The README claim "windows
   follow" is withdrawn (PLAN.md 1.8).

**Consequences.** Classic, tiling and performance modes inherit the rows since they
share the polytope. The benchmark reports 0 false certificates after this batch. The
choice of a single half-plane is a deliberate over-constraint, as for the order between
rooms (see `docs/formulas/separated-polytope.md`).

### ADR-6 — The ranges of §6 are checked at the boundary, not in the constructors

> **Addendum (phase 3, 2026-09-25).** `legalize` validates its arguments once at
> entry (`archlux.validation.validate_inputs`, `InvalidInput`): a single check
> costs nothing, the objection below does not apply to it. The types **outside the hot
> loop** also validate at construction: `Opening` (ranges of `s` and `relative_width`)
> and `GeometricProof` (a valid proof reports no fault). `Room`, `Wall` and
> `Orientation` stay free: Frank-Wolfe builds them by the thousand, and the proof must
> be able to *report* a malformed room. `from_dict` checks the ranges on the raw
> data, before building, to report all the violations together.

`ARCHITECTURE.md` §6 documents `s ∈ [0,1]` and `relative_width ∈ ]0,1]`, and a room has
positive dimensions. Nothing enforced it: `Opening(s=42.0)` was built
without complaint.

| Option | Verdict |
|---|---|
| Validate in `__post_init__` | Rejected — would forbid the solver any intermediate out-of-range state, and would charge a check at every construction in a Frank-Wolfe loop that makes thousands of them |
| **Validate in `from_dict`** | **Chosen** |
| Validate nothing | Rejected — the invariant stayed purely documentary |

The JSON boundary is where data comes from outside: that is where it
must be refused. The in-memory object stays free, which lets `solve` work without
constraint, and a file that has been read is guaranteed sound.

`_check_ranges` reports **all** the violations at once, not the first one:
fixing a file one error at a time is torture, and nothing forces anyone to put up with it.

Corollary drawn from the same pass: `json.loads` accepts the literals `NaN` and
`Infinity`. Since `write` already refused to write them, reading had to refuse to read them —
otherwise a file produced by another tool injects non-finite values into the
solver, where they propagate silently up to an absurd certificate.

### ADR-5 — `Plan.from_json` and `Certificate.report()`: two named exemptions

`DOCUMENTATION.md` §3 and §5 fix a public API where loading and rendering are
**methods of the model**: `Plan.from_json(...)`, `q.certificate.report()`. Honouring them
requires `types` to reach `io` and `certify`, whereas `types` must depend on
nothing.

Three options were weighed:

| Option | Verdict |
|---|---|
| Free functions `ax.load` / `ax.report` | Rejected — contradicts the API that the specs already publish in their examples |
| Import of `io` and `certify` at the top of `types` | Rejected — cycle at import, and the rule "`types` depends on nothing" disappears |
| **Local import in the two methods** | **Chosen** |

The local import runs at call time, never at import time: no cycle, and `import archlux`
stays as light as before. The two methods only **delegate** — reading stays
in `io`, formatting in `certify`. The cost is real and accepted: two entries in
`EXEMPTIONS`, capped by a test.

## 8. Implementation order and status

| Milestone | Modules | Deliverable | Skeleton status |
|:--:|---|---|---|
| 1 | `types`, `errors`, `io`, `bench.{seeds,manifest}` | JSON round trip | **Done** — round-trip property green on 200 cases |
| **2** | `geom`, `lmo`, `certify.proof`, `api` | **Classic legalization + proof** | Steps 1 to 3 done (`geom.graph`, `geom.polytope`, `lmo.solver`); steps 4 to 7 to come |
| 3 | `light.analytic`, `orient`, `solve` | Performance **without learning** | Contracts written |
| 4 | `light.learned`, `light.validation`, `uq.registry` | Trained surrogate + validated gradient | Contracts written |
| 5 | `uq.conformal`, `uq.drift`, `certify.{bound,dual,report}` | Complete certificate | Contracts written |
| 6 | non-Manhattan, active, IFC | v1.0 | — |

> **Status at batch 1.8 (PLAN.md).** This table describes the skeleton of milestone 1 and is
> no longer up to date: milestones 1 to 5 are implemented; milestone 6 is partly
> (L-shaped rooms, active learning, IFC export; **not** non-Manhattan); milestones
> 7 to 9 are experiments (`experiments/`, `results/`). The sentence
> "outside milestone 1, no function body is implemented" is withdrawn.

Milestone 1 delivers on the way what does not show in the table: `plans_quelconques`,
the Hypothesis strategy on which the acceptance criterion of milestone 2, the cut tests
and the drift tests will depend. Written once here, it avoids three diverging generators.

---

## 9. Cross-cutting conventions

| Point | Rule | Where it is checked |
|---|---|---|
| Units | metres, m², azimuth degrees | Docstrings; review |
| Origin | bottom-left corner, `y` towards north | `geom.polytope` |
| Determinism | explicit sorting of identifiers, never the order of a `set` | `Plan.room_ids`, `RelativeOrder.rooms` |
| Seeds | `seed: int` mandatory, **without default** | Signatures of `uq.drift`, `light.validation` |
| Metrics | value **+** interval, never a bare scalar | `PerformanceBound` |
| Logs | `structlog`, structured, never free text | Review |
| Frozen dictionaries | tuples of pairs in the frozen types | `Regulation`, `Manifest`, `Certificate` |

The last point deserves a word: a `dict` in a `dataclass(frozen=True)` stays mutable
and is not hashable. The model types therefore use sorted `tuple[tuple[str, T], ...]`
— which also makes serialization reproducible, a condition of the manifest.

---

## 10. What this blueprint does not allow

The eight anti-patterns of `ARCHITECTURE.md` §10 count as grounds for refusal in review,
without discussion of the particular case. The three most costly to discover late:

1. **Raster as the input of a surrogate.** Zero gradient almost everywhere, blind optimizer.
   Detectable only by `validate_gradient` — hence its mandatory nature.
2. **Calibration set seen during training.** No test reports it; only the token
   of ADR-2 prevents it.
3. **`origins` omitted from the `Polytope`.** The dual diagnostics of milestone 5 become
   impossible and the module must be rebuilt.
