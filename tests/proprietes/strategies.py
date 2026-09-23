"""Stratégies Hypothesis partagées par tous les jalons.

Ce module est le livrable caché du jalon 1 : le test d'acceptation du jalon 2, les tests
de coupes et ceux de dérive le réutiliseront tous. Écrit une fois, correctement, il évite
trois générateurs de plans divergents.

Les stratégies non encore nécessaires lèvent ``NotImplementedError`` avec leur jalon :
les écrire d'avance produirait des générateurs jamais exécutés, donc jamais corrects.
"""

from __future__ import annotations

import itertools

import numpy as np
from hypothesis import strategies as st

from archlux.geom.graphe import OrdreRelatif
from archlux.types import (
    BornePerformance,
    Certificat,
    Contexte,
    Manifeste,
    ModeleTrace,
    Mur,
    Orientation,
    Ouverture,
    Piece,
    Plan,
    PreuveGeometrique,
    Referentiel,
    Structure,
)

__all__ = [
    "CONTEXTE_DEFAUT",
    "contextes",
    "murs",
    "ordres_valides",
    "pieces",
    "plans_quelconques",
    "plans_valides",
    "realistic_scenarios",
    "vecteurs_objectifs",
]

_COORD = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)
_TAILLE = st.floats(min_value=0.1, max_value=1e3, allow_nan=False, allow_infinity=False)
_UNITE = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_IDS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789", min_size=1, max_size=8)
_TYPES = st.sampled_from(["sejour", "chambre", "cuisine", "sdb", "couloir", "wc"])


def pieces() -> st.SearchStrategy[Piece]:
    """Pièces rectangulaires quelconques, dimensions strictement positives."""
    return st.builds(Piece, id=_IDS, type=_TYPES, x=_COORD, y=_COORD, w=_TAILLE, h=_TAILLE)


def murs() -> st.SearchStrategy[Mur]:
    """Murs quelconques, porteurs ou non."""
    return st.builds(
        Mur,
        id=_IDS,
        a=st.tuples(_COORD, _COORD),
        b=st.tuples(_COORD, _COORD),
        porteur=st.booleans(),
        epaisseur=st.floats(min_value=0.05, max_value=0.6, allow_nan=False),
    )


def _ouvertures(ids_murs: list[str]) -> st.SearchStrategy[Ouverture]:
    return st.builds(
        Ouverture,
        id=_IDS,
        mur_id=st.sampled_from(ids_murs),
        s=_UNITE,
        largeur_rel=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
        hauteur_allege=st.floats(min_value=0.0, max_value=1.5, allow_nan=False),
        hauteur_linteau=st.floats(min_value=1.6, max_value=3.0, allow_nan=False),
    )


def _preuves() -> st.SearchStrategy[PreuveGeometrique]:
    """Preuves géométriques, **avec** des violations parfois non vides.

    Un générateur qui ne produirait que ``violations=()`` rendrait la sérialisation de
    ce champ inatteignable : le test paraîtrait exhaustif tout en n'exécutant jamais la
    branche.
    """
    return st.builds(
        PreuveGeometrique,
        valide=st.booleans(),
        chevauchement=st.booleans(),
        jours=st.booleans(),
        surfaces_ok=st.booleans(),
        structure_preservee=st.booleans(),
        deplacement_max=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        violations=st.lists(st.text(max_size=40), max_size=3).map(tuple),
    )


def _bornes() -> st.SearchStrategy[BornePerformance]:
    """Bornes conformes, toujours munies de leur couverture et de ``n_calibration``."""
    reels = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    return st.builds(
        BornePerformance,
        indicateur=st.sampled_from(["sDA", "ASE", "UDI", "vue"]),
        valeur=reels,
        borne_inf=reels,
        borne_sup=reels,
        couverture=st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
        n_calibration=st.integers(min_value=1, max_value=100_000),
    )


def _manifestes() -> st.SearchStrategy[Manifeste]:
    """Manifestes de reproductibilité, champs optionnels parfois renseignés."""
    paires = st.lists(st.tuples(st.text(max_size=12), st.text(max_size=12)), max_size=3).map(tuple)
    modeles = st.one_of(
        st.none(),
        st.builds(
            ModeleTrace,
            poids=st.text(min_size=1, max_size=32),
            calibration_n=st.integers(min_value=1, max_value=10_000),
            alpha=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
        ),
    )
    return st.builds(
        Manifeste,
        version=st.text(min_size=1, max_size=10),
        horodatage=st.text(min_size=1, max_size=32),
        graine=st.integers(min_value=0, max_value=2**32 - 1),
        empreinte_donnees=st.one_of(st.none(), st.text(max_size=20)),
        decoupage=st.one_of(st.none(), st.text(max_size=20)),
        environnement=paires,
        parametres=paires,
        modele=modeles,
    )


def _certificats() -> st.SearchStrategy[Certificat]:
    """Certificats complets : les deux garanties, le diagnostic dual et la trace.

    ``performance`` est ``None`` **une fois sur deux** et non systématiquement : les
    deux modes — classique sans borne, performantiel avec borne — doivent tous deux
    traverser la sérialisation.
    """
    return st.builds(
        Certificat,
        geometrie=_preuves(),
        performance=st.one_of(st.none(), _bornes()),
        duaux=st.lists(
            st.tuples(
                st.text(max_size=20),
                st.floats(min_value=-1e3, max_value=1e3, allow_nan=False),
            ),
            max_size=3,
        ).map(tuple),
        manifeste=st.one_of(st.none(), _manifestes()),
    )


@st.composite
def plans_quelconques(draw: st.DrawFn) -> Plan:
    """Plans arbitraires, valides ou non — l'entrée réelle du système.

    C'est délibérément permissif : ``legalize`` doit rendre un plan valide *y compris*
    sur une entrée absurde, et un générateur qui ne produirait que du plausible ne
    testerait pas cette promesse.
    """
    liste_murs = draw(st.lists(murs(), min_size=1, max_size=6, unique_by=lambda m: m.id))
    ids_murs = [m.id for m in liste_murs]
    liste_pieces = draw(st.lists(pieces(), min_size=1, max_size=6, unique_by=lambda p: p.id))
    liste_ouv = draw(st.lists(_ouvertures(ids_murs), max_size=5, unique_by=lambda o: o.id))
    contour = draw(st.lists(st.tuples(_COORD, _COORD), min_size=3, max_size=8))
    certificat = draw(st.one_of(st.none(), _certificats()))
    return Plan(
        pieces=tuple(liste_pieces),
        murs=tuple(liste_murs),
        ouvertures=tuple(liste_ouv),
        contour=tuple(contour),
        certificat=certificat,
    )


LARGEUR_MIN_DEFAUT = 1.0
"""Largeur minimale du contexte de référence, en mètres."""

CONTOUR_DEFAUT_CM = (1200, 900)
"""Contour de référence, en **centimètres** : 12 m x 9 m."""

CONTEXTE_DEFAUT = Contexte(
    structure=Structure(murs_porteurs=()),
    orientation=Orientation(deg=0.0),
    contour=((0.0, 0.0), (12.0, 0.0), (12.0, 9.0), (0.0, 9.0)),
    referentiel=Referentiel(aires_min=(), largeur_min=LARGEUR_MIN_DEFAUT),
)
"""Contexte de référence des tests, accordé à :func:`plans_valides`."""


def _decouper(
    draw: st.DrawFn, x: int, y: int, w: int, h: int, profondeur: int, minimum: int
) -> list[tuple[int, int, int, int]]:
    """Découper récursivement un rectangle en guillotine, en centimètres.

    Les coupes sont entières : additionner des centimètres reste exact, là où des coupes
    flottantes laisseraient des jours de l'ordre de 1e-16 entre pièces voisines.
    """
    axes = [axe for axe, taille in (("v", w), ("h", h)) if taille >= 2 * minimum]
    if profondeur == 0 or not axes or not draw(st.booleans()):
        return [(x, y, w, h)]
    axe = draw(st.sampled_from(axes))
    if axe == "v":
        coupe = draw(st.integers(min_value=minimum, max_value=w - minimum))
        gauche = _decouper(draw, x, y, coupe, h, profondeur - 1, minimum)
        return gauche + _decouper(draw, x + coupe, y, w - coupe, h, profondeur - 1, minimum)
    coupe = draw(st.integers(min_value=minimum, max_value=h - minimum))
    bas = _decouper(draw, x, y, w, coupe, profondeur - 1, minimum)
    return bas + _decouper(draw, x, y + coupe, w, h - coupe, profondeur - 1, minimum)


@st.composite
def plans_valides(draw: st.DrawFn, profondeur: int = 3) -> Plan:
    """Plans géométriquement valides, accordés à :data:`CONTEXTE_DEFAUT`.

    Construits par **découpes en guillotine** : le contour est coupé récursivement en
    deux, et les feuilles deviennent les pièces. Le pavage est alors exact par
    construction — aucun chevauchement, aucun jour — sans qu'aucune vérification
    géométrique ne soit nécessaire côté générateur.

    C'est le point important : un générateur qui appellerait ``verifier_exactement`` pour
    filtrer ses sorties rendrait tautologique tout test de validité.

    Notes
    -----
    Les plans produits sont des pavages en guillotine, qui ne couvrent pas tous les
    plans valides — un pavage « en moulin » n'est pas atteignable. C'est une limite
    connue et acceptée : elle restreint la couverture, elle ne fausse aucun test.
    """
    largeur, hauteur = CONTOUR_DEFAUT_CM
    minimum = int(LARGEUR_MIN_DEFAUT * 100)
    rectangles = _decouper(draw, 0, 0, largeur, hauteur, profondeur, minimum)
    pieces = tuple(
        Piece(
            id=f"p{i}",
            type=draw(_TYPES),
            x=x / 100.0,
            y=y / 100.0,
            w=w / 100.0,
            h=h / 100.0,
        )
        for i, (x, y, w, h) in enumerate(rectangles)
    )
    return Plan(
        pieces=pieces,
        murs=(),
        ouvertures=(),
        contour=CONTEXTE_DEFAUT.contour,
    )


@st.composite
def ordres_valides(draw: st.DrawFn, max_pieces: int = 6) -> OrdreRelatif:
    """Ordres relatifs acycliques dont toute paire est séparée.

    Construit **sans réutiliser ``deduire_ordre``** : deux rangs totaux tirés au hasard,
    un par axe, puis un axe choisi à pile ou face pour chaque paire. L'arête suit le rang
    de l'axe retenu.

    Les deux propriétés attendues tombent alors par construction, et pour des raisons
    indépendantes du code testé :

    - **acyclique**, car les arêtes d'un axe suivent un ordre total ;
    - **toute paire séparée**, car chaque paire reçoit exactement une arête.

    Dériver ces ordres du code de production rendrait les tests tautologiques : ils
    passeraient quelle que soit l'erreur commise des deux côtés.
    """
    nombre = draw(st.integers(min_value=2, max_value=max_pieces))
    identifiants = [f"p{i}" for i in range(nombre)]
    rang_x = {nom: i for i, nom in enumerate(draw(st.permutations(identifiants)))}
    rang_y = {nom: i for i, nom in enumerate(draw(st.permutations(identifiants)))}

    horizontal: list[tuple[str, str]] = []
    vertical: list[tuple[str, str]] = []
    for a, b in itertools.combinations(sorted(identifiants), 2):
        if draw(st.booleans()):
            horizontal.append((a, b) if rang_x[a] < rang_x[b] else (b, a))
        else:
            vertical.append((a, b) if rang_y[a] < rang_y[b] else (b, a))

    return OrdreRelatif(
        horizontal=tuple(horizontal),
        vertical=tuple(vertical),
        pieces=tuple(sorted(identifiants)),
    )


@st.composite
def contextes(draw: st.DrawFn) -> Contexte:
    """Contextes cohérents : contour rectangulaire, orientation, référentiel.

    La structure porteuse est vide : lier une pièce à un mur porteur demande une
    incidence que ``construire_polytope(ordre, ctx)`` n'a pas les moyens de calculer
    (voir la note d'ADR-7 dans le blueprint).
    """
    largeur = draw(st.floats(min_value=5.0, max_value=30.0, allow_nan=False))
    hauteur = draw(st.floats(min_value=5.0, max_value=30.0, allow_nan=False))
    return Contexte(
        structure=Structure(murs_porteurs=()),
        orientation=Orientation(deg=draw(st.floats(0.0, 360.0, allow_nan=False))),
        contour=((0.0, 0.0), (largeur, 0.0), (largeur, hauteur), (0.0, hauteur)),
        referentiel=Referentiel(
            aires_min=(),
            largeur_min=draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False)),
        ),
    )


def vecteurs_objectifs(dimension: int) -> st.SearchStrategy[np.ndarray]:
    """Vecteurs de coûts bornés, **d'origine indifférente** — comme les voit ``lmo``.

    Le générateur ne sait pas plus que le solveur d'où vient le vecteur : distance
    géométrique au jalon 2, gradient d'éclairement au jalon 3. C'est cette ignorance que
    les tests doivent refléter.
    """
    return st.lists(
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False),
        min_size=dimension,
        max_size=dimension,
    ).map(lambda valeurs: np.array(valeurs, dtype=float))


@st.composite
def realistic_scenarios(draw: st.DrawFn) -> tuple[Plan, Contexte]:
    """Valid plan plus a context that actually constrains it (PLAN.md, task 0.8).

    Every other strategy uses ``aires_min=()`` and no load-bearing wall, which is how the
    critical defects of AUDIT.md §3 went unnoticed. Here:

    - one load-bearing wall lies on a real partition of the plan (a room edge that is
      not on the outline), so the input respects it;
    - each room type present gets a minimum area between 50 % and 100 % of its smallest
      room, the tight case included, so the input satisfies every minimum;
    - the orientation is arbitrary.

    The input is therefore valid under its own context: any violation in the output is
    introduced by ``legalize``.
    """
    plan = draw(plans_valides())
    largeur, hauteur = (c / 100.0 for c in CONTOUR_DEFAUT_CM)

    edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for room in plan.pieces:
        right, top = room.x + room.w, room.y + room.h
        if right < largeur - 1e-9:
            edges.append(((right, room.y), (right, top)))
        if top < hauteur - 1e-9:
            edges.append(((room.x, top), (right, top)))
    walls: tuple[Mur, ...] = ()
    if edges:
        a, b = draw(st.sampled_from(edges))
        walls = (Mur(id="lb0", a=a, b=b, porteur=True),)

    smallest: dict[str, float] = {}
    for room in plan.pieces:
        smallest[room.type] = min(smallest.get(room.type, float("inf")), room.w * room.h)
    ratio = draw(st.floats(min_value=0.5, max_value=1.0, allow_nan=False))
    minimum_areas = tuple(sorted((kind, ratio * area) for kind, area in smallest.items()))

    context = Contexte(
        structure=Structure(murs_porteurs=walls),
        orientation=Orientation(deg=draw(st.floats(0.0, 360.0, allow_nan=False))),
        contour=CONTEXTE_DEFAUT.contour,
        referentiel=Referentiel(aires_min=minimum_areas, largeur_min=LARGEUR_MIN_DEFAUT),
    )
    return Plan(pieces=plan.pieces, murs=walls, ouvertures=(), contour=plan.contour), context
