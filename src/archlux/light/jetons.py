"""Tokenisation d'un plan : ensemble de jetons, **jamais une image**.

Déplacer un mur de 2 cm doit changer les jetons. Sur un raster, ce déplacement ne
change aucun pixel : gradient nul, projet impossible (`ARCHITECTURE.md` §10).
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from archlux.errors import InvalidInput
from archlux.light.protocole import Glazing
from archlux.orient.circulaire import encode, encoder
from archlux.types import Context, Opening, Orientation, Plan, Wall

__all__ = [
    "CHAMPS_PAR_PIECE",
    "DIM_JETON",
    "permuter_pieces",
    "plan_vers_jetons",
    "plan_vers_vecteur",
    "vecteur_vers_jetons",
]

DIM_JETON = 32
CHAMPS_PAR_PIECE = 4
"""``(x, y, w, h)`` par pièce. Dupliqué ici pour que ``light`` n'importe pas ``geom``."""
_TYPES = ("sejour", "chambre", "cuisine", "sdb", "couloir", "wc")
_EPS = 1e-12


def permuter_pieces(plan: Plan, ordre: tuple[int, ...]) -> Plan:
    """Réordonner les pièces sans changer la géométrie."""
    if len(ordre) != len(plan.rooms):
        raise InvalidInput("ordre", "the permutation must have one index per room")
    pieces = tuple(plan.rooms[i] for i in ordre)
    return replace(plan, rooms=pieces)


def plan_vers_vecteur(plan: Plan) -> np.ndarray:
    """Vecteur de décision ``(x, y, w, h)`` par pièce, même contrat que le polytope."""
    return np.array(
        [(piece.x, piece.y, piece.w, piece.h) for piece in plan.rooms],
        dtype=float,
    ).ravel()


def _jeton_piece(
    x: float,
    y: float,
    w: float,
    h: float,
    type_piece: str,
    orientation: Orientation,
    n_pieces: float,
    aire_totale: float,
) -> np.ndarray:
    """Un jeton de pièce, continu en géométrie et périodique en azimut."""
    w = max(w, _EPS)
    h = max(h, _EPS)
    aire = w * h
    peri = 2.0 * (w + h)
    compact = 4.0 * aire / (peri * peri)
    type_oh = np.zeros(len(_TYPES) + 1, dtype=float)
    if type_piece in _TYPES:
        type_oh[_TYPES.index(type_piece)] = 1.0
    else:
        type_oh[-1] = 1.0
    azimut = encoder(orientation, harmoniques=3)
    jeton = np.zeros(DIM_JETON, dtype=float)
    jeton[0:4] = (x, y, w, h)
    jeton[4:7] = (aire, peri, compact)
    jeton[7:14] = type_oh
    jeton[14:20] = azimut
    jeton[20] = n_pieces
    jeton[21] = aire_totale
    return jeton


def _jeton_ouverture(
    ouv: Opening,
    mur: Wall,
    n_pieces: float,
    aire_totale: float,
    orientation: Orientation,
) -> np.ndarray:
    """Un jeton de baie : azimut du mur porteur, jamais recopié sur chaque pièce."""
    azimut_mur = math.degrees(math.atan2(mur.b[1] - mur.a[1], mur.b[0] - mur.a[0]))
    jeton = np.zeros(DIM_JETON, dtype=float)
    jeton[14:20] = encoder(orientation, harmoniques=3)
    jeton[20] = n_pieces
    jeton[21] = aire_totale
    jeton[22:28] = np.concatenate(
        [
            encode(azimut_mur, harmoniques=1),
            np.array([ouv.s, ouv.relative_width, ouv.head_height, 1.0], dtype=float),
        ]
    )
    jeton[28] = ouv.sill_height
    return jeton


def plan_vers_jetons(plan: Plan, ctx: Context) -> tuple[np.ndarray, np.ndarray]:
    """Encoder ``plan`` en ``(jetons [N, d], masque_padding [N])``.

    Trois familles, dans cet ordre : pièces, puis ouvertures (`MILESTONE-4.md` §4).
    Une baie n'est **pas** recopiée sur chaque pièce.

    ``masque_padding[i]`` est vrai si le jeton ``i`` est du remplissage
    (convention PyTorch ``src_key_padding_mask``).
    """
    n = len(plan.rooms)
    aire_totale = sum(p.area for p in plan.rooms)
    jetons = np.zeros((n, DIM_JETON), dtype=float)
    for i, piece in enumerate(plan.rooms):
        jetons[i] = _jeton_piece(
            piece.x,
            piece.y,
            piece.w,
            piece.h,
            piece.type,
            ctx.orientation,
            float(n),
            aire_totale,
        )
    murs_par_id = {mur.id: mur for mur in plan.walls}
    extra: list[np.ndarray] = []
    for ouv in plan.openings:
        mur = murs_par_id.get(ouv.wall_id)
        if mur is None:
            continue
        extra.append(_jeton_ouverture(ouv, mur, float(n), aire_totale, ctx.orientation))
    if extra:
        jetons = np.vstack((jetons, np.stack(extra)))
    masque = np.zeros(jetons.shape[0], dtype=bool)
    return jetons, masque


def vecteur_vers_jetons(
    x: np.ndarray, orientation: Orientation, glazing: Glazing | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Même vocabulaire depuis le vecteur de décision, baies comprises.

    Parameters
    ----------
    x : numpy.ndarray
        Vecteur de décision ``(x, y, w, h)`` par pièce.
    orientation : Orientation
        Azimut du bâtiment.
    baies : Baies or None, optional
        Fenestration. ``None`` rend les seuls jetons de pièce — c'est le
        comportement d'avant l'extension du protocole, et il est **exactement**
        conservé.

    Returns
    -------
    tuple
        ``(jetons [N, DIM_JETON], masque_padding [N])``, pièces puis baies.

    Notes
    -----
    Le type de pièce est inconnu depuis un vecteur nu : toutes les pièces portent
    donc ``"sejour"``. C'est une perte assumée — le vecteur de décision ne
    transporte pas le programme.
    """
    vecteur = np.asarray(x, dtype=float).ravel()
    n = vecteur.size // CHAMPS_PAR_PIECE
    pieces = vecteur[: n * CHAMPS_PAR_PIECE].reshape(n, CHAMPS_PAR_PIECE)
    aire_totale = float(np.sum(pieces[:, 2] * pieces[:, 3]))
    jetons = np.zeros((n, DIM_JETON), dtype=float)
    for i in range(n):
        jetons[i] = _jeton_piece(
            float(pieces[i, 0]),
            float(pieces[i, 1]),
            float(pieces[i, 2]),
            float(pieces[i, 3]),
            "sejour",
            orientation,
            float(n),
            aire_totale,
        )
    if glazing is not None and not glazing.empty:
        murs_par_id = {mur.id: mur for mur in glazing.walls}
        extra = [
            _jeton_ouverture(ouv, murs_par_id[ouv.wall_id], float(n), aire_totale, orientation)
            for ouv in glazing.openings
            if ouv.wall_id in murs_par_id
        ]
        if extra:
            jetons = np.vstack((jetons, np.stack(extra)))
    return jetons, np.zeros(jetons.shape[0], dtype=bool)
