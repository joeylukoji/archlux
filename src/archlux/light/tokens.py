"""Tokenisation d'un plan : ensemble de jetons, **jamais une image**.

Déplacer un mur de 2 cm doit changer les jetons. Sur un raster, ce déplacement ne
change aucun pixel : gradient nul, projet impossible (`ARCHITECTURE.md` §10).
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvalidInput
from archlux.light.protocol import Glazing
from archlux.orient.circular import encode, encode_orientation
from archlux.types import Context, Opening, Orientation, Plan, Wall
from archlux.types import vectorize as _vectorize

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
"""``len(archlux.types.FIELDS_VECTOR)``: ``(x, y, w, h)`` par pièce."""
_TYPES = ("living_room", "bedroom", "kitchen", "bathroom", "corridor", "toilet")
_EPS = 1e-12


@renamed_parameters({"ordre": "order"})
def permute_rooms(plan: Plan, order: tuple[int, ...]) -> Plan:
    """Réordonner les pièces sans changer la géométrie."""
    if len(order) != len(plan.rooms):
        raise InvalidInput("order", "the permutation must have one index per room")
    rooms = tuple(plan.rooms[i] for i in order)
    return replace(plan, rooms=rooms)


def plan_to_vector(plan: Plan) -> np.ndarray:
    """``(x, y, w, h)`` per room, in ``plan.rooms`` order.

    :func:`archlux.types.vectorize` (PLAN.md phase 4, block 2): kept here under its own
    name since ``light`` may not import ``geom``, and this is the plain encoding, not
    the solver's index-ordered one.
    """
    return _vectorize(plan)


def _room_token(
    x: float,
    y: float,
    w: float,
    h: float,
    room_type: str,
    orientation: Orientation,
    n_rooms: float,
    total_area: float,
) -> np.ndarray:
    """Un jeton de pièce, continu en géométrie et périodique en azimut."""
    w = max(w, _EPS)
    h = max(h, _EPS)
    area = w * h
    peri = 2.0 * (w + h)
    compact = 4.0 * area / (peri * peri)
    type_oh = np.zeros(len(_TYPES) + 1, dtype=float)
    if room_type in _TYPES:
        type_oh[_TYPES.index(room_type)] = 1.0
    else:
        type_oh[-1] = 1.0
    azimuth = encode_orientation(orientation, harmonics=3)
    token = np.zeros(TOKEN_DIM, dtype=float)
    token[0:4] = (x, y, w, h)
    token[4:7] = (area, peri, compact)
    token[7:14] = type_oh
    token[14:20] = azimuth
    token[20] = n_rooms
    token[21] = total_area
    return token


def _opening_token(
    opening: Opening,
    wall: Wall,
    n_rooms: float,
    total_area: float,
    orientation: Orientation,
) -> np.ndarray:
    """Un jeton de baie : azimut du mur porteur, jamais recopié sur chaque pièce."""
    wall_azimuth = math.degrees(math.atan2(wall.b[1] - wall.a[1], wall.b[0] - wall.a[0]))
    token = np.zeros(TOKEN_DIM, dtype=float)
    token[14:20] = encode_orientation(orientation, harmonics=3)
    token[20] = n_rooms
    token[21] = total_area
    token[22:28] = np.concatenate(
        [
            encode(wall_azimuth, harmonics=1),
            np.array([opening.s, opening.relative_width, opening.head_height, 1.0], dtype=float),
        ]
    )
    token[28] = opening.sill_height
    return token


def plan_to_tokens(plan: Plan, ctx: Context) -> tuple[np.ndarray, np.ndarray]:
    """Encoder ``plan`` en ``(jetons [N, d], masque_padding [N])``.

    Trois familles, dans cet ordre : pièces, puis ouvertures (`MILESTONE-4.md` §4).
    Une baie n'est **pas** recopiée sur chaque pièce.

    ``masque_padding[i]`` est vrai si le jeton ``i`` est du remplissage
    (convention PyTorch ``src_key_padding_mask``).
    """
    n = len(plan.rooms)
    total_area = sum(p.area for p in plan.rooms)
    tokens = np.zeros((n, TOKEN_DIM), dtype=float)
    for i, room in enumerate(plan.rooms):
        tokens[i] = _room_token(
            room.x,
            room.y,
            room.w,
            room.h,
            room.type,
            ctx.orientation,
            float(n),
            total_area,
        )
    walls_by_id = {wall.id: wall for wall in plan.walls}
    extra: list[np.ndarray] = []
    for opening in plan.openings:
        wall = walls_by_id.get(opening.wall_id)
        if wall is None:
            continue
        extra.append(_opening_token(opening, wall, float(n), total_area, ctx.orientation))
    if extra:
        tokens = np.vstack((tokens, np.stack(extra)))
    mask = np.zeros(tokens.shape[0], dtype=bool)
    return tokens, mask


@renamed_parameters({"baies": "glazing"})
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
    glazing : Baies or None, optional
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
    vector = np.asarray(x, dtype=float).ravel()
    n = vector.size // FIELDS_PER_ROOM
    rooms = vector[: n * FIELDS_PER_ROOM].reshape(n, FIELDS_PER_ROOM)
    total_area = float(np.sum(rooms[:, 2] * rooms[:, 3]))
    tokens = np.zeros((n, TOKEN_DIM), dtype=float)
    for i in range(n):
        tokens[i] = _room_token(
            float(rooms[i, 0]),
            float(rooms[i, 1]),
            float(rooms[i, 2]),
            float(rooms[i, 3]),
            "living_room",
            orientation,
            float(n),
            total_area,
        )
    if glazing is not None and not glazing.empty:
        walls_by_id = {wall.id: wall for wall in glazing.walls}
        extra = [
            _opening_token(opening, walls_by_id[opening.wall_id], float(n), total_area, orientation)
            for opening in glazing.openings
            if opening.wall_id in walls_by_id
        ]
        if extra:
            tokens = np.vstack((tokens, np.stack(extra)))
    return tokens, np.zeros(tokens.shape[0], dtype=bool)


__getattr__ = lazy_aliases(
    __name__,
    {
        "permuter_pieces": Alias(permute_rooms, "archlux.light.tokens.permute_rooms"),
        "plan_vers_vecteur": Alias(plan_to_vector, "archlux.light.tokens.plan_to_vector"),
        "plan_vers_jetons": Alias(plan_to_tokens, "archlux.light.tokens.plan_to_tokens"),
        "vecteur_vers_jetons": Alias(vector_to_tokens, "archlux.light.tokens.vector_to_tokens"),
        "DIM_JETON": Alias(TOKEN_DIM, "archlux.light.tokens.TOKEN_DIM"),
        "CHAMPS_PAR_PIECE": Alias(FIELDS_PER_ROOM, "archlux.light.tokens.FIELDS_PER_ROOM"),
    },
)
