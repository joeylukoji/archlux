"""JSON round trip: the exit criterion of milestone 1.

The central property is the identity ``from_dict(to_dict(p)) == p``. It is not
tautological: the equality comes from the frozen `dataclass`, not from a comparison
rewritten here, and it breaks as soon as a field is forgotten in the serialization.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings

from archlux.errors import InvariantViolation
from archlux.io.json_io import VERSION_SCHEMA, from_dict, to_dict
from archlux.types import Certificate, GeometricProof, Opening, Plan, Room, Wall
from tests.properties.strategies import arbitrary_plans

PLAN_T2 = Plan(
    rooms=(
        Room(id="living_room", type="living_room", x=0.0, y=0.0, w=4.0, h=3.5),
        Room(id="bathroom", type="bathroom", x=4.0, y=0.0, w=2.0, h=2.5),
    ),
    walls=(Wall(id="m_sud", a=(0.0, 0.0), b=(6.0, 0.0), load_bearing=True),),
    openings=(Opening(id="f1", wall_id="m_sud", s=0.3, relative_width=0.25),),
    outline=((0.0, 0.0), (6.0, 0.0), (6.0, 3.5), (0.0, 3.5)),
)


@given(plan=arbitrary_plans())
@settings(max_examples=200, deadline=None)
def test_round_trip_in_memory(plan: Plan) -> None:
    """No information is lost between the plan and its JSON form."""
    assert from_dict(to_dict(plan)) == plan


def test_round_trip_on_disk(tmp_path: Path) -> None:
    """``Plan.to_json`` then ``Plan.from_json`` return the original plan."""
    path = tmp_path / "plan.json"
    PLAN_T2.to_json(path)
    assert Plan.from_json(path) == PLAN_T2


def test_the_certificate_survives_the_round_trip() -> None:
    """A legalized plan carries its certificate; reading it back must not lose it."""
    proof = GeometricProof(
        valid=True,
        overlap=False,
        gaps=False,
        areas_ok=True,
        structure_kept=True,
        max_displacement=0.21,
        violations=(),
    )
    legalized = Plan(
        rooms=PLAN_T2.rooms,
        walls=PLAN_T2.walls,
        openings=PLAN_T2.openings,
        outline=PLAN_T2.outline,
        certificate=Certificate(geometry=proof),
    )
    reread = from_dict(to_dict(legalized))
    assert reread.certificate is not None
    assert reread.certificate.geometry.max_displacement == pytest.approx(0.21)
    assert reread.certificate.performance is None


def test_the_schema_version_is_written() -> None:
    """A file without a declared version would be unreadable in two years."""
    assert to_dict(PLAN_T2)["schema"] == VERSION_SCHEMA


def test_an_unknown_version_is_refused() -> None:
    """Better to refuse loudly than to guess the format."""
    data = to_dict(PLAN_T2)
    data["schema"] = "999"
    with pytest.raises(InvariantViolation):
        from_dict(data)


def test_writing_is_reproducible(tmp_path: Path) -> None:
    """Two writes of the same plan give the same bytes.

    Without that, the fingerprint of a manifest changes from one run to the next and
    the reproducibility promised by the README does not hold.
    """
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    PLAN_T2.to_json(a)
    PLAN_T2.to_json(b)
    assert a.read_bytes() == b.read_bytes()
