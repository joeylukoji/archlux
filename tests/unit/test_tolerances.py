"""The tolerance registry matches the library and exposes its inconsistencies."""

from __future__ import annotations

import inspect

from archlux import tolerances
from archlux.certify import proof
from archlux.export import pathologies
from archlux.geom import graph, polytope, rectilinear
from archlux.lmo import cuts


def test_registry_documents_the_values_used_today() -> None:
    """Phase 0 registers existing values; a drift here means someone forgot the registry."""
    assert tolerances.CONTACT_M == graph.TOLERANCE_CONTACT
    assert tolerances.GAP_M2 == proof.GAP_TOLERANCE_M2
    assert tolerances.WALL_M == proof._WALL_TOLERANCE_M
    assert tolerances.AREA_PROOF_M2 == proof._AREA_TOLERANCE_M2
    assert cuts._AREA_TOLERANCE == tolerances.AREA_PROOF_M2
    assert tolerances.CUTS_LENGTH_M == cuts._LENGTH_TOLERANCE
    assert tolerances.SNAP_M == rectilinear._TOL_RECT
    snap_default = inspect.signature(polytope.freeze_contacts).parameters["tol"].default
    assert snap_default == tolerances.SNAP_M
    assert tolerances.OVERLAP_M2 == pathologies._AREA_TOL


def test_the_solver_is_never_looser_than_the_proof() -> None:
    """A plan the solver accepts must never be rejected by the proof on tolerance alone."""
    assert cuts._AREA_TOLERANCE <= tolerances.AREA_PROOF_M2
    assert tolerances.AREA_TARGET_MARGIN_M2 > tolerances.AREA_PROOF_M2
