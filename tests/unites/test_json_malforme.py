"""Entrées malformées : le format est refusé, jamais deviné.

Un plan mal relu produirait un certificat faux — c'est-à-dire une garantie affirmée sur
une géométrie qui n'est pas celle du fichier. Chaque branche de refus a donc son test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.erreurs import InvariantViole
from archlux.io.json_io import charger, depuis_dict, vers_dict
from archlux.types import Mur, Ouverture, Piece, Plan

PLAN = Plan(
    pieces=(Piece(id="sejour", type="sejour", x=0.0, y=0.0, w=4.0, h=3.5),),
    murs=(Mur(id="m", a=(0.0, 0.0), b=(4.0, 0.0)),),
    ouvertures=(Ouverture(id="f", mur_id="m", s=0.5, largeur_rel=0.2),),
    contour=((0.0, 0.0), (4.0, 0.0), (4.0, 3.5), (0.0, 3.5)),
)


class TestStructureInvalide:
    """Refus au niveau de la structure."""

    def test_un_point_mal_forme(self) -> None:
        """Un contour dont un sommet n'est pas ``[x, y]``."""
        donnees = vers_dict(PLAN)
        donnees["contour"] = [[0.0, 0.0], [1.0, 2.0, 3.0]]
        with pytest.raises(InvariantViole, match="point attendu"):
            depuis_dict(donnees)

    def test_un_champ_manquant(self) -> None:
        """Une pièce sans hauteur ne peut pas être devinée."""
        donnees = vers_dict(PLAN)
        del donnees["pieces"][0]["h"]
        with pytest.raises(InvariantViole, match="structure JSON invalide"):
            depuis_dict(donnees)

    def test_un_champ_non_numerique(self) -> None:
        """Une largeur textuelle est refusée, pas convertie au petit bonheur."""
        donnees = vers_dict(PLAN)
        donnees["pieces"][0]["w"] = "large"
        with pytest.raises(InvariantViole, match="structure JSON invalide"):
            depuis_dict(donnees)

    def test_un_indicateur_inconnu(self) -> None:
        """Un indicateur hors des quatre connus invaliderait la borne conforme."""
        donnees = vers_dict(PLAN)
        donnees["certificat"] = {
            "geometrie": {
                "valide": True,
                "chevauchement": False,
                "jours": False,
                "surfaces_ok": True,
                "structure_preservee": True,
                "deplacement_max": 0.0,
                "violations": [],
            },
            "performance": {
                "indicateur": "confort_thermique",
                "valeur": 0.5,
                "borne_inf": 0.4,
                "borne_sup": 0.6,
                "couverture": 0.9,
                "n_calibration": 100,
            },
            "duaux": [],
            "manifeste": None,
        }
        with pytest.raises(InvariantViole, match="indicateur inconnu"):
            depuis_dict(donnees)


class TestFichierInvalide:
    """Refus au niveau du fichier."""

    def test_du_texte_qui_n_est_pas_du_json(self, tmp_path: Path) -> None:
        """Un fichier tronqué ou corrompu."""
        chemin = tmp_path / "casse.json"
        chemin.write_text("{ceci n'est pas du json", encoding="utf-8")
        with pytest.raises(InvariantViole, match="pas du JSON valide"):
            charger(chemin)

    def test_du_json_qui_n_est_pas_un_objet(self, tmp_path: Path) -> None:
        """Une liste de plans n'est pas un plan ; le dire plutôt que d'échouer plus loin."""
        chemin = tmp_path / "liste.json"
        chemin.write_text("[]", encoding="utf-8")
        with pytest.raises(InvariantViole, match="objet JSON"):
            charger(chemin)
