"""Frank-Wolfe — `MILESTONE-3.md` §5. L'oracle est ``lmo.solve``."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import numpy as np
import pytest

from archlux.geom.graphe import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.solveur import solve
from archlux.solve.frank_wolfe import frank_wolfe
from archlux.types import Context, Orientation, Regulation, Structure

CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    regulation=Regulation(min_areas=(), min_width=1.5),
)
POLY = build_polytope(RelativeOrder(horizontal=(), vertical=(), rooms=("A",)), CTX)
NORD = Orientation(deg=0.0)


@dataclass(frozen=True, slots=True)
class ObjectifLineaire:
    """Substitut affine : le maximum sur un polytope est un sommet."""

    c: np.ndarray
    indicator: str = "sDA"

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        del orientation, glazing
        return float(self.c @ x)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> np.ndarray:
        del x, orientation, glazing
        return self.c

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: object = None
    ) -> float:
        del x, orientation, glazing
        return 0.08


def _depart_faisable() -> np.ndarray:
    """Un point intérieur : pièce 4×4 au coin, largeur min 1,5."""
    x = np.zeros(4)
    x[POLY.index["A.x"]] = 0.0
    x[POLY.index["A.y"]] = 0.0
    x[POLY.index["A.w"]] = 4.0
    x[POLY.index["A.h"]] = 4.0
    assert POLY.contains(x)
    return x


def test_tous_les_iteres_sont_dans_le_polytope() -> None:
    objectif = ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 1.0]))
    resultat = frank_wolfe(POLY, objectif, NORD, _depart_faisable(), max_iter=8)
    assert resultat.trace.iterates
    assert all(POLY.contains(point, tol=1e-7) for point in resultat.trace.iterates)


def test_objectif_non_decroissant() -> None:
    objectif = ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 1.0]))
    valeurs = frank_wolfe(POLY, objectif, NORD, _depart_faisable(), max_iter=8).trace.values
    for avant, apres in pairwise(valeurs):
        assert apres >= avant - 1e-9


def test_gap_majore_l_ecart_a_l_optimum_lineaire() -> None:
    """Sur un objectif linéaire, le LMO donne l'optimum : le gap borne l'écart."""
    c = np.array([0.0, 0.0, 1.0, 0.0])
    objectif = ObjectifLineaire(c=c)
    x0 = _depart_faisable()
    resultat = frank_wolfe(POLY, objectif, NORD, x0, max_iter=10, away_steps=False)
    optimum = solve(POLY, -c, start=x0)
    assert optimum.status == "optimal"
    ecart = float(c @ optimum.x) - resultat.value
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
    original = solve

    def tracer(poly, c, *, start=None, cuts=None, duaux=False):
        appels.append(start)
        return original(poly, c, start=start, cuts=cuts, duaux=duaux)

    monkeypatch.setattr("archlux.solve.frank_wolfe.solve", tracer)
    frank_wolfe(
        POLY,
        ObjectifLineaire(c=np.array([0.0, 0.0, 1.0, 0.0])),
        NORD,
        _depart_faisable(),
        max_iter=4,
        away_steps=False,
    )
    assert appels
    assert all(start is not None for start in appels)
