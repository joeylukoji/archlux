"""SVG rendering of a plan — to **look at** what the correction did.

Why this module exists
-----------------------
A repair rate does not say what a repair looks like. "certified valid plan" and
"median displacement of 43% of the side" are two correct statements that, alone,
suggest opposite things. Looking at them side by side settles in one second what
a table takes a page to suggest.

This is how the most serious defect of milestone 8 was found: rooms reduced to
zero thickness by the correction. No table showed it — the room count stayed
correct — and a single figure was enough.

The format is hand-written SVG: no dependency added — ``export`` may only import
``types`` and ``errors`` —, a vector output readable in any browser, and text that
``git diff`` can compare.

What the rendering shows, and why
-----------------------------------
- Rooms are **semi-transparent**: an overlap shows up as a denser zone, without any
  calculation annotating it.
- A **gap** reads as background still visible inside the outline.
- The target outline is drawn dashed, even when no room reaches it.
- :func:`compare` enforces **a single scale for both panels**. Two plans each
  rendered at their own scale would make a shrunk plan look intact: this is the
  error this constraint forbids.

This module measures nothing and proves nothing: see
:mod:`archlux.geom.diagnostic` and :mod:`archlux.certify.proof`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvalidInput

if TYPE_CHECKING:
    from archlux.types import Plan, Point, Wall

__all__ = ["compare", "render", "sheet"]

_MARGE = 28.0
_LARGEUR_PANNEAU = 380.0
_ESPACE = 12.0

# Hues by room type. An unknown type falls back to grey: inventing a color by
# hashing would make two corpora incomparable from one rendering to the next.
_TEINTES = {
    "living": "#c8d9ec",
    "living_room": "#c8d9ec",
    "living_dining": "#c3d6ea",
    "salon": "#c8d9ec",
    "kitchen": "#e8d9bd",
    "kitchen_dining": "#e5d5b8",
    "bedroom": "#d6e0cd",
    "room": "#d9e2d1",
    "bathroom": "#d5dfe6",
    "hallway": "#e4e0d8",
    "corridor": "#e4e0d8",
    "dining": "#ded4e2",
    "office": "#dcdce6",
    "storage": "#e0dcd6",
    "storeroom": "#e0dcd6",
}
_GRIS = "#dcdcdc"


def _echapper(texte: str) -> str:
    """Neutralize the five characters XML does not tolerate in a text node."""
    for brut, entite in (
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&apos;"),
    ):
        texte = texte.replace(brut, entite)
    return texte


def _etendue(
    plans: tuple[Plan, ...], contours: tuple[tuple[Point, ...], ...]
) -> tuple[float, float, float, float]:
    """Common bounding box, in meters. Empty if nothing is drawable."""
    xs: list[float] = []
    ys: list[float] = []
    for plan in plans:
        for room in plan.rooms:
            xs.extend((room.x, room.x + room.w))
            ys.extend((room.y, room.y + room.h))
    for outline in contours:
        xs.extend(point[0] for point in outline)
        ys.extend(point[1] for point in outline)
    if not xs:
        return (0.0, 0.0, 1.0, 1.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _panneau(
    plan: Plan,
    outline: tuple[Point, ...],
    titre: str,
    etendue: tuple[float, float, float, float],
    decalage_x: float,
    decalage_y: float = 0.0,
    walls: tuple[Wall, ...] = (),
) -> list[str]:
    """A panel: frame, dashed outline, rooms, walls, title. SVG coordinates.

    Load-bearing walls are drawn thick and dark (class ``wall-load-bearing``), other
    walls thin and grey (class ``wall``).
    """
    x0, y0, x1, y1 = etendue
    largeur_m = max(x1 - x0, 1e-9)
    hauteur_m = max(y1 - y0, 1e-9)
    utile = _LARGEUR_PANNEAU - 2 * _MARGE
    echelle = min(utile / largeur_m, utile / hauteur_m)
    hauteur_px = hauteur_m * echelle + 2 * _MARGE

    def vers_svg(x: float, y: float) -> tuple[float, float]:
        # The SVG y axis points down; a plan's points up. Without this flip the
        # rendering would be the mirror of the certified plan.
        return (
            decalage_x + _MARGE + (x - x0) * echelle,
            decalage_y + _MARGE + (y1 - y) * echelle,
        )

    parties = [
        f'<rect x="{decalage_x + 1:.1f}" y="{decalage_y + 1:.1f}" '
        f'width="{_LARGEUR_PANNEAU - 2:.1f}" height="{hauteur_px - 2:.1f}" '
        'fill="#ffffff" stroke="#c9c9c9" stroke-width="1"/>',
        f'<text x="{decalage_x + _MARGE:.1f}" y="{decalage_y + 18:.1f}" '
        'font-family="system-ui,sans-serif" '  # lang-ok: CSS value, not French
        f'font-size="13" font-weight="600" fill="#333">{_echapper(titre)}</text>',
    ]

    if outline:
        points = " ".join(
            f"{x:.2f},{y:.2f}" for x, y in map(lambda p: vers_svg(p[0], p[1]), outline)
        )
        parties.append(
            f'<polygon points="{points}" fill="none" stroke="#b04a4a" '
            'stroke-width="1.4" stroke-dasharray="6 4"/>'
        )

    for room in plan.rooms:
        coin_x, coin_y = vers_svg(room.x, room.y + room.h)
        teinte = _TEINTES.get(room.type.lower(), _GRIS)
        parties.append(
            f'<rect x="{coin_x:.2f}" y="{coin_y:.2f}" '
            f'width="{room.w * echelle:.2f}" height="{room.h * echelle:.2f}" '
            f'fill="{teinte}" fill-opacity="0.55" stroke="#4a4a4a" '
            'stroke-width="1"/>'
        )
        centre_x, centre_y = vers_svg(room.x + room.w / 2, room.y + room.h / 2)
        parties.append(
            f'<text x="{centre_x:.2f}" y="{centre_y:.2f}" text-anchor="middle" '
            'font-family="system-ui,sans-serif" font-size="9" fill="#2a2a2a">'  # lang-ok: CSS value
            f"{_echapper(room.type[:12])}</text>"
        )

    # Walls last, on top of rooms: a load-bearing wall crossed by a room must be visible.
    declared = {wall.id for wall in plan.walls}
    for wall in plan.walls + tuple(w for w in walls if w.id not in declared):
        (xa, ya), (xb, yb) = vers_svg(*wall.a), vers_svg(*wall.b)
        css_class, colour, width = (
            ("wall-load-bearing", "#1f1f1f", 4.0) if wall.load_bearing else ("wall", "#6b6b6b", 1.5)
        )
        parties.append(
            f'<line class="{css_class}" x1="{xa:.2f}" y1="{ya:.2f}" x2="{xb:.2f}" '
            f'y2="{yb:.2f}" stroke="{colour}" stroke-width="{width}" '
            'stroke-linecap="square"/>'
        )
    return parties


@renamed_parameters({"contour": "outline"})
def render(
    plan: Plan,
    *,
    outline: tuple[Point, ...] = (),
    titre: str = "",
    walls: tuple[Wall, ...] = (),
) -> str:
    """Render a plan as a standalone SVG.

    Parameters
    ----------
    plan : Plan
        Plan to draw. May be invalid — that is the use case.
    outline : tuple of Point, optional
        Target outline, drawn dashed. Default: the plan's own.
    titre : str, optional
        Label shown at the top of the panel.
    walls : tuple of Mur, optional
        Extra walls to draw, typically ``ctx.structure.load_bearing_walls``: a plan does not
        have to repeat its load-bearing structure, but a drawing should show it.

    Returns
    -------
    str
        Complete SVG document, encodable as-is in UTF-8.

    Examples
    --------
    >>> from archlux.types import Plan, Room
    >>> plan = Plan(
    ...     rooms=(Room(id="a", type="salon", x=0.0, y=0.0, w=3.0, h=2.0),),
    ...     walls=(), openings=(), outline=(),
    ... )
    >>> render(plan, titre="essai").startswith("<svg")
    True
    """
    vise = outline or plan.outline
    etendue = _etendue((plan,), (vise,) if vise else ())
    parties = _panneau(plan, vise, titre, etendue, 0.0, walls=walls)
    hauteur = _hauteur(etendue)
    return _document(_LARGEUR_PANNEAU, hauteur, parties)


@renamed_parameters({"contour": "outline"})
def compare(
    avant: Plan,
    apres: Plan,
    *,
    outline: tuple[Point, ...] = (),
    titres: tuple[str, str] = ("before", "after"),
    walls: tuple[Wall, ...] = (),
) -> str:
    """Render two plans side by side, **at the same scale**.

    Parameters
    ----------
    avant, apres : Plan
        The two states to compare.
    outline : tuple of Point, optional
        Target outline, common to both panels. Default: ``avant``'s own.
    titres : tuple of str, optional
        Labels of the two panels.
    walls : tuple of Mur, optional
        Extra walls drawn in both panels (see :func:`render`).

    Returns
    -------
    str
        Complete SVG document.

    Notes
    -----
    The scale is computed on the union of both extents, never panel by panel: a
    shrunk plan must **look** shrunk.

    Examples
    --------
    >>> from archlux.types import Plan, Room
    >>> a = Plan(rooms=(Room(id="p", type="salon", x=0.0, y=0.0, w=4.0, h=3.0),),
    ...          walls=(), openings=(), outline=())
    >>> b = Plan(rooms=(Room(id="p", type="salon", x=0.0, y=0.0, w=2.0, h=3.0),),
    ...          walls=(), openings=(), outline=())
    >>> svg = compare(a, b)
    >>> svg.count("<rect") >= 4        # two frames, two rooms
    True
    """
    return sheet(((avant, titres[0]), (apres, titres[1])), outline=outline, walls=walls)


@renamed_parameters({"contour": "outline"})
def sheet(
    volets: tuple[tuple[Plan, str], ...],
    *,
    outline: tuple[Point, ...] = (),
    colonnes: int = 4,
    walls: tuple[Wall, ...] = (),
) -> str:
    """Render a **series** of variants as a grid, all at the same scale.

    Parameters
    ----------
    volets : tuple of (Plan, str)
        The variants and their caption, in display order.
    outline : tuple of Point, optional
        Target outline, common to all panels. Default: the first plan's own.
    colonnes : int, optional
        Panels per row.
    walls : tuple of Mur, optional
        Extra walls drawn in every panel (see :func:`render`).

    Returns
    -------
    str
        Complete SVG document.

    Raises
    ------
    ValueError
        Empty series: there is nothing to draw, and rendering an empty document
        would hide the upstream error.

    Notes
    -----
    Designed for sweeps — one variant per solar azimuth, for example. A single
    scale for the whole sheet is what makes the series legible: otherwise each
    panel reframes itself and the displacements become invisible.

    Examples
    --------
    >>> from archlux.types import Plan, Room
    >>> plans = tuple(
    ...     (Plan(rooms=(Room(id="p", type="salon", x=float(k), y=0.0,
    ...                        w=3.0, h=2.0),),
    ...           walls=(), openings=(), outline=()), f"{k}°")
    ...     for k in range(3)
    ... )
    >>> sheet(plans, colonnes=2).startswith("<svg")
    True
    """
    if not volets:
        raise InvalidInput("volets", "empty sheet: nothing to draw")
    vise = outline or volets[0][0].outline
    etendue = _etendue(tuple(p for p, _ in volets), (vise,) if vise else ())
    step_x = _LARGEUR_PANNEAU + _ESPACE
    step_y = _hauteur(etendue) + _ESPACE

    parties: list[str] = []
    for rang, (plan, titre) in enumerate(volets):
        column, rangee = rang % colonnes, rang // colonnes
        parties += _panneau(
            plan, vise, titre, etendue, column * step_x, rangee * step_y, walls=walls
        )
    n_colonnes = min(len(volets), colonnes)
    n_rangees = (len(volets) + colonnes - 1) // colonnes
    return _document(n_colonnes * step_x - _ESPACE, n_rangees * step_y - _ESPACE, parties)


def _hauteur(etendue: tuple[float, float, float, float]) -> float:
    """Document height, in pixels, for a given metric extent."""
    x0, y0, x1, y1 = etendue
    largeur_m = max(x1 - x0, 1e-9)
    hauteur_m = max(y1 - y0, 1e-9)
    utile = _LARGEUR_PANNEAU - 2 * _MARGE
    return hauteur_m * min(utile / largeur_m, utile / hauteur_m) + 2 * _MARGE


def _document(largeur: float, hauteur: float, parties: list[str]) -> str:
    """Wrap the fragments in a standalone SVG document."""
    corps = "\n  ".join(parties)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largeur:.0f}" '
        f'height="{hauteur:.0f}" viewBox="0 0 {largeur:.0f} {hauteur:.0f}">\n'
        f'  <rect width="{largeur:.0f}" height="{hauteur:.0f}" fill="#f7f6f3"/>\n'
        f"  {corps}\n</svg>\n"
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "rendre": Alias(render, "archlux.export.svg.render"),
        "comparer": Alias(compare, "archlux.export.svg.compare"),
        "planche": Alias(sheet, "archlux.export.svg.sheet"),
    },
)
