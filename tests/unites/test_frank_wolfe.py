"""Frank-Wolfe — `MILESTONE-3.md` §5. L'oracle est ``lmo.resoudre``."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np
import pytest

from archlux.geom.graphe import OrdreRelatif
from archlux.geom.polytope import construire_polytope
from archlux.lmo.solveur import resoudre
from archlux.solve.frank_wolfe import frank_wolfe
from archlux.types import Contexte, Orientation, Referentiel, Structure

CTX = Contexte(
    structure=Structure(murs_porteurs=()),
    orientation=Orientation(deg=0.0),
    contour=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    referentiel=Referentiel(aires_min=(), largeur_min=1.5),
)
POLY = construire_polytope(OrdreRelatif(horizontal=(), vertical=(), pieces=("A",)), CTX)
NORD = Orientation(deg=0.0)


@dataclass(frozen=True, slots=True)
class ObjectifLineaire:
    """Substitut affine : le maximum sur un polytope est un sommet."""

    c: np.ndarray
    indicateur: str = "sDA"

    def evaluer(self, x: np.ndarray, orientation: Orientation, *, baies: object = None) -> float:
        del orientation, baies
        return float(self.c @ x)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> np.ndarray:
        del x, orientation, baies
        return self.c

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> float:
        del x, orientation, baies
        return 0.08


def _depart_faisable() -> np.ndarray:
    """Un point intérieur : pièce 4×4 au coin, largeur min 1,5."""
    x = np.zeros(4)
    x[POLY.index["A.x"]] = 0.0
    x[POLY.index["A.y"]] = 0.0
    x[POLY.index["A.w"]] = 4.0
    x[POLY.index["A.h"]] = 4.0
    assert POLY.contient(x)
    return x


def test_tous_les_iteres_sont_dans_le_polytope() -> None:
    objectif = ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 1.0]))
    resultat = frank_wolfe(POLY, objectif, NORD, _depart_faisable(), max_iter=8)
    assert resultat.trace.iteres
    assert all(POLY.contient(point, tol=1e-7) for point in resultat.trace.iteres)


def test_objectif_non_decroissant() -> None:
    objectif = ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 1.0]))
    valeurs = frank_wolfe(POLY, objectif, NORD, _depart_faisable(), max_iter=8).trace.objectif
    for avant, apres in pairwise(valeurs):
        assert apres >= avant - 1e-9


def test_gap_majore_l_ecart_a_l_optimum_lineaire() -> None:
    """Sur un objectif linéaire, le LMO donne l'optimum : le gap borne l'écart."""
    c = np.array([0.0, 0.0, 1.0, 0.0])
    objectif = ObjectifLineaire(c=c)
    x0 = _depart_faisable()
    resultat = frank_wolfe(POLY, objectif, NORD, x0, max_iter=10, away_steps=False)
    optimum = resoudre(POLY, -c, depart=x0)
    assert optimum.statut == "optimal"
    ecart = float(c @ optimum.x) - resultat.valeur
    assert ecart <= resultat.gap + 1e-6


def test_dualite_terminale_petite_sur_lineaire() -> None:
    """Sur un objectif linéaire, le LMO est exact : le gap tombe sous la tolérance."""
    resultat = frank_wolfe(
        POLY,
        ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 0.0])),
        NORD,
        _depart_faisable(),
        max_iter=12,
        away_steps=False,
    )
    assert resultat.gap <= 1e-4 + 1e-9


def test_warm_start_passe_toujours_depart(monkeypatch: pytest.MonkeyPatch) -> None:
    """ARCHITECTURE.md §10 : omettre ``depart=`` coûte un facteur 3 à 5."""
    appels: list[np.ndarray | None] = []
    original = resoudre

    def tracer(poly, c, *, depart=None, coupes=None, duaux=False):
        appels.append(depart)
        return original(poly, c, depart=depart, coupes=coupes, duaux=duaux)

    monkeypatch.setattr("archlux.solve.frank_wolfe.resoudre", tracer)
    frank_wolfe(
        POLY,
        ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 0.0])),
        NORD,
        _depart_faisable(),
        max_iter=4,
        away_steps=False,
    )
    assert appels
    assert all(depart is not None for depart in appels)
