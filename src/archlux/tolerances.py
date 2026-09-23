"""Registry of numerical tolerances (PLAN.md, task 0.9).

Tolerances are part of what a certificate means: "no overlap" is only ever true up to
some epsilon, and two modules that disagree on that epsilon can disagree on validity.
This module names geometric tolerances once, with their unit and meaning.

Status (phase 0): the registry **documents** the values currently hard-coded across the
library; modules do not import it yet. PLAN.md phase 1.5 migrates every usage here and
resolves the inconsistencies listed below. This module imports nothing, so every layer
may depend on it.

Not registered yet (inventoried in phase 1.5): ``geom.diagnostic._AIRE_MIN``, the
``tol`` defaults of ``Polytope.contient`` and ``lmo.coupes.satisfait``, the pivot of
``geom.rectilineaire``, ``lmo.coupes._TOLERANCE_BORNE``, ``api._DUAL_SEUIL``, the
``seuil`` of ``certify.dual`` and ``geom.pavage._EPS``.

Known inconsistencies (to be resolved in phase 1.5)
----------------------------------------------------
- Minimum area: the cutting-plane loop (``lmo.coupes``) accepts a room
  ``AREA_CUTS_M2`` short of its minimum, but the proof (``certify.preuve``) only
  tolerates ``AREA_PROOF_M2``. The solver can stop on a plan the proof then rejects.
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
"""Wall tolerance of the proof (``certify.preuve``): two wall end points closer than this
coincide, and a room is shrunk by this much before testing whether a load-bearing wall
crosses its interior (so a room merely bounded by the wall is accepted)."""

CUTS_LENGTH_M: Final = 1e-6
"""Length tolerance of the cutting-plane loop (``lmo.coupes._TOLERANCE_LONGUEUR``)."""

# --- Areas (square metres) -----------------------------------------------------------

OVERLAP_M2: Final = 1e-9
"""Intersection area under which two rooms do not overlap (``certify.preuve``,
``export.pathologie``)."""

GAP_M2: Final = 1e-6
"""Uncovered area under which the outline counts as tiled (``certify.preuve``)."""

AREA_PROOF_M2: Final = 1e-9
"""Shortfall under a minimum area tolerated by the proof (``certify.preuve``)."""

AREA_CUTS_M2: Final = 1e-6
"""Shortfall under a minimum area tolerated by the cutting-plane loop
(``lmo.coupes._TOLERANCE_AIRE``). Looser than ``AREA_PROOF_M2``: see module notes."""

# --- Pure numerics (dimensionless) ---------------------------------------------------

DIVISION_EPS: Final = 1e-12
"""Guard against division by zero; not a geometric tolerance."""
