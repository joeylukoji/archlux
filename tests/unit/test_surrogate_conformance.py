"""Every surrogate honours the full ``Surrogate`` signature (PLAN.md batch 1.3).

``isinstance(x, Substitut)`` only checks method *names* (``runtime_checkable``), so
``Daylight`` passed it while rejecting the ``baies`` keyword that Frank-Wolfe always
sends: ``legalize(objective=Daylight(...))`` crashed with ``TypeError`` (AUDIT.md §3
n°3). This test compares signatures, which ``isinstance`` never does.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

import archlux
from archlux.light.analytique import AnalyticSurrogate
from archlux.light.appris import LearnedSurrogate
from archlux.light.base import DenseSurrogate
from archlux.light.objectif import Daylight
from archlux.light.protocole import Glazing, Surrogate
from archlux.light.simulateur import SplitFluxOracle
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure
from tests import checkers

IMPLEMENTATIONS = (AnalyticSurrogate, LearnedSurrogate, DenseSurrogate, SplitFluxOracle, Daylight)
METHODS = ("evaluate", "gradient", "uncertainty")


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("method", METHODS)
def test_every_method_accepts_the_protocol_keywords(cls: type, method: str) -> None:
    """Same positional parameters as the protocol, and ``baies`` keyword-only, optional."""
    expected = inspect.signature(getattr(Surrogate, method)).parameters
    actual = inspect.signature(getattr(cls, method)).parameters
    assert list(actual)[:3] == list(expected)[:3], f"{cls.__name__}.{method} positional"
    glazing = actual.get("glazing")
    assert glazing is not None, f"{cls.__name__}.{method} has no 'baies' parameter"
    assert glazing.kind is inspect.Parameter.KEYWORD_ONLY
    assert glazing.default is None


class _Recorder:
    """A surrogate that records the ``baies`` it receives."""

    indicator = "sDA"

    def __init__(self) -> None:
        self.seen: list[object] = []

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        self.seen.append(glazing)
        return float(np.sum(x))

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        self.seen.append(glazing)
        return np.ones_like(x)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        self.seen.append(glazing)
        return 1.0 + 0.01 * float(np.sum(x))


def test_daylight_forwards_the_glazing_to_the_wrapped_surrogate() -> None:
    inner = _Recorder()
    objective = Daylight(inner, q_chapeau=1.5)
    glazing = Glazing(walls=(), openings=())
    x, orientation = np.ones(8), Orientation(deg=0.0)
    objective.evaluate(x, orientation, glazing=glazing)
    objective.gradient(x, orientation, glazing=glazing)
    objective.uncertainty(x, orientation, glazing=glazing)
    assert inner.seen and all(seen is glazing for seen in inner.seen)


def test_legalize_accepts_a_daylight_objective() -> None:
    """End to end, the call of the README: it used to raise TypeError."""
    outline = ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0))
    rooms = (
        Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=6.0),
        Room(id="b", type="bedroom", x=6.0, y=0.0, w=4.0, h=6.0),
    )
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=30.0),
        outline=outline,
        regulation=Regulation(min_areas=(("bedroom", 12.0),), min_width=1.0),
    )
    plan = Plan(rooms=rooms, walls=(), openings=(), outline=outline)
    result = archlux.legalize(plan, ctx, objective=Daylight(AnalyticSurrogate(), q_chapeau=1.0))
    assert checkers.violations(result, ctx) == []


def test_a_surrogate_with_the_french_members_gets_a_migration_hint() -> None:
    """Review of the stack (#9): the protocol methods were renamed without an alias."""

    class OldStyle:
        indicateur = "sDA"

        def evaluer(self, x, orientation, *, baies=None):  # type: ignore[no-untyped-def]
            return 0.0

        def gradient(self, x, orientation, *, baies=None):  # type: ignore[no-untyped-def]
            return np.zeros_like(x)

        def incertitude(self, x, orientation, *, baies=None):  # type: ignore[no-untyped-def]
            return 1.0

    plan = Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=4.0, h=3.0),),
        outline=((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)),
    )
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        regulation=Regulation(min_areas=(), min_width=1.0),
    )
    with pytest.raises(TypeError, match=r"evaluer -> evaluate.*incertitude -> uncertainty"):
        archlux.legalize(plan, ctx, objective=OldStyle())  # type: ignore[arg-type]
