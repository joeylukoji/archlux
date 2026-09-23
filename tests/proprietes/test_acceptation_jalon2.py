"""Critère d'acceptation du jalon 2. Le jalon est terminé quand ce test passe.

Un seul test, une seule propriété : *toute* sortie de ``legalize`` est géométriquement
valide. Les pavages en guillotine de :func:`plans_valides` sont le domaine où un
plan valide existe toujours dans l'enveloppe ; 500 exemples, deadline levée.
"""

from __future__ import annotations

from hypothesis import given, settings

import archlux
from archlux.types import Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides


@given(plan=plans_valides())
@settings(max_examples=500, deadline=None)
def test_toute_sortie_est_valide(plan: Plan) -> None:
    """`MILESTONE-2.md` §0 : le critère d'acceptation unique du jalon."""
    resultat = archlux.legalize(plan, CONTEXTE_DEFAUT)
    assert resultat.certificat is not None
    assert resultat.certificat.geometrie.valide
    assert resultat.certificat.performance is None
