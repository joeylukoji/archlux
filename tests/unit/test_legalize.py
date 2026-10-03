"""Public API ``legalize``: `MILESTONE-2.md` §7."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import archlux
from archlux.api import gradient_distance
from archlux.errors import Infeasible
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, extend_l1_slack, vectorize
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure
from tests.properties.strategies import DEFAULT_CONTEXT


def test_gradient_distance_has_double_dimension() -> None:
    """c = (0_n, 1_n): the objective only bears on the deviations."""
    c = gradient_distance(np.ones(4))
    assert c.shape == (8,)
    assert np.allclose(c[:4], 0.0)
    assert np.allclose(c[4:], 1.0)


def test_l1_of_a_feasible_point_is_zero() -> None:
    """If x̂ ∈ P, min ||x − x̂||₁ = 0 and x★ = x̂ (Bertsimas–Tsitsiklis)."""
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    q = archlux.legalize(plan, DEFAULT_CONTEXT)
    assert q.certificate is not None
    assert q.certificate.geometry.valid
    assert q.certificate.geometry.max_displacement == pytest.approx(0.0, abs=1e-5)


def test_an_overlap_is_fixed() -> None:
    """Two rooms overlapping by 1 m in x, union = envelope, are separated.

    L1 prefers to shrink ``a.w`` by one metre rather than create a gap: after the fix
    the tiling stays exact (Bertsimas–Tsitsiklis, epigraph).
    """
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
            Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    q = archlux.legalize(plan, DEFAULT_CONTEXT)
    assert q.certificate is not None
    assert q.certificate.geometry.valid
    assert q.certificate.geometry.overlap is False
    left = next(p for p in q.rooms if p.id == "a")
    right = next(p for p in q.rooms if p.id == "b")
    assert left.x + left.w <= right.x + 1e-6


def test_a_programme_too_large_raises_infeasible() -> None:
    """Two rooms of min width 8 m in a 12 m envelope, side by side."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
        regulation=Regulation(min_areas=(), min_width=8.0),
    )
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=8.0, h=8.0),
            Room(id="b", type="living_room", x=8.0, y=0.0, w=8.0, h=8.0),
        ),
        walls=(),
        openings=(),
        outline=ctx.outline,
    )
    with pytest.raises(Infeasible) as capture:
        archlux.legalize(plan, ctx)
    assert capture.value.farkas_certificate is not None
    assert capture.value.origins


def test_min_width_larger_than_the_envelope_raises_infeasible() -> None:
    """Regression test: ``min_width`` > envelope is infeasible, not an internal bug.

    The bounds of ``w`` were then ``(min_width, xmax - xmin)``, an **inverted**
    interval: GLOP answered ``ABNORMAL``, translated into the status ``"limite"``, and
    ``legalize`` raised ``InvariantViolation`` ("internal bug") instead of ``Infeasible``,
    without any diagnostic, while the programme is indeed infeasible.
    """
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)),
        regulation=Regulation(min_areas=(), min_width=4.0),
    )
    plan = Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=3.0, h=3.0),),
        walls=(),
        openings=(),
        outline=ctx.outline,
    )
    with pytest.raises(Infeasible) as capture:
        archlux.legalize(plan, ctx)
    assert capture.value.origins
    assert any("minimum width" in origin for origin in capture.value.origins)


def test_a_polytope_without_rooms_tolerates_a_narrow_envelope() -> None:
    """No room: no ``w``/``h`` variable, hence nothing to declare infeasible."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)),
        regulation=Regulation(min_areas=(), min_width=4.0),
    )
    empty = Plan(rooms=(), walls=(), openings=(), outline=ctx.outline)
    poly = build_polytope(deduce_order(empty), ctx)
    assert poly.index == {}
    assert poly.bounds == ()


def test_an_invalid_objective_raises_typeerror() -> None:
    plan = Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=3.0, h=3.0),),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    with pytest.raises(TypeError, match="Surrogate"):
        archlux.legalize(plan, DEFAULT_CONTEXT, objective=object())  # type: ignore[arg-type]


def test_analytic_objective_stays_valid() -> None:
    from archlux.light.analytic import AnalyticSurrogate

    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    q = archlux.legalize(plan, DEFAULT_CONTEXT, objective=AnalyticSurrogate())
    assert q.certificate is not None
    assert q.certificate.geometry.valid
    assert q.certificate.performance is None


def test_legalize_trace_returns_the_iterates() -> None:
    from archlux.light.analytic import AnalyticSurrogate
    from archlux.solve.trace import Trace

    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    with pytest.warns(DeprecationWarning, match="legalize_trace"):
        q = archlux.legalize(plan, DEFAULT_CONTEXT, objective=AnalyticSurrogate(), trace=True)
    assert isinstance(q.trace, Trace)
    assert q.trace.iterates
    assert q.certificate is not None
    assert q.certificate.geometry.valid


def test_legalize_trace_positive_is_deprecated() -> None:
    """PLAN.md phase 4, block 2: ``trace=True`` still works, but points at the
    replacement."""
    plan = Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=12.0, h=9.0),),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    with pytest.warns(DeprecationWarning, match="legalize_trace") as caught:
        q = archlux.legalize(plan, DEFAULT_CONTEXT, trace=True)
    assert caught[0].filename == __file__  # the caller's line, not the alias wrapper
    assert q.trace is None  # classic mode: no Frank-Wolfe pass, nothing to warn about
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        archlux.legalize(plan, DEFAULT_CONTEXT)  # trace=False by default: no warning


def test_legalize_trace_returns_the_trace_instead_of_attaching_it() -> None:
    from archlux.light.analytic import AnalyticSurrogate
    from archlux.solve.trace import Trace

    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="living_room", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # legalize_trace must not warn about itself
        q, trace = archlux.legalize_trace(plan, DEFAULT_CONTEXT, objective=AnalyticSurrogate())
    assert q.trace is None  # the trace is returned, not attached
    assert isinstance(trace, Trace)
    assert trace.iterates
    assert q.certificate is not None
    assert q.certificate.geometry.valid


def test_legalize_trace_is_none_in_classic_mode() -> None:
    """No ``objective`` means no Frank-Wolfe pass: nothing to trace."""
    plan = Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=12.0, h=9.0),),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    q, trace = archlux.legalize_trace(plan, DEFAULT_CONTEXT)
    assert trace is None
    assert q.trace is None
    assert q.certificate is not None and q.certificate.geometry.valid


def test_zero_budget_stays_at_the_l1_point() -> None:
    """``budget=0`` forbids any performance move: the result stays at L1."""
    from archlux.light.analytic import AnalyticSurrogate

    plan = Plan(
        rooms=(
            Room(id="sw", type="living_room", x=0.0, y=0.0, w=6.0, h=4.5),
            Room(id="se", type="bedroom", x=6.0, y=0.0, w=6.0, h=4.5),
            Room(id="nw", type="living_room", x=0.0, y=4.5, w=6.0, h=4.5),
            Room(id="ne", type="bedroom", x=6.0, y=4.5, w=6.0, h=4.5),
        ),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    l1 = archlux.legalize(plan, DEFAULT_CONTEXT)
    blocked = archlux.legalize(plan, DEFAULT_CONTEXT, objective=AnalyticSurrogate(), budget=0.0)
    xl1 = np.array([(p.x, p.y, p.w, p.h) for p in l1.rooms])
    xb = np.array([(p.x, p.y, p.w, p.h) for p in blocked.rooms])
    assert np.allclose(xl1, xb, atol=1e-6)


def test_an_insufficient_area_is_enlarged() -> None:
    """Kelley + AM-GM: a 2×9 = 18 m² room under a_min = 20 m² is enlarged."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=DEFAULT_CONTEXT.outline,
        regulation=Regulation(min_areas=(("bathroom", 20.0),), min_width=1.0),
    )
    plan = Plan(
        rooms=(
            Room(id="bathroom", type="bathroom", x=0.0, y=0.0, w=2.0, h=9.0),
            Room(id="living_room", type="living_room", x=2.0, y=0.0, w=10.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=ctx.outline,
    )
    q = archlux.legalize(plan, ctx)
    bathroom = next(p for p in q.rooms if p.id == "bathroom")
    assert bathroom.area >= 20.0 - 1e-6
    assert q.certificate is not None
    assert q.certificate.geometry.valid


def test_extend_l1_doubles_the_variables() -> None:
    plan = Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=3.0, h=3.0),),
        walls=(),
        openings=(),
        outline=DEFAULT_CONTEXT.outline,
    )
    poly = build_polytope(deduce_order(plan), DEFAULT_CONTEXT)
    x = vectorize(plan, poly.index)
    extended = extend_l1_slack(poly, x)
    assert len(extended.index) == 2 * len(poly.index)
    assert extended.A.shape[1] == 2 * len(poly.index)
