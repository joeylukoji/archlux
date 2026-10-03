"""Every implementation of ``Surrogate`` really respects the protocol.

A `Protocol` is structural: nothing signals that an implementation has drifted, until the
day ``solve`` receives an object that lacks ``uncertainty``. This test turns that silent
drift into a CI failure.

It also checks that the **signatures** match, not only the names: a method
``gradient(self, x)`` that had lost its ``orientation`` parameter would pass an
``isinstance`` without a murmur.
"""

from __future__ import annotations

import inspect
from typing import Generic, Protocol

import pytest

from archlux.light.analytic import AnalyticSurrogate
from archlux.light.learned import LearnedSurrogate
from archlux.light.protocol import Surrogate

IMPLEMENTATIONS = [AnalyticSurrogate, LearnedSurrogate]

# `glazing` came with the extension of the protocol: the decision vector only carries
# (x, y, w, h) per room, hence no fenestration information. Measured on 369 Swiss
# apartments, target = simulated irradiance, split by site: analytic R2 = -0.000,
# perceptron R2 = -0.667, at or below the plain mean. It is an input defect, not a
# capacity one. The parameter is **named and optional**: an implementation that
# ignores it stays compliant.
EXPECTED_SIGNATURES = {
    "evaluate": ("self", "x", "orientation", "glazing"),
    "gradient": ("self", "x", "orientation", "glazing"),
    "uncertainty": ("self", "x", "orientation", "glazing"),
}


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_implements_the_protocol(cls: type) -> None:
    """The four members of the protocol are present."""
    for member in ("indicator", *EXPECTED_SIGNATURES):
        assert hasattr(cls, member), f"{cls.__name__} lacks {member}"


@pytest.mark.parametrize("cls", IMPLEMENTATIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("method", sorted(EXPECTED_SIGNATURES))
def test_the_signatures_match(cls: type, method: str) -> None:
    """The parameter names are identical to those of the protocol."""
    actual = tuple(inspect.signature(getattr(cls, method)).parameters)
    assert actual == EXPECTED_SIGNATURES[method]


def _protocol_members(protocol: type) -> set[str]:
    """Members declared by ``protocol`` and its parent protocols.

    ``__protocol_attrs__`` only exists from Python 3.12 (``typing.get_protocol_members``
    from 3.13), and the CI also runs 3.11: read the class bodies instead.
    """
    members: set[str] = set()
    for base in protocol.__mro__:
        if base in (object, Protocol, Generic):
            continue
        members |= set(vars(base)) | set(getattr(base, "__annotations__", {}))
    return members


def test_the_protocol_has_exactly_four_members() -> None:
    """Three methods and one attribute. Widening the protocol widens the learned surface.

    Each member added here is one more thing that ``solve`` must know about the light
    model, hence a step towards the coupling the architecture avoids.
    """
    members = {m for m in _protocol_members(Surrogate) if not m.startswith("_")}
    assert members == {"indicator", "evaluate", "gradient", "uncertainty"}
