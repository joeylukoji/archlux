"""Chargeur de corpus reel (MSD) — `docs/donnees/msd.md`.

Le CSV de test est fabrique ici : le corpus reel fait 400 Mo et n'est pas
redistribuable. La geometrie reproduit ce qui compte dans MSD — repere tourne,
cloisons epaisses, pieces non jointives, pieces en L.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from shapely import affinity
from shapely.geometry import Polygon, box

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.data.chargeurs import (
    StatistiquesChargement,
    _recoller,
    _trame,
    charger_msd,
)
from archlux.types import Referentiel

_ANGLE = 23.0  # repere tourne, comme dans MSD


def _tourner(poly: Polygon) -> Polygon:
    return affinity.rotate(poly, _ANGLE, origin=(0.0, 0.0))


def _ecrire_csv(chemin: Path, lignes: list[tuple[str, str, str, Polygon]]) -> None:
    """Ecrire un CSV au format MSD (colonnes utiles seulement)."""
    entete = "apartment_id,entity_type,entity_subtype,geom\n"
    corps = "".join(
        f'{app},{genre},{sous_type},"{_tourner(poly).wkt}"\n'
        for app, genre, sous_type, poly in lignes
    )
    chemin.write_text(entete + corps, encoding="utf-8")


def _appartement_deux_pieces() -> list[tuple[str, str, str, Polygon]]:
    """Deux pieces separees par une cloison de 20 cm, plus un mur et une baie.

    Les `area` sont les surfaces **interieures** : elles ne se touchent pas, comme
    dans MSD. Le recollage doit les rendre jointives.
    """
    return [
        ("a1", "area", "LIVING_ROOM", box(0.0, 0.0, 3.9, 5.0)),
        ("a1", "area", "BEDROOM", box(4.1, 0.0, 8.0, 5.0)),
        ("a1", "separator", "WALL", box(3.9, 0.0, 4.1, 5.0)),
        ("a1", "opening", "WINDOW", box(1.0, -0.1, 2.2, 0.1)),
    ]


def test_trame_regroupe_les_coordonnees_voisines() -> None:
    """Deux bords distants de moins que la tolerance deviennent le meme bord."""
    correspondance = _trame([0.0, 0.05, 3.90, 4.10, 8.0], tolerance=0.30)
    assert correspondance[0.0] == correspondance[0.05]
    assert correspondance[3.90] == correspondance[4.10] == pytest.approx(4.0)
    assert correspondance[8.0] != correspondance[4.10]


def test_trame_est_transitive_le_long_d_une_enfilade() -> None:
    """Une chaine de pas courts fusionne, meme si les extremes sont eloignes."""
    correspondance = _trame([0.0, 0.2, 0.4, 0.6], tolerance=0.30)
    assert len(set(correspondance.values())) == 1


def test_recollage_rend_les_pieces_jointives() -> None:
    """Avant recollage l'union est trouee ; apres, elle est d'un seul tenant."""
    gauche = box(0.0, 0.0, 3.9, 5.0)
    droite = box(4.1, 0.0, 8.0, 5.0)
    assert gauche.distance(droite) == pytest.approx(0.2)
    recolles = _recoller([gauche, droite], tolerance=0.30)
    assert len(recolles) == 2
    assert recolles[0].distance(recolles[1]) == pytest.approx(0.0)


def test_charge_un_appartement_tourne_et_le_redresse(tmp_path: Path) -> None:
    """Le repere tourne est retrouve et devient l'`Orientation` du contexte."""
    csv = tmp_path / "msd.csv"
    _ecrire_csv(csv, _appartement_deux_pieces())
    apparts = list(charger_msd(csv))
    assert len(apparts) == 1
    appart = apparts[0]
    # L'angle est defini modulo 90 : 23 deg et 113 deg decrivent la meme trame.
    assert (
        min(
            abs(appart.angle_redressement - _ANGLE),
            abs(appart.angle_redressement - _ANGLE + 90.0),
        )
        < 0.5
    )
    assert appart.contexte.orientation.deg == appart.angle_redressement
    assert len(appart.plan.pieces) == 2
    # Les baies sont relatives a leur mur, jamais absolues.
    for ouverture in appart.plan.ouvertures:
        assert 0.0 <= ouverture.s <= 1.0
        assert 0.0 < ouverture.largeur_rel <= 1.0
        assert ouverture.mur_id in {mur.id for mur in appart.plan.murs}


def test_referentiel_par_defaut_neutralise_la_largeur_minimale(tmp_path: Path) -> None:
    """MSD ne porte aucune reglementation : `largeur_min` doit valoir 0.

    Le defaut de `Referentiel` (1,80 m) s'appliquerait a chaque **sous-rectangle**,
    y compris aux bandes etroites issues d'une decomposition en L. Le plan reel
    sortirait alors de son propre polytope.
    """
    csv = tmp_path / "msd.csv"
    _ecrire_csv(csv, _appartement_deux_pieces())
    appart = next(iter(charger_msd(csv)))
    assert appart.contexte.referentiel.largeur_min == 0.0
    assert appart.contexte.referentiel.aires_min == ()


def test_legalize_est_idempotent_sur_un_plan_reel_valide(tmp_path: Path) -> None:
    """Un plan deja valide ressort **inchange** : deplacement exactement nul.

    C'est le contrat de l'objectif L1 : si l'entree est admissible, l'optimum est
    `e = 0`. Mesure sur 80 appartements MSD : 80/80 valides avant et apres,
    deplacement maximal 0,0000 m.
    """
    csv = tmp_path / "msd.csv"
    _ecrire_csv(csv, _appartement_deux_pieces())
    appart = next(iter(charger_msd(csv)))
    assert verify_exactly(appart.plan, appart.contexte).valide

    corrige = ax.legalize(appart.plan, appart.contexte, fusions=appart.fusions)
    preuve = corrige.certificat.geometrie
    assert preuve.valide
    assert preuve.deplacement_max == pytest.approx(0.0, abs=1e-9)


def test_largeur_minimale_heritee_deforme_un_plan_reel(tmp_path: Path) -> None:
    """Contre-epreuve : avec le defaut 1,80 m, le plan sort de son polytope.

    Ce test **documente le piege** plutot qu'un comportement souhaitable : une
    piece de 3,9 m de large est elargie ou refusee des lors qu'un seuil
    reglementaire non voulu est herite en silence.
    """
    csv = tmp_path / "msd.csv"
    _ecrire_csv(csv, _appartement_deux_pieces())
    etroit = Referentiel(aires_min=(), largeur_min=6.0)  # plus large que les pieces
    appart = next(iter(charger_msd(csv, referentiel=etroit)))
    with pytest.raises(ax.ArchluxError):
        ax.legalize(appart.plan, appart.contexte, fusions=appart.fusions)


def test_statistiques_ventilent_les_rejets(tmp_path: Path) -> None:
    """Le taux de retention et ses motifs sont exposes, pas seulement le total."""
    oblique = Polygon([(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (2.0, 4.5), (0.0, 3.0)])
    csv = tmp_path / "msd.csv"
    _ecrire_csv(
        csv,
        [*_appartement_deux_pieces(), ("a2", "area", "ROOM", oblique)],
    )
    stats = StatistiquesChargement()
    retenus = list(charger_msd(csv, statistiques=stats))
    assert stats.lus == 2
    assert len(retenus) == stats.retenus
    assert 0.0 < stats.taux_retention <= 1.0
    assert sum(stats.rejets.values()) == stats.lus - stats.retenus
    assert "lus 2" in stats.resume()


def test_fichier_absent_leve_invariant(tmp_path: Path) -> None:
    """Un corpus introuvable est une erreur typee, pas un `FileNotFoundError` nu."""
    with pytest.raises(ax.InvariantViole, match="introuvable"):
        list(charger_msd(tmp_path / "absent.csv"))


def test_limite_arrete_le_chargement(tmp_path: Path) -> None:
    """`limite` plafonne le nombre d'appartements **retenus**."""
    lignes = []
    for k in range(4):
        for app, genre, sous_type, poly in _appartement_deux_pieces():
            decale = affinity.translate(poly, xoff=20.0 * k)
            lignes.append((f"{app}_{k}", genre, sous_type, decale))
    csv = tmp_path / "msd.csv"
    _ecrire_csv(csv, lignes)
    assert len(list(charger_msd(csv, limite=2))) == 2


def test_angle_de_redressement_est_coherent_avec_la_geometrie(tmp_path: Path) -> None:
    """Apres redressement, toutes les aretes des pieces sont axiales."""
    csv = tmp_path / "msd.csv"
    _ecrire_csv(csv, _appartement_deux_pieces())
    appart = next(iter(charger_msd(csv)))
    for piece in appart.plan.pieces:
        assert piece.w > 0.0
        assert piece.h > 0.0
    coords = list(appart.plan.contour)
    for (x0, y0), (x1, y1) in zip(coords, coords[1:] + coords[:1], strict=True):
        assert math.isclose(x0, x1, abs_tol=1e-6) or math.isclose(y0, y1, abs_tol=1e-6)
