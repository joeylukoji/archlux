"""Préparer le corpus synthétique et écrire les splits. API publique + data."""
from __future__ import annotations

from pathlib import Path

from archlux.bench.protocole import charger_decoupage
from archlux.data.synthese import generer_corpus

racine = Path("donnees/v1")
for nom in ("train", "calibration", "test"):
    (racine / nom).mkdir(parents=True, exist_ok=True)
corpus = generer_corpus(90, seed=17)
decoupage = charger_decoupage(Path("splits/v1"))
for identifiant, plan in corpus.items():
    if identifiant in decoupage.entrainement:
        cible = racine / "train"
    elif identifiant in decoupage.calibration:
        cible = racine / "calibration"
    else:
        cible = racine / "test"
    plan.to_json(cible / f"{identifiant}.json")
print("plans", len(corpus), "empreinte", decoupage.empreinte)
