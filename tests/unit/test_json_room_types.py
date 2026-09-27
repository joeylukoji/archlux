"""The room types are English in memory; files of schema v1 keep the French ones.

PLAN.md 3.9, wave 4. A v1 file says ``"sejour"``; the model says ``"living_room"``. The
reader maps the six former values, and passes any other type through unchanged.
"""

from __future__ import annotations

import pytest

from archlux.io.json_io import from_dict

V1_TO_ENGLISH = {
    "sejour": "living_room",
    "chambre": "bedroom",
    "cuisine": "kitchen",
    "sdb": "bathroom",
    "wc": "toilet",
    "couloir": "corridor",
}
SQUARE = ((0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0))


def v1_document(room_type: str) -> dict[str, object]:
    """A minimal schema v1 file, written by hand: independent of what the writer emits."""
    return {
        "schema": "1",
        "contour": [list(point) for point in SQUARE],
        "pieces": [{"id": "a", "type": room_type, "x": 0.0, "y": 0.0, "w": 6.0, "h": 4.0}],
        "murs": [],
        "ouvertures": [],
        "certificat": None,
    }


@pytest.mark.parametrize(("old", "new"), V1_TO_ENGLISH.items())
def test_a_v1_file_is_read_with_english_types(old: str, new: str) -> None:
    plan = from_dict(v1_document(old))
    assert plan.rooms[0].type == new


@pytest.mark.parametrize("other", ["living", "salon", "office", "anything"])
def test_any_other_type_passes_through(other: str) -> None:
    assert from_dict(v1_document(other)).rooms[0].type == other
