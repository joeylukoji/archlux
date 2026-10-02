"""The package root re-exports ``verdict``'s business logic (PLAN.md phase 4, block 10, item 29)."""

from __future__ import annotations

import archlux.feasibility as feasibility
from archlux.feasibility import verdict


def test_the_package_root_re_exports_verdict_s_public_names() -> None:
    assert feasibility.is_feasible is verdict.is_feasible
    assert feasibility.Verdict is verdict.Verdict
    assert feasibility.FeasibilityCertificate is verdict.FeasibilityCertificate


def test_the_business_logic_is_not_duplicated_in_init() -> None:
    """``__init__.py`` holds no ``def``: everything lives in ``verdict.py``."""
    from pathlib import Path

    source = Path(feasibility.__file__).read_text(encoding="utf-8")
    assert "def " not in source
