"""The former French exception names stay importable, deprecated, until 1.0.0.

PLAN.md 3.9, wave 1 (ADR 0001). One parametrized test covers the whole alias table.
"""

from __future__ import annotations

import warnings

import pytest

import archlux
from archlux import erreurs

RENAMED = {
    "OrdreIncoherent": "InconsistentOrder",
    "SeparationManquante": "MissingSeparation",
    "Infaisable": "Infeasible",
    "InvariantViole": "InvariantViolation",
    "CalibrationVerrouillee": "CalibrationLocked",
    "ModeleModifie": "ModelModified",
    "SubstitutInvalide": "InvalidSurrogate",
}


def test_the_alias_table_is_the_one_tested_here() -> None:
    assert erreurs.DEPRECATED_NAMES == RENAMED


@pytest.mark.parametrize(("old", "new"), RENAMED.items())
def test_the_package_root_serves_the_old_name_with_a_warning(old: str, new: str) -> None:
    with pytest.warns(DeprecationWarning, match=f"archlux.{old} is deprecated, use archlux.{new}"):
        legacy = getattr(archlux, old)
    assert legacy is getattr(archlux, new)


@pytest.mark.parametrize(("old", "new"), RENAMED.items())
def test_the_error_module_serves_the_old_name_with_a_warning(old: str, new: str) -> None:
    message = f"archlux.erreurs.{old} is deprecated, use archlux.erreurs.{new}"
    with pytest.warns(DeprecationWarning, match=message):
        legacy = getattr(erreurs, old)
    assert legacy is getattr(erreurs, new)


@pytest.mark.parametrize("old", RENAMED)
def test_a_from_import_warns_exactly_once(old: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        exec(f"from archlux import {old}", {})
    assert sum(issubclass(w.category, DeprecationWarning) for w in caught) == 1


@pytest.mark.parametrize(("old", "new"), RENAMED.items())
def test_old_names_are_not_advertised(old: str, new: str) -> None:
    assert old not in archlux.__all__
    assert old not in erreurs.__all__
    assert new in archlux.__all__
    assert new in erreurs.__all__


def test_old_code_that_catches_the_old_name_still_catches_the_new_error() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = archlux.InvariantViole  # type: ignore[attr-defined]
    with pytest.raises(legacy):
        raise archlux.InvariantViolation(("boom",))


def test_the_lazy_packages_still_load_from_the_package_root() -> None:
    assert archlux.light.Daylight is not None
    assert callable(archlux.legalize)
    with pytest.raises(AttributeError):
        _ = archlux.NoSuchName  # type: ignore[attr-defined]
