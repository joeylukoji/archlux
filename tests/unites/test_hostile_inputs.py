"""Hostile inputs are refused at the door with a typed, actionable error.

PLAN.md phase 3, slice A (3.1, 3.3, 3.4). Before it, a negative width surfaced as
``InvariantViole: gap`` (an internal-bug exception for a typo) and ``nan`` as an LP status.
Now every case raises ``InvalidInput``, which names the offending field.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from archlux import (
    Contexte,
    InvalidInput,
    Orientation,
    Piece,
    Plan,
    Referentiel,
    Structure,
    legalize,
)

SQUARE = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def make_plan(**changes: object) -> Plan:
    """Two valid rooms side by side, with ``changes`` applied to the first one."""
    first = replace(Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0), **changes)  # type: ignore[arg-type]
    second = Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0)
    return Plan(pieces=(first, second), murs=(), ouvertures=(), contour=SQUARE)


def make_context(*, degrees: float = 0.0, largeur_min: float = 1.0) -> Contexte:
    """Empty structure, square outline, no minimum areas."""
    return Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=degrees),
        contour=SQUARE,
        referentiel=Referentiel(aires_min=(), largeur_min=largeur_min),
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
    from archlux import InvariantViole

    assert not issubclass(InvalidInput, InvariantViole)


def gapped_plan() -> Plan:
    """A 3 cm gap between the rooms: valid input, but not a tiling."""
    first = Piece(id="a", type="sejour", x=0.0, y=0.0, w=5.97, h=9.0)
    second = Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0)
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


# --- Review of slices A to C ---------------------------------------------------------


def test_an_invalid_proof_without_gap_is_not_blamed_on_tiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gap is read from the proof's flags, never from the text of its violations."""
    import archlux.api
    from archlux import GapNeedsTiling, InvariantViole, PreuveGeometrique

    silent = PreuveGeometrique(
        valide=False,
        chevauchement=False,
        jours=False,
        surfaces_ok=True,
        structure_preservee=True,
        deplacement_max=0.0,
        violations=(),
    )
    monkeypatch.setattr(archlux.api, "verify_exactly", lambda *a, **k: silent)
    with pytest.raises(InvariantViole) as raised:
        legalize(make_plan(), make_context())
    assert not isinstance(raised.value, GapNeedsTiling)


def test_zero_wall_thickness_is_refused_as_by_the_json_reader() -> None:
    from archlux import Mur

    plan = replace(make_plan(), murs=(Mur(id="m", a=(0.0, 0.0), b=(12.0, 0.0), epaisseur=0.0),))
    with pytest.raises(InvalidInput) as raised:
        legalize(plan, make_context())
    assert raised.value.field == "murs[m].epaisseur"


def test_the_type_warning_points_at_the_caller() -> None:
    ctx = replace(make_context(), referentiel=Referentiel(aires_min=(("sejour", 1.0),)))
    with pytest.warns(UserWarning, match="sejuor") as record:
        legalize(
            make_plan(type="sejuor"),
            replace(ctx, referentiel=replace(ctx.referentiel, largeur_min=1.0)),
        )
    assert record[0].filename == __file__
