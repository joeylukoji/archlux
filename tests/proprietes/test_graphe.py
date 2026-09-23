"""Propriétés du graphe de contraintes — `MILESTONE-2.md` §2.

Les deux propriétés qui comptent : aucune paire ne peut échapper à la séparation, et la
réduction transitive ne perd aucune information d'ordre.
"""

from __future__ import annotations

import itertools

from hypothesis import given, settings

from archlux.geom.graphe import (
    OrdreRelatif,
    construire_graphe,
    deduire_ordre,
    reduction_transitive,
)
from archlux.types import Plan
from tests.proprietes.strategies import ordres_valides, plans_quelconques


@given(plan=plans_quelconques())
@settings(max_examples=200, deadline=None)
def test_tout_plan_donne_un_ordre_acceptable(plan: Plan) -> None:
    """**Le contrat d'assemblage du pipeline.**

    ``deduire_ordre`` et ``construire_graphe`` peuvent être corrects isolément et la
    chaîne rester inutilisable. Cette propriété dit que le second accepte toujours ce
    que produit le premier — y compris sur des plans absurdes, qui sont l'entrée réelle
    du système.
    """
    ordre = deduire_ordre(plan)
    construire_graphe(ordre, list(ordre.pieces))


@given(ordre=ordres_valides())
@settings(max_examples=200, deadline=None)
def test_toute_paire_est_separee(ordre: OrdreRelatif) -> None:
    """Sans séparation sur au moins un axe, le chevauchement reste possible."""
    graphe = construire_graphe(ordre, list(ordre.pieces))
    for a, b in itertools.combinations(ordre.pieces, 2):
        assert graphe.a_separation(a, b)


@given(ordre=ordres_valides())
@settings(max_examples=200, deadline=None)
def test_reduction_preserve_la_fermeture(ordre: OrdreRelatif) -> None:
    """La réduction retire des arêtes, jamais de l'information.

    C'est ce qui autorise à réduire sans risque : les contraintes retirées restent
    impliquées par celles qui demeurent.
    """
    complet = construire_graphe(ordre, list(ordre.pieces))
    reduit = reduction_transitive(complet)
    assert complet.fermeture() == reduit.fermeture()


@given(ordre=ordres_valides())
@settings(max_examples=100, deadline=None)
def test_la_reduction_ne_grossit_jamais(ordre: OrdreRelatif) -> None:
    """Le nombre d'arêtes ne peut que décroître — c'est la raison d'être de l'étape."""
    complet = construire_graphe(ordre, list(ordre.pieces))
    reduit = reduction_transitive(complet)
    for axe in ("horizontal", "vertical"):
        assert getattr(reduit, axe).number_of_edges() <= getattr(complet, axe).number_of_edges()
