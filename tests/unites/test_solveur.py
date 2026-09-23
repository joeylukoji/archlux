"""Oracle linéaire — `MILESTONE-2.md` §4.

Le module sous test **ne sait pas d'où vient ``c``**. Ces tests non plus : ils lui
passent des vecteurs de coûts arbitraires, jamais un « gradient de distance ».
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from scipy import sparse

from archlux.geom.graphe import OrdreRelatif
from archlux.geom.polytope import construire_polytope
from archlux.lmo.coupes import Coupe
from archlux.lmo.solveur import resoudre
from archlux.types import Contexte, Orientation, Referentiel, Structure

CTX = Contexte(
    structure=Structure(murs_porteurs=()),
    orientation=Orientation(deg=0.0),
    contour=((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)),
    referentiel=Referentiel(aires_min=(), largeur_min=1.5),
)

ORDRE_1 = OrdreRelatif(horizontal=(), vertical=(), pieces=("A",))
ORDRE_AB = OrdreRelatif(horizontal=(("A", "B"),), vertical=(), pieces=("A", "B"))

POLY_1 = construire_polytope(ORDRE_1, CTX)
POLY_AB = construire_polytope(ORDRE_AB, CTX)


class TestResolutionSimple:
    """Cas où l'optimum se lit à la main."""

    def test_lp_trivial(self) -> None:
        """Une seule pièce, minimiser ``x`` : la solution est la borne basse."""
        sol = resoudre(POLY_1, c=np.array([1.0, 0.0, 0.0, 0.0]))
        assert sol.statut == "optimal"
        assert sol.x[POLY_1.index["A.x"]] == pytest.approx(0.0)

    def test_maximiser_revient_a_minimiser_l_oppose(self) -> None:
        """``c = −e_x`` pousse ``x`` à sa borne haute, sans que le solveur sache pourquoi."""
        c = np.zeros(4)
        c[POLY_1.index["A.x"]] = -1.0
        sol = resoudre(POLY_1, c=c)
        # x + w <= 10 et w >= 1,5 : le maximum de x vaut 8,5.
        assert sol.x[POLY_1.index["A.x"]] == pytest.approx(8.5)

    def test_la_solution_est_dans_le_polytope(self) -> None:
        """Vérifié par ``Polytope.contient``, qui n'emprunte rien au solveur."""
        c = np.array([1.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, -1.0])
        sol = resoudre(POLY_AB, c=c)
        assert sol.statut == "optimal"
        assert POLY_AB.contient(sol.x, tol=1e-7)

    def test_les_diagnostics_sont_renseignes(self) -> None:
        """``temps_ms`` et ``iterations`` ne sont pas décoratifs : le §9 les mesure."""
        sol = resoudre(POLY_AB, c=np.zeros(8))
        assert sol.temps_ms > 0.0
        assert sol.iterations >= 0


class TestDuaux:
    """Les prix duaux ne sont extraits que si on les demande."""

    def test_absents_par_defaut(self) -> None:
        """Les extraire coûte ; ne pas les demander doit vouloir dire ne pas les payer."""
        assert resoudre(POLY_AB, c=np.zeros(8)).duaux is None

    def test_presents_sur_demande(self) -> None:
        """Un dual par ligne de ``A`` — l'appariement avec ``origines`` en dépend."""
        c = np.zeros(8)
        c[POLY_AB.index["A.w"]] = -1.0
        sol = resoudre(POLY_AB, c=c, duaux=True)
        assert sol.duaux is not None
        assert sol.duaux.shape == (POLY_AB.A.shape[0],)

    def test_une_contrainte_active_a_un_prix_non_nul(self) -> None:
        """Élargir ``A`` bute sur le contour : cette ligne-là doit coûter quelque chose."""
        c = np.zeros(8)
        c[POLY_AB.index["A.w"]] = -1.0
        sol = resoudre(POLY_AB, c=c, duaux=True)
        assert sol.duaux is not None
        actives = {POLY_AB.origines[i] for i, prix in enumerate(sol.duaux) if abs(prix) > 1e-9}
        assert actives, "aucune contrainte active alors que l'optimum est sur une face"


class TestInfaisable:
    """Une infaisabilité porte sa preuve, jamais un simple message."""

    @staticmethod
    def _polytope_surcontraint() -> object:
        """Deux pièces de 2 m minimum côte à côte dans un contour de 3 m."""
        ctx = Contexte(
            structure=Structure(murs_porteurs=()),
            orientation=Orientation(deg=0.0),
            contour=((0.0, 0.0), (3.0, 0.0), (3.0, 8.0), (0.0, 8.0)),
            referentiel=Referentiel(aires_min=(), largeur_min=2.0),
        )
        return construire_polytope(ORDRE_AB, ctx)

    def test_infaisable_produit_un_certificat(self) -> None:
        """Le programme ne tient pas dans l'enveloppe : il faut le prouver, pas l'affirmer."""
        poly = self._polytope_surcontraint()
        sol = resoudre(poly, c=np.zeros(8))  # type: ignore[arg-type]
        assert sol.statut == "infaisable"
        assert sol.certificat_farkas is not None
        assert sol.certificat_farkas.shape == (poly.A.shape[0],)  # type: ignore[attr-defined]

    def test_le_certificat_designe_des_contraintes_reelles(self) -> None:
        """Un certificat de Farkas non nul, sinon il n'explique rien."""
        poly = self._polytope_surcontraint()
        sol = resoudre(poly, c=np.zeros(8))  # type: ignore[arg-type]
        assert sol.certificat_farkas is not None
        assert np.any(np.abs(sol.certificat_farkas) > 1e-9)
        assert np.all(sol.certificat_farkas >= -1e-9), "les multiplicateurs sont positifs"


class TestDemarrageAChaud:
    """`ARCHITECTURE.md` §10 : un LP sans ``depart=`` dans une boucle coûte ×3 à ×5."""

    def test_le_resultat_est_identique_a_froid_et_a_chaud(self) -> None:
        """**La propriété qui compte.**

        Le démarrage à chaud est une optimisation de temps ; s'il changeait la solution,
        il changerait le certificat, et deux exécutions du même plan divergeraient.
        """
        c1 = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        c2 = np.array([0.0, 1.0, -1.0, 0.0, 0.0, 1.0, 0.0, -1.0])
        froid = resoudre(POLY_AB, c=c2)
        chaud = resoudre(POLY_AB, c=c2, depart=resoudre(POLY_AB, c=c1).x)
        assert chaud.statut == froid.statut
        assert np.allclose(chaud.x, froid.x, atol=1e-7)

    def test_un_depart_de_mauvaise_dimension_est_refuse(self) -> None:
        """Un vecteur mal apparié est un bogue d'appel, pas une donnée."""
        from archlux.erreurs import InvariantViole

        with pytest.raises(InvariantViole, match="dimension"):
            resoudre(POLY_AB, c=np.zeros(8), depart=np.zeros(3))


class TestStatutsRares:
    """« Pas optimal » recouvre trois situations, pas une."""

    def test_un_domaine_non_borne_est_signale(self) -> None:
        """Sans borne haute, minimiser ``x`` n'a pas de solution finie.

        Le polytope du projet est toujours borné par son contour ; ce statut existe pour
        que ``solve`` puisse distinguer « domaine ouvert » de « programme impossible »
        au lieu de confondre les deux sous un booléen.
        """
        ouvert = replace(POLY_1, bornes=tuple((-np.inf, np.inf) for _ in POLY_1.bornes))
        sol = resoudre(ouvert, c=np.array([1.0, 0.0, 0.0, 0.0]))
        assert sol.statut in ("non_borne", "limite")

    def test_les_egalites_sont_honorees(self) -> None:
        """``A_eq`` est vide aujourd'hui, mais portera la structure porteuse (ADR-7).

        La laisser non testée jusque-là reviendrait à découvrir sa traduction vers GLOP
        le jour où elle décidera de la position d'un mur porteur.
        """
        avec_egalite = replace(
            POLY_1,
            A_eq=sparse.csr_matrix(
                ([1.0], ([0], [POLY_1.index["A.x"]])), shape=(1, len(POLY_1.index))
            ),
            b_eq=np.array([2.5]),
        )
        sol = resoudre(avec_egalite, c=np.array([1.0, 0.0, 0.0, 0.0]))
        assert sol.statut == "optimal"
        assert sol.x[POLY_1.index["A.x"]] == pytest.approx(2.5)

    def test_un_objectif_de_mauvaise_dimension_est_refuse(self) -> None:
        """Un vecteur de coûts mal apparié est un bogue d'appel."""
        from archlux.erreurs import InvariantViole

        with pytest.raises(InvariantViole, match="objectif de dimension"):
            resoudre(POLY_1, c=np.zeros(99))


class TestCoupes:
    """Les coupes fournies sont ajoutées au système, avec leur origine."""

    def test_une_coupe_contraint_la_solution(self) -> None:
        """``w_A ≥ 4`` interdit la solution que le LP choisirait sans elle."""
        c = np.zeros(8)
        c[POLY_AB.index["A.w"]] = 1.0  # minimiser w_A → il irait à 1,5
        sans = resoudre(POLY_AB, c=c)
        avec = resoudre(
            POLY_AB,
            c=c,
            coupes=[Coupe(coeffs=(("A.w", 1.0),), borne_inf=4.0, origine="essai")],
        )
        assert sans.x[POLY_AB.index["A.w"]] == pytest.approx(1.5)
        assert avec.x[POLY_AB.index["A.w"]] == pytest.approx(4.0)

    def test_une_coupe_infaisable_est_signalee(self) -> None:
        """Une coupe impossible rend le système infaisable, pas silencieusement ignorée."""
        coupe = Coupe(coeffs=(("A.w", 1.0),), borne_inf=99.0, origine="impossible")
        sol = resoudre(POLY_AB, c=np.zeros(8), coupes=[coupe])
        assert sol.statut == "infaisable"
