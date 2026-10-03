r"""Independent, exact verification of an infeasibility certificate (PLAN.md batch 1.5c).

The solver is never believed on its word (``ARCHITECTURE.md``). When the LP says
"infeasible", it returns multipliers ``y >= 0`` for the rows of ``A x <= b`` and free
multipliers ``z`` for the rows of ``A_eq x = b_eq``. Any admissible ``x`` then satisfies

.. math::

    r^\top x \le \beta, \qquad r = A^\top y + A_{eq}^\top z, \qquad
    \beta = b^\top y + b_{eq}^\top z.

If even the smallest value of :math:`r^\top x` over the box of variable bounds exceeds
:math:`\beta`, no admissible ``x`` exists. That minimum is separable,
:math:`\sum_j \min(r_j l_j, r_j u_j)`, and it is computed here in exact rational
arithmetic: a float multiplier is an exact rational, so the conclusion is rigorous even
if the solver rounded. A noisy certificate can fail to verify; it can never verify a
feasible system.

Scope: the certificate proves infeasibility **of this polytope**, that is for the
relative order read from the proposed plan. Another order might admit a valid plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix

    from archlux.arrays import FloatVector
    from archlux.geom.polytope import Polytope

__all__ = ["FarkasCheck", "verify_infeasibility"]


@dataclass(frozen=True, slots=True)
class FarkasCheck:
    """Outcome of the exact check of an infeasibility certificate.

    Attributes
    ----------
    verified : bool
        True if the certificate proves that the polytope is empty.
    margin : float
        ``min r^T x - beta`` over the bounds (positive when verified), as a float.
    reason : str
        Why the certificate does not verify, empty when it does.
    """

    verified: bool
    margin: float
    reason: str = ""


def _accumulate(
    rows: csr_matrix,
    b: FloatVector,
    raw_weights: FloatVector,
    r: list[Fraction],
    beta: Fraction,
    *,
    clip_negative: bool,
) -> Fraction:
    """Add ``weight * row`` into ``r`` (in place) and ``weight * b`` into ``beta``.

    Extracted from :func:`verify_infeasibility` (PLAN.md phase 4, block 9): the
    inequality rows (``clip_negative=True``, negative solver noise clipped to zero)
    and the equality rows (``clip_negative=False``, any sign) share this exact loop.
    """
    for i in range(rows.shape[0]):
        raw = float(raw_weights[i])
        weight = Fraction(max(raw, 0.0)) if clip_negative else Fraction(raw)
        if weight == 0:
            continue
        beta += weight * Fraction(float(b[i]))
        for k in range(rows.indptr[i], rows.indptr[i + 1]):
            r[rows.indices[k]] += weight * Fraction(float(rows.data[k]))
    return beta


def _lowest_over_box(poly: Polytope, r: list[Fraction]) -> Fraction | str:
    """Minimum of ``r @ x`` over the box of variable bounds.

    Returns the name of the first unbounded variable whose bound the minimum would
    need, instead, when one is encountered.
    """
    names = {column: name for name, column in poly.index.items()}
    lowest = Fraction(0)
    for j, coefficient in enumerate(r):
        if coefficient == 0:
            continue
        low, high = poly.bounds[j]
        bound = low if coefficient > 0 else high
        if not isfinite(bound):
            return names[j]
        lowest += coefficient * Fraction(bound)
    return lowest


def verify_infeasibility(poly: Polytope, y: FloatVector, z: FloatVector | None) -> FarkasCheck:
    """Check exactly that ``(y, z)`` proves ``poly`` empty.

    Parameters
    ----------
    poly : Polytope
        The system the certificate is about.
    y : numpy.ndarray
        One multiplier per row of ``A``; negative entries (solver noise) are clipped to
        zero, which keeps the combination valid.
    z : numpy.ndarray or None
        One multiplier per row of ``A_eq``, any sign; ``None`` means none.

    Returns
    -------
    FarkasCheck
        ``verified`` is True only if the proof holds in exact arithmetic.
    """
    multipliers = [float(v) for v in y] + ([] if z is None else [float(v) for v in z])
    if not all(isfinite(v) for v in multipliers):
        return FarkasCheck(False, float("nan"), "non-finite multiplier")
    r = [Fraction(0)] * len(poly.index)
    beta = _accumulate(poly.A.tocsr(), poly.b, y, r, Fraction(0), clip_negative=True)
    if z is not None and poly.A_eq.shape[0]:
        beta = _accumulate(poly.A_eq.tocsr(), poly.b_eq, z, r, beta, clip_negative=False)

    lowest = _lowest_over_box(poly, r)
    if isinstance(lowest, str):
        return FarkasCheck(False, float("-inf"), f"unbounded variable {lowest}")

    margin = lowest - beta
    if margin > 0:
        return FarkasCheck(True, float(margin))
    return FarkasCheck(False, float(margin), "the combination does not exclude the box")
