"""Propriétés de l'oracle linéaire — `MILESTONE-2.md` §4."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.geom.graph import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.solver import solve
from archlux.types import Context
from tests.properties.strategies import contextes, ordres_valides, vecteurs_objectifs


@given(ordre=ordres_valides(), ctx=contextes(), tirage=st.data())
@settings(max_examples=150, deadline=None)
def test_solution_est_admissible(ordre: RelativeOrder, ctx: Context, tirage: st.DataObject) -> None:
    """Toute solution rendue optimale appartient au polytope.

    La vérification passe par ``Polytope.contient``, qui n'emprunte rien au solveur :
    si GLOP se trompe, c'est elle qui l'attrape.
    """
    poly = build_polytope(ordre, ctx)
    c = tirage.draw(vecteurs_objectifs(len(poly.index)))
    sol = solve(poly, c)
    if sol.status == "optimal":
        assert poly.contains(sol.x, tol=1e-7)


@given(ordre=ordres_valides(), ctx=contextes(), tirage=st.data())
@settings(max_examples=100, deadline=None)
def test_le_demarrage_a_chaud_ne_change_pas_la_solution(
    ordre: RelativeOrder, ctx: Context, tirage: st.DataObject
) -> None:
    """Le démarrage à chaud accélère ; il ne doit rien décider.

    S'il changeait la solution, il changerait le certificat — et deux exécutions du même
    plan cesseraient d'être reproductibles, ce que le README interdit.
    """
    poly = build_polytope(ordre, ctx)
    c = tirage.draw(vecteurs_objectifs(len(poly.index)))
    froid = solve(poly, c)
    chaud = solve(poly, c, start=np.zeros(len(poly.index)))
    assert froid.status == chaud.status
    if froid.status == "optimal":
        assert froid.value == np.float64(chaud.value) or abs(froid.value - chaud.value) < 1e-6


@given(ordre=ordres_valides(), ctx=contextes())
@settings(max_examples=100, deadline=None)
def test_un_objectif_nul_rend_un_point_admissible(ordre: RelativeOrder, ctx: Context) -> None:
    """Avec ``c = 0``, le LP se réduit à une question de faisabilité.

    C'est le mode qu'utilisera ``certify`` pour distinguer « programme impossible » de
    « objectif mal choisi ».
    """
    poly = build_polytope(ordre, ctx)
    sol = solve(poly, np.zeros(len(poly.index)))
    assert sol.status in ("optimal", "infaisable")
    if sol.status == "optimal":
        assert poly.contains(sol.x, tol=1e-7)
    else:
        assert sol.farkas_certificate is not None
