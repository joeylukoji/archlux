"""Gradient checkpoint — `MILESTONE-4.md` §7. Blocking, at **every** azimuth.

The former version asserted at south only, the one azimuth where the network passes
(``results/j4_gradient.csv``: 1.000 at 180 degrees, 0.50 to 0.68 elsewhere). A
checkpoint chosen where it passes checks nothing; this one exits non-zero if any of the
four cardinal azimuths is below 0.80, and writes all four values first.

The reference is the frozen split-flux oracle: a closed form, not a physical measure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from archlux.light.base import DenseSurrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.light.trust import DEFAULT_SIGN_THRESHOLD, gradient_agreement
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
pts = [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (5.0, 6.0, 7.0, 7.5)]
lines, failed = ["# Gradient checkpoint (reference: closed-form oracle)", ""], []
for deg in (0.0, 90.0, 180.0, 270.0):
    a = gradient_agreement(dense, SIM, pts, [Orientation(deg)] * len(pts), step=0.10)
    lines.append(f"azimuth {deg:g}: sign_agreement = {a.sign_agreement:.3f}, "
                 f"mean_cosine = {a.mean_cosine:.3f}")  # fmt: skip
    if not a.sign_agreement >= DEFAULT_SIGN_THRESHOLD:
        failed.append(deg)
lines.append(f"passed = {not failed}")
Path("results/j4_gradient.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
if failed:
    sys.exit(f"do NOT go on to milestone 5: below {DEFAULT_SIGN_THRESHOLD} at {failed}")
