"""Comparer acquisition active vs aleatoire — budget egal, calibration independante."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from archlux.active import Aleatoire, Loop, UncertaintyTimesDensity
from archlux.light.base import SubstitutDense
from archlux.light.simulateur import SimulateurExact
from archlux.types import Orientation

GRAINE = 17
N_REPETITIONS = 10
_CENTRE = np.array([0.0, 0.0, 6.0, 4.5, 6.0, 0.0, 6.0, 4.5])


def _plan(c: float) -> np.ndarray:
    return np.array([0.0, 0.0, c, 4.5, c, 0.0, 12.0 - c, 4.5])


def _tirer(rng: np.random.Generator, n: int) -> tuple[list[np.ndarray], list[Orientation]]:
    xs = [_plan(float(rng.uniform(4.0, 8.0))) for _ in range(n)]
    os_ = [Orientation(float(rng.uniform(0.0, 360.0))) for _ in range(n)]
    return xs, os_


def _campagne(acquire: object, graine: int) -> float:
    rng = np.random.default_rng(graine)
    sim = SimulateurExact()
    props, oris = _tirer(rng, 48)
    # Calibration et holdout tires INDEPENDAMMENT du pool d'acquisition : c'est ce
    # qui rend la couverture publiable et la comparaison honnete (meme q-chapeau).
    calib, calib_o = _tirer(rng, 16)
    hold, hold_o = _tirer(rng, 30)
    ref = [_CENTRE + rng.normal(0, 0.05, 8) for _ in range(10)]

    net = SubstitutDense()
    xs0, os0 = tuple(props[:6]), tuple(oris[:6])
    ys0 = np.array([sim.evaluer(x, o) for x, o in zip(xs0, os0, strict=True)])
    net.ajuster(xs0, ys0, os0, seed=graine, epoques=25, lr=0.12)
    rapport = Loop(
        net, sim, acquire, budget=24, batch=4, seed=graine  # type: ignore[arg-type]
    ).run(
        props,
        oris,
        reference_optimiseur=ref,
        holdout=hold,
        holdout_orientations=hold_o,
        calibration=calib,
        calibration_orientations=calib_o,
    )
    assert rapport.calibration_independante
    return rapport.largeur_intervalle_finale


graines = [GRAINE + k for k in range(N_REPETITIONS)]
la = np.array([_campagne(Aleatoire(), g) for g in graines])
lb = np.array([_campagne(UncertaintyTimesDensity(), g) for g in graines])
diff = la - lb  # > 0 : l'actif borne plus etroit
gagne = int(np.sum(diff > 0))
Path("resultats/j6_actif.md").write_text(
    "# Jalon 6 — actif vs aleatoire\n\n"
    f"repetitions={N_REPETITIONS} graines={graines[0]}..{graines[-1]}\n"
    f"largeur_aleatoire_moy={la.mean():.4f} (ecart-type {la.std(ddof=1):.4f})\n"
    f"largeur_actif_moy={lb.mean():.4f} (ecart-type {lb.std(ddof=1):.4f})\n"
    f"gain_moyen={diff.mean():+.4f}\n"
    f"graines_ou_actif_gagne={gagne}/{N_REPETITIONS}\n",
    encoding="utf-8",
)
print(f"aleatoire {la.mean():.4f}  actif {lb.mean():.4f}  actif gagne {gagne}/{N_REPETITIONS}")
