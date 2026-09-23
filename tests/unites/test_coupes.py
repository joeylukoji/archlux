"""Coupes de surface — `MILESTONE-2.md` §5.

Les valeurs attendues sont des littéraux indépendants de l'implémentation : AM-GM
donne l'égalité sur l'hyperbole, pas un recalcul du code.
"""

from __future__ import annotations

import pytest

from archlux.erreurs import InvariantViole
from archlux.geom.graphe import OrdreRelatif
from archlux.geom.polytope import construire_polytope
from archlux.lmo.coupes import coupe_surface, surfaces_violees
from archlux.types import Contexte, Orientation, Piece, Referentiel, Structure

CTX = Contexte(
    structure=Structure(murs_porteurs=()),
    orientation=Orientation(deg=0.0),
    contour=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    referentiel=Referentiel(aires_min=(("sejour", 9.0),), largeur_min=1.5),
)


class TestTangente:
    """Formule : h₀ w + w₀ h ≥ 2a au point de l'hyperbole w₀ h₀ = a."""

    def test_egalite_sur_le_point_de_linearisation(self) -> None:
        """(w, h) = (3, 3), a = 9 : 3·3 + 3·3 = 18 = 2a."""
        coupe = coupe_surface(3.0, 3.0, 9.0)
        assert coupe.satisfait(3.0, 3.0)
        assert coupe.borne_inf == pytest.approx(18.0)

    def test_un_rectangle_plus_grand_passe(self) -> None:
        """4 × 3 = 12 > 9 : le point reste du bon côté de la tangente."""
        assert coupe_surface(3.0, 3.0, 9.0).satisfait(4.0, 3.0)

    def test_un_carre_trop_petit_est_coupe(self) -> None:
        """2 × 2 = 4 < 9. Après projection, la tangente exclut ce point."""
        assert not coupe_surface(2.0, 2.0, 9.0).satisfait(2.0, 2.0)

    def test_origine_porte_la_piece(self) -> None:
        assert "sejour" in coupe_surface(3.0, 3.0, 9.0, piece="sejour").origine

    def test_un_point_degenere_est_refuse(self) -> None:
        with pytest.raises(InvariantViole, match="strictement positif"):
            coupe_surface(0.0, 3.0, 9.0)


class TestSurfacesViolees:
    """Lecture directe de w·h contre a_min, sans passer par le solveur."""

    def test_une_piece_sous_le_seuil_est_listée(self) -> None:
        poly = construire_polytope(OrdreRelatif((), (), ("A",)), CTX)
        # A.x, A.y, A.w, A.h
        x = [0.0, 0.0, 2.0, 2.0]
        pieces = (Piece(id="A", type="sejour", x=0.0, y=0.0, w=2.0, h=2.0),)
        assert surfaces_violees(x, poly, CTX, pieces=pieces) == ("A",)

    def test_une_piece_au_seuil_n_est_pas_listée(self) -> None:
        poly = construire_polytope(OrdreRelatif((), (), ("A",)), CTX)
        x = [0.0, 0.0, 3.0, 3.0]
        pieces = (Piece(id="A", type="sejour", x=0.0, y=0.0, w=3.0, h=3.0),)
        assert surfaces_violees(x, poly, CTX, pieces=pieces) == ()
