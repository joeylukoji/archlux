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
    import numpy as np

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


def verify_infeasibility(poly: Polytope, y: np.ndarray, z: np.ndarray | None) -> FarkasCheck:
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
    n_var = len(poly.index)
    r = [Fraction(0)] * n_var
    beta = Fraction(0)

    rows = poly.A.tocsr()
    for i in range(rows.shape[0]):
        weight = Fraction(max(float(y[i]), 0.0))
        if weight == 0:
            continue
        beta += weight * Fraction(float(poly.b[i]))
        for k in range(rows.indptr[i], rows.indptr[i + 1]):
            r[rows.indices[k]] += weight * Fraction(float(rows.data[k]))

    if z is not None and poly.A_eq.shape[0]:
        equalities = poly.A_eq.tocsr()
        for i in range(equalities.shape[0]):
            weight = Fraction(float(z[i]))
            if weight == 0:
                continue
            beta += weight * Fraction(float(poly.b_eq[i]))
            for k in range(equalities.indptr[i], equalities.indptr[i + 1]):
                r[equalities.indices[k]] += weight * Fraction(float(equalities.data[k]))

    names = {column: name for name, column in poly.index.items()}
    lowest = Fraction(0)
    for j, coefficient in enumerate(r):
        if coefficient == 0:
            continue
        low, high = poly.bornes[j]
        bound = low if coefficient > 0 else high
        if not isfinite(bound):
            return FarkasCheck(False, float("-inf"), f"unbounded variable {names[j]}")
        lowest += coefficient * Fraction(bound)

    margin = lowest - beta
    if margin > 0:
        return FarkasCheck(True, float(margin))
    return FarkasCheck(False, float(margin), "the combination does not exclude the box")
