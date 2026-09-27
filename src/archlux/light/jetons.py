"""Tokenisation d'un plan : ensemble de jetons, **jamais une image**.

Déplacer un mur de 2 cm doit changer les jetons. Sur un raster, ce déplacement ne
change aucun pixel : gradient nul, projet impossible (`ARCHITECTURE.md` §10).
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvalidInput
from archlux.light.protocole import Glazing
from archlux.orient.circulaire import encode, encode_orientation
from archlux.types import Context, Opening, Orientation, Plan, Wall

__all__ = [
    "FIELDS_PER_ROOM",
    "TOKEN_DIM",
    "permute_rooms",
    "plan_to_tokens",
    "plan_to_vector",
    "vector_to_tokens",
]

TOKEN_DIM = 32
FIELDS_PER_ROOM = 4
"""``(x, y, w, h)`` par pièce. Dupliqué ici pour que ``light`` n'importe pas ``geom``."""
_TYPES = ("living_room", "bedroom", "kitchen", "bathroom", "corridor", "toilet")
_EPS = 1e-12


def permute_rooms(plan: Plan, ordre: tuple[int, ...]) -> Plan:
    """Réordonner les pièces sans changer la géométrie."""
    if len(ordre) != len(plan.rooms):
        raise InvalidInput("ordre", "the permutation must have one index per room")
    rooms = tuple(plan.rooms[i] for i in ordre)
    return replace(plan, rooms=rooms)


def plan_to_vector(plan: Plan) -> np.ndarray:
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
    room_type: str,
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
    if room_type in _TYPES:
        type_oh[_TYPES.index(room_type)] = 1.0
    else:
        type_oh[-1] = 1.0
    azimut = encode_orientation(orientation, harmoniques=3)
    token = np.zeros(TOKEN_DIM, dtype=float)
    token[0:4] = (x, y, w, h)
    token[4:7] = (aire, peri, compact)
    token[7:14] = type_oh
    token[14:20] = azimut
    token[20] = n_pieces
    token[21] = aire_totale
    return token


def _jeton_ouverture(
    ouv: Opening,
    mur: Wall,
    n_pieces: float,
    aire_totale: float,
    orientation: Orientation,
) -> np.ndarray:
    """Un jeton de baie : azimut du mur porteur, jamais recopié sur chaque pièce."""
    azimut_mur = math.degrees(math.atan2(mur.b[1] - mur.a[1], mur.b[0] - mur.a[0]))
    token = np.zeros(TOKEN_DIM, dtype=float)
    token[14:20] = encode_orientation(orientation, harmoniques=3)
    token[20] = n_pieces
    token[21] = aire_totale
    token[22:28] = np.concatenate(
        [
            encode(azimut_mur, harmoniques=1),
            np.array([ouv.s, ouv.relative_width, ouv.head_height, 1.0], dtype=float),
        ]
    )
    token[28] = ouv.sill_height
    return token


def plan_to_tokens(plan: Plan, ctx: Context) -> tuple[np.ndarray, np.ndarray]:
    """Encoder ``plan`` en ``(jetons [N, d], masque_padding [N])``.

    Trois familles, dans cet ordre : pièces, puis ouvertures (`MILESTONE-4.md` §4).
    Une baie n'est **pas** recopiée sur chaque pièce.

    ``masque_padding[i]`` est vrai si le jeton ``i`` est du remplissage
    (convention PyTorch ``src_key_padding_mask``).
    """
    n = len(plan.rooms)
    aire_totale = sum(p.area for p in plan.rooms)
    jetons = np.zeros((n, TOKEN_DIM), dtype=float)
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


def vector_to_tokens(
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
    donc ``"living_room"``. C'est une perte assumée — le vecteur de décision ne
    transporte pas le programme.
    """
    vecteur = np.asarray(x, dtype=float).ravel()
    n = vecteur.size // FIELDS_PER_ROOM
    rooms = vecteur[: n * FIELDS_PER_ROOM].reshape(n, FIELDS_PER_ROOM)
    aire_totale = float(np.sum(rooms[:, 2] * rooms[:, 3]))
    jetons = np.zeros((n, TOKEN_DIM), dtype=float)
    for i in range(n):
        jetons[i] = _jeton_piece(
            float(rooms[i, 0]),
            float(rooms[i, 1]),
            float(rooms[i, 2]),
            float(rooms[i, 3]),
            "living_room",
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


__getattr__ = lazy_aliases(
    __name__,
    {
        "permuter_pieces": Alias(permute_rooms, "archlux.light.jetons.permute_rooms"),
        "plan_vers_vecteur": Alias(plan_to_vector, "archlux.light.jetons.plan_to_vector"),
        "plan_vers_jetons": Alias(plan_to_tokens, "archlux.light.jetons.plan_to_tokens"),
        "vecteur_vers_jetons": Alias(vector_to_tokens, "archlux.light.jetons.vector_to_tokens"),
        "DIM_JETON": Alias(TOKEN_DIM, "archlux.light.jetons.TOKEN_DIM"),
        "CHAMPS_PAR_PIECE": Alias(FIELDS_PER_ROOM, "archlux.light.jetons.FIELDS_PER_ROOM"),
    },
)
