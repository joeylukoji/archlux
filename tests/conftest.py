"""Shared fixtures. No random data without an explicit seed."""

from __future__ import annotations

import pytest

TEST_SEED = 17
"""Single seed of the tests. Never implicit, never missing (`ARCHITECTURE.md` §7)."""


@pytest.fixture(scope="session")
def seed() -> int:
    """Deterministic seed for any test that samples."""
    return TEST_SEED
