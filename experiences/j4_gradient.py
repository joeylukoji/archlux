"""Comparer analytique vs appris par le simulateur — jamais par le réseau."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SplitFluxOracle
from archlux.light.validation import valider_gradient
from archlux.types import Orientation

sim, rng = SplitFluxOracle(), np.random.default_rng(17)
xs, ys, os_ = [], [], []
for _ in range(36):
    c = float(rng.uniform(4.0, 8.0))
    x = np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])
    o = Orientation(float(rng.uniform(0.0, 360.0)))
    xs.append(x)
    os_.append(o)
    ys.append(sim.evaluer(x, o))
net = SubstitutDense()
net.ajuster(tuple(xs), np.array(ys), tuple(os_), seed=17, epoques=40, lr=0.12)
sud = Orientation(deg=180.0)
pts = np.stack([np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (5.0, 6.0, 7.0)])
rapport = valider_gradient(net, pts, sud, seed=17, reference=sim)
paires = zip(xs, os_, ys, strict=True)
mae_a = np.mean([abs(SubstitutAnalytique().evaluer(x, o) - y) for x, o, y in paires])
paires = zip(xs, os_, ys, strict=True)
mae_n = np.mean([abs(net.evaluer(x, o) - y) for x, o, y in paires])
Path("resultats/j4_gradient.md").write_text(
    f"# Jalon 4 — gradient\n\naccord_de_signe={rapport.accord_de_signe:.3f}\n"
    f"mae_analytique={mae_a:.4f}\nmae_reseau={mae_n:.4f}\n",
    encoding="utf-8",
)
print("accord", rapport.accord_de_signe, "mae", float(mae_a), float(mae_n))
