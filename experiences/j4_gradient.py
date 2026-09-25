"""Gradient checkpoint of milestone 4, replayed as written (PLAN.md phase 2): MAE on a
held-out TEST set, sign agreement on 80 points at four azimuths. Control: the untrained
analytic surrogate takes the same checkpoint; if it passes, it does not measure learning.
"""

import csv
import sys
from pathlib import Path

import numpy as np

from archlux.erreurs import SubstitutInvalide
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SplitFluxOracle
from archlux.light.validation import valider_gradient
from archlux.types import Orientation

SEED = 17
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "resultats") / "j4_gradient.csv"
oracle, rng = SplitFluxOracle(), np.random.default_rng(SEED)


def draw(n: int) -> tuple[list[np.ndarray], list[Orientation]]:
    xs = [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in rng.uniform(4, 8, n)]
    return xs, [Orientation(float(d)) for d in rng.uniform(0.0, 360.0, n)]


(train_x, train_o), (test_x, test_o) = draw(36), draw(80)
net = SubstitutDense()
train_y = np.array([oracle.evaluer(x, o) for x, o in zip(train_x, train_o, strict=True)])
net.ajuster(tuple(train_x), train_y, tuple(train_o), seed=SEED, epoques=40, lr=0.12)
truth = [oracle.evaluer(x, o) for x, o in zip(test_x, test_o, strict=True)]
with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(("surrogate", "azimuth", "n_points", "sign_agreement", "mae_test"))
    for name, model in (("dense", net), ("analytic_untrained", SubstitutAnalytique())):
        pred = [model.evaluer(x, o) for x, o in zip(test_x, test_o, strict=True)]
        mae = float(np.mean(np.abs(np.array(pred) - truth)))
        for azimuth in (0.0, 90.0, 180.0, 270.0):
            points = np.stack(test_x[int(azimuth) // 90 * 20 :][:20])
            try:
                report = valider_gradient(
                    model, points, Orientation(azimuth), seed=SEED, reference=oracle
                )
            except SubstitutInvalide as failed:  # below 0.80: recorded, not hidden
                report = failed.report
            sign = report.accord_de_signe  # lang-ok: French field, renamed with module light
            writer.writerow((name, azimuth, 20, f"{sign:.4f}", f"{mae:.4f}"))
