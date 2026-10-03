# Train a surrogate

The learned surrogate enters `legalize` **only** if it follows the vector
protocol and if its gradient is validated against the frozen oracle (`SplitFluxOracle`,
BRE split-flux; (Radiance) off the critical path).

The blocks of this page run in order, as is. The sizes are
reduced to run in a few seconds (80 plans, 8 neurons, 30 epochs): the
chain is complete, the resulting model is only a toy.

## 1. A plan, and layouts to learn from

The plan to repair is the one of [getting started](getting-started.md): three rooms in
a 12 m × 9 m envelope, a 5 cm overlap and a 3 cm gap. The surrogate only
sees a vector `[x, y, w, h]` per room; `layout` draws valid variants
of the same three rooms.

```python
from pathlib import Path

import numpy as np

import archlux as ax

outline = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
plan = ax.Plan(
    rooms=(
        ax.Room(id="living_room", type="living_room", x=0.0, y=0.0, w=6.05, h=9.0),
        ax.Room(id="bedroom", type="bedroom", x=6.0, y=0.0, w=6.0, h=5.0),
        ax.Room(id="bathroom", type="bathroom", x=6.0, y=5.03, w=6.0, h=3.97),
    ),
    walls=(),
    openings=(),
    outline=outline,
)
ctx = ax.Context(
    structure=ax.Structure(load_bearing_walls=()),
    orientation=ax.Orientation(deg=12.0),
    outline=outline,
    regulation=ax.Regulation(min_areas=(("bathroom", 5.0),), min_width=1.0),
)


def layout(rng: np.random.Generator) -> np.ndarray:
    """Living room on the left, bedroom and bathroom stacked on the right."""
    w, h = rng.uniform(4.0, 8.0), rng.uniform(3.0, 6.0)
    return np.array([0, 0, w, 9, w, 0, 12 - w, h, w, h, 12 - w, 9 - h], dtype=float)
```

## 2. Train, save, freeze

```python
from archlux.light.base import DenseSurrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.uq.registry import issue_token

sim = SplitFluxOracle()
rng = np.random.default_rng(17)
# xs, ys, orientations: training set only — never the calibration set
xs = tuple(layout(rng) for _ in range(80))
orientations = tuple(ax.Orientation(deg=float(d)) for d in rng.uniform(0.0, 360.0, len(xs)))
ys = np.array([sim.evaluate(x, o) for x, o in zip(xs, orientations, strict=True)])

dense = DenseSurrogate(largeur=8)
dense.fit(xs, ys, orientations, seed=17, epoques=30)
Path("weights").mkdir(exist_ok=True)
path = Path("weights/dense.npz")
fingerprint = dense.save(path)
token = issue_token(fingerprint, "2026-09-09T10:00:00Z")  # after the freeze
```

`save` returns the SHA-256 fingerprint of the written file; the token binds it to the
moment of the freeze. It is the token that will open the calibration set in the
[next tutorial](calibrate-a-surrogate.md).

## 3. Validate the gradient, then legalize

```python
from archlux.light.learned import LearnedSurrogate
from archlux.light.validation import validate_gradient

network = LearnedSurrogate(path, fingerprint, gele=True)
points = np.stack([layout(rng) for _ in range(8)])
report = validate_gradient(network, points, ctx.orientation, seed=17, reference=sim)
assert report.accord_de_signe > 0.80

q = ax.legalize(plan, ctx, objective=network, budget=0.5, tiling=True)
assert q.certificate is not None and q.certificate.geometry.valid
```

!!! danger "Checkpoint reopened (phase 2 review)"
    This example measures sign agreement at **one** orientation. Replayed on 80 points at
    four azimuths, the perceptron fails at 0°, 90° and 270° (0.68 / 0.50 / 0.67), as
    does the untrained analytic surrogate: see [the milestone 4 review](../revues/j4.md).
    Passing this check here does not say that the gradient is usable.

`validate_gradient` raises `InvalidSurrogate` below the sign-agreement threshold (0.80):
the `assert` only makes the checkpoint visible. `budget=0.5` bounds the
displacement of each wall to 50 cm around the proposal; without it, Frank-Wolfe
follows the surrogate as far as the polytope allows: in this example, it shrinks
the living room to 1 m, the minimum width.

`torch` is loaded only for a `.pt` file. CI trains the numpy
perceptron (`light.base`).

!!! warning "The transformer is not implemented"
    `LearnedSurrogate._charger_torch` **always raises**: the
    `archlux[ml]` extra installs `torch`, but no `.pt` model is served. The only
    learned implementation in the repository is the `numpy` perceptron above.

!!! danger "Where do `xs`, `ys`, `orientations` come from?"
    Here, as in the repository, `ys` comes from `SplitFluxOracle` — a **closed form**.
    The perceptron then learns the residual between two analytic formulas: the chain
    is exercised, the physics is not measured. For real labels, read
    [ground truth](../data/ground-truth.md): Swiss Dwellings (CC BY 4.0,
    367 simulation columns per room) or a Radiance campaign.

The calibration set is **not** opened here. See
[calibrate a surrogate](calibrate-a-surrogate.md) (milestone 5).

Formulas: [tokens](../formulas/tokens.md),
[gradient validation](../formulas/gradient-validation.md).
[Why not an image](../concepts/why-not-an-image.md).
