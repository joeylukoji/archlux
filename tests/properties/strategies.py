"""Hypothesis strategies shared by every milestone.

This module is the hidden deliverable of milestone 1: the acceptance test of milestone 2,
the cut tests and the drift tests all reuse it. Written once, correctly, it avoids three
diverging plan generators.

Strategies that are not needed yet raise ``NotImplementedError`` with their milestone:
writing them ahead of time would produce generators never run, hence never correct.
"""

from __future__ import annotations

import itertools
import os
from typing import Any

import numpy as np
from hypothesis import strategies as st

from archlux.geom.graph import RelativeOrder
from archlux.types import (
    REGIMES,
    Certificate,
    Context,
    GeometricProof,
    Manifest,
    ModelTrace,
    Opening,
    Orientation,
    PerformanceBound,
    Plan,
    Regulation,
    Room,
    Structure,
    Wall,
)

__all__ = [
    "DEFAULT_CONTEXT",
    "arbitrary_plans",
    "contexts",
    "objective_vectors",
    "realistic_scenarios",
    "rooms",
    "valid_orders",
    "valid_plans",
    "walls",
]

_COORD = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)
_SIZE = st.floats(min_value=0.1, max_value=1e3, allow_nan=False, allow_infinity=False)
_UNIT = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_IDS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789", min_size=1, max_size=8)
_TYPES = st.sampled_from(["living_room", "bedroom", "kitchen", "bathroom", "corridor", "toilet"])


def rooms() -> st.SearchStrategy[Room]:
    """Arbitrary rectangular rooms, with strictly positive dimensions."""
    return st.builds(Room, id=_IDS, type=_TYPES, x=_COORD, y=_COORD, w=_SIZE, h=_SIZE)


def walls() -> st.SearchStrategy[Wall]:
    """Arbitrary walls, load-bearing or not."""
    return st.builds(
        Wall,
        id=_IDS,
        a=st.tuples(_COORD, _COORD),
        b=st.tuples(_COORD, _COORD),
        load_bearing=st.booleans(),
        thickness=st.floats(min_value=0.05, max_value=0.6, allow_nan=False),
    )


def _openings(wall_ids: list[str]) -> st.SearchStrategy[Opening]:
    return st.builds(
        Opening,
        id=_IDS,
        wall_id=st.sampled_from(wall_ids),
        s=_UNIT,
        relative_width=st.floats(
            min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
        sill_height=st.floats(min_value=0.0, max_value=1.5, allow_nan=False),
        head_height=st.floats(min_value=1.6, max_value=3.0, allow_nan=False),
    )


def _proofs() -> st.SearchStrategy[GeometricProof]:
    """Geometric proofs, **with** violations that are sometimes non-empty.

    A generator that only produced ``violations=()`` would make the serialization of
    this field unreachable: the test would look exhaustive while never running the
    branch.
    """
    return st.builds(
        _proof,
        valid=st.booleans(),
        overlap=st.booleans(),
        gaps=st.booleans(),
        areas_ok=st.booleans(),
        structure_kept=st.booleans(),
        max_displacement=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        violations=st.lists(st.text(max_size=40), max_size=3).map(tuple),
    )


def _proof(*, valid: bool, **fields: Any) -> GeometricProof:
    """A ``valid`` proof reports no fault (invariant of ``types``, phase 3.2)."""
    if valid:
        fields |= {
            "overlap": False,
            "gaps": False,
            "areas_ok": True,
            "structure_kept": True,
            "violations": (),
        }
    return GeometricProof(valid=valid, **fields)


def _bounds() -> st.SearchStrategy[PerformanceBound]:
    """Conformal bounds, always with their coverage and ``n_calibration``."""
    reals = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    # An interval is ordered (batch 1.6 refuses lower > upper).
    return st.tuples(reals, reals).flatmap(
        lambda pair: st.builds(
            PerformanceBound,
            indicator=st.sampled_from(["sDA", "ASE", "UDI", "vue"]),
            value=reals,
            lower=st.just(min(pair)),
            upper=st.just(max(pair)),
            coverage=st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
            n_calibration=st.integers(min_value=1, max_value=100_000),
            regime=st.sampled_from(REGIMES),
        )
    )


def _manifests() -> st.SearchStrategy[Manifest]:
    """Reproducibility manifests, optional fields sometimes filled in."""
    pairs = st.lists(st.tuples(st.text(max_size=12), st.text(max_size=12)), max_size=3).map(tuple)
    models = st.one_of(
        st.none(),
        st.builds(
            ModelTrace,
            weights_fingerprint=st.text(min_size=1, max_size=32),
            calibration_n=st.integers(min_value=1, max_value=10_000),
            alpha=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
        ),
    )
    return st.builds(
        Manifest,
        version=st.text(min_size=1, max_size=10),
        timestamp=st.text(min_size=1, max_size=32),
        seed=st.integers(min_value=0, max_value=2**32 - 1),
        data_fingerprint=st.one_of(st.none(), st.text(max_size=20)),
        split=st.one_of(st.none(), st.text(max_size=20)),
        environment=pairs,
        parameters=pairs,
        model=models,
    )


def _certificates() -> st.SearchStrategy[Certificate]:
    """Complete certificates: both guarantees, the dual diagnostic and the trace.

    ``performance`` is ``None`` **half of the time**, not always: both modes (classic
    without a bound, performance with a bound) must go through serialization.
    """
    return st.builds(
        Certificate,
        geometry=_proofs(),
        performance=st.one_of(st.none(), _bounds()),
        duals=st.lists(
            st.tuples(
                st.text(max_size=20),
                st.floats(min_value=-1e3, max_value=1e3, allow_nan=False),
            ),
            max_size=3,
        ).map(tuple),
        manifest=st.one_of(st.none(), _manifests()),
    )


@st.composite
def arbitrary_plans(draw: st.DrawFn) -> Plan:
    """Arbitrary plans, valid or not: the real input of the system.

    This is deliberately permissive: ``legalize`` must return a valid plan *even* on an
    absurd input, and a generator that only produced plausible plans would not test
    that promise.
    """
    wall_list = draw(st.lists(walls(), min_size=1, max_size=6, unique_by=lambda m: m.id))
    wall_ids = [m.id for m in wall_list]
    room_list = draw(st.lists(rooms(), min_size=1, max_size=6, unique_by=lambda p: p.id))
    opening_list = draw(st.lists(_openings(wall_ids), max_size=5, unique_by=lambda o: o.id))
    outline = draw(st.lists(st.tuples(_COORD, _COORD), min_size=3, max_size=8))
    certificate = draw(st.one_of(st.none(), _certificates()))
    return Plan(
        rooms=tuple(room_list),
        walls=tuple(wall_list),
        openings=tuple(opening_list),
        outline=tuple(outline),
        certificate=certificate,
    )


GATE_EXAMPLES = int(os.environ.get("ARCHLUX_GATE_EXAMPLES", "60"))
"""Examples per guarantee property: 60 in CI, 2000 for the phase 1 exit gate (PLAN.md)."""

DEFAULT_MIN_WIDTH = 1.0
"""Minimum width of the reference context, in metres."""

DEFAULT_OUTLINE_CM = (1200, 900)
"""Reference outline, in **centimetres**: 12 m x 9 m."""

DEFAULT_CONTEXT = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    regulation=Regulation(min_areas=(), min_width=DEFAULT_MIN_WIDTH),
)
"""Reference context of the tests, matched to :func:`valid_plans`."""


def _cut_up(
    draw: st.DrawFn,
    x: int,
    y: int,
    w: int,
    h: int,
    depth: int,
    minimum: int,
    force_split: bool = False,
) -> list[tuple[int, int, int, int]]:
    """Cut a rectangle up recursively into a guillotine tiling, in centimetres.

    The cuts are integers: adding centimetres stays exact, where floating cuts would
    leave gaps of the order of 1e-16 between neighbouring rooms.

    ``force_split`` makes the first cut mandatory (when the rectangle allows one), so
    that the plan has at least two rooms.
    """
    axes = [axis for axis, size in (("v", w), ("h", h)) if size >= 2 * minimum]
    if depth == 0 or not axes or (not force_split and not draw(st.booleans())):
        return [(x, y, w, h)]
    axis = draw(st.sampled_from(axes))
    if axis == "v":
        cut = draw(st.integers(min_value=minimum, max_value=w - minimum))
        left = _cut_up(draw, x, y, cut, h, depth - 1, minimum)
        return left + _cut_up(draw, x + cut, y, w - cut, h, depth - 1, minimum)
    cut = draw(st.integers(min_value=minimum, max_value=h - minimum))
    low = _cut_up(draw, x, y, w, cut, depth - 1, minimum)
    return low + _cut_up(draw, x, y + cut, w, h - cut, depth - 1, minimum)


@st.composite
def valid_plans(draw: st.DrawFn, depth: int = 3, force_split: bool = False) -> Plan:
    """Geometrically valid plans, matched to :data:`DEFAULT_CONTEXT`.

    Built by **guillotine cuts**: the outline is cut recursively in two, and the leaves
    become the rooms. The tiling is then exact by construction (no overlap, no gap)
    without any geometric check on the generator side.

    That is the important point: a generator that called ``verify_exactly`` to filter
    its outputs would make every validity test tautological.

    Notes
    -----
    The plans produced are guillotine tilings, which do not cover every valid plan: a
    "pinwheel" tiling is not reachable. This is a known and accepted limit: it narrows
    the coverage, it does not distort any test.
    """
    width, height = DEFAULT_OUTLINE_CM
    minimum = int(DEFAULT_MIN_WIDTH * 100)
    rectangles = _cut_up(draw, 0, 0, width, height, depth, minimum, force_split=force_split)
    rooms = tuple(
        Room(
            id=f"p{i}",
            type=draw(_TYPES),
            x=x / 100.0,
            y=y / 100.0,
            w=w / 100.0,
            h=h / 100.0,
        )
        for i, (x, y, w, h) in enumerate(rectangles)
    )
    return Plan(
        rooms=rooms,
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )


@st.composite
def valid_orders(draw: st.DrawFn, max_rooms: int = 6) -> RelativeOrder:
    """Acyclic relative orders in which every pair is separated.

    Built **without reusing ``deduce_order``**: two total ranks drawn at random, one per
    axis, then an axis chosen by a coin flip for each pair. The edge follows the rank of
    the chosen axis.

    Both expected properties then hold by construction, for reasons independent of the
    code under test:

    - **acyclic**, because the edges of an axis follow a total order;
    - **every pair separated**, because each pair receives exactly one edge.

    Deriving these orders from the production code would make the tests tautological:
    they would pass whatever the error made on both sides.
    """
    count = draw(st.integers(min_value=2, max_value=max_rooms))
    names = [f"p{i}" for i in range(count)]
    rank_x = {name: i for i, name in enumerate(draw(st.permutations(names)))}
    rank_y = {name: i for i, name in enumerate(draw(st.permutations(names)))}

    horizontal: list[tuple[str, str]] = []
    vertical: list[tuple[str, str]] = []
    for a, b in itertools.combinations(sorted(names), 2):
        if draw(st.booleans()):
            horizontal.append((a, b) if rank_x[a] < rank_x[b] else (b, a))
        else:
            vertical.append((a, b) if rank_y[a] < rank_y[b] else (b, a))

    return RelativeOrder(
        horizontal=tuple(horizontal),
        vertical=tuple(vertical),
        rooms=tuple(sorted(names)),
    )


@st.composite
def contexts(draw: st.DrawFn) -> Context:
    """Consistent contexts: rectangular outline, orientation, regulation.

    The load-bearing structure is empty: tying a room to a load-bearing wall needs an
    incidence that ``build_polytope(order, ctx)`` has no means to compute (see the
    ADR-7 note in the blueprint).
    """
    width = draw(st.floats(min_value=5.0, max_value=30.0, allow_nan=False))
    height = draw(st.floats(min_value=5.0, max_value=30.0, allow_nan=False))
    return Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=draw(st.floats(0.0, 360.0, allow_nan=False))),
        outline=((0.0, 0.0), (width, 0.0), (width, height), (0.0, height)),
        regulation=Regulation(
            min_areas=(),
            min_width=draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False)),
        ),
    )


def objective_vectors(dimension: int) -> st.SearchStrategy[np.ndarray]:
    """Bounded cost vectors, **of any origin**, as ``lmo`` sees them.

    The generator knows no more than the solver where the vector comes from: geometric
    distance at milestone 2, illuminance gradient at milestone 3. The tests must reflect
    that ignorance.
    """
    return st.lists(
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False),
        min_size=dimension,
        max_size=dimension,
    ).map(lambda values: np.array(values, dtype=float))


@st.composite
def realistic_scenarios(draw: st.DrawFn) -> tuple[Plan, Context]:
    """Valid plan plus a context that actually constrains it (PLAN.md, task 0.8).

    Every other strategy uses ``min_areas=()`` and no load-bearing wall, which is how the
    critical defects of AUDIT.md §3 went unnoticed. Here:

    - one load-bearing wall lies on a real partition of the plan (a room edge that is
      not on the outline), so the input respects it;
    - each room type present gets a minimum area between 50 % and 100 % of its smallest
      room, the tight case included, so the input satisfies every minimum;
    - the orientation is arbitrary.

    The input is therefore valid under its own context: any violation in the output is
    introduced by ``legalize``.
    """
    plan = draw(valid_plans(force_split=True))
    width, height = (c / 100.0 for c in DEFAULT_OUTLINE_CM)

    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for room in plan.rooms:
        right, top = room.x + room.w, room.y + room.h
        if right < width - 1e-9:
            edges.append(((right, room.y), (right, top)))
        if top < height - 1e-9:
            edges.append(((room.x, top), (right, top)))
    # At least two rooms (force_split), hence at least one interior edge.
    a, b = draw(st.sampled_from(edges))
    load_bearing_walls = (Wall(id="lb0", a=a, b=b, load_bearing=True),)

    smallest: dict[str, float] = {}
    for room in plan.rooms:
        smallest[room.type] = min(smallest.get(room.type, float("inf")), room.w * room.h)
    ratio = draw(st.floats(min_value=0.5, max_value=1.0, allow_nan=False))
    minimum_areas = tuple(sorted((kind, ratio * area) for kind, area in smallest.items()))

    context = Context(
        structure=Structure(load_bearing_walls=load_bearing_walls),
        orientation=Orientation(deg=draw(st.floats(0.0, 360.0, allow_nan=False))),
        outline=DEFAULT_CONTEXT.outline,
        regulation=Regulation(min_areas=minimum_areas, min_width=DEFAULT_MIN_WIDTH),
    )
    return Plan(
        rooms=plan.rooms, walls=load_bearing_walls, openings=(), outline=plan.outline
    ), context
