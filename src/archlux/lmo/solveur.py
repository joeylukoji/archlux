"""Oracle linéaire : résoudre ``min <c, x>`` sur le polytope.

**Ce module ne sait pas d'où vient ``c``.** Cette ignorance est délibérée et constitue
le cœur de l'architecture : le même solveur sert à la légalisation classique (``c`` =
gradient de distance) et à la légalisation performantielle (``c`` = −gradient
d'éclairement), sans une ligne de différence. Faire connaître la lumière à ``lmo`` casse
cette réutilisation (`ARCHITECTURE.md` §10).

Dépendances autorisées : ``types``, ``erreurs``, ``geom``. **Jamais ``light``.**

Dualité, phase I et Farkas : ``docs/formules/farkas.md``.
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from ortools.linear_solver import pywraplp

from archlux.erreurs import InvariantViole

if TYPE_CHECKING:
    from archlux.geom.polytope import Polytope
    from archlux.lmo.coupes import Coupe

__all__ = ["SolutionLP", "resoudre", "vider_cache"]

_TAILLE_CACHE = 4
"""Nombre de modèles conservés pour le démarrage à chaud.

Une boucle de Frank-Wolfe travaille sur **un** polytope ; quatre suffit largement, et
borne l'empreinte mémoire de ce cache.
"""

_CACHE: OrderedDict[int, tuple[Polytope, Any, list[Any], list[Any]]] = OrderedDict()
"""Modèles GLOP déjà construits, indexés par ``id`` du polytope.

Le polytope est conservé **par référence forte** dans la valeur : tant qu'il est là, son
``id`` ne peut pas être réattribué à un autre objet, et la clé reste correcte.

Ce cache ne change aucun résultat, seulement le temps : mêmes entrées, même solution.
La pureté que `ARCHITECTURE.md` §3 exige de ``lmo`` — déterminisme, rien d'appris — est
préservée, et un test de propriété le vérifie à chaque exécution.
"""


@dataclass(frozen=True, slots=True)
class SolutionLP:
    """Résultat d'un appel à l'oracle.

    Attributes
    ----------
    statut : {"optimal", "infaisable", "non_borne", "limite"}
        Jamais un booléen : « pas optimal » recouvre trois situations qui appellent
        trois réactions différentes.
    duaux : numpy.ndarray or None
        Prix duaux, renseignés seulement si ``duaux=True``. Traduits en langage métier
        par :mod:`archlux.certify.dual` via ``Polytope.origines``.
    certificat_farkas : numpy.ndarray or None
        Preuve d'infaisabilité, renseignée seulement si ``statut == "infaisable"``.
    """

    x: np.ndarray
    valeur: float
    statut: Literal["optimal", "infaisable", "non_borne", "limite"]
    duaux: np.ndarray | None = None
    certificat_farkas: np.ndarray | None = None
    iterations: int = 0
    temps_ms: float = 0.0


def vider_cache() -> None:
    """Oublier les modèles conservés pour le démarrage à chaud.

    Utile aux mesures de performance, qui doivent pouvoir garantir un départ à froid.
    """
    _CACHE.clear()


def _statut(code: int) -> Literal["optimal", "infaisable", "non_borne", "limite"]:
    """Traduire le code de retour d'OR-Tools en statut du projet.

    Attention : **GLOP rend ``INFEASIBLE`` pour un problème non borné**, confondant deux
    situations opposées — « le programme ne tient pas dans l'enveloppe » et « l'objectif
    n'a pas d'optimum fini ». Le statut rendu ici est donc provisoire : c'est
    :func:`_est_faisable` qui tranche.
    """
    if code == pywraplp.Solver.OPTIMAL:
        return "optimal"
    if code == pywraplp.Solver.INFEASIBLE:
        return "infaisable"
    if code == pywraplp.Solver.UNBOUNDED:
        return "non_borne"
    return "limite"


def _borne_glop(solveur: object, valeur: float, *, superieure: bool) -> float:
    """Traduire une borne Python (éventuellement infinie) en borne GLOP."""
    if math.isfinite(valeur):
        return float(valeur)
    infini = float(solveur.infinity())  # type: ignore[attr-defined]
    return infini if superieure else -infini


def _construire_modele(
    poly: Polytope, coupes: list[Coupe] | None
) -> tuple[Any, list[Any], list[Any]]:
    """Traduire un polytope en modèle GLOP.

    Returns
    -------
    tuple
        Le solveur, ses variables dans l'ordre des colonnes, et ses contraintes dans
        l'ordre des lignes de ``A`` — cet ordre est ce qui rend les duaux appariables
        avec ``origines``.
    """
    solveur = pywraplp.Solver.CreateSolver("GLOP")
    if solveur is None:  # pragma: no cover - dépend de l'installation d'OR-Tools
        raise InvariantViole(("backend GLOP indisponible",))

    noms = sorted(poly.index, key=lambda nom: poly.index[nom])
    variables = [
        solveur.NumVar(
            _borne_glop(solveur, poly.bornes[i][0], superieure=False),
            _borne_glop(solveur, poly.bornes[i][1], superieure=True),
            nom,
        )
        for i, nom in enumerate(noms)
    ]

    contraintes: list[Any] = []
    matrice = poly.A.tocsr()
    for ligne in range(matrice.shape[0]):
        debut, fin = matrice.indptr[ligne], matrice.indptr[ligne + 1]
        contrainte = solveur.RowConstraint(-solveur.infinity(), float(poly.b[ligne]))
        for colonne, valeur in zip(
            matrice.indices[debut:fin], matrice.data[debut:fin], strict=True
        ):
            contrainte.SetCoefficient(variables[colonne], float(valeur))
        contraintes.append(contrainte)

    egalites = poly.A_eq.tocsr()
    for ligne in range(egalites.shape[0]):
        debut, fin = egalites.indptr[ligne], egalites.indptr[ligne + 1]
        borne = float(poly.b_eq[ligne])
        contrainte = solveur.RowConstraint(borne, borne)
        for colonne, valeur in zip(
            egalites.indices[debut:fin], egalites.data[debut:fin], strict=True
        ):
            contrainte.SetCoefficient(variables[colonne], float(valeur))

    for coupe in coupes or ():
        # Une coupe s'écrit ``Σ coeffs·v ≥ borne_inf`` ; GLOP prend la borne telle quelle.
        contrainte = solveur.RowConstraint(coupe.borne_inf, solveur.infinity())
        for nom, coefficient in coupe.coeffs:
            contrainte.SetCoefficient(variables[poly.index[nom]], float(coefficient))

    return solveur, variables, contraintes


def _est_faisable(poly: Polytope, coupes: list[Coupe] | None) -> bool:
    """Dire si les contraintes admettent au moins un point, objectif mis de côté.

    **Le discriminant entre « infaisable » et « non borné »**, que GLOP rend sous le même
    code. Un LP à objectif nul ne peut pas être non borné : s'il trouve un point, l'échec
    du problème d'origine venait de son objectif, pas de son programme.

    Le modèle est identique à celui du problème réel — coupes, égalités et bornes
    comprises — de sorte que le verdict porte bien sur le même système.
    """
    solveur, _, _ = _construire_modele(poly, coupes)
    solveur.Objective().SetMinimization()
    return _statut(solveur.Solve()) == "optimal"


def _certificat_farkas(
    poly: Polytope, coupes: list[Coupe] | None
) -> np.ndarray:
    """Extraire une preuve d'infaisabilité par le **problème auxiliaire**.

    On relâche chaque inégalité ``a_i x ≤ b_i`` par une variable d'écart ``s_i ≥ 0``,
    puis on minimise ``Σ s_i``. Le problème auxiliaire est toujours faisable ; si son
    optimum est strictement positif, l'original ne l'est pas, et les prix duaux de ses
    contraintes forment un certificat de Farkas — des multiplicateurs positifs qui
    rendent le système contradictoire.

    Les coupes sont relâchées elles aussi. Sans cela, une coupe impossible rend le
    problème auxiliaire lui-même infaisable, et ses duaux ne veulent plus rien dire.

    Returns
    -------
    numpy.ndarray
        Un multiplicateur **positif** par ligne de ``A``. Croisé avec ``origines``, il
        dit **quelles contraintes s'excluent**, ce qu'un simple « infaisable » ne dit
        pas. Exemple réel : ``separation horizontale A|B`` et ``contour droit B`` valent
        1, les autres 0 — deux pièces de 2 m au minimum ne tiennent pas dans 3 m.

        **Vecteur nul** si le problème auxiliaire lui-même n'a pas d'optimum : seules
        les lignes de ``A`` sont relâchées, donc une infaisabilité venue des bornes ou
        de ``A_eq`` le rend insoluble et ses duaux ne veulent alors rien dire. Un
        certificat vide se lit « conflit non imputable à une ligne de ``A`` » ; un
        certificat faux, non.

    Notes
    -----
    OR-Tools rend les duaux d'une contrainte ``≤`` avec le signe opposé à la convention
    de Farkas. Les multiplicateurs sont donc négués ici pour être rendus sous la forme
    canonique ``y ≥ 0``, seule utilisable par :mod:`archlux.certify.dual` sans que chaque
    lecteur ait à connaître la convention interne du backend.
    """
    solveur, variables, contraintes = _construire_modele(poly, coupes)
    objectif = solveur.Objective()

    ecarts = [
        solveur.NumVar(0.0, solveur.infinity(), f"ecart_{i}")
        for i in range(len(contraintes))
    ]
    for contrainte, ecart in zip(contraintes, ecarts, strict=True):
        contrainte.SetCoefficient(ecart, -1.0)
        objectif.SetCoefficient(ecart, 1.0)

    # Les coupes sont relâchées dans l'autre sens : elles s'écrivent ``≥``.
    for rang, coupe in enumerate(coupes or ()):
        relache = solveur.NumVar(0.0, solveur.infinity(), f"ecart_coupe_{rang}")
        contrainte = solveur.RowConstraint(coupe.borne_inf, solveur.infinity())
        for nom, coefficient in coupe.coeffs:
            contrainte.SetCoefficient(variables[poly.index[nom]], float(coefficient))
        contrainte.SetCoefficient(relache, 1.0)
        objectif.SetCoefficient(relache, 1.0)

    objectif.SetMinimization()
    if _statut(solveur.Solve()) != "optimal":
        return np.zeros(len(contraintes), dtype=float)
    return -np.array([c.dual_value() for c in contraintes], dtype=float)


def resoudre(
    poly: Polytope,
    c: np.ndarray,
    *,
    depart: np.ndarray | None = None,
    coupes: list[Coupe] | None = None,
    duaux: bool = False,
) -> SolutionLP:
    """Minimiser ``<c, x>`` sur le polytope, avec les coupes fournies.

    Backend OR-Tools GLOP.

    Parameters
    ----------
    poly : Polytope
        Domaine admissible.
    c : numpy.ndarray
        Vecteur de coûts. **Son origine est sans importance ici** : distance
        géométrique ou gradient d'éclairement, le solveur ne fait pas la différence.
    depart : numpy.ndarray or None, optional
        Point de démarrage à chaud. **Seule sa présence est utilisée** : les valeurs ne
        sont pas transmises à GLOP, qui repart de sa propre base courante. Ce qu'elle
        autorise, c'est la réutilisation du modèle déjà construit pour ce polytope —
        seuls les coefficients de l'objectif changent. Dans une boucle de Frank-Wolfe,
        l'omettre coûte un facteur 3 à 5 (`ARCHITECTURE.md` §10). Sa dimension est
        néanmoins validée : un ``depart`` mal formé signale un appelant qui s'est trompé
        de polytope, et le laisser passer rendrait un résultat juste pour une mauvaise
        raison.
    coupes : list of Coupe or None, optional
        Coupes accumulées, réinjectées entre deux appels. Elles invalident le modèle en
        cache : leur nombre change le système, pas seulement l'objectif.
    duaux : bool, optional
        Extraire les prix duaux, dans l'ordre des lignes de ``poly.A`` — c'est cet ordre
        qui les rend appariables avec ``poly.origines``. **Les lignes de ``poly.A_eq``
        et les coupes n'y figurent pas** : elles n'ont pas de libellé dans ``origines``.
        Conséquence à connaître : après :func:`archlux.geom.polytope.figer_contacts`,
        les contraintes saturées — les plus informatives — sont passées dans ``A_eq`` et
        leur prix disparaît donc du diagnostic.

    Returns
    -------
    SolutionLP
        Solution, statut et diagnostics.

    Raises
    ------
    InvariantViole
        Dimension de ``c`` ou de ``depart`` incompatible avec le polytope.

    Guarantees
    ----------
    - Géométrique : **exacte** si ``statut == "optimal"`` — la solution appartient au
      polytope à la tolérance du solveur près. Cette appartenance est **revérifiée
      indépendamment** par :mod:`archlux.certify.preuve` avant tout retour à
      l'utilisateur : le solveur n'est jamais cru sur parole.
    - **Le démarrage à chaud ne change pas la solution**, seulement le temps. Sans cela,
      un certificat dépendrait de l'ordre des appels.
    - Aucune garantie de performance lumineuse n'est produite ici.

    Complexity
    ----------
    Simplexe. Budget : < 10 ms à froid, < 3 ms à chaud, 15 pièces
    (`ARCHITECTURE.md` §9).

    Notes
    -----
    **Ne pas simplifier cette signature.** ``depart`` et ``duaux`` paraissent inutiles
    au jalon 2 ; ils sont indispensables aux jalons 3 et 5. Les ajouter après oblige à
    restructurer l'interface pour faire circuler l'état (`MILESTONE-2.md` §4).
    """
    debut = time.perf_counter()
    n_var = len(poly.index)
    if c.shape != (n_var,):
        raise InvariantViole((f"objectif de dimension {c.shape}, attendu ({n_var},)",))
    if depart is not None and depart.shape != (n_var,):
        raise InvariantViole((f"départ de dimension {depart.shape}, attendu ({n_var},)",))

    cle = id(poly)
    en_cache = _CACHE.get(cle)
    reutilisable = depart is not None and en_cache is not None and not coupes
    if reutilisable and en_cache is not None:
        _, solveur, variables, contraintes = en_cache
        _CACHE.move_to_end(cle)
    else:
        solveur, variables, contraintes = _construire_modele(poly, coupes)
        if not coupes:
            _CACHE[cle] = (poly, solveur, variables, contraintes)
            _CACHE.move_to_end(cle)
            while len(_CACHE) > _TAILLE_CACHE:
                _CACHE.popitem(last=False)

    objectif = solveur.Objective()
    for variable, coefficient in zip(variables, c, strict=True):
        objectif.SetCoefficient(variable, float(coefficient))
    objectif.SetMinimization()

    code = solveur.Solve()
    statut = _statut(code)
    temps_ms = (time.perf_counter() - debut) * 1000.0

    if statut == "infaisable":
        # GLOP confond « infaisable » et « non borné ». Le problème auxiliaire tranche :
        # un optimum nul veut dire que les contraintes sont satisfiables, donc que
        # l'échec venait de l'objectif. Sans cette distinction, ``api.legalize`` lèverait
        # « le programme ne tient pas dans l'enveloppe » sur un domaine ouvert.
        if _est_faisable(poly, coupes):
            return SolutionLP(
                x=np.zeros(n_var),
                valeur=float("-inf"),
                statut="non_borne",
                iterations=solveur.iterations(),
                temps_ms=(time.perf_counter() - debut) * 1000.0,
            )
        return SolutionLP(
            x=np.zeros(n_var),
            valeur=float("inf"),
            statut=statut,
            certificat_farkas=_certificat_farkas(poly, coupes),
            iterations=solveur.iterations(),
            temps_ms=(time.perf_counter() - debut) * 1000.0,
        )

    x = np.array([v.solution_value() for v in variables], dtype=float)
    return SolutionLP(
        x=x,
        valeur=float(objectif.Value()),
        statut=statut,
        duaux=(
            np.array([contrainte.dual_value() for contrainte in contraintes], dtype=float)
            if duaux
            else None
        ),
        iterations=solveur.iterations(),
        temps_ms=temps_ms,
    )
