"""API publique ``legalize`` — `MILESTONE-2.md` §7."""

from __future__ import annotations

import numpy as np
import pytest

import archlux
from archlux.api import gradient_distance
from archlux.errors import Infeasible
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, etendre_ecarts_l1, vectoriser
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure
from tests.proprietes.strategies import CONTEXTE_DEFAUT


def test_gradient_distance_a_la_dimension_double() -> None:
    """c = (0_n, 1_n) : l'objectif ne porte que sur les écarts."""
    c = gradient_distance(np.ones(4))
    assert c.shape == (8,)
    assert np.allclose(c[:4], 0.0)
    assert np.allclose(c[4:], 1.0)


def test_l1_d_un_point_faisable_est_nulle() -> None:
    """Si x̂ ∈ P, min ||x − x̂||₁ = 0 et x★ = x̂ (Bertsimas–Tsitsiklis)."""
    plan = Plan(
        rooms=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT)
    assert q.certificate is not None
    assert q.certificate.geometry.valid
    assert q.certificate.geometry.max_displacement == pytest.approx(0.0, abs=1e-5)


def test_un_chevauchement_est_corrige() -> None:
    """Deux pièces qui se recouvrent de 1 m en x, union = enveloppe, sont séparées.

    L1 préfère réduire ``a.w`` d'un mètre plutôt que de créer un jour : après
    correction le pavage reste exact (Bertsimas–Tsitsiklis, épigraphe).
    """
    plan = Plan(
        rooms=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
            Room(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT)
    assert q.certificate is not None
    assert q.certificate.geometry.valid
    assert q.certificate.geometry.overlap is False
    gauche = next(p for p in q.rooms if p.id == "a")
    droite = next(p for p in q.rooms if p.id == "b")
    assert gauche.x + gauche.w <= droite.x + 1e-6


def test_programme_trop_gros_leve_infaisable() -> None:
    """Deux pièces de largeur min 8 m dans 12 m d'enveloppe, côte à côte."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
        regulation=Regulation(min_areas=(), min_width=8.0),
    )
    plan = Plan(
        rooms=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=8.0, h=8.0),
            Room(id="b", type="sejour", x=8.0, y=0.0, w=8.0, h=8.0),
        ),
        walls=(),
        openings=(),
        outline=ctx.outline,
    )
    with pytest.raises(Infeasible) as capture:
        archlux.legalize(plan, ctx)
    assert capture.value.farkas_certificate is not None
    assert capture.value.origins


def test_largeur_min_plus_grande_que_l_enveloppe_leve_infaisable() -> None:
    """Non-régression : ``largeur_min`` > enveloppe est infaisable, pas un bogue interne.

    Les bornes de ``w`` valaient alors ``(largeur_min, xmax - xmin)``, un intervalle
    **inversé** : GLOP répondait ``ABNORMAL``, traduit en statut ``"limite"``, et
    ``legalize`` levait ``InvariantViolation`` (« bogue interne ») au lieu d'``Infeasible``,
    sans aucun diagnostic — alors que le programme est bel et bien infaisable.
    """
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)),
        regulation=Regulation(min_areas=(), min_width=4.0),
    )
    plan = Plan(
        rooms=(Room(id="a", type="sejour", x=0.0, y=0.0, w=3.0, h=3.0),),
        walls=(),
        openings=(),
        outline=ctx.outline,
    )
    with pytest.raises(Infeasible) as capture:
        archlux.legalize(plan, ctx)
    assert capture.value.origins
    assert any("largeur minimale" in origine for origine in capture.value.origins)


def test_polytope_sans_piece_tolere_une_enveloppe_etroite() -> None:
    """Aucune pièce : aucune variable ``w``/``h``, donc rien à déclarer infaisable."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)),
        regulation=Regulation(min_areas=(), min_width=4.0),
    )
    vide = Plan(rooms=(), walls=(), openings=(), outline=ctx.outline)
    poly = construire_polytope(deduire_ordre(vide), ctx)
    assert poly.index == {}
    assert poly.bornes == ()


def test_objective_invalide_leve_typeerror() -> None:
    plan = Plan(
        rooms=(Room(id="a", type="sejour", x=0.0, y=0.0, w=3.0, h=3.0),),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    with pytest.raises(TypeError, match="Surrogate"):
        archlux.legalize(plan, CONTEXTE_DEFAUT, objective=object())  # type: ignore[arg-type]


def test_objective_analytique_reste_valide() -> None:
    from archlux.light.analytique import SubstitutAnalytique

    plan = Plan(
        rooms=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=SubstitutAnalytique())
    assert q.certificate is not None
    assert q.certificate.geometry.valid
    assert q.certificate.performance is None


def test_legalize_trace_remonte_les_iteres() -> None:
    from archlux.light.analytique import SubstitutAnalytique
    from archlux.solve.trace import Trace

    plan = Plan(
        rooms=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=SubstitutAnalytique(), trace=True)
    assert isinstance(q.trace, Trace)
    assert q.trace.iterates
    assert q.certificate is not None
    assert q.certificate.geometry.valid


def test_budget_zero_reste_au_point_l1() -> None:
    """``budget=0`` interdit tout déplacement performantiel : on reste au L1."""
    from archlux.light.analytique import SubstitutAnalytique

    plan = Plan(
        rooms=(
            Room(id="sw", type="sejour", x=0.0, y=0.0, w=6.0, h=4.5),
            Room(id="se", type="chambre", x=6.0, y=0.0, w=6.0, h=4.5),
            Room(id="nw", type="sejour", x=0.0, y=4.5, w=6.0, h=4.5),
            Room(id="ne", type="chambre", x=6.0, y=4.5, w=6.0, h=4.5),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    l1 = archlux.legalize(plan, CONTEXTE_DEFAUT)
    bloque = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=SubstitutAnalytique(), budget=0.0)
    xl1 = np.array([(p.x, p.y, p.w, p.h) for p in l1.rooms])
    xb = np.array([(p.x, p.y, p.w, p.h) for p in bloque.rooms])
    assert np.allclose(xl1, xb, atol=1e-6)


def test_une_surface_insuffisante_est_agrandie() -> None:
    """Kelley + AM-GM : une pièce 2×9 = 18 m² sous a_min = 20 m² est dilatée."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=CONTEXTE_DEFAUT.outline,
        regulation=Regulation(min_areas=(("sdb", 20.0),), min_width=1.0),
    )
    plan = Plan(
        rooms=(
            Room(id="sdb", type="sdb", x=0.0, y=0.0, w=2.0, h=9.0),
            Room(id="sejour", type="sejour", x=2.0, y=0.0, w=10.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=ctx.outline,
    )
    q = archlux.legalize(plan, ctx)
    sdb = next(p for p in q.rooms if p.id == "sdb")
    assert sdb.area >= 20.0 - 1e-6
    assert q.certificate is not None
    assert q.certificate.geometry.valid


def test_etendre_l1_double_les_variables() -> None:
    plan = Plan(
        rooms=(Room(id="a", type="sejour", x=0.0, y=0.0, w=3.0, h=3.0),),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    poly = construire_polytope(deduire_ordre(plan), CONTEXTE_DEFAUT)
    x = vectoriser(plan, poly.index)
    etendu = etendre_ecarts_l1(poly, x)
    assert len(etendu.index) == 2 * len(poly.index)
    assert etendu.A.shape[1] == 2 * len(poly.index)
