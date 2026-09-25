"""Hostile inputs are refused at the door with a typed, actionable error.

PLAN.md phase 3, slice A (3.1, 3.3, 3.4). Before it, a negative width surfaced as
``InvariantViolation: gap`` (an internal-bug exception for a typo) and ``nan`` as an LP status.
Now every case raises ``InvalidInput``, which names the offending field.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from archlux import (
    Context,
    InvalidInput,
    Orientation,
    Plan,
    Regulation,
    Room,
    Structure,
    legalize,
)

SQUARE = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def make_plan(**changes: object) -> Plan:
    """Two valid rooms side by side, with ``changes`` applied to the first one."""
    first = replace(Room(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0), **changes)  # type: ignore[arg-type]
    second = Room(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0)
    return Plan(pieces=(first, second), murs=(), ouvertures=(), contour=SQUARE)


def make_context(*, degrees: float = 0.0, largeur_min: float = 1.0) -> Context:
    """Empty structure, square outline, no minimum areas."""
    return Context(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=degrees),
        contour=SQUARE,
        referentiel=Regulation(aires_min=(), largeur_min=largeur_min),
    )


def test_valid_input_is_accepted() -> None:
    assert legalize(make_plan(), make_context()).certificat is not None


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"w": -1.0}, "w"),
        ({"h": 0.0}, "h"),
        ({"w": math.nan}, "w"),
        ({"x": math.inf}, "x"),
        ({"y": "0"}, "y"),
        ({"id": ""}, "id"),
    ],
)
def test_bad_room_field_names_the_field(changes: dict[str, object], field: str) -> None:
    with pytest.raises(InvalidInput) as raised:
        legalize(make_plan(**changes), make_context())
    assert raised.value.field.endswith(field)
    assert "a" in str(raised.value)


def test_duplicate_room_ids_are_refused() -> None:
    with pytest.raises(InvalidInput, match="duplicate"):
        legalize(make_plan(id="b"), make_context())


def test_plan_without_room_is_refused() -> None:
    empty = Plan(pieces=(), murs=(), ouvertures=(), contour=SQUARE)
    with pytest.raises(InvalidInput, match="no room"):
        legalize(empty, make_context())


@pytest.mark.parametrize("budget", [-1.0, math.nan, math.inf])
def test_bad_budget_is_refused(budget: float) -> None:
    with pytest.raises(InvalidInput) as raised:
        legalize(make_plan(), make_context(), budget=budget)
    assert raised.value.field == "budget"


def test_bad_repair_budget_is_refused() -> None:
    with pytest.raises(InvalidInput) as raised:
        legalize(make_plan(), make_context(), pavage=True, budget_reparation=-1)
    assert raised.value.field == "budget_reparation"


@pytest.mark.parametrize("degrees", [math.nan, math.inf])
def test_non_finite_orientation_is_refused(degrees: float) -> None:
    with pytest.raises(InvalidInput) as raised:
        legalize(make_plan(), make_context(degrees=degrees))
    assert raised.value.field == "orientation.deg"


@pytest.mark.parametrize("largeur_min", [-1.0, math.nan])
def test_bad_minimum_width_is_refused(largeur_min: float) -> None:
    with pytest.raises(InvalidInput) as raised:
        legalize(make_plan(), make_context(largeur_min=largeur_min))
    assert raised.value.field == "referentiel.largeur_min"


def test_bad_outline_is_refused() -> None:
    plan = replace(make_plan(), contour=((0.0, 0.0), (1.0, 0.0)))
    with pytest.raises(InvalidInput) as raised:
        legalize(plan, make_context())
    assert raised.value.field == "contour"


def test_invalid_input_is_a_value_error_and_an_archlux_error() -> None:
    """Callers that caught ``ValueError`` keep working; ``ArchluxError`` catches all."""
    from archlux import ArchluxError

    assert issubclass(InvalidInput, ValueError)
    assert issubclass(InvalidInput, ArchluxError)


def test_invalid_input_is_not_an_internal_bug() -> None:
    from archlux import InvariantViolation

    assert not issubclass(InvalidInput, InvariantViolation)


def gapped_plan() -> Plan:
    """A 3 cm gap between the rooms: valid input, but not a tiling."""
    first = Room(id="a", type="sejour", x=0.0, y=0.0, w=5.97, h=9.0)
    second = Room(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0)
    return Plan(pieces=(first, second), murs=(), ouvertures=(), contour=SQUARE)


def test_gap_without_tiling_says_to_use_tiling() -> None:
    """3.4: the refusal names the cause and the fix, and is an input limit."""
    from archlux import GapNeedsTiling, UnsupportedInput

    with pytest.raises(GapNeedsTiling, match=r"pavage=True") as raised:
        legalize(gapped_plan(), make_context())
    assert isinstance(raised.value, UnsupportedInput)
    assert raised.value.violations
    assert all(v.startswith("gap") for v in raised.value.violations)


def test_gap_is_repaired_with_tiling() -> None:
    fixed = legalize(gapped_plan(), make_context(), pavage=True)
    assert fixed.certificat is not None
    assert fixed.certificat.geometrie.valide


def test_public_exports_input_limits() -> None:
    import archlux

    for name in ("UnsupportedInput", "GridNotRecoverable", "GapNeedsTiling", "InvalidInput"):
        assert name in archlux.__all__


def test_is_feasible_answers_for_a_plan_with_a_gap() -> None:
    """3.10 (audit 8, 5c): a feasible program with a gap gives a Verdict, not an error."""
    from archlux.feasibility import is_feasible

    verdict = is_feasible(gapped_plan(), Structure(murs_porteurs=()), make_context())
    assert verdict.faisable
    assert verdict.certificat is None


def test_is_feasible_refuses_a_malformed_program_with_invalid_input() -> None:
    from archlux.feasibility import is_feasible

    with pytest.raises(InvalidInput):
        is_feasible(make_plan(w=-1.0), Structure(murs_porteurs=()), make_context())


# --- Review of slices A to C ---------------------------------------------------------


def test_an_invalid_proof_without_gap_is_not_blamed_on_tiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gap is read from the proof's flags, never from the text of its violations."""
    import archlux.api
    from archlux import GapNeedsTiling, GeometricProof, InvariantViolation

    silent = GeometricProof(
        valide=False,
        chevauchement=False,
        jours=False,
        surfaces_ok=True,
        structure_preservee=True,
        deplacement_max=0.0,
        violations=(),
    )
    monkeypatch.setattr(archlux.api, "verify_exactly", lambda *a, **k: silent)
    with pytest.raises(InvariantViolation) as raised:
        legalize(make_plan(), make_context())
    assert not isinstance(raised.value, GapNeedsTiling)


def test_zero_wall_thickness_is_refused_as_by_the_json_reader() -> None:
    from archlux import Wall

    plan = replace(make_plan(), murs=(Wall(id="m", a=(0.0, 0.0), b=(12.0, 0.0), epaisseur=0.0),))
    with pytest.raises(InvalidInput) as raised:
        legalize(plan, make_context())
    assert raised.value.field == "murs[m].epaisseur"


def test_the_type_warning_points_at_the_caller() -> None:
    ctx = replace(make_context(), referentiel=Regulation(aires_min=(("sejour", 1.0),)))
    with pytest.warns(UserWarning, match="sejuor") as record:
        legalize(
            make_plan(type="sejuor"),
            replace(ctx, referentiel=replace(ctx.referentiel, largeur_min=1.0)),
        )
    assert record[0].filename == __file__


def test_is_feasible_keeps_the_scope_of_the_refusal() -> None:
    """A refusal *with* restrictions (here the load-bearing sides) must say which."""
    from archlux import Wall
    from archlux.feasibility import is_feasible

    wall = Wall(id="w", a=(6.0, 0.0), b=(6.0, 9.0), porteur=True)
    structure = Structure(murs_porteurs=(wall,))
    ctx = replace(make_context(), structure=structure)
    plan = replace(
        make_plan(),
        pieces=(
            Room(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
            Room(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
        ),
    )
    ctx = replace(ctx, referentiel=Regulation(aires_min=(("sejour", 60.0),), largeur_min=1.0))
    verdict = is_feasible(plan, structure, ctx)
    assert not verdict
    assert verdict.certificat is not None
    assert "load-bearing sides" in verdict.certificat.scope
    assert "load-bearing sides" in verdict.certificat.expliquer()
