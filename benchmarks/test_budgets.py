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


CTX_15_AREAS = Contexte(
    structure=CTX_15.structure,
    orientation=Orientation(deg=20.0),
    contour=CTX_15.contour,
    referentiel=Referentiel(aires_min=(("sejour", 11.0),), largeur_min=1.0),
)
"""The realistic case the budgets missed (AUDIT.md Q-C2): tight minimum areas."""


@pytest.mark.budget
def test_budget_performance_legalization_with_minimum_areas(benchmark: BenchmarkFixture) -> None:
    """Frank-Wolfe with tight minimum areas stays under the 500 ms budget.

    Until PLAN.md batch 1.2 this case raised InvariantViole, and the tangent cuts it
    needed disabled the LP warm start on every iteration.
    """
    from archlux.light.analytique import SubstitutAnalytique

    plan = _plan_15_pieces()
    benchmark(archlux.legalize, plan, CTX_15_AREAS, objective=SubstitutAnalytique())
    _assert_within_budget(benchmark, "legalisation_performantielle")


@pytest.mark.budget
@pytest.mark.parametrize(
    ("columns", "rows", "limit_ms"), [(5, 3, 500), (10, 5, 1000), (10, 10, 2000)]
)
def test_performance_mode_scales_with_tight_minimum_areas(
    columns: int, rows: int, limit_ms: float
) -> None:
    """Performance mode scales with tight minimum areas (AUDIT.md §5.6).

    At 15, 50 and 100 rooms with a_min = 11 m² for 12 m² rooms, the performance mode
    raised InvariantViole at every size. It must now return a valid plan, within a time
    that grows reasonably (limits are loose for slow CI machines).
    """
    import time

    from tests import checkers

    from archlux.light.analytique import SubstitutAnalytique

    width, height = 3.0 * columns, 4.0 * rows
    outline = ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
    rooms = tuple(
        Piece(id=f"p{i}_{j}", type="sejour", x=3.0 * i, y=4.0 * j, w=3.0, h=4.0)
        for i in range(columns)
        for j in range(rows)
    )
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=20.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(("sejour", 11.0),), largeur_min=1.0),
    )
    plan = Plan(pieces=rooms, murs=(), ouvertures=(), contour=outline)
    start = time.perf_counter()
    result = archlux.legalize(plan, ctx, objective=SubstitutAnalytique())
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert checkers.violations(result, ctx) == []
    assert elapsed_ms < limit_ms, f"{len(rooms)} rooms: {elapsed_ms:.0f} ms > {limit_ms} ms"


@pytest.mark.budget
def test_budget_certification(benchmark: BenchmarkFixture) -> None:
    """The exact proof of a 15-room plan stays under 5 ms (ARCHITECTURE.md §9).

    Declared in BUDGETS_MS since milestone 2 but never measured (AUDIT.md §5.6).
    """
    from archlux.certify.proof import verify_exactly

    plan = _plan_15_pieces()
    benchmark(verify_exactly, plan, CTX_15, reference=plan)
    _assert_within_budget(benchmark, "certification")
