"""Daylight surrogate against real simulations, milestone 7.

Corpus not redistributed. Usage: j7_sd_labels.py <msd.csv> <sd.zip> [n].
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from archlux.data.loaders import (
    DEFAULT_SUN_COLUMN,
    label,
    load_msd,
    load_sd_labels,
    split_by_site,
)
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, vectorize
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.base import DenseSurrogate
from archlux.light.protocol import Glazing
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
print(f"simulations read: {len(labels)} rooms")

kept, ys = [], []
for apartment in load_msd(MSD, limit=TARGET):
    target = label(apartment, labels)
    if target is None or not apartment.site_id:
        continue
    kept.append(apartment)
    ys.append(target)
print(f"labelled apartments: {len(kept)}  sites: {len({a.site_id for a in kept})}")

train, calib, test = split_by_site(kept, seed=SEED)
index = {id(a): k for k, a in enumerate(kept)}


def vectors(batch: list) -> tuple[tuple, np.ndarray, tuple, tuple]:
    xs, targets, oris, windows = [], [], [], []
    for apartment in batch:
        poly = build_polytope(deduce_order(apartment.plan), apartment.context)
        xs.append(vectorize(apartment.plan, poly.index))
        targets.append(ys[index[id(apartment)]])
        oris.append(apartment.context.orientation)
        windows.append(Glazing(walls=apartment.plan.walls, openings=apartment.plan.openings))
    return tuple(xs), np.asarray(targets, dtype=float), tuple(oris), tuple(windows)


x_tr, y_tr, o_tr, b_tr = vectors(train)
x_ca, y_ca, o_ca, b_ca = vectors(calib)
x_te, y_te, o_te, b_te = vectors(test)
print(f"windows per apartment: median {int(np.median([len(b.openings) for b in b_tr]))}")
print(f"train {len(x_tr)} | calibration {len(x_ca)} | test {len(x_te)} (by site)")

ana = AnalyticSurrogate()
# The analytic surrogate returns a score in arbitrary units: without an affine rescaling
# fitted on the train set, comparing it with a simulated irradiance makes no sense.
raw_tr = np.array([ana.evaluate(x, o) for x, o in zip(x_tr, o_tr, strict=True)])
raw_te = np.array([ana.evaluate(x, o) for x, o in zip(x_te, o_te, strict=True)])
slope, intercept = np.polyfit(raw_tr, y_tr, 1)
pred_ana = slope * raw_te + intercept
pred_null = np.full_like(y_te, float(y_tr.mean()))
net = DenseSurrogate()
net.fit(x_tr, y_tr, o_tr, seed=SEED, epochs=150)
pred_net = np.array([net.evaluate(x, o) for x, o in zip(x_te, o_te, strict=True)])
# Same model, same hyperparameters, same seed: only the input changes.
net_b = DenseSurrogate()
net_b.fit(x_tr, y_tr, o_tr, seed=SEED, epochs=150, glazing=b_tr)
pred_netb = np.array(
    [net_b.evaluate(x, o, glazing=b) for x, o, b in zip(x_te, o_te, b_te, strict=True)]
)


def score(pred: np.ndarray, true: np.ndarray) -> str:
    err = true - pred
    mae = float(np.abs(err).mean())
    return (
        f"MAE {mae:8.3f}   rel MAE {100 * mae / float(np.abs(true).mean()):6.1f} %   "
        f"R2 {1 - err.var() / true.var():7.3f}"
    )


cal = ConformalCalibrator(indicator="sDA")
p_ca = np.array([net.evaluate(x, o) for x, o in zip(x_ca, o_ca, strict=True)])
s_ca = np.array([net.uncertainty(x, o) for x, o in zip(x_ca, o_ca, strict=True)])
cal.fit(p_ca, y_ca, s_ca, alpha=0.10)
bounds = [
    cal.bound(float(p), float(net.uncertainty(x, o)), regime="exchangeable")
    for p, x, o in zip(pred_net, x_te, o_te, strict=True)
]
cover = float(np.mean([b.lower <= v <= b.upper for b, v in zip(bounds, y_te, strict=True)]))
width = float(np.mean([b.upper - b.lower for b in bounds]))

report = (
    f"# Milestone 7: surrogate against Swiss Dwellings simulations\n\n"
    f"target: `{DEFAULT_SUN_COLUMN}`, area-weighted mean\n"
    f"split **by site** (seed {SEED}): "
    f"train {len(x_tr)} / calibration {len(x_ca)} / test {len(x_te)}\n"
    f"sites: {len({a.site_id for a in train})} / {len({a.site_id for a in calib})} / "
    f"{len({a.site_id for a in test})}\n\n"
    f"target on the test set: mean {y_te.mean():.3f}, standard deviation {y_te.std():.3f}\n\n"
    f"| model | MAE | relative MAE | R2 |\n|---|--:|--:|--:|\n"
    f"| constant (train mean) | {np.abs(y_te - pred_null).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_null).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_null).var() / y_te.var():.3f} |\n"
    f"| rescaled analytic ({slope:.4f}f{intercept:+.2f}) | "
    f"{np.abs(y_te - pred_ana).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_ana).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_ana).var() / y_te.var():.3f} |\n"
    f"| perceptron (no glazing) | {np.abs(y_te - pred_net).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_net).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_net).var() / y_te.var():.3f} |\n"
    f"| perceptron **with glazing** | {np.abs(y_te - pred_netb).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_netb).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_netb).var() / y_te.var():.3f} |\n\n"
    f"conformal alpha=0.10: measured coverage **{100 * cover:.1f} %** "
    f"(target 90 %), mean width {width:.3f}, n_calibration {cal.n}\n"
)
Path("results").mkdir(exist_ok=True)
Path("results/j7_sd_labels.md").write_text(report, encoding="utf-8")
print("\nconstant   :", score(pred_null, y_te))
print("analytic   :", score(pred_ana, y_te), f"[rescaled {slope:.4f}f{intercept:+.3f}]")
print("perceptron :", score(pred_net, y_te))
print("+ glazing  :", score(pred_netb, y_te))
print(f"\nconformal: coverage {100 * cover:.1f} % (target 90), width {width:.3f}")
