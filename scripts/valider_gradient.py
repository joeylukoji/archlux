"""Point de contrôle du gradient — `MILESTONE-4.md` §7. Assert bloquant."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SimulateurExact
from archlux.light.validation import valider_gradient
from archlux.types import Orientation

SIM, rng = SimulateurExact(), np.random.default_rng(17)
xs, ys, oris = [], [], []
for _ in range(36):
    c = float(rng.uniform(4.0, 8.0))
    x = np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])
    o = Orientation(deg=float(rng.uniform(0.0, 360.0)))
    xs.append(x)
    oris.append(o)
    ys.append(SIM.evaluer(x, o))
dense = SubstitutDense()
dense.ajuster(tuple(xs), np.array(ys), tuple(oris), seed=17, epoques=40, lr=0.12)
sud = Orientation(deg=180.0)
pts = np.stack(
    [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (5.0, 6.0, 7.0, 7.5)]
)
rapport = valider_gradient(dense, pts, sud, seed=17, reference=SIM)
assert rapport.accord_de_signe > 0.80, "NE PAS passer au jalon 5"
Path("resultats/j4_gradient.md").write_text(
    f"# Point de contrôle gradient\n\naccord_de_signe = {rapport.accord_de_signe:.3f}\n"
    f"cosinus_moyen = {rapport.cosinus_moyen:.3f}\nconforme = {rapport.conforme}\n",
    encoding="utf-8",
)
print("accord_de_signe", rapport.accord_de_signe)
