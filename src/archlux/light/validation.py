"""Gradient validation of a surrogate. Without it, the optimizer converges towards noise.

A surrogate whose value is excellent but whose gradient is wrong yields an optimization
that *seems* to work: it converges, it returns valid plans, and it picks them at random.
No accuracy test detects this. This check is the only safeguard, and it is mandatory
before any use of a surrogate in :mod:`archlux.solve`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes, renamed_parameters
from archlux.errors import InvalidSurrogate

if TYPE_CHECKING:
    from archlux.light.protocol import Surrogate
    from archlux.types import Orientation

__all__ = ["GradientReport", "validate_gradient"]

_NIGHT = 1e-8


@renamed_attributes(
    {
        "erreur_relative_max": "max_relative_error",
        "cosinus_moyen": "mean_cosine",
        "accord_de_signe": "sign_agreement",  # lang-ok: deprecated French field
        "graine": "seed",
        "conforme": "passed",
    }
)
@dataclass(frozen=True, slots=True)
class GradientReport:
    """Comparison of the declared gradient with the finite differences of a reference.

    Attributes
    ----------
    sign_agreement : float
        Fraction of coordinates whose sign matches. **Checkpoint**: below 0.80, do not
        move on to milestone 5 (`MILESTONE-4.md` §7).
    """

    max_relative_error: float
    mean_cosine: float
    sign_agreement: float
    n_points: int
    seed: int
    passed: bool


def _finite_differences(
    surrogate: Surrogate, x: np.ndarray, orientation: Orientation, step: float
) -> np.ndarray:
    """Centred slope of ``evaluate`` along each coordinate of ``x``."""
    x0 = np.asarray(x, dtype=float).ravel()
    g = np.empty_like(x0)
    for i in range(x0.size):
        plus, minus = x0.copy(), x0.copy()
        plus[i] += step
        minus[i] -= step
        g[i] = (
            float(surrogate.evaluate(plus, orientation))
            - float(surrogate.evaluate(minus, orientation))
        ) / (2.0 * step)
    return g


@renamed_parameters(
    {
        "substitut": "surrogate",
        "pas": "step",  # lang-ok: deprecated French keyword
        "seuil_signe": "sign_threshold",
    }
)
def validate_gradient(
    surrogate: Surrogate,
    points: np.ndarray,
    orientation: Orientation,
    *,
    seed: int,
    reference: Surrogate | None = None,
    step: float = 0.10,
    epsilon: float = 1e-5,
    tolerance: float = 1e-3,
    sign_threshold: float = 0.80,
) -> GradientReport:
    """Compare the gradient of the surrogate with finite differences.

    If ``reference`` is given (frozen oracle), the **signs** are compared with the actual
    slope — the checkpoint of the project. Otherwise, the internal consistency of
    ``gradient`` against ``evaluate`` of the same object is checked.

    Parameters
    ----------
    surrogate : Surrogate
        Model to validate, analytic or learned.
    points : numpy.ndarray
        Evaluation points, one per row.
    orientation : Orientation
        Azimuth used for every evaluation.
    seed : int
        Seed of the draw. **Mandatory, no default** (`ARCHITECTURE.md` §7). Orders the
        points before aggregation, for a reproducible diagnostic.
    reference : Surrogate or None, optional
        Ground truth. ``None`` = self-check by finite differences.
    step : float, optional
        Displacement for the actual slope (checkpoint).
    epsilon : float, optional
        Step of the self-check finite differences.
    tolerance : float, optional
        Maximal relative error accepted in self-check.
    sign_threshold : float, optional
        Sign agreement threshold. Default 0.80.

    Returns
    -------
    GradientReport
        Full diagnostic, never a plain boolean.

    Raises
    ------
    InvalidSurrogate
        Self-check out of tolerance, or sign agreement below the threshold.

    Notes
    -----
    - ``GradientReport.passed`` is **always** ``True`` in the returned value: a failure
      raises, it is not reported. The numeric diagnostic promised above is therefore
      never readable in the case where it matters most. A caller who wants to inspect a
      failure must go through the exception, which carries only a message.
    - ``seed`` only permutes the points; the aggregates being a ``max`` and two means,
      it changes the result only in the last rounding bit. It satisfies the "mandatory
      seed" rule of §7 without making the function random.
    - The self-check mode compares the declared gradient with the finite differences of
      the **same** object: it detects a wrong derivative, never a wrong model. Only the
      ``reference`` mode confronts the frozen oracle.
    """
    matrix = np.asarray(points, dtype=float)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    rng = np.random.default_rng(seed)
    matrix = matrix[rng.permutation(matrix.shape[0])]
    oracle = reference
    step_fd = step if oracle is not None else epsilon
    errors: list[float] = []
    cosine: list[float] = []
    signs: list[bool] = []
    for x in matrix:
        declare = np.asarray(surrogate.gradient(x, orientation), dtype=float).ravel()
        target = (
            _finite_differences(oracle, x, orientation, step_fd)
            if oracle is not None
            else _finite_differences(surrogate, x, orientation, step_fd)
        )
        norm_c = float(np.linalg.norm(target))
        norm_d = float(np.linalg.norm(declare))
        if norm_c < _NIGHT and norm_d < _NIGHT:
            errors.append(0.0)
            cosine.append(1.0)
            signs.extend([True] * declare.size)
            continue
        denom = max(norm_c, _NIGHT)
        errors.append(float(np.linalg.norm(declare - target) / denom))
        if norm_c > _NIGHT and norm_d > _NIGHT:
            cosine.append(float(np.dot(declare, target) / (norm_d * norm_c)))
        else:
            cosine.append(0.0)
        for a, b in zip(declare, target, strict=True):
            if abs(b) < 1e-3:
                continue
            if abs(a) < _NIGHT:
                signs.append(False)
            else:
                signs.append((a >= 0.0) == (b >= 0.0))
    report = GradientReport(
        max_relative_error=max(errors) if errors else 0.0,
        mean_cosine=float(np.mean(cosine)) if cosine else 1.0,
        sign_agreement=float(np.mean(signs)) if signs else 1.0,
        n_points=int(matrix.shape[0]),
        seed=seed,
        passed=False,
    )
    if oracle is None:
        passed = report.max_relative_error <= tolerance
        if not passed:
            raise InvalidSurrogate(
                f"relative error {report.max_relative_error:.3g} > {tolerance}",
                report=report,
            )
    else:
        passed = report.sign_agreement >= sign_threshold
        if not passed:
            raise InvalidSurrogate(
                f"sign agreement {report.sign_agreement:.3f} < {sign_threshold} "
                "— do not move on to milestone 5",
                report=report,
            )
    return replace(report, passed=True)


__getattr__ = lazy_aliases(
    __name__,
    {
        "RapportGradient": Alias(GradientReport, "archlux.light.validation.GradientReport"),
        "valider_gradient": Alias(validate_gradient, "archlux.light.validation.validate_gradient"),
    },
)
