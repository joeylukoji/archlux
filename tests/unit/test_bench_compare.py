"""``bench.compare`` exige un évaluateur externe — `MILESTONE-4.md` §8."""

from __future__ import annotations

import pytest

from archlux.bench.protocol import compare
from archlux.light.analytic import AnalyticSurrogate
from archlux.types import Plan, Room


def test_pas_d_evaluation_circulaire() -> None:
    plan = Plan(
        rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=6.0, h=9.0),),
        walls=(),
        openings=(),
        outline=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    )
    with pytest.raises(TypeError):
        compare(plans=(plan,), methods=(AnalyticSurrogate(),))
