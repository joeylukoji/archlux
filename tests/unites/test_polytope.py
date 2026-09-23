"""Assemblage du polytope — `MILESTONE-2.md` §3, cas déterministes.

Les lignes attendues sont écrites à la main : `x_A + w_A − x_B ≤ 0` pour « A à gauche de
B ». Comparer à un calcul refait comme le code serait tautologique.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from scipy import sparse

from archlux.erreurs import InvariantViole
from archlux.geom.graphe import OrdreRelatif
from archlux.geom.polytope import (
    construire_polytope,
    devectoriser,
    figer_contacts,
    vectoriser,
)
from archlux.types import (
    Contexte,
    Orientation,
    Piece,
    Plan,
    Referentiel,
    Structure,
)

CTX = Contexte(
    structure=Structure(murs_porteurs=()),
    orientation=Orientation(deg=0.0),
    contour=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    referentiel=Referentiel(aires_min=(("sdb", 5.0),), largeur_min=1.5),
)

ORDRE_AB = OrdreRelatif(horizontal=(("A", "B"),), vertical=(), pieces=("A", "B"))

PLAN_AB = Plan(
    pieces=(
        Piece(id="A", type="sejour", x=0.0, y=0.0, w=4.0, h=8.0),
        Piece(id="B", type="sdb", x=4.0, y=0.0, w=6.0, h=8.0),
    ),
    murs=(),
    ouvertures=(),
    contour=CTX.contour,
)


class TestVariables:
    """Quatre variables par pièce, indexées de façon déterministe."""

    def test_quatre_variables_par_piece(self) -> None:
        """``x``, ``y``, ``w``, ``h`` — et rien d'autre."""
        poly = construire_polytope(ORDRE_AB, CTX)
        assert len(poly.index) == 8
        assert set(poly.index) == {
            f"{piece}.{champ}" for piece in ("A", "B") for champ in ("x", "y", "w", "h")
        }

    def test_les_colonnes_sont_contigues(self) -> None:
        """Les indices couvrent ``0..4n-1`` sans trou : c'est ce que suppose ``lmo``."""
        poly = construire_polytope(ORDRE_AB, CTX)
        assert sorted(poly.index.values()) == list(range(8))


class TestContraintes:
    """Le contenu des lignes, pas seulement leur nombre."""

    def test_ligne_de_separation_horizontale(self) -> None:
        """« A à gauche de B » s'écrit ``x_A + w_A − x_B ≤ 0``."""
        poly = construire_polytope(ORDRE_AB, CTX)
        ligne = next(
            i for i, o in enumerate(poly.origines) if o.startswith("separation horizontale")
        )
        attendu = np.zeros(8)
        attendu[poly.index["A.x"]] = 1.0
        attendu[poly.index["A.w"]] = 1.0
        attendu[poly.index["B.x"]] = -1.0
        assert np.allclose(poly.A.toarray()[ligne], attendu)
        assert poly.b[ligne] == 0.0

    def test_ligne_de_contour(self) -> None:
        """``x_i + w_i ≤ W`` borne la pièce dans l'enveloppe."""
        poly = construire_polytope(ORDRE_AB, CTX)
        ligne = poly.origines.index("contour droit A")
        attendu = np.zeros(8)
        attendu[poly.index["A.x"]] = 1.0
        attendu[poly.index["A.w"]] = 1.0
        assert np.allclose(poly.A.toarray()[ligne], attendu)
        assert poly.b[ligne] == pytest.approx(10.0)

    def test_les_largeurs_minimales_sont_dans_les_bornes(self) -> None:
        """`MILESTONE-2.md` §3 : ``w_i ≥ ℓ_min`` passe par ``bornes``, pas par ``A``."""
        poly = construire_polytope(ORDRE_AB, CTX)
        assert poly.bornes[poly.index["A.w"]] == (1.5, 10.0)
        assert poly.bornes[poly.index["A.h"]] == (1.5, 8.0)
        assert poly.bornes[poly.index["A.x"]] == (0.0, 10.0)

    def test_aucune_contrainte_de_surface(self) -> None:
        """``w·h ≥ a`` est non linéaire : reporté aux coupes de l'étape 4."""
        poly = construire_polytope(ORDRE_AB, CTX)
        assert not any("surface" in o for o in poly.origines)


class TestOrigines:
    """`origines` est obligatoire dès la première version."""

    def test_une_origine_par_ligne(self) -> None:
        """Sans cette correspondance, un prix dual est « le nombre de la ligne 47 »."""
        poly = construire_polytope(ORDRE_AB, CTX)
        assert poly.A.shape[0] == len(poly.origines)

    def test_les_origines_sont_lisibles(self) -> None:
        """Un libellé doit se lire en revue de projet, pas seulement en débogage."""
        poly = construire_polytope(ORDRE_AB, CTX)
        assert all(isinstance(o, str) and len(o) > 3 for o in poly.origines)
        assert "separation horizontale A|B" in poly.origines


class TestContient:
    """Vérification d'appartenance, naïve et indépendante de tout solveur."""

    def test_un_plan_conforme_est_dedans(self) -> None:
        """Le plan de référence satisfait toutes les lignes."""
        poly = construire_polytope(ORDRE_AB, CTX)
        assert poly.contient(vectoriser(PLAN_AB, poly.index))

    def test_un_chevauchement_est_dehors(self) -> None:
        """Reculer B de deux mètres viole la séparation."""
        poly = construire_polytope(ORDRE_AB, CTX)
        point = vectoriser(PLAN_AB, poly.index)
        point[poly.index["B.x"]] = 2.0
        assert not poly.contient(point)

    def test_un_debordement_du_contour_est_dehors(self) -> None:
        """Élargir B au-delà de l'enveloppe viole la ligne de contour."""
        poly = construire_polytope(ORDRE_AB, CTX)
        point = vectoriser(PLAN_AB, poly.index)
        point[poly.index["B.w"]] = 20.0
        assert not poly.contient(point)

    def test_une_piece_trop_etroite_est_dehors(self) -> None:
        """La largeur minimale est une borne, elle compte aussi."""
        poly = construire_polytope(ORDRE_AB, CTX)
        point = vectoriser(PLAN_AB, poly.index)
        point[poly.index["A.w"]] = 0.1
        assert not poly.contient(point)


class TestVectorisation:
    """Aller-retour entre plan et vecteur de décision."""

    def test_aller_retour(self) -> None:
        """``devectoriser(vectoriser(p))`` rend le plan d'origine."""
        poly = construire_polytope(ORDRE_AB, CTX)
        point = vectoriser(PLAN_AB, poly.index)
        assert devectoriser(point, PLAN_AB, poly.index) == PLAN_AB

    def test_les_ouvertures_suivent_sans_retouche(self) -> None:
        """**La raison d'être de l'invariant du §6.**

        Le vecteur ne porte que les pièces. Les baies étant relatives à leur mur, elles
        traversent la dévectorisation intactes — aucune resynchronisation à écrire.
        """
        poly = construire_polytope(ORDRE_AB, CTX)
        point = vectoriser(PLAN_AB, poly.index)
        point[poly.index["A.w"]] = 3.0
        resultat = devectoriser(point, PLAN_AB, poly.index)
        assert resultat.ouvertures == PLAN_AB.ouvertures
        assert resultat.murs == PLAN_AB.murs

    def test_une_piece_absente_est_signalee(self) -> None:
        """Vectoriser un plan qui n'a pas les pièces de l'ordre est un bogue interne."""
        poly = construire_polytope(ORDRE_AB, CTX)
        autre = Plan(
            pieces=(Piece(id="Z", type="sejour", x=0.0, y=0.0, w=1.0, h=1.0),),
            murs=(),
            ouvertures=(),
            contour=CTX.contour,
        )
        with pytest.raises(InvariantViole):
            vectoriser(autre, poly.index)


class TestStructurePorteuse:
    """État actuel de `A_eq` — voir ADR-7."""

    def test_a_eq_est_vide_mais_bien_dimensionnee(self) -> None:
        """Aucun mur porteur n'est encore lié à une pièce, mais la forme est correcte.

        ``construire_polytope(ordre, ctx)`` ne reçoit pas le plan proposé : l'incidence
        pièce ↔ mur porteur n'est pas calculable depuis cette signature. La structure est
        donc vérifiée en aval par ``certify.preuve``, jamais silencieusement ignorée.
        """
        poly = construire_polytope(ORDRE_AB, CTX)
        assert poly.A_eq.shape == (0, len(poly.index))
        assert poly.b_eq.shape == (0,)


class TestRefus:
    """Aucune dimension incohérente ne passe en silence."""

    def test_contient_refuse_une_dimension_incoherente(self) -> None:
        """Un vecteur de mauvaise taille est un bogue d'appariement, pas un point hors domaine."""
        poly = construire_polytope(ORDRE_AB, CTX)
        with pytest.raises(InvariantViole, match="dimension"):
            poly.contient(np.zeros(3))

    def test_devectoriser_refuse_une_dimension_incoherente(self) -> None:
        """Même règle en sortie de solveur."""
        poly = construire_polytope(ORDRE_AB, CTX)
        with pytest.raises(InvariantViole, match="dimension"):
            devectoriser(np.zeros(3), PLAN_AB, poly.index)

    def test_devectoriser_refuse_une_piece_hors_polytope(self) -> None:
        """Laisser une pièce non mise à jour produirait un plan faux.

        Le défaut serait attrapé plus loin par ``certify``, mais avec un diagnostic sans
        rapport avec sa cause — le pire des deux mondes.
        """
        poly = construire_polytope(ORDRE_AB, CTX)
        etranger = Plan(
            pieces=(*PLAN_AB.pieces, Piece(id="Z", type="wc", x=0.0, y=0.0, w=1.0, h=1.0)),
            murs=(),
            ouvertures=(),
            contour=CTX.contour,
        )
        with pytest.raises(InvariantViole, match="Z"):
            devectoriser(vectoriser(PLAN_AB, poly.index), etranger, poly.index)

    def test_contient_verifie_aussi_les_egalites(self) -> None:
        """``A_eq`` est vide aujourd'hui, mais ``contient`` doit savoir la traiter.

        Le jour où ADR-7 sera tranchée, cette branche portera la structure porteuse ;
        la laisser non testée jusque-là reviendrait à la découvrir en production.
        """
        poly = construire_polytope(ORDRE_AB, CTX)
        ligne = sparse.csr_matrix(
            ([1.0], ([0], [poly.index["A.x"]])), shape=(1, len(poly.index))
        )
        point = vectoriser(PLAN_AB, poly.index)  # A.x vaut 0

        # Deux variantes du même polytope : seul le second membre change, de sorte que
        # les deux branches soient comparables toutes choses égales par ailleurs.
        assert replace(poly, A_eq=ligne, b_eq=np.array([0.0])).contient(point)
        assert not replace(poly, A_eq=ligne, b_eq=np.array([3.0])).contient(point)

    def test_un_contour_plat_est_refuse(self) -> None:
        """Un contour d'aire nulle donnerait des bornes vides sans le dire."""
        ctx = Contexte(
            structure=Structure(murs_porteurs=()),
            orientation=Orientation(deg=0.0),
            contour=((0.0, 0.0), (10.0, 0.0), (10.0, 0.0)),
            referentiel=Referentiel(aires_min=()),
        )
        with pytest.raises(InvariantViole, match="dégénéré"):
            construire_polytope(ORDRE_AB, ctx)


def test_un_contour_degenere_est_refuse() -> None:
    """Un contour vide n'a pas d'enveloppe : le dire plutôt que produire des bornes nulles."""
    ctx = Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=0.0),
        contour=(),
        referentiel=Referentiel(aires_min=()),
    )
    with pytest.raises(InvariantViole):
        construire_polytope(ORDRE_AB, ctx)


def test_figer_contacts_interdit_un_jour() -> None:
    """Un pavage saturé, figé, n'admet plus d'écartement des pièces."""
    from archlux.geom.graphe import deduire_ordre

    poly = construire_polytope(deduire_ordre(PLAN_AB), CTX)
    x = vectoriser(PLAN_AB, poly.index)
    serre = figer_contacts(poly, x)
    assert serre.A_eq.shape[0] > poly.A_eq.shape[0]
    assert serre.contient(x)
    ecarte = x.copy()
    ecarte[poly.index["B.x"]] += 0.5
    ecarte[poly.index["B.w"]] -= 0.5
    assert poly.contient(ecarte)
    assert not serre.contient(ecarte)
    jour_gauche = x.copy()
    jour_gauche[poly.index["A.x"]] += 0.2
    jour_gauche[poly.index["A.w"]] -= 0.2
    assert poly.contient(jour_gauche)
    assert not serre.contient(jour_gauche)
