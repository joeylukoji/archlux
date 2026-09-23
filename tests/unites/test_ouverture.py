"""La position d'une baie est **dérivée**, jamais stockée.

Les extrémités attendues sont des littéraux calculés à la main sur des murs choisis pour
que la géométrie soit vérifiable de tête (mur horizontal de 10 m, triangle 3-4-5).
"""

from __future__ import annotations

import pytest

from archlux.erreurs import InvariantViole
from archlux.types import Mur, Ouverture

MUR_SUD = Mur(id="m_sud", a=(0.0, 0.0), b=(10.0, 0.0))
MUR_OBLIQUE = Mur(id="m_obl", a=(0.0, 0.0), b=(3.0, 4.0))  # longueur 5

BAIE = Ouverture(id="f1", mur_id="m_sud", s=0.5, largeur_rel=0.2)


def test_baie_centree_sur_un_mur_horizontal() -> None:
    """Mur de 10 m, baie de 20 % centrée : de 4 m à 6 m."""
    debut, fin = BAIE.segment_absolu(MUR_SUD)
    assert debut == pytest.approx((4.0, 0.0))
    assert fin == pytest.approx((6.0, 0.0))


def test_baie_sur_un_mur_oblique() -> None:
    """Mur 3-4-5 (longueur 5), baie de 20 % centrée : longueur 1, centrée en (1,5 ; 2)."""
    baie = Ouverture(id="f2", mur_id="m_obl", s=0.5, largeur_rel=0.2)
    debut, fin = baie.segment_absolu(MUR_OBLIQUE)
    assert debut == pytest.approx((1.2, 1.6))
    assert fin == pytest.approx((1.8, 2.4))


def test_la_baie_suit_le_mur_quand_le_solveur_le_deplace() -> None:
    """**La raison d'être de l'invariant.**

    La même ``Ouverture``, non modifiée, rend une position différente dès que son mur
    bouge. C'est exactement ce qu'une coordonnée absolue stockée ne ferait pas : elle
    resterait sur place et désynchroniserait la fenêtre de sa cloison.
    """
    mur_deplace = Mur(id="m_sud", a=(0.0, 3.0), b=(10.0, 3.0))
    debut, fin = BAIE.segment_absolu(mur_deplace)
    assert debut == pytest.approx((4.0, 3.0))
    assert fin == pytest.approx((6.0, 3.0))


def test_un_mur_etranger_est_refuse() -> None:
    """Dériver une baie sur un autre mur que le sien est un bogue, pas un cas limite."""
    with pytest.raises(InvariantViole) as capture:
        BAIE.segment_absolu(MUR_OBLIQUE)
    assert "m_sud" in str(capture.value)
