"""Propriétés de l'oracle linéaire — `MILESTONE-2.md` §4."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from archlux.geom.graphe import OrdreRelatif
from archlux.geom.polytope import construire_polytope
from archlux.lmo.solveur import resoudre
from archlux.types import Contexte
from tests.proprietes.strategies import contextes, ordres_valides, vecteurs_objectifs


@given(ordre=ordres_valides(), ctx=contextes(), tirage=st.data())
@settings(max_examples=150, deadline=None)
def test_solution_est_admissible(
    ordre: OrdreRelatif, ctx: Contexte, tirage: st.DataObject
) -> None:
    """Toute solution rendue optimale appartient au polytope.

    La vérification passe par ``Polytope.contient``, qui n'emprunte rien au solveur :
    si GLOP se trompe, c'est elle qui l'attrape.
    """
    poly = construire_polytope(ordre, ctx)
    c = tirage.draw(vecteurs_objectifs(len(poly.index)))
    sol = resoudre(poly, c)
    if sol.statut == "optimal":
        assert poly.contient(sol.x, tol=1e-7)


@given(ordre=ordres_valides(), ctx=contextes(), tirage=st.data())
@settings(max_examples=100, deadline=None)
def test_le_demarrage_a_chaud_ne_change_pas_la_solution(
    ordre: OrdreRelatif, ctx: Contexte, tirage: st.DataObject
) -> None:
    """Le démarrage à chaud accélère ; il ne doit rien décider.

    S'il changeait la solution, il changerait le certificat — et deux exécutions du même
    plan cesseraient d'être reproductibles, ce que le README interdit.
    """
    poly = construire_polytope(ordre, ctx)
    c = tirage.draw(vecteurs_objectifs(len(poly.index)))
    froid = resoudre(poly, c)
    chaud = resoudre(poly, c, depart=np.zeros(len(poly.index)))
    assert froid.statut == chaud.statut
    if froid.statut == "optimal":
        assert froid.valeur == np.float64(chaud.valeur) or abs(
            froid.valeur - chaud.valeur
        ) < 1e-6


@given(ordre=ordres_valides(), ctx=contextes())
@settings(max_examples=100, deadline=None)
def test_un_objectif_nul_rend_un_point_admissible(
    ordre: OrdreRelatif, ctx: Contexte
) -> None:
    """Avec ``c = 0``, le LP se réduit à une question de faisabilité.

    C'est le mode qu'utilisera ``certify`` pour distinguer « programme impossible » de
    « objectif mal choisi ».
    """
    poly = construire_polytope(ordre, ctx)
    sol = resoudre(poly, np.zeros(len(poly.index)))
    assert sol.statut in ("optimal", "infaisable")
    if sol.statut == "optimal":
        assert poly.contient(sol.x, tol=1e-7)
    else:
        assert sol.certificat_farkas is not None
