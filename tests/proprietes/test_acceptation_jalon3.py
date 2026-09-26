"""Critères d'acceptation du jalon 3. Le jalon avance quand ces tests passent.

Le protocole reste **vectoriel** (`ARCHITECTURE.md`) : on n'élargit pas ``Surrogate``
à ``Plan`` / ``Indicateurs``. La trace des itérés est celle de Frank-Wolfe, pas un
champ nouveau de ``legalize``.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

import archlux
from archlux.geom.graphe import deduce_order
from archlux.geom.polytope import build_polytope, freeze_contacts
from archlux.light.analytique import SubstitutAnalytique
from archlux.solve.trace import Trace
from archlux.types import Context, Orientation, Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides

ANALYTIQUE = SubstitutAnalytique()


@given(plan=plans_valides())
@settings(max_examples=40, deadline=None)
def test_sortie_performantielle_valide(plan: Plan) -> None:
    """Toute sortie de ``legalize(..., objective=)`` reste géométriquement valide."""
    resultat = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=ANALYTIQUE)
    assert resultat.certificate is not None
    assert resultat.certificate.geometry.valid
    assert resultat.certificate.performance is None


@given(plan=plans_valides())
@settings(max_examples=25, deadline=None)
def test_tous_les_iteres_sont_valides(plan: Plan) -> None:
    """Chaque itéré reste dans le domaine FW : ordre du *proposé* + contacts figés.

    Reconstruire le polytope depuis ``deduire_ordre(resultat)`` est trop strict :
    Frank-Wolfe travaille sur ``figer_contacts``, pas sur le relaxé d'ordre du
    point final.
    """
    resultat = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=ANALYTIQUE, trace=True)
    assert isinstance(resultat.trace, Trace)
    assert resultat.trace.iterates
    poly = build_polytope(deduce_order(plan), CONTEXTE_DEFAUT)
    poly_fw = freeze_contacts(poly, resultat.trace.iterates[0])
    assert all(poly_fw.contains(point, tol=1e-6) for point in resultat.trace.iterates)


@given(plan=plans_valides())
@settings(max_examples=20, deadline=None)
def test_objectif_monotone(plan: Plan) -> None:
    resultat = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=ANALYTIQUE, trace=True)
    assert isinstance(resultat.trace, Trace)
    for avant, apres in pairwise(resultat.trace.values):
        assert apres >= avant - 1e-9


@given(theta=st.floats(0.0, 360.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=15, deadline=None)
def test_orientation_circulaire(theta: float) -> None:
    """``θ`` et ``θ + 360`` produisent le même plan (encodage périodique)."""
    plan = archlux.Plan(
        rooms=(
            archlux.Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            archlux.Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )

    def _ctx(azimut: float) -> Context:
        return Context(
            structure=CONTEXTE_DEFAUT.structure,
            orientation=Orientation(deg=azimut),
            outline=CONTEXTE_DEFAUT.outline,
            regulation=CONTEXTE_DEFAUT.regulation,
        )

    a = archlux.legalize(plan, _ctx(theta), objective=ANALYTIQUE)
    b = archlux.legalize(plan, _ctx(theta + 360.0), objective=ANALYTIQUE)
    xa = np.array([(p.x, p.y, p.w, p.h) for p in a.rooms])
    xb = np.array([(p.x, p.y, p.w, p.h) for p in b.rooms])
    assert np.allclose(xa, xb, atol=1e-6)


def test_non_regression_jalon2() -> None:
    """``objective=None`` reste la légalisation L1 du jalon 2."""
    plan = archlux.Plan(
        rooms=(
            archlux.Room(id="a", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
            archlux.Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )
    classique = archlux.legalize(plan, CONTEXTE_DEFAUT)
    explicite = archlux.legalize(plan, CONTEXTE_DEFAUT, objective=None)
    assert classique.rooms == explicite.rooms
    assert classique.certificate is not None
    assert classique.certificate.geometry.valid
    assert classique.certificate.performance is None


def _plan_grille() -> archlux.Plan:
    """Quatre pièces en 2×2, assez de liberté pour que le nord déplace les cotes."""
    return archlux.Plan(
        rooms=(
            archlux.Room(id="sw", type="living_room", x=0.0, y=0.0, w=6.0, h=4.5),
            archlux.Room(id="se", type="bedroom", x=6.0, y=0.0, w=6.0, h=4.5),
            archlux.Room(id="nw", type="living_room", x=0.0, y=4.5, w=6.0, h=4.5),
            archlux.Room(id="ne", type="bedroom", x=6.0, y=4.5, w=6.0, h=4.5),
        ),
        walls=(),
        openings=(),
        outline=CONTEXTE_DEFAUT.outline,
    )


def test_orientation_change_le_plan() -> None:
    """Nord et sud ne rendent plus le même pavage — c'est le livrable du jalon 3."""

    def _ctx(deg: float) -> Context:
        return Context(
            structure=CONTEXTE_DEFAUT.structure,
            orientation=Orientation(deg=deg),
            outline=CONTEXTE_DEFAUT.outline,
            regulation=CONTEXTE_DEFAUT.regulation,
        )

    plan = _plan_grille()
    nord = archlux.legalize(plan, _ctx(0.0), objective=ANALYTIQUE)
    sud = archlux.legalize(plan, _ctx(180.0), objective=ANALYTIQUE)
    xn = np.array([(p.x, p.y, p.w, p.h) for p in nord.rooms])
    xs = np.array([(p.x, p.y, p.w, p.h) for p in sud.rooms])
    assert not np.allclose(xn, xs, atol=1e-3)
    assert nord.certificate is not None and nord.certificate.geometry.valid
    assert sud.certificate is not None and sud.certificate.geometry.valid
    l1 = archlux.legalize(plan, _ctx(180.0))
    xl1 = np.array([(p.x, p.y, p.w, p.h) for p in l1.rooms])
    assert not np.allclose(xs, xl1, atol=1e-3)
