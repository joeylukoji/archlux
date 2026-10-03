"""Propriétés du graphe de contraintes — `MILESTONE-2.md` §2.

Les deux propriétés qui comptent : aucune paire ne peut échapper à la séparation, et la
réduction transitive ne perd aucune information d'ordre.
"""

from __future__ import annotations

import itertools

from hypothesis import given, settings

from archlux.geom.graph import (
    RelativeOrder,
    build_graph,
    deduce_order,
    transitive_reduction,
)
from archlux.types import Plan
from tests.properties.strategies import ordres_valides, plans_quelconques


@given(plan=plans_quelconques())
@settings(max_examples=200, deadline=None)
def test_tout_plan_donne_un_ordre_acceptable(plan: Plan) -> None:
    """**Le contrat d'assemblage du pipeline.**

    ``deduire_ordre`` et ``construire_graphe`` peuvent être corrects isolément et la
    chaîne rester inutilisable. Cette propriété dit que le second accepte toujours ce
    que produit le premier — y compris sur des plans absurdes, qui sont l'entrée réelle
    du système.
    """
    ordre = deduce_order(plan)
    build_graph(ordre, list(ordre.rooms))


@given(ordre=ordres_valides())
@settings(max_examples=200, deadline=None)
def test_toute_paire_est_separee(ordre: RelativeOrder) -> None:
    """Sans séparation sur au moins un axe, le chevauchement reste possible."""
    graphe = build_graph(ordre, list(ordre.rooms))
    for a, b in itertools.combinations(ordre.rooms, 2):
        assert graphe.has_separation(a, b)


@given(ordre=ordres_valides())
@settings(max_examples=200, deadline=None)
def test_reduction_preserve_la_fermeture(ordre: RelativeOrder) -> None:
    """La réduction retire des arêtes, jamais de l'information.

    C'est ce qui autorise à réduire sans risque : les contraintes retirées restent
    impliquées par celles qui demeurent.
    """
    complet = build_graph(ordre, list(ordre.rooms))
    reduit = transitive_reduction(complet)
    assert complet.closure() == reduit.closure()


@given(ordre=ordres_valides())
@settings(max_examples=100, deadline=None)
def test_la_reduction_ne_grossit_jamais(ordre: RelativeOrder) -> None:
    """Le nombre d'arêtes ne peut que décroître — c'est la raison d'être de l'étape."""
    complet = build_graph(ordre, list(ordre.rooms))
    reduit = transitive_reduction(complet)
    for axis in ("horizontal", "vertical"):
        assert getattr(reduit, axis).number_of_edges() <= getattr(complet, axis).number_of_edges()
