"""Diagnostic géométrique — quantifier *comment* un plan est invalide.

Ces tests pinnent les cinq grandeurs qui décident si `legalize` a une chance sur
une entrée donnée. Ils portent sur des cas construits à la main, où la valeur
attendue se calcule de tête : un diagnostic dont on ne sait pas recalculer la
sortie ne sert à rien pour caractériser un corpus.
"""

from __future__ import annotations

import pytest

from archlux.geom.diagnostic import Diagnostic, diagnose
from archlux.types import Plan, Room


def _plan(*boites: tuple[float, float, float, float]) -> Plan:
    """Plan sans murs ni contour, une pièce par ``(x, y, w, h)``."""
    return Plan(
        rooms=tuple(
            Room(id=f"p{i}", type="salon", x=x, y=y, w=w, h=h)
            for i, (x, y, w, h) in enumerate(boites)
        ),
        walls=(),
        openings=(),
        outline=(),
    )


def test_un_pavage_exact_ne_montre_aucune_pathologie() -> None:
    """Deux pièces jointives : rien à signaler, et la trame vaut 2 cellules."""
    diag = diagnose(_plan((0.0, 0.0, 3.0, 2.0), (3.0, 0.0, 2.0, 2.0)))
    assert diag == Diagnostic(
        overlaps=0.0,
        gap_share=0.0,
        hole_share=0.0,
        fragments=1,
        cells=2,
        size=pytest.approx(10.0**0.5),
    )


def test_le_recouvrement_se_compte_dans_les_deux_sens() -> None:
    """Deux pièces qui se chevauchent en recouvrent chacune une : moyenne 1,0.

    Compter la paire une seule fois donnerait 0,5 et ne serait plus comparable au
    chiffre publié par les auteurs de MSD (4,11 pièces recouvertes par pièce).
    """
    diag = diagnose(_plan((0.0, 0.0, 3.0, 2.0), (2.0, 0.0, 3.0, 2.0)))
    assert diag.overlaps == 1.0


def test_un_contact_par_arete_ne_compte_pas_comme_recouvrement() -> None:
    """Deux pièces mitoyennes partagent une arête d'aire nulle, pas une surface."""
    assert diagnose(_plan((0.0, 0.0, 3.0, 2.0), (3.0, 0.0, 2.0, 2.0))).overlaps == 0.0


def test_un_jour_de_bord_n_est_pas_un_trou_interieur() -> None:
    """La distinction est le cœur du module : ici un jour, aucun trou.

    Sans elle, on impute au générateur un défaut qui n'est peut-être que le choix
    d'une boîte englobante rectangulaire sur une emprise en L.
    """
    diag = diagnose(_plan((0.0, 0.0, 2.0, 2.0), (2.0, 2.0, 2.0, 2.0)))
    assert diag.gap_share == pytest.approx(0.5)
    assert diag.hole_share == 0.0
    # Elles ne se touchent que par un coin : deux composantes, pas une. C'est la
    # bonne sémantique ici — un coin partagé n'est ni un mur mitoyen ni un
    # passage, et pour le pavage il reste un jour.
    assert diag.fragments == 2


def test_un_trou_ferme_est_compte_deux_fois() -> None:
    """Un anneau de quatre pièces : le trou central compte en jour **et** en trou."""
    diag = diagnose(
        _plan(
            (0.0, 0.0, 3.0, 1.0),  # bas
            (0.0, 2.0, 3.0, 1.0),  # haut
            (0.0, 1.0, 1.0, 1.0),  # gauche
            (2.0, 1.0, 1.0, 1.0),  # droite
        )
    )
    assert diag.hole_share == pytest.approx(1.0 / 9.0)
    assert diag.gap_share == pytest.approx(diag.hole_share)


def test_des_pieces_separees_forment_un_archipel() -> None:
    """Le nombre de morceaux est ce qui distingue un plan abîmé d'un plan absent.

    Trois pièces disjointes ne sont pas un appartement à réparer : aucune trame ne
    les rattrapera à budget raisonnable. C'est le régime observé sur les sorties
    de HouseDiffusion (`results/j8_*.md`).
    """
    diag = diagnose(_plan((0.0, 0.0, 1.0, 1.0), (3.0, 0.0, 1.0, 1.0), (6.0, 0.0, 1.0, 1.0)))
    assert diag.fragments == 3
    assert diag.overlaps == 0.0


def test_les_cellules_explosent_quand_aucun_bord_ne_coincide() -> None:
    """Trois pièces alignées sur les mêmes lignes : 3 cellules. Décalées : 25.

    C'est la mesure qui dit si la structure combinatoire du pavage existe. Sur un
    plan réel les pièces partagent leurs murs ; sur une sortie de modèle, presque
    aucune coordonnée ne coïncide et la trame enfle.
    """
    alignees = diagnose(_plan((0.0, 0.0, 1.0, 2.0), (1.0, 0.0, 1.0, 2.0), (2.0, 0.0, 1.0, 2.0)))
    decalees = diagnose(_plan((0.0, 0.0, 1.0, 2.0), (1.3, 0.4, 1.1, 2.0), (2.7, 0.9, 1.2, 2.0)))
    assert alignees.cells == 3
    assert decalees.cells == 25


def test_le_cote_donne_l_echelle_du_deplacement() -> None:
    """``cote`` est la racine de l'aire englobante : 5 m sur 10 m se lit autrement."""
    assert diagnose(_plan((0.0, 0.0, 4.0, 9.0))).size == pytest.approx(6.0)


def test_un_plan_sans_piece_leve() -> None:
    """Rendre des zéros laisserait croire à un plan sain : on refuse."""
    with pytest.raises(ValueError, match="nothing to diagnose"):
        diagnose(_plan())


@pytest.mark.parametrize("facteur", [0.1, 1.0, 7.5])
def test_les_parts_sont_invariantes_d_echelle(facteur: float) -> None:
    """Jour, trou et recouvrement sont des ratios : les mètres n'y entrent pas.

    C'est ce qui autorise à comparer des plans RPLAN — sans unité — à des plans
    MSD en mètres, et ce qui rend le choix d'échelle du jalon 8 sans effet sur
    les taux rapportés.
    """
    boites = ((0.0, 0.0, 2.0, 2.0), (1.0, 2.0, 2.0, 2.0))
    reference = diagnose(_plan(*boites))
    mis_a_l_echelle = diagnose(
        _plan(*((x * facteur, y * facteur, w * facteur, h * facteur) for x, y, w, h in boites))
    )
    assert mis_a_l_echelle.gap_share == pytest.approx(reference.gap_share)
    assert mis_a_l_echelle.hole_share == pytest.approx(reference.hole_share)
    assert mis_a_l_echelle.overlaps == reference.overlaps
    assert mis_a_l_echelle.size == pytest.approx(reference.size * facteur)
