"""Apprentissage actif — `MILESTONE-6.md` §3."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from archlux.active.boucle import Loop
from archlux.active.densite import densite_noyau
from archlux.active.selection import Aleatoire, UncertaintyTimesDensity
from archlux.types import Orientation


def test_produit_nul_ecarte_le_candidat() -> None:
    """Densité nulle → score nul → dernier du classement."""
    inc = np.array([10.0, 1.0, 5.0])
    dens = np.array([0.0, 1.0, 0.5])
    # scores = (0, 1, 2.5) → ordre 2, 1, 0
    idxs = UncertaintyTimesDensity().selectionner(inc, dens, n=3, seed=0)
    assert list(idxs) == [2, 1, 0]


def test_aleatoire_est_deterministe_avec_seed() -> None:
    inc = np.ones(20)
    dens = np.ones(20)
    a = Aleatoire().selectionner(inc, dens, n=5, seed=42)
    b = Aleatoire().selectionner(inc, dens, n=5, seed=42)
    assert np.array_equal(a, b)


def test_densite_plus_haute_pres_de_la_reference() -> None:
    ref = np.array([[0.0, 0.0], [0.1, 0.0], [-0.1, 0.05]])
    cand = np.array([[0.0, 0.0], [5.0, 5.0]])
    d = densite_noyau(cand, ref)
    assert d[0] > d[1]


@dataclass
class _OracleRegion:
    """Vérité : y = x[0] ; bruit faible près de 0, fort loin (|x[0]| > 2)."""

    indicateur: str = "sDA"

    def evaluer(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> float:
        del orientation, baies
        z = float(np.asarray(x, dtype=float).ravel()[0])
        bruit = 0.05 if abs(z) <= 2.0 else 2.0
        # Déterministe : « bruit » = offset fixe selon la région (reproductible).
        return z + (0.01 if bruit < 1.0 else 1.5)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> np.ndarray:
        g = np.zeros_like(np.asarray(x, dtype=float).ravel())
        g[0] = 1.0
        return g

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> float:
        del x, orientation, baies
        return 1.0


@dataclass
class _ModeleLocal:
    """Régression constante locale : moyenne des y labellisés proches."""

    indicateur: str = "sDA"
    xs: list[np.ndarray] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)
    _sigma: float = 1.0

    def evaluer(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> float:
        del orientation, baies
        if not self.ys:
            return 0.0
        z = float(np.asarray(x, dtype=float).ravel()[0])
        zs = np.array([float(np.asarray(v, dtype=float).ravel()[0]) for v in self.xs])
        poids = np.exp(-0.5 * (zs - z) ** 2)
        return float(np.average(self.ys, weights=poids))

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> np.ndarray:
        return np.zeros_like(np.asarray(x, dtype=float).ravel())

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: object = None
    ) -> float:
        """Distance au plus proche labellisé (explore l'inconnu)."""
        del orientation, baies
        if not self.xs:
            return 1.0
        z = float(np.asarray(x, dtype=float).ravel()[0])
        zs = np.array([float(np.asarray(v, dtype=float).ravel()[0]) for v in self.xs])
        return float(np.min(np.abs(zs - z)) + self._sigma * 0.1)

    def ajuster(
        self,
        xs: tuple[np.ndarray, ...],
        ys: np.ndarray,
        orientations: tuple[Orientation, ...],
        *,
        seed: int,
        epoques: int = 1,
        lr: float = 0.1,
    ) -> None:
        del orientations, seed, epoques, lr
        self.xs = [np.asarray(x, dtype=float).copy() for x in xs]
        self.ys = [float(y) for y in ys]
        preds = np.array([self.evaluer(x, Orientation(0.0)) for x in self.xs])
        self._sigma = float(max(np.std(preds - np.asarray(ys)), 0.05))


def test_actif_bat_l_aleatoire() -> None:
    """À budget égal, l'actif borne mieux la région utile (densité optimiseur).

    Pool mixte : région utile |z|≤2 (faible bruit) et région lointaine |z|>3
    (bruit structurel). La densité optimiseur est concentrée sur l'utile ;
    l'aléatoire gaspille des simulations au loin → q plus large.
    """
    rng = np.random.default_rng(0)
    utiles = [np.array([float(z)]) for z in rng.uniform(-1.5, 1.5, size=30)]
    lointains = [np.array([float(z)]) for z in rng.choice([-4.0, -3.5, 3.5, 4.0], size=30)]
    pool = utiles + lointains
    oris = [Orientation(0.0) for _ in pool]
    ref = [np.array([float(z)]) for z in np.linspace(-1.0, 1.0, 15)]
    hold = [np.array([float(z)]) for z in np.linspace(-1.2, 1.2, 12)]
    hold_o = [Orientation(0.0) for _ in hold]
    # Calibration INDEPENDANTE : tiree hors du pool d'acquisition, sur la meme loi
    # que le holdout. C'est le seul mode dont la couverture soit publiable, et le
    # seul qui rende la comparaison entre strategies honnete (meme q-chapeau).
    cal_rng = np.random.default_rng(99)
    calib = [np.array([float(z)]) for z in cal_rng.uniform(-1.5, 1.5, size=16)]
    calib_o = [Orientation(0.0) for _ in calib]

    def _campagne(acquire: object) -> float:
        modele = _ModeleLocal()
        # Amorçage : 4 points utiles.
        xs0 = tuple(utiles[:4])
        ys0 = np.array([_OracleRegion().evaluer(x, Orientation(0.0)) for x in xs0])
        modele.ajuster(xs0, ys0, tuple(Orientation(0.0) for _ in xs0), seed=0)
        boucle = Loop(
            substitut=modele,
            simulateur=_OracleRegion(),
            acquire=acquire,  # type: ignore[arg-type]
            budget=20,
            batch=4,
            seed=3,
        )
        rapport = boucle.run(
            pool,
            oris,
            reference_optimiseur=ref,
            holdout=hold,
            holdout_orientations=hold_o,
            calibration=calib,
            calibration_orientations=calib_o,
        )
        assert rapport.calibration_independante
        assert rapport.n_calibration == len(calib)
        return rapport.largeur_intervalle_finale

    largeur_aleatoire = _campagne(Aleatoire())
    largeur_actif = _campagne(UncertaintyTimesDensity())
    assert largeur_actif < largeur_aleatoire, (
        f"actif={largeur_actif:.4f} aleatoire={largeur_aleatoire:.4f}"
    )
