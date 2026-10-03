"""Predict per room rather than per apartment, milestone 7.

92 % of the irradiance variance lies within apartments: aggregating destroys the signal.
The baseline is not the mean but the **floor area**, the only trivial variable that
predicts anything at all.

Usage: j7_sd_per_room.py <msd.csv> <sd.zip> [n].
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from archlux.data.loaders import (
    DEFAULT_SUN_COLUMN,
    load_msd,
    load_sd_labels,
    split_by_site,
)
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, vectorize
from archlux.light.analytic import AnalyticSurrogate
from archlux.uq.conformal import ConformalCalibrator

MSD = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/archlux-donnees/msd/mds_V2_5.372k.csv")
SD = Path(
    sys.argv[2]
    if len(sys.argv) > 2
    else "D:/archlux-donnees/swiss-dwellings/swiss-dwellings-v3.0.0.zip"
)
TARGET = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
SEED = 17

labels = load_sd_labels(SD, column=DEFAULT_SUN_COLUMN)
ana = AnalyticSurrogate()
kept = [a for a in load_msd(MSD, limit=TARGET) if a.site_id and a.source_areas]
train, calib, test = split_by_site(kept, seed=SEED)
print(f"apartments: {len(kept)}  sites: {len({a.site_id for a in kept})}")


def pairs(batch: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(analytic, area, truth) **per source room**."""
    pred: list[float] = []
    areas: list[float] = []
    truths: list[float] = []
    for apartment in batch:
        poly = build_polytope(deduce_order(apartment.plan), apartment.context)
        parts = ana.evaluate_rooms(
            vectorize(apartment.plan, poly.index), apartment.context.orientation
        )
        # The sub-rectangles of a room carry the prefix `pNNN`: they are merged back to
        # recover the granularity of the simulation.
        total: dict[int, float] = defaultdict(float)
        surface: dict[int, float] = defaultdict(float)
        for room, value in zip(apartment.plan.rooms, parts, strict=True):
            rank = int(room.id.split("__")[0][1:])
            total[rank] += float(value)
            surface[rank] += room.area
        for rank, area_id in enumerate(apartment.source_areas):
            key = (apartment.id, area_id)
            if key in labels and rank in total:
                pred.append(total[rank])
                areas.append(surface[rank])
                truths.append(labels[key][0])
    return (
        np.asarray(pred, dtype=float),
        np.asarray(areas, dtype=float),
        np.asarray(truths, dtype=float),
    )


p_tr, a_tr, y_tr = pairs(train)
p_ca, a_ca, y_ca = pairs(calib)
p_te, a_te, y_te = pairs(test)
print(f"rooms: train {p_tr.size} | calibration {p_ca.size} | test {p_te.size}")


def fit(input_tr: np.ndarray, input_te: np.ndarray) -> np.ndarray:
    """Affine rescaling on the train set. The analytic surrogate is in arbitrary units."""
    slope, intercept = np.polyfit(input_tr, y_tr, 1)
    return slope * input_te + intercept


def score(pred: np.ndarray) -> tuple[float, float, float]:
    """MAE, R2, and **rank** correlation, robust to heavy tails.

    The Pearson correlation and least squares are dominated by the extreme values of
    the analytic surrogate (standard deviation 82.6 for a mean of 27.6): a zero R2 there
    would mean "no linear fit", not "no information".
    """
    err = y_te - pred
    rho = float(stats.spearmanr(pred, y_te).statistic)
    return float(np.abs(err).mean()), float(1.0 - err.var() / y_te.var()), rho


models = {
    "constant (train mean)": np.full_like(y_te, float(y_tr.mean())),
    "floor area alone": fit(a_tr, a_te),
    "analytic per room": fit(p_tr, p_te),
}

rows = ["| model | MAE | relative MAE | R2 | Spearman rho |", "|---|--:|--:|--:|--:|"]
for name, pred in models.items():
    mae, r2, rho = score(pred)
    rows.append(
        f"| {name} | {mae:.3f} | {100 * mae / np.abs(y_te).mean():.1f} % | {r2:.3f} | {rho:+.3f} |"
    )
    print(f"{name:30s} MAE {mae:.3f}  R2 {r2:+.3f}  rho {rho:+.3f}")

pred_ca = fit(p_tr, p_ca)
sigma = float(np.abs(y_ca - pred_ca).std()) or 1.0
cal = ConformalCalibrator(indicator="sDA")
cal.fit(pred_ca, y_ca, np.full_like(pred_ca, sigma), alpha=0.10)
bounds = [cal.bound(float(v), sigma, regime="exchangeable") for v in models["analytic per room"]]
cover = float(np.mean([b.lower <= v <= b.upper for b, v in zip(bounds, y_te, strict=True)]))
width = float(np.mean([b.upper - b.lower for b in bounds]))

Path("results").mkdir(exist_ok=True)
Path("results/j7_sd_per_room.md").write_text(
    f"# Milestone 7: prediction **per room**\n\n"
    f"target `{DEFAULT_SUN_COLUMN}`, split by site (seed {SEED})\n"
    f"rooms: train {p_tr.size} / calibration {p_ca.size} / test {p_te.size}\n\n"
    f"target on the test set: mean {y_te.mean():.3f}, standard deviation {y_te.std():.3f}\n\n"
    + "\n".join(rows)
    + f"\n\nconformal alpha=0.10 on the analytic surrogate: coverage **{100 * cover:.1f} %** "
    f"(target 90 %), width {width:.3f}, n_calibration {cal.n}\n",
    encoding="utf-8",
)
print(f"\nconformal: coverage {100 * cover:.1f} % (target 90), width {width:.3f}")
