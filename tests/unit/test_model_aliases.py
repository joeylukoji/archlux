"""The former French names of the model classes stay importable, deprecated, until 1.0.0.

PLAN.md 3.9, wave 2 (ADR 0001). One parametrized test covers the whole alias table.
"""

from __future__ import annotations

import warnings

import pytest

import archlux
from archlux import types

RENAMED = {
    "Piece": "Room",
    "Mur": "Wall",
    "Ouverture": "Opening",
    "Contexte": "Context",
    "Referentiel": "Regulation",
    "Certificat": "Certificate",
    "PreuveGeometrique": "GeometricProof",
    "BornePerformance": "PerformanceBound",
    "Manifeste": "Manifest",
    "ModeleTrace": "ModelTrace",
    "Indicateur": "Indicator",
}
ON_THE_ROOT = {old: new for old, new in RENAMED.items() if new in archlux.__all__}


def test_the_alias_table_is_the_one_tested_here() -> None:
    assert types.DEPRECATED_NAMES == RENAMED


@pytest.mark.parametrize(("old", "new"), RENAMED.items())
def test_the_types_module_serves_the_old_name_with_a_warning(old: str, new: str) -> None:
    message = f"archlux.types.{old} is deprecated, use archlux.types.{new}"
    with pytest.warns(DeprecationWarning, match=message):
        legacy = getattr(types, old)
    assert legacy is getattr(types, new)


@pytest.mark.parametrize(("old", "new"), ON_THE_ROOT.items())
def test_the_package_root_serves_the_old_name_with_a_warning(old: str, new: str) -> None:
    with pytest.warns(DeprecationWarning, match=f"archlux.{old} is deprecated, use archlux.{new}"):
        legacy = getattr(archlux, old)
    assert legacy is getattr(archlux, new)


def test_the_root_exports_the_eight_public_model_classes() -> None:
    assert len(ON_THE_ROOT) == 8


@pytest.mark.parametrize("old", ON_THE_ROOT)
def test_a_from_import_warns_exactly_once(old: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        exec(f"from archlux import {old}", {})
    assert sum(issubclass(w.category, DeprecationWarning) for w in caught) == 1


@pytest.mark.parametrize(("old", "new"), RENAMED.items())
def test_old_names_are_not_advertised(old: str, new: str) -> None:
    assert old not in types.__all__
    assert new in types.__all__
    assert old not in archlux.__all__


def test_an_object_built_through_the_old_name_is_the_same_type() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = archlux.Piece  # type: ignore[attr-defined]
    room = legacy(id="a", type="living", x=0.0, y=0.0, w=1.0, h=1.0)
    assert isinstance(room, archlux.Room)
    assert isinstance(room, legacy)


def test_the_exception_aliases_still_work_beside_the_model_ones() -> None:
    with pytest.warns(DeprecationWarning):
        assert archlux.Infaisable is archlux.Infeasible  # type: ignore[attr-defined]
