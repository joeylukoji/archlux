"""The package root re-exports ``verdict``'s business logic (PLAN.md phase 4, block 10, item 29)."""

from __future__ import annotations

import ast
import pickle
from pathlib import Path

import pytest

import archlux.feasibility as feasibility
from archlux.feasibility import verdict


def test_the_package_root_re_exports_verdict_s_public_names() -> None:
    assert feasibility.is_feasible is verdict.is_feasible
    assert feasibility.Verdict is verdict.Verdict
    assert feasibility.FeasibilityCertificate is verdict.FeasibilityCertificate


def test_the_business_logic_is_not_duplicated_in_init() -> None:
    """``__init__.py`` defines no function or class: everything lives in ``verdict.py``."""
    tree = ast.parse(Path(feasibility.__file__).read_text(encoding="utf-8"))
    definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    assert not [node for node in ast.walk(tree) if isinstance(node, definitions)]


def test_the_french_certificate_alias_warns_and_is_the_english_class() -> None:
    with pytest.warns(DeprecationWarning):
        alias = feasibility.CertificatFaisabilite  # type: ignore[attr-defined]
    assert alias is verdict.FeasibilityCertificate


def test_a_verdict_survives_a_pickle_round_trip() -> None:
    original = verdict.Verdict(feasible=True, certificate=None)
    restored = pickle.loads(pickle.dumps(original))
    assert restored == original
    assert bool(restored) is True
