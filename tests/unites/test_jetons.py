"""Tokenisation — `MILESTONE-4.md` §3. Jamais une image."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from hypothesis import given, settings

from archlux.light.jetons import permuter_pieces, plan_vers_jetons
from tests.proprietes.strategies import CONTEXTE_DEFAUT, plans_valides


@given(plan=plans_valides())
@settings(max_examples=25, deadline=None)
def test_jetons_continus(plan) -> None:
    """Déplacer un mur de 2 cm doit changer les jetons — test anti-image."""
    j1, _ = plan_vers_jetons(plan, CONTEXTE_DEFAUT)
    piece = plan.rooms[0]
    deplace = replace(
        plan,
        rooms=(replace(piece, x=piece.x + 0.02), *plan.rooms[1:]),
    )
    j2, _ = plan_vers_jetons(deplace, CONTEXTE_DEFAUT)
    assert not np.allclose(j1, j2)


@given(plan=plans_valides())
@settings(max_examples=20, deadline=None)
def test_invariance_par_permutation_des_jetons(plan) -> None:
    """L'ordre des pièces ne change pas la moyenne de l'ensemble."""
    if len(plan.rooms) < 2:
        return
    j1, m1 = plan_vers_jetons(plan, CONTEXTE_DEFAUT)
    ordre = tuple(reversed(range(len(plan.rooms))))
    j2, m2 = plan_vers_jetons(permuter_pieces(plan, ordre), CONTEXTE_DEFAUT)
    assert np.allclose(j1[~m1].mean(axis=0), j2[~m2].mean(axis=0), atol=1e-5)


def test_ouvertures_sont_des_jetons_distincts() -> None:
    """Une baie n'est pas recopiée sur chaque pièce — `MILESTONE-4.md` §4."""
    from archlux.types import Opening, Plan, Room, Wall

    mur = Wall(id="m0", a=(0.0, 0.0), b=(6.0, 0.0))
    ouv = Opening(id="o0", wall_id="m0", s=0.5, relative_width=0.3)
    plan = Plan(
        rooms=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=4.5),
            Room(id="b", type="chambre", x=6.0, y=0.0, w=6.0, h=4.5),
        ),
        walls=(mur,),
        openings=(ouv,),
        outline=((0.0, 0.0), (12.0, 0.0), (12.0, 4.5), (0.0, 4.5)),
    )
    jetons, masque = plan_vers_jetons(plan, CONTEXTE_DEFAUT)
    assert jetons.shape[0] == 3
    assert not masque.any()
    assert np.allclose(jetons[0, 22:28], 0.0)
    assert np.allclose(jetons[1, 22:28], 0.0)
    assert not np.allclose(jetons[2, 22:28], 0.0)
