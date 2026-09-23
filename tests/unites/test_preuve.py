"""Vérification exacte — `MILESTONE-2.md` §6.

Les cas sont des géométries calculables à la main, pas des oracles du solveur.
"""

from __future__ import annotations

from archlux.certify.preuve import verifier_exactement
from archlux.types import (
    Contexte,
    Mur,
    Orientation,
    Piece,
    Plan,
    Referentiel,
    Structure,
)
from tests.proprietes.strategies import CONTEXTE_DEFAUT

CTX = CONTEXTE_DEFAUT


def _plan(*pieces: Piece) -> Plan:
    return Plan(pieces=pieces, murs=(), ouvertures=(), contour=CTX.contour)


class TestChevauchement:
    def test_detecte_un_chevauchement(self) -> None:
        """Deux carrés 2×2 dont l'intersection fait 1 m²."""
        a = Piece(id="cuisine", type="cuisine", x=0.0, y=0.0, w=2.0, h=2.0)
        b = Piece(id="sdb", type="sdb", x=1.0, y=0.0, w=2.0, h=2.0)
        preuve = verifier_exactement(_plan(a, b), CTX)
        assert preuve.chevauchement is True
        assert preuve.valide is False
        assert any("chevauchement cuisine|sdb" in v for v in preuve.violations)

    def test_deux_pieces_disjointes_ne_se_chevauchent_pas(self) -> None:
        a = Piece(id="a", type="sejour", x=0.0, y=0.0, w=2.0, h=2.0)
        b = Piece(id="b", type="sejour", x=3.0, y=0.0, w=2.0, h=2.0)
        assert verifier_exactement(_plan(a, b), CTX).chevauchement is False


class TestJours:
    def test_detecte_un_jour(self) -> None:
        """Une pièce 2×2 dans 12×9 laisse un jour d'aire 108 − 4 = 104 m²."""
        p = Piece(id="a", type="sejour", x=0.0, y=0.0, w=2.0, h=2.0)
        preuve = verifier_exactement(_plan(p), CTX)
        assert preuve.jours is True
        assert preuve.valide is False


class TestSurfaces:
    def test_surface_insuffisante(self) -> None:
        ctx = Contexte(
            structure=Structure(murs_porteurs=()),
            orientation=Orientation(deg=0.0),
            contour=CTX.contour,
            referentiel=Referentiel(aires_min=(("sdb", 5.0),), largeur_min=1.0),
        )
        p = Piece(id="sdb", type="sdb", x=0.0, y=0.0, w=2.0, h=2.0)
        preuve = verifier_exactement(_plan(p), ctx)
        assert preuve.surfaces_ok is False


class TestStructure:
    def test_mur_porteur_deplace(self) -> None:
        mur = Mur(id="p1", a=(0.0, 0.0), b=(3.0, 0.0), porteur=True)
        ctx = Contexte(
            structure=Structure(murs_porteurs=(mur,)),
            orientation=Orientation(deg=0.0),
            contour=CTX.contour,
            referentiel=Referentiel(aires_min=(), largeur_min=1.0),
        )
        plan = Plan(
            pieces=(),
            murs=(Mur(id="p1", a=(0.0, 1.0), b=(3.0, 1.0), porteur=True),),
            ouvertures=(),
            contour=CTX.contour,
        )
        preuve = verifier_exactement(plan, ctx)
        assert preuve.structure_preservee is False
