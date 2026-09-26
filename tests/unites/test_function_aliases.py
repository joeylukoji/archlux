"""Former French function and class names stay importable, deprecated, until 1.0.0.

PLAN.md 3.9, wave 5 (first batch). One parametrized test covers the whole table.
"""

from __future__ import annotations

import importlib
import warnings

import pytest

ALIASES = [
    ("archlux.certify", "construire_borne", "build_bound"),
    ("archlux.certify", "rendre", "render"),
    ("archlux.certify", "traduire_duaux", "translate_duals"),
    ("archlux.certify.borne", "construire_borne", "build_bound"),
    ("archlux.certify.dual", "traduire_duaux", "translate_duals"),
    ("archlux.certify.rapport", "rendre", "render"),
    ("archlux.export.svg", "rendre", "render"),
    ("archlux.feasibility", "CertificatFaisabilite", "FeasibilityCertificate"),
]


@pytest.mark.parametrize(("module", "old", "new"), ALIASES)
def test_the_old_name_is_the_new_object_and_warns(module: str, old: str, new: str) -> None:
    target = importlib.import_module(module)
    message = f"{module}.{old} is deprecated, use {module}.{new}"
    with pytest.warns(DeprecationWarning, match=message.replace(".", r"\.")):
        legacy = getattr(target, old)
    assert legacy is getattr(target, new)


@pytest.mark.parametrize(("module", "old", "new"), ALIASES)
def test_a_from_import_warns_exactly_once(module: str, old: str, new: str) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        exec(f"from {module} import {old}", {})
    assert sum(issubclass(w.category, DeprecationWarning) for w in caught) == 1


@pytest.mark.parametrize(("module", "old", "new"), ALIASES)
def test_old_names_are_not_advertised(module: str, old: str, new: str) -> None:
    target = importlib.import_module(module)
    assert old not in getattr(target, "__all__", [])
    assert new in target.__all__
