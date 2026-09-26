"""Les plages documentées par `ARCHITECTURE.md` §6 sont vérifiées **à la frontière**.

Décision d'architecture (ADR-6) : la validation a lieu en lecture JSON, pas dans les
constructeurs. Les données venues de l'extérieur sont garanties saines ; l'objet en
mémoire reste libre, de sorte que le solveur puisse traverser des états intermédiaires
sans payer une validation à chaque construction.
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


def _avec(chemin: list[str | int], valeur: object) -> dict:
    """Copier le plan de référence en remplaçant un champ par une valeur fautive."""
    donnees = to_dict(PLAN)
    cible = donnees
    for cle in chemin[:-1]:
        cible = cible[cle]  # type: ignore[index]
    cible[chemin[-1]] = valeur  # type: ignore[index]
    return donnees


class TestPlagesOuverture:
    """`s ∈ [0, 1]` et `relative_width ∈ ]0, 1]`."""

    @pytest.mark.parametrize("s", [-0.01, 1.5])
    def test_abscisse_hors_plage(self, s: float) -> None:
        """Une baie hors de son mur n'a pas de position dérivable."""
        with pytest.raises(InvariantViolation, match="s"):
            from_dict(_avec(["openings", 0, "s"], s))

    @pytest.mark.parametrize("s", [0.0, 1.0])
    def test_les_bornes_sont_incluses(self, s: float) -> None:
        """Une baie en bout de mur est licite : l'intervalle est fermé."""
        assert from_dict(_avec(["openings", 0, "s"], s)).openings[0].s == s

    @pytest.mark.parametrize("largeur", [0.0, -0.5, 1.01])
    def test_largeur_relative_hors_plage(self, largeur: float) -> None:
        """Une largeur nulle ou négative n'est pas une baie ; au-delà de 1, elle déborde."""
        with pytest.raises(InvariantViolation, match="relative_width"):
            from_dict(_avec(["openings", 0, "relative_width"], largeur))

    def test_une_baie_pleine_largeur_est_licite(self) -> None:
        """``relative_width = 1`` est la borne haute, incluse."""
        relu = from_dict(_avec(["openings", 0, "relative_width"], 1.0))
        assert relu.openings[0].relative_width == 1.0


class TestPlagesPiece:
    """Une pièce a des dimensions strictement positives."""

    @pytest.mark.parametrize("champ", ["w", "h"])
    @pytest.mark.parametrize("valeur", [0.0, -2.0])
    def test_dimension_non_positive(self, champ: str, valeur: float) -> None:
        """Une pièce de largeur nulle ou négative casserait le polytope en silence."""
        with pytest.raises(InvariantViolation, match=champ):
            from_dict(_avec(["rooms", 0, champ], valeur))


class TestPlagesMur:
    """Un mur a une épaisseur strictement positive."""

    def test_epaisseur_non_positive(self) -> None:
        """Une épaisseur nulle rendrait la structure porteuse inexistante."""
        with pytest.raises(InvariantViolation, match="thickness"):
            from_dict(_avec(["walls", 0, "thickness"], 0.0))


class TestValeursNonFinies:
    """`ecrire` refuse d'écrire `NaN` ; `charger` doit refuser de le lire.

    ``json.loads`` accepte les littéraux ``NaN`` et ``Infinity`` par défaut. Sans cette
    garde, un fichier non écrit par archlux introduirait des ``NaN`` dans le solveur.
    """

    def test_nan_dans_un_champ(self) -> None:
        """Une coordonnée ``NaN`` est refusée à la lecture."""
        with pytest.raises(InvariantViolation, match="non-finite"):
            from_dict(_avec(["rooms", 0, "x"], float("nan")))

    def test_infini_dans_un_point(self) -> None:
        """Un sommet de contour infini également."""
        with pytest.raises(InvariantViolation, match="non-finite"):
            from_dict(_avec(["outline", 0], [float("inf"), 0.0]))

    def test_nan_lu_depuis_un_fichier(self, tmp_path: Path) -> None:
        """Le cas réel : un fichier produit par un autre outil."""
        chemin = tmp_path / "nan.json"
        chemin.write_text(
            '{"schema": "1", "contour": [[NaN, 0.0]], "pieces": [], "murs": [],'
            ' "ouvertures": [], "certificat": null}',
            encoding="utf-8",
        )
        with pytest.raises(InvariantViolation, match="non-finite"):
            load(chemin)


class TestDiagnostic:
    """Le refus rapporte **toutes** les violations, pas seulement la première."""

    def test_les_violations_sont_toutes_listees(self) -> None:
        """Corriger un fichier une erreur à la fois est un supplice inutile."""
        donnees = to_dict(PLAN)
        donnees["rooms"][0]["w"] = -1.0
        donnees["openings"][0]["s"] = 3.0
        with pytest.raises(InvariantViolation) as capture:
            from_dict(donnees)
        message = str(capture.value)
        assert "w" in message
        assert "s" in message


def test_un_plan_valide_passe_toujours() -> None:
    """La validation ne doit rien rejeter de licite."""
    assert from_dict(to_dict(PLAN)) == PLAN
