"""Contraintes de pavage exact — `geom.pavage`.

La these du module : la condition de pavage est **combinatoire**. Elle ne porte
que sur les incidences bord/ligne, jamais sur les coordonnees. Ces tests pinnent
cette propriete, et le fait qu'un jour devient non representable.
"""

from __future__ import annotations

import numpy as np
import pytest

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.errors import GridNotRecoverable, UnsupportedInput
from archlux.geom.pavage import deduce_grid
from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure

_RECT = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def _ctx(contour: tuple[tuple[float, float], ...] = _RECT) -> Context:
    return Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=contour,
        regulation=Regulation(min_areas=(), min_width=0.0),
    )


def _pavage_2x2(largeur_sw: float = 5.0) -> Plan:
    """Pavage 2x2 ; `largeur_sw` < 5 ouvre un jour sous la piece nord-ouest."""
    return Plan(
        rooms=(
            Room(id="sw", type="living_room", x=0.0, y=0.0, w=largeur_sw, h=4.0),
            Room(id="se", type="bedroom", x=5.0, y=0.0, w=7.0, h=4.0),
            Room(id="nw", type="kitchen", x=0.0, y=4.0, w=5.0, h=5.0),
            Room(id="ne", type="bathroom", x=5.0, y=4.0, w=7.0, h=5.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )


def _moulin() -> Plan:
    """Moulin a vent : 5 rectangles, dissection **non tranchable**."""
    contour = ((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))
    return Plan(
        rooms=(
            Room(id="A", type="living_room", x=0.0, y=6.0, w=6.0, h=3.0),
            Room(id="B", type="living_room", x=6.0, y=3.0, w=3.0, h=6.0),
            Room(id="C", type="living_room", x=3.0, y=0.0, w=6.0, h=3.0),
            Room(id="D", type="living_room", x=0.0, y=0.0, w=3.0, h=6.0),
            Room(id="E", type="living_room", x=3.0, y=3.0, w=3.0, h=3.0),
        ),
        walls=(),
        openings=(),
        outline=contour,
    )


def test_trame_d_un_pavage_sain() -> None:
    """Les lignes sont les bords partages, pas un bord par piece."""
    grid = deduce_grid(_pavage_2x2(), _ctx())
    assert grid.x_lines == (0.0, 5.0, 12.0)
    assert grid.y_lines == (0.0, 4.0, 9.0)
    assert grid.n_cells == 4


def test_dissection_non_tranchable_est_acceptee() -> None:
    """Le moulin a vent n'est decoupable par aucune coupe guillotine.

    C'est le cas qui distingue une vraie condition de pavage d'une hypothese de
    sliceabilite : les 9 cellules forment bien une partition.
    """
    grid = deduce_grid(_moulin(), _ctx(((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))))
    assert grid.n_cells == 9
    assert len(grid.incidences) == 5


def test_contour_rectilineaire_est_accepte() -> None:
    """Un contour en L : les cellules hors contour doivent rester vides.

    Exiger le pavage de la **boite englobante** rejetterait tout appartement reel.
    """
    contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 4.0), (5.0, 4.0), (5.0, 9.0), (0.0, 9.0))
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=5.0, h=4.0),
            Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=4.0),
            Room(id="c", type="kitchen", x=0.0, y=4.0, w=5.0, h=5.0),
        ),
        walls=(),
        openings=(),
        outline=contour,
    )
    grid = deduce_grid(plan, _ctx(contour))
    assert grid.x_lines == (0.0, 5.0, 12.0)
    # Toutes les lignes portent un sommet du contour : aucune ne peut glisser.
    assert grid.anchored_x == frozenset({0, 1, 2})


@pytest.mark.parametrize("jour", [0.05, 0.5, 2.0])
def test_le_support_recupere_la_trame_quelle_que_soit_l_amplitude(jour: float) -> None:
    """Une ligne orpheline est resorbee, sans aucun seuil en metres.

    C'est ce qui distingue le critere de support d'une tolerance metrique : un
    jour de 2 m se rattrape aussi bien qu'un jour de 5 cm.
    """
    grid = deduce_grid(_pavage_2x2(largeur_sw=5.0 - jour), _ctx())
    assert grid.x_lines == (0.0, 5.0, 12.0)


def test_une_cloison_etroite_n_est_pas_ecrasee() -> None:
    """Le refus d'ecraser une piece borne la consolidation."""
    plan = Plan(
        rooms=(
            Room(id="corridor", type="corridor", x=0.0, y=0.0, w=0.4, h=9.0),
            Room(id="living_room", type="living_room", x=0.4, y=0.0, w=11.6, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    assert deduce_grid(plan, _ctx()).x_lines == (0.0, 0.4, 12.0)


def _trois_pieces_sur_quatre() -> Plan:
    """Pavage 2x2 ampute de sa piece nord-est : une cellule reste vide."""
    return Plan(
        rooms=(
            Room(id="sw", type="living_room", x=0.0, y=0.0, w=5.0, h=4.0),
            Room(id="se", type="bedroom", x=5.0, y=0.0, w=7.0, h=4.0),
            Room(id="nw", type="kitchen", x=0.0, y=4.0, w=5.0, h=5.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )


def test_jour_structurel_est_detecte_sans_budget() -> None:
    """`repair_budget=0` : la partition est verifiee, jamais retouchee."""
    with pytest.raises(GridNotRecoverable, match="uncovered"):
        deduce_grid(_trois_pieces_sur_quatre(), _ctx(), repair_budget=0)


def test_une_piece_manquante_est_absorbee_par_sa_voisine() -> None:
    """Conséquence semantique a connaitre : le programme change.

    Avec le budget par defaut, la cellule vide est rendue a une piece voisine
    plutot que refusee. C'est le comportement attendu d'un legaliseur — fermer un
    jour, c'est agrandir quelqu'un — mais le plan sort avec **une piece de moins**
    que ce que le generateur avait prevu. Un appelant qui doit preserver le
    programme piece par piece passe `repair_budget=0`.
    """
    plan = _trois_pieces_sur_quatre()
    grid = deduce_grid(plan, _ctx())
    aires = {inc[0]: (inc[2] - inc[1]) * (inc[4] - inc[3]) for inc in grid.incidences}
    assert sum(aires.values()) == grid.n_cells  # la grille est entierement couverte
    assert len(grid.incidences) == 3

    corrige = ax.legalize(plan, _ctx(), tiling=True)
    assert corrige.certificate is not None
    assert corrige.certificate.geometry.valid
    assert len(corrige.rooms) == 3


def test_le_budget_borne_la_reparation() -> None:
    """Au-dela du budget, la faute n'est plus une cote fausse : on refuse."""
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=2.0, h=3.0),
            Room(id="b", type="bedroom", x=4.0, y=6.0, w=2.0, h=3.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    with pytest.raises(GridNotRecoverable):
        deduce_grid(plan, _ctx(), repair_budget=1)


@pytest.mark.parametrize("budget", [0, 1, 2, 4, 8])
@pytest.mark.parametrize("degat", [0.05, 0.5, 2.0, 6.0])
def test_toute_trame_rendue_est_une_partition_valide(budget: int, degat: float) -> None:
    """Propriete centrale : `deduire_trame` refuse, ou rend une partition exacte.

    Elle ne doit **jamais** rendre une structure a demi reparee : ni cellule vide,
    ni cellule doublement couverte, ni piece aux bords inverses. C'est cette
    propriete qui autorise `etendre_pavage` a garantir le pavage sans verification
    a l'execution.
    """
    plan = _pavage_2x2(largeur_sw=max(0.5, 5.0 - degat))
    try:
        grid = deduce_grid(plan, _ctx(), repair_budget=budget)
    except GridNotRecoverable:
        return  # refus explicite : c'est l'autre branche du contrat
    grille = np.zeros((len(grid.x_lines) - 1, len(grid.y_lines) - 1), dtype=int)
    for name, gauche, droite, low, high in grid.incidences:
        assert gauche < droite, f"{name} a ses bords inverses en x"
        assert low < high, f"{name} a ses bords inverses en y"
        grille[gauche:droite, low:high] += 1
    assert np.all(grille == 1), "la trame rendue n'est pas une partition"


def test_la_reparation_ne_change_pas_un_plan_sain() -> None:
    """Sur une partition deja exacte, aucune retouche n'est appliquee."""
    sain = deduce_grid(_pavage_2x2(), _ctx(), repair_budget=0)
    avec = deduce_grid(_pavage_2x2(), _ctx(), repair_budget=8)
    assert sain == avec


def test_chevauchement_simple_est_resorbe_par_le_support() -> None:
    """Deux bords orphelins qui se chevauchent fusionnent sur une ligne commune.

    C'est le comportement voulu : un chevauchement de 2 m entre deux pieces
    voisines est une intention d'adjacence mal cotee, pas une incoherence d'ordre.
    """
    plan = Plan(
        rooms=(
            Room(id="a", type="living_room", x=0.0, y=0.0, w=7.0, h=9.0),
            Room(id="b", type="bedroom", x=5.0, y=0.0, w=7.0, h=9.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    grid = deduce_grid(plan, _ctx())
    assert len(grid.x_lines) == 3
    gauches = {inc[0]: inc[1:3] for inc in grid.incidences}
    assert gauches["a"][1] == gauches["b"][0]  # a se termine ou b commence


def test_chevauchement_structurel_est_refuse() -> None:
    """Une piece **contenue** dans une autre : aucune fusion de lignes ne la sauve."""
    plan = Plan(
        rooms=(
            Room(id="englobante", type="living_room", x=0.0, y=0.0, w=12.0, h=9.0),
            Room(id="incluse", type="bedroom", x=0.0, y=0.0, w=5.0, h=4.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    with pytest.raises(GridNotRecoverable, match="covered twice"):
        deduce_grid(plan, _ctx())


def test_legalize_avec_pavage_ferme_un_jour() -> None:
    """Le cas que `legalize` seul ne sait pas corriger.

    Sans `tiling=True`, le plan troue est deja le plus proche de lui-meme :
    l'optimum L1 le laisse tel quel et la verification exacte le rejette.
    """
    abime = _pavage_2x2(largeur_sw=4.5)
    ctx = _ctx()
    assert not verify_exactly(abime, ctx).valid

    with pytest.raises(ax.GapNeedsTiling, match="tiling=True"):
        ax.legalize(abime, ctx)

    corrige = ax.legalize(abime, ctx, tiling=True)
    assert corrige.certificate is not None
    assert corrige.certificate.geometry.valid
    assert not corrige.certificate.geometry.gaps


def test_pavage_preserve_l_idempotence() -> None:
    """Sur un plan deja valide, `tiling=True` ne deplace rien."""
    ctx = _ctx()
    corrige = ax.legalize(_pavage_2x2(), ctx, tiling=True)
    assert corrige.certificate is not None
    assert corrige.certificate.geometry.max_displacement == pytest.approx(0.0, abs=1e-9)


def test_pavage_est_invariant_par_translation_des_lignes() -> None:
    """La these du module : la condition ne porte que sur les incidences.

    Deux plans de meme structure combinatoire mais de coordonnees differentes ont
    la meme trame en indices, et les deux sont des pavages valides.
    """
    ctx = _ctx()
    a = deduce_grid(_pavage_2x2(), ctx)
    decale = Plan(
        rooms=(
            Room(id="sw", type="living_room", x=0.0, y=0.0, w=3.0, h=6.0),
            Room(id="se", type="bedroom", x=3.0, y=0.0, w=9.0, h=6.0),
            Room(id="nw", type="kitchen", x=0.0, y=6.0, w=3.0, h=3.0),
            Room(id="ne", type="bathroom", x=3.0, y=6.0, w=9.0, h=3.0),
        ),
        walls=(),
        openings=(),
        outline=_RECT,
    )
    b = deduce_grid(decale, ctx)
    assert [inc[1:] for inc in a.incidences] == [inc[1:] for inc in b.incidences]
    assert a.x_lines != b.x_lines
    assert verify_exactly(decale, ctx).valid


def test_egalites_de_pavage_ne_polluent_pas_le_diagnostic_dual() -> None:
    """Les contraintes de pavage sont des egalites : elles ne sont pas dualisees."""
    ctx = _ctx()
    sans = ax.legalize(_pavage_2x2(), ctx)
    avec = ax.legalize(_pavage_2x2(), ctx, tiling=True)
    assert sans.certificate is not None
    assert avec.certificate is not None
    libelles = {libelle for libelle, _ in avec.certificate.duals}
    assert not any(name.startswith(("trame ", "contour ")) for name in libelles)


def test_plan_sans_piece_est_refuse() -> None:
    """Erreur typee, jamais un IndexError nu."""
    vide = Plan(rooms=(), walls=(), openings=(), outline=_RECT)
    with pytest.raises(UnsupportedInput, match="no room"):
        deduce_grid(vide, _ctx())


def test_trame_est_deterministe() -> None:
    """Deux appels sur le meme plan rendent exactement la meme trame."""
    plan = _pavage_2x2(largeur_sw=4.7)
    a = deduce_grid(plan, _ctx())
    b = deduce_grid(plan, _ctx())
    assert a == b
    assert np.allclose(a.x_lines, b.x_lines)
