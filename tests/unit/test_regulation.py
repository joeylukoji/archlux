"""Regulatory thresholds: `Regulation` is data, not code.

The expected values come from the regulation built in the test, never from a
computation that redoes what the implementation does.
"""

from __future__ import annotations

import pytest

from archlux.types import Regulation

FRENCH_REGULATION = Regulation(
    min_areas=(("living_room", 9.0), ("bedroom", 9.0), ("bathroom", 5.0), ("kitchen", 6.0)),
    min_width=1.80,
)


@pytest.mark.parametrize(
    ("room_type", "expected"),
    [("living_room", 9.0), ("bedroom", 9.0), ("bathroom", 5.0), ("kitchen", 6.0)],
)
def test_returns_the_threshold_of_the_type(room_type: str, expected: float) -> None:
    """Each regulated type returns its threshold."""
    assert FRENCH_REGULATION.min_area(room_type) == expected


def test_an_unregulated_type_constrains_nothing() -> None:
    """A corridor has no minimum area: the threshold is zero, not an exception.

    Raising here would force every caller to tell "no threshold" from "zero threshold",
    while both have exactly the same effect on the polytope.
    """
    assert FRENCH_REGULATION.min_area("corridor") == 0.0


def test_the_regulation_is_frozen() -> None:
    """Changing regulation creates a new regulation object, never a mutation."""
    with pytest.raises(AttributeError):
        FRENCH_REGULATION.min_width = 2.0  # type: ignore[misc]
