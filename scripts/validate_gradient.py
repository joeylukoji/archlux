"""Gradient checkpoint — `MILESTONE-4.md` §7. Blocking assert."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from archlux.light.base import DenseSurrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.validation import validate_gradient
from archlux.types import Orientation

SIM, rng = SplitFluxOracle(), np.random.default_rng(17)
xs, ys, oris = [], [], []
for _ in range(36):
    c = float(rng.uniform(4.0, 8.0))
    x = np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])
    o = Orientation(deg=float(rng.uniform(0.0, 360.0)))
    xs.append(x)
    oris.append(o)
    ys.append(SIM.evaluate(x, o))
dense = DenseSurrogate()
dense.fit(tuple(xs), np.array(ys), tuple(oris), seed=17, epochs=40, lr=0.12)
south = Orientation(deg=180.0)
pts = np.stack([np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (5.0, 6.0, 7.0, 7.5)])
report = validate_gradient(dense, pts, south, seed=17, reference=SIM)
assert report.sign_agreement > 0.80, "do NOT go on to milestone 5"
Path("results/j4_gradient.md").write_text(
    f"# Gradient checkpoint\n\nsign_agreement = {report.sign_agreement:.3f}\n"
    f"mean_cosine = {report.mean_cosine:.3f}\npassed = {report.passed}\n",
    encoding="utf-8",
)
print("sign_agreement", report.sign_agreement)
