"""Every surrogate honours the full ``Substitut`` signature (PLAN.md batch 1.3).

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
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.appris import SubstitutAppris
from archlux.light.base import SubstitutDense
from archlux.light.objectif import Daylight
from archlux.light.protocole import Baies, Substitut
from archlux.light.simulateur import SimulateurExact
from archlux.types import Contexte, Orientation, Piece, Plan, Referentiel, Structure
from tests import checkers

IMPLEMENTATIONS = (SubstitutAnalytique, SubstitutAppris, SubstitutDense, SimulateurExact, Daylight)
METHODS = ("evaluer", "gradient", "incertitude")


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("method", METHODS)
def test_every_method_accepts_the_protocol_keywords(cls: type, method: str) -> None:
    """Same positional parameters as the protocol, and ``baies`` keyword-only, optional."""
    expected = inspect.signature(getattr(Substitut, method)).parameters
    actual = inspect.signature(getattr(cls, method)).parameters
    assert list(actual)[:3] == list(expected)[:3], f"{cls.__name__}.{method} positional"
    baies = actual.get("baies")
    assert baies is not None, f"{cls.__name__}.{method} has no 'baies' parameter"
    assert baies.kind is inspect.Parameter.KEYWORD_ONLY
    assert baies.default is None


class _Recorder:
    """A surrogate that records the ``baies`` it receives."""

    indicateur = "sDA"

    def __init__(self) -> None:
        self.seen: list[object] = []

    def evaluer(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        self.seen.append(baies)
        return float(np.sum(x))

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> np.ndarray:
        self.seen.append(baies)
        return np.ones_like(x)

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        self.seen.append(baies)
        return 1.0 + 0.01 * float(np.sum(x))


def test_daylight_forwards_the_glazing_to_the_wrapped_surrogate() -> None:
    inner = _Recorder()
    objective = Daylight(inner, q_chapeau=1.5)
    glazing = Baies(murs=(), ouvertures=())
    x, orientation = np.ones(8), Orientation(deg=0.0)
    objective.evaluer(x, orientation, baies=glazing)
    objective.gradient(x, orientation, baies=glazing)
    objective.incertitude(x, orientation, baies=glazing)
    assert inner.seen and all(seen is glazing for seen in inner.seen)


def test_legalize_accepts_a_daylight_objective() -> None:
    """End to end, the call of the README: it used to raise TypeError."""
    outline = ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0))
    rooms = (
        Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=6.0),
        Piece(id="b", type="chambre", x=6.0, y=0.0, w=4.0, h=6.0),
    )
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=30.0),
        contour=outline,
        referentiel=Referentiel(aires_min=(("chambre", 12.0),), largeur_min=1.0),
    )
    plan = Plan(pieces=rooms, murs=(), ouvertures=(), contour=outline)
    result = archlux.legalize(plan, ctx, objective=Daylight(SubstitutAnalytique(), q_chapeau=1.0))
    assert checkers.violations(result, ctx) == []
