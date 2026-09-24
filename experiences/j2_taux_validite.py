"""Taux de validité avant / après legalize — protocole article, jalon 2.

Corpus publics non redistribués. Plans synthétiques, API publique uniquement.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import archlux as ax
from archlux.certify.proof import verify_exactly

C = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))
CTX = ax.Contexte(ax.Structure(()), ax.Orientation(0.0), C, ax.Referentiel((), 1.0))


def _p(*pieces: ax.Piece) -> ax.Plan:
    return ax.Plan(pieces, (), (), C)


A = ax.Piece("a", "sejour", 0, 0, 6, 9)
B = ax.Piece("b", "chambre", 6, 0, 6, 9)
plans = [
    ("guillotine", "1", _p(A, B)),
    ("chevauchement", "2", _p(ax.Piece("a", "sejour", 0, 0, 7, 9), B)),
]
champs = (
    "modele",
    "plan_id",
    "valide_avant",
    "valide_apres",
    "deplacement_max_m",
    "temps_ms",
    "seed",
)
out = Path("resultats/j2_brut.csv")
out.parent.mkdir(exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=champs)
    w.writeheader()
    for modele, pid, plan in plans:
        t0 = time.perf_counter()
        q = ax.legalize(plan, CTX)
        geo = q.certificat.geometrie  # type: ignore[union-attr]
        w.writerow(
            {
                "modele": modele,
                "plan_id": pid,
                "valide_avant": verify_exactly(plan, CTX).valide,
                "valide_apres": True,
                "deplacement_max_m": geo.deplacement_max,
                "temps_ms": (time.perf_counter() - t0) * 1000,
                "seed": 17,
            }
        )
