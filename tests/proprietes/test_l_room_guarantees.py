"""Exact guarantees with a fused (L, T, Z) room in the plan (PLAN.md batch 1.7).

Two adjacent rooms of a realistic scenario are merged into one fused room, decomposed
into the two rectangles they were. The output of ``legalize`` is checked by the
independent checker of ``tests/checkers.py``, which measures a fused room as a whole:
its recorded shared edge must hold, and the union must meet the room minimum.
"""

from __future__ import annotations

from dataclasses import replace

from hypothesis import assume, given, settings
from hypothesis import strategies as st

import archlux
from archlux.erreurs import ArchluxError
from archlux.geom.rectilineaire import FUSION_DROIT, FUSION_HAUT, PieceRectilineaire
from archlux.light.analytique import SubstitutAnalytique
from archlux.types import Contexte, Piece, Plan
from tests import checkers
from tests.proprietes.strategies import GATE_EXAMPLES, realistic_scenarios

_SETTINGS = settings(
    max_examples=GATE_EXAMPLES, deadline=None, derandomize=True, report_multiple_bugs=False
)
_EDGE = 1e-9
"""Two scenario edges closer than this coincide: the plans are drawn on a centimetre grid."""


def _fusion_kind(a: Piece, b: Piece) -> str | None:
    """How ``b`` continues ``a`` across a shared edge of positive length, if it does."""
    if abs(a.x + a.w - b.x) <= _EDGE and min(a.y + a.h, b.y + b.h) - max(a.y, b.y) > _EDGE:
        return FUSION_DROIT
    if abs(a.y + a.h - b.y) <= _EDGE and min(a.x + a.w, b.x + b.w) - max(a.x, b.x) > _EDGE:
        return FUSION_HAUT
    return None


@st.composite
def scenarios_with_a_fused_room(
    draw: st.DrawFn, *, fault: bool = True
) -> tuple[Plan, Contexte, PieceRectilineaire]:
    """A realistic scenario in which two adjacent rooms become one fused room.

    Both parts take the type of the first one. The union is larger than the first
    room, and the second room leaves its type, so every minimum area still holds: the
    input is valid under its own context. With ``fault``, another room may then be
    moved, so that legalize has to push the fused room.
    """
    plan, ctx = draw(realistic_scenarios())

    def fuse(a: Piece, b: Piece, kind: str) -> tuple[PieceRectilineaire, list[Piece]]:
        first = replace(a, id="fused__0")
        second = replace(b, id="fused__1", type=a.type)
        room = PieceRectilineaire(id="fused", rectangles=(first, second), fusions=((0, 1, kind),))
        return room, [first, second, *(r for r in plan.pieces if r is not a and r is not b)]

    # Only pairs that make one valid room: no load-bearing wall on their seam (it would
    # cut the room in two) and a seam at least ``largeur_min`` long.
    pairs = [
        (a, b, kind)
        for a in plan.pieces
        for b in plan.pieces
        if a is not b
        and (kind := _fusion_kind(a, b)) is not None
        and not checkers.violations(
            replace(plan, pieces=tuple(fuse(a, b, kind)[1])),
            ctx,
            fusions=(fuse(a, b, kind)[0],),
        )
    ]
    assume(pairs)
    a, b, kind = draw(st.sampled_from(pairs))
    room, rooms = fuse(a, b, kind)
    second = rooms[1]
    # The fault that slides a part: a neighbour of the second part pushed into it along
    # the shared edge, which the fusion equality alone does not resist.
    along = "y" if kind == FUSION_DROIT else "x"
    neighbours = [
        k
        for k in range(2, len(rooms))
        if _fusion_kind(rooms[k], second) or _fusion_kind(second, rooms[k])
    ]
    if fault and neighbours and draw(st.booleans()):
        k = draw(st.sampled_from(neighbours))
        shift = draw(st.sampled_from((-0.5, -0.25, 0.25, 0.5)))
        rooms[k] = replace(rooms[k], **{along: getattr(rooms[k], along) + shift})
    return replace(plan, pieces=tuple(rooms)), ctx, room


@_SETTINGS
@given(scenario=scenarios_with_a_fused_room(fault=False))
def test_the_fused_input_is_valid_under_its_own_context(
    scenario: tuple[Plan, Contexte, PieceRectilineaire],
) -> None:
    """Sanity check of the strategy: any later violation comes from legalize."""
    plan, ctx, room = scenario
    assert checkers.violations(plan, ctx, fusions=(room,)) == []


@_SETTINGS
@given(scenario=scenarios_with_a_fused_room())
def test_legalize_never_certifies_a_broken_fused_room(
    scenario: tuple[Plan, Contexte, PieceRectilineaire],
) -> None:
    """Either an honest, typed refusal or a plan whose fused room is still one room,
    with its minimum area met by the union, and every other exact guarantee kept."""
    plan, ctx, room = scenario
    for objective in (None, SubstitutAnalytique()):
        try:
            result = archlux.legalize(plan, ctx, objective=objective, fusions=(room,))
        except ArchluxError:
            continue  # refusing is allowed; lying is not
        assert checkers.violations(result, ctx, fusions=(room,)) == []
        assert _aligned_ends(result, room) == _aligned_ends(plan, room)


def _aligned_ends(plan: Plan, room: PieceRectilineaire) -> tuple[bool, bool]:
    """Whether the low ends, and the high ends, of the two parts coincide along the
    shared edge: the L-ness of the room, which ``legalize`` keeps."""
    by_id = {r.id: r for r in plan.pieces}
    a, b = (by_id[r.id] for r in room.rectangles)
    ((_, _, kind),) = room.fusions
    if kind == FUSION_DROIT:
        ends = ((a.y, b.y), (a.y + a.h, b.y + b.h))
    else:
        ends = ((a.x, b.x), (a.x + a.w, b.x + b.w))
    low, high = (abs(u - v) <= checkers.TOLERANCE for u, v in ends)
    return low, high
