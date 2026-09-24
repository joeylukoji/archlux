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

from archlux.data.chargeurs import (
    COLONNE_SOLEIL_DEFAUT,
    charger_etiquettes_sd,
    charger_msd,
    decouper_par_site,
)
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, vectoriser
from archlux.light.analytique import SubstitutAnalytique
from archlux.uq.conforme import CalibrateurConforme

MSD = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/archlux-donnees/msd/mds_V2_5.372k.csv")
SD = Path(
    sys.argv[2]
    if len(sys.argv) > 2
    else "D:/archlux-donnees/swiss-dwellings/swiss-dwellings-v3.0.0.zip"
)
CIBLE = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
GRAINE = 17

etiquettes = charger_etiquettes_sd(SD, colonne=COLONNE_SOLEIL_DEFAUT)
ana = SubstitutAnalytique()
retenus = [a for a in charger_msd(MSD, limite=CIBLE) if a.site_id and a.aires_sources]
train, calib, test = decouper_par_site(retenus, seed=GRAINE)
print(f"appartements : {len(retenus)}  sites : {len({a.site_id for a in retenus})}")


def paires(lot: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(analytique, surface, verite) **par piece d'origine**."""
    pred: list[float] = []
    aires: list[float] = []
    vrais: list[float] = []
    for appart in lot:
        poly = construire_polytope(deduire_ordre(appart.plan), appart.contexte)
        parts = ana.evaluer_pieces(vectoriser(appart.plan, poly.index), appart.contexte.orientation)
        # Les sous-rectangles d'une piece portent le prefixe `pNNN` : on les recompose
        # pour retrouver la granularite de la simulation.
        somme: dict[int, float] = defaultdict(float)
        surface: dict[int, float] = defaultdict(float)
        for piece, valeur in zip(appart.plan.pieces, parts, strict=True):
            rang = int(piece.id.split("__")[0][1:])
            somme[rang] += float(valeur)
            surface[rang] += piece.aire
        for rang, aire_id in enumerate(appart.aires_sources):
            cle = (appart.identifiant, aire_id)
            if cle in etiquettes and rang in somme:
                pred.append(somme[rang])
                aires.append(surface[rang])
                vrais.append(etiquettes[cle][0])
    return (
        np.asarray(pred, dtype=float),
        np.asarray(aires, dtype=float),
        np.asarray(vrais, dtype=float),
    )


p_tr, a_tr, y_tr = paires(train)
p_ca, a_ca, y_ca = paires(calib)
p_te, a_te, y_te = paires(test)
print(f"pieces : train {p_tr.size} | calibration {p_ca.size} | test {p_te.size}")


def ajuster(entree_tr: np.ndarray, entree_te: np.ndarray) -> np.ndarray:
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
    "surface au sol seule": ajuster(a_tr, a_te),
    "analytique par piece": ajuster(p_tr, p_te),
}

lignes = ["| modele | MAE | MAE relative | R2 | rho de Spearman |", "|---|--:|--:|--:|--:|"]
for nom, pred in modeles.items():
    mae, r2, rho = score(pred)
    lignes.append(
        f"| {nom} | {mae:.3f} | {100 * mae / np.abs(y_te).mean():.1f} % | {r2:.3f} | {rho:+.3f} |"
    )
    print(f"{nom:30s} MAE {mae:.3f}  R2 {r2:+.3f}  rho {rho:+.3f}")

pred_ca = ajuster(p_tr, p_ca)
sigma = float(np.abs(y_ca - pred_ca).std()) or 1.0
cal = CalibrateurConforme(indicateur="sDA")
cal.ajuster(pred_ca, y_ca, np.full_like(pred_ca, sigma), alpha=0.10)
bornes = [
    cal.borne(float(v), sigma, regime="exchangeable") for v in modeles["analytique par piece"]
]
couv = float(np.mean([b.borne_inf <= v <= b.borne_sup for b, v in zip(bornes, y_te, strict=True)]))
largeur = float(np.mean([b.borne_sup - b.borne_inf for b in bornes]))

Path("resultats").mkdir(exist_ok=True)
Path("resultats/j7_sd_par_piece.md").write_text(
    f"# Jalon 7 — prediction **par piece**\n\n"
    f"cible `{COLONNE_SOLEIL_DEFAUT}`, decoupage par site (graine {GRAINE})\n"
    f"pieces : train {p_tr.size} / calibration {p_ca.size} / test {p_te.size}\n\n"
    f"cible sur le test : moyenne {y_te.mean():.3f}, ecart-type {y_te.std():.3f}\n\n"
    + "\n".join(lignes)
    + f"\n\nconforme alpha=0,10 sur l'analytique : couverture **{100 * couv:.1f} %** "
    f"(visee 90 %), largeur {largeur:.3f}, n_calibration {cal.n}\n",
    encoding="utf-8",
)
print(f"\nconforme : couverture {100 * couv:.1f} % (visee 90), largeur {largeur:.3f}")
