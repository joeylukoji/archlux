r"""Contraintes de pavage exact — rendre un « jour » non représentable.

Le problème
-----------
Le polytope d'ordre est un **relaxé** : ``x_a + w_a ≤ x_b`` interdit le
chevauchement, jamais le trou. Si l'entrée porte un jour, le plan troué est déjà
le point le plus proche de lui-même : l'optimum L1 le laisse tel quel, et
``certify.proof`` le rejette. Mesuré sur MSD sans ce module : ``legalize`` répare
68 % des chevauchements et 10 % des jours.

Le résultat qui débloque
------------------------
Dans une dissection rectangulaire, tout bord de pièce est porté par une **ligne
de trame**. Écrivons la pièce :math:`i` comme
:math:`[v_{l(i)}, v_{r(i)}] \times [h_{b(i)}, h_{t(i)}]`, indices entiers. La
pièce couvre alors exactement les cellules :math:`l(i) \le a < r(i)`,
:math:`b(i) \le \beta < t(i)`.

**La condition de pavage ne porte que sur les indices, jamais sur les
coordonnées.** L'union pave le contour si et seulement si ces cellules forment
une partition du tableau — un fait combinatoire, vérifié une fois.

Il suffit donc d'imposer *« ces bords partagent une ligne »*, ce qui est un jeu
d'égalités affines dans les variables existantes. Tout point admissible est alors
un pavage exact : **un jour cesse d'être représentable**.

Deux propriétés en découlent, et ce sont elles qui distinguent cette approche du
gel de contacts (:func:`~archlux.geom.polytope.figer_contacts`) :

1. **Le système reste faisable.** Les positions de trame du plan de référence
   sont toujours un point admissible. Geler des contacts *approximativement*
   saturés n'offre aucune garantie de ce genre — 8 % de LP infaisables mesurés.
2. **La garantie est structurelle, pas numérique.** Elle ne dépend d'aucune
   tolérance à l'exécution : la vérification de partition a déjà eu lieu.

Récupérer la structure
----------------------
La contrepartie est que la trame doit être **récupérable** depuis le plan proposé,
qui est justement fautif. Le levier n'est pas une tolérance métrique — la deviner
échoue : trop large elle écrase les pièces étroites, trop étroite elle ne récupère
rien (mesuré : 3,8 % de réparation).

Le bon critère est le **support** d'une ligne, c'est-à-dire le nombre de bords
qu'elle porte. Dans un plan sain, une ligne intérieure en porte au moins deux : un
mur sépare deux pièces. Déplacer une pièce fait quitter sa ligne à un bord et en
crée une nouvelle, portée par lui seul. Résorber les lignes **orphelines** dans
leur voisine la plus proche — en refusant toute fusion qui écraserait une pièce —
récupère donc la structure voulue sans aucun seuil en mètres. Un jour de 2 m se
rattrape aussi bien qu'un jour de 5 cm, et une cloison de 40 cm survit.

S'y ajoute une **réparation bornée** de la partition : agrandir ou rétrécir une
pièce d'un cran tant que les cellules concernées sont toutes manquantes, ou toutes
en excès. Le budget (défaut 4) distingue la réparation de la reconstruction.

Mesuré sur MSD, 4 796 plans corrompus : la réparation passe de 35,9 % à 93,9 %, et
sur les jours seuls de 10,0 % à 98,0 %.

Référence : formulation par coordonnées de murs des dissections rectangulaires,
Otten (1982) et Lengauer (1990) ch. 10 — voir ``docs/formules/sources.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse
from shapely import contains_xy
from shapely.geometry import Polygon

from archlux.erreurs import GridNotRecoverable, InvariantViole

if TYPE_CHECKING:
    from collections.abc import Sequence

    from archlux.geom.polytope import Polytope
    from archlux.types import Contexte, Plan

__all__ = ["Trame", "contraintes_pavage", "deduire_trame", "etendre_pavage", "snap_to_grid"]

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class Trame:
    """Structure combinatoire d'une dissection rectangulaire.

    Attributes
    ----------
    lignes_x, lignes_y : tuple of float
        Positions **de référence** des lignes de trame, croissantes. Elles ne sont
        pas imposées : seules les incidences le sont. Elles servent de point
        admissible de repli et de diagnostic.
    incidences : tuple of (str, int, int, int, int)
        Par pièce : ``(id, gauche, droite, bas, haut)``, indices dans
        ``lignes_x`` / ``lignes_y``. ``gauche < droite`` et ``bas < haut``.
    """

    lignes_x: tuple[float, ...]
    lignes_y: tuple[float, ...]
    incidences: tuple[tuple[str, int, int, int, int], ...]
    ancrees_x: frozenset[int] = frozenset()
    ancrees_y: frozenset[int] = frozenset()

    @property
    def n_cellules(self) -> int:
        """Nombre de cellules du tableau, ``(p - 1) × (q - 1)``."""
        return (len(self.lignes_x) - 1) * (len(self.lignes_y) - 1)


def _regrouper(valeurs: Sequence[float], tolerance: float) -> tuple[list[float], dict[float, int]]:
    """Regrouper des coordonnées proches en lignes de trame croissantes.

    Balayage croissant : on agrège tant que l'écart au **précédent** reste sous
    ``tolerance``. Le regroupement est donc transitif le long d'une chaîne, ce qui
    est voulu : une enfilade de bords décalés de proche en proche décrit une seule
    intention d'alignement.
    """
    triees = sorted(set(valeurs))
    if not triees:
        return [], {}
    groupes: list[list[float]] = [[triees[0]]]
    for valeur in triees[1:]:
        if valeur - groupes[-1][-1] <= tolerance:
            groupes[-1].append(valeur)
        else:
            groupes.append([valeur])
    lignes = [sum(g) / len(g) for g in groupes]
    rang: dict[float, int] = {}
    for indice, groupe in enumerate(groupes):
        for valeur in groupe:
            rang[valeur] = indice
    return lignes, rang


def _consolider(
    lignes: list[float],
    bords: list[tuple[int, int]],
    protegees: set[int],
    support_min: int,
) -> tuple[list[float], list[tuple[int, int]], set[int]]:
    """Résorber les lignes **orphelines** dans leur voisine la plus proche.

    Dans un plan sain, une ligne de trame intérieure est portée par plusieurs
    bords : un mur sépare deux pièces, donc au moins un bord de chaque côté.
    Déplacer une pièce fait quitter sa ligne à un bord et en crée une nouvelle,
    portée par lui seul. Le **support** — le nombre de bords portés — distingue
    donc la structure voulue de l'accident, sans qu'aucune tolérance métrique ait
    à être devinée.

    On résorbe tant qu'il reste une ligne intérieure de support ``< support_min``,
    en la fusionnant avec la ligne la plus proche — sauf si cela **écrase une
    pièce**, c'est-à-dire ramène ses deux bords sur la même ligne. Ce refus est ce
    qui empêche une pièce étroite d'être absorbée par une tolérance trop large.

    Parameters
    ----------
    lignes : list of float
        Positions des lignes, croissantes.
    bords : list of (int, int)
        Un couple ``(ligne_basse, ligne_haute)`` par pièce, sur cet axe.
    protegees : set of int
        Lignes qu'on ne résorbe jamais — les bords du contour.
    support_min : int
        En deçà de ce nombre de bords portés, une ligne intérieure est orpheline.

    Returns
    -------
    tuple
        ``(lignes, bords, protegees)`` réindexés, sans ligne orpheline résorbable.
    """
    while True:
        support: dict[int, int] = dict.fromkeys(range(len(lignes)), 0)
        for basse, haute in bords:
            support[basse] += 1
            support[haute] += 1
        candidates = sorted(
            (k for k, n in support.items() if n < support_min and k not in protegees),
            key=lambda k: (support[k], k),
        )
        fusion: tuple[int, int] | None = None
        for orpheline in candidates:
            voisines = sorted(
                (j for j in range(len(lignes)) if j != orpheline),
                key=lambda j: abs(lignes[j] - lignes[orpheline]),
            )
            for cible in voisines:
                remplace = {orpheline: cible}
                # La voisine la plus proche peut se trouver de l'autre cote du bord
                # deplace : tester l'egalite ne suffit pas, il faut l'ordre strict,
                # sinon la piece ressort avec ses bords inverses.
                ecrase = any(
                    remplace.get(basse, basse) >= remplace.get(haute, haute)
                    for basse, haute in bords
                )
                if not ecrase:
                    fusion = (orpheline, cible)
                    break
            if fusion is not None:
                break
        if fusion is None:
            return lignes, bords, protegees
        orpheline, cible = fusion
        bords = [
            (cible if basse == orpheline else basse, cible if haute == orpheline else haute)
            for basse, haute in bords
        ]
        # Reindexer en retirant la ligne resorbee, protegees comprises.
        garde = [k for k in range(len(lignes)) if k != orpheline]
        nouveau = {ancien: rang for rang, ancien in enumerate(garde)}
        lignes = [lignes[k] for k in garde]
        bords = [(nouveau[basse], nouveau[haute]) for basse, haute in bords]
        protegees = {nouveau[k] for k in protegees if k in nouveau}


def _couverture(
    incidences: list[tuple[str, int, int, int, int]], forme: tuple[int, int]
) -> np.ndarray:
    """Nombre de pieces couvrant chaque cellule."""
    grille = np.zeros(forme, dtype=int)
    for _, gauche, droite, bas, haut in incidences:
        grille[gauche:droite, bas:haut] += 1
    return grille


def _retouches(
    incidence: tuple[str, int, int, int, int], forme: tuple[int, int]
) -> list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]]:
    """Agrandissements et retrecissements d'un cran, avec les cellules concernees.

    Le booleen dit s'il s'agit d'une extension (vrai) ou d'une reduction (faux).
    Bouger un seul indice d'un cran laisse la piece rectangulaire par construction.
    """
    nom, gauche, droite, bas, haut = incidence
    largeur, hauteur = forme
    propositions: list[tuple[tuple[str, int, int, int, int], tuple[slice, slice], bool]] = []
    if gauche > 0:
        propositions.append(
            (
                (nom, gauche - 1, droite, bas, haut),
                (slice(gauche - 1, gauche), slice(bas, haut)),
                True,
            )
        )
    if droite < largeur:
        propositions.append(
            (
                (nom, gauche, droite + 1, bas, haut),
                (slice(droite, droite + 1), slice(bas, haut)),
                True,
            )
        )
    if bas > 0:
        propositions.append(
            (
                (nom, gauche, droite, bas - 1, haut),
                (slice(gauche, droite), slice(bas - 1, bas)),
                True,
            )
        )
    if haut < hauteur:
        propositions.append(
            (
                (nom, gauche, droite, bas, haut + 1),
                (slice(gauche, droite), slice(haut, haut + 1)),
                True,
            )
        )
    if droite - gauche > 1:
        propositions.append(
            (
                (nom, gauche + 1, droite, bas, haut),
                (slice(gauche, gauche + 1), slice(bas, haut)),
                False,
            )
        )
        propositions.append(
            (
                (nom, gauche, droite - 1, bas, haut),
                (slice(droite - 1, droite), slice(bas, haut)),
                False,
            )
        )
    if haut - bas > 1:
        propositions.append(
            (
                (nom, gauche, droite, bas + 1, haut),
                (slice(gauche, droite), slice(bas, bas + 1)),
                False,
            )
        )
        propositions.append(
            (
                (nom, gauche, droite, bas, haut - 1),
                (slice(gauche, droite), slice(haut - 1, haut)),
                False,
            )
        )
    return propositions


def _reparer_partition(
    incidences: list[tuple[str, int, int, int, int]],
    dedans: np.ndarray,
    budget: int,
) -> list[tuple[str, int, int, int, int]] | None:
    """Corriger une partition a quelques cellules pres, en indices seulement.

    Apres consolidation il subsiste des defauts **locaux** : une cellule non
    couverte, ou couverte deux fois. Mesure sur MSD, c'est le cas dominant --
    127 jours et 115 chevauchements d'exactement une cellule sur 1 200 corruptions.

    On les resorbe en agrandissant ou retrecissant une piece **d'un cran**, ce qui
    la laisse rectangulaire par construction : seuls les indices bougent, jamais
    une coordonnee. Une extension n'est retenue que si **toutes** les cellules
    qu'elle gagne sont manquantes ; une reduction, que si toutes celles qu'elle
    libere sont en exces. Aucune structure n'est donc inventee : on rend a une
    piece ce qu'une faute lui avait pris, ou on lui retire ce qu'elle avait pris.

    Parameters
    ----------
    incidences : list of (str, int, int, int, int)
        Incidences courantes, eventuellement fautives.
    dedans : numpy.ndarray of bool
        Masque des cellules interieures au contour.
    budget : int
        Nombre maximal de retouches. Le borner distingue une **reparation** d'une
        reconstruction : au-dela, la faute n'est plus une cote fausse mais une
        incoherence d'ordre, et il faut refuser plutot que deviner.

    Returns
    -------
    list or None
        Incidences reparees, ou ``None`` si le budget est epuise avant partition.
    """
    forme = (int(dedans.shape[0]), int(dedans.shape[1]))
    incidences = list(incidences)
    for _ in range(budget):
        grille = _couverture(incidences, forme)
        manquantes = dedans & (grille < 1)
        excedents = (dedans & (grille > 1)) | (~dedans & (grille > 0))
        if not manquantes.any() and not excedents.any():
            return incidences
        meilleure: tuple[int, tuple[str, int, int, int, int], int] | None = None
        for rang, incidence in enumerate(incidences):
            for propose, cellules, extension in _retouches(incidence, forme):
                vise = manquantes if extension else excedents
                zone = vise[cellules]
                if zone.size and bool(zone.all()):
                    gain = int(zone.size)
                    if meilleure is None or gain > meilleure[2]:
                        meilleure = (rang, propose, gain)
        if meilleure is None:
            return None
        rang, propose, _ = meilleure
        incidences[rang] = propose
    grille = _couverture(incidences, forme)
    reste = bool((dedans & (grille != 1)).any() or (~dedans & (grille > 0)).any())
    return None if reste else incidences


def deduire_trame(
    plan: Plan,
    ctx: Contexte,
    *,
    tolerance: float = 0.01,
    support_min: int = 2,
    budget_reparation: int = 4,
) -> Trame:
    """Récupérer la trame du plan proposé et **prouver** qu'elle pave le contour.

    Parameters
    ----------
    plan : Plan
        Plan proposé, éventuellement invalide. Ses bords fixent les incidences.
    ctx : Contexte
        Le contour sert de bord extérieur : la première et la dernière ligne de
        chaque axe doivent y coïncider, sinon l'union ne couvre pas l'enveloppe.
    tolerance : float, optional
        Regroupement **numérique** seulement : deux bords distants de moins que ce
        seuil sont la même ligne. Défaut 1 cm. Ce n'est pas le levier de
        récupération — voir ``support_min``.
    support_min : int, optional
        Une ligne intérieure portée par moins de ``support_min`` bords est
        **orpheline** : elle est résorbée dans sa voisine la plus proche, sauf si
        cela écrase une pièce. C'est ainsi que la structure voulue se récupère,
        sans deviner de tolérance métrique. Défaut 2 : un mur intérieur sépare
        deux pièces, donc porte au moins deux bords. ``support_min=1`` désactive
        la consolidation.

    Returns
    -------
    Trame
        Structure vérifiée : les cellules couvertes forment une partition.

    Raises
    ------
    GridNotRecoverable
        The cells do not form a partition: an empty cell (structural gap) or a cell
        covered twice (structural overlap). The fault is then not a coordinate
        offset but the order itself, and no partition move will repair it.
    InvariantViole
        Empty plan, room degenerate after grouping, non-rectangular outline, or grid
        not covering the outline (to be reclassified as input limits, PLAN.md
        phase 3).

    Notes
    -----
    Complexité : ``O(n log n)`` pour le regroupement, ``O(Σ cellules)`` pour la
    vérification de partition, soit ``O(n·p·q)`` au pire.
    """
    if not plan.pieces:
        raise InvariantViole(("plan sans piece : aucune trame",))
    if not ctx.contour:
        raise InvariantViole(("contour vide : trame non ancrable",))

    xs = [p.x for p in plan.pieces] + [p.x + p.w for p in plan.pieces]
    ys = [p.y for p in plan.pieces] + [p.y + p.h for p in plan.pieces]
    xs_contour = [point[0] for point in ctx.contour]
    ys_contour = [point[1] for point in ctx.contour]
    # Toutes les coordonnees du contour entrent dans la trame, pas seulement les
    # extremes : sur un contour rectilineaire, chaque cellule doit etre entierement
    # dedans ou entierement dehors, sinon le masque ci-dessous n'a pas de sens.
    lignes_x, rang_x = _regrouper([*xs, *xs_contour], tolerance)
    lignes_y, rang_y = _regrouper([*ys, *ys_contour], tolerance)
    # A line that carries an outline vertex *is* the outline: the group mean would
    # drift with the room edges grouped with it, and the anchoring equalities would
    # then pin the rooms off the outline, leaving an uncovered strip.
    for valeur in xs_contour:
        lignes_x[rang_x[valeur]] = valeur
    for valeur in ys_contour:
        lignes_y[rang_y[valeur]] = valeur
    if len(lignes_x) < 2 or len(lignes_y) < 2:
        raise InvariantViole(("trame degeneree : moins de deux lignes sur un axe",))

    bords_x = [(rang_x[p.x], rang_x[p.x + p.w]) for p in plan.pieces]
    bords_y = [(rang_y[p.y], rang_y[p.y + p.h]) for p in plan.pieces]
    for (gauche, droite), piece in zip(bords_x, plan.pieces, strict=True):
        if gauche >= droite:
            raise InvariantViole((f"piece {piece.id} plate en x",))
    for (bas, haut), piece in zip(bords_y, plan.pieces, strict=True):
        if bas >= haut:
            raise InvariantViole((f"piece {piece.id} plate en y",))

    # Les lignes qui portent un sommet du contour sont figees : l'enveloppe est une
    # donnee d'entree, elle ne bouge pas. Elles echappent donc a la consolidation.
    ancrees_x = {rang_x[v] for v in xs_contour}
    ancrees_y = {rang_y[v] for v in ys_contour}

    if support_min > 1:
        lignes_x, bords_x, ancrees_x = _consolider(lignes_x, bords_x, ancrees_x, support_min)
        lignes_y, bords_y, ancrees_y = _consolider(lignes_y, bords_y, ancrees_y, support_min)

    incidences = [
        (piece.id, gauche, droite, bas, haut)
        for piece, (gauche, droite), (bas, haut) in zip(plan.pieces, bords_x, bords_y, strict=True)
    ]

    # Partition : chaque cellule **interieure au contour** couverte exactement une
    # fois, et aucune cellule exterieure couverte. Le contour reel est rectilineaire,
    # pas rectangulaire : exiger le pavage de la boite englobante serait faux.
    enveloppe = Polygon(ctx.contour)
    if not enveloppe.is_valid:
        raise InvariantViole(("contour invalide : pavage non verifiable",))
    centres_x = 0.5 * (np.asarray(lignes_x[:-1]) + np.asarray(lignes_x[1:]))
    centres_y = 0.5 * (np.asarray(lignes_y[:-1]) + np.asarray(lignes_y[1:]))
    maille_x, maille_y = np.meshgrid(centres_x, centres_y, indexing="ij")
    dedans = np.asarray(contains_xy(enveloppe, maille_x, maille_y))
    forme = (len(lignes_x) - 1, len(lignes_y) - 1)
    grille = _couverture(incidences, forme)
    trop = int(np.sum(grille[dedans] > 1) + np.sum(grille[~dedans] > 0))
    manque = int(np.sum(grille[dedans] < 1))
    if trop or manque:
        # Defaut local de quelques cellules : tenter une retouche d'indices bornee
        # avant de refuser. Au-dela du budget, ce n'est plus une cote fausse.
        repare = (
            _reparer_partition(incidences, dedans, budget_reparation)
            if budget_reparation > 0
            else None
        )
        if repare is None:
            raise GridNotRecoverable(excess=trop, missing=manque)
        incidences = repare

    # Dernier filet : la reparation comme la consolidation ne manipulent que des
    # indices, et une piece aux bords inverses passerait silencieusement en LP.
    for nom, gauche, droite, bas, haut in incidences:
        if gauche >= droite or bas >= haut:
            raise InvariantViole((f"piece {nom} degeneree dans la trame",))

    return Trame(
        lignes_x=tuple(lignes_x),
        lignes_y=tuple(lignes_y),
        incidences=tuple(incidences),
        ancrees_x=frozenset(ancrees_x),
        ancrees_y=frozenset(ancrees_y),
    )


def snap_to_grid(plan: Plan, trame: Trame) -> Plan:
    """Place every room of ``plan`` on the reference lines of its recovered grid.

    The result is an exact tiling of the outline (the partition of ``trame`` is
    verified), so every pair of rooms is separated on the axis the grid says. Reading
    the relative order from it rather than from the faulty plan keeps the order
    consistent with the tiling equalities: a room moved onto its neighbour overlaps it
    on both axes, and the centres alone may then pick the wrong axis.

    Parameters
    ----------
    plan : Plan
        The proposed plan ``trame`` was recovered from.
    trame : Trame
        Grid returned by :func:`deduire_trame` for ``plan``.

    Returns
    -------
    Plan
        New plan, rooms in the same order, only their coordinates changed.
    """
    lignes = {
        nom: (gauche, droite, bas, haut) for nom, gauche, droite, bas, haut in trame.incidences
    }
    pieces = []
    for piece in plan.pieces:
        gauche, droite, bas, haut = lignes[piece.id]
        x, y = trame.lignes_x[gauche], trame.lignes_y[bas]
        pieces.append(
            replace(piece, x=x, y=y, w=trame.lignes_x[droite] - x, h=trame.lignes_y[haut] - y)
        )
    return replace(plan, pieces=tuple(pieces))


def contraintes_pavage(
    trame: Trame, index: dict[str, int]
) -> tuple[tuple[str, dict[str, float], float], ...]:
    """Traduire la trame en égalités affines ``Σ a_k v_k = b``.

    Deux familles, et rien d'autre :

    - **partage de ligne** — deux bords sur la même ligne sont égaux. Le premier
      bord rencontré sert de référence, les suivants s'y rattachent : ``m`` bords
      sur une ligne donnent ``m − 1`` égalités, jamais ``m(m−1)/2``.
    - **ancrage** — les bords portés par la première et la dernière ligne d'un axe
      sont fixés sur le contour. Sans eux la trame entière pourrait glisser, ou se
      contracter à l'intérieur de l'enveloppe.

    Returns
    -------
    tuple
        Triplets ``(libelle, termes, second_membre)``, mêmes conventions que
        :func:`~archlux.geom.rectilineaire.contraintes_fusion`.

    Raises
    ------
    InvariantViole
        Une variable attendue manque à ``index``.
    """
    egalites: list[tuple[str, dict[str, float], float]] = []
    # Un bord est decrit par les termes qui l'expriment : bord gauche = x,
    # bord droit = x + w. Meme chose en y.
    bords_x: dict[int, list[tuple[str, dict[str, float]]]] = {}
    bords_y: dict[int, list[tuple[str, dict[str, float]]]] = {}
    for piece_id, gauche, droite, bas, haut in trame.incidences:
        for nom in (f"{piece_id}.x", f"{piece_id}.w", f"{piece_id}.y", f"{piece_id}.h"):
            if nom not in index:
                raise InvariantViole((f"variable absente de l'index : {nom}",))
        bords_x.setdefault(gauche, []).append((piece_id, {f"{piece_id}.x": 1.0}))
        bords_x.setdefault(droite, []).append(
            (piece_id, {f"{piece_id}.x": 1.0, f"{piece_id}.w": 1.0})
        )
        bords_y.setdefault(bas, []).append((piece_id, {f"{piece_id}.y": 1.0}))
        bords_y.setdefault(haut, []).append(
            (piece_id, {f"{piece_id}.y": 1.0, f"{piece_id}.h": 1.0})
        )

    for axe, bords, lignes, ancrees in (
        ("x", bords_x, trame.lignes_x, trame.ancrees_x),
        ("y", bords_y, trame.lignes_y, trame.ancrees_y),
    ):
        for ligne, membres in sorted(bords.items()):
            if ligne in ancrees:
                # Ancrage : chaque bord de la ligne est fixe sur le contour.
                cible = lignes[ligne]
                for piece_id, termes in membres:
                    egalites.append((f"contour {axe}={cible:.4f} {piece_id}", dict(termes), cible))
                continue
            reference_id, reference = membres[0]
            for piece_id, termes in membres[1:]:
                combines = dict(reference)
                for nom, coef in termes.items():
                    combines[nom] = combines.get(nom, 0.0) - coef
                combines = {n: c for n, c in combines.items() if abs(c) > _EPS}
                if not combines:
                    continue
                egalites.append(
                    (
                        f"trame {axe}#{ligne} {reference_id}|{piece_id}",
                        combines,
                        0.0,
                    )
                )
    return tuple(egalites)


def etendre_pavage(poly: Polytope, trame: Trame) -> Polytope:
    """Ajouter les égalités de pavage au polytope (``A_eq``, ``b_eq``).

    Parameters
    ----------
    poly : Polytope
        Système déjà assemblé pour les pièces de ``trame``.
    trame : Trame
        Structure vérifiée par :func:`deduire_trame`.

    Returns
    -------
    Polytope
        Nouvelle instance. ``origines`` est inchangé : ce sont des égalités, pas
        des inégalités dualisées — elles n'apparaissent donc **pas** dans le
        diagnostic dual du certificat.
    """
    egalites = contraintes_pavage(trame, poly.index)
    if not egalites:
        return poly
    n_var = len(poly.index)
    lignes: list[int] = []
    colonnes: list[int] = []
    valeurs: list[float] = []
    seconds: list[float] = []
    labels: list[str] = []
    for rang, (libelle, termes, borne) in enumerate(egalites):
        for nom, coef in termes.items():
            lignes.append(rang)
            colonnes.append(poly.index[nom])
            valeurs.append(coef)
        seconds.append(borne)
        labels.append(f"tiling {libelle}")
    a_extra = sparse.coo_matrix((valeurs, (lignes, colonnes)), shape=(len(egalites), n_var)).tocsr()
    if poly.A_eq.shape[0]:
        a_eq = sparse.vstack([poly.A_eq, a_extra], format="csr")
        b_eq = np.concatenate([poly.b_eq, np.asarray(seconds, dtype=float)])
    else:
        a_eq = a_extra
        b_eq = np.asarray(seconds, dtype=float)
    return replace(poly, A_eq=a_eq, b_eq=b_eq, origines_eq=poly.labels_eq() + tuple(labels))
