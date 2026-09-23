"""Propriétés dérivées du modèle et frontières d'erreur.

Complète les tranches du jalon 1 : ces membres publics étaient implémentés mais jamais
exécutés par un test, ce que la mesure de couverture a révélé.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archlux.erreurs import (
    Infaisable,
    InvariantViole,
    OrdreIncoherent,
    SeparationManquante,
)
from archlux.types import Certificat, Mur, Ouverture, Piece, Plan, PreuveGeometrique

SEJOUR = Piece(id="sejour", type="sejour", x=1.0, y=2.0, w=4.0, h=3.0)


class TestPiece:
    """Grandeurs dérivées d'une pièce."""

    def test_aire(self) -> None:
        """4 m x 3 m = 12 m²."""
        assert SEJOUR.aire == 12.0

    def test_centre(self) -> None:
        """Coin bas-gauche en (1, 2), donc centre en (3, 3,5)."""
        assert SEJOUR.centre == (3.0, 3.5)


class TestPlan:
    """Déterminisme du modèle."""

    def test_les_ids_sont_tries(self) -> None:
        """L'ordre d'itération est explicite, jamais celui d'un ``set``.

        Un ordre non déterministe produit des polytopes dont les lignes changent d'une
        exécution à l'autre, donc des prix duaux impossibles à comparer.
        """
        plan = Plan(
            pieces=(
                Piece(id="wc", type="wc", x=0.0, y=0.0, w=1.0, h=1.0),
                Piece(id="cuisine", type="cuisine", x=0.0, y=0.0, w=1.0, h=1.0),
                Piece(id="bain", type="sdb", x=0.0, y=0.0, w=1.0, h=1.0),
            ),
            murs=(),
            ouvertures=(),
            contour=(),
        )
        assert plan.ids_pieces == ("bain", "cuisine", "wc")


class TestOuvertureDegeneree:
    """Cas limites de la dérivation d'une baie."""

    def test_un_mur_de_longueur_nulle_est_refuse(self) -> None:
        """Une direction indéfinie doit lever, jamais rendre des ``NaN`` silencieux."""
        mur = Mur(id="m", a=(2.0, 2.0), b=(2.0, 2.0))
        baie = Ouverture(id="f", mur_id="m", s=0.5, largeur_rel=0.5)
        with pytest.raises(InvariantViole, match="longueur nulle"):
            baie.segment_absolu(mur)


class TestCertificat:
    """Le certificat délègue son rendu, il ne le réimplémente pas."""

    def test_rapport_delegue_a_certify(self) -> None:
        """La délégation produit le gabarit à deux natures, sans score composite."""
        certificat = Certificat(
            geometrie=PreuveGeometrique(
                valide=True,
                chevauchement=False,
                jours=False,
                surfaces_ok=True,
                structure_preservee=True,
                deplacement_max=0.0,
            )
        )
        texte = certificat.rapport()
        assert "[EXACT]" in texte
        assert "[PREDICTION" in texte
        assert "NON EVALUABLE" in texte


class TestExceptions:
    """Les exceptions publiques portent leur diagnostic, pas seulement un message."""

    def test_ordre_incoherent_expose_le_cycle(self) -> None:
        """Le cycle est exploitable par l'appelant, pas seulement lisible."""
        erreur = OrdreIncoherent(cycle=("a", "b", "a"), axe="horizontal")
        assert erreur.cycle == ("a", "b", "a")
        assert "a -> b -> a" in str(erreur)

    def test_separation_manquante_expose_la_paire(self) -> None:
        """La paire non séparée est celle qu'il faut corriger."""
        erreur = SeparationManquante(paire=("cuisine", "sdb"))
        assert erreur.paire == ("cuisine", "sdb")

    def test_infaisable_porte_sa_preuve(self) -> None:
        """Une infaisabilité sans certificat n'apprend rien à personne."""
        erreur = Infaisable(certificat_farkas=[1.0, 0.0], origines=("mur porteur axe 3",))
        assert erreur.certificat_farkas == [1.0, 0.0]
        assert "mur porteur axe 3" in str(erreur)

    def test_infaisable_sans_origines_le_dit(self) -> None:
        """Le message ne prétend pas à un diagnostic qu'il n'a pas."""
        assert "origines non renseignees" in str(Infaisable(certificat_farkas=None))


class TestEcritureRobuste:
    """Frontière d'écriture : aucune exception non typée n'en sort."""

    def test_un_nan_leve_une_exception_typee(self, tmp_path: Path) -> None:
        """``NaN`` est exactement ce qu'un solveur bogué produit.

        Le laisser remonter en ``ValueError`` brut violerait `ARCHITECTURE.md` §7 et
        ferait sortir du domaine d'erreurs du projet une faute pourtant interne.
        """
        plan = Plan(
            pieces=(Piece(id="a", type="sejour", x=float("nan"), y=0.0, w=1.0, h=1.0),),
            murs=(),
            ouvertures=(),
            contour=(),
        )
        with pytest.raises(InvariantViole, match="non finie"):
            plan.to_json(tmp_path / "x.json")
