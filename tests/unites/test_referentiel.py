"""Seuils réglementaires : `Regulation` est une donnée, pas du code.

Les valeurs attendues viennent du référentiel construit dans le test, jamais d'un calcul
qui refait ce que fait l'implémentation.
"""

from __future__ import annotations

import pytest

from archlux.types import Regulation

REFERENTIEL_FR = Regulation(
    min_areas=(("living_room", 9.0), ("bedroom", 9.0), ("bathroom", 5.0), ("kitchen", 6.0)),
    min_width=1.80,
)


@pytest.mark.parametrize(
    ("type_piece", "attendu"),
    [("living_room", 9.0), ("bedroom", 9.0), ("bathroom", 5.0), ("kitchen", 6.0)],
)
def test_rend_le_seuil_du_type(type_piece: str, attendu: float) -> None:
    """Chaque type réglementé rend son seuil."""
    assert REFERENTIEL_FR.min_area(type_piece) == attendu


def test_un_type_non_reglemente_ne_contraint_rien() -> None:
    """Un couloir n'a pas de surface minimale : le seuil est nul, pas une exception.

    Lever ici forcerait chaque appelant à distinguer « pas de seuil » de « seuil zéro »,
    alors que les deux ont exactement le même effet sur le polytope.
    """
    assert REFERENTIEL_FR.min_area("corridor") == 0.0


def test_le_referentiel_est_gele() -> None:
    """Changer de réglementation crée un nouveau référentiel, jamais une mutation."""
    with pytest.raises(AttributeError):
        REFERENTIEL_FR.min_width = 2.0  # type: ignore[misc]
