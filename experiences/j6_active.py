"""Active acquisition against random, milestone 6 review (PLAN.md phase 2, AUDIT.md Q-M5):
30 paired campaigns on derived seeds (seed + cycle shared streams across campaigns), equal
budget, independent calibration; measure: final interval width (narrower is better)."""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

from archlux.active import Aleatoire, Loop, UncertaintyTimesDensity
from archlux.data.synthese import two_room_vectors
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SplitFluxOracle
from archlux.seeds import derive

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "resultats") / "j6_active.csv"
oracle = SplitFluxOracle()


def campaign(acquire: object, seed: int) -> float:
    pool, pool_o = two_room_vectors(48, seed=derive(seed, "pool"))
    calib, calib_o = two_room_vectors(16, seed=derive(seed, "calibration"))
    hold, hold_o = two_room_vectors(30, seed=derive(seed, "holdout"))
    rng = np.random.default_rng(derive(seed, "reference"))
    reference = [np.array([0, 0, 6, 4.5, 6, 0, 6, 4.5]) + rng.normal(0, 0.05, 8) for _ in range(10)]
    net = SubstitutDense()  # same six starting labels for both strategies
    ys = np.array([oracle.evaluer(x, o) for x, o in zip(pool[:6], pool_o[:6], strict=True)])
    net.ajuster(pool[:6], ys, pool_o[:6], seed=derive(seed, "init"), epoques=25, lr=0.12)
    loop = Loop(net, oracle, acquire, budget=24, batch=4, seed=seed)  # type: ignore[arg-type]
    kwargs = {"holdout": hold, "holdout_orientations": hold_o, "calibration": calib}
    report = loop.run(
        pool, pool_o, reference_optimiseur=reference, calibration_orientations=calib_o, **kwargs
    )
    assert report.calibration_independante
    return report.largeur_intervalle_finale


seeds = [derive(17, f"campaign/{k}") for k in range(30)]
with OUT.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, lineterminator="\n")
    writer.writerow(("seed", "width_random", "width_active"))
    rows = [(s, campaign(Aleatoire(), s), campaign(UncertaintyTimesDensity(), s)) for s in seeds]
    writer.writerows((s, f"{a:.6f}", f"{b:.6f}") for s, a, b in rows)
gain = np.array([a - b for _, a, b in rows])  # > 0: active is narrower
p_value, wins = wilcoxon(gain).pvalue, int((gain > 0).sum())
print(f"mean gain {gain.mean():+.3f}, active wins {wins}/30, Wilcoxon p {p_value:.3g}")
