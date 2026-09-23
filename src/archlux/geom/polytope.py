"""Graphe de contraintes → polytope ``A x ≤ b``, ``A_eq x = b_eq``, bornes.

Quatre variables par pièce : ``<piece>.x``, ``<piece>.y``, ``<piece>.w``, ``<piece>.h``.

Les surfaces minimales ne sont **pas** produites ici : ``w · h ≥ a`` est non linéaire et
se traite par coupes tangentes dans :mod:`archlux.lmo.coupes`.

Assemblage A x <= b et sources : ``docs/formules/polytope-separe.md``.
Épigraphe L1 : ``docs/formules/epigraphe-l1.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse

from archlux.erreurs import Infaisable, InvariantViole
from archlux.geom.graphe import construire_graphe, reduction_transitive

if TYPE_CHECKING:
    from archlux.geom.graphe import OrdreRelatif
    from archlux.types import Contexte, Plan

__all__ = [
    "CHAMPS",
    "Polytope",
    "construire_polytope",
    "devectoriser",
    "etendre_ecarts_l1",
    "figer_contacts",
    "vectoriser",
]

CHAMPS = ("x", "y", "w", "h")
"""Les quatre variables d'une pièce, **dans cet ordre**.

L'ordre est un contrat : ``lmo`` et ``solve`` supposent des colonnes contiguës par pièce,
et une trace de duaux archivée n'est relisible que si les colonnes n'ont pas bougé.
"""


@dataclass(frozen=True, slots=True)
class Polytope:
    """Le domaine admissible, sous forme matricielle creuse.

    Attributes
    ----------
    index : dict of str to int
        ``"sejour.x"`` → ``12``. Le seul pont entre noms métier et colonnes.
        **Invariant :** les valeurs sont exactement ``0..len(index)-1``, sans trou.
        ``lmo`` et ``geom`` s'appuient dessus pour identifier « rang dans la liste des
        noms triés par colonne » et « indice de colonne » ; un index troué produirait
        silencieusement des coefficients rangés sur la mauvaise variable.
    origines : tuple of str
        Ligne ``i`` de ``A`` → libellé lisible, ex. ``"separation horizontale a|b"``.
        ``len(origines) == A.shape[0]`` : c'est ce qui rend les duaux appariables.
        Les lignes de ``A_eq`` n'y figurent **pas** — elles ne sont pas dualisées.

    Notes
    -----
    **``origines`` est obligatoire, dès la première version.** Sans ce champ, un prix
    dual est « le nombre de la ligne 47 » : inutilisable. Avec lui, c'est « le mur
    porteur de l'axe 3 vous coûte 4,1 points ». Ce champ est impossible à rattraper
    après coup sans reconstruire le module (`ARCHITECTURE.md` §10, `MILESTONE-2.md` §3).

    ``index`` est un ``dict`` mutable dans un type gelé : c'est la signature imposée par
    `MILESTONE-2.md` §3. Le traiter comme immuable ; rien dans le projet ne le modifie
    après construction.
    """

    A: sparse.csr_matrix
    b: np.ndarray
    A_eq: sparse.csr_matrix
    b_eq: np.ndarray
    bornes: tuple[tuple[float, float], ...]
    index: dict[str, int]
    origines: tuple[str, ...]

    def contient(self, x: np.ndarray, tol: float = 1e-9) -> bool:
        """Dire si le point ``x`` satisfait toutes les contraintes, à ``tol`` près.

        Vérification **naïve et directe**, indépendante de tout solveur : c'est elle qui
        attrape une erreur du solveur, elle ne doit donc rien lui emprunter.

        Parameters
        ----------
        x : numpy.ndarray
            Vecteur de dimension ``len(self.index)``.
        tol : float, optional
            Tolérance absolue sur chaque contrainte.

        Returns
        -------
        bool
            ``True`` si le point est admissible : inégalités, égalités et bornes.

        Raises
        ------
        InvariantViole
            La dimension de ``x`` ne correspond pas au polytope.

        Complexity
        ----------
        O(nnz(A)).
        """
        if x.shape != (len(self.index),):
            raise InvariantViole((f"vecteur de dimension {x.shape}, attendu ({len(self.index)},)",))
        if self.A.shape[0] and np.any(self.A @ x > self.b + tol):
            return False
        if self.A_eq.shape[0] and np.any(np.abs(self.A_eq @ x - self.b_eq) > tol):
            return False
        bas = np.array([b[0] for b in self.bornes])
        haut = np.array([b[1] for b in self.bornes])
        return bool(np.all(x >= bas - tol) and np.all(x <= haut + tol))


def figer_contacts(poly: Polytope, x: np.ndarray, *, tol: float = 1e-7) -> Polytope:
    """Transformer les contacts saturés en égalités, y compris les bords du contour.

    Le polytope d'ordre est un **relaxé** : ``x_a + w_a ≤ x_b`` autorise un jour,
    et les bords gauche / bas ne sont que des ``bornes``. Après une légalisation L1
    d'un pavage, les contacts et le collage au contour sont saturés. Les figer
    empêche Frank-Wolfe d'ouvrir un trou, tout en laissant les cloisons internes
    bouger. Les largeurs minimales saturées ne sont **pas** figées : une pièce
    étroite doit pouvoir s'agrandir.

    Parameters
    ----------
    poly : Polytope
        Système d'inégalités issu de :func:`construire_polytope`.
    x : numpy.ndarray
        Point de référence, typiquement la sortie L1.
    tol : float, optional
        Un contact est saturé si ``b - Ax ≤ tol`` ; une borne l'est si l'écart
        à ``x`` est ``≤ tol``.

    Returns
    -------
    Polytope
        Même ``index`` ; lignes saturées dans ``A_eq`` ; ``x``/``y`` collés au
        contour figés dans ``bornes``.
    """
    if x.shape != (len(poly.index),):
        raise InvariantViole((f"vecteur de dimension {x.shape}, attendu ({len(poly.index)},)",))
    noms = {colonne: nom for nom, colonne in poly.index.items()}
    bornes: list[tuple[float, float]] = []
    for colonne, (lo, hi) in enumerate(poly.bornes):
        val = float(x[colonne])
        champ = noms[colonne].rsplit(".", 1)[1]
        bas, haut = lo, hi
        if champ in {"x", "y"}:
            if val - lo <= tol or hi - val <= tol:
                bas = haut = val
        elif hi - val <= tol:
            bas = haut = val
        bornes.append((bas, haut))

    if poly.A.shape[0] == 0:
        return replace(poly, bornes=tuple(bornes))
    marge = poly.b - np.ravel(poly.A @ x)
    saturees = marge <= tol
    if not np.any(saturees):
        return replace(poly, bornes=tuple(bornes))
    libres = ~saturees
    n_var = len(poly.index)
    a_libres = poly.A[libres]
    if a_libres.shape[0] == 0:
        a_libres = sparse.csr_matrix((0, n_var))
    a_saturees = poly.A[saturees]
    b_libres = poly.b[libres]
    b_saturees = poly.b[saturees]
    if poly.A_eq.shape[0]:
        a_eq = sparse.vstack([poly.A_eq, a_saturees], format="csr")
        b_eq = np.concatenate([poly.b_eq, b_saturees])
    else:
        a_eq = a_saturees.tocsr()
        b_eq = b_saturees
    origines = tuple(
        libelle for libelle, garder in zip(poly.origines, libres, strict=True) if garder
    )
    return replace(
        poly,
        A=a_libres.tocsr(),
        b=np.asarray(b_libres, dtype=float),
        A_eq=a_eq,
        b_eq=np.asarray(b_eq, dtype=float),
        bornes=tuple(bornes),
        origines=origines,
    )


def _enveloppe(ctx: Contexte) -> tuple[float, float, float, float]:
    """Boîte englobante du contour : ``(xmin, ymin, xmax, ymax)``."""
    if not ctx.contour:
        raise InvariantViole(("contour vide : aucune enveloppe n'est définissable",))
    xs = [point[0] for point in ctx.contour]
    ys = [point[1] for point in ctx.contour]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    if xmax <= xmin or ymax <= ymin:
        raise InvariantViole((f"contour dégénéré : {xmax - xmin} x {ymax - ymin}",))
    return xmin, ymin, xmax, ymax


def _verifier_enveloppe_admissible(
    largeur_min: float, largeur: float, hauteur: float, pieces: tuple[str, ...]
) -> None:
    """Refuser une enveloppe trop petite pour la largeur minimale réglementaire.

    Sans ce contrôle, ``bornes`` porte un intervalle **inversé** (``lo > hi``) : GLOP
    répond ``ABNORMAL``, que :func:`archlux.lmo.solveur._statut` traduit en
    ``"limite"``, et ``api.legalize`` lève ``InvariantViole`` — « bogue interne » — sur
    ce qui est en réalité un programme infaisable. Le certificat de Farkas est de plus
    inexploitable dans ce cas : l'infaisabilité ne vient d'aucune ligne de ``A``, donc
    le problème auxiliaire n'a lui-même pas de solution.

    Raises
    ------
    Infaisable
        ``largeur_min`` dépasse une des deux dimensions de l'enveloppe. Sans pièce, il
        n'y a aucune variable ``w``/``h`` et donc rien à refuser.
    """
    if not pieces:
        return
    conflits = tuple(
        f"largeur minimale {largeur_min} m > {libelle} de l'enveloppe ({etendue} m)"
        for libelle, etendue in (("largeur", largeur), ("hauteur", hauteur))
        if largeur_min > etendue
    )
    if conflits:
        raise Infaisable(certificat_farkas=None, origines=conflits)


def construire_polytope(ordre: OrdreRelatif, ctx: Contexte) -> Polytope:
    """Assembler le système linéaire décrivant tous les plans valides de cet ordre.

    Contraintes produites :

    - séparation horizontale ``x_a + w_a − x_b ≤ 0`` par arête de ``g.horizontal`` ;
    - séparation verticale ``y_a + h_a − y_b ≤ 0`` ;
    - load-bearing walls: one row per room and wall, keeping the room on its side
      (``ordre.wall_sides``, see :class:`archlux.geom.graphe.WallSide`);
    - contour ``x_i + w_i ≤ x_max``, ``y_i + h_i ≤ y_max`` ;
    - bords bas et gauche, et largeurs minimales ``w_i ≥ ℓ_min``, **via ``bornes``**.

    Le graphe est **réduit transitivement** avant l'assemblage. Les arêtes retirées
    restent impliquées : de ``x_a + w_a ≤ x_b`` et ``x_b + w_b ≤ x_c``, avec ``w_b ≥ 0``,
    découle ``x_a + w_a ≤ x_c``.

    Parameters
    ----------
    ordre : OrdreRelatif
        Ordre partiel, typiquement issu de :func:`archlux.geom.graphe.deduire_ordre`.
    ctx : Contexte
        Contour, structure porteuse et référentiel.

    Returns
    -------
    Polytope
        Système complet, ``index`` et ``origines`` renseignés.

    Raises
    ------
    OrdreIncoherent, SeparationManquante
        Propagées depuis :func:`archlux.geom.graphe.construire_graphe`.
    InvariantViole
        Contour vide ou dégénéré.
    Infaisable
        ``referentiel.largeur_min`` dépasse une dimension de l'enveloppe : aucune pièce
        n'y tient. Détecté ici plutôt que par le LP, qui ne saurait pas le distinguer
        d'une erreur numérique (voir :func:`_verifier_enveloppe_admissible`).

    Guarantees
    ----------
    - Géométrique : **exacte**. Tout point du polytope est un plan sans chevauchement,
      à ordre relatif fixé. La réciproque — tout plan valide de cet ordre est dans le
      polytope — est vérifiée par test de propriété sur des pavages exacts.
    - Aucune garantie de performance : ce module ignore la lumière.

    Complexity
    ----------
    O(n²) contraintes au pire, O(n) après réduction transitive en pratique.
    Budget : < 5 ms pour 15 pièces (`ARCHITECTURE.md` §9).
    """
    xmin, ymin, xmax, ymax = _enveloppe(ctx)
    graphe = reduction_transitive(construire_graphe(ordre, ordre.pieces))

    index = {
        f"{piece}.{champ}": 4 * rang + decalage
        for rang, piece in enumerate(ordre.pieces)
        for decalage, champ in enumerate(CHAMPS)
    }
    n_var = len(index)

    lignes: list[int] = []
    colonnes: list[int] = []
    valeurs: list[float] = []
    second_membre: list[float] = []
    origines: list[str] = []

    def _ajouter(termes: dict[str, float], borne: float, origine: str) -> None:
        """Ajouter une ligne ``A x <= b`` et son libelle d'origine."""
        ligne = len(origines)
        for nom, coefficient in termes.items():
            lignes.append(ligne)
            colonnes.append(index[nom])
            valeurs.append(coefficient)
        second_membre.append(borne)
        origines.append(origine)

    axes = (("horizontal", "horizontale", "x", "w"), ("vertical", "verticale", "y", "h"))
    for axe, libelle, position, taille in axes:
        for a, b in sorted(getattr(graphe, axe).edges):
            _ajouter(
                {f"{a}.{position}": 1.0, f"{a}.{taille}": 1.0, f"{b}.{position}": -1.0},
                0.0,
                f"separation {libelle} {a}|{b}",
            )

    for piece in ordre.pieces:
        _ajouter({f"{piece}.x": 1.0, f"{piece}.w": 1.0}, xmax, f"contour droit {piece}")
        _ajouter({f"{piece}.y": 1.0, f"{piece}.h": 1.0}, ymax, f"contour haut {piece}")

    # Load-bearing walls are fixed obstacles: each room keeps the side it was on.
    wall_rows: dict[str, tuple[dict[str, float], float]] = {
        "left": ({"x": 1.0, "w": 1.0}, 1.0),  # x + w <= bound
        "right": ({"x": -1.0}, -1.0),  # -x <= -bound
        "below": ({"y": 1.0, "h": 1.0}, 1.0),  # y + h <= bound
        "above": ({"y": -1.0}, -1.0),  # -y <= -bound
    }
    for side in ordre.wall_sides:
        terms, sign = wall_rows[side.side]
        _ajouter(
            {f"{side.room}.{field}": coefficient for field, coefficient in terms.items()},
            sign * side.bound,
            f"load-bearing {side.wall}: {side.room} {side.side} of {side.bound:g}",
        )

    matrice = sparse.coo_matrix((valeurs, (lignes, colonnes)), shape=(len(origines), n_var)).tocsr()

    largeur_min = ctx.referentiel.largeur_min
    _verifier_enveloppe_admissible(largeur_min, xmax - xmin, ymax - ymin, ordre.pieces)
    bornes_par_champ = {
        "x": (xmin, xmax),
        "y": (ymin, ymax),
        "w": (largeur_min, xmax - xmin),
        "h": (largeur_min, ymax - ymin),
    }
    bornes = tuple(bornes_par_champ[champ] for _ in ordre.pieces for champ in CHAMPS)

    return Polytope(
        A=matrice,
        b=np.array(second_membre, dtype=float),
        # Empty but well shaped. Load-bearing walls are inequality rows (ordre.wall_sides),
        # not equalities: a room only has to stay on its side of a wall.
        A_eq=sparse.csr_matrix((0, n_var)),
        b_eq=np.zeros(0, dtype=float),
        bornes=bornes,
        index=index,
        origines=tuple(origines),
    )


def vectoriser(plan: Plan, index: dict[str, int]) -> np.ndarray:
    """Projeter un plan sur le vecteur de décision ordonné par ``index``.

    Parameters
    ----------
    plan : Plan
        Plan à encoder.
    index : dict of str to int
        Table de correspondance issue d'un :class:`Polytope`.

    Returns
    -------
    numpy.ndarray
        Vecteur de dimension ``len(index)``.

    Raises
    ------
    InvariantViole
        Une pièce attendue par ``index`` est absente du plan. C'est un bogue interne :
        le polytope et le plan doivent venir du même ordre.

    Complexity
    ----------
    O(n).
    """
    point = np.zeros(len(index), dtype=float)
    par_id = {piece.id: piece for piece in plan.pieces}
    for nom, colonne in index.items():
        piece_id, champ = nom.rsplit(".", 1)
        piece = par_id.get(piece_id)
        if piece is None:
            raise InvariantViole((f"pièce {piece_id} absente du plan à vectoriser",))
        point[colonne] = getattr(piece, champ)
    return point


def devectoriser(x: np.ndarray, gabarit: Plan, index: dict[str, int]) -> Plan:
    """Reconstruire un plan depuis un vecteur solution.

    ``gabarit`` fournit tout ce que le vecteur ne porte pas : murs, ouvertures, contour.
    Les ouvertures étant relatives à leur mur, elles suivent le déplacement sans
    retouche — c'est exactement la raison de l'invariant de `ARCHITECTURE.md` §6.

    Parameters
    ----------
    x : numpy.ndarray
        Solution du LP.
    gabarit : Plan
        Plan d'origine, **non muté** : un nouveau plan est rendu.
    index : dict of str to int
        Table de correspondance du polytope.

    Returns
    -------
    Plan
        Nouveau plan, **sans certificat** — c'est ``api.legalize`` qui l'y attache, et
        seulement après vérification exacte indépendante.

    Raises
    ------
    InvariantViole
        Dimension inattendue, ou pièce du gabarit absente du polytope. Laisser une pièce
        non mise à jour produirait un plan faux que ``certify`` rejetterait plus loin,
        avec un diagnostic sans rapport avec la cause.

    Complexity
    ----------
    O(n).
    """
    if x.shape != (len(index),):
        raise InvariantViole((f"vecteur de dimension {x.shape}, attendu ({len(index)},)",))
    manquantes = sorted(piece.id for piece in gabarit.pieces if f"{piece.id}.x" not in index)
    if manquantes:
        raise InvariantViole((f"pièces absentes du polytope : {', '.join(manquantes)}",))
    pieces = tuple(
        replace(
            piece,
            x=float(x[index[f"{piece.id}.x"]]),
            y=float(x[index[f"{piece.id}.y"]]),
            w=float(x[index[f"{piece.id}.w"]]),
            h=float(x[index[f"{piece.id}.h"]]),
        )
        for piece in gabarit.pieces
    )
    return replace(gabarit, pieces=pieces, certificat=None)


def etendre_ecarts_l1(poly: Polytope, x_ref: np.ndarray) -> Polytope:
    r"""Épigraphe de :math:`\\|x - \\hat{x}\\|_1` : variables d'écart et deux inégalités.

    Formule
    -------
    :math:`\\min_x \\sum_i |x_i - \\hat{x}_i|` n'est pas linéaire. L'épigraphe
    (Bertsimas & Tsitsiklis, *Introduction to Linear Optimization*, Athena
    Scientific, 1997, §1.3) introduit :math:`e_i \\ge 0` tel que

    .. math::

        e_i \\ge x_i - \\hat{x}_i, \\qquad e_i \\ge \\hat{x}_i - x_i,

    soit, sous la forme :math:`A x \\le b` du polytope :

    .. math::

        x_i - e_i \\le \\hat{x}_i, \\qquad -x_i - e_i \\le -\\hat{x}_i.

    L'objectif devient :math:`\\min \\sum_i e_i`, linéaire. Omettre une des deux
    familles rend :math:`e_i` libre d'un côté et produit un déplacement apparent
    énorme (`MILESTONE-2.md` §10).

    Les colonnes d'origine gardent leurs indices ``0..n-1`` ; les écarts occupent
    ``n..2n-1`` sous le nom ``e.<variable>``.

    Parameters
    ----------
    poly : Polytope
        Domaine géométrique, n variables.
    x_ref : numpy.ndarray
        Plan proposé vectorisé, dimension n.

    Returns
    -------
    Polytope
        Domaine de dimension ``2n``.

    Raises
    ------
    InvariantViole
        Dimension de ``x_ref`` incompatible.

    Notes
    -----
    Dérivation et cas d'usage : ``docs/formules/epigraphe-l1.md``.
    """
    n_var = len(poly.index)
    if x_ref.shape != (n_var,):
        raise InvariantViole((f"référence de dimension {x_ref.shape}, attendu ({n_var},)",))
    noms = sorted(poly.index, key=lambda nom: poly.index[nom])
    index = dict(poly.index)
    for rang, nom in enumerate(noms):
        index[f"e.{nom}"] = n_var + rang

    n_lignes = poly.A.shape[0]
    a_pad = (
        sparse.hstack([poly.A, sparse.csr_matrix((n_lignes, n_var))]).tocsr()
        if n_lignes
        else sparse.csr_matrix((0, 2 * n_var))
    )
    a_eq_pad = (
        sparse.hstack([poly.A_eq, sparse.csr_matrix((poly.A_eq.shape[0], n_var))]).tocsr()
        if poly.A_eq.shape[0]
        else sparse.csr_matrix((0, 2 * n_var))
    )

    lignes: list[int] = []
    colonnes: list[int] = []
    valeurs: list[float] = []
    second: list[float] = []
    origines_extra: list[str] = []
    for rang, nom in enumerate(noms):
        ligne = 2 * rang
        lignes.extend((ligne, ligne))
        colonnes.extend((rang, n_var + rang))
        valeurs.extend((1.0, -1.0))
        second.append(float(x_ref[rang]))
        origines_extra.append(f"ecart plus {nom}")
        ligne = 2 * rang + 1
        lignes.extend((ligne, ligne))
        colonnes.extend((rang, n_var + rang))
        valeurs.extend((-1.0, -1.0))
        second.append(float(-x_ref[rang]))
        origines_extra.append(f"ecart moins {nom}")

    extra = sparse.coo_matrix((valeurs, (lignes, colonnes)), shape=(2 * n_var, 2 * n_var)).tocsr()
    matrice = sparse.vstack([a_pad, extra]).tocsr() if n_lignes else extra
    inf = float("inf")
    return Polytope(
        A=matrice,
        b=np.concatenate([poly.b, np.asarray(second, dtype=float)]),
        A_eq=a_eq_pad,
        b_eq=poly.b_eq,
        bornes=tuple(poly.bornes) + tuple((0.0, inf) for _ in range(n_var)),
        index=index,
        origines=tuple(poly.origines) + tuple(origines_extra),
    )
