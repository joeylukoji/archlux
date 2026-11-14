"""Three states of a plan, evaluated by the surrogate and by an independent reference.

AUDIT 2.2: a gain announced by the surrogate is a gain of the model until an
independent engine sees it. Every plan is therefore kept in three states, the
**initial** (generated) plan, the plan after **classic** legalization (L1, no daylight
objective) and the plan after archlux **optimization**, and the three are measured by the
same reference with the same openings, orientation and settings. The rows say how much
of the predicted gain the reference confirms, including the cases where the surrogate
announces a gain that does not exist.

The openings are invariant (:class:`~archlux.light.protocol.Glazing`): only the
partitions move. :func:`facade_glazing` gives a documented default when a plan comes
without openings, one window centred on each outline edge.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from archlux.light.evaluation import BeforeAfter, GainStatus, compare_before_after
from archlux.light.protocol import Glazing
from archlux.light.reference import ReferenceUnavailable
from archlux.types import Opening, Orientation, Point, Wall

if TYPE_CHECKING:
    from archlux.light.protocol import Surrogate
    from archlux.light.reference import Reference

__all__ = ["ThreeStates", "compare_three_states", "facade_glazing"]


def facade_glazing(
    outline: Sequence[Point],
    *,
    relative_width: float = 0.40,
    sill_height: float = 1.00,
    head_height: float = 2.15,
) -> Glazing:
    """One window centred on every edge of the outline.

    Parameters
    ----------
    outline : sequence of Point
        Outline of the dwelling, in order, without repeating the first point.
    relative_width : float, optional
        Window width as a fraction of the edge length (default 0.40).
    sill_height, head_height : float, optional
        Sill and head heights in metres.

    Returns
    -------
    Glazing
        One wall per outline edge (ids ``facade0``, ``facade1``...) and one opening on
        each, at ``s = 0.5``.

    Examples
    --------
    >>> g = facade_glazing(((0, 0), (4, 0), (4, 3), (0, 3)))
    >>> len(g.walls), len(g.openings), g.openings[0].wall_id
    (4, 4, 'facade0')
    """
    points = [(float(x), float(y)) for x, y in outline]
    walls = tuple(
        Wall(id=f"facade{k}", a=a, b=points[(k + 1) % len(points)]) for k, a in enumerate(points)
    )
    openings = tuple(
        Opening(
            id=f"window{k}",
            wall_id=wall.id,
            s=0.5,
            relative_width=relative_width,
            sill_height=sill_height,
            head_height=head_height,
        )
        for k, wall in enumerate(walls)
    )
    return Glazing(walls=walls, openings=openings)


@dataclass(frozen=True, slots=True)
class ThreeStates:
    """One plan in its three states, predicted and measured.

    Attributes
    ----------
    id : str
        Plan identifier.
    reference_kind : str
        ``"physical"``, ``"closed_form"``, or ``"unavailable"`` when the reference could
        not measure the plan.
    reference_initial, reference_classic, reference_optimized : float
        Reference values of the three states; ``nan`` when unmeasured.
    predicted_initial : float
        Surrogate value of the initial plan.
    gain : BeforeAfter
        Classic -> optimized: the gain the surrogate predicts and the one the reference
        measures, and its status (``confirmed`` only for a physical reference).
    """

    id: str
    reference_kind: str
    reference_initial: float
    reference_classic: float
    reference_optimized: float
    predicted_initial: float
    gain: BeforeAfter

    @property
    def status(self) -> GainStatus:
        """What the reference says about the predicted gain.

        Returns
        -------
        GainStatus
            The status of the classic -> optimized gain.
        """
        return self.gain.status


def _measure(
    reference: Reference, x: np.ndarray, orientation: Orientation, glazing: Glazing
) -> float:
    """Reference value of ``x``, ``nan`` when the reference cannot measure it.

    Parameters
    ----------
    reference : Reference
        Independent reference.
    x : numpy.ndarray
        Decision vector.
    orientation : Orientation
        Azimuth.
    glazing : Glazing
        Openings.

    Returns
    -------
    float
        The measured value, or ``nan``.
    """
    try:
        return float(reference.measure(x, orientation, glazing=glazing).value)
    except ReferenceUnavailable:
        return float("nan")


def compare_three_states(
    surrogate: Surrogate,
    reference: Reference,
    cases: Sequence[tuple[str, np.ndarray, np.ndarray, np.ndarray, Orientation, Glazing]],
) -> tuple[ThreeStates, ...]:
    """Measure the initial, classic and optimized states of each plan.

    Parameters
    ----------
    surrogate : Surrogate
        Model the optimizer used.
    reference : Reference
        Independent reference, the same for the three states.
    cases : sequence of tuple
        ``(id, x_initial, x_classic, x_optimized, orientation, glazing)``; the three
        vectors share one layout (``(x, y, w, h)`` per room, same room order).

    Returns
    -------
    tuple of ThreeStates
        One row per case, in order.
    """
    pairs = [(i, c, o, ori, g) for i, _, c, o, ori, g in cases]
    gains = compare_before_after(surrogate, reference, pairs)
    rows = []
    for (identifier, initial, _, _, orientation, glazing), gain in zip(cases, gains, strict=True):
        x0 = np.asarray(initial, dtype=float)
        measured = not np.isnan(gain.reference_before)
        rows.append(
            ThreeStates(
                id=identifier,
                reference_kind=str(reference.kind) if measured else "unavailable",
                reference_initial=_measure(reference, x0, orientation, glazing),
                reference_classic=gain.reference_before,
                reference_optimized=gain.reference_after,
                predicted_initial=float(surrogate.evaluate(x0, orientation, glazing=glazing)),
                gain=gain,
            )
        )
    return tuple(rows)
