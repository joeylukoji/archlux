"""The Frank-Wolfe helpers against ``docs/formules/frank-wolfe.md`` (away steps, weights).

Expectations are derived by hand from the formulas (Lacoste-Julien & Jaggi 2015), not
from running the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

from archlux.solve.frank_wolfe import _line_search, _step_away, _update_weights
from archlux.types import Orientation

NORD = Orientation(deg=0.0)


# --- _step_away -------------------------------------------------------------------


def test_away_step_taken_when_it_beats_the_frank_wolfe_direction() -> None:
    """Away vertex = argmin <g, v>; gamma_max = w_a / (1 - w_a)."""
    gradient = np.array([1.0, 0.0])
    vertices = [np.array([0.0, 0.0]), np.array([4.0, 0.0])]
    weights = [0.25, 0.75]
    x = 0.25 * vertices[0] + 0.75 * vertices[1]  # (3, 0)
    fw_direction = np.array([4.0, 0.0]) - x  # <g, d_fw> = 1
    direction, gamma_max, away, index = _step_away(gradient, x, fw_direction, vertices, weights)
    # d_away = x - v_0 = (3, 0): <g, d_away> = 3 > 1.
    assert away is True
    assert index == 0
    np.testing.assert_array_equal(direction, np.array([3.0, 0.0]))
    assert gamma_max == pytest.approx(0.25 / 0.75)


def test_plain_step_when_away_does_not_improve() -> None:
    gradient = np.array([1.0, 0.0])
    vertices = [np.array([0.0, 0.0]), np.array([4.0, 0.0])]
    weights = [0.25, 0.75]
    x = np.array([3.0, 0.0])
    fw_direction = np.array([10.0, 0.0])  # <g, d_fw> = 10 > 3
    direction, gamma_max, away, index = _step_away(gradient, x, fw_direction, vertices, weights)
    assert (away, index, gamma_max) == (False, None, 1.0)
    np.testing.assert_array_equal(direction, fw_direction)


def test_plain_step_with_a_single_active_vertex() -> None:
    fw_direction = np.array([1.0, 1.0])
    _, gamma_max, away, index = _step_away(
        np.array([1.0, 0.0]), np.zeros(2), fw_direction, [np.zeros(2)], [1.0]
    )
    assert (away, index, gamma_max) == (False, None, 1.0)


# --- _line_search -----------------------------------------------------------------


@dataclass
class ScriptedSurrogate:
    """Returns pre-set values in call order, recording the evaluated points."""

    values: list[float]
    seen: list[np.ndarray] = field(default_factory=list)
    indicator: str = "sDA"

    def evaluate(self, x: np.ndarray, orientation: Orientation, *, glazing: object = None) -> float:
        del orientation, glazing
        self.seen.append(x.copy())
        return self.values[len(self.seen) - 1]


def test_line_search_starts_at_two_over_k_plus_two_and_halves() -> None:
    """gamma_k = min(2/(k+2), gamma_max), halved while f decreases."""
    surrogate = ScriptedSurrogate(values=[0.0, 0.5, 2.0])  # value at x is 1.0
    x = np.zeros(1)
    result = _line_search(
        surrogate,
        NORD,
        x,
        1.0,
        np.array([1.0]),
        1.0,
        2,
        glazing=None,  # type: ignore[arg-type]
    )
    assert result is not None
    candidate, new_value, gamma = result
    # 2/(2+2) = 0.5, then 0.25, then 0.125 accepted.
    assert [float(p[0]) for p in surrogate.seen] == [0.5, 0.25, 0.125]
    assert gamma == 0.125
    assert new_value == 2.0
    np.testing.assert_array_equal(candidate, np.array([0.125]))


def test_line_search_caps_the_first_step_at_gamma_max() -> None:
    surrogate = ScriptedSurrogate(values=[1.0])
    result = _line_search(
        surrogate,
        NORD,
        np.zeros(1),
        1.0,
        np.array([1.0]),
        0.1,
        0,
        glazing=None,  # type: ignore[arg-type]
    )
    assert result is not None
    assert result[2] == 0.1


def test_line_search_gives_up_after_twelve_tries() -> None:
    surrogate = ScriptedSurrogate(values=[0.0] * 20)
    result = _line_search(
        surrogate,
        NORD,
        np.zeros(1),
        1.0,
        np.array([1.0]),
        1.0,
        0,
        glazing=None,  # type: ignore[arg-type]
    )
    assert result is None
    assert len(surrogate.seen) == 12


# --- _update_weights --------------------------------------------------------------


def test_frank_wolfe_step_adds_a_new_vertex() -> None:
    """w <- (1 - gamma) w, then w_s += gamma for a new s."""
    vertices = [np.array([0.0]), np.array([1.0])]
    kept, weights = _update_weights(
        vertices, [0.5, 0.5], np.array([2.0]), 0.2, away=False, away_index=None
    )
    assert [float(v[0]) for v in kept] == [0.0, 1.0, 2.0]
    assert weights == pytest.approx([0.4, 0.4, 0.2])


def test_frank_wolfe_step_onto_an_existing_vertex() -> None:
    vertices = [np.array([0.0]), np.array([1.0])]
    kept, weights = _update_weights(
        vertices, [0.5, 0.5], np.array([1.0]), 0.2, away=False, away_index=None
    )
    assert len(kept) == 2
    assert weights == pytest.approx([0.4, 0.6])


def test_away_step_moves_mass_off_the_away_vertex() -> None:
    """w <- (1 + gamma) w, then w_a -= gamma."""
    vertices = [np.array([0.0]), np.array([1.0])]
    kept, weights = _update_weights(
        vertices, [0.25, 0.75], np.array([9.0]), 0.2, away=True, away_index=0
    )
    assert len(kept) == 2
    assert weights == pytest.approx([0.1, 0.9])


def test_away_step_at_gamma_max_drops_the_vertex() -> None:
    """At gamma_max = w_a / (1 - w_a) the away vertex's mass is zero: it is pruned."""
    vertices = [np.array([0.0]), np.array([1.0])]
    kept, weights = _update_weights(
        vertices, [0.5, 0.5], np.array([9.0]), 1.0, away=True, away_index=0
    )
    assert [float(v[0]) for v in kept] == [1.0]
    assert weights == [1.0]


def test_full_frank_wolfe_step_prunes_and_renormalizes() -> None:
    """gamma = 1 empties every old vertex: only s remains, with weight 1."""
    kept, weights = _update_weights(
        [np.array([0.0]), np.array([1.0])],
        [0.3, 0.7],
        np.array([5.0]),
        1.0,
        away=False,
        away_index=None,
    )
    assert [float(v[0]) for v in kept] == [5.0]
    assert weights == [1.0]
