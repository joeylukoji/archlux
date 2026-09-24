"""Propriétés de la vérification exacte — `MILESTONE-2.md` §6.

Les pavages en guillotine de :func:`plans_valides` sont exacts par construction
(centimètres entiers), sans filtrage par ``verify_exactly`` : le test n'est
pas tautologique.
"""

from __future__ import annotations

from hypothesis import given, settings

from archlux.certify.proof import verify_exactly
from archlux.types import Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides


@given(plan=plans_valides())
@settings(max_examples=200, deadline=None)
def test_un_plan_valide_passe(plan: Plan) -> None:
    preuve = verify_exactly(plan, CONTEXTE_DEFAUT)
    assert preuve.valide
    assert preuve.chevauchement is False
    assert preuve.jours is False
    assert preuve.surfaces_ok
    assert preuve.structure_preservee
