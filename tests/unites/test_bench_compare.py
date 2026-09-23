"""``bench.compare`` exige un évaluateur externe — `MILESTONE-4.md` §8."""

from __future__ import annotations

import pytest

from archlux.bench.protocole import compare
from archlux.light.analytique import SubstitutAnalytique
from archlux.types import Piece, Plan


def test_pas_d_evaluation_circulaire() -> None:
    plan = Plan(
        pieces=(Piece("a", "sejour", 0.0, 0.0, 6.0, 9.0),),
        murs=(),
        ouvertures=(),
        contour=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    )
    with pytest.raises(TypeError):
        compare(plans=(plan,), methods=(SubstitutAnalytique(),))
