"""The tolerance registry matches the library and exposes its inconsistencies."""

from __future__ import annotations

import pytest

from archlux import tolerances
from archlux.certify import preuve
from archlux.geom import graphe
from archlux.lmo import coupes


def test_registry_documents_the_values_used_today() -> None:
    """Phase 0 registers existing values; a drift here means someone forgot the registry."""
    assert tolerances.CONTACT_M == graphe.TOLERANCE_CONTACT
    assert tolerances.GAP_M2 == preuve.TOLERANCE_JOUR_M2
    assert tolerances.WALL_M == preuve._TOLERANCE_MUR_M
    assert tolerances.AREA_PROOF_M2 == preuve._TOLERANCE_AIRE_M2
    assert tolerances.AREA_CUTS_M2 == coupes._TOLERANCE_AIRE
    assert tolerances.CUTS_LENGTH_M == coupes._TOLERANCE_LONGUEUR


@pytest.mark.xfail(
    strict=True,
    reason="lmo.coupes stops 1e-6 m² short of a minimum the proof checks at 1e-9 m² — PLAN.md 1.5",
)
def test_the_solver_is_never_looser_than_the_proof() -> None:
    """A plan the solver accepts must never be rejected by the proof on tolerance alone."""
    assert tolerances.AREA_CUTS_M2 <= tolerances.AREA_PROOF_M2
