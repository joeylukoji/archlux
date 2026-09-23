"""Critères d'acceptation du jalon 3. Le jalon avance quand ces tests passent.

Le protocole reste **vectoriel** (`ARCHITECTURE.md`) : on n'élargit pas ``Substitut``
à ``Plan`` / ``Indicateurs``. La trace des itérés est celle de Frank-Wolfe, pas un
champ nouveau de ``legalize``.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

import archlux
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, figer_contacts
from archlux.light.analytique import SubstitutAnalytique
from archlux.solve.trace import Trace
from archlux.types import Contexte, Orientation, Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides

ANALYTIQUE = SubstitutAnalytique()


@given(plan=plans_valides())
@settings(max_examples=40, deadline=None)
def test_sortie_performantielle_valide(plan: Plan) -> None:
    """Toute sortie de ``legalize(..., objective=)`` reste géométriquement valide."""
    resultat = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=ANALYTIQUE)
    assert resultat.certificat is not None
    assert resultat.certificat.geometrie.valide
    assert resultat.certificat.performance is None


@given(plan=plans_valides())
@settings(max_examples=25, deadline=None)
def test_tous_les_iteres_sont_valides(plan: Plan) -> None:
    """Chaque itéré reste dans le domaine FW : ordre du *proposé* + contacts figés.

    Reconstruire le polytope depuis ``deduire_ordre(resultat)`` est trop strict :
    Frank-Wolfe travaille sur ``figer_contacts``, pas sur le relaxé d'ordre du
    point final.
    """
    resultat = archlux.legalize(
        plan, CONTEXTE_DEFAUT, objective=ANALYTIQUE, trace=True
    )
    assert isinstance(resultat.trace, Trace)
    assert resultat.trace.iteres
    poly = construire_polytope(deduire_ordre(plan), CONTEXTE_DEFAUT)
    poly_fw = figer_contacts(poly, resultat.trace.iteres[0])
    assert all(poly_fw.contient(point, tol=1e-6) for point in resultat.trace.iteres)


@given(plan=plans_valides())
@settings(max_examples=20, deadline=None)
def test_objectif_monotone(plan: Plan) -> None:
    resultat = archlux.legalize(
        plan, CONTEXTE_DEFAUT, objective=ANALYTIQUE, trace=True
    )
    assert isinstance(resultat.trace, Trace)
    for avant, apres in pairwise(resultat.trace.objectif):
        assert apres >= avant - 1e-9


@given(theta=st.floats(0.0, 360.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=15, deadline=None)
def test_orientation_circulaire(theta: float) -> None:
    """``θ`` et ``θ + 360`` produisent le même plan (encodage périodique)."""
    plan = archlux.Plan(
        pieces=(
            archlux.Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            archlux.Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )

    def _ctx(azimut: float) -> Contexte:
        return Contexte(
            structure=CONTEXTE_DEFAUT.structure,
            orientation=Orientation(deg=azimut),
            contour=CONTEXTE_DEFAUT.contour,
            referentiel=CONTEXTE_DEFAUT.referentiel,
        )

    a = archlux.legalize(plan, _ctx(theta), objective=ANALYTIQUE)
    b = archlux.legalize(plan, _ctx(theta + 360.0), objective=ANALYTIQUE)
    xa = np.array([(p.x, p.y, p.w, p.h) for p in a.pieces])
    xb = np.array([(p.x, p.y, p.w, p.h) for p in b.pieces])
    assert np.allclose(xa, xb, atol=1e-6)


def test_non_regression_jalon2() -> None:
    """``objective=None`` reste la légalisation L1 du jalon 2."""
    plan = archlux.Plan(
        pieces=(
            archlux.Piece(id="a", type="sejour", x=0.0, y=0.0, w=7.0, h=9.0),
            archlux.Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    classique = archlux.legalize(plan, CONTEXTE_DEFAUT)
    explicite = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=None)
    assert classique.pieces == explicite.pieces
    assert classique.certificat is not None
    assert classique.certificat.geometrie.valide
    assert classique.certificat.performance is None


def _plan_grille() -> archlux.Plan:
    """Quatre pièces en 2×2, assez de liberté pour que le nord déplace les cotes."""
    return archlux.Plan(
        pieces=(
            archlux.Piece(id="sw", type="sejour", x=0.0, y=0.0, w=6.0, h=4.5),
            archlux.Piece(id="se", type="chambre", x=6.0, y=0.0, w=6.0, h=4.5),
            archlux.Piece(id="nw", type="sejour", x=0.0, y=4.5, w=6.0, h=4.5),
            archlux.Piece(id="ne", type="chambre", x=6.0, y=4.5, w=6.0, h=4.5),
        ),
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )


def test_orientation_change_le_plan() -> None:
    """Nord et sud ne rendent plus le même pavage — c'est le livrable du jalon 3."""

    def _ctx(deg: float) -> Contexte:
        return Contexte(
            structure=CONTEXTE_DEFAUT.structure,
            orientation=Orientation(deg=deg),
            contour=CONTEXTE_DEFAUT.contour,
            referentiel=CONTEXTE_DEFAUT.referentiel,
        )

    plan = _plan_grille()
    nord = archlux.legalize(plan, _ctx(0.0), objective=ANALYTIQUE)
    sud = archlux.legalize(plan, _ctx(180.0), objective=ANALYTIQUE)
    xn = np.array([(p.x, p.y, p.w, p.h) for p in nord.pieces])
    xs = np.array([(p.x, p.y, p.w, p.h) for p in sud.pieces])
    assert not np.allclose(xn, xs, atol=1e-3)
    assert nord.certificat is not None and nord.certificat.geometrie.valide
    assert sud.certificat is not None and sud.certificat.geometrie.valide
    l1 = archlux.legalize(plan, _ctx(180.0))
    xl1 = np.array([(p.x, p.y, p.w, p.h) for p in l1.pieces])
    assert not np.allclose(xs, xl1, atol=1e-3)

