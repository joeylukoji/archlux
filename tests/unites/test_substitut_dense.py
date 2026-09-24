"""Perceptron dense et point de contrôle — `MILESTONE-4.md` §4–7."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from archlux.erreurs import InvariantViole
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.appris import MAX_PARAMETRES, SubstitutAppris
from archlux.light.base import SubstitutDense
from archlux.light.protocole import Substitut
from archlux.light.simulateur import SplitFluxOracle
from archlux.light.validation import valider_gradient
from archlux.types import Orientation

_SIM = SplitFluxOracle()
_ANA = SubstitutAnalytique()


def _jeu(
    *, seed: int, n: int = 40
) -> tuple[tuple[np.ndarray, ...], np.ndarray, tuple[Orientation, ...]]:
    rng = np.random.default_rng(seed)
    xs: list[np.ndarray] = []
    ys: list[float] = []
    orients: list[Orientation] = []
    for _ in range(n):
        coupe = float(rng.uniform(4.0, 8.0))
        x = np.array([0.0, 0.0, coupe, 4.5, coupe, 0.0, 12.0 - coupe, 4.5])
        deg = float(rng.uniform(0.0, 360.0))
        ori = Orientation(deg=deg)
        xs.append(x)
        orients.append(ori)
        ys.append(_SIM.evaluer(x, ori))
    return tuple(xs), np.array(ys), tuple(orients)


def _entraine(tmp_path: Path) -> SubstitutAppris:
    xs, ys, oris = _jeu(seed=17, n=48)
    dense = SubstitutDense()
    dense.ajuster(xs, ys, oris, seed=17, epoques=40, lr=0.12)
    chemin = tmp_path / "dense.npz"
    empreinte = dense.sauver(chemin)
    return SubstitutAppris(chemin, empreinte, gele=True)


def test_dense_respecte_le_protocole() -> None:
    assert isinstance(SubstitutDense(), Substitut)


def test_meilleur_que_analytique(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    xs, ys, oris = _jeu(seed=99, n=24)

    def mae(modele) -> float:
        return float(
            np.mean([abs(modele.evaluer(x, o) - y) for x, o, y in zip(xs, oris, ys, strict=True)])
        )

    assert mae(reseau) < mae(_ANA)


def test_taille_raisonnable(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    assert reseau.n_parametres() < MAX_PARAMETRES


def test_erreur_stratifiee_par_orientation(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    xs, ys, oris = _jeu(seed=5, n=32)
    noms = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    erreurs: dict[str, list[float]] = {nom: [] for nom in noms}
    for x, y, ori in zip(xs, ys, oris, strict=True):
        secteur = noms[int(((ori.deg % 360.0) + 22.5) // 45.0) % 8]
        erreurs[secteur].append(abs(reseau.evaluer(x, ori) - y))
    for secteur, vals in erreurs.items():
        if not vals:
            continue
        assert float(np.mean(vals)) < 25.0, f"échec sur {secteur}"


def test_accord_de_signe_point_de_controle(tmp_path: Path) -> None:
    reseau = _entraine(tmp_path)
    sud = Orientation(deg=180.0)
    points = np.stack(
        [np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5]) for c in (4.5, 5.5, 6.5, 7.5)]
    )
    rapport = valider_gradient(
        reseau,
        points,
        sud,
        seed=17,
        reference=_SIM,
        pas=0.10,
        seuil_signe=0.80,
    )
    assert rapport.accord_de_signe > 0.80
    assert rapport.conforme


def test_empreinte_divergente_leve(tmp_path: Path) -> None:
    xs, ys, oris = _jeu(seed=3, n=12)
    dense = SubstitutDense()
    dense.ajuster(xs, ys, oris, seed=3, epoques=8, lr=0.12)
    chemin = tmp_path / "dense.npz"
    dense.sauver(chemin)
    reseau = SubstitutAppris(chemin, "0" * 64, gele=True)
    with pytest.raises(InvariantViole):
        reseau.n_parametres()
