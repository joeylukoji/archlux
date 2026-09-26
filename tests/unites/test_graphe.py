"""Graphe de contraintes de séparation — cas déterministes.

`MILESTONE-2.md` §2. La règle fondatrice : pour chaque paire de pièces, **au moins une**
séparation doit exister. Sans elle, le chevauchement reste possible et aucun ajout de
contrainte ultérieur ne le rattrape.
"""

from __future__ import annotations

import pytest

from archlux.errors import InconsistentOrder, MissingSeparation
from archlux.geom.graphe import (
    RelativeOrder,
    build_graph,
    deduce_order,
    transitive_reduction,
)
from archlux.types import Plan, Room


def _plan(*pieces: Room) -> Plan:
    return Plan(rooms=pieces, walls=(), openings=(), outline=())


def _carre(nom: str, x: float, y: float, cote: float = 1.0) -> Room:
    return Room(id=nom, type="living_room", x=x, y=y, w=cote, h=cote)


class TestConstruireGraphe:
    """Assemblage et validation de l'ordre."""

    def test_separation_simple(self) -> None:
        """Une arête horizontale déclarée se retrouve dans le graphe horizontal."""
        ordre = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B"))
        graphe = build_graph(ordre, ["A", "B"])
        assert ("A", "B") in graphe.horizontal.edges

    def test_cycle_detecte(self) -> None:
        """« A à gauche de B à gauche de A » n'a pas de solution géométrique."""
        ordre = RelativeOrder(horizontal=(("A", "B"), ("B", "A")), vertical=(), rooms=("A", "B"))
        with pytest.raises(InconsistentOrder) as capture:
            build_graph(ordre, ["A", "B"])
        assert capture.value.axis == "horizontal"
        assert set(capture.value.cycle) == {"A", "B"}

    def test_cycle_vertical_detecte(self) -> None:
        """Le même défaut sur l'axe vertical est rapporté avec le bon axe."""
        ordre = RelativeOrder(horizontal=(), vertical=(("A", "B"), ("B", "A")), rooms=("A", "B"))
        with pytest.raises(InconsistentOrder) as capture:
            build_graph(ordre, ["A", "B"])
        assert capture.value.axis == "vertical"

    def test_paire_non_separee_refusee(self) -> None:
        """Deux pièces sans séparation peuvent se chevaucher : c'est une erreur d'entrée."""
        ordre = RelativeOrder(horizontal=(("A", "B"),), vertical=(), rooms=("A", "B", "C"))
        with pytest.raises(MissingSeparation) as capture:
            build_graph(ordre, ["A", "B", "C"])
        assert "C" in capture.value.pair

    def test_une_piece_inconnue_est_refusee(self) -> None:
        """Une arête vers une pièce absente de l'ensemble déclaré est incohérente."""
        ordre = RelativeOrder(horizontal=(("A", "Z"),), vertical=(), rooms=("A", "B"))
        with pytest.raises(InconsistentOrder):
            build_graph(ordre, ["A", "B"])


class TestDeduireOrdre:
    """Extraction de l'ordre relatif depuis un plan proposé."""

    def test_deux_pieces_cote_a_cote(self) -> None:
        """Centres écartés en x : la séparation est horizontale."""
        ordre = deduce_order(_plan(_carre("A", 0.0, 0.0), _carre("B", 5.0, 0.0)))
        assert ordre.horizontal == (("A", "B"),)
        assert ordre.vertical == ()

    def test_deux_pieces_superposees(self) -> None:
        """Centres écartés en y : la séparation est verticale."""
        ordre = deduce_order(_plan(_carre("A", 0.0, 0.0), _carre("B", 0.0, 5.0)))
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
        ordre = deduce_order(
            _plan(
                Room(id="A", type="living_room", x=0.0, y=0.0, w=1.0, h=1.0),
                Room(id="B", type="living_room", x=1.0, y=0.0, w=1.0, h=9.0),
            )
        )
        assert ordre.horizontal == (("A", "B"),)
        assert ordre.vertical == ()

    def test_l_axe_dominant_tranche_les_chevauchements(self) -> None:
        """Quand les pièces se recouvrent sur les deux axes, l'écart des centres décide.

        C'est le seul cas où l'heuristique s'applique — et c'est précisément le défaut
        que ``legalize`` existe pour corriger.
        """
        ordre = deduce_order(
            _plan(
                Room(id="A", type="living_room", x=0.0, y=0.0, w=4.0, h=4.0),
                Room(id="B", type="living_room", x=1.0, y=3.0, w=4.0, h=4.0),
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
        gauche = Room(id="A", type="living_room", x=1.0, y=0.0, w=3.47, h=9.0)
        droite = Room(id="B", type="living_room", x=4.47, y=0.0, w=1.0, h=1.0)
        assert gauche.x + gauche.w != droite.x  # le piège, en une ligne
        ordre = deduce_order(_plan(gauche, droite))
        assert ordre.horizontal == (("A", "B"),)

    def test_est_deterministe(self) -> None:
        """Deux lectures du même plan donnent le même ordre, aux mêmes indices.

        Un ordre non déterministe produirait des polytopes dont les lignes changent
        d'une exécution à l'autre, donc des prix duaux incomparables.
        """
        plan = _plan(_carre("c", 4.0, 0.0), _carre("a", 0.0, 0.0), _carre("b", 2.0, 3.0))
        assert deduce_order(plan) == deduce_order(plan)

    def test_l_ordre_deduit_est_accepte(self) -> None:
        """Un ordre déduit d'un plan réel passe la validation sans exception.

        C'est le contrat d'assemblage entre les deux fonctions : sans lui, chacune peut
        être correcte isolément et la chaîne rester inutilisable.
        """
        plan = _plan(
            _carre("living_room", 0.0, 0.0, 4.0),
            _carre("kitchen", 5.0, 0.0, 3.0),
            _carre("bathroom", 0.0, 5.0, 2.0),
        )
        graphe = build_graph(deduce_order(plan), list(plan.room_ids))
        assert graphe.has_separation("living_room", "kitchen")
        assert graphe.has_separation("living_room", "bathroom")


class TestReductionTransitive:
    """Retrait des arêtes impliquées par transitivité."""

    def test_retire_l_arete_redondante(self) -> None:
        """``A→B→C`` rend ``A→C`` superflue.

        Le gain n'est pas cosmétique : 15 pièces passent de ~210 contraintes à ~30, et
        le solveur est appelé 50 fois par légalisation performantielle.
        """
        ordre = RelativeOrder(
            horizontal=(("A", "B"), ("B", "C"), ("A", "C")),
            vertical=(),
            rooms=("A", "B", "C"),
        )
        reduit = transitive_reduction(build_graph(ordre, ["A", "B", "C"]))
        assert ("A", "C") not in reduit.horizontal.edges
        assert ("A", "B") in reduit.horizontal.edges
        assert ("B", "C") in reduit.horizontal.edges

    def test_conserve_toutes_les_pieces(self) -> None:
        """Réduire les arêtes ne doit jamais faire disparaître une pièce."""
        ordre = RelativeOrder(
            horizontal=(("A", "B"), ("B", "C"), ("A", "C")),
            vertical=(),
            rooms=("A", "B", "C"),
        )
        reduit = transitive_reduction(build_graph(ordre, ["A", "B", "C"]))
        assert set(reduit.horizontal.nodes) == {"A", "B", "C"}
