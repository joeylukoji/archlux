"""Simuler le corpus : vérité terrain synthétique (Radiance hors chemin critique)."""
from __future__ import annotations

import csv
import time
from pathlib import Path

from archlux.data.synthese import generer_corpus
from archlux.light.jetons import plan_vers_vecteur
from archlux.light.simulateur import SimulateurExact
from archlux.types import Orientation

out = Path("resultats/j4_simulations.csv")
out.parent.mkdir(exist_ok=True)
sim, corpus = SimulateurExact(), generer_corpus(90, seed=17)
champs = (
    "id",
    "orientation",
    "score",
    "moteur",
    "fichier_climatique",
    "modele_ciel",
    "duree_s",
)
with out.open("w", newline="", encoding="utf-8") as handle:
    w = csv.DictWriter(handle, fieldnames=champs)
    w.writeheader()
    for identifiant, plan in corpus.items():
        debut = time.perf_counter()
        score = sim.evaluer(plan_vers_vecteur(plan), Orientation(deg=0.0))
        w.writerow(
            {
                "id": identifiant,
                "orientation": 0.0,
                "score": score,
                "moteur": "synthetique",
                "fichier_climatique": "",
                "modele_ciel": "ferme",
                "duree_s": f"{time.perf_counter() - debut:.6f}",
            }
        )
print("lignes", 90)
