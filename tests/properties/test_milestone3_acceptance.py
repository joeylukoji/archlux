"""Acceptance criteria of milestone 3. The milestone moves on when these tests pass.

The protocol stays **vector-based** (`ARCHITECTURE.md`): ``Surrogate`` is not widened to
``Plan`` / indicators. The trace of the iterates is that of Frank-Wolfe, not a new field
of ``legalize``.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

import archlux
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, freeze_contacts
from archlux.light.analytic import AnalyticSurrogate
from archlux.solve.trace import Trace
from archlux.types import Context, Orientation, Plan
from tests.properties.strategies import DEFAULT_CONTEXT, valid_plans

ANALYTIC = AnalyticSurrogate()


@given(plan=valid_plans())
@settings(max_examples=40, deadline=None)
def test_performance_output_is_valid(plan: Plan) -> None:
    """Every output of ``legalize(..., objective=)`` stays geometrically valid."""
    result = archlux.legalize(plan, DEFAULT_CONTEXT, objective=ANALYTIC)
    assert result.certificate is not None
    assert result.certificate.geometry.valid
    assert result.certificate.performance is None


@given(plan=valid_plans())
@settings(max_examples=25, deadline=None)
def test_every_iterate_is_valid(plan: Plan) -> None:
    """Every iterate stays in the FW domain: order of the *proposal* + frozen contacts.

    Rebuilding the polytope from ``deduce_order(result)`` is too strict: Frank-Wolfe
    works on ``freeze_contacts``, not on the order relaxation of the final point.
    """
    _result, trace = archlux.legalize_trace(plan, DEFAULT_CONTEXT, objective=ANALYTIC)
    assert isinstance(trace, Trace)
    assert trace.iterates
    poly = build_polytope(deduce_order(plan), DEFAULT_CONTEXT)
    poly_fw = freeze_contacts(poly, trace.iterates[0])
    assert all(poly_fw.contains(point, tol=1e-6) for point in trace.iterates)


@given(plan=valid_plans())
@settings(max_examples=20, deadline=None)
def test_monotone_objective(plan: Plan) -> None:
    _result, trace = archlux.legalize_trace(plan, DEFAULT_CONTEXT, objective=ANALYTIC)
    assert isinstance(trace, Trace)
    for before, after in pairwise(trace.values):
        assert after >= before - 1e-9


@given(theta=st.floats(0.0, 360.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=15, deadline=None)
def test_circular_orientation(theta: float) -> None:
    """``θ`` and ``θ + 360`` produce the same plan (periodic encoding)."""
    plan = archlux.Plan(
        rooms=(
            archlux.Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            archlux.Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )

    def _ctx(azimuth: float) -> Context:
        return Context(
            structure=DEFAULT_CONTEXT.structure,
            orientation=Orientation(deg=azimuth),
            outline=DEFAULT_CONTEXT.outline,
            regulation=DEFAULT_CONTEXT.regulation,
        )

    a = archlux.legalize(plan, _ctx(theta), objective=ANALYTIC)
    b = archlux.legalize(plan, _ctx(theta + 360.0), objective=ANALYTIC)
    xa = np.array([(p.x, p.y, p.w, p.h) for p in a.rooms])
    xb = np.array([(p.x, p.y, p.w, p.h) for p in b.rooms])
    assert np.allclose(xa, xb, atol=1e-6)


def test_no_regression_of_milestone2() -> None:
    """``objective=None`` stays the L1 legalization of milestone 2."""
    plan = archlux.Plan(
        rooms=(
            archlux.Room(id="a", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
            archlux.Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    classic = archlux.legalize(plan, DEFAULT_CONTEXT)
    explicit = archlux.legalize(plan, DEFAULT_CONTEXT, objective=None)
    assert classic.rooms == explicit.rooms
    assert classic.certificate is not None
    assert classic.certificate.geometry.valid
    assert classic.certificate.performance is None


def _grid_plan() -> archlux.Plan:
    """Four rooms in 2×2, enough freedom for north to move the dimensions."""
    return archlux.Plan(
        rooms=(
            archlux.Room(id="sw", type="living_room", x=0.0, y=0.0, w=6.0, h=4.5),
            archlux.Room(id="se", type="bedroom", x=6.0, y=0.0, w=6.0, h=4.5),
            archlux.Room(id="nw", type="living_room", x=0.0, y=4.5, w=6.0, h=4.5),
            archlux.Room(id="ne", type="bedroom", x=6.0, y=4.5, w=6.0, h=4.5),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )


def test_orientation_changes_the_plan() -> None:
    """North and south no longer return the same tiling: the deliverable of milestone 3."""

    def _ctx(deg: float) -> Context:
        return Context(
            structure=DEFAULT_CONTEXT.structure,
            orientation=Orientation(deg=deg),
            outline=DEFAULT_CONTEXT.outline,
            regulation=DEFAULT_CONTEXT.regulation,
        )

    plan = _grid_plan()
    north = archlux.legalize(plan, _ctx(0.0), objective=ANALYTIC)
    south = archlux.legalize(plan, _ctx(180.0), objective=ANALYTIC)
    xn = np.array([(p.x, p.y, p.w, p.h) for p in north.rooms])
    xs = np.array([(p.x, p.y, p.w, p.h) for p in south.rooms])
    assert not np.allclose(xn, xs, atol=1e-3)
    assert north.certificate is not None and north.certificate.geometry.valid
    assert south.certificate is not None and south.certificate.geometry.valid
    l1 = archlux.legalize(plan, _ctx(180.0))
    xl1 = np.array([(p.x, p.y, p.w, p.h) for p in l1.rooms])
    assert not np.allclose(xs, xl1, atol=1e-3)
