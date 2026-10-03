"""Protocole `PerRoomSurrogate` — valeurs par piece.

La these : l'eclairement est une grandeur **par piece**, pas par plan. Mesure sur
367 466 pieces de Swiss Dwellings — 92 % de la variance est intra-appartement,
l'identite du batiment n'en explique que 2,6 %. Ces tests pinnent la coherence
entre la granularite fine et le scalaire que `solve` continue d'optimiser.
"""

from __future__ import annotations

import numpy as np
import pytest

from archlux.light.analytic import AnalyticSurrogate
from archlux.light.protocol import PerRoomSurrogate, Surrogate
from archlux.light.split_flux import SplitFluxOracle
from archlux.types import Orientation

IMPLEMENTATIONS = [AnalyticSurrogate, SplitFluxOracle]
INDICATEURS = ["sDA", "ASE", "UDI", "vue"]


def _plan(n: int) -> np.ndarray:
    """Vecteur de decision de ``n`` pieces, dimensions non triviales."""
    rng = np.random.default_rng(11)
    morceaux = []
    for _ in range(n):
        morceaux.extend(
            [
                float(rng.uniform(0.0, 8.0)),
                float(rng.uniform(0.0, 6.0)),
                float(rng.uniform(2.0, 7.0)),
                float(rng.uniform(2.0, 6.0)),
            ]
        )
    return np.array(morceaux, dtype=float)


@pytest.mark.parametrize("classe", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_implemente_les_deux_protocoles(classe: type) -> None:
    """Un substitut par piece reste un `Surrogate` : l'extension est additive."""
    instance = classe()
    assert isinstance(instance, Surrogate)
    assert isinstance(instance, PerRoomSurrogate)


@pytest.mark.parametrize("classe", IMPLEMENTATIONS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("indicator", INDICATEURS)
@pytest.mark.parametrize("n_pieces", [1, 3, 7])
def test_la_somme_des_parts_redonne_le_scalaire(
    classe: type, indicator: str, n_pieces: int
) -> None:
    """Contrat central : la scalarisation du dépôt est la **somme**.

    Sans cette garantie, `solve` optimiserait une grandeur sans rapport avec les
    valeurs par piece exposees, et le certificat serait incoherent avec lui-meme.
    """
    surrogate = classe(target_indicator=indicator)
    x = _plan(n_pieces)
    orientation = Orientation(deg=143.0)
    parts = surrogate.evaluate_rooms(x, orientation)
    assert parts.shape == (n_pieces,)
    assert float(parts.sum()) == pytest.approx(
        surrogate.evaluate(x, orientation), rel=1e-9, abs=1e-9
    )


@pytest.mark.parametrize("classe", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_le_signe_ase_porte_sur_chaque_piece(classe: type) -> None:
    """ASE est rendu negatif : la convention doit valoir **piece par piece**.

    L'inverser globalement seulement laisserait passer un plan ou une piece
    eblouissante compenserait une piece sombre.
    """
    x = _plan(4)
    orientation = Orientation(deg=200.0)
    positif = classe(target_indicator="sDA").evaluate_rooms(x, orientation)
    negatif = classe(target_indicator="ASE").evaluate_rooms(x, orientation)
    assert np.allclose(negatif, -positif)
    assert np.all(positif > 0.0)


@pytest.mark.parametrize("classe", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_les_parts_sont_deterministes(classe: type) -> None:
    """Deux appels identiques rendent le meme vecteur, bit a bit."""
    surrogate = classe()
    x = _plan(5)
    orientation = Orientation(deg=17.0)
    assert np.array_equal(
        surrogate.evaluate_rooms(x, orientation),
        surrogate.evaluate_rooms(x, orientation),
    )


@pytest.mark.parametrize("classe", IMPLEMENTATIONS, ids=lambda c: c.__name__)
def test_une_piece_plus_grande_recoit_plus(classe: type) -> None:
    """Coherence physique minimale : agrandir une piece augmente sa part.

    Test grossier, et c'est voulu : il ne verifie pas la physique, il verifie que
    la granularite fine n'a pas inverse une convention.
    """
    surrogate = classe()
    orientation = Orientation(deg=180.0)
    petite = np.array([0.0, 0.0, 3.0, 3.0, 5.0, 0.0, 3.0, 3.0])
    grande = np.array([0.0, 0.0, 6.0, 3.0, 5.0, 0.0, 3.0, 3.0])
    assert (
        surrogate.evaluate_rooms(grande, orientation)[0]
        > (surrogate.evaluate_rooms(petite, orientation)[0])
    )


def test_les_parts_ignorent_les_baies_pour_les_substituts_analytiques() -> None:
    """Les deux analytiques supposent un bandeau vitre constant : ils ignorent `baies`.

    C'est explicite, pas accidentel — et c'est ce qui leur vaut `R2 = -0,000` contre
    une irradiance simulee.
    """
    from archlux.light.protocol import Glazing
    from archlux.types import Opening, Wall

    x = _plan(3)
    orientation = Orientation(deg=90.0)
    glazing = Glazing(
        walls=(Wall(id="m", a=(0.0, 0.0), b=(6.0, 0.0)),),
        openings=(Opening(id="f", wall_id="m", s=0.5, relative_width=0.9),),
    )
    for classe in IMPLEMENTATIONS:
        surrogate = classe()
        assert np.array_equal(
            surrogate.evaluate_rooms(x, orientation),
            surrogate.evaluate_rooms(x, orientation, glazing=glazing),
        )
