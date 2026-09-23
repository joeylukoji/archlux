"""API publique ``legalize`` — `MILESTONE-2.md` §7."""

from __future__ import annotations

import numpy as np
import pytest

import archlux
from archlux.api import gradient_distance
from archlux.erreurs import Infaisable
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, etendre_ecarts_l1, vectoriser
from archlux.types import Contexte, Orientation, Piece, Plan, Referentiel, Structure
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
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT)
    assert q.certificat is not None
    assert q.certificat.geometrie.valide
    assert q.certificat.geometrie.deplacement_max == pytest.approx(0.0, abs=1e-5)


def test_un_chevauchement_est_corrige() -> None:
    """Deux pièces qui se recouvrent de 1 m en x, union = enveloppe, sont séparées.

    L1 préfère réduire ``a.w`` d'un mètre plutôt que de créer un jour : après
    correction le pavage reste exact (Bertsimas–Tsitsiklis, épigraphe).
    """
    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
            Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT)
    assert q.certificat is not None
    assert q.certificat.geometrie.valide
    assert q.certificat.geometrie.chevauchement is False
    gauche = next(p for p in q.pieces if p.id == "a")
    droite = next(p for p in q.pieces if p.id == "b")
    assert gauche.x + gauche.w <= droite.x + 1e-6


def test_programme_trop_gros_leve_infaisable() -> None:
    """Deux pièces de largeur min 8 m dans 12 m d'enveloppe, côte à côte."""
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
        referentiel=Referentiel(aires_min=(), largeur_min=8.0),
    )
    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=8.0, h=8.0),
            Piece(id="b", type="sejour", x=8.0, y=0.0, w=8.0, h=8.0),
        ),
        murs=(),
        ouvertures=(),
        contour=ctx.contour,
    )
    with pytest.raises(Infaisable) as capture:
        archlux.legalize(plan, ctx)
    assert capture.value.certificat_farkas is not None
    assert capture.value.origines


def test_largeur_min_plus_grande_que_l_enveloppe_leve_infaisable() -> None:
    """Non-régression : ``largeur_min`` > enveloppe est infaisable, pas un bogue interne.

    Les bornes de ``w`` valaient alors ``(largeur_min, xmax - xmin)``, un intervalle
    **inversé** : GLOP répondait ``ABNORMAL``, traduit en statut ``"limite"``, et
    ``legalize`` levait ``InvariantViole`` (« bogue interne ») au lieu d'``Infaisable``,
    sans aucun diagnostic — alors que le programme est bel et bien infaisable.
    """
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)),
        referentiel=Referentiel(aires_min=(), largeur_min=4.0),
    )
    plan = Plan(
        pieces=(Piece(id="a", type="sejour", x=0.0, y=0.0, w=3.0, h=3.0),),
        murs=(),
        ouvertures=(),
        contour=ctx.contour,
    )
    with pytest.raises(Infaisable) as capture:
        archlux.legalize(plan, ctx)
    assert capture.value.origines
    assert any("largeur minimale" in origine for origine in capture.value.origines)


def test_polytope_sans_piece_tolere_une_enveloppe_etroite() -> None:
    """Aucune pièce : aucune variable ``w``/``h``, donc rien à déclarer infaisable."""
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)),
        referentiel=Referentiel(aires_min=(), largeur_min=4.0),
    )
    vide = Plan(pieces=(), murs=(), ouvertures=(), contour=ctx.contour)
    poly = construire_polytope(deduire_ordre(vide), ctx)
    assert poly.index == {}
    assert poly.bornes == ()


def test_objective_invalide_leve_typeerror() -> None:
    plan = Plan(
        pieces=(Piece(id="a", type="sejour", x=0.0, y=0.0, w=3.0, h=3.0),),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    with pytest.raises(TypeError, match="Substitut"):
        archlux.legalize(plan, CONTEXTE_DEFAUT, objective=object())  # type: ignore[arg-type]


def test_objective_analytique_reste_valide() -> None:
    from archlux.light.analytique import SubstitutAnalytique

    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=SubstitutAnalytique())
    assert q.certificat is not None
    assert q.certificat.geometrie.valide
    assert q.certificat.performance is None


def test_legalize_trace_remonte_les_iteres() -> None:
    from archlux.light.analytique import SubstitutAnalytique
    from archlux.solve.trace import Trace

    plan = Plan(
        pieces=(
            Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    q = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=SubstitutAnalytique(), trace=True)
    assert isinstance(q.trace, Trace)
    assert q.trace.iteres
    assert q.certificat is not None
    assert q.certificat.geometrie.valide


def test_budget_zero_reste_au_point_l1() -> None:
    """``budget=0`` interdit tout déplacement performantiel : on reste au L1."""
    from archlux.light.analytique import SubstitutAnalytique

    plan = Plan(
        pieces=(
            Piece(id="sw", type="sejour", x=0.0, y=0.0, w=6.0, h=4.5),
            Piece(id="se", type="chambre", x=6.0, y=0.0, w=6.0, h=4.5),
            Piece(id="nw", type="sejour", x=0.0, y=4.5, w=6.0, h=4.5),
            Piece(id="ne", type="chambre", x=6.0, y=4.5, w=6.0, h=4.5),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    l1 = archlux.legalize(plan, CONTEXTE_DEFAUT)
    bloque = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=SubstitutAnalytique(), budget=0.0)
    xl1 = np.array([(p.x, p.y, p.w, p.h) for p in l1.pieces])
    xb = np.array([(p.x, p.y, p.w, p.h) for p in bloque.pieces])
    assert np.allclose(xl1, xb, atol=1e-6)


def test_une_surface_insuffisante_est_agrandie() -> None:
    """Kelley + AM-GM : une pièce 2×9 = 18 m² sous a_min = 20 m² est dilatée."""
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=CONTEXTE_DEFAUT.contour,
        referentiel=Referentiel(aires_min=(("sdb", 20.0),), largeur_min=1.0),
    )
    plan = Plan(
        pieces=(
            Piece(id="sdb", type="sdb", x=0.0, y=0.0, w=2.0, h=9.0),
            Piece(id="sejour", type="sejour", x=2.0, y=0.0, w=10.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=ctx.contour,
    )
    q = archlux.legalize(plan, ctx)
    sdb = next(p for p in q.pieces if p.id == "sdb")
    assert sdb.aire >= 20.0 - 1e-6
    assert q.certificat is not None
    assert q.certificat.geometrie.valide


def test_etendre_l1_double_les_variables() -> None:
    plan = Plan(
        pieces=(Piece(id="a", type="sejour", x=0.0, y=0.0, w=3.0, h=3.0),),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    poly = construire_polytope(deduire_ordre(plan), CONTEXTE_DEFAUT)
    x = vectoriser(plan, poly.index)
    etendu = etendre_ecarts_l1(poly, x)
    assert len(etendu.index) == 2 * len(poly.index)
    assert etendu.A.shape[1] == 2 * len(poly.index)
