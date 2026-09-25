"""Vérification exacte — `MILESTONE-2.md` §6.

Les cas sont des géométries calculables à la main, pas des oracles du solveur.
"""

from __future__ import annotations

from archlux.certify.proof import verify_exactly
from archlux.types import (
    Context,
    Orientation,
    Plan,
    Regulation,
    Room,
    Structure,
    Wall,
)
from tests.proprietes.strategies import CONTEXTE_DEFAUT

CTX = CONTEXTE_DEFAUT


def _plan(*pieces: Room) -> Plan:
    return Plan(rooms=pieces, walls=(), openings=(), outline=CTX.outline)


class TestChevauchement:
    def test_detecte_un_chevauchement(self) -> None:
        """Deux carrés 2×2 dont l'intersection fait 1 m²."""
        a = Room(id="cuisine", type="cuisine", x=0.0, y=0.0, w=2.0, h=2.0)
        b = Room(id="sdb", type="sdb", x=1.0, y=0.0, w=2.0, h=2.0)
        preuve = verify_exactly(_plan(a, b), CTX)
        assert preuve.overlap is True
        assert preuve.valide is False
        assert any("overlap cuisine|sdb" in v for v in preuve.violations)

    def test_deux_pieces_disjointes_ne_se_chevauchent_pas(self) -> None:
        a = Room(id="a", type="sejour", x=0.0, y=0.0, w=2.0, h=2.0)
        b = Room(id="b", type="sejour", x=3.0, y=0.0, w=2.0, h=2.0)
        assert verify_exactly(_plan(a, b), CTX).overlap is False


class TestJours:
    def test_detecte_un_jour(self) -> None:
        """Une pièce 2×2 dans 12×9 laisse un jour d'aire 108 − 4 = 104 m²."""
        p = Room(id="a", type="sejour", x=0.0, y=0.0, w=2.0, h=2.0)
        preuve = verify_exactly(_plan(p), CTX)
        assert preuve.gaps is True
        assert preuve.valide is False


class TestSurfaces:
    def test_surface_insuffisante(self) -> None:
        ctx = Context(
            structure=Structure(load_bearing_walls=()),
            orientation=Orientation(deg=0.0),
            outline=CTX.outline,
            regulation=Regulation(min_areas=(("sdb", 5.0),), largeur_min=1.0),
        )
        p = Room(id="sdb", type="sdb", x=0.0, y=0.0, w=2.0, h=2.0)
        preuve = verify_exactly(_plan(p), ctx)
        assert preuve.areas_ok is False


class TestStructure:
    def test_mur_porteur_deplace(self) -> None:
        mur = Wall(id="p1", a=(0.0, 0.0), b=(3.0, 0.0), load_bearing=True)
        ctx = Context(
            structure=Structure(load_bearing_walls=(mur,)),
            orientation=Orientation(deg=0.0),
            outline=CTX.outline,
            regulation=Regulation(min_areas=(), largeur_min=1.0),
        )
        plan = Plan(
            rooms=(),
            walls=(Wall(id="p1", a=(0.0, 1.0), b=(3.0, 1.0), load_bearing=True),),
            openings=(),
            outline=CTX.outline,
        )
        preuve = verify_exactly(plan, ctx)
        assert preuve.structure_kept is False
