"""Contraintes de pavage exact — `geom.pavage`.

La these du module : la condition de pavage est **combinatoire**. Elle ne porte
que sur les incidences bord/ligne, jamais sur les coordonnees. Ces tests pinnent
cette propriete, et le fait qu'un jour devient non representable.
"""

from __future__ import annotations

import numpy as np
import pytest

import archlux as ax
from archlux.certify.preuve import verifier_exactement
from archlux.erreurs import InvariantViole
from archlux.geom.pavage import deduire_trame
from archlux.types import Contexte, Orientation, Piece, Plan, Referentiel, Structure

_RECT = ((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0))


def _ctx(contour: tuple[tuple[float, float], ...] = _RECT) -> Contexte:
    return Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=contour,
        referentiel=Referentiel(aires_min=(), largeur_min=0.0),
    )


def _pavage_2x2(largeur_sw: float = 5.0) -> Plan:
    """Pavage 2x2 ; `largeur_sw` < 5 ouvre un jour sous la piece nord-ouest."""
    return Plan(
        pieces=(
            Piece("sw", "sejour", 0.0, 0.0, largeur_sw, 4.0),
            Piece("se", "chambre", 5.0, 0.0, 7.0, 4.0),
            Piece("nw", "cuisine", 0.0, 4.0, 5.0, 5.0),
            Piece("ne", "sdb", 5.0, 4.0, 7.0, 5.0),
        ),
        murs=(),
        ouvertures=(),
        contour=_RECT,
    )


def _moulin() -> Plan:
    """Moulin a vent : 5 rectangles, dissection **non tranchable**."""
    contour = ((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))
    return Plan(
        pieces=(
            Piece("A", "sejour", 0.0, 6.0, 6.0, 3.0),
            Piece("B", "sejour", 6.0, 3.0, 3.0, 6.0),
            Piece("C", "sejour", 3.0, 0.0, 6.0, 3.0),
            Piece("D", "sejour", 0.0, 0.0, 3.0, 6.0),
            Piece("E", "sejour", 3.0, 3.0, 3.0, 3.0),
        ),
        murs=(),
        ouvertures=(),
        contour=contour,
    )


def test_trame_d_un_pavage_sain() -> None:
    """Les lignes sont les bords partages, pas un bord par piece."""
    trame = deduire_trame(_pavage_2x2(), _ctx())
    assert trame.lignes_x == (0.0, 5.0, 12.0)
    assert trame.lignes_y == (0.0, 4.0, 9.0)
    assert trame.n_cellules == 4


def test_dissection_non_tranchable_est_acceptee() -> None:
    """Le moulin a vent n'est decoupable par aucune coupe guillotine.

    C'est le cas qui distingue une vraie condition de pavage d'une hypothese de
    sliceabilite : les 9 cellules forment bien une partition.
    """
    trame = deduire_trame(_moulin(), _ctx(((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))))
    assert trame.n_cellules == 9
    assert len(trame.incidences) == 5


def test_contour_rectilineaire_est_accepte() -> None:
    """Un contour en L : les cellules hors contour doivent rester vides.

    Exiger le pavage de la **boite englobante** rejetterait tout appartement reel.
    """
    contour = ((0.0, 0.0), (12.0, 0.0), (12.0, 4.0), (5.0, 4.0), (5.0, 9.0), (0.0, 9.0))
    plan = Plan(
        pieces=(
            Piece("a", "sejour", 0.0, 0.0, 5.0, 4.0),
            Piece("b", "chambre", 5.0, 0.0, 7.0, 4.0),
            Piece("c", "cuisine", 0.0, 4.0, 5.0, 5.0),
        ),
        murs=(),
        ouvertures=(),
        contour=contour,
    )
    trame = deduire_trame(plan, _ctx(contour))
    assert trame.lignes_x == (0.0, 5.0, 12.0)
    # Toutes les lignes portent un sommet du contour : aucune ne peut glisser.
    assert trame.ancrees_x == frozenset({0, 1, 2})


@pytest.mark.parametrize("jour", [0.05, 0.5, 2.0])
def test_le_support_recupere_la_trame_quelle_que_soit_l_amplitude(jour: float) -> None:
    """Une ligne orpheline est resorbee, sans aucun seuil en metres.

    C'est ce qui distingue le critere de support d'une tolerance metrique : un
    jour de 2 m se rattrape aussi bien qu'un jour de 5 cm.
    """
    trame = deduire_trame(_pavage_2x2(largeur_sw=5.0 - jour), _ctx())
    assert trame.lignes_x == (0.0, 5.0, 12.0)


def test_une_cloison_etroite_n_est_pas_ecrasee() -> None:
    """Le refus d'ecraser une piece borne la consolidation."""
    plan = Plan(
        pieces=(
            Piece("couloir", "couloir", 0.0, 0.0, 0.4, 9.0),
            Piece("sejour", "sejour", 0.4, 0.0, 11.6, 9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=_RECT,
    )
    assert deduire_trame(plan, _ctx()).lignes_x == (0.0, 0.4, 12.0)


def _trois_pieces_sur_quatre() -> Plan:
    """Pavage 2x2 ampute de sa piece nord-est : une cellule reste vide."""
    return Plan(
        pieces=(
            Piece("sw", "sejour", 0.0, 0.0, 5.0, 4.0),
            Piece("se", "chambre", 5.0, 0.0, 7.0, 4.0),
            Piece("nw", "cuisine", 0.0, 4.0, 5.0, 5.0),
        ),
        murs=(),
        ouvertures=(),
        contour=_RECT,
    )


def test_jour_structurel_est_detecte_sans_budget() -> None:
    """`budget_reparation=0` : la partition est verifiee, jamais retouchee."""
    with pytest.raises(InvariantViole, match="jour structurel"):
        deduire_trame(_trois_pieces_sur_quatre(), _ctx(), budget_reparation=0)


def test_une_piece_manquante_est_absorbee_par_sa_voisine() -> None:
    """Conséquence semantique a connaitre : le programme change.

    Avec le budget par defaut, la cellule vide est rendue a une piece voisine
    plutot que refusee. C'est le comportement attendu d'un legaliseur — fermer un
    jour, c'est agrandir quelqu'un — mais le plan sort avec **une piece de moins**
    que ce que le generateur avait prevu. Un appelant qui doit preserver le
    programme piece par piece passe `budget_reparation=0`.
    """
    plan = _trois_pieces_sur_quatre()
    trame = deduire_trame(plan, _ctx())
    aires = {inc[0]: (inc[2] - inc[1]) * (inc[4] - inc[3]) for inc in trame.incidences}
    assert sum(aires.values()) == trame.n_cellules  # la grille est entierement couverte
    assert len(trame.incidences) == 3

    corrige = ax.legalize(plan, _ctx(), pavage=True)
    assert corrige.certificat is not None
    assert corrige.certificat.geometrie.valide
    assert len(corrige.pieces) == 3


def test_le_budget_borne_la_reparation() -> None:
    """Au-dela du budget, la faute n'est plus une cote fausse : on refuse."""
    plan = Plan(
        pieces=(
            Piece("a", "sejour", 0.0, 0.0, 2.0, 3.0),
            Piece("b", "chambre", 4.0, 6.0, 2.0, 3.0),
        ),
        murs=(),
        ouvertures=(),
        contour=_RECT,
    )
    with pytest.raises(InvariantViole, match="structurel"):
        deduire_trame(plan, _ctx(), budget_reparation=1)


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
        trame = deduire_trame(plan, _ctx(), budget_reparation=budget)
    except InvariantViole:
        return  # refus explicite : c'est l'autre branche du contrat
    grille = np.zeros((len(trame.lignes_x) - 1, len(trame.lignes_y) - 1), dtype=int)
    for nom, gauche, droite, bas, haut in trame.incidences:
        assert gauche < droite, f"{nom} a ses bords inverses en x"
        assert bas < haut, f"{nom} a ses bords inverses en y"
        grille[gauche:droite, bas:haut] += 1
    assert np.all(grille == 1), "la trame rendue n'est pas une partition"


def test_la_reparation_ne_change_pas_un_plan_sain() -> None:
    """Sur une partition deja exacte, aucune retouche n'est appliquee."""
    sain = deduire_trame(_pavage_2x2(), _ctx(), budget_reparation=0)
    avec = deduire_trame(_pavage_2x2(), _ctx(), budget_reparation=8)
    assert sain == avec


def test_chevauchement_simple_est_resorbe_par_le_support() -> None:
    """Deux bords orphelins qui se chevauchent fusionnent sur une ligne commune.

    C'est le comportement voulu : un chevauchement de 2 m entre deux pieces
    voisines est une intention d'adjacence mal cotee, pas une incoherence d'ordre.
    """
    plan = Plan(
        pieces=(
            Piece("a", "sejour", 0.0, 0.0, 7.0, 9.0),
            Piece("b", "chambre", 5.0, 0.0, 7.0, 9.0),
        ),
        murs=(),
        ouvertures=(),
        contour=_RECT,
    )
    trame = deduire_trame(plan, _ctx())
    assert len(trame.lignes_x) == 3
    gauches = {inc[0]: inc[1:3] for inc in trame.incidences}
    assert gauches["a"][1] == gauches["b"][0]  # a se termine ou b commence


def test_chevauchement_structurel_est_refuse() -> None:
    """Une piece **contenue** dans une autre : aucune fusion de lignes ne la sauve."""
    plan = Plan(
        pieces=(
            Piece("englobante", "sejour", 0.0, 0.0, 12.0, 9.0),
            Piece("incluse", "chambre", 0.0, 0.0, 5.0, 4.0),
        ),
        murs=(),
        ouvertures=(),
        contour=_RECT,
    )
    with pytest.raises(InvariantViole, match="chevauchement structurel"):
        deduire_trame(plan, _ctx())


def test_legalize_avec_pavage_ferme_un_jour() -> None:
    """Le cas que `legalize` seul ne sait pas corriger.

    Sans `pavage=True`, le plan troue est deja le plus proche de lui-meme :
    l'optimum L1 le laisse tel quel et la verification exacte le rejette.
    """
    abime = _pavage_2x2(largeur_sw=4.5)
    ctx = _ctx()
    assert not verifier_exactement(abime, ctx).valide

    with pytest.raises(ax.InvariantViole, match="jours"):
        ax.legalize(abime, ctx)

    corrige = ax.legalize(abime, ctx, pavage=True)
    assert corrige.certificat is not None
    assert corrige.certificat.geometrie.valide
    assert not corrige.certificat.geometrie.jours


def test_pavage_preserve_l_idempotence() -> None:
    """Sur un plan deja valide, `pavage=True` ne deplace rien."""
    ctx = _ctx()
    corrige = ax.legalize(_pavage_2x2(), ctx, pavage=True)
    assert corrige.certificat is not None
    assert corrige.certificat.geometrie.deplacement_max == pytest.approx(0.0, abs=1e-9)


def test_pavage_est_invariant_par_translation_des_lignes() -> None:
    """La these du module : la condition ne porte que sur les incidences.

    Deux plans de meme structure combinatoire mais de coordonnees differentes ont
    la meme trame en indices, et les deux sont des pavages valides.
    """
    ctx = _ctx()
    a = deduire_trame(_pavage_2x2(), ctx)
    decale = Plan(
        pieces=(
            Piece("sw", "sejour", 0.0, 0.0, 3.0, 6.0),
            Piece("se", "chambre", 3.0, 0.0, 9.0, 6.0),
            Piece("nw", "cuisine", 0.0, 6.0, 3.0, 3.0),
            Piece("ne", "sdb", 3.0, 6.0, 9.0, 3.0),
        ),
        murs=(),
        ouvertures=(),
        contour=_RECT,
    )
    b = deduire_trame(decale, ctx)
    assert [inc[1:] for inc in a.incidences] == [inc[1:] for inc in b.incidences]
    assert a.lignes_x != b.lignes_x
    assert verifier_exactement(decale, ctx).valide


def test_egalites_de_pavage_ne_polluent_pas_le_diagnostic_dual() -> None:
    """Les contraintes de pavage sont des egalites : elles ne sont pas dualisees."""
    ctx = _ctx()
    sans = ax.legalize(_pavage_2x2(), ctx)
    avec = ax.legalize(_pavage_2x2(), ctx, pavage=True)
    assert sans.certificat is not None
    assert avec.certificat is not None
    libelles = {libelle for libelle, _ in avec.certificat.duaux}
    assert not any(nom.startswith(("trame ", "contour ")) for nom in libelles)


def test_plan_sans_piece_est_refuse() -> None:
    """Erreur typee, jamais un IndexError nu."""
    vide = Plan(pieces=(), murs=(), ouvertures=(), contour=_RECT)
    with pytest.raises(InvariantViole, match="sans piece"):
        deduire_trame(vide, _ctx())


def test_trame_est_deterministe() -> None:
    """Deux appels sur le meme plan rendent exactement la meme trame."""
    plan = _pavage_2x2(largeur_sw=4.7)
    a = deduire_trame(plan, _ctx())
    b = deduire_trame(plan, _ctx())
    assert a == b
    assert np.allclose(a.lignes_x, b.lignes_x)
