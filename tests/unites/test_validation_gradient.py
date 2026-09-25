"""Point de contrôle du gradient — `MILESTONE-4.md` §7."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.erreurs import SubstitutInvalide
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.validation import valider_gradient
from archlux.types import Orientation

X = np.array([[1.0, 2.0, 4.0, 5.0, 5.0, 2.0, 3.0, 5.0]])
NORD = Orientation(deg=0.0)


def test_analytique_est_coherent_avec_ses_differences_finies() -> None:
    rapport = valider_gradient(SubstitutAnalytique(), X, NORD, seed=17, epsilon=1e-5)
    assert rapport.conforme
    assert rapport.cosinus_moyen > 0.99


def test_gradient_faux_leve_substitut_invalide() -> None:
    class Faux:
        indicateur = "sDA"

        def evaluer(self, x, orientation):
            del orientation
            return float(np.sum(x))

        def gradient(self, x, orientation):
            del orientation
            return np.ones_like(x) * 7.0

        def incertitude(self, x, orientation):
            del x, orientation
            return 0.08

    with pytest.raises(SubstitutInvalide):
        valider_gradient(Faux(), X, NORD, seed=17)


def test_a_failed_check_carries_its_report() -> None:
    """PLAN.md phase 2, J4: the failing value is read from the report, not the message."""
    from archlux.light.analytique import SubstitutAnalytique

    class Negated(SubstitutAnalytique):
        def gradient(self, x, orientation, *, baies=None):  # type: ignore[no-untyped-def]
            return -super().gradient(x, orientation, baies=baies)

    with pytest.raises(SubstitutInvalide) as capture:
        valider_gradient(Negated(), X, NORD, seed=17, reference=SubstitutAnalytique())
    report = capture.value.report
    assert report is not None and not report.conforme
    assert report.accord_de_signe < 0.8
