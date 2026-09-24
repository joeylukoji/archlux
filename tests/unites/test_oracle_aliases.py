"""Former names of ``SplitFluxOracle`` stay available, deprecated, until 1.0.0.

The class was called ``SimulateurExact`` (and ``ExactSimulator``): it is a frozen
closed-form oracle, neither a simulation nor exact (PLAN.md batch 1.8, ADR 0001).
"""

from __future__ import annotations

import pytest

from archlux import light
from archlux.light import simulateur
from archlux.light.simulateur import SplitFluxOracle


@pytest.mark.parametrize("old", ["SimulateurExact", "ExactSimulator"])
def test_package_aliases_warn_and_return_the_same_class(old: str) -> None:
    with pytest.warns(DeprecationWarning, match=f"light.{old} is deprecated, use"):
        legacy = getattr(light, old)
    assert legacy is SplitFluxOracle


def test_module_alias_warns_and_returns_the_same_class() -> None:
    with pytest.warns(DeprecationWarning, match="simulateur.SimulateurExact is deprecated"):
        legacy = simulateur.SimulateurExact  # type: ignore[attr-defined]
    assert legacy is SplitFluxOracle


def test_the_from_import_form_still_works() -> None:
    with pytest.warns(DeprecationWarning):
        from archlux.light import SimulateurExact  # type: ignore[attr-defined]
    assert SimulateurExact is SplitFluxOracle


def test_old_names_are_not_advertised() -> None:
    assert "SimulateurExact" not in light.__all__
    assert "ExactSimulator" not in light.__all__
    assert "SplitFluxOracle" in light.__all__


def test_unknown_names_still_raise() -> None:
    with pytest.raises(AttributeError):
        _ = light.NoSuchOracle  # type: ignore[attr-defined]
