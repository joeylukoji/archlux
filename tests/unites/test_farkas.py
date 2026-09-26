"""Infeasibility certificates are named and checked exactly (PLAN.md batch 1.5c).

Before this batch, a conflict among the equalities of the tiling left the Farkas
auxiliary problem without an optimum: 68 of 200 noisy benchmark plans were refused with
"origines non renseignees", and no certificate was ever checked.
"""

from __future__ import annotations

import numpy as np
import pytest
from benchmarks.guarantees.measure import MODES
from benchmarks.guarantees.scenarios import generate

import archlux
from archlux.certify.farkas import verify_infeasibility
from archlux.errors import Infeasible
from archlux.geom.graphe import RelativeOrder
from archlux.geom.polytope import build_polytope
from archlux.lmo.solveur import solve
from archlux.types import Context, Orientation, Regulation, Structure

_CTX = Context(
    structure=Structure(load_bearing_walls=()),
    orientation=Orientation(deg=0.0),
    outline=((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)),
    regulation=Regulation(min_areas=(), min_width=2.0),
)
_TWO_ROOMS_IN_3M = build_polytope(
    RelativeOrder(horizontal=(("a", "b"),), vertical=(), rooms=("a", "b")), _CTX
)


def test_a_genuine_certificate_verifies_exactly() -> None:
    """Two rooms at least 2 m wide, side by side, in 3 m: no plan exists."""
    solution = solve(_TWO_ROOMS_IN_3M, np.zeros(8))
    assert solution.status == "infaisable"
    check = verify_infeasibility(
        _TWO_ROOMS_IN_3M, solution.farkas_certificate, solution.farkas_certificate_eq
    )
    assert check.verified and check.margin > 0


def test_a_forged_certificate_does_not_verify() -> None:
    """The checker trusts no one: random multipliers prove nothing."""
    forged = np.random.default_rng(3).random(_TWO_ROOMS_IN_3M.A.shape[0])
    assert not verify_infeasibility(_TWO_ROOMS_IN_3M, forged, None).verified


def test_a_feasible_system_never_verifies() -> None:
    wide = build_polytope(
        RelativeOrder(horizontal=(("a", "b"),), vertical=(), rooms=("a", "b")),
        Context(
            structure=_CTX.structure,
            orientation=_CTX.orientation,
            outline=((0.0, 0.0), (5.0, 0.0), (5.0, 3.0), (0.0, 3.0)),
            regulation=_CTX.regulation,
        ),
    )
    rng = np.random.default_rng(7)
    for _ in range(50):
        assert not verify_infeasibility(wide, rng.random(wide.A.shape[0]) * 10, None).verified


@pytest.mark.parametrize("index", range(12))
def test_tiling_conflicts_are_named_and_verified(index: int) -> None:
    """Noisy plans refused as infeasible now name their conflicting constraints."""
    mode = MODES["classic_noisy"]
    scenario = generate(17, index)
    try:
        archlux.legalize(mode.prepare(scenario), scenario.context, pavage=True)
    except Infeasible as refusal:
        assert refusal.origins, "an infeasibility must name its constraints"
        assert refusal.verified is True
    except archlux.ArchluxError:
        pass  # other refusals are not about infeasibility


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_a_non_finite_multiplier_is_not_verified(bad: float) -> None:
    """Review of batch 1.5, minor 3: a non-finite certificate fails, it does not raise."""
    y = np.ones(_TWO_ROOMS_IN_3M.A.shape[0])
    y[0] = bad
    check = verify_infeasibility(_TWO_ROOMS_IN_3M, y, None)
    assert not check.verified and check.reason == "non-finite multiplier"
