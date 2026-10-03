"""Circular statistics for orientation.

An orientation is a point on a circle, not a real number. Treating 359° and 1°
as 358° apart produces false means, false regressions, and false conclusions --
and nothing in the usual tests flags it.

Every quantity derived from :class:`archlux.types.Orientation` goes through this
module.

Formulas: ``docs/formules/circulaire.md`` (Mardia & Jupp, 2000).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvalidInput, InvariantViolation
from archlux.types import Orientation

__all__ = [
    "RegressionResult",
    "angular_difference",
    "circular_linear_regression",
    "circular_mean",
    "circular_variance",
    "concentration",
    "dominant_direction",
    "encode",
    "encode_orientation",
    "rayleigh",
    "sector",
    "stratify",
]

_NOMS_HUIT = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_EPS_ANGLE = 1e-9
"""Tolerance for realigning an angle onto the edge of its period."""
_EPS_RESULTANTE = 1e-12
"""Below this resultant magnitude, no direction is dominant."""


@dataclass(frozen=True, slots=True)
class RegressionResult:
    r"""Fit :math:`y \approx a\cos\theta + b\sin\theta + c`."""

    a: float
    b: float
    c: float
    residus: np.ndarray


def encode(deg: float, *, harmoniques: int = 3) -> np.ndarray:
    """Encode an azimuth as ``(cos θ, sin θ, cos 2θ, sin 2θ, ...)``.

    Parameters
    ----------
    deg : float
        Azimuth, in degrees. **Never** returned as-is.
    harmoniques : int, optional
        Number of harmonics. A single one does not capture the east/west asymmetry.

    Returns
    -------
    numpy.ndarray
        Vector of dimension ``2 * harmoniques``, bounded, continuous at 0°/360°.
    """
    if harmoniques < 1:
        raise InvalidInput("harmoniques", f"must be >= 1, got {harmoniques}")
    theta = math.radians(deg)
    composantes = np.empty(2 * harmoniques, dtype=float)
    for rang in range(1, harmoniques + 1):
        composantes[2 * (rang - 1)] = math.cos(rang * theta)
        composantes[2 * (rang - 1) + 1] = math.sin(rang * theta)
    return composantes


def encode_orientation(orientation: Orientation, *, harmoniques: int = 2) -> np.ndarray:
    """Encode an :class:`~archlux.types.Orientation` as Fourier harmonics.

    Parameters
    ----------
    orientation : Orientation
        Azimuth, in degrees.
    harmoniques : int, optional
        Number of harmonics. Default 2 (historical contract of the skeleton).

    Returns
    -------
    numpy.ndarray
        Vector of dimension ``2 * harmoniques``.
    """
    return encode(orientation.deg, harmoniques=harmoniques)


def _radians(degres: np.ndarray | Sequence[float]) -> np.ndarray:
    """Convert a sequence of azimuths to radians, raveled."""
    valeurs = np.ravel(np.asarray(degres, dtype=float))
    if valeurs.size == 0:
        raise InvalidInput("degres", "at least one orientation is required")
    return np.asarray(np.radians(valeurs), dtype=float)


def _resultante(degres: np.ndarray | Sequence[float]) -> tuple[float, float, int]:
    """Sum of the unit vectors ``(C, S)`` and count ``n``."""
    theta = _radians(degres)
    return float(np.cos(theta).sum()), float(np.sin(theta).sum()), int(theta.size)


def circular_mean(degres: np.ndarray | Sequence[float]) -> float:
    """Mean direction, via the sum of the unit vectors.

    Returns
    -------
    float
        Mean azimuth in degrees, in ``[0, 360)``. ``360°`` is identified with ``0°``.
    """
    cosinus, sinus, _n = _resultante(degres)
    deg = float(np.degrees(np.arctan2(sinus, cosinus))) % 360.0
    return 0.0 if deg > 360.0 - 1e-9 else deg


@renamed_parameters({"poids": "weights"})
def dominant_direction(
    degres: np.ndarray | Sequence[float],
    weights: np.ndarray | Sequence[float] | None = None,
    *,
    periode: float = 90.0,
) -> float:
    r"""Mean direction of a set of axes, weighted and of period ``periode``.

    A wall edge has no direction of travel: ``10°`` and ``190°`` describe the
    same direction, and on an orthogonal grid ``10°``, ``100°``, ``190°``,
    ``280°`` describe the same *pattern*. An ordinary circular mean (period 360°)
    would cancel them out and yield an arbitrary direction.

    The method is the one for axial data (Mardia & Jupp, §2.3.3), generalized to a
    period :math:`p`: the angle is multiplied by :math:`m = 360/p` to bring
    equivalent directions to the same point on the circle, the weighted circular
    mean is taken there, then divided by :math:`m`:

    .. math::

        \bar\theta = \frac{1}{m}\,\operatorname{arg}
        \sum_k \ell_k \, e^{\,i\,m\,\theta_k},
        \qquad m = \frac{360}{p}.

    The weights are typically **lengths**: a 6 m wall should weigh more than a
    10 cm reveal.

    Parameters
    ----------
    degres : array_like
        Angles of the axes, in degrees.
    weights : array_like or None, optional
        Positive weights, same length. ``None`` = unit weights.
    periode : float, optional
        Period of the symmetry, in degrees. ``90`` for an orthogonal grid
        (default), ``180`` for unoriented axes, ``360`` for vectors.

    Returns
    -------
    float
        Dominant direction, in degrees, in ``[0, periode)``.

    Raises
    ------
    InvariantViolation
        Empty input, inconsistent lengths, ``periode`` outside ``]0, 360]``,
        negative weights, or a null resultant -- in this last case no direction is
        dominant and returning an angle would be inventing information.

    Examples
    --------
    >>> from archlux.orient.circular import direction_dominante
    >>> round(direction_dominante([10.0, 100.0, 190.0, 280.0]), 6)
    10.0
    >>> round(direction_dominante([0.0, 90.0], [1.0, 3.0]), 6)
    0.0
    """
    angles = np.asarray(degres, dtype=float).ravel()
    if angles.size == 0:
        raise InvariantViolation(("no axes: dominant direction is undefined",))
    if not 0.0 < periode <= 360.0:
        raise InvariantViolation((f"periode out of ]0, 360]: {periode}",))
    if weights is None:
        longueurs = np.ones_like(angles)
    else:
        longueurs = np.asarray(weights, dtype=float).ravel()
        if longueurs.size != angles.size:
            raise InvariantViolation(("degres and poids have distinct lengths",))
        if bool(np.any(longueurs < 0.0)):
            raise InvariantViolation(("negative weight",))
    m = 360.0 / periode
    phases = np.radians(m * angles)
    cosinus = float(np.sum(longueurs * np.cos(phases)))
    sinus = float(np.sum(longueurs * np.sin(phases)))
    if math.hypot(cosinus, sinus) <= _EPS_RESULTANTE:
        raise InvariantViolation(("null resultant: no dominant direction",))
    deg = float(np.degrees(math.atan2(sinus, cosinus)) / m) % periode
    # A direction just below ``periode`` is the same as ``0``: without this
    # realignment, a grid perfectly aligned with the x-axis comes out at
    # 89.999999° instead of 0°, because ``atan2`` returns an infinitesimally
    # negative angle.
    return 0.0 if deg > periode - _EPS_ANGLE else deg


def concentration(degres: np.ndarray | Sequence[float]) -> float:
    """Length of the mean resultant, in ``[0, 1]``.

    Returns
    -------
    float
        ``0`` = uniform orientations, ``1`` = all identical. This is the circular
        analogue of the inverse of a variance, and it has no angular unit.
    """
    cosinus, sinus, effectif = _resultante(degres)
    return math.hypot(cosinus, sinus) / effectif


def circular_variance(degres: np.ndarray | Sequence[float]) -> float:
    r"""Circular variance :math:`V = 1 - \bar R` (Mardia & Jupp, §2.3)."""
    return 1.0 - concentration(degres)


def rayleigh(degres: np.ndarray | Sequence[float]) -> tuple[float, float]:
    r"""Rayleigh test of uniformity on the circle.

    Returns
    -------
    tuple of float
        ``(R̄, p)``. Under the uniformity hypothesis, :math:`n\bar R^2` is
        approximately exponential: :math:`p \approx e^{-n\bar R^2}`.

    Notes
    -----
    The name is not ``test_rayleigh``: pytest would collect the function as a test.

    The approximation :math:`p = e^{-Z}`, :math:`Z = n\bar R^2`, is the **first
    order** of Mardia & Jupp (§6.3.1). It is anti-conservative at small ``n``: it
    returns a ``p`` that is too small, so it rejects uniformity too often. The
    usual correction :math:`p \approx e^{-Z}\,[1 + (2Z - Z^2)/(4n)]` is not applied
    here. Below about fifty observations, do not publish this ``p`` uncorrected.
    """
    resultante = concentration(degres)
    effectif = _radians(degres).size
    p_valeur = math.exp(-effectif * resultante * resultante)
    return resultante, p_valeur


def angular_difference(a: float, b: float) -> float:
    """Shortest signed difference between two azimuths, in ``]-180, 180]``."""
    ecart = (a - b + 180.0) % 360.0 - 180.0
    if ecart <= -180.0:
        return 180.0
    return float(ecart)


def circular_linear_regression(theta: np.ndarray, y: np.ndarray) -> RegressionResult:
    r"""Regression :math:`y \sim a\cos\theta + b\sin\theta + c`.

    Parameters
    ----------
    theta : numpy.ndarray
        Azimuths, in degrees.
    y : numpy.ndarray
        Linear response (indicator, gain, ...).
    """
    azimut = np.ravel(np.asarray(theta, dtype=float))
    reponse = np.ravel(np.asarray(y, dtype=float))
    if azimut.size != reponse.size:
        raise InvalidInput("theta", "theta and y must have the same length")
    if azimut.size < 3:
        raise InvalidInput("theta", "at least three observations are required")
    radians = np.radians(azimut)
    dessin = np.column_stack((np.cos(radians), np.sin(radians), np.ones(azimut.size)))
    coefficients, *_reste = np.linalg.lstsq(dessin, reponse, rcond=None)
    residus = reponse - dessin @ coefficients
    return RegressionResult(
        a=float(coefficients[0]),
        b=float(coefficients[1]),
        c=float(coefficients[2]),
        residus=residus,
    )


def sector(
    deg: float | np.ndarray | Sequence[float],
    n_sectors: int,
    *,
    center: bool = True,
) -> np.ndarray:
    """Index of the sector of width ``360 / n_sectors`` containing each azimuth.

    Parameters
    ----------
    deg : float or array-like
        Azimuth(s), in degrees. Any real value: wrapped modulo 360 first.
    n_sectors : int
        Number of equal-width sectors, an integer >= 1.
    center : bool, optional
        ``True`` (default): sector 0 is centered on 0 degrees, i.e.
        ``[-w/2, w/2[`` where ``w = 360 / n_sectors`` (the compass-rose convention
        :func:`stratify` names). ``False``: sector 0 is ``[0, w[`` (edge-aligned).
        No caller in ``src`` uses it: :func:`archlux.uq.reliability.stratify_by_orientation`
        needs this convention but keeps its own copy (``uq`` may not import ``orient``,
        ARCHITECTURE.md §5); a test pins both to the same partition of ``[0, 360[``.

    Returns
    -------
    numpy.ndarray
        Integer sector index per input angle, in ``[0, n_sectors[``. A scalar
        ``deg`` returns a 0-d array; ``int(...)`` converts it.

    Raises
    ------
    InvalidInput
        If ``n_sectors`` is not an integer >= 1.
    """
    if isinstance(n_sectors, bool) or not isinstance(n_sectors, (int, np.integer)) or n_sectors < 1:
        raise InvalidInput("n_sectors", f"must be an integer >= 1, got {n_sectors!r}")
    values = np.asarray(deg, dtype=float)
    width = 360.0 / n_sectors
    angles = values % 360.0
    if center:
        angles = (angles + width / 2.0) % 360.0
    return np.floor(angles / width).astype(int) % n_sectors


def stratify(
    degres: np.ndarray | Sequence[float],
    *,
    n_secteurs: int = 8,
) -> dict[str, np.ndarray]:
    """Split azimuths into sectors of equal width.

    Parameters
    ----------
    degres : array-like
        Azimuths, in degrees.
    n_secteurs : int, optional
        Number of sectors. 8 -> named compass rose (N, NE, ...).
    """
    if n_secteurs < 1:
        raise InvalidInput("n_secteurs", f"must be >= 1, got {n_secteurs}")
    valeurs = np.ravel(np.asarray(degres, dtype=float))
    indices = sector(valeurs, n_secteurs)
    noms = _NOMS_HUIT if n_secteurs == 8 else tuple(str(i) for i in range(n_secteurs))
    return {nom: valeurs[indices == rang] for rang, nom in enumerate(noms)}


__getattr__ = lazy_aliases(
    __name__,
    {
        "ResultatRegression": Alias(RegressionResult, "archlux.orient.circular.RegressionResult"),
        "difference_angulaire": Alias(
            angular_difference, "archlux.orient.circular.angular_difference"
        ),
        "direction_dominante": Alias(
            dominant_direction, "archlux.orient.circular.dominant_direction"
        ),
        "encoder": Alias(encode_orientation, "archlux.orient.circular.encode_orientation"),
        "moyenne_circulaire": Alias(circular_mean, "archlux.orient.circular.circular_mean"),
        "regression_circulaire_lineaire": Alias(
            circular_linear_regression, "archlux.orient.circular.circular_linear_regression"
        ),
        "stratifier": Alias(stratify, "archlux.orient.circular.stratify"),
        "variance_circulaire": Alias(
            circular_variance, "archlux.orient.circular.circular_variance"
        ),
    },
)
