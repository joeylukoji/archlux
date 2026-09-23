"""Graphe de contraintes de séparation — cas déterministes.

`MILESTONE-2.md` §2. La règle fondatrice : pour chaque paire de pièces, **au moins une**
séparation doit exister. Sans elle, le chevauchement reste possible et aucun ajout de
contrainte ultérieur ne le rattrape.
"""

from __future__ import annotations

import pytest

from archlux.erreurs import OrdreIncoherent, SeparationManquante
from archlux.geom.graphe import (
    OrdreRelatif,
    construire_graphe,
    deduire_ordre,
    reduction_transitive,
)
from archlux.types import Piece, Plan


def _plan(*pieces: Piece) -> Plan:
    return Plan(pieces=pieces, murs=(), ouvertures=(), contour=())


def _carre(nom: str, x: float, y: float, cote: float = 1.0) -> Piece:
    return Piece(id=nom, type="sejour", x=x, y=y, w=cote, h=cote)


class TestConstruireGraphe:
    """Assemblage et validation de l'ordre."""

    def test_separation_simple(self) -> None:
        """Une arête horizontale déclarée se retrouve dans le graphe horizontal."""
        ordre = OrdreRelatif(horizontal=(("A", "B"),), vertical=(), pieces=("A", "B"))
        graphe = construire_graphe(ordre, ["A", "B"])
        assert ("A", "B") in graphe.horizontal.edges

    def test_cycle_detecte(self) -> None:
        """« A à gauche de B à gauche de A » n'a pas de solution géométrique."""
        ordre = OrdreRelatif(horizontal=(("A", "B"), ("B", "A")), vertical=(), pieces=("A", "B"))
        with pytest.raises(OrdreIncoherent) as capture:
            construire_graphe(ordre, ["A", "B"])
        assert capture.value.axe == "horizontal"
        assert set(capture.value.cycle) == {"A", "B"}

    def test_cycle_vertical_detecte(self) -> None:
        """Le même défaut sur l'axe vertical est rapporté avec le bon axe."""
        ordre = OrdreRelatif(horizontal=(), vertical=(("A", "B"), ("B", "A")), pieces=("A", "B"))
        with pytest.raises(OrdreIncoherent) as capture:
            construire_graphe(ordre, ["A", "B"])
        assert capture.value.axe == "vertical"

    def test_paire_non_separee_refusee(self) -> None:
        """Deux pièces sans séparation peuvent se chevaucher : c'est une erreur d'entrée."""
        ordre = OrdreRelatif(horizontal=(("A", "B"),), vertical=(), pieces=("A", "B", "C"))
        with pytest.raises(SeparationManquante) as capture:
            construire_graphe(ordre, ["A", "B", "C"])
        assert "C" in capture.value.paire

    def test_une_piece_inconnue_est_refusee(self) -> None:
        """Une arête vers une pièce absente de l'ensemble déclaré est incohérente."""
        ordre = OrdreRelatif(horizontal=(("A", "Z"),), vertical=(), pieces=("A", "B"))
        with pytest.raises(OrdreIncoherent):
            construire_graphe(ordre, ["A", "B"])


class TestDeduireOrdre:
    """Extraction de l'ordre relatif depuis un plan proposé."""

    def test_deux_pieces_cote_a_cote(self) -> None:
        """Centres écartés en x : la séparation est horizontale."""
        ordre = deduire_ordre(_plan(_carre("A", 0.0, 0.0), _carre("B", 5.0, 0.0)))
        assert ordre.horizontal == (("A", "B"),)
        assert ordre.vertical == ()

    def test_deux_pieces_superposees(self) -> None:
        """Centres écartés en y : la séparation est verticale."""
        ordre = deduire_ordre(_plan(_carre("A", 0.0, 0.0), _carre("B", 0.0, 5.0)))
        assert ordre.vertical == (("A", "B"),)
        assert ordre.horizontal == ()

    def test_l_axe_reellement_separateur_l_emporte(self) -> None:
        """**Régression.** Disjointes en x, recouvrantes en y : la séparation est en x.

        Contre-exemple trouvé par le test de propriété du polytope. ``A`` occupe
        ``y ∈ [0, 1]`` et ``B`` ``y ∈ [0, 9]`` : elles se recouvrent verticalement. Mais
        l'écart de leurs centres est plus grand en y, si bien qu'une règle fondée sur
        l'axe dominant produisait ``y_A + h_A ≤ y_B``, soit ``1 ≤ 0`` — une contrainte
        que le plan d'origine, pourtant valide, violait.
        """
        ordre = deduire_ordre(
            _plan(
                Piece(id="A", type="sejour", x=0.0, y=0.0, w=1.0, h=1.0),
                Piece(id="B", type="sejour", x=1.0, y=0.0, w=1.0, h=9.0),
            )
        )
        assert ordre.horizontal == (("A", "B"),)
        assert ordre.vertical == ()

    def test_l_axe_dominant_tranche_les_chevauchements(self) -> None:
        """Quand les pièces se recouvrent sur les deux axes, l'écart des centres décide.

        C'est le seul cas où l'heuristique s'applique — et c'est précisément le défaut
        que ``legalize`` existe pour corriger.
        """
        ordre = deduire_ordre(
            _plan(
                Piece(id="A", type="sejour", x=0.0, y=0.0, w=4.0, h=4.0),
                Piece(id="B", type="sejour", x=1.0, y=3.0, w=4.0, h=4.0),
            )
        )
        assert ordre.vertical == (("A", "B"),)
        assert ordre.horizontal == ()

    def test_deux_pieces_jointives_restent_separees(self) -> None:
        """**Régression flottante.** ``1.0 + 3.47`` vaut ``4.470000000000001``.

        Deux pièces qui se touchent exactement se retrouvent recouvrantes de 1e-16 en
        binaire. Sans tolérance de contact, elles basculaient dans le cas dégradé et
        recevaient une contrainte verticale que le plan violait. Le cas survient dès
        qu'un mur sépare deux pièces adjacentes — c'est-à-dire partout.
        """
        gauche = Piece(id="A", type="sejour", x=1.0, y=0.0, w=3.47, h=9.0)
        droite = Piece(id="B", type="sejour", x=4.47, y=0.0, w=1.0, h=1.0)
        assert gauche.x + gauche.w != droite.x  # le piège, en une ligne
        ordre = deduire_ordre(_plan(gauche, droite))
        assert ordre.horizontal == (("A", "B"),)

    def test_est_deterministe(self) -> None:
        """Deux lectures du même plan donnent le même ordre, aux mêmes indices.

        Un ordre non déterministe produirait des polytopes dont les lignes changent
        d'une exécution à l'autre, donc des prix duaux incomparables.
        """
        plan = _plan(_carre("c", 4.0, 0.0), _carre("a", 0.0, 0.0), _carre("b", 2.0, 3.0))
        assert deduire_ordre(plan) == deduire_ordre(plan)

    def test_l_ordre_deduit_est_accepte(self) -> None:
        """Un ordre déduit d'un plan réel passe la validation sans exception.

        C'est le contrat d'assemblage entre les deux fonctions : sans lui, chacune peut
        être correcte isolément et la chaîne rester inutilisable.
        """
        plan = _plan(
            _carre("sejour", 0.0, 0.0, 4.0),
            _carre("cuisine", 5.0, 0.0, 3.0),
            _carre("sdb", 0.0, 5.0, 2.0),
        )
        graphe = construire_graphe(deduire_ordre(plan), list(plan.ids_pieces))
        assert graphe.a_separation("sejour", "cuisine")
        assert graphe.a_separation("sejour", "sdb")


class TestReductionTransitive:
    """Retrait des arêtes impliquées par transitivité."""

    def test_retire_l_arete_redondante(self) -> None:
        """``A→B→C`` rend ``A→C`` superflue.

        Le gain n'est pas cosmétique : 15 pièces passent de ~210 contraintes à ~30, et
        le solveur est appelé 50 fois par légalisation performantielle.
        """
        ordre = OrdreRelatif(
            horizontal=(("A", "B"), ("B", "C"), ("A", "C")),
            vertical=(),
            pieces=("A", "B", "C"),
        )
        reduit = reduction_transitive(construire_graphe(ordre, ["A", "B", "C"]))
        assert ("A", "C") not in reduit.horizontal.edges
        assert ("A", "B") in reduit.horizontal.edges
        assert ("B", "C") in reduit.horizontal.edges

    def test_conserve_toutes_les_pieces(self) -> None:
        """Réduire les arêtes ne doit jamais faire disparaître une pièce."""
        ordre = OrdreRelatif(
            horizontal=(("A", "B"), ("B", "C"), ("A", "C")),
            vertical=(),
            pieces=("A", "B", "C"),
        )
        reduit = reduction_transitive(construire_graphe(ordre, ["A", "B", "C"]))
        assert set(reduit.horizontal.nodes) == {"A", "B", "C"}
