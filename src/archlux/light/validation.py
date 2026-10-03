"""Validation du gradient d'un substitut. Sans elle, l'optimiseur converge vers du bruit.

Un substitut dont la valeur est excellente mais le gradient faux produit une optimisation
qui *semble* fonctionner : elle converge, elle rend des plans valides, et elle les choisit
au hasard. Aucun test de précision ne détecte cela. Cette vérification est le seul garde-
fou, et elle est obligatoire avant tout usage d'un substitut dans :mod:`archlux.solve`.
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
        "accord_de_signe": "sign_agreement",
        "graine": "seed",
        "conforme": "passed",
    }
)
@dataclass(frozen=True, slots=True)
class GradientReport:
    """Comparaison du gradient déclaré aux différences finies d'une référence.

    Attributes
    ----------
    accord_de_signe : float
        Fraction de coordonnées dont le signe coïncide. **Point de contrôle** :
        sous 0,80, ne pas passer au jalon 5 (`MILESTONE-4.md` §7).
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
    """Pente centrée de ``evaluate`` le long de chaque coordonnée de ``x``."""
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


@renamed_parameters({"substitut": "surrogate", "pas": "step", "seuil_signe": "sign_threshold"})
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
    """Comparer le gradient du substitut aux différences finies.

    Si ``reference`` est fournie (oracle gelé), on compare les **signes**
    au pente réelle — c'est le point de contrôle du projet. Sinon, on vérifie
    la cohérence interne ``gradient`` vs ``evaluate`` du même objet.

    Parameters
    ----------
    surrogate : Substitut
        Modèle à valider, analytique ou appris.
    points : numpy.ndarray
        Points d'évaluation, un par ligne.
    orientation : Orientation
        Azimut utilisé pour toutes les évaluations.
    seed : int
        Graine du tirage. **Obligatoire, sans défaut** (`ARCHITECTURE.md` §7).
        Ordonne les points avant agrégation, pour un diagnostic reproductible.
    reference : Substitut or None, optional
        Vérité terrain. ``None`` = auto-contrôle par différences finies.
    pas : float, optional
        Déplacement pour la pente réelle (point de contrôle).
    epsilon : float, optional
        Pas des différences finies d'auto-contrôle.
    tolerance : float, optional
        Erreur relative maximale admise en auto-contrôle.
    seuil_signe : float, optional
        Seuil d'accord de signe. Défaut 0,80.

    Returns
    -------
    RapportGradient
        Diagnostic complet, jamais un simple booléen.

    Raises
    ------
    InvalidSurrogate
        Auto-contrôle hors tolérance, ou accord de signe sous le seuil.

    Notes
    -----
    - ``RapportGradient.conforme`` vaut **toujours** ``True`` dans la valeur rendue :
      l'échec lève, il ne se rapporte pas. Le diagnostic chiffré promis ci-dessus n'est
      donc jamais lisible dans le cas qui l'intéresse le plus. Un appelant qui veut
      inspecter un échec doit passer par l'exception, qui ne porte qu'un message.
    - ``seed`` ne fait que permuter les points ; les agrégats étant un ``max`` et deux
      moyennes, il ne change le résultat qu'au dernier bit d'arrondi. Il satisfait la
      règle « graine obligatoire » du §7 sans rendre la fonction aléatoire.
    - Le mode auto-contrôle compare le gradient déclaré aux différences finies du
      **même** objet : il détecte une dérivée fausse, jamais un modèle faux. Seul le
      mode ``reference`` confronte à l'oracle gelé.
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
                f"erreur relative {report.max_relative_error:.3g} > {tolerance}",
                report=report,
            )
    else:
        passed = report.sign_agreement >= sign_threshold
        if not passed:
            raise InvalidSurrogate(
                f"accord de signe {report.sign_agreement:.3f} < {sign_threshold} "
                "— ne pas passer au jalon 5",
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
