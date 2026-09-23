"""Fixtures partagées. Aucune donnée aléatoire sans graine explicite."""

from __future__ import annotations

import pytest

GRAINE_TESTS = 17
"""Graine unique des tests. Jamais implicite, jamais absente (`ARCHITECTURE.md` §7)."""


@pytest.fixture(scope="session")
def graine() -> int:
    """Graine déterministe pour tout test qui échantillonne."""
    return GRAINE_TESTS
