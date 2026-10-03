"""Substitut d'eclairement contre de vraies simulations — jalon 7.

Corpus non redistribue. Usage : j7_sd_labels.py <msd.csv> <sd.zip> [n].
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
CIBLE = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
GRAINE = 17

labels = load_sd_labels(SD, column=DEFAULT_SUN_COLUMN)
print(f"simulations lues : {len(labels)} pieces")

kept, ys = [], []
for appart in load_msd(MSD, limit=CIBLE):
    cible = label(appart, labels)
    if cible is None or not appart.site_id:
        continue
    kept.append(appart)
    ys.append(cible)
print(f"appartements etiquetes : {len(kept)}  sites : {len({a.site_id for a in kept})}")

train, calib, test = split_by_site(kept, seed=GRAINE)
index = {id(a): k for k, a in enumerate(kept)}


def vecteurs(lot: list) -> tuple[tuple, np.ndarray, tuple, tuple]:
    xs, cibles, oris, fen = [], [], [], []
    for appart in lot:
        poly = build_polytope(deduce_order(appart.plan), appart.context)
        xs.append(vectorize(appart.plan, poly.index))
        cibles.append(ys[index[id(appart)]])
        oris.append(appart.context.orientation)
        fen.append(Glazing(walls=appart.plan.walls, openings=appart.plan.openings))
    return tuple(xs), np.asarray(cibles, dtype=float), tuple(oris), tuple(fen)


x_tr, y_tr, o_tr, b_tr = vecteurs(train)
x_ca, y_ca, o_ca, b_ca = vecteurs(calib)
x_te, y_te, o_te, b_te = vecteurs(test)
print(f"baies par appartement : median {int(np.median([len(b.openings) for b in b_tr]))}")
print(f"train {len(x_tr)} | calibration {len(x_ca)} | test {len(x_te)} (par site)")

ana = AnalyticSurrogate()
# L'analytique rend un score en unites arbitraires : sans recalage affine ajuste
# sur le train, le comparer a une irradiance simulee n'a aucun sens.
brut_tr = np.array([ana.evaluate(x, o) for x, o in zip(x_tr, o_tr, strict=True)])
brut_te = np.array([ana.evaluate(x, o) for x, o in zip(x_te, o_te, strict=True)])
pente, ordonnee = np.polyfit(brut_tr, y_tr, 1)
pred_ana = pente * brut_te + ordonnee
pred_nul = np.full_like(y_te, float(y_tr.mean()))
net = DenseSurrogate()
net.fit(x_tr, y_tr, o_tr, seed=GRAINE, epochs=150)
pred_net = np.array([net.evaluate(x, o) for x, o in zip(x_te, o_te, strict=True)])
# Meme modele, memes hyperparametres, meme graine : seule l'entree change.
net_b = DenseSurrogate()
net_b.fit(x_tr, y_tr, o_tr, seed=GRAINE, epochs=150, glazing=b_tr)
pred_netb = np.array(
    [net_b.evaluate(x, o, glazing=b) for x, o, b in zip(x_te, o_te, b_te, strict=True)]
)


def score(pred: np.ndarray, vrai: np.ndarray) -> str:
    err = vrai - pred
    mae = float(np.abs(err).mean())
    return (
        f"MAE {mae:8.3f}   MAE rel {100 * mae / float(np.abs(vrai).mean()):6.1f} %   "
        f"R2 {1 - err.var() / vrai.var():7.3f}"
    )


cal = ConformalCalibrator(indicator="sDA")
p_ca = np.array([net.evaluate(x, o) for x, o in zip(x_ca, o_ca, strict=True)])
s_ca = np.array([net.uncertainty(x, o) for x, o in zip(x_ca, o_ca, strict=True)])
cal.fit(p_ca, y_ca, s_ca, alpha=0.10)
bornes = [
    cal.bound(float(p), float(net.uncertainty(x, o)), regime="exchangeable")
    for p, x, o in zip(pred_net, x_te, o_te, strict=True)
]
couv = float(np.mean([b.lower <= v <= b.upper for b, v in zip(bornes, y_te, strict=True)]))
largeur = float(np.mean([b.upper - b.lower for b in bornes]))

rapport = (
    f"# Jalon 7 — substitut contre simulations Swiss Dwellings\n\n"
    f"cible : `{DEFAULT_SUN_COLUMN}`, moyenne ponderee par surface\n"
    f"decoupage **par site** (graine {GRAINE}) : "
    f"train {len(x_tr)} / calibration {len(x_ca)} / test {len(x_te)}\n"
    f"sites : {len({a.site_id for a in train})} / {len({a.site_id for a in calib})} / "
    f"{len({a.site_id for a in test})}\n\n"
    f"cible sur le test : moyenne {y_te.mean():.3f}, ecart-type {y_te.std():.3f}\n\n"
    f"| modele | MAE | MAE relative | R2 |\n|---|--:|--:|--:|\n"
    f"| constante (moyenne du train) | {np.abs(y_te - pred_nul).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_nul).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_nul).var() / y_te.var():.3f} |\n"
    f"| analytique recale ({pente:.4f}f{ordonnee:+.2f}) | {np.abs(y_te - pred_ana).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_ana).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_ana).var() / y_te.var():.3f} |\n"
    f"| perceptron (sans baies) | {np.abs(y_te - pred_net).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_net).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_net).var() / y_te.var():.3f} |\n"
    f"| perceptron **avec baies** | {np.abs(y_te - pred_netb).mean():.3f} | "
    f"{100 * np.abs(y_te - pred_netb).mean() / np.abs(y_te).mean():.1f} % | "
    f"{1 - (y_te - pred_netb).var() / y_te.var():.3f} |\n\n"
    f"conforme alpha=0,10 : couverture mesuree **{100 * couv:.1f} %** "
    f"(visee 90 %), largeur moyenne {largeur:.3f}, n_calibration {cal.n}\n"
)
Path("results").mkdir(exist_ok=True)
Path("results/j7_sd_labels.md").write_text(rapport, encoding="utf-8")
print("\nconstante  :", score(pred_nul, y_te))
print("analytique :", score(pred_ana, y_te), f"[recale {pente:.4f}f{ordonnee:+.3f}]")
print("perceptron :", score(pred_net, y_te))
print("+ baies    :", score(pred_netb, y_te))
print(f"\nconforme : couverture {100 * couv:.1f} % (visee 90), largeur {largeur:.3f}")
