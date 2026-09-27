"""Every ``>>>`` example of a docstring runs (PLAN.md 3.9).

The renames of the English-API waves left stale examples behind (``Piece(...)``,
``mur_id=``): nothing executed them. One test per module of ``archlux`` now does.
"""

from __future__ import annotations

import doctest
import importlib
import pkgutil
import warnings

import pytest

import archlux


def _modules() -> list[str]:
    names = [
        info.name
        for info in pkgutil.walk_packages(archlux.__path__, "archlux.")
        if not info.name.endswith(".appris")  # torch is optional and never imported here
    ]
    return sorted(names)


@pytest.mark.parametrize("name", _modules())
def test_the_examples_of_a_module_run(name: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        module = importlib.import_module(name)
    result = doctest.testmod(module, verbose=False, report=True)
    assert result.failed == 0, f"{name}: {result.failed} of {result.attempted} examples failed"
