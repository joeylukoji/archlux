"""Diagnostic géométrique — quantifier *comment* un plan est invalide.

Ces tests pinnent les cinq grandeurs qui décident si `legalize` a une chance sur
une entrée donnée. Ils portent sur des cas construits à la main, où la valeur
attendue se calcule de tête : un diagnostic dont on ne sait pas recalculer la
sortie ne sert à rien pour caractériser un corpus.
"""

from __future__ import annotations

import pytest

from archlux.geom.diagnostic import Diagnostic, diagnostiquer
from archlux.types import Piece, Plan


def _plan(*boites: tuple[float, float, float, float]) -> Plan:
    """Plan sans murs ni contour, une pièce par ``(x, y, w, h)``."""
    return Plan(
        pieces=tuple(
            Piece(id=f"p{i}", type="salon", x=x, y=y, w=w, h=h)
            for i, (x, y, w, h) in enumerate(boites)
        ),
        murs=(),
        ouvertures=(),
        contour=(),
    )


def test_un_pavage_exact_ne_montre_aucune_pathologie() -> None:
    """Deux pièces jointives : rien à signaler, et la trame vaut 2 cellules."""
    diag = diagnostiquer(_plan((0.0, 0.0, 3.0, 2.0), (3.0, 0.0, 2.0, 2.0)))
    assert diag == Diagnostic(
        recouvrements=0.0,
        part_jour=0.0,
        part_trou=0.0,
        morceaux=1,
        cellules=2,
        cote=pytest.approx(10.0**0.5),
    )


def test_le_recouvrement_se_compte_dans_les_deux_sens() -> None:
    """Deux pièces qui se chevauchent en recouvrent chacune une : moyenne 1,0.

    Compter la paire une seule fois donnerait 0,5 et ne serait plus comparable au
    chiffre publié par les auteurs de MSD (4,11 pièces recouvertes par pièce).
    """
    diag = diagnostiquer(_plan((0.0, 0.0, 3.0, 2.0), (2.0, 0.0, 3.0, 2.0)))
    assert diag.recouvrements == 1.0


def test_un_contact_par_arete_ne_compte_pas_comme_recouvrement() -> None:
    """Deux pièces mitoyennes partagent une arête d'aire nulle, pas une surface."""
    assert diagnostiquer(
        _plan((0.0, 0.0, 3.0, 2.0), (3.0, 0.0, 2.0, 2.0))
    ).recouvrements == 0.0


def test_un_jour_de_bord_n_est_pas_un_trou_interieur() -> None:
    """La distinction est le cœur du module : ici un jour, aucun trou.

    Sans elle, on impute au générateur un défaut qui n'est peut-être que le choix
    d'une boîte englobante rectangulaire sur une emprise en L.
    """
    diag = diagnostiquer(_plan((0.0, 0.0, 2.0, 2.0), (2.0, 2.0, 2.0, 2.0)))
    assert diag.part_jour == pytest.approx(0.5)
    assert diag.part_trou == 0.0
    # Elles ne se touchent que par un coin : deux composantes, pas une. C'est la
    # bonne sémantique ici — un coin partagé n'est ni un mur mitoyen ni un
    # passage, et pour le pavage il reste un jour.
    assert diag.morceaux == 2


def test_un_trou_ferme_est_compte_deux_fois() -> None:
    """Un anneau de quatre pièces : le trou central compte en jour **et** en trou."""
    diag = diagnostiquer(
        _plan(
            (0.0, 0.0, 3.0, 1.0),   # bas
            (0.0, 2.0, 3.0, 1.0),   # haut
            (0.0, 1.0, 1.0, 1.0),   # gauche
            (2.0, 1.0, 1.0, 1.0),   # droite
        )
    )
    assert diag.part_trou == pytest.approx(1.0 / 9.0)
    assert diag.part_jour == pytest.approx(diag.part_trou)


def test_des_pieces_separees_forment_un_archipel() -> None:
    """Le nombre de morceaux est ce qui distingue un plan abîmé d'un plan absent.

    Trois pièces disjointes ne sont pas un appartement à réparer : aucune trame ne
    les rattrapera à budget raisonnable. C'est le régime observé sur les sorties
    de HouseDiffusion (`resultats/j8_*.md`).
    """
    diag = diagnostiquer(
        _plan((0.0, 0.0, 1.0, 1.0), (3.0, 0.0, 1.0, 1.0), (6.0, 0.0, 1.0, 1.0))
    )
    assert diag.morceaux == 3
    assert diag.recouvrements == 0.0


def test_les_cellules_explosent_quand_aucun_bord_ne_coincide() -> None:
    """Trois pièces alignées sur les mêmes lignes : 3 cellules. Décalées : 25.

    C'est la mesure qui dit si la structure combinatoire du pavage existe. Sur un
    plan réel les pièces partagent leurs murs ; sur une sortie de modèle, presque
    aucune coordonnée ne coïncide et la trame enfle.
    """
    alignees = diagnostiquer(
        _plan((0.0, 0.0, 1.0, 2.0), (1.0, 0.0, 1.0, 2.0), (2.0, 0.0, 1.0, 2.0))
    )
    decalees = diagnostiquer(
        _plan((0.0, 0.0, 1.0, 2.0), (1.3, 0.4, 1.1, 2.0), (2.7, 0.9, 1.2, 2.0))
    )
    assert alignees.cellules == 3
    assert decalees.cellules == 25


def test_le_cote_donne_l_echelle_du_deplacement() -> None:
    """``cote`` est la racine de l'aire englobante : 5 m sur 10 m se lit autrement."""
    assert diagnostiquer(_plan((0.0, 0.0, 4.0, 9.0))).cote == pytest.approx(6.0)


def test_un_plan_sans_piece_leve() -> None:
    """Rendre des zéros laisserait croire à un plan sain : on refuse."""
    with pytest.raises(ValueError, match="rien à diagnostiquer"):
        diagnostiquer(_plan())


@pytest.mark.parametrize("facteur", [0.1, 1.0, 7.5])
def test_les_parts_sont_invariantes_d_echelle(facteur: float) -> None:
    """Jour, trou et recouvrement sont des ratios : les mètres n'y entrent pas.

    C'est ce qui autorise à comparer des plans RPLAN — sans unité — à des plans
    MSD en mètres, et ce qui rend le choix d'échelle du jalon 8 sans effet sur
    les taux rapportés.
    """
    boites = ((0.0, 0.0, 2.0, 2.0), (1.0, 2.0, 2.0, 2.0))
    reference = diagnostiquer(_plan(*boites))
    mis_a_l_echelle = diagnostiquer(
        _plan(*((x * facteur, y * facteur, w * facteur, h * facteur)
                for x, y, w, h in boites))
    )
    assert mis_a_l_echelle.part_jour == pytest.approx(reference.part_jour)
    assert mis_a_l_echelle.part_trou == pytest.approx(reference.part_trou)
    assert mis_a_l_echelle.recouvrements == reference.recouvrements
    assert mis_a_l_echelle.cote == pytest.approx(reference.cote * facteur)
