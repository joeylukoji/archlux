"""Predire par piece plutot que par appartement — jalon 7.

92 % de la variance de l'irradiance est intra-appartement : agreger detruit le signal.
La reference n'est pas la moyenne mais la **surface au sol**, seule variable triviale
qui predise quoi que ce soit.

Usage : j7_sd_par_piece.py <msd.csv> <sd.zip> [n].
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
CIBLE = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
GRAINE = 17

labels = load_sd_labels(SD, column=DEFAULT_SUN_COLUMN)
ana = AnalyticSurrogate()
kept = [a for a in load_msd(MSD, limit=CIBLE) if a.site_id and a.source_areas]
train, calib, test = split_by_site(kept, seed=GRAINE)
print(f"appartements : {len(kept)}  sites : {len({a.site_id for a in kept})}")


def paires(lot: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(analytique, surface, verite) **par piece d'origine**."""
    pred: list[float] = []
    aires: list[float] = []
    vrais: list[float] = []
    for appart in lot:
        poly = build_polytope(deduce_order(appart.plan), appart.context)
        parts = ana.evaluate_rooms(vectorize(appart.plan, poly.index), appart.context.orientation)
        # Les sous-rectangles d'une piece portent le prefixe `pNNN` : on les recompose
        # pour retrouver la granularite de la simulation.
        somme: dict[int, float] = defaultdict(float)
        surface: dict[int, float] = defaultdict(float)
        for piece, value in zip(appart.plan.rooms, parts, strict=True):
            rang = int(piece.id.split("__")[0][1:])
            somme[rang] += float(value)
            surface[rang] += piece.aire
        for rang, aire_id in enumerate(appart.source_areas):
            cle = (appart.id, aire_id)
            if cle in labels and rang in somme:
                pred.append(somme[rang])
                aires.append(surface[rang])
                vrais.append(labels[cle][0])
    return (
        np.asarray(pred, dtype=float),
        np.asarray(aires, dtype=float),
        np.asarray(vrais, dtype=float),
    )


p_tr, a_tr, y_tr = paires(train)
p_ca, a_ca, y_ca = paires(calib)
p_te, a_te, y_te = paires(test)
print(f"pieces : train {p_tr.size} | calibration {p_ca.size} | test {p_te.size}")


def fit(entree_tr: np.ndarray, entree_te: np.ndarray) -> np.ndarray:
    """Recalage affine sur le train. L'analytique est en unites arbitraires."""
    pente, ordonnee = np.polyfit(entree_tr, y_tr, 1)
    return pente * entree_te + ordonnee


def score(pred: np.ndarray) -> tuple[float, float, float]:
    """MAE, R2, et correlation de **rang** — robuste aux queues lourdes.

    La correlation de Pearson et les moindres carres sont domines par les valeurs
    extremes de l'analytique (ecart-type 82,6 pour une moyenne de 27,6) : un R2 nul
    y signifierait « pas d'ajustement lineaire », pas « aucune information ».
    """
    err = y_te - pred
    rho = float(stats.spearmanr(pred, y_te).statistic)
    return float(np.abs(err).mean()), float(1.0 - err.var() / y_te.var()), rho


modeles = {
    "constante (moyenne du train)": np.full_like(y_te, float(y_tr.mean())),
    "surface au sol seule": fit(a_tr, a_te),
    "analytique par piece": fit(p_tr, p_te),
}

rows = ["| modele | MAE | MAE relative | R2 | rho de Spearman |", "|---|--:|--:|--:|--:|"]
for name, pred in modeles.items():
    mae, r2, rho = score(pred)
    rows.append(
        f"| {name} | {mae:.3f} | {100 * mae / np.abs(y_te).mean():.1f} % | {r2:.3f} | {rho:+.3f} |"
    )
    print(f"{name:30s} MAE {mae:.3f}  R2 {r2:+.3f}  rho {rho:+.3f}")

pred_ca = fit(p_tr, p_ca)
sigma = float(np.abs(y_ca - pred_ca).std()) or 1.0
cal = ConformalCalibrator(indicator="sDA")
cal.fit(pred_ca, y_ca, np.full_like(pred_ca, sigma), alpha=0.10)
bornes = [
    cal.borne(float(v), sigma, regime="exchangeable") for v in modeles["analytique par piece"]
]
couv = float(np.mean([b.lower <= v <= b.upper for b, v in zip(bornes, y_te, strict=True)]))
largeur = float(np.mean([b.upper - b.lower for b in bornes]))

Path("results").mkdir(exist_ok=True)
Path("results/j7_sd_par_piece.md").write_text(
    f"# Jalon 7 — prediction **par piece**\n\n"
    f"cible `{DEFAULT_SUN_COLUMN}`, decoupage par site (graine {GRAINE})\n"
    f"pieces : train {p_tr.size} / calibration {p_ca.size} / test {p_te.size}\n\n"
    f"cible sur le test : moyenne {y_te.mean():.3f}, ecart-type {y_te.std():.3f}\n\n"
    + "\n".join(rows)
    + f"\n\nconforme alpha=0,10 sur l'analytique : couverture **{100 * couv:.1f} %** "
    f"(visee 90 %), largeur {largeur:.3f}, n_calibration {cal.n}\n",
    encoding="utf-8",
)
print(f"\nconforme : couverture {100 * couv:.1f} % (visee 90), largeur {largeur:.3f}")
