"""Budgets de performance de `ARCHITECTURE.md` §9. Un dépassement casse la construction.

Ce ne sont pas des mesures indicatives : ce sont des contrats. Le rapport entre la
légalisation performantielle (< 500 ms) et une simulation exacte (minutes à heures) est
l'argument de faisabilité du projet ; le perdre, c'est perdre le projet.

Référence : **15 pièces**, et 50 itérations pour le mode performantiel.
"""

from __future__ import annotations

from statistics import median
from typing import TYPE_CHECKING

import numpy as np
import pytest

import archlux
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope
from archlux.lmo.solveur import resoudre, vider_cache
from archlux.types import (
    Contexte,
    Orientation,
    Piece,
    Plan,
    Referentiel,
    Structure,
)

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

BUDGETS_MS = {
    "polytope": 5.0,
    "lp_froid": 10.0,
    "lp_chaud": 3.0,
    "legalisation_classique": 20.0,
    "legalisation_performantielle": 500.0,
    "certification": 5.0,
}
"""Référence : 15 pièces ; 50 itérations pour le mode performantiel."""


def _assert_within_budget(benchmark: BenchmarkFixture, budget: str) -> None:
    """Fail if the measured mean exceeds ``BUDGETS_MS[budget]``.

    With ``--benchmark-disable`` the function runs once and ``benchmark.stats`` is
    ``None``: nothing was measured, so the budget is reported as skipped rather than
    silently passed. An unmeasured budget is not a met budget.
    """
    if benchmark.stats is None:
        pytest.skip(f"benchmarks disabled: budget '{budget}' not measured")
    mean_ms = benchmark.stats["mean"] * 1000
    limit_ms = BUDGETS_MS[budget]
    assert mean_ms < limit_ms, f"{mean_ms:.2f} ms > {limit_ms} ms — budget §9 '{budget}' exceeded"


CTX_15 = Contexte(
    structure=Structure(murs_porteurs=()),
    orientation=Orientation(deg=0.0),
    contour=((0.0, 0.0), (15.0, 0.0), (15.0, 12.0), (0.0, 12.0)),
    referentiel=Referentiel(aires_min=(), largeur_min=1.0),
)


def _plan_15_pieces() -> Plan:
    """Grille 5 x 3 de pièces jointives, le cas de référence du §9."""
    pieces = tuple(
        Piece(
            id=f"p{colonne}_{ligne}",
            type="sejour",
            x=colonne * 3.0,
            y=ligne * 4.0,
            w=3.0,
            h=4.0,
        )
        for colonne in range(5)
        for ligne in range(3)
    )
    return Plan(pieces=pieces, murs=(), ouvertures=(), contour=CTX_15.contour)


def _poly_15() -> object:
    return construire_polytope(deduire_ordre(_plan_15_pieces()), CTX_15)


@pytest.mark.budget
def test_budget_lp_a_froid(benchmark: BenchmarkFixture) -> None:
    """Un appel LP à froid < 10 ms : construction du modèle **comprise**."""
    poly = _poly_15()
    c = np.ones(len(poly.index))  # type: ignore[attr-defined]
    vider_cache()
    benchmark(resoudre, poly, c)
    _assert_within_budget(benchmark, "lp_froid")


@pytest.mark.budget
def test_budget_lp_a_chaud(benchmark: BenchmarkFixture) -> None:
    """Un appel LP à chaud < 3 ms : le modèle est réutilisé, seul l'objectif change."""
    poly = _poly_15()
    n = len(poly.index)  # type: ignore[attr-defined]
    froid = resoudre(poly, np.ones(n))
    benchmark(resoudre, poly, -np.ones(n), depart=froid.x)
    _assert_within_budget(benchmark, "lp_chaud")


@pytest.mark.budget
def test_warm_start_est_plus_rapide() -> None:
    """`ARCHITECTURE.md` §10 : un LP sans ``depart=`` dans une boucle coûte ×3 à ×5.

    Les mesures sont **entrelacées** et comparées par leur **médiane**. Sommer deux
    séries mesurées l'une après l'autre laisse un seul pic d'ordonnancement décider du
    verdict : le test échouait alors environ une fois sur sept. Un test instable est pire
    qu'un test qui échoue — on finit par ignorer les deux.
    """
    poly = _poly_15()
    n = len(poly.index)  # type: ignore[attr-defined]
    vider_cache()
    reference = resoudre(poly, np.ones(n))

    froids: list[float] = []
    chauds: list[float] = []
    for k in range(15):
        c = np.full(n, (-1.0) ** k)
        vider_cache()
        froids.append(resoudre(poly, c).temps_ms)
        resoudre(poly, c, depart=reference.x)  # amorce le modèle en cache
        chauds.append(resoudre(poly, c, depart=reference.x).temps_ms)

    median_froid, median_chaud = median(froids), median(chauds)
    assert median_chaud < median_froid, (
        f"médiane à chaud {median_chaud:.3f} ms, à froid {median_froid:.3f} ms"
    )


@pytest.mark.budget
def test_budget_polytope(benchmark: BenchmarkFixture) -> None:
    """Construction du polytope < 5 ms pour 15 pièces.

    L'ordre est déduit **hors mesure** : le budget du §9 porte sur l'assemblage du
    système, et mélanger les deux rendrait le dépassement impossible à imputer.
    """
    ordre = deduire_ordre(_plan_15_pieces())
    benchmark(construire_polytope, ordre, CTX_15)
    _assert_within_budget(benchmark, "polytope")


@pytest.mark.budget
def test_budget_legalisation_classique(benchmark: BenchmarkFixture) -> None:
    """Pipeline complet ``legalize`` < 20 ms pour 15 pièces (`ARCHITECTURE.md` §9)."""
    plan = _plan_15_pieces()
    benchmark(archlux.legalize, plan, CTX_15)
    _assert_within_budget(benchmark, "legalisation_classique")


@pytest.mark.budget
def test_budget_legalisation_performantielle(benchmark: BenchmarkFixture) -> None:
    """Frank-Wolfe + substitut analytique < 500 ms (`ARCHITECTURE.md` §9)."""
    from archlux.light.analytique import SubstitutAnalytique

    plan = _plan_15_pieces()
    objectif = SubstitutAnalytique()
    benchmark(archlux.legalize, plan, CTX_15, objective=objectif)
    _assert_within_budget(benchmark, "legalisation_performantielle")
