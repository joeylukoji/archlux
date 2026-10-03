# ARCHITECTURE — archlux

> Context for coding agents (Cursor, Claude Code, etc.).
> **Read this file before any change.** The rules below are binding.

---

## 1. Purpose of the project

`archlux` corrects architectural plans produced by generative models:

1. **make the plan geometrically valid** (no overlap, no gap, minimum areas
   respected, every room on the right side of the load-bearing walls, displacement bounded
   by `budget`);
2. **improve daylight without leaving that validity**: among the valid
   plans that **keep the proposed relative order** (a single cell of the space of
   plans: frozen contacts, displacement budget), Frank-Wolfe looks for a better
   point for the surrogate. It returns a stationary point, not the global optimum, and
   never explores the other relative orders.

The output carries **two guarantees of different kinds**:

| Guarantee | Kind | Verification |
|---|---|---|
| Geometric | **exact** on the model (axis-aligned rectangles) | `certify.proof.verify_exactly`: rational arithmetic on an axis-aligned rectangular outline (only tolerance: `SNAP_M` on lengths), GEOS with declared tolerances otherwise; infeasibility by a Farkas certificate verified exactly, **for the proposed relative order** |
| Daylight performance | **probabilistic** | conformal prediction; coverage ≥ 1−α **only** in the `"exchangeable"` regime. A plan chosen by the optimizer is in the `"selected"` regime: coverage **not** guaranteed (`PerformanceBound.regime`) |

**Never confuse them, not in the code, not in the types, not in the messages.**

---

## 2. Founding principle

> The generator decides **the order** of the rooms.
> The solver decides **the dimensions**.
> The neural network **only** provides a direction (gradient).

Consequence: the Frank-Wolfe linear oracle **is** the legalization solver.
One solver, two objective vectors.

```text
# pseudo-code (real calls: lmo.coupes.resoudre_avec_surfaces, solve.frank_wolfe)  # lang-ok: French identifier, not renamed yet
# classical legalization: L1 epigraph around the proposed plan
x = lmo.resoudre(poly_l1, c=gradient_distance(x_propose))

# performance legalization (1 Frank-Wolfe iteration), warm start
s = lmo.resoudre(poly_fw, c=-substitut.gradient(x_k, orientation), depart=x_k)
```

**Daylight oracle.** The core only knows the `Surrogate` protocol.
Shipped implementations: `AnalyticSurrogate` (closed forms), `SplitFluxOracle`
(analytic + BRE split-flux: the **frozen oracle** of the CI, a closed form, neither a
simulation nor a ground truth), `DenseSurrogate` (`numpy` perceptron) and
`LearnedSurrogate` (which refuses `.pt` weights: the transformer does not exist). A
ray-tracing engine (Radiance) is **off the critical path**: empty `sim` extra, never
imported by the core, never required by the CI nor by milestones 5–6. It can be plugged in
later behind the same protocol. The daylight guarantee of milestone 5 is about **this
frozen oracle**, not about an LM-83 sDA.

---

## 3. Layers

```
INPUTS: proposed plan · load-bearing structure · orientation · room program
   │
   ▼
[1] geom      modelling → polytope (A, b)           DETERMINISTIC
   │
   ├──────────────┬──────────────────────────┐
   ▼              ▼                          ▼
[2a] lmo       LP solver, configurable   [2b] light   surrogate
     objective (GLOP cache)                  value / gradient / σ    LEARNED
   │              │                          │
   └──────────────┴────────► [3] solve  Frank-Wolfe   DETERMINISTIC
                                   │
                                   ▼
                             [4] certify   proof + bound + duals   DETERMINISTIC
                                   │
                                   ▼
              OUTPUT: valid plan + certificate + dual diagnostic
```

**All layers are deterministic** (same inputs, same output); only one is
learned, isolated behind a protocol. They are not all **pure**: `lmo` keeps
a mutable global cache of GLOP models (at most 4, `lmo.solver._CACHE`, ADR-8 of the
blueprint) for the Frank-Wolfe warm start. This cache changes the time, never
the result; `lmo.solver.clear_cache` empties it, and the budget tests empty it before
measuring a cold LP.

---

## 4. Modules

| Module | Single responsibility | Learned? |
|---|---|---|
| `types` | `Plan`, `Room`, `Opening`, `Wall`, `Context`, `Certificate` | no |
| `geom` | relative order → constraint graph → polytope | no |
| `lmo` | solve `min <c,x>` over the polytope. **Ignores where `c` comes from** | no |
| `solve` | Frank-Wolfe (+ away-steps, warm start, cuts) | no |
| `light` | `Surrogate` protocol: `evaluate`, `gradient`, `incertitude` | **yes** |
| `orient` | circular encoding and statistics | no |
| `uq` | conformal calibration, drift control | no |
| `active` | selection of plans to simulate (uncertainty × density) | no |
| `export` | IFC / DXF, pathologies, survival rate (Wilson) | no |
| `feasibility` | existence of a valid plan (Farkas), without daylight | no |
| `certify` | exact verification + bound + translation of the duals | no |
| `bench` | protocol, seeds, manifests, run/report/stats | no |
| `data` | corpus, dedup, frozen split | no |

---

## 5. Dependency rules (binding)

```
types   ← everyone
tolerances, seeds, arrays ← everyone   (leaves: they import nothing from archlux)
validation ← types, errors   (door checks of the public arguments; imported by api)
geom    ← types
lmo     ← types, geom
solve   ← types, geom, lmo, light PROTOCOL (never the implementation)
light   ← types, orient
uq      ← types
data    ← types, uq, orient, geom   (corpus loaders: straightening + split)
active  ← types, light.protocol, uq
export  ← types, errors
feasibility ← types, errors, api
certify ← types, geom, uq
api     ← types, errors, validation, geom, lmo, solve, light PROTOCOL, certify, io
bench   ← everything
```

**FORBIDDEN:**

- [ ] `geom`, `lmo`, `solve`, `certify` **must never import `torch`**
- [ ] `lmo` must never import `light`
- [ ] `light` must never import `geom`, `lmo` or `solve`
- [ ] `active` imports no `light.*` implementation (only the protocol)
- [ ] `export` imports neither `geom` nor `certify` (certificate appendix via `Plan.certificate`)
- [ ] `feasibility` imports neither `light` nor `uq` (no performance promise).
      **Justified exception:** `is_feasible` calls `legalize`, so `feasibility` depends
      on `api` by design and therefore *loads* `light.protocol` (via `solve`) and `uq`
      (via `certify`) through it. It never imports them directly (static test), loads no
      `light` implementation, and loads nothing `api` does not already load (dynamic test)
- [ ] no module may import `bench`
- [ ] `data` may read `geom` and `orient` (corpus loaders **only**),
      never `lmo`, `solve` or `light`: it produces inputs, it solves nothing

Every rule above is checked twice by `tests/test_dependencies.py`: statically (the AST
of every module against `AUTORISE`) and dynamically (`FORBIDDEN`: a fresh subprocess
imports the package, all its submodules and every name of its `__all__`, then reads
`sys.modules`, with no transitive closure). The simplest of these tests:

```python
def test_le_noyau_n_importe_pas_torch():  # lang-ok: real test name in tests/test_dependencies.py
    import subprocess, sys
    code = "import archlux, sys; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
```

---


## 6. Data model — invariants

```python
@dataclass(frozen=True, slots=True, kw_only=True)   # Piece, Mur, Ouverture: keyword-only
class Room:
    id: str; type: str
    x: float; y: float; w: float; h: float      # metres

@dataclass(frozen=True, slots=True, kw_only=True)
class Opening:
    id: str
    wall_id: str            # ← relative to a wall
    s: float               # relative abscissa ∈ [0,1]
    relative_width: float     # ∈ ]0,1]
    sill_height: float = 1.00
    head_height: float = 2.15

@dataclass(frozen=True, slots=True)
class Plan:
    rooms: tuple[Room, ...]
    walls: tuple[Wall, ...] = ()
    openings: tuple[Opening, ...] = ()
    outline: tuple[tuple[float, float], ...] = ()   # empty: taken from Contexte.contour
    certificate: "Certificat | None" = None
```

**Absolute rules:**

- [ ] All types are `frozen=True` — **never any in-place mutation**
- [ ] The **absolute** position of an opening is **never stored**, always derived
- [ ] A legalized plan **always** carries its certificate
- [ ] `GeometricProof` has **no** probability field
- [ ] `PerformanceBound` **always** carries `coverage` and `n_calibration`

---

## 7. Conventions

| Topic | Rule |
|---|---|
| Units | metres, m², degrees (azimuth) |
| Origin | bottom-left corner of the outline, y axis towards geographic north |
| Seeds | `seed: int` argument **mandatory, with no default**, on every function that samples |
| Metrics | return **value + interval**, never a bare scalar |
| Errors | typed exceptions (`InconsistentOrder`, `Infeasible`, `InvariantViolation`) — never `Exception` |
| Logs | `structlog`, structured logging, never free text |
| Style | `ruff check` + `ruff format` + `mypy --strict` on `src/` |
| Language | **English** for code, API, docstrings, messages, tests and documentation. New code is English now; existing French is migrated batch by batch ([ADR 0001](../adr/0001-english-first.md), [glossary](../glossary.md)). This file was translated in batch E3 |
| Tolerances | target rule, enforced from PLAN.md 1.5: declared once in `archlux/tolerances.py`, never as inline literals |

---

## 8. Definition of "done" for any change

- [ ] `pytest` passes (unit + properties)
- [ ] `ruff check .` and `mypy src/` clean
- [ ] No new dependency in the core
- [ ] If the public API changes: `CHANGELOG.md` updated
- [ ] If an invariant is added: a **property-based** test comes with it
- [ ] The performance budgets of §9 are met

---

## 9. Performance budgets (contracts, measured in CI)

| Operation | Budget | Reference |
|---|---|---|
| Polytope construction | < 5 ms | 15 rooms |
| Cold LP | < 10 ms | 15 rooms |
| Warm LP (`depart=`) | < 3 ms | 15 rooms |
| Full classical legalization | < 20 ms | 15 rooms |
| Performance legalization | < 500 ms | 15 rooms, 50 iterations at most |
| Certification | < 5 ms | 15 rooms |

**What is measured, and what is not.** `benchmarks/test_budgets.py` (CI job
`budgets`, `pytest -m budget --benchmark-only`) measures these budgets on **the most
favourable case**: a 5 × 3 grid of rooms that is already valid, with no load-bearing wall, no tiling,
analytic surrogate. Since batch 1.2, it also covers the performance mode with tight
minimum areas (15 rooms) and a scaling test at 15, 50 and 100 rooms. No
budget covers a noisy input, `tiling=True` or load-bearing walls: for these cases,
the `benchmarks/guarantees/` bench records median times (about 5 ms in classical mode,
15 to 20 ms in performance mode over 200 scenarios) without making them a contract. Under
`--benchmark-disable`, an unmeasured budget is **skipped**, not validated.

---

## 10. Anti-patterns to reject in review

| Anti-pattern | Why it is fatal |
|---|---|
| Image / raster as surrogate input | Gradient zero almost everywhere → blind optimizer → **project impossible** |
| Absolute coordinates for openings | Walls/windows out of sync |
| `lmo` that knows about daylight | Breaks the reuse of the solver, the heart of the architecture |
| Calibration set read during training | **False conformal guarantee, and nothing reports it** |
| Metric returning a bare scalar | Violates the "no value without uncertainty" principle |
| Mutation of a `Plan` | Types are frozen; working around it = bug |
| `np.quantile(scores, 0.90)` in conformal | Must be `ceil((n+1)*(1-α))/n` — finite-sample correction |
| LP without `depart=` in the FW loop | ×3 to ×5 time wasted |

---

## 11. Directory layout

Repository state (batch 1.8). French names are migrated batch by batch (ADR 0001); the
old public names remain as deprecated aliases until 1.0.0.

```
archlux/
├── pyproject.toml
├── src/archlux/
│   ├── __init__.py          # public interface ONLY
│   ├── _version.py          # single source of the version
│   ├── api.py               # legalize
│   ├── errors.py            # typed exceptions (`erreurs.py`: deprecated alias module)
│   ├── tolerances.py        # registry of numerical tolerances
│   ├── validation.py        # `validate_inputs`: InvalidInput at the door of legalize
│   ├── seeds.py             # named sub-seeds (`derive`), importable by every layer
│   ├── arrays.py            # `VecteurF`, the float64 array alias of the numerical core
│   ├── types.py
│   ├── geom/{graph,polytope,tiling,grid,grid_repair,rectilinear,diagnostic}.py
│   ├── lmo/{solver,cuts}.py
│   ├── solve/{frank_wolfe,trace}.py
│   ├── light/{protocol,analytic,learned,base,tokens,objective,split_flux,validation}.py
│   ├── orient/circular.py
│   ├── uq/{conformal,registry,drift,reliability}.py
│   ├── certify/{proof,farkas,bound,dual,report}.py
│   ├── feasibility/__init__.py
│   ├── active/{loop,densite,selection}.py
│   ├── data/{loaders,corruption,splits,dedup,imputation,synthetic}.py
│   ├── export/{ifc,dxf,svg,pathologies,survie,wilson}.py
│   ├── bench/{seeds,manifest,protocol,report,run,stats}.py
│   ├── io/json_io.py
│   └── …                    # French module names (`geom/pavage.py`, `lmo/coupes.py`,
│                            #   `certify/preuve.py`, …): deprecated shims (ADR 0001)
├── tests/{unites,proprietes,references,docs}/   # + checkers.py, test_dependencies.py,
│                                                #   test_hygiene.py, test_language.py
├── benchmarks/{test_budgets.py,guarantees/}
├── experiments/            # experiment scripts (milestones 2 to 9)
├── results/              # raw results and published tables
├── scripts/                # data preparation, labelling by the frozen oracle
└── splits/v1/              # frozen split
```

**Rule:** a script in `experiments/` longer than 50 lines signals a function
missing from the library. Since phase 2, 11 of 16 scripts comply; the five corpus
scripts that can only be checked against their data (`j7_sd_*`, `j8_*`, `j9_*`) do not
yet: known debt (PLAN.md phase 2). A script imports only public names: those of
`archlux.__all__` and the `__all__` of a documented module (`archlux.data.synthetic`,
`archlux.certify`, `archlux.uq.reliability`...), never a name starting with `_`, and
never another script. `python scripts/results.py` (or `make results`) runs them;
their outputs carry no timing, so `results/SHA256SUMS` fingerprints them.

---

## 12. Implementation order

| Milestone | Content | Deliverable |
|---|---|---|
| 1 | `types`, `io` | JSON round trip |
| **2** | **`geom`, `lmo`, `certify.proof`** | **classical legalization — see `MILESTONE-2.md`** |
| **3** | **`light.analytic`, `orient`, `solve`** | **performance legalization without learning — `MILESTONE-3.md`** |
| 4 | `light.learned`, `light.validation` | trained surrogate + gradient validation against `SplitFluxOracle` (split-flux closed form) — `MILESTONE-4.md` |
| 5 | `uq`, `certify.bound`, `certify.dual` | complete certificate — `MILESTONE-5.md` |
| 6 | L-shaped rooms (unions of rectangles), active, IFC export; **non-Manhattan is not delivered** (an oblique load-bearing wall raises `UnsupportedInput`) | `MILESTONE-6.md` |
