"""The invariants of `ARCHITECTURE.md` §6 are tested, not only written."""

from __future__ import annotations

import dataclasses

import pytest

from archlux import types as t

FROZEN_TYPES = [
    t.Room,
    t.Wall,
    t.Opening,
    t.Plan,
    t.Orientation,
    t.Regulation,
    t.Structure,
    t.Context,
    t.GeometricProof,
    t.PerformanceBound,
    t.ModelTrace,
    t.Manifest,
    t.Certificate,
]


@pytest.mark.parametrize("type_", FROZEN_TYPES, ids=lambda c: c.__name__)
def test_every_type_is_frozen(type_: type) -> None:
    """No in-place mutation: getting around the freeze is a bug, not a shortcut."""
    assert dataclasses.is_dataclass(type_)
    assert type_.__dataclass_params__.frozen


def test_the_geometric_proof_has_no_probability_field() -> None:
    """A proof and a prediction do not mix, down to the types."""
    forbidden = {
        "couverture",
        "alpha",
        "proba",
        "probabilite",
        "confiance",
        "sigma",
    }  # lang-ok: former French field names, data
    fields = {f.name for f in dataclasses.fields(t.GeometricProof)}
    assert not (fields & forbidden)


def test_the_bound_always_carries_its_coverage() -> None:
    """A conformal bound without coverage or calibration size cannot be checked."""
    fields = {f.name for f in dataclasses.fields(t.PerformanceBound)}
    assert {"coverage", "n_calibration"} <= fields


def test_an_opening_stores_no_absolute_position() -> None:
    """The absolute position is derived; storing it desynchronizes walls and windows."""
    fields = {f.name for f in dataclasses.fields(t.Opening)}
    assert not (fields & {"x", "y", "x_abs", "y_abs", "position"})
