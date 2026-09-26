"""Propriétés des coupes de surface — `MILESTONE-2.md` §5.

Source de vérité : inégalité AM-GM, pas le code de ``coupe_surface``.
"""

from __future__ import annotations

import numpy as np
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from archlux.geom.polytope import construire_polytope
from archlux.lmo.coupes import coupe_surface, resoudre_avec_surfaces
from archlux.types import Context, Orientation, Regulation, Room, Structure
from tests.proprietes.strategies import ordres_valides


@given(
    w0=st.floats(min_value=0.5, max_value=10.0, allow_nan=False),
    h0=st.floats(min_value=0.5, max_value=10.0, allow_nan=False),
    w=st.floats(min_value=0.5, max_value=20.0, allow_nan=False),
    h=st.floats(min_value=0.5, max_value=20.0, allow_nan=False),
)
@settings(max_examples=200, deadline=None)
def test_la_coupe_n_exclut_aucun_point_valide(w0: float, h0: float, w: float, h: float) -> None:
    """Toute tangente à {wh ≥ a} laisse passer les points de produit suffisant.

    AM-GM : (w/w₀ + h/h₀)/2 ≥ √(wh / (w₀ h₀)). Sur l'hyperbole w₀ h₀ = a,
    cela donne h₀ w + w₀ h ≥ 2a dès que wh ≥ a.
    """
    a = w0 * h0
    assume(w * h + 1e-12 >= a)
    assert coupe_surface(w0, h0, a).satisfait(w, h)


@given(ordre=ordres_valides(max_pieces=4))
@settings(max_examples=40, deadline=None)
def test_surfaces_minimales_respectees(ordre: object) -> None:
    """Après la boucle de coupes, aucune pièce n'est sous son a_min."""
    ctx = Context(
        structure=Structure(load_bearing_walls=()),
        orientation=Orientation(deg=0.0),
        outline=((0.0, 0.0), (20.0, 0.0), (20.0, 16.0), (0.0, 16.0)),
        regulation=Regulation(min_areas=(("living_room", 4.0),), min_width=1.0),
    )
    poly = construire_polytope(ordre, ctx)  # type: ignore[arg-type]
    pieces = tuple(
        Room(id=nom, type="living_room", x=0.0, y=0.0, w=1.0, h=1.0)
        for nom in ordre.pieces  # type: ignore[attr-defined]
    )
    c = np.zeros(len(poly.index))
    for nom, colonne in poly.index.items():
        if nom.endswith(".w") or nom.endswith(".h"):
            c[colonne] = 1.0
    sol = resoudre_avec_surfaces(poly, c, ctx, pieces)
    if sol.statut != "optimal":
        return
    for piece in pieces:
        w = float(sol.x[poly.index[f"{piece.id}.w"]])
        h = float(sol.x[poly.index[f"{piece.id}.h"]])
        assert w * h >= 4.0 - 1e-6
