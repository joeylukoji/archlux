"""Tokenization: `MILESTONE-4.md` §3. Never an image."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from hypothesis import given, settings

from archlux.light.tokens import permute_rooms, plan_to_tokens
from tests.properties.strategies import DEFAULT_CONTEXT, valid_plans


@given(plan=valid_plans())
@settings(max_examples=25, deadline=None)
def test_continuous_tokens(plan) -> None:
    """Moving a wall by 2 cm must change the tokens: the anti-image test."""
    j1, _ = plan_to_tokens(plan, DEFAULT_CONTEXT)
    room = plan.rooms[0]
    moved = replace(
        plan,
        rooms=(replace(room, x=room.x + 0.02), *plan.rooms[1:]),
    )
    j2, _ = plan_to_tokens(moved, DEFAULT_CONTEXT)
    assert not np.allclose(j1, j2)


@given(plan=valid_plans())
@settings(max_examples=20, deadline=None)
def test_token_permutation_invariance(plan) -> None:
    """The order of the rooms does not change the mean of the set."""
    if len(plan.rooms) < 2:
        return
    j1, m1 = plan_to_tokens(plan, DEFAULT_CONTEXT)
    order = tuple(reversed(range(len(plan.rooms))))
    j2, m2 = plan_to_tokens(permute_rooms(plan, order), DEFAULT_CONTEXT)
    assert np.allclose(j1[~m1].mean(axis=0), j2[~m2].mean(axis=0), atol=1e-5)


def test_openings_are_distinct_tokens() -> None:
    """An opening is not copied onto each room: `MILESTONE-4.md` §4."""
    from archlux.types import Opening, Plan, Room, Wall

    wall = Wall(id="m0", a=(0.0, 0.0), b=(6.0, 0.0))
    opening = Opening(id="o0", wall_id="m0", s=0.5, relative_width=0.3)
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=4.5),
            Room(id="b", type="bedroom", x=6.0, y=0.0, w=6.0, h=4.5),
        ),
        walls=(wall,),
        openings=(opening,),
        outline=((0.0, 0.0), (12.0, 0.0), (12.0, 4.5), (0.0, 4.5)),
    )
    tokens, mask = plan_to_tokens(plan, DEFAULT_CONTEXT)
    assert tokens.shape[0] == 3
    assert not mask.any()
    assert np.allclose(tokens[0, 22:28], 0.0)
    assert np.allclose(tokens[1, 22:28], 0.0)
    assert not np.allclose(tokens[2, 22:28], 0.0)
