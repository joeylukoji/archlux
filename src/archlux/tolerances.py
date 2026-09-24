"""Registry of numerical tolerances (PLAN.md, task 0.9).

Tolerances are part of what a certificate means: "no overlap" is only ever true up to
some epsilon, and two modules that disagree on that epsilon can disagree on validity.
This module names geometric tolerances once, with their unit and meaning.

Status (batch 1.5): ``certify.proof`` and ``lmo.coupes`` import their tolerances from
here; the other modules still hold literals equal to these values, migrated as they are
touched (PLAN.md). This module imports nothing, so every layer
may depend on it.

Not registered yet (inventoried in phase 1.5): ``geom.diagnostic._AIRE_MIN``, the
``tol`` defaults of ``Polytope.contient`` and ``lmo.coupes.satisfait``, the pivot of
``geom.rectilineaire``, ``lmo.coupes._TOLERANCE_BORNE``, ``api._DUAL_SEUIL``, the
``seuil`` of ``certify.dual`` and ``geom.pavage._EPS``.

Known inconsistencies (to be resolved in phase 1.5)
----------------------------------------------------
- Contact: rooms are adjacent below ``CONTACT_M`` in ``geom.graphe`` but contacts are
  frozen below ``SNAP_M`` in ``geom.polytope.figer_contacts``.
"""

from __future__ import annotations

from typing import Final

# --- Lengths (metres) ----------------------------------------------------------------

CONTACT_M: Final = 1e-9
"""Gap under which two rooms are adjacent (``geom.graphe.TOLERANCE_CONTACT``)."""

SNAP_M: Final = 1e-7
"""Gap under which a contact is frozen or a rectangle edge is snapped
(``geom.polytope.figer_contacts``, ``geom.rectilineaire._TOL_RECT``); also the tolerance
under which a load-bearing wall counts as axis-aligned, or as a point to ignore
(``geom.graphe``)."""

WALL_M: Final = 1e-7
"""Wall tolerance of the proof (``certify.proof``): two wall end points closer than this
coincide, and a room is shrunk by this much before testing whether a load-bearing wall
crosses its interior (so a room merely bounded by the wall is accepted)."""

CUTS_LENGTH_M: Final = 1e-6
"""Length tolerance of the cutting-plane loop (``lmo.coupes._TOLERANCE_LONGUEUR``)."""

# --- Areas (square metres) -----------------------------------------------------------

OVERLAP_M2: Final = 1e-9
"""Intersection area under which two rooms do not overlap (``certify.proof``,
``export.pathologie``)."""

GAP_M2: Final = 1e-6
"""Uncovered area under which the outline counts as tiled (``certify.proof``)."""

AREA_PROOF_M2: Final = 1e-9
"""Shortfall under a minimum area tolerated by the proof (``certify.proof``)."""

AREA_TARGET_MARGIN_M2: Final = 1e-6
"""Margin above a minimum area that cuts and bound tightening aim at (``lmo.coupes``).

The cutting-plane loop *accepts* an area with the proof tolerance ``AREA_PROOF_M2``, and
*aims* ``AREA_TARGET_MARGIN_M2`` above the minimum, well beyond the LP noise (about
1e-7), so that the proof never rejects a plan the solver accepted. Until batch 1.5 the
loop accepted a shortfall of 1e-6 m² that the proof then refused."""

# --- Pure numerics (dimensionless) ---------------------------------------------------

DIVISION_EPS: Final = 1e-12
"""Guard against division by zero; not a geometric tolerance."""
