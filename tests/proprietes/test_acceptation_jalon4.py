"""Critères d'acceptation du jalon 4. Le point de contrôle est bloquant."""

from __future__ import annotations

import numpy as np

from archlux.light.analytique import SubstitutAnalytique
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SimulateurExact
from archlux.light.validation import valider_gradient
from archlux.types import Orientation

_SIM = SimulateurExact()
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
