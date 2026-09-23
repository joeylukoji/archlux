r"""Coupes tangentes pour les contraintes de surface minimale.

Formule
=======
L'aire d'un rectangle est le produit :math:`a(w,h) = w h`. La contrainte
réglementaire :math:`w h \\ge a_{\\min}` n'est **pas linéaire**. GLOP ne sait
la traiter que via une approximation linéaire.

Convexité
---------
Sur :math:`\\mathbb{R}_{>0}^2`, :math:`g(w,h) = \\log w + \\log h` est concave
(Boyd & Vandenberghe, *Convex Optimization*, Cambridge University Press, 2004,
§3.1.5, composition avec le log). Ses super-niveaux

.. math::

    K = \\{(w,h) : w>0,\\ h>0,\\ w h \\ge a_{\\min}\\}
      = \\{ g \\ge \\log a_{\\min} \\}

sont donc **convexes** (ibid., §3.1.6).

Tangente
--------
Au point de contact :math:`(w_0,h_0)` de l'hyperbole :math:`w_0 h_0 = a_{\\min}`,
:math:`\\nabla g = (1/w_0,\\ 1/h_0)` et le demi-espace d'appui contenant :math:`K`
s'écrit

.. math::

    \\frac{w-w_0}{w_0} + \\frac{h-h_0}{h_0} \\ge 0
    \\quad\\Longleftrightarrow\\quad
    h_0 w + w_0 h \\ge 2 a_{\\min}.

C'est aussi l'AM-GM (Hardy, Littlewood, Pólya, *Inequalities*, 2e éd., Cambridge,
1952, th. 16) : :math:`(w/w_0 + h/h_0)/2 \\ge \\sqrt{wh/(w_0 h_0)}`, qui vaut
:math:`\\ge 1` dès que :math:`wh \\ge a_{\\min}`.

Si le point courant viole la contrainte, on le **projette** d'abord sur
l'hyperbole en conservant le rapport d'aspect
:math:`(w_0,h_0) \\leftarrow \\sqrt{a_{\\min}/(wh)}\\,(w,h)`, sans quoi la
tangente écrite en un point intérieur à l'infaissable **exclut** des points
admissibles (même rapport, produit :math:`= a_{\\min}`).

La boucle de Kelley (Kelley, J. E., *The cutting-plane method for solving convex
programs*, SIAM J. 8, 1960) ajoute ces tangentes jusqu'à satisfaction ou
``MAX_COUPES_PAR_PIECE``.

Dérivation pas à pas, cas d'usage et DOI : ``docs/formules/coupes-surface.md``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from math import sqrt
from typing import TYPE_CHECKING

import numpy as np
import structlog

from archlux.erreurs import InvariantViole
from archlux.lmo.solveur import resoudre

if TYPE_CHECKING:
    from archlux.geom.polytope import Polytope
    from archlux.lmo.solveur import SolutionLP
    from archlux.types import Contexte, Piece

__all__ = [
    "MAX_COUPES_PAR_PIECE",
    "Coupe",
    "coupe_surface",
    "resoudre_avec_surfaces",
    "surfaces_violees",
]

MAX_COUPES_PAR_PIECE = 10
"""Au-delà, ``log.warning("coupe.limite", piece=...)`` et arrêt pour cette pièce."""

_LOG = structlog.get_logger("archlux.lmo.coupes")
_TOLERANCE_AIRE = 1e-6
"""Alignée sur la tolérance du §5 : ``aire >= a_min - 1e-6``, en mètres carrés."""
_TOLERANCE_BORNE = 1e-12
"""Tolérance d'appartenance à la boîte des bornes, en mètres."""
_TOLERANCE_LONGUEUR = 1e-6
"""Tolérance de comparaison d'une longueur à une borne, en mètres.

Distincte de :data:`_TOLERANCE_AIRE` malgré la valeur commune : l'une porte sur des
mètres carrés, l'autre sur des mètres. Les confondre rendrait toute révision de l'une
silencieusement dépendante de l'autre.
"""


def _points_appui_hyperbole(
    a_min: float, w_min: float, w_max: float, h_min: float, h_max: float
) -> tuple[tuple[float, float], ...]:
    """Points de l'hyperbole ``wh = a_min`` dans la boîte des bornes.

    Les tangentes en ces points forment l'approximation extérieure initiale
    (Kelley, 1960) : extrémités de l'arc admissible et le carré, s'il y tient.
    """
    points: list[tuple[float, float]] = []
    cote = sqrt(a_min)

    def _dans_boite(largeur: float, hauteur: float) -> bool:
        """Dire si le couple ``(largeur, hauteur)`` tient dans les bornes du LP."""
        return (
            w_min - _TOLERANCE_BORNE <= largeur <= w_max + _TOLERANCE_BORNE
            and h_min - _TOLERANCE_BORNE <= hauteur <= h_max + _TOLERANCE_BORNE
        )

    if _dans_boite(cote, cote):
        points.append((cote, cote))
    if w_min > 0.0 and _dans_boite(w_min, a_min / w_min):
        points.append((w_min, a_min / w_min))
    if h_min > 0.0 and _dans_boite(a_min / h_min, h_min):
        points.append((a_min / h_min, h_min))
    uniques: list[tuple[float, float]] = []
    for candidat in points:
        if not any(
            abs(candidat[0] - vu[0]) < _TOLERANCE_BORNE
            and abs(candidat[1] - vu[1]) < _TOLERANCE_BORNE
            for vu in uniques
        ):
            uniques.append(candidat)
    return tuple(uniques)


def _coupes_initiales(
    poly: Polytope, ctx: Contexte, pieces: tuple[Piece, ...]
) -> list[Coupe]:
    """Tangentes d'enveloppe, avant la première résolution."""
    coupes: list[Coupe] = []
    for piece in pieces:
        seuil = ctx.referentiel.a_min(piece.type)
        if seuil <= 0.0:
            continue
        w_min, w_max = poly.bornes[poly.index[f"{piece.id}.w"]]
        h_min, h_max = poly.bornes[poly.index[f"{piece.id}.h"]]
        for largeur, hauteur in _points_appui_hyperbole(
            seuil, w_min, w_max, h_min, h_max
        ):
            coupes.append(coupe_surface(largeur, hauteur, seuil, piece=piece.id))
    return coupes


@dataclass(frozen=True, slots=True)
class Coupe:
    """Inégalité linéaire ``Σ coeffs[v]·v ≥ borne_inf`` ajoutée au polytope.

    Attributes
    ----------
    coeffs : tuple of (str, float)
        Paires ``(nom de variable, coefficient)``, triées.
    origine : str
        Libellé reversé dans le diagnostic dual.
    """

    coeffs: tuple[tuple[str, float], ...]
    borne_inf: float
    origine: str

    def satisfait(self, w: float, h: float, tol: float = 1e-9) -> bool:
        """Dire si le couple ``(w, h)`` satisfait la coupe de surface.

        Parameters
        ----------
        w, h : float
            Largeur et hauteur testées, en mètres.
        tol : float, optional
            Tolérance additive sur l'inégalité.

        Returns
        -------
        bool
            ``True`` si ``Σ coef·variable ≥ borne_inf - tol``.
        """
        total = 0.0
        for nom, coefficient in self.coeffs:
            champ = nom.rsplit(".", 1)[-1]
            if champ == "w":
                total += coefficient * w
            elif champ == "h":
                total += coefficient * h
        return bool(total + tol >= self.borne_inf)


def coupe_surface(w0: float, h0: float, a_min: float, *, piece: str = "") -> Coupe:
    """Tangente à l'hyperbole ``w h = a_min`` au point projeté de ``(w₀, h₀)``.

    Parameters
    ----------
    w0, h0 : float
        Point de linéarisation, strictement positif (solution courante).
    a_min : float
        Surface minimale, en mètres carrés, strictement positive.
    piece : str, optional
        Identifiant de pièce, préfixe des variables ``<id>.w`` / ``<id>.h``.

    Returns
    -------
    Coupe
        ``h_★ w + w_★ h ≥ 2 a_min`` au point ``(w_★, h_★)`` de l'hyperbole.

    Raises
    ------
    InvariantViole
        Point non strictement positif, ou ``a_min`` non strictement positive.

    Guarantees
    ----------
    - Géométrique : **exacte**. Aucun ``(w,h)`` de produit ``≥ a_min`` n'est exclu.

    Notes
    -----
    Formule et sources : ``docs/formules/coupes-surface.md``.
    """
    if w0 <= 0.0 or h0 <= 0.0:
        raise InvariantViole((f"point de linéarisation non strictement positif : {(w0, h0)}",))
    if a_min <= 0.0:
        raise InvariantViole((f"surface minimale non strictement positive : {a_min}",))
    produit = w0 * h0
    scale = sqrt(a_min / produit)
    w_star, h_star = w0 * scale, h0 * scale
    nom_w = f"{piece}.w" if piece else "w"
    nom_h = f"{piece}.h" if piece else "h"
    coeffs = tuple(sorted(((nom_w, h_star), (nom_h, w_star))))
    origine = f"surface {piece}" if piece else "surface"
    return Coupe(coeffs=coeffs, borne_inf=2.0 * a_min, origine=origine)


def surfaces_violees(
    x: np.ndarray | Sequence[float],
    poly: Polytope,
    ctx: Contexte,
    *,
    pieces: tuple[Piece, ...],
) -> tuple[str, ...]:
    """Lister les pièces dont ``w h`` est strictement sous ``a_min``.

    Parameters
    ----------
    x : numpy.ndarray
        Solution courante du LP.
    poly : Polytope
        Fournit ``index``.
    ctx : Contexte
        Fournit ``referentiel.a_min``.
    pieces : tuple of Piece
        Identifiants et types — le polytope ne porte pas le programme.

    Returns
    -------
    tuple of str
        Identifiants triés.
    """
    vecteur = np.asarray(x, dtype=float)
    violees: list[str] = []
    for piece in pieces:
        seuil = ctx.referentiel.a_min(piece.type)
        if seuil <= 0.0:
            continue
        largeur = float(vecteur[poly.index[f"{piece.id}.w"]])
        hauteur = float(vecteur[poly.index[f"{piece.id}.h"]])
        if largeur * hauteur + _TOLERANCE_AIRE < seuil:
            violees.append(piece.id)
    return tuple(sorted(violees))


def _cible_sur_hyperbole(
    largeur: float,
    hauteur: float,
    a_min: float,
    w_min: float,
    w_max: float,
    h_min: float,
    h_max: float,
) -> tuple[float, float] | None:
    """Point de ``wh = a_min`` dans la boîte, même rapport d'aspect si possible.

    Si le rayon sort par un bord, on glisse sur l'arc jusqu'à l'intersection
    hyperbole–boîte (sommet réel de ``K``, atteignable par le simplexe).
    """
    if largeur <= 0.0 or hauteur <= 0.0 or a_min <= 0.0:
        return None
    if largeur * hauteur + _TOLERANCE_AIRE >= a_min:
        return None
    facteur = sqrt(a_min / (largeur * hauteur))
    w_star, h_star = largeur * facteur, hauteur * facteur
    w_star = min(max(w_star, w_min), w_max)
    h_star = a_min / w_star if w_star > 0.0 else h_max
    if h_min - _TOLERANCE_LONGUEUR <= h_star <= h_max + _TOLERANCE_LONGUEUR:
        return w_star, min(max(h_star, h_min), h_max)
    h_star = min(max(hauteur * facteur, h_min), h_max)
    w_star = a_min / h_star if h_star > 0.0 else w_max
    if w_min - _TOLERANCE_LONGUEUR <= w_star <= w_max + _TOLERANCE_LONGUEUR:
        return min(max(w_star, w_min), w_max), h_star
    return None


def _resserrer_bornes(
    poly: Polytope, x: np.ndarray, ctx: Contexte, pieces: tuple[Piece, ...]
) -> Polytope:
    """Élever les bornes inférieures de ``w,h`` jusqu'à l'hyperbole courante.

    Le simplexe ne rend que des sommets d'un polyèdre. Sur ``{wh ≥ a}``,
    strictement convexe, l'optimum (AM-GM : minimiser ``w+h``) n'est jamais un
    sommet d'une approximation finie : les sommets oscillent sur une corde,
    produit ``a − δ²``. Imposer ``w ≥ w★``, ``h ≥ h★`` force le sommet suivant
    à respecter l'aire, et laisse GLOP réajuster ``x, y`` (Kelley, 1960, plus
    resserrement de bornes).
    """
    bornes = list(poly.bornes)
    change = False
    for piece in pieces:
        seuil = ctx.referentiel.a_min(piece.type)
        if seuil <= 0.0:
            continue
        idx_w = poly.index[f"{piece.id}.w"]
        idx_h = poly.index[f"{piece.id}.h"]
        w_min, w_max = bornes[idx_w]
        h_min, h_max = bornes[idx_h]
        cible = _cible_sur_hyperbole(
            float(x[idx_w]), float(x[idx_h]), seuil, w_min, w_max, h_min, h_max
        )
        if cible is None:
            continue
        w_star, h_star = cible
        if w_star > w_min + _TOLERANCE_LONGUEUR:
            bornes[idx_w] = (w_star, w_max)
            change = True
        if h_star > h_min + _TOLERANCE_LONGUEUR:
            bornes[idx_h] = (h_star, h_max)
            change = True
    return replace(poly, bornes=tuple(bornes)) if change else poly


def _identifiants_a_couper(
    x: np.ndarray,
    poly: Polytope,
    ctx: Contexte,
    pieces: tuple[Piece, ...],
    comptes: Counter[str],
) -> list[str]:
    """Pièces encore sous ``a_min`` et sous le plafond de coupes."""
    restantes: list[str] = []
    for identifiant in surfaces_violees(x, poly, ctx, pieces=pieces):
        if comptes[identifiant] >= MAX_COUPES_PAR_PIECE:
            _LOG.warning("coupe.limite", piece=identifiant)
            continue
        restantes.append(identifiant)
    return restantes


def _empiler_tangentes(
    restantes: list[str],
    x: np.ndarray,
    poly: Polytope,
    ctx: Contexte,
    pieces: tuple[Piece, ...],
    coupes: list[Coupe],
    comptes: Counter[str],
) -> None:
    """Ajouter une tangente Kelley par pièce restante (Kelley, 1960)."""
    par_id = {piece.id: piece for piece in pieces}
    for identifiant in restantes:
        piece = par_id[identifiant]
        largeur = float(x[poly.index[f"{identifiant}.w"]])
        hauteur = float(x[poly.index[f"{identifiant}.h"]])
        coupes.append(
            coupe_surface(
                largeur, hauteur, ctx.referentiel.a_min(piece.type), piece=identifiant
            )
        )
        comptes[identifiant] += 1


def resoudre_avec_surfaces(
    poly: Polytope,
    c: np.ndarray,
    ctx: Contexte,
    pieces: tuple[Piece, ...],
    *,
    depart: np.ndarray | None = None,
    duaux: bool = False,
) -> SolutionLP:
    """Résoudre le LP en ajoutant les tangentes de surface jusqu'à satisfaction.

    Parameters
    ----------
    poly : Polytope
        Domaine linéaire (séparations, contour, éventuellement écarts L1).
    c : numpy.ndarray
        Objectif, dimension ``len(poly.index)``.
    ctx : Contexte
        Référentiel des surfaces.
    pieces : tuple of Piece
        Programme, pour typer chaque identifiant.
    depart : numpy.ndarray or None, optional
        Warm start du premier appel.
    duaux : bool, optional
        Extraire les duaux du dernier LP.

    Returns
    -------
    SolutionLP
        Dernière solution. Statut inchangé si le LP d'origine est infaisable.

    Warnings
    --------
    ``statut == "optimal"`` **ne garantit pas** ``w·h ≥ a_min`` :

    - la boucle rend la main dès qu'une pièce atteint ``MAX_COUPES_PAR_PIECE``, avec la
      dernière solution telle quelle. C'est un plafond de terminaison, pas une preuve ;
    - :func:`_resserrer_bornes` **restreint** le domaine (``w ≥ w★`` et ``h ≥ h★``
      simultanément, alors que ``{wh ≥ a_min}`` autorise d'échanger l'un contre
      l'autre). L'optimum rendu est donc celui du domaine resserré, pas du domaine
      exact, et il peut être strictement moins bon.

    Dans les deux cas, seule :func:`archlux.certify.preuve.verifier_exactement` tranche.
    Les duaux rendus sont ceux des lignes de ``A``, inchangées par le resserrement : la
    pression exercée par les surfaces minimales n'y apparaît pas.

    Notes
    -----
    Dérivation, sources et cas d'usage : ``docs/formules/coupes-surface.md``.
    """
    domaine = poly
    coupes: list[Coupe] = _coupes_initiales(domaine, ctx, pieces)
    comptes: Counter[str] = Counter()
    courant = depart
    while True:
        solution = resoudre(
            domaine, c, depart=courant, coupes=coupes or None, duaux=duaux
        )
        if solution.statut != "optimal":
            return solution
        if not surfaces_violees(solution.x, domaine, ctx, pieces=pieces):
            return solution
        resserre = _resserrer_bornes(domaine, solution.x, ctx, pieces)
        if resserre is not domaine:
            affine = resoudre(
                resserre, c, depart=solution.x, coupes=coupes or None, duaux=duaux
            )
            if affine.statut == "optimal":
                if not surfaces_violees(affine.x, resserre, ctx, pieces=pieces):
                    return affine
                domaine = resserre
                solution = affine
        restantes = _identifiants_a_couper(
            solution.x, domaine, ctx, pieces, comptes
        )
        if not restantes:
            return solution
        _empiler_tangentes(
            restantes, solution.x, domaine, ctx, pieces, coupes, comptes
        )
        courant = solution.x
