"""Types refuse incoherent values at construction (PLAN.md phase 3, slice B: 3.2, 3.5, 3.7)."""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from archlux import GeometricProof, InvalidInput, Opening, Orientation, Plan
from archlux.types import Context, Regulation, Structure
from tests.unites.test_hostile_inputs import SQUARE, make_plan


def proof(**changes: object) -> GeometricProof:
    """A coherent, valid proof with ``changes`` applied."""
    fields: dict[str, object] = {
        "valid": True,
        "overlap": False,
        "gaps": False,
        "areas_ok": True,
        "structure_kept": True,
        "max_displacement": 0.0,
        "violations": (),
    }
    fields.update(changes)
    return GeometricProof(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"overlap": True},
        {"gaps": True},
        {"areas_ok": False},
        {"structure_kept": False},
        {"violations": ("overlap a|b",)},
    ],
)
def test_a_valid_proof_cannot_report_a_fault(changes: dict[str, object]) -> None:
    with pytest.raises(InvalidInput, match="valid"):
        proof(**changes)


def test_an_invalid_proof_may_report_anything() -> None:
    assert not proof(valid=False, overlap=True, violations=("x",)).valid


@pytest.mark.parametrize("value", [-0.1, math.nan])
def test_displacement_is_never_negative_or_nan(value: float) -> None:
    with pytest.raises(InvalidInput, match="max_displacement"):
        proof(max_displacement=value)


def test_unbounded_displacement_is_allowed_on_an_invalid_proof() -> None:
    """The proof reports ``inf`` for a NaN reference (final review of phase 1)."""
    assert proof(valid=False, max_displacement=math.inf).max_displacement == math.inf


@pytest.mark.parametrize(("s", "width"), [(2.0, 0.2), (-0.1, 0.2), (0.5, 0.0), (0.5, 1.5)])
def test_opening_ranges(s: float, width: float) -> None:
    with pytest.raises(InvalidInput):
        Opening(id="o", wall_id="m", s=s, relative_width=width)


def test_opening_on_the_boundary_is_allowed() -> None:
    assert Opening(id="o", wall_id="m", s=1.0, relative_width=1.0).s == 1.0


def test_a_plan_with_a_trace_is_hashable_and_equal_without_it() -> None:
    plain = make_plan()
    traced = Plan(
        rooms=plain.rooms,
        walls=plain.walls,
        openings=plain.openings,
        outline=plain.outline,
        trace=np.zeros(3),
    )
    assert hash(traced) == hash(plain)
    assert traced == plain


def test_unknown_room_type_warns_when_the_regulation_has_thresholds() -> None:
    from archlux import legalize

    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=SQUARE,
        regulation=Regulation(min_areas=(("sejour", 1.0),), min_width=1.0),
    )
    typo = make_plan(type="sejuor")
    with pytest.warns(UserWarning, match="sejuor"):
        legalize(typo, ctx)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        legalize(make_plan(), ctx)


def test_no_warning_when_the_regulation_has_no_threshold() -> None:
    from archlux import legalize
    from tests.unites.test_hostile_inputs import make_context

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        legalize(make_plan(type="anything"), make_context())
