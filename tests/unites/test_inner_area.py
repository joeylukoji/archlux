"""Inner polyhedral approximation of the minimum areas (PLAN.md batch 1.2).

Frank-Wolfe mixed a valid start with vertices of an *outer* approximation of
``{w h >= a}`` (tangent cuts), so its iterates could fall below a minimum area
(AUDIT.md §3 n°6; benchmark: 167 of 200 refusals in performance mode). An *inner*
approximation, written as linear rows, keeps every point of the domain, hence every
convex combination, above the minimum area.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import archlux
from archlux.erreurs import InvariantViole
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import Polytope, construire_polytope, vectoriser
from archlux.light.analytique import SubstitutAnalytique
from archlux.lmo.coupes import inner_area_constraints
from archlux.types import Contexte, Orientation, Piece, Plan, Referentiel, Structure
from tests import checkers

_OUTLINE = ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0))


def _setup(w0: float, h0: float, a_min: float) -> tuple[Polytope, np.ndarray, Contexte, Plan]:
    """One room of w0 x h0 (plus a filler room) under a minimum area ``a_min``."""
    rooms = (
        Piece(id="r", type="chambre", x=0.0, y=0.0, w=w0, h=h0),
        Piece(id="f", type="couloir", x=w0, y=0.0, w=10.0 - w0, h=6.0),
    )
    plan = Plan(pieces=rooms, murs=(), ouvertures=(), contour=_OUTLINE)
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=_OUTLINE,
        referentiel=Referentiel(aires_min=(("chambre", a_min),), largeur_min=0.5),
    )
    poly = construire_polytope(deduire_ordre(plan), ctx)
    return poly, vectoriser(plan, poly.index), ctx, plan


def _satisfies_new_rows(poly: Polytope, inner: Polytope, w: float, h: float) -> bool:
    """Whether (w, h) of room ``r`` satisfies the rows and bounds added for it."""
    x = np.zeros(len(inner.index))
    x[inner.index["r.w"]], x[inner.index["r.h"]] = w, h
    n_old = poly.A.shape[0]
    ok_rows = bool(np.all(inner.A[n_old:] @ x <= inner.b[n_old:] + 1e-12))
    (w_lo, _), (h_lo, _) = inner.bornes[inner.index["r.w"]], inner.bornes[inner.index["r.h"]]
    return ok_rows and w >= w_lo - 1e-12 and h >= h_lo - 1e-12


def _boundary_height(poly: Polytope, inner: Polytope, w: float) -> float | None:
    """Lowest h admitted for room ``r`` at width ``w`` (None if w is below the bound)."""
    iw, ih = inner.index["r.w"], inner.index["r.h"]
    if w < inner.bornes[iw][0]:
        return None
    n_old = poly.A.shape[0]
    rows, rhs = inner.A[n_old:].toarray(), inner.b[n_old:]
    # Row: slope * w - h <= rhs  <=>  h >= slope * w - rhs.
    floors = [row[iw] * w - bound for row, bound in zip(rows, rhs, strict=True)]
    return max([inner.bornes[ih][0], *floors])


@settings(max_examples=400, deadline=None, derandomize=True)
@given(
    w0=st.floats(1.0, 8.0),
    aspect=st.floats(0.3, 3.0),
    slack=st.floats(1.0, 1.5),
    position=st.floats(0.0, 1.0),
    above=st.floats(0.0, 0.01),
)
def test_every_point_of_the_inner_region_keeps_the_minimum_area(
    w0: float, aspect: float, slack: float, position: float, above: float
) -> None:
    """Soundness, sampled where a defect would show: just above the region's boundary."""
    h0 = min(max(w0 * aspect, 0.6), 6.0)
    a_min = w0 * h0 / slack
    poly, x0, ctx, plan = _setup(w0, h0, a_min)
    inner = inner_area_constraints(poly, x0, ctx, plan.pieces)
    w_lo = inner.bornes[inner.index["r.w"]][0]
    w = w_lo + position * (4.0 * w0 - w_lo)
    floor = _boundary_height(poly, inner, w)
    assert floor is not None
    h = floor * (1.0 + above)
    assert _satisfies_new_rows(poly, inner, w, h)
    assert w * h >= a_min * (1 - 1e-9)


def test_the_soundness_check_detects_a_weakened_region() -> None:
    """Guard: rows built for 97 % of the area must be caught by the boundary sampling."""
    poly, x0, ctx, plan = _setup(4.0, 3.0, 12.0)
    weak_ctx = Contexte(
        structure=ctx.structure,
        orientation=ctx.orientation,
        contour=ctx.contour,
        referentiel=Referentiel(aires_min=(("chambre", 12.0 * 0.97),), largeur_min=0.5),
    )
    inner = inner_area_constraints(poly, x0, weak_ctx, plan.pieces)
    w = 4.0 * 1.25**0.5  # between two nodes
    floor = _boundary_height(poly, inner, w)
    assert floor is not None and w * floor < 12.0


@settings(max_examples=200, deadline=None)
@given(w0=st.floats(1.0, 8.0), aspect=st.floats(0.3, 3.0), slack=st.floats(1.0, 1.5))
def test_the_start_point_stays_admissible(w0: float, aspect: float, slack: float) -> None:
    h0 = min(max(w0 * aspect, 0.6), 6.0)  # within the base polytope (width >= 0.5)
    poly, x0, ctx, plan = _setup(w0, h0, w0 * h0 / slack)
    inner = inner_area_constraints(poly, x0, ctx, plan.pieces)
    assert inner.contient(x0)


def test_a_room_at_its_minimum_area_can_still_change_shape() -> None:
    """A single corner w >= w0, h >= h0 would freeze a tight room; chords must not."""
    poly, x0, ctx, plan = _setup(4.0, 3.0, 12.0)
    inner = inner_area_constraints(poly, x0, ctx, plan.pieces)
    wider = 4.0 * 1.2
    assert _satisfies_new_rows(poly, inner, wider, 12.0 / wider * 1.01)
    narrower = 4.0 / 1.2
    assert _satisfies_new_rows(poly, inner, narrower, 12.0 / narrower * 1.01)


def test_a_room_whose_height_is_fixed_can_still_narrow() -> None:
    """Review M1: a contact freezing h used to leave only w >= w0 instead of w >= a/h0."""
    poly, x0, ctx, plan = _setup(4.0, 6.0, 20.0)  # full height, 24 m² for 20 m² required
    ih = poly.index["r.h"]
    frozen = list(poly.bornes)
    frozen[ih] = (6.0, 6.0)
    poly = replace(poly, bornes=tuple(frozen))
    inner = inner_area_constraints(poly, x0, ctx, plan.pieces)
    assert _satisfies_new_rows(poly, inner, 3.45, 6.0)  # 20.7 m² >= 20 m², narrower


def test_a_start_below_the_minimum_area_is_refused() -> None:
    poly, x0, ctx, plan = _setup(4.0, 3.0, 12.5)  # 12 m² for 12.5 required
    with pytest.raises(InvariantViole, match="minimum area r"):
        inner_area_constraints(poly, x0, ctx, plan.pieces)


def test_rooms_without_minimum_area_get_no_row() -> None:
    poly, x0, ctx, plan = _setup(4.0, 3.0, 12.0)
    inner = inner_area_constraints(poly, x0, ctx, plan.pieces)
    labels = [o for o in inner.origines if o.startswith("minimum area")]
    assert labels and all(o.startswith("minimum area r:") for o in labels)


def test_performance_mode_keeps_tight_minimum_areas() -> None:
    """End to end, the case of the benchmark: 3 x 4 rooms with a_min = 11 m²."""
    outline = ((0.0, 0.0), (15.0, 0.0), (15.0, 12.0), (0.0, 12.0))
    rooms = tuple(
        Piece(id=f"p{i}_{j}", type="chambre", x=3.0 * i, y=4.0 * j, w=3.0, h=4.0)
        for i in range(5)
        for j in range(3)
    )
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=20.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(("chambre", 11.0),), largeur_min=1.0),
    )
    plan = Plan(pieces=rooms, murs=(), ouvertures=(), contour=outline)
    result = archlux.legalize(plan, ctx, objective=SubstitutAnalytique(), trace=True)
    assert checkers.violations(result, ctx) == []
    for iteration in result.trace.iteres:  # type: ignore[union-attr]
        areas = iteration.reshape(-1, 4)[:, 2] * iteration.reshape(-1, 4)[:, 3]
        assert np.all(areas >= 11.0 * (1 - 1e-9)), "every iterate keeps the minimum area"
