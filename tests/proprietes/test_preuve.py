"""Propriétés de la vérification exacte — `MILESTONE-2.md` §6.

Les pavages en guillotine de :func:`plans_valides` sont exacts par construction
(centimètres entiers), sans filtrage par ``verifier_exactement`` : le test n'est
pas tautologique.
"""

from __future__ import annotations

from hypothesis import given, settings

from archlux.certify.preuve import verifier_exactement
from archlux.types import Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides


@given(plan=plans_valides())
@settings(max_examples=200, deadline=None)
def test_un_plan_valide_passe(plan: Plan) -> None:
    preuve = verifier_exactement(plan, CONTEXTE_DEFAUT)
    assert preuve.valide
    assert preuve.chevauchement is False
    assert preuve.jours is False
    assert preuve.surfaces_ok
    assert preuve.structure_preservee
