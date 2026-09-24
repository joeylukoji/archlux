"""Substitut d'eclairement contre de vraies simulations — jalon 7.

Corpus non redistribue. Usage : j7_sd_etiquettes.py <msd.csv> <sd.zip> [n].
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from archlux.data.chargeurs import (
    COLONNE_SOLEIL_DEFAUT,
    charger_etiquettes_sd,
    charger_msd,
    decouper_par_site,
    etiqueter,
)
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, vectoriser
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.base import SubstitutDense
from archlux.light.protocole import Baies
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
print(f"simulations lues : {len(etiquettes)} pieces")

retenus, ys = [], []
for appart in charger_msd(MSD, limite=CIBLE):
    cible = etiqueter(appart, etiquettes)
    if cible is None or not appart.site_id:
        continue
    retenus.append(appart)
    ys.append(cible)
print(f"appartements etiquetes : {len(retenus)}  sites : {len({a.site_id for a in retenus})}")

train, calib, test = decouper_par_site(retenus, seed=GRAINE)
index = {id(a): k for k, a in enumerate(retenus)}


def vecteurs(lot: list) -> tuple[tuple, np.ndarray, tuple, tuple]:
    xs, cibles, oris, fen = [], [], [], []
    for appart in lot:
        poly = construire_polytope(deduire_ordre(appart.plan), appart.contexte)
        xs.append(vectoriser(appart.plan, poly.index))
        cibles.append(ys[index[id(appart)]])
        oris.append(appart.contexte.orientation)
        fen.append(Baies(murs=appart.plan.murs, ouvertures=appart.plan.ouvertures))
    return tuple(xs), np.asarray(cibles, dtype=float), tuple(oris), tuple(fen)


x_tr, y_tr, o_tr, b_tr = vecteurs(train)
x_ca, y_ca, o_ca, b_ca = vecteurs(calib)
x_te, y_te, o_te, b_te = vecteurs(test)
print(f"baies par appartement : median {int(np.median([len(b.ouvertures) for b in b_tr]))}")
print(f"train {len(x_tr)} | calibration {len(x_ca)} | test {len(x_te)} (par site)")

ana = SubstitutAnalytique()
# L'analytique rend un score en unites arbitraires : sans recalage affine ajuste
# sur le train, le comparer a une irradiance simulee n'a aucun sens.
brut_tr = np.array([ana.evaluer(x, o) for x, o in zip(x_tr, o_tr, strict=True)])
brut_te = np.array([ana.evaluer(x, o) for x, o in zip(x_te, o_te, strict=True)])
pente, ordonnee = np.polyfit(brut_tr, y_tr, 1)
pred_ana = pente * brut_te + ordonnee
pred_nul = np.full_like(y_te, float(y_tr.mean()))
net = SubstitutDense()
net.ajuster(x_tr, y_tr, o_tr, seed=GRAINE, epoques=150)
pred_net = np.array([net.evaluer(x, o) for x, o in zip(x_te, o_te, strict=True)])
# Meme modele, memes hyperparametres, meme graine : seule l'entree change.
net_b = SubstitutDense()
net_b.ajuster(x_tr, y_tr, o_tr, seed=GRAINE, epoques=150, baies=b_tr)
pred_netb = np.array(
    [net_b.evaluer(x, o, baies=b) for x, o, b in zip(x_te, o_te, b_te, strict=True)]
)


def score(pred: np.ndarray, vrai: np.ndarray) -> str:
    err = vrai - pred
    mae = float(np.abs(err).mean())
    return (
        f"MAE {mae:8.3f}   MAE rel {100 * mae / float(np.abs(vrai).mean()):6.1f} %   "
        f"R2 {1 - err.var() / vrai.var():7.3f}"
    )


cal = CalibrateurConforme(indicateur="sDA")
p_ca = np.array([net.evaluer(x, o) for x, o in zip(x_ca, o_ca, strict=True)])
s_ca = np.array([net.incertitude(x, o) for x, o in zip(x_ca, o_ca, strict=True)])
cal.ajuster(p_ca, y_ca, s_ca, alpha=0.10)
bornes = [
    cal.borne(float(p), float(net.incertitude(x, o)), regime="exchangeable")
    for p, x, o in zip(pred_net, x_te, o_te, strict=True)
]
couv = float(np.mean([b.borne_inf <= v <= b.borne_sup for b, v in zip(bornes, y_te, strict=True)]))
largeur = float(np.mean([b.borne_sup - b.borne_inf for b in bornes]))

rapport = (
    f"# Jalon 7 — substitut contre simulations Swiss Dwellings\n\n"
    f"cible : `{COLONNE_SOLEIL_DEFAUT}`, moyenne ponderee par surface\n"
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
Path("resultats").mkdir(exist_ok=True)
Path("resultats/j7_sd_etiquettes.md").write_text(rapport, encoding="utf-8")
print("\nconstante  :", score(pred_nul, y_te))
print("analytique :", score(pred_ana, y_te), f"[recale {pente:.4f}f{ordonnee:+.3f}]")
print("perceptron :", score(pred_net, y_te))
print("+ baies    :", score(pred_netb, y_te))
print(f"\nconforme : couverture {100 * couv:.1f} % (visee 90), largeur {largeur:.3f}")
