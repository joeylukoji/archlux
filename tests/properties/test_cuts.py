"""Properties of the area cuts: `MILESTONE-2.md` §5.

Source of truth: the AM-GM inequality, not the code of ``area_cut``.
"""

from __future__ import annotations

import numpy as np
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from archlux.geom.polytope import build_polytope
from archlux.lmo.cuts import area_cut, solve_with_areas
from archlux.types import Context, Orientation, Regulation, Room, Structure
from tests.properties.strategies import valid_orders


@given(
    w0=st.floats(min_value=0.5, max_value=10.0, allow_nan=False),
    h0=st.floats(min_value=0.5, max_value=10.0, allow_nan=False),
    w=st.floats(min_value=0.5, max_value=20.0, allow_nan=False),
    h=st.floats(min_value=0.5, max_value=20.0, allow_nan=False),
)
@settings(max_examples=200, deadline=None)
def test_the_cut_excludes_no_valid_point(w0: float, h0: float, w: float, h: float) -> None:
    """Every tangent to {wh ≥ a} lets the points of large enough product through.

    AM-GM: (w/w₀ + h/h₀)/2 ≥ √(wh / (w₀ h₀)). On the hyperbola w₀ h₀ = a, this gives
    h₀ w + w₀ h ≥ 2a as soon as wh ≥ a.
    """
    a = w0 * h0
    assume(w * h + 1e-12 >= a)
    assert area_cut(w0, h0, a).satisfied(w, h)


@given(order=valid_orders(max_rooms=4))
@settings(max_examples=40, deadline=None)
def test_minimum_areas_are_respected(order: object) -> None:
    """After the cut loop, no room is below its a_min."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (20.0, 0.0), (20.0, 16.0), (0.0, 16.0)),
        regulation=Regulation(min_areas=(("living_room", 4.0),), min_width=1.0),
    )
    poly = build_polytope(order, ctx)  # type: ignore[arg-type]
    rooms = tuple(
        Room(id=name, type="living_room", x=0.0, y=0.0, w=1.0, h=1.0)
        for name in order.rooms  # type: ignore[attr-defined]
    )
    c = np.zeros(len(poly.index))
    for name, column in poly.index.items():
        if name.endswith(".w") or name.endswith(".h"):
            c[column] = 1.0
    sol = solve_with_areas(poly, c, ctx, rooms)
    if sol.status != "optimal":
        return
    for room in rooms:
        w = float(sol.x[poly.index[f"{room.id}.w"]])
        h = float(sol.x[poly.index[f"{room.id}.h"]])
        assert w * h >= 4.0 - 1e-6
