"""Les invariants de `ARCHITECTURE.md` §6 sont testés, pas seulement écrits."""

from __future__ import annotations

import dataclasses

import pytest

from archlux import types as t

TYPES_GELES = [
    t.Piece, t.Mur, t.Ouverture, t.Plan, t.Orientation, t.Referentiel, t.Structure,
    t.Contexte, t.PreuveGeometrique, t.BornePerformance, t.ModeleTrace, t.Manifeste,
    t.Certificat,
]


@pytest.mark.parametrize("type_", TYPES_GELES, ids=lambda c: c.__name__)
def test_tous_les_types_sont_geles(type_: type) -> None:
    """Aucune mutation en place : contourner le gel est un bogue, pas un raccourci."""
    assert dataclasses.is_dataclass(type_)
    assert type_.__dataclass_params__.frozen


def test_la_preuve_geometrique_n_a_aucun_champ_de_probabilite() -> None:
    """Une preuve et une prédiction ne se mélangent pas, jusque dans les types."""
    interdits = {"couverture", "alpha", "proba", "probabilite", "confiance", "sigma"}
    champs = {f.name for f in dataclasses.fields(t.PreuveGeometrique)}
    assert not (champs & interdits)


def test_la_borne_porte_toujours_sa_couverture() -> None:
    """Une borne conforme sans couverture ni taille de calibration est invérifiable."""
    champs = {f.name for f in dataclasses.fields(t.BornePerformance)}
    assert {"couverture", "n_calibration"} <= champs


def test_une_ouverture_ne_stocke_aucune_position_absolue() -> None:
    """La position absolue est dérivée ; la stocker désynchronise murs et fenêtres."""
    champs = {f.name for f in dataclasses.fields(t.Ouverture)}
    assert not (champs & {"x", "y", "x_abs", "y_abs", "position"})
