"""Seuils réglementaires : `Referentiel` est une donnée, pas du code.

Les valeurs attendues viennent du référentiel construit dans le test, jamais d'un calcul
qui refait ce que fait l'implémentation.
"""

from __future__ import annotations

import pytest

from archlux.types import Referentiel

REFERENTIEL_FR = Referentiel(
    aires_min=(("sejour", 9.0), ("chambre", 9.0), ("sdb", 5.0), ("cuisine", 6.0)),
    largeur_min=1.80,
)


@pytest.mark.parametrize(
    ("type_piece", "attendu"),
    [("sejour", 9.0), ("chambre", 9.0), ("sdb", 5.0), ("cuisine", 6.0)],
)
def test_rend_le_seuil_du_type(type_piece: str, attendu: float) -> None:
    """Chaque type réglementé rend son seuil."""
    assert REFERENTIEL_FR.a_min(type_piece) == attendu


def test_un_type_non_reglemente_ne_contraint_rien() -> None:
    """Un couloir n'a pas de surface minimale : le seuil est nul, pas une exception.

    Lever ici forcerait chaque appelant à distinguer « pas de seuil » de « seuil zéro »,
    alors que les deux ont exactement le même effet sur le polytope.
    """
    assert REFERENTIEL_FR.a_min("couloir") == 0.0


def test_le_referentiel_est_gele() -> None:
    """Changer de réglementation crée un nouveau référentiel, jamais une mutation."""
    with pytest.raises(AttributeError):
        REFERENTIEL_FR.largeur_min = 2.0  # type: ignore[misc]
