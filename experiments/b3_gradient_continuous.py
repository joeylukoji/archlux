"""B3 extended (AUDIT 2.1): sign agreement, Pearson / Spearman, mean angle and median
norm error of gradients against centred finite differences of the frozen split-flux
oracle (not physical), 8 azimuths x 3 amplitudes. Network and test plans of
``j4_gradient.py``; three-room strips scored with the analytic surrogate."""

import csv
import sys
from pathlib import Path

import numpy as np

from archlux.light.analytic import AnalyticSurrogate
from archlux.light.base import DenseSurrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.trust import gradient_agreement
from archlux.types import Orientation

SEED, OUT = 17, Path(sys.argv[1] if len(sys.argv) > 1 else "results") / "b3_gradient_continuous.csv"
oracle, rng = SplitFluxOracle(), np.random.default_rng(SEED)


def draw(n: int) -> tuple[list[np.ndarray], list[Orientation]]:
    xs = [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in rng.uniform(4, 8, n)]
    return xs, [Orientation(float(d)) for d in rng.uniform(0.0, 360.0, n)]


(train_x, train_o), (test_x, _) = draw(36), draw(80)
net = DenseSurrogate()
train_y = np.array([oracle.evaluate(x, o) for x, o in zip(train_x, train_o, strict=True)])
net.fit(tuple(train_x), train_y, tuple(train_o), seed=SEED, epochs=40, lr=0.12)
strips = [
    np.array([0, 0, a, 4.5, a, 0, b, 4.5, a + b, 0, 12 - a - b, 4.5], dtype=float)
    for a, b in rng.uniform(3, 4.5, (20, 2))
]
cases = (
    ("dense", "two_rooms", net, test_x[:20]),
    ("analytic", "two_rooms", AnalyticSurrogate(), test_x[:20]),
    ("analytic", "three_rooms", AnalyticSurrogate(), strips),
)
COLUMNS = ("sign_agreement", "pearson", "spearman", "mean_angle_deg", "median_norm_error")
with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(("surrogate", "typology", "azimuth", "step_m", "n_points", *COLUMNS))
    for name, typology, model, points in cases:
        for azimuth in range(0, 360, 45):
            for step in (0.02, 0.10, 0.50):
                o = [Orientation(float(azimuth))] * len(points)
                a = gradient_agreement(model, oracle, points, o, step=step)
                values = (f"{getattr(a, c):.4f}" for c in COLUMNS)
                writer.writerow((name, typology, azimuth, step, a.n_points, *values))
