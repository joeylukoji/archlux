# archlux

> **Repair a generated floor plan into a geometrically valid one while keeping its
> daylight. Geometry is proved; daylight is bounded.**

[![CI](https://github.com/ORG/archlux/actions/workflows/ci.yml/badge.svg)](https://github.com/ORG/archlux/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

**Where it works, and where it does not.** archlux repairs plans that are *almost*
right. On 4,796 corruptions of 300 real apartments (MSD corpus: gaps, overlaps,
undersized and shifted rooms), it returns a certified valid plan in **93.9 %** of cases
(95 % CI [93.2, 94.5], tiling mode with fallback; `resultats/j7_reparation.md`). On raw
outputs of a generative model (HouseDiffusion, 740 plans, none valid at the start), it
returns an intact certified plan in only **about 20 %** of cases (17.8 % to 23.0 %
across three sets; `resultats/j8_generation.md`): four plans out of five are too far
from any exact tiling to be repaired without losing a room. Post hoc legalization does
not replace a generator that respects the tiling condition. Both figures predate the
load-bearing wall constraints of batch 1.1 and will be measured again (PLAN.md, J7 and
J8).

The project is in development (`0.10.0.dev0`, no release yet). The public API is still
partly French; it is being migrated to English ([ADR 0001](docs/adr/0001-english-first.md),
[glossary](docs/glossary.md)).

---

## Contents

- [The problem](#the-problem)
- [What archlux does](#what-archlux-does)
- [Installation](#installation)
- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [The two guarantees](#the-two-guarantees)
- [The certificate](#the-certificate)
- [Architecture](#architecture)
- [Data](#data)
- [Daylight indicators](#daylight-indicators)
- [Performance](#performance)
- [Scientific context](#scientific-context)
- [Roadmap](#roadmap)
- [Reproducibility](#reproducibility)
- [Limitations](#limitations)
- [Documentation](#documentation)
- [Citing](#citing)

---

## The problem

Generative models (diffusion, transformers, language models) now produce plausible
apartment plans, but only *almost* valid ones: two partitions overlap by three
centimetres, a two-centimetre gap is left between two rooms, a bathroom has 4.6 m²
where 5 m² are required. This is structural: these models treat geometric validity as
a penalty in a loss, and a finite penalty never brings the probability of an invalid
output to zero.

The repair has a name, inherited from integrated circuit design where it has been
studied since the 1980s: **legalization**, usually stated as "among all valid layouts,
take the closest to the proposal". In circuit design, closeness is a sound proxy: the
rough placement minimized wire length, and moving away from it degrades it. In
architecture, the rough plan comes from a model that imitates a corpus; closeness to it
is a proxy for nothing. Around an invalid proposal there is a whole continuum of valid
plans, and two corrections of similar size can differ widely in the daylight they give.

Building physics has the opposite difficulty. Annual daylight needs ray tracing
(minutes to hours per plan), so the field uses **surrogate models** that predict
indicators from geometry. They are used to rank designs, rarely to optimize under
constraints: an optimizer exploits the errors of its estimator, and a daylight
objective without geometric constraints produces absurd rooms.

Each side supplies what the other lacks: legalization needs an objective, the surrogate
provides one; the surrogate needs a domain of validity, legalization provides one. A
bound on how far walls move is also a bound on how far the surrogate extrapolates.

---

## What archlux does

`archlux` takes a proposed plan and returns a **valid** plan with a **certificate** that
separates what is proved from what is predicted.

| Function | Input | Output |
|---|---|---|
| **Classic legalization** | Invalid plan | Closest valid plan (L1) + exact proof |
| **Performance legalization** | Invalid plan + orientation + surrogate | Valid plan improved for the surrogate + exact proof (+ a bound in the *selected* regime if a calibration is given) |
| **Infeasibility detection** | Program + outline | Verdict + Farkas certificate naming the conflicting constraints, *for the relative order read from the proposal* |
| **Dual diagnosis** | — | Active constraints with their local unit price |
| **Verification only** | Hand-drawn plan | Exact geometric proof, no learned model involved |

**What archlux does not do:** generate plans, or simulate daylight. Plans come from
generative models or architects; daylight comes from a surrogate you supply, checked
against an oracle you choose.

---

## Installation

```bash
pip install archlux                 # core: geometry, solver, certificate
pip install "archlux[ml]"           # + PyTorch, reserved for a learned surrogate (not shipped yet)
pip install "archlux[bim]"          # + IFC export (ifcopenshell)
```

The package is not on PyPI yet: install from a clone with `pip install -e ".[dev]"`.
The `sim` and `stats` extras exist but are empty.

**The core never imports PyTorch**, and a test checks it (`tests/test_dependances.py`).
Core dependencies: `numpy`, `scipy`, `shapely`, `networkx`, `ortools`, `structlog`.

---

## Quick start

Every Python block of this page is executed by the test suite
(`tests/docs/test_examples.py`), in order, in one namespace.

### Repair a plan

Three rooms in a 12 m × 9 m outline, with a load-bearing wall at x = 6 m. The living
room crosses the wall by 5 cm and a 3 cm gap separates the bedroom from the bathroom.
Room types are free strings; `Referentiel` gives the minimum area per type and the
minimum width.

```python
import archlux as ax

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    pieces=(
        ax.Piece(id="living", type="living", x=0.0, y=0.0, w=6.05, h=9.0),
        ax.Piece(id="bed", type="bedroom", x=6.0, y=0.0, w=6.0, h=5.0),
        ax.Piece(id="bath", type="bathroom", x=6.0, y=5.03, w=6.0, h=3.97),
    ),
    murs=(),
    ouvertures=(),
    contour=outline,
)
ctx = ax.Contexte(
    structure=ax.Structure(
        murs_porteurs=(ax.Mur(id="axis-3", a=(6.0, 0.0), b=(6.0, 9.0), porteur=True),)
    ),
    orientation=ax.Orientation(deg=12.0),  # north at 12 degrees east
    contour=outline,
    referentiel=ax.Referentiel(aires_min=(("bathroom", 5.0),), largeur_min=1.0),
)

repaired = ax.legalize(plan, ctx, pavage=True)
assert repaired.certificat is not None and repaired.certificat.geometrie.valide
print(repaired.certificat.rapport())
```

`pavage=True` requires the rooms to tile the outline exactly. Use it whenever the input
may contain a gap, which is the case of generator outputs: without it, the separations
are inequalities, a plan with a gap is already the closest point to itself, and the
exact check then rejects it (`InvariantViole`). If the tiling grid cannot be recovered
from the proposal, `legalize` raises `GridNotRecoverable`, naming the cells.

Plans round-trip through JSON with their certificate:

```python
repaired.to_json("repaired.json")
again = ax.Plan.from_json("repaired.json")
assert again.certificat is not None and again.certificat.geometrie.valide
```

### Repair while keeping the daylight

One argument changes: `objective`. Here the objective is the analytic surrogate,
wrapped in `Daylight`, which maximizes the pessimistic value `mu - q sigma`. A
`calibration` makes the certificate carry a conformal interval; it is computed against
`OracleSplitFlux`, the frozen closed-form oracle of the CI (a split-flux daylight
factor, not a simulation).

```python
import numpy as np

from archlux.light import Daylight, OracleSplitFlux, SubstitutAnalytique
from archlux.uq.conforme import CalibrateurConforme

surrogate, oracle = SubstitutAnalytique(), OracleSplitFlux()
rng = np.random.default_rng(17)
held_out = []  # layouts of the same three rooms, never used to fit the surrogate
for _ in range(200):
    w, h = rng.uniform(4.0, 8.0), rng.uniform(3.0, 6.0)
    held_out.append(np.array([0, 0, w, 9, w, 0, 12 - w, h, w, h, 12 - w, 9 - h], float))

azimuth = ctx.orientation
calibrator = CalibrateurConforme(indicateur="sDA")
calibrator.ajuster(
    np.array([surrogate.evaluer(x, azimuth) for x in held_out]),
    np.array([oracle.evaluer(x, azimuth) for x in held_out]),
    np.array([surrogate.incertitude(x, azimuth) for x in held_out]),
    alpha=0.10,
)

better = ax.legalize(
    plan,
    ctx,
    objective=Daylight(surrogate, q_chapeau=calibrator.q),
    calibration=calibrator.snapshot(),
    budget=0.5,  # maximum displacement from the proposal, in metres, checked by the proof
    pavage=True,
)
bound = better.certificat.performance
assert bound is not None and bound.regime == "selected"
assert not bound.coverage_guaranteed  # the optimizer chose this plan
```

The geometry of `better` is proved exactly, like before. Its daylight bound is not a
guarantee: the plan was **selected** by the optimizer, so it sits where the surrogate
is most optimistic, and the nominal 90 % coverage no longer holds (winner's curse). The
report says so:

```text
PERFORMANCE                        [PREDICTION — plan selectionne, couverture NON garantie]
```

A guaranteed coverage needs a plan exchangeable with the calibration set, for instance
a held-out plan bounded with `calibrator.borne(prediction, sigma, regime="exchangeable")`.
In this example the interval is also wide: the analytic surrogate misses the split-flux
term of the oracle, and the calibration reports that error instead of hiding it.

### Detect an infeasible program

Three rooms side by side, each at least 4.5 m wide, in a 12 m wide outline:

```python
narrow = ax.Plan(
    pieces=tuple(
        ax.Piece(id=name, type="bedroom", x=4.0 * k, y=0.0, w=4.0, h=9.0)
        for k, name in enumerate("abc")
    ),
    murs=(),
    ouvertures=(),
    contour=outline,
)
wide_rooms = ax.Contexte(
    structure=ax.Structure(murs_porteurs=()),
    orientation=ax.Orientation(deg=0.0),
    contour=outline,
    referentiel=ax.Referentiel(aires_min=(), largeur_min=4.5),
)
verdict = ax.feasibility.is_feasible(narrow, wide_rooms.structure, wide_rooms)
assert not verdict and verdict.certificat is not None
print(verdict.certificat.expliquer())
```

```text
Infeasible for this relative order: conflicting constraints [separation horizontale a|b, separation horizontale b|c, contour droit c]. Certificate verified exactly.
```

The verdict is about the relative order read from the proposal (a left of b left of c):
another order might fit. The Farkas certificate is checked in exact rational
arithmetic; when it cannot be (for instance when the conflict involves minimum-area
cuts, which are not rows of the polytope), the message says "Certificate NOT verified:
treat as a solver diagnosis, not a proof". `legalize` raises `Infaisable` with the same
information (`origines`, `certificat_farkas`, `verified`).

Generative models always return something, even when the request is impossible, and
the result is then wrong somewhere without any warning. archlux refuses and says why.

---

## How it works

### The division of labour

> The generator decides the **order** of the rooms.
> The solver decides the **dimensions**.
> The surrogate only provides a **direction**.

### Step 1: the polytope

"Room A is left of room B" means that A ends before B starts: `x_A + w_A <= x_B`. With
one such separation per pair of rooms, overlap becomes impossible by construction, not
discouraged by a penalty. The order is read from the proposed plan
(`geom.graphe.deduire_ordre`), and each room is also kept on its side of every
load-bearing wall.

Minimum areas (`w h >= a`) are not linear but define a convex set. The classic mode
adds **tangent cuts** on demand (Kelley's method): a tangent is an *outer*
approximation, so a cut alone does **not** guarantee the area (around `w = h = 3`, the
cut `3w + 3h >= 18` accepts `w = 5.9, h = 0.1`, whose area is 0.59 m²). The loop adds
cuts until the exact check passes, and the proof then checks every area. The
performance mode instead uses an *inner* approximation (chords of the hyperbola around
the start, `lmo.coupes.inner_area_constraints`), so that every iterate keeps every
minimum area. See `docs/formules/coupes-surface.md`.

### Step 2: one solver, two objectives

The performance problem maximizes a smooth function over a convex compact set, which
is the setting of the **Frank-Wolfe** algorithm: take the gradient given by the
surrogate, ask "which valid plan goes furthest in this direction?", move a step toward
it, repeat. That question is a linear program over the same polytope as classic
legalization. The same solver (`lmo`) serves both modes; only the cost vector changes
(pseudo-code):

```text
classic legalization:      x = lmo(polytope, c = L1 distance to the proposal)
one Frank-Wolfe iteration: x = lmo(polytope, c = -gradient of the surrogate, warm start)
```

Consequences, stated with their limits:

- **Every Frank-Wolfe iterate is a valid plan** since batch 1.2 (inner area
  approximation; a property test checks every iterate with an independent checker).
  The returned plan is re-verified exactly anyway.
- **The Frank-Wolfe gap is a stationarity measure, not a distance to the optimum.** It
  bounds the suboptimality only for a concave objective, and no shipped surrogate is
  concave. `Trace.status` says why the run stopped (`converged`, `max_iter`, ...).
- **The displacement budget is spent once**, over the classic pass and Frank-Wolfe
  together, and the proof rejects a plan moved beyond it.

### Step 3: the surrogate

A surrogate implements the `Substitut` protocol: `evaluer` (value), `gradient`,
`incertitude` (sigma), each taking the decision vector `(x, y, w, h)` per room, an
azimuth, and the glazing (`baies`). Shipped implementations:

| Class | What it is |
|---|---|
| `SubstitutAnalytique` | Closed-form rules (CIBSE depth rule, sector factor), no learning |
| `OracleSplitFlux` | Analytic part + BRE split-flux daylight factor: the **frozen oracle** of the CI, used to test the chain end to end. A closed form, not a simulation and not ground truth |
| `light.base.SubstitutDense` | Three-layer perceptron, numpy weights, trained on the residual to the analytic form |
| `light.appris.SubstitutAppris` | Loads numpy weights; **PyTorch `.pt` weights are refused**: the token transformer is not implemented |
| `Daylight` | Wraps a surrogate and returns the pessimistic value `mu - q sigma` |

The input is a set of numbers per room, not an image: moving a wall by 2 cm changes no
pixel of a coarse image, so an image-based gradient is zero almost everywhere.
Openings are stored relative to their wall (`Ouverture.mur_id`, relative abscissa
`s`); their absolute position is never stored. The solver moves rooms, never walls, and
the glazing is passed unchanged to the surrogate during the optimization.

Read [`docs/donnees/verite-terrain.md`](docs/donnees/verite-terrain.md) before quoting
any daylight figure: the shipped labels come from a closed form, not from a measured
or simulated physical quantity.

### Step 4: the conformal margin

A prediction without a margin cannot go into a certificate. archlux uses **split
conformal prediction**: on a calibration set never seen in training, compute the
normalized errors `|y - mu| / sigma`, take their finite-sample quantile
`ceil((n + 1)(1 - alpha)) / n`, and publish `mu +/- q sigma`. For a plan
**exchangeable** with the calibration set, the coverage is at least `1 - alpha`, with no
assumption on the data distribution or on the model. The shipped splits (`splits/v1`)
hold 18 calibration plans: enough to exercise the mechanism, not to publish a figure.

`Daylight` optimizes `mu - q sigma`, so a surrogate whose sigma grows away from its
training data would steer the optimizer back. **The shipped surrogates return a
constant sigma**, so this safeguard is inactive with them: the margin has the same
width everywhere.

### Step 5: the dual diagnosis

The LP also returns a price per constraint: how much the objective would improve if
the constraint were relaxed by one unit. The certificate lists the active constraints
with that price (local validity only). In performance mode the list is often empty:
contacts are frozen into equalities, which are not dualized. Translating prices into
daylight points ("this load-bearing wall costs 4 points of sDA") is on the roadmap.

---

## The two guarantees

This is the core of the project, and the two must never be confused.

| | Geometric | Daylight |
|---|---|---|
| **Nature** | Exact, a proof about the model | Probabilistic |
| **Statement** | "these rectangles do not overlap, tile the outline, meet the minimum areas, stay on their side of load-bearing walls, move at most `budget`" | "the oracle value lies in this interval" |
| **Checked by** | `certify.proof.verify_exactly`, after the solver, never trusting it | Split conformal prediction on a calibration set |
| **Assumptions** | Rooms are axis-aligned rectangles (or rectangles fused into L-shapes); outline and walls as given | Exchangeability with the calibration set (`regime="exchangeable"`) |
| **Can it be wrong?** | Only through its declared tolerances: exact rational arithmetic on axis-aligned rectangular outlines, edges closer than 1e-7 m identified (`SNAP_M`); floating-point GEOS checks with area tolerances on other outlines | Yes, in at most alpha of the cases for an exchangeable plan; **no guarantee at all** for a plan chosen by the optimizer (`regime="selected"`) |

- **Geometry, exact.** On an axis-aligned rectangular outline, overlaps and gaps are
  decided in rational arithmetic (`certify.proof.rational_tiling`; theorem and proof in
  `docs/formules/preuve-exacte.md`). The only tolerance is the identification of edges
  closer than `SNAP_M`, and the raw plan is bounded as well so that this identification
  cannot accept a plan the floating-point check would reject. Other outlines use GEOS
  with the tolerances of `archlux/tolerances.py`. Infeasibility is proved by a Farkas
  certificate verified in exact arithmetic, and only for the relative order read from
  the proposal.
- **Daylight, probabilistic.** `BornePerformance.regime` is mandatory.
  `"exchangeable"`: the plan is exchangeable with the calibration set, and the coverage
  is guaranteed. `"selected"`: the optimizer chose the plan, the coverage is **not**
  guaranteed, and the report says "couverture NON garantie". `legalize(...,
  calibration=...)` always gives `"selected"`. Without `calibration`,
  `certificat.performance` is `None`. The bound is about the oracle the calibration was
  computed against (here the frozen split-flux oracle), never about a measured LM-83
  sDA.

The two are **distinct types**: `PreuveGeometrique` has no probability field,
`BornePerformance` always carries its coverage, calibration size and regime. See
[`docs/concepts/deux-garanties.md`](docs/concepts/deux-garanties.md).

---

## The certificate

Every plan returned by `legalize` carries its certificate. The report of the quick
start plan reads (the report text is still in French):

```text
CERTIFICAT                              archlux 0.10.0.dev0

GEOMETRIE                                       [EXACT]
  Chevauchement          aucun         verifie
  Jours                  aucun         verifie
  Surfaces minimales     ok            verifie
  Structure preservee    oui           verifie
  Deplacement maximal    0,05 m
```

It then prints the daylight section (`[PREDICTION — couverture 90 %]` for an
exchangeable plan, `couverture NON garantie` for a selected one, `NON EVALUABLE`
without calibration), the dual diagnosis, and an out-of-scope section (summer comfort,
building services, materials). "Structure preservee" is checked since batch 1.1: no
room interior contains a stretch of a load-bearing wall. The maximum displacement is a
checked predicate when a `budget` is given. `Certificat.manifeste` is `None` unless the
caller attaches one.

---

## Architecture

```text
INPUT: proposed plan, load-bearing structure, orientation, program
   |
   v
[1] geom      relative order -> polytope (A, b)               deterministic
   |
   +------------------+---------------------------+
   v                  v                           v
[2a] lmo   LP solver, any cost vector     [2b] light   surrogate
           (GLOP model cache)                  value / gradient / sigma
   |                  |                           |
   +------------------+-------> [3] solve  Frank-Wolfe        deterministic
                                      |
                                      v
                                [4] certify  proof + bound + duals
                                      |
                                      v
                OUTPUT: valid plan + certificate + dual diagnosis
```

Every layer is deterministic: same inputs, same outputs. `lmo` is not pure in the
strict sense: it keeps a small module-level cache of solver models (at most four) to
warm-start Frank-Wolfe; the cache changes timing, never results
(`lmo.solveur.vider_cache` empties it). `lmo` receives a cost vector and does not know
whether it comes from a distance or from a daylight gradient: this is what lets one
solver serve both modes.

| Module | Responsibility |
|---|---|
| `types` | `Plan`, `Piece`, `Mur`, `Ouverture`, `Contexte`, `Certificat` |
| `geom` | relative order, load-bearing sides, tiling grid, polytope, L-shaped fusions |
| `lmo` | solve `min <c, x>` over the polytope, area cuts; ignores where `c` comes from |
| `solve` | Frank-Wolfe, warm start, trace |
| `light` | `Substitut` protocol and its implementations |
| `orient` | circular encoding of the azimuth |
| `uq` | conformal calibration, drift control, calibration-set access token |
| `certify` | exact proof, Farkas check, conformal bound, dual translation, report |
| `feasibility` | feasibility verdict, no daylight |
| `active`, `data`, `export`, `bench`, `io` | active learning, corpus loaders, IFC/DXF/SVG export, evaluation protocol, JSON |

Details and dependency rules: [`ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md).

---

## Data

`archlux` redistributes no corpus. The repository ships a deterministic synthetic
generator (90 tilings of 2 × 2 rooms) used by the CI, and documents the ingestion of
public data sets.

| Corpus | What it brings | Licence | Access |
|---|---|---|---|
| **[Swiss Dwellings](docs/donnees/swiss-dwellings.md)** | geometry and simulated sun, view and noise per room (45,000 apartments) | CC BY 4.0 | [doi:10.5281/zenodo.7788422](https://doi.org/10.5281/zenodo.7788422) |
| **[MSD](docs/donnees/msd.md)** (Modified Swiss Dwellings) | annotated load-bearing walls and columns, cardinal orientation kept; many plans are not rectilinear | CC BY-SA 4.0 | [arXiv:2407.10121](https://arxiv.org/abs/2407.10121) |
| **[CubiCasa5K](docs/donnees/cubicasa.md)** | annotated doors and windows, vector SVG | research, non-commercial | [github.com/CubiCasa/CubiCasa5k](https://github.com/CubiCasa/CubiCasa5k) |
| **RPLAN** | 80,000 plans, comparability with the vision literature | on request | [project page](http://staff.ustc.edu.cn/~fuxm/projects/DeepLayout/index.html) |

The MSD loader (`data.chargeurs`) keeps only axis-aligned plans with a simple outline:
in the J7 run, 143 apartments were rejected for oblique geometry and 240 for a
non-simple outline.

**Three splits, not two.** Training (60 %), calibration (20 %, never seen in training)
and test (20 %, opened once). If the calibration set leaks into training, the coverage
guarantee is silently wrong, and no test or review would notice. `uq.gestion` keeps
three distinct directories and hands out the calibration set against a token issued
after the model is frozen. This is a checkable discipline, not a lock: the token is an
unkeyed checksum, and `CalibrateurConforme` calibrates from plain arrays without asking
for it (the module docstring lists the known bypasses).

---

## Daylight indicators

| Indicator | Definition | Direction |
|---|---|---|
| **sDA(300/50%)** | share of the floor above 300 lux for at least 50 % of occupied hours | higher is better |
| **ASE(1000,250h)** | share of the floor receiving more than 1,000 lux of direct sun for more than 250 h a year | lower is better |
| **UDI** | share of time with illuminance in a useful range | neither too dark nor too bright |
| **View** | visual opening from occupied areas | well-being |

These are the target indicators. **The shipped oracle does not compute them**: the
value named `sDA` in the examples is a split-flux score in composite units (m² times
percent), not an LM-83 sDA. sDA and ASE pull in opposite directions; exploring their
trade-off is on the roadmap. The orientation is a **circular variable**, encoded as
(cos, sin) harmonics, so that 359° and 1° are close.

---

## Performance

Budgets from [`ARCHITECTURE.md` §9](docs/specification/ARCHITECTURE.md), measured by
`benchmarks/test_budgets.py` (CI job `budgets`, `pytest -m budget --benchmark-only`):

| Operation | Budget | Measured on |
|---|---|---|
| Polytope construction | < 5 ms | 15 rooms, valid 5 × 3 grid |
| Cold LP call | < 10 ms | same |
| Warm LP call | < 3 ms | same |
| **Classic legalization** | **< 20 ms** | same |
| **Performance legalization** | **< 500 ms** | same, 50 iterations max; also with tight minimum areas |
| Certification | < 5 ms | 15 rooms |

The budgets are measured on an already valid grid, without tiling or load-bearing
walls; they do not cover noisy inputs. For those, the guarantee benchmark
([`benchmarks/guarantees/README.md`](benchmarks/guarantees/README.md)) records a median
of about 5 ms per plan in classic mode and 15 to 20 ms in performance mode, on 200
scenarios per mode, with **0 false certificates** in every mode. It also shows the
limit of the classic mode: when every coordinate is moved by up to 3 cm, 199 plans out
of 200 are refused (safely, with a typed error), not repaired. A daylight simulation
takes minutes to hours; the ratio is what makes surrogate-guided legalization practical.

---

## Scientific context

Three literatures that do not read each other: legalization and placement (electronic
design automation), environmental surrogates (building physics) and plan generation
(computer vision). What this project adds:

- **Legalization with a physical objective**, instead of closeness to the proposal.
- **Two guarantees of different natures produced together**, with the regime of the
  probabilistic one stated.
- **An infeasibility certificate**, verified exactly: a system that refuses and
  explains, rather than returning a wrong plan.
- **A dual diagnosis** of the active constraints.

Founding references:

- Moffitt M. D., Ng A. N., Markov I. L., Pollack M. E. (2008). *Constraint-Driven
  Floorplan Repair*. ACM TODAES.
- Murata H., Fujiyoshi K., Nakatake S., Kajitani Y. (1996). *VLSI Module Placement Based
  on Rectangle-Packing by the Sequence-Pair*. IEEE TCAD.
- Lacoste-Julien S., Jaggi M. (2015). *On the Global Linear Convergence of Frank-Wolfe
  Optimization Variants*. NeurIPS.
- Vovk V., Gammerman A., Shafer G. (2005). *Algorithmic Learning in a Random World*.
- Shabani M. A., Hosseini S., Furukawa Y. (2023). *HouseDiffusion*. CVPR.
- van Engelenburg C. et al. (2024). *MSD: A Benchmark Dataset for Floor Plan Generation
  of Building Complexes*. ECCV.

---

## Roadmap

Done, with the limits stated above: JSON round trip; classic legalization with exact
proof; performance legalization with the analytic surrogate; numpy perceptron checked
against the frozen oracle; conformal bound with its regime; Farkas certificates; L-shaped
rooms fused from rectangles (`legalize(..., fusions=...)`); active learning loop; IFC
export; MSD loader.

Not implemented yet:

| Feature | Status |
|---|---|
| **Non-Manhattan geometry** (oblique walls, non-rectilinear rooms) | Not supported. An oblique load-bearing wall raises `UnsupportedInput`; oblique MSD plans are rejected by the loader |
| **sDA / ASE trade-off curve** (Pareto front with warm restarts) | No code |
| Learned token transformer (PyTorch) | Not implemented: `SubstitutAppris` refuses `.pt` weights |
| Daylight labels from a physical simulation (Swiss Dwellings `sun_*`, Radiance) | Not wired; the CI oracle is a closed form |
| Coverage measured on real data, and on plans selected by the optimizer | Open research question (PLAN.md, J5) |
| Dual prices translated into daylight points | Prices are listed in LP units |
| `bench.compare` with intervals | It returns bare means; use `bench.report` for tables |
| English public API and report | In progress (ADR 0001, track E) |

The development plan is [`PLAN.md`](PLAN.md); the audit it answers is
[`AUDIT.md`](AUDIT.md) (both in French).

---

## Reproducibility

`archlux.bench.emettre(seed=...)` builds a **manifest**: version, UTC timestamp, seed,
data fingerprint, split, environment versions, parameters, model fingerprint and
calibration size. `legalize` itself does not attach one. Format example (illustrative
values):

```json
{
  "version": "0.10.0.dev0",
  "horodatage": "2026-08-27T14:32:11Z",
  "graine": 17,
  "empreinte_donnees": "sha256:9c2f...",
  "decoupage": "splits/v1",
  "environnement": [["numpy", "2.1.0"], ["ortools", "9.8.3296"], ["python", "3.12.4"]],
  "parametres": [["budget", "0.25"], ["max_iter", "50"]],
  "modele": {"poids": "sha256:4a1b...", "calibration_n": 18, "alpha": 0.1}
}
```

- Every sampling function takes a **seed, with no default**.
- Splits are **frozen and published** as lists of identifiers.
- Raw results are published **before** any aggregation (`resultats/*_brut.csv`).
- **The calibration set is published with the model**: without it, a conformal bound
  cannot be checked.
- Any change in the behaviour of the oracle or of the certificate is a **major
  version**.

---

## Limitations

Read before any professional use. Full version (in French):
[`docs/limites.md`](docs/limites.md).

- Daylight figures are **early-design estimates** against a frozen closed-form oracle.
  They replace no regulatory daylight or thermal study.
- The daylight bound assumes exchangeability with the calibration set. Plans produced
  by the optimizer are *selected*: their coverage is not guaranteed, and the
  certificate says so.
- Rooms are axis-aligned rectangles (L-shapes through fusions). Oblique geometry is not
  supported.
- Infeasibility is proved for the relative order of the proposal, not for every
  possible layout.
- On raw generator outputs, most plans cannot be repaired without losing a room (see
  the first paragraph).
- The geometric check computes predicates on a model of the plan. **It is not legal
  advice** and replaces no licensed professional.

> **A plan produced by this system is a proposal, never a construction document.
> Design responsibility remains with a licensed professional.**

---

## Documentation

The documentation site is still in French (translation: PLAN.md, track E22).

| | |
|---|---|
| [Gallery](docs/galerie/) | Worked examples |
| [Tutorials](docs/tutoriels/) | Guided walkthroughs |
| [Concepts](docs/concepts/) | The why rather than the how |
| [API reference](docs/reference/) | Signatures |
| [Limitations](docs/limites.md) | What the system does not do |
| [Glossary](docs/glossary.md) | French and English names |
| [`ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md) | For contributors |

A shorter French version of this page: [`README.fr.md`](README.fr.md).

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md), and read
[`ARCHITECTURE.md`](docs/specification/ARCHITECTURE.md) first: the dependency rules are
binding and checked automatically. In particular, `geom`, `lmo`, `solve` and `certify`
never import `torch`. A public function without a docstring is not finished.

---

## Citing

```bibtex
@software{archlux,
  title   = {archlux: geometric legalization of generated floor plans
             with conformally bounded daylight surrogates},
  year    = {2026},
  url     = {https://github.com/ORG/archlux},
  version = {0.10.0.dev0}
}
```

Cite a tagged version, never "the repository": a certificate must stay traceable to an
exact version of the library and of its calibration. See also
[`CITATION.cff`](CITATION.cff). No version has been released yet.

---

## Licence

Apache 2.0, see [`LICENSE`](LICENSE).
