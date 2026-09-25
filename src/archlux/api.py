r"""Interface publique : une seule fonction, un paramètre qui change tout.

``objective=None`` donne la légalisation classique ; un ``Substitut`` donne la
légalisation performantielle. **Une fonction, un paramètre.**

Pipeline classique
------------------
1. Déduire l'ordre (le générateur décide l'ordre).
2. Construire le polytope (séparations linéaires).
3. Étendre par l'épigraphe L1 (Bertsimas–Tsitsiklis §1.3).
4. Minimiser :math:`\\sum e_i` sous coupes de surface (Kelley / AM-GM).
5. Dévectoriser, revérifier **indépendamment**, attacher le certificat.

Chaîne complète, hypothèses et contre-indications : ``docs/formules/pipeline.md``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from archlux.certify.borne import bound_selected_plan, check_calibration
from archlux.certify.dual import traduire_duaux
from archlux.certify.farkas import verify_infeasibility
from archlux.certify.proof import verify_exactly
from archlux.erreurs import Infaisable, InvariantViole
from archlux.geom.graphe import OrdreRelatif, deduire_ordre
from archlux.geom.pavage import deduire_trame, etendre_pavage, snap_to_grid
from archlux.geom.polytope import (
    Polytope,
    construire_polytope,
    devectoriser,
    etendre_ecarts_l1,
    figer_contacts,
    vectoriser,
)
from archlux.geom.rectilineaire import (
    PieceRectilineaire,
    etendre_fusions,
    minimum_area_shares,
)
from archlux.light.protocole import Baies, Substitut, point_prediction
from archlux.lmo.coupes import inner_area_constraints, resoudre_avec_surfaces
from archlux.lmo.solveur import SolutionLP
from archlux.solve.frank_wolfe import frank_wolfe, restrict_to_budget
from archlux.types import Certificat, Contexte, Plan

if TYPE_CHECKING:
    from archlux.certify.borne import Calibration

__all__ = ["gradient_distance", "legalize"]

_DUAL_SEUIL = 1e-9


def gradient_distance(x_propose: np.ndarray) -> np.ndarray:
    r"""Vecteur de coûts de l'épigraphe L1 : zéros sur :math:`x`, uns sur :math:`e`.

    .. math::

        c = (0,\\ldots,0, 1,\\ldots,1) \\in \\mathbb{R}^{2n},
        \\qquad \\min\\, c^\\top (x,e) = \\min \\sum_i e_i.

    ``x_propose`` fixe uniquement la dimension :math:`n` ; les :math:`\\hat{x}_i`
    entrent dans les contraintes d':func:`etendre_ecarts_l1`, pas dans ``c``.

    Parameters
    ----------
    x_propose : numpy.ndarray
        Plan proposé, vectorisé, dimension n.

    Returns
    -------
    numpy.ndarray
        Vecteur ``c`` de dimension ``2n``.

    Notes
    -----
    Épigraphe : ``docs/formules/epigraphe-l1.md``.
    """
    n_var = int(x_propose.shape[0])
    couts = np.zeros(2 * n_var, dtype=float)
    couts[n_var:] = 1.0
    return couts


def _origines_actives(sol: SolutionLP, poly: Polytope) -> tuple[str, ...]:
    """Labels of the rows, inequalities and equalities, with a non-zero Farkas weight.

    Without a certificate nothing is identified; listing every constraint, as before
    batch 1.5c, wrongly presented all of them as conflicting.
    """
    labels: list[str] = []
    if sol.certificat_farkas is not None:
        labels += [
            label
            for label, weight in zip(poly.origines, sol.certificat_farkas, strict=True)
            if abs(float(weight)) > _DUAL_SEUIL
        ]
    if sol.certificat_farkas_eq is not None:
        labels += [
            label
            for label, weight in zip(poly.labels_eq(), sol.certificat_farkas_eq, strict=True)
            if abs(float(weight)) > _DUAL_SEUIL
        ]
    return tuple(labels)


def _duaux_traduits(duaux: np.ndarray | None, poly: Polytope) -> tuple[tuple[str, float], ...]:
    """Apparier les duaux des lignes de ``A`` avec ``poly.origines``.

    ``duaux`` doit provenir d'un LP résolu sur **ce** polytope : l'appariement est
    positionnel, et ``origines`` ne couvre que ``A``, jamais ``A_eq`` ni les coupes.
    """
    if duaux is None:
        return ()
    return traduire_duaux(duaux, poly, seuil=_DUAL_SEUIL)


GRID_LABEL = "tiling grid"
"""Scope entry of the tiling equalities (``pavage=True``)."""


def budget_label(budget: float) -> str:
    """Scope entry of the displacement budget."""
    return f"budget {budget:g} m"


def _scope(
    ordre: OrdreRelatif,
    fusions: tuple[PieceRectilineaire, ...],
    grid: bool,
    budget: float | None,
) -> tuple[str, ...]:
    """Restrictions of the solver's domain beyond the relative order, as built."""
    scope: list[str] = []
    if ordre.wall_sides:
        scope.append("load-bearing sides")
    if fusions:
        scope.append("fused-room seams and area shares")
    if ordre.shared_sides:
        scope.append("one shared side per fused room straddling a wall")
    if grid:
        scope.append(GRID_LABEL)
    if budget is not None:
        scope.append(budget_label(budget))
    return tuple(scope)


def legalize(
    plan: Plan,
    ctx: Contexte,
    *,
    objective: Substitut | None = None,
    calibration: Calibration | None = None,
    budget: float | None = None,
    trace: bool = False,
    fusions: tuple[PieceRectilineaire, ...] = (),
    pavage: bool = False,
    budget_reparation: int = 4,
) -> Plan:
    """Corriger un plan vers le plan valide le plus proche, ou le plus performant.

    Avec ``objective=None``, minimise le déplacement L1 des variables de décision.
    Un ``Substitut`` enchaîne Frank-Wolfe depuis ce point, sans sortir du polytope.

    Parameters
    ----------
    plan : Plan
        Plan proposé, éventuellement invalide. Une pièce en L doit déjà être
        décomposée en sous-rectangles (:func:`~archlux.geom.rectilineaire.decomposer`).
    ctx : Contexte
        Structure porteuse, orientation, contour, référentiel.
    objective : Substitut or None, optional
        Objectif à maximiser. ``None`` = proximité géométrique.
    calibration : Calibration or None, optional
        Conformal calibration of ``objective`` (same indicator, scores normalized by
        ``σ``). With it, ``certificat.performance`` holds the conformal interval of the
        returned plan, labelled ``regime="selected"``: the optimizer chose the plan, so
        the nominal coverage is **not** guaranteed and the report says so. Requires
        ``objective``.
    budget : float or None, optional
        Maximum L-infinity displacement from the proposed plan, in metres, over the
        whole legalization (classic pass and Frank-Wolfe share it), checked by the proof.
        A budget too small for the plan raises ``Infaisable``.
    trace : bool, optional
        Si vrai, attache la trace Frank-Wolfe à ``resultat.trace`` (non sérialisée).
    fusions : tuple of PieceRectilineaire, optional
        Fused rooms (L, T, U, Z) decomposed into sub-rectangles. Their shared edges
        become equalities of ``A_eq``; on the orthogonal axis, the order of the
        sub-rectangle ends is kept and every shared edge keeps at least
        ``referentiel.largeur_min`` of length, so an L cannot turn into a Z or split
        (:func:`~archlux.geom.rectilineaire.overlap_constraints`).
    pavage : bool, optional
        Imposer que l'union des pièces **pave exactement** le contour. Sans cela,
        les séparations du polytope étant des inégalités, un plan troué reste le
        point le plus proche de lui-même : l'optimum L1 le laisse tel quel et la
        vérification exacte le rejette. Avec, un jour cesse d'être représentable.

        À activer dès que l'entrée peut porter un **jour** — c'est le cas des
        sorties de modèles génératifs. Mesuré sur 4 796 corruptions de 300 plans
        MSD réels (`resultats/j7_reparation.md`) : la réparation passe de 35,9 %
        à 93,0 %, et sur les jours seuls de 10,0 % à 97,6 % (colonne ``pavage=True`` ;
        les 93,9 % du README sont la colonne « repli » : ``pavage=True``, sinon
        ``legalize`` seul). Chiffres mesurés avant le lot 1.1.

        Exige que la trame du plan proposé soit récupérable
        (:func:`~archlux.geom.pavage.deduire_trame`) ; sinon ``GridNotRecoverable``
        nomme les cellules fautives. Défaut ``False`` : contrat 1.x inchangé.
        With a grid, the relative order and the load-bearing sides are read from
        the plan snapped onto it (:func:`~archlux.geom.pavage.snap_to_grid`), so
        that they never contradict the tiling equalities.
    budget_reparation : int, optional
        Nombre de crans de réparation accordés à la récupération de trame, passé
        tel quel à :func:`~archlux.geom.pavage.deduire_trame`. Sans effet si
        ``pavage`` est faux.

        Le défaut ``4`` est calé sur des plans **corrompus**, où la faute est une
        cote fausse et se résorbe en un ou deux crans. Une sortie de modèle
        génératif relève d'un autre régime : ses pièces ne partagent aucune ligne,
        la trame compte des dizaines de cellules et le budget devient le facteur
        limitant. ``0`` interdit toute réparation et n'accepte qu'une trame déjà
        cohérente ; un appelant qui doit préserver le programme pièce par pièce
        s'en sert pour refuser plutôt que d'absorber une pièce dans sa voisine.

    Returns
    -------
    Plan
        Plan valide portant son ``certificat``.

    Raises
    ------
    OrdreIncoherent, SeparationManquante
        Propagées depuis la construction du graphe.
    UnsupportedInput
        An oblique load-bearing wall: it cannot be kept by a linear side constraint.
        With ``pavage``, also an input the grid cannot describe (no room, empty or
        invalid outline, flat room, outline edges closer than the grouping tolerance).
    GridNotRecoverable
        With ``pavage``: the rooms do not fall into the cells of the recovered grid
        (an input limit, subclass of ``UnsupportedInput``).
    Infaisable
        The program does not fit the envelope for this relative order. The exception
        carries ``origines`` and, when the conflict is attributable to rows of ``A`` or
        ``A_eq``, ``certificat_farkas`` with its exact verification (``verified``).
        Raised before the LP if ``largeur_min`` already exceeds the envelope.
    InvariantViole
        Sortie du solveur rejetée par la vérification exacte, ou statut LP inattendu.
        Le cas le plus fréquent est une surface minimale encore violée après épuisement
        des coupes de Kelley : le LP se dit « optimal », la vérification exacte non.
    TypeError
        ``objective`` fourni n'implémente pas :class:`~archlux.light.protocole.Substitut`.
    ValueError
        ``calibration`` without ``objective``, or calibrated for another indicator.
        A calibration unable to give a finite bound (too small for its ``alpha``,
        non-finite scores) raises ``InvariantViole``, before any solving.

    Guarantees
    ----------
    - Géométrique : **exacte**. ``resultat.certificat.geometrie.valide`` est
      revérifié par :func:`archlux.certify.proof.verify_exactly` avant
      retour — le solveur n'est jamais cru sur parole.
    - Performance: **none** in classic mode (``objective is None``), nor with a
      surrogate but no ``calibration`` (``performance`` is then ``None``). With both, a
      conformal interval in the **selected** regime: nominal coverage stated, not
      guaranteed, because the optimizer chose the plan (AUDIT.md §5.3).

    Complexity
    ----------
    Mode classique : un LP par itération de Kelley, au plus
    ``MAX_COUPES_PAR_PIECE`` par pièce, < 20 ms pour 15 pièces.
    Mode performantiel : jusqu'à 50 LP à chaud, < 500 ms
    (`ARCHITECTURE.md` §9).
    A refusal costs up to three times the classic mode: the tiling grid and the budget
    are each dropped once, solved and proved, to fill ``Infaisable.relaxable``. No §9
    budget covers refusals.

    Notes
    -----
    Pipeline et sources : ``docs/formules/pipeline.md``.

    Examples
    --------
    >>> from archlux.types import (
    ...     Contexte, Orientation, Piece, Plan, Referentiel, Structure,
    ... )
    >>> plan = Plan(
    ...     pieces=(
    ...         Piece(id="a", type="sejour", x=0.0, y=0.0, w=6.0, h=9.0),
    ...         Piece(id="b", type="sejour", x=6.0, y=0.0, w=6.0, h=9.0),
    ...     ),
    ...     murs=(),
    ...     ouvertures=(),
    ...     contour=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    ... )
    >>> ctx = Contexte(
    ...     structure=Structure(murs_porteurs=()),
    ...     orientation=Orientation(deg=0.0),
    ...     contour=plan.contour,
    ...     referentiel=Referentiel(aires_min=(), largeur_min=1.0),
    ... )
    >>> q = legalize(plan, ctx)
    >>> q.certificat.geometrie.valide
    True
    """
    if objective is not None and not isinstance(objective, Substitut):
        raise TypeError("objective doit implémenter archlux.light.protocole.Substitut")
    if calibration is not None:
        if objective is None:
            raise ValueError(
                "calibration requires an objective: classic mode claims no performance"
            )
        check_calibration(calibration)
        if calibration.indicateur != objective.indicateur:
            raise ValueError(
                f"calibration of {calibration.indicateur!r} cannot bound {objective.indicateur!r}"
            )

    # Rend un jour non representable : voir ``geom.pavage``. Leve si la trame
    # du plan propose n'est pas recuperable — echec explicite, pas silencieux.
    trame = deduire_trame(plan, ctx, budget_reparation=budget_reparation) if pavage else None
    # With a grid, the order is read from the plan snapped onto it: the order read from
    # the faulty plan could contradict the tiling equalities (a room moved onto its
    # neighbour overlaps it on both axes).
    ordre = deduire_ordre(
        plan if trame is None else snap_to_grid(plan, trame),
        structure=ctx.structure,
        # A fused room keeps one side of every wall: never a wall on its seam.
        groups=tuple(tuple(r.id for r in piece_l.rectangles) for piece_l in fusions),
    )
    base = construire_polytope(ordre, ctx)
    for piece_l in fusions:
        base = etendre_fusions(base, piece_l, min_contact=ctx.referentiel.largeur_min)
    x_ref = vectoriser(plan, base.index)
    minima = minimum_area_shares(plan.pieces, fusions, ctx.referentiel)

    def domain(*, grid: bool = True, bounded: bool = True) -> tuple[Polytope, Polytope]:
        """The solver's domain, optionally without the tiling grid or the budget."""
        geometric = etendre_pavage(base, trame) if grid and trame is not None else base
        l1 = etendre_ecarts_l1(geometric, x_ref)
        if bounded and budget is not None:
            n_geo = len(geometric.index)
            bornes = tuple(l1.bornes[:n_geo]) + tuple((0.0, float(budget)) for _ in range(n_geo))
            l1 = replace(l1, bornes=bornes)
        return geometric, l1

    def solve(l1: Polytope) -> SolutionLP:
        return resoudre_avec_surfaces(
            l1, gradient_distance(x_ref), ctx, plan.pieces, duaux=True, minima=minima
        )

    poly, poly_l1 = domain()
    sol = solve(poly_l1)
    if sol.statut == "infaisable":
        check = (
            verify_infeasibility(poly_l1, sol.certificat_farkas, sol.certificat_farkas_eq)
            if sol.certificat_farkas is not None
            else None
        )
        # The certificate is about this domain, not about the order alone (final review
        # of phase 1, C1): name every restriction, and test the ones legalize added.
        scope = _scope(ordre, fusions, trame is not None, budget)

        def admits(l1: Polytope, *, bounded: bool) -> bool:
            """The relaxed optimum is a plan the exact proof accepts, as returned.

            An ``"optimal"`` LP is not enough: without the grid the L1 optimum keeps a
            gap, and the area cuts are an outer approximation (final review, M1).
            """
            relaxed = solve(l1)
            if relaxed.statut != "optimal":
                return False
            candidate = replace(devectoriser(relaxed.x, plan, l1.index), contour=ctx.contour)
            return verify_exactly(
                candidate,
                ctx,
                reference=plan,
                budget=budget if bounded else None,
                fusions=fusions,
            ).valide

        relaxable: list[str] = []
        if trame is not None and admits(domain(grid=False)[1], bounded=True):
            relaxable.append(GRID_LABEL)
        if budget is not None and admits(domain(bounded=False)[1], bounded=False):
            relaxable.append(budget_label(budget))
        raise Infaisable(
            certificat_farkas=sol.certificat_farkas,
            origines=_origines_actives(sol, poly_l1),
            verified=None if check is None else check.verified,
            scope=scope,
            relaxable=tuple(relaxable),
        )
    if sol.statut != "optimal":
        raise InvariantViole((f"statut LP inattendu : {sol.statut}",))

    corrige = replace(
        devectoriser(sol.x, plan, poly_l1.index),
        contour=ctx.contour,
    )
    preuve = verify_exactly(corrige, ctx, reference=plan, budget=budget, fusions=fusions)
    if not preuve.valide:
        raise InvariantViole(preuve.violations)
    # sol a été résolu sur poly_l1 : les duaux alignent poly_l1.A / origines, pas poly.
    duaux = _duaux_traduits(sol.duaux, poly_l1)
    if objective is None:
        return replace(
            corrige,
            certificat=Certificat(geometrie=preuve, performance=None, duaux=duaux),
        )

    x0 = vectoriser(corrige, poly.index)
    # Inner approximation of the minimum areas, added *after* freezing contacts so that
    # a tight room is not frozen into an equality: every point of this domain, hence
    # every Frank-Wolfe iterate, keeps every minimum area (PLAN.md batch 1.2).
    poly_fw = inner_area_constraints(
        figer_contacts(poly, x0),
        x0,
        ctx,
        corrige.pieces,
        minima=minimum_area_shares(corrige.pieces, fusions, ctx.referentiel),
    )
    if budget is not None:
        # Centred on the *proposed* plan, not on x0: the budget is spent once over the
        # whole legalization (AUDIT.md §5.8 measured up to twice the budget).
        poly_fw = restrict_to_budget(poly_fw, x_ref, budget, keep=x0)
    # Glazing is not part of the decision vector: it is constant during the
    # optimization and passed through unchanged. Without it the surrogate only sees
    # rectangles and cannot predict real daylight (`docs/formules/jetons.md`).
    glazing = Baies(murs=corrige.murs, ouvertures=corrige.ouvertures)
    resultat = frank_wolfe(poly_fw, objective, ctx.orientation, x0, glazing=glazing)
    performant = replace(
        devectoriser(resultat.x, corrige, poly.index),
        contour=ctx.contour,
    )
    preuve_fw = verify_exactly(performant, ctx, reference=plan, budget=budget, fusions=fusions)
    if not preuve_fw.valide:
        raise InvariantViole(preuve_fw.violations)
    # Le dernier LP de Frank-Wolfe porte sur poly_fw, pas sur poly_l1 : ses duaux sont
    # les seuls appariables avec poly_fw.origines. À défaut, on garde ceux de la passe
    # L1 — ils décrivent un autre polytope, mais sont au moins étiquetés correctement.
    # Attention : figer_contacts a déplacé les lignes saturées dans A_eq, qui n'est pas
    # dualisée ; ce diagnostic est donc souvent vide (voir lmo.solveur.resoudre).
    duaux_fw = duaux
    if resultat.duals is not None:
        duaux_fw = _duaux_traduits(resultat.duals, poly_fw)
    performance = None
    if calibration is not None:
        # Centred on the prediction mu, not on the pessimistic objective mu - q sigma.
        mu, sigma = point_prediction(objective, resultat.x, ctx.orientation, baies=glazing)
        performance = bound_selected_plan(mu, calibration, uncertainty=sigma)
    return replace(
        performant,
        certificat=Certificat(geometrie=preuve_fw, performance=performance, duaux=duaux_fw),
        trace=resultat.trace if trace else None,
    )
