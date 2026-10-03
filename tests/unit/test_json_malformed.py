"""Entrées malformées : le format est refusé, jamais deviné.

Un plan mal relu produirait un certificat faux — c'est-à-dire une garantie affirmée sur
une géométrie qui n'est pas celle du fichier. Chaque branche de refus a donc son test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.errors import InvariantViolation
from archlux.io.json_io import from_dict, load, to_dict
from archlux.types import Opening, Plan, Room, Wall

PLAN = Plan(
    rooms=(Room(id="living_room", type="living_room", x=0.0, y=0.0, w=4.0, h=3.5),),
    walls=(Wall(id="m", a=(0.0, 0.0), b=(4.0, 0.0)),),
    openings=(Opening(id="f", wall_id="m", s=0.5, relative_width=0.2),),
    outline=((0.0, 0.0), (4.0, 0.0), (4.0, 3.5), (0.0, 3.5)),
)


class TestStructureInvalide:
    """Refus au niveau de la structure."""

    def test_un_point_mal_forme(self) -> None:
        """Un contour dont un sommet n'est pas ``[x, y]``."""
        donnees = to_dict(PLAN)
        donnees["outline"] = [[0.0, 0.0], [1.0, 2.0, 3.0]]
        with pytest.raises(InvariantViolation, match="expected a point"):
            from_dict(donnees)

    def test_un_champ_manquant(self) -> None:
        """Une pièce sans hauteur ne peut pas être devinée."""
        donnees = to_dict(PLAN)
        del donnees["rooms"][0]["h"]
        with pytest.raises(InvariantViolation, match="invalid JSON structure"):
            from_dict(donnees)

    def test_un_champ_non_numerique(self) -> None:
        """Une largeur textuelle est refusée, pas convertie au petit bonheur."""
        donnees = to_dict(PLAN)
        donnees["rooms"][0]["w"] = "large"
        with pytest.raises(InvariantViolation, match="invalid JSON structure"):
            from_dict(donnees)

    def test_un_indicateur_inconnu(self) -> None:
        """Un indicateur hors des quatre connus invaliderait la borne conforme."""
        donnees = to_dict(PLAN)
        donnees["certificate"] = {
            "geometry": {
                "valid": True,
                "overlap": False,
                "gaps": False,
                "areas_ok": True,
                "structure_kept": True,
                "max_displacement": 0.0,
                "violations": [],
            },
            "performance": {
                "indicator": "confort_thermique",
                "value": 0.5,
                "lower": 0.4,
                "upper": 0.6,
                "coverage": 0.9,
                "n_calibration": 100,
            },
            "duals": [],
            "manifest": None,
        }
        with pytest.raises(InvariantViolation, match="unknown indicator"):
            from_dict(donnees)


class TestFichierInvalide:
    """Refus au niveau du fichier."""

    def test_du_texte_qui_n_est_pas_du_json(self, tmp_path: Path) -> None:
        """Un fichier tronqué ou corrompu."""
        path = tmp_path / "casse.json"
        path.write_text("{ceci n'est pas du json", encoding="utf-8")
        with pytest.raises(InvariantViolation, match="not valid JSON"):
            load(path)

    def test_du_json_qui_n_est_pas_un_objet(self, tmp_path: Path) -> None:
        """Une liste de plans n'est pas un plan ; le dire plutôt que d'échouer plus loin."""
        path = tmp_path / "liste.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(InvariantViolation, match="JSON object"):
            load(path)


@pytest.mark.parametrize(
    ("key", "value"),
    [("pieces", [1]), ("pieces", None), ("pieces", {"a": 1}), ("ouvertures", None)],
)
def test_a_malformed_v1_file_is_refused_with_a_typed_error(key: str, value: object) -> None:
    """Review of the stack (#10): the v1 upgrade raised a bare TypeError before reading."""
    document = {
        "schema": "1",
        "contour": [[0, 0], [4, 0], [4, 3], [0, 3]],
        "pieces": [{"id": "a", "type": "sejour", "x": 0, "y": 0, "w": 4, "h": 3}],
        "murs": [],
        "ouvertures": [],
        "certificat": None,
    }
    document[key] = value
    with pytest.raises(InvariantViolation):
        from_dict(document)
