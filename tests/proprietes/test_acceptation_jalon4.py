"""Critères d'acceptation du jalon 4. Le point de contrôle est bloquant."""

from __future__ import annotations

import numpy as np
import pytest

from archlux.erreurs import SubstitutInvalide
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SplitFluxOracle
from archlux.light.validation import valider_gradient
from archlux.types import Orientation

_SIM = SplitFluxOracle()
_ANA = SubstitutAnalytique()


def test_reseau_predit_mieux_que_analytique() -> None:
    rng = np.random.default_rng(21)
    xs: list[np.ndarray] = []
    ys: list[float] = []
    oris: list[Orientation] = []
    for _ in range(36):
        coupe = float(rng.uniform(4.0, 8.0))
        x = np.array([0.0, 0.0, coupe, 4.5, coupe, 0.0, 12.0 - coupe, 4.5])
        ori = Orientation(deg=float(rng.uniform(0.0, 360.0)))
        xs.append(x)
        oris.append(ori)
        ys.append(_SIM.evaluer(x, ori))
    dense = SubstitutDense()
    dense.ajuster(tuple(xs), np.array(ys), tuple(oris), seed=21, epoques=50, lr=0.12)
    hold_x, hold_y, hold_o = [], [], []
    for _ in range(16):
        coupe = float(rng.uniform(4.0, 8.0))
        x = np.array([0.0, 0.0, coupe, 4.5, coupe, 0.0, 12.0 - coupe, 4.5])
        ori = Orientation(deg=float(rng.uniform(0.0, 360.0)))
        hold_x.append(x)
        hold_o.append(ori)
        hold_y.append(_SIM.evaluer(x, ori))

    def mae(modele) -> float:
        return float(
            np.mean(
                [
                    abs(modele.evaluer(x, o) - y)
                    for x, o, y in zip(hold_x, hold_o, hold_y, strict=True)
                ]
            )
        )

    assert mae(dense) < mae(_ANA)


def test_point_de_controle_gradient() -> None:
    rng = np.random.default_rng(8)
    xs, ys, oris = [], [], []
    for _ in range(36):
        coupe = float(rng.uniform(4.0, 8.0))
        x = np.array([0.0, 0.0, coupe, 4.5, coupe, 0.0, 12.0 - coupe, 4.5])
        ori = Orientation(deg=float(rng.uniform(0.0, 360.0)))
        xs.append(x)
        oris.append(ori)
        ys.append(_SIM.evaluer(x, ori))
    dense = SubstitutDense()
    dense.ajuster(tuple(xs), np.array(ys), tuple(oris), seed=8, epoques=50, lr=0.12)
    sud = Orientation(deg=180.0)
    points = np.stack(
        [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (4.5, 5.5, 6.5, 7.5)]
    )
    rapport = valider_gradient(dense, points, sud, seed=8, reference=_SIM, pas=0.10)
    assert rapport.accord_de_signe > 0.80, (
        "Le substitut n'indique pas la bonne direction. NE PAS passer au jalon 5 avant correction."
    )


@pytest.mark.xfail(
    raises=SubstitutInvalide,
    strict=True,
    reason="J4 checkpoint reopened (PLAN.md phase 2, docs/revues/j4.md, ADR 0002): "
    "measured at south only it passed; at 0, 90 and 270 degrees it does not",
)
def test_gradient_checkpoint_as_written_on_80_points_at_four_azimuths() -> None:
    """MILESTONE-4.md §0: ``echantillon(80)``, not four points at south."""
    rng = np.random.default_rng(17)

    def draw(n: int) -> tuple[list[np.ndarray], list[Orientation]]:
        cuts = rng.uniform(4.0, 8.0, n)
        xs = [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in cuts]
        return xs, [Orientation(deg=float(d)) for d in rng.uniform(0.0, 360.0, n)]

    (train_x, train_o), (test_x, _) = draw(36), draw(80)
    dense = SubstitutDense()
    ys = np.array([_SIM.evaluer(x, o) for x, o in zip(train_x, train_o, strict=True)])
    dense.ajuster(tuple(train_x), ys, tuple(train_o), seed=17, epoques=40, lr=0.12)
    for k, azimuth in enumerate((0.0, 90.0, 180.0, 270.0)):
        points = np.stack(test_x[20 * k : 20 * (k + 1)])
        valider_gradient(dense, points, Orientation(deg=azimuth), seed=17, reference=_SIM)
