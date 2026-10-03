"""Propriétés du polytope — `MILESTONE-2.md` §3.

La propriété qui compte : **un plan valide appartient à son propre polytope**. Si elle
tombe, c'est que la modélisation ne décrit pas l'ensemble qu'elle prétend décrire, et
tout ce qui suit — solveur, certificat — raisonne sur le mauvais domaine.
"""

from __future__ import annotations

from hypothesis import given, settings

from archlux.geom.graph import RelativeOrder, deduce_order
from archlux.geom.polytope import build_polytope, vectorize
from archlux.types import Context, Plan
from tests.properties.strategies import (
    CONTEXTE_DEFAUT,
    contextes,
    ordres_valides,
    plans_valides,
)


@given(ordre=ordres_valides(), ctx=contextes())
@settings(max_examples=200, deadline=None)
def test_dimensions_coherentes(ordre: RelativeOrder, ctx: Context) -> None:
    """Une origine par ligne, une colonne par variable."""
    poly = build_polytope(ordre, ctx)
    assert poly.A.shape[0] == len(poly.origins)
    assert poly.A.shape[1] == len(poly.index)
    assert poly.b.shape[0] == poly.A.shape[0]
    assert len(poly.bounds) == len(poly.index)


@given(plan=plans_valides())
@settings(max_examples=200, deadline=None)
def test_un_plan_valide_est_dans_le_polytope(plan: Plan) -> None:
    """Le contrat central de la modélisation.

    Un pavage exact du contour satisfait nécessairement l'ordre qu'on en déduit — sans
    quoi ``legalize`` déplacerait des murs sur un plan qui n'avait aucun défaut.
    """
    poly = build_polytope(deduce_order(plan), CONTEXTE_DEFAUT)
    assert poly.contains(vectorize(plan, poly.index), tol=1e-9)


@given(plan=plans_valides())
@settings(max_examples=100, deadline=None)
def test_la_legalisation_d_un_plan_valide_est_idempotente_en_domaine(plan: Plan) -> None:
    """Le point reste dans le polytope après aller-retour de vectorisation."""
    from archlux.geom.polytope import devectorize

    poly = build_polytope(deduce_order(plan), CONTEXTE_DEFAUT)
    point = vectorize(plan, poly.index)
    assert devectorize(point, plan, poly.index) == plan
