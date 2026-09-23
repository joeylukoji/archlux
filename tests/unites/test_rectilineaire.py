"""Décomposition rectilinéaire — `MILESTONE-6.md` §2. Convention : coupe verticale à gauche."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry import Polygon, box

from archlux.erreurs import InvariantViole
from archlux.geom.rectilineaire import (
    FUSION_DROIT,
    MAX_RECTANGLES,
    decomposer,
    recomposer,
)
from archlux.types import Piece, Plan
from tests.proprietes.strategies import CONTEXTE_DEFAUT


def _L() -> Polygon:
    """L classique : barre verticale 1×3 + embase 2×1, coupe verticale en x=1."""
    return Polygon([(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (1.0, 1.0), (1.0, 3.0), (0.0, 3.0)])


def test_rectangle_reste_un_seul_morceau() -> None:
    poly = box(0.0, 0.0, 4.0, 3.0)
    piece = decomposer(poly, id="sejour", type_piece="sejour")
    assert len(piece.rectangles) == 1
    assert piece.fusions == ()
    assert recomposer(piece).equals(poly)


def test_L_se_decoupe_en_deux_par_coupe_verticale_gauche() -> None:
    """Convention jalon 6 : coupe verticale au réflexe le plus à gauche."""
    piece = decomposer(_L(), id="cuisine", type_piece="cuisine")
    assert len(piece.rectangles) == 2
    assert len(piece.fusions) >= 1
    assert recomposer(piece).equals(_L())
    # La coupe en x=1 produit (0,0,1,3) et (1,0,1,1) — ordre déterministe.
    a, b = piece.rectangles
    assert { (round(a.x, 9), round(a.y, 9), round(a.w, 9), round(a.h, 9)),
             (round(b.x, 9), round(b.y, 9), round(b.w, 9), round(b.h, 9)) } == {
        (0.0, 0.0, 1.0, 3.0),
        (1.0, 0.0, 1.0, 1.0),
    }


def test_recomposer_inverse_decomposer() -> None:
    piece = decomposer(_L(), id="p", type_piece="sejour")
    assert recomposer(piece).equals(_L())


def test_polygone_non_rectilineaire_refuse() -> None:
    with pytest.raises(InvariantViole, match="rectilinéaire"):
        decomposer(Polygon([(0.0, 0.0), (2.0, 0.0), (1.0, 1.5)]))


def test_decomposition_est_deterministe() -> None:
    a = decomposer(_L(), id="p", type_piece="sejour")
    b = decomposer(_L(), id="p", type_piece="sejour")
    assert a == b


def _plan_avec_L(*, chevauche: bool = False) -> tuple[Plan, object]:
    """Pavage 12×9 contenant un L décomposé + trois rectangles complémentaires."""
    piece = decomposer(_L(), id="cuisine", type_piece="cuisine")
    x_r1 = 1.5 if chevauche else 2.0
    w_r1 = 10.5 if chevauche else 10.0
    reste = (
        Piece(id="r1", type="sejour", x=x_r1, y=0.0, w=w_r1, h=1.0),
        Piece(id="r2", type="sejour", x=1.0, y=1.0, w=11.0, h=2.0),
        Piece(id="r3", type="sejour", x=0.0, y=3.0, w=12.0, h=6.0),
    )
    plan = Plan(
        pieces=piece.rectangles + reste,
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )
    return plan, piece


def test_etendre_fusions_impose_egalite() -> None:
    from archlux.geom.graphe import deduire_ordre
    from archlux.geom.polytope import construire_polytope, vectoriser
    from archlux.geom.rectilineaire import etendre_fusions

    plan, piece = _plan_avec_L()
    poly = construire_polytope(deduire_ordre(plan), CONTEXTE_DEFAUT)
    poly = etendre_fusions(poly, piece)
    assert poly.A_eq.shape[0] >= 1
    assert poly.contient(vectoriser(plan, poly.index), tol=1e-6)


def test_legalize_preserve_validite_avec_L() -> None:
    """`MILESTONE-6.md` §2 : legalize sur un pavage contenant un L reste valide."""
    import archlux

    plan, piece = _plan_avec_L(chevauche=True)
    q = archlux.legalize(plan, CONTEXTE_DEFAUT, fusions=(piece,))
    assert q.certificat is not None
    assert q.certificat.geometrie.valide
    sous = sorted(
        (p for p in q.pieces if p.id.startswith("cuisine__")),
        key=lambda p: (p.x, p.y),
    )
    assert len(sous) == 2
    assert sous[0].x + sous[0].w == pytest.approx(sous[1].x, abs=1e-5)


@st.composite
def polygones_rectilineaires(draw: st.DrawFn) -> Polygon:
    """Rectangles et L générés sur une grille entière (reproductibles)."""
    if draw(st.booleans()):
        w = draw(st.integers(1, 5))
        h = draw(st.integers(1, 5))
        x = draw(st.integers(0, 3))
        y = draw(st.integers(0, 3))
        return box(float(x), float(y), float(x + w), float(y + h))
    # L : largeur embase 2..4, hauteur barre 2..5, épaisseur 1
    w = draw(st.integers(2, 4))
    h = draw(st.integers(2, 5))
    return Polygon(
        [
            (0.0, 0.0),
            (float(w), 0.0),
            (float(w), 1.0),
            (1.0, 1.0),
            (1.0, float(h)),
            (0.0, float(h)),
        ]
    )


@given(poly=polygones_rectilineaires())
@settings(max_examples=40, deadline=None)
def test_decomposition_recompose(poly: Polygon) -> None:
    """`MILESTONE-6.md` §2 : recomposer(decomposer(P)) = P."""
    piece = decomposer(poly, id="p", type_piece="sejour")
    assert recomposer(piece).equals(poly)
    assert 1 <= len(piece.rectangles) <= 4


def test_coupe_verticale_reunit_les_morceaux_colineaires() -> None:
    """L reel de MSD : la corde et l'arete de bord arrivent en morceaux separes.

    GEOS rend l'intersection de la verticale avec le polygone en plusieurs
    LineString colineaires et jointives au sommet reflexe. Retenir le premier
    revenait a proposer une arete du polygone comme coupe : elle ne separe rien,
    et `decomposer` levait « aucune coupe guillotine reproductible ». Sur MSD ce
    cas represente 1 219 pieces sur 4 456.
    """
    poly = Polygon(
        [
            (-1.785, -2.594),
            (-2.245, -2.594),
            (-2.245, -1.369),
            (-0.569, -1.369),
            (-0.569, -2.995),
            (-1.785, -2.995),
        ]
    )
    piece = decomposer(poly, id="p", type_piece="sejour")
    assert len(piece.rectangles) == 2
    assert piece.fusions == ((0, 1, FUSION_DROIT),)
    assert recomposer(piece).equals(poly)


def test_repli_horizontal_quand_aucune_verticale_ne_separe() -> None:
    """U couche : aucune corde verticale ne separe, la coupe horizontale si.

    La convention verticale de `MILESTONE-6.md` §2 garde la priorite ; le repli
    n'intervient que lorsqu'elle echoue.
    """
    poly = Polygon(
        [
            (0.0, 0.0),
            (3.0, 0.0),
            (3.0, 1.0),
            (1.0, 1.0),
            (1.0, 2.0),
            (3.0, 2.0),
            (3.0, 3.0),
            (0.0, 3.0),
        ]
    )
    piece = decomposer(poly, id="u", type_piece="sejour", max_rectangles=8)
    assert recomposer(piece).equals(poly)
    assert len(piece.rectangles) >= 3


def test_max_rectangles_par_defaut_reste_a_quatre() -> None:
    """Le plafond public ne bouge pas : contrat 1.x (`ARCHITECTURE.md` §8)."""
    assert MAX_RECTANGLES == 4
    # Peigne a trois dents : demande 6 rectangles, donc refuse au plafond par defaut.
    peigne = Polygon(
        [
            (0.0, 0.0), (6.0, 0.0), (6.0, 1.0), (5.0, 1.0), (5.0, 2.0),
            (4.0, 2.0), (4.0, 1.0), (3.0, 1.0), (3.0, 2.0), (2.0, 2.0),
            (2.0, 1.0), (1.0, 1.0), (1.0, 2.0), (0.0, 2.0),
        ]
    )
    with pytest.raises(InvariantViole, match="trop de rectangles"):
        decomposer(peigne, id="e", type_piece="sejour")
    piece = decomposer(peigne, id="e", type_piece="sejour", max_rectangles=8)
    assert len(piece.rectangles) == 6
    assert recomposer(piece).equals(peigne)
