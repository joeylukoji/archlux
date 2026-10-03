"""Real corpus loaders: WKT -> :class:`~archlux.types.Plan`.

The MSD corpus (van Engelenburg *et al.*, ECCV 2024, CC BY-SA 4.0) delivers each
floor as WKT polygons, **in the site's own frame**: no apartment is aligned on
the axes. Yet ``geom`` works on axis-aligned rectangles.

The conversion holds in four steps, in this order:

1. **Straighten.** The dominant direction of the walls, of period 90 degrees and
   weighted by length (:func:`~archlux.orient.circular.dominant_direction`),
   gives the angle of the local frame. This angle **is** the ``Orientation`` of
   the plan: it is not discarded, it becomes the input of the daylight
   surrogate.
2. **Snap.** After rotation, the edges sit within a few millimetres of an axis
   (measured median: 0 mm). Exact alignment is forced under ``snap_tolerance``,
   without which ``geom.rectilinear`` refuses the polygon for a "diagonal
   edge".
3. **Decompose.** Few real rooms are rectangles (0.1% of apartments); almost
   all are rectilinear. Each room becomes a
   :class:`~archlux.geom.rectilinear.RectilinearRoom`, and its bonding
   equalities are passed to ``legalize(..., merges=)``.
4. **Attach openings.** A window is projected onto the nearest wall and stored
   as ``(wall_id, s, relative_width)`` — **never** in absolute coordinates
   (`ARCHITECTURE.md` §10).

What MSD does not give
-----------------------
**No load-bearing wall annotation.** The only separator subtypes are ``WALL``
and ``COLUMN``. ``Structure.load_bearing_walls`` is therefore empty and only
the columns are populated: inventing load-bearing status would produce
arbitrary ``A_eq`` equalities, and a ``structure_kept`` that means nothing.

No daylight simulation either: see ``docs/data/ground-truth.md``.
"""

from __future__ import annotations

import csv
import io
import math
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from shapely import affinity, wkt
from shapely.errors import ShapelyError
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvariantViolation
from archlux.geom.rectilinear import RectilinearRoom, decompose
from archlux.orient.circular import dominant_direction
from archlux.types import (
    Context,
    Opening,
    Orientation,
    Plan,
    Regulation,
    Room,
    Structure,
    Wall,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

__all__ = [
    "DEFAULT_SUN_COLUMN",
    "EXCLUDED_TYPES",
    "LoadStatistics",
    "MSDApartment",
    "label",
    "load_msd",
    "load_sd_labels",
    "split_by_site",
]

EXCLUDED_TYPES = frozenset({"SHAFT", "ELEVATOR", "STAIRCASE", "VOID", "BALCONY", "TERRACE"})
"""``area`` subtypes discarded: they are not part of the habitable unit.

Shafts and elevator cages create **holes** in the union of rooms; balconies and
terraces stick out of it. In both cases the outline stops being a simple ring,
which :class:`~archlux.types.Plan` cannot represent.
"""

DEFAULT_SUN_COLUMN = "sun_201803211200_mean"
"""Irradiance column used by default: March 21 at noon, averaged per room.

`simulations.csv` offers **126** of them: 18 instants x 7 aggregations (``max``,
``mean``, ``median``, ``min``, ``p20``, ``p80``, ``stddev``). The choice above is
the equinox at noon, the least atypical of the eighteen instants; it has
nothing canonical about it and must be **cited as such** in any publication.

!!! danger "This is not an sDA"
    These columns are irradiance aggregates at fixed instants, not the share of
    floor above 300 lux during 50% of occupied hours. Calibrating on them
    bounds **these columns**, never an LM-83 sDA. The ``indicator`` label of
    ``archlux`` must then be read as the name of the learned target, not as the
    IES metric.
"""

_EPS = 1e-9
_MAX_WALL_WIDTH = 1.0
"""Beyond this, the "wall" is a solid mass, not a partition: its long axis has no meaning."""


@dataclass(frozen=True, slots=True)
class MSDApartment:
    """A converted MSD apartment, ready for :func:`~archlux.api.legalize`.

    Attributes
    ----------
    merges : tuple of RectilinearRoom
        To be passed as is to ``legalize(..., merges=...)``. Empty if all
        rooms were already rectangles.
    straightening_angle : float
        Rotation applied, in degrees. The returned geometry is **already**
        straightened; this angle is carried over into ``context.orientation``.
    site_id : str
        Originating Swiss Dwellings site. **This is the splitting unit**,
        never the apartment: two units on the same site share urban mask,
        climate and orientation. See :func:`split_by_site`.
    source_areas : tuple of str
        Swiss Dwellings ``area_id`` of the rooms **before decomposition**, in
        the order they were read. Join key to the simulations.
    """

    id: str
    plan: Plan
    context: Context
    merges: tuple[RectilinearRoom, ...]
    straightening_angle: float
    site_id: str = ""
    source_areas: tuple[str, ...] = ()


@dataclass(slots=True)
class LoadStatistics:
    """Count of apartments read, kept, and the reasons for rejection.

    A real corpus is partly rejected; publishing the retention rate **and**
    its breakdown is what makes a paper's sample verifiable.
    """

    read: int = 0
    kept: int = 0
    rejections: Counter[str] = field(default_factory=Counter)

    @property
    def retention_rate(self) -> float:
        """Share of read apartments actually converted, in ``[0, 1]``."""
        return self.kept / self.read if self.read else 0.0

    def summary(self) -> str:
        """Render a readable summary, reasons sorted by decreasing frequency."""
        rows = [f"lus {self.read}, retenus {self.kept} ({100.0 * self.retention_rate:.1f} %)"]
        rows.extend(f"  rejet {reason} : {n}" for reason, n in self.rejections.most_common())
        return "\n".join(rows)


def _identifier(value: str) -> str:
    """Normalize a numeric identifier.

    MSD writes ``area_id`` as a float (``484803.0``), Swiss Dwellings as an
    integer (``484803``). Without this normalization the join yields **0%**
    instead of 99%.
    """
    text = str(value).strip()
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def _angles_and_lengths(  # lang-ok: kept private identifier
    polygons: list[Polygon],
) -> tuple[list[float], list[float]]:
    """Angle and length of each edge, to estimate the grid direction."""
    angles: list[float] = []
    lengths: list[float] = []
    for poly in polygons:
        coords = list(poly.exterior.coords)[:-1]
        for (x0, y0), (x1, y1) in zip(coords, coords[1:] + coords[:1], strict=True):
            length = math.hypot(x1 - x0, y1 - y0)
            if length <= _EPS:
                continue
            angles.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
            lengths.append(length)
    return angles, lengths


def _snap(poly: Polygon, tolerance: float) -> Polygon:
    """Force each near-axial edge to be exactly axial.

    The snap propagates the coordinate of the previous vertex: it closes the
    outline without creating a residual diagonal edge, which a simple rounding
    does not guarantee.
    """
    coords = [list(point) for point in list(poly.exterior.coords)[:-1]]
    n = len(coords)
    for i in range(n):
        j = (i + 1) % n
        dx = abs(coords[j][0] - coords[i][0])
        dy = abs(coords[j][1] - coords[i][1])
        if dx <= tolerance and dx <= dy:
            coords[j][0] = coords[i][0]
        elif dy <= tolerance:
            coords[j][1] = coords[i][1]
    return Polygon([(float(x), float(y)) for x, y in coords])


def _grid(values: list[float], tolerance: float) -> dict[float, float]:
    """Group nearby coordinates and return the representative of each group.

    Increasing sweep: a group is opened, values are aggregated into it as long
    as the gap to the **previous** value stays under ``tolerance``, and the
    representative is the mean of the group. The grouping is therefore
    transitive by construction — two values more than ``tolerance`` apart can
    end up together if a chain links them, which is the intended behaviour for
    a run of partitions.
    """
    if not values:
        return {}
    sorted_lines = sorted(values)
    groups: list[list[float]] = [[sorted_lines[0]]]
    for value in sorted_lines[1:]:
        if value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    mapping: dict[float, float] = {}
    for group in groups:
        representative = sum(group) / len(group)
        for value in group:
            mapping[value] = representative
    return mapping


def _stitch(polygons: list[Polygon], tolerance: float) -> list[Polygon]:
    r"""Snap rooms back together onto a common grid, so they tile exactly.

    In MSD an ``area`` is the **interior** surface of a room: neighbouring
    rooms are separated by the thickness of the partition (measured median
    :math:`0{,}209\\,\\mathrm{m}` of wall, :math:`0{,}067\\,\\mathrm{m}` gap
    between rooms; only 1.7% are contiguous). ``archlux``'s model, in
    contrast, assumes zero-thickness partitions and an exact tiling of the
    outline — ``certify.proof`` rejects any area gap.

    The abscissas and ordinates of every vertex of the apartment are therefore
    quantized onto a common grid: two edges less than ``tolerance`` apart
    become **the same** edge, halfway between. The rooms then touch exactly,
    and the real thickness is still carried by ``Wall.thickness``.

    This is a **transformation of the corpus**, not a correction: it moves
    partitions by at most ``tolerance / 2``. Any publication must cite the
    value used and the area bias it induces.
    """
    xs: list[float] = []
    ys: list[float] = []
    for poly in polygons:
        for x, y in list(poly.exterior.coords)[:-1]:
            xs.append(float(x))
            ys.append(float(y))
    grid_x = _grid(xs, tolerance)
    grid_y = _grid(ys, tolerance)
    stitched: list[Polygon] = []
    for poly in polygons:
        coords = [(grid_x[float(x)], grid_y[float(y)]) for x, y in list(poly.exterior.coords)[:-1]]
        # Snapping can flatten an edge: remove consecutive vertices that became
        # identical, otherwise shapely returns an invalid polygon.
        clean: list[tuple[float, float]] = []
        for point in coords:
            if not clean or point != clean[-1]:
                clean.append(point)
        if len(clean) >= 2 and clean[0] == clean[-1]:
            clean.pop()
        if len(clean) < 4:
            return []
        stitched.append(Polygon(clean))
    return stitched


def _wall_segment(poly: Polygon) -> LineString | None:  # lang-ok: kept private identifier
    """Long axis of a partition, from its minimum rotated bounding rectangle."""
    rect = poly.minimum_rotated_rectangle
    if not isinstance(rect, Polygon) or rect.is_empty:
        return None
    coords = list(rect.exterior.coords)[:-1]
    if len(coords) != 4:
        return None
    sides = [
        (math.dist(coords[i], coords[(i + 1) % 4]), coords[i], coords[(i + 1) % 4])
        for i in range(4)
    ]
    sides.sort(key=lambda c: c[0])
    thickness = sides[0][0]
    if thickness > _MAX_WALL_WIDTH:
        return None
    _, a, b = sides[-1]
    center = poly.centroid
    ux = (b[0] - a[0]) / max(math.dist(a, b), _EPS)
    uy = (b[1] - a[1]) / max(math.dist(a, b), _EPS)
    half = math.dist(a, b) / 2.0
    return LineString(
        [
            (center.x - half * ux, center.y - half * uy),
            (center.x + half * ux, center.y + half * uy),
        ]
    )


def _walls_from_polygons(polygons: list[Polygon], thicknesses: list[float]) -> tuple[Wall, ...]:
    """Convert solid partitions into axis segments, with stable identifiers."""
    walls: list[Wall] = []
    for rank, (poly, thickness) in enumerate(zip(polygons, thicknesses, strict=True)):
        segment = _wall_segment(poly)  # lang-ok: kept private identifier
        if segment is None or segment.length <= _EPS:
            continue
        (ax, ay), (bx, by) = list(segment.coords)
        walls.append(
            Wall(
                id=f"m{rank:04d}",
                a=(float(ax), float(ay)),
                b=(float(bx), float(by)),
                load_bearing=False,
                thickness=float(thickness),
            )
        )
    return tuple(walls)


def _opening_from_window(window: Polygon, walls: tuple[Wall, ...], rank: int) -> Opening | None:
    """Project an opening onto the nearest wall, in **relative** coordinates."""
    if not walls:
        return None
    center = window.centroid
    best: tuple[float, Wall] | None = None
    for wall in walls:
        distance = LineString([wall.a, wall.b]).distance(center)
        if best is None or distance < best[0]:
            best = (distance, wall)
    if best is None:
        return None
    _, wall = best
    axis = LineString([wall.a, wall.b])
    length = axis.length
    if length <= _EPS:
        return None
    s = float(axis.project(Point(center.x, center.y)) / length)
    width = float(window.minimum_rotated_rectangle.length / 4.0) if window.area > 0 else 0.0
    # Opening length = longer side of its minimum rotated bounding rectangle.
    coords = list(window.minimum_rotated_rectangle.exterior.coords)[:-1]
    if len(coords) == 4:
        width = max(math.dist(coords[i], coords[(i + 1) % 4]) for i in range(4))
    relative_width = width / length
    if not 0.0 < relative_width <= 1.0 or not 0.0 <= s <= 1.0:
        return None
    return Opening(id=f"b{rank:04d}", wall_id=wall.id, s=s, relative_width=relative_width)


def _simple_outline(rooms: list[Polygon]) -> tuple[tuple[float, float], ...] | None:
    """Outer ring of the union of rooms, or ``None`` if it is not simple.

    A plan whose union is a ``MultiPolygon`` (apartment in two pieces) or
    pierced by an inner ring cannot be represented: ``Plan.outline`` is a
    single ring, and ``certify.proof`` compares a union area to the area of
    **this** outline. Silently plugging the hole would fabricate a gap that
    does not exist.
    """
    union = unary_union(rooms)
    if not isinstance(union, Polygon) or union.is_empty:
        return None
    if list(union.interiors):
        return None
    return tuple((float(x), float(y)) for x, y in list(union.exterior.coords)[:-1])


def _read_groups(
    path: Path, excluded_types: frozenset[str]
) -> dict[str, list[tuple[str, str, str, str, str]]]:
    """Group the CSV by apartment, keeping only the useful entities.

    Each entity is ``(kind, subtype, wkt, area_id, site_id)``. The last two
    are not used for the geometry: they carry the join to the Swiss Dwellings
    simulations and the splitting unit.
    """
    kept_kinds = {("separator", "WALL"), ("separator", "COLUMN"), ("opening", "WINDOW")}
    groups: dict[str, list[tuple[str, str, str, str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8", errors="replace", newline="") as flux:
        for row in csv.DictReader(flux):
            kind = row["entity_type"]
            subtype = row["entity_subtype"]
            if kind == "area":
                if subtype in excluded_types:
                    continue
            elif (kind, subtype) not in kept_kinds:
                continue
            groups[row["apartment_id"]].append(
                (
                    kind,
                    subtype,
                    row["geom"],
                    _identifier(row.get("area_id", "")),
                    _identifier(row.get("site_id", "")),
                )
            )
    return groups


@renamed_parameters(
    {
        "chemin": "path",
        "referentiel": "regulation",
        "max_pieces": "max_rooms",
        "types_exclus": "excluded_types",
        "statistiques": "stats",
        "limite": "limit",
        "tolerance_calage": "snap_tolerance",
        "tolerance_recollage": "stitch_tolerance",
    }
)
def load_msd(
    path: Path | str,
    *,
    regulation: Regulation | None = None,
    max_rooms: int = 15,
    max_rectangles: int = 8,
    snap_tolerance: float = 0.05,
    stitch_tolerance: float = 0.20,
    excluded_types: frozenset[str] = EXCLUDED_TYPES,
    stats: LoadStatistics | None = None,
    limit: int | None = None,
) -> Iterator[MSDApartment]:
    """Convert the MSD CSV into apartments usable by ``archlux``.

    Parameters
    ----------
    path : Path or str
        MSD CSV (``mds_V2_*.csv``), columns ``apartment_id``, ``entity_type``,
        ``entity_subtype``, ``geom`` (WKT, metres).
    regulation : Regulation or None, optional
        Regulatory thresholds attached to the context. ``None`` = ``min_areas=()``
        **and** ``min_width=0``, the neutral case: MSD carries no regulation.

        Not neutralizing ``min_width`` is a costly trap. Its default value
        (1.80 m) applies to **every sub-rectangle**, including those produced
        by decomposing an L-shaped room — yet a sub-rectangle is a decomposition
        artefact, not a room: a 1.2 m strip is perfectly normal there. The real
        plan then falls outside its own polytope, ``legalize`` widens the
        strips to meet the threshold, the tiling tears, and ``certify.proof``
        rejects for a "gap". Measured: 87% failures on MSD with the default,
        0% without.
    max_rooms : int, optional
        Cap on **sub-rectangles** per apartment, after decomposition. Default
        15, the reference of the `ARCHITECTURE.md` §9 budgets.
    max_rectangles : int, optional
        Cap per room, passed to
        :func:`~archlux.geom.rectilinear.decompose`.
    snap_tolerance : float, optional
        Maximum gap, in metres, under which an edge is snapped onto an axis.
    stitch_tolerance : float, optional
        Maximum gap, in metres, under which two edges of neighbouring rooms
        are merged into one (see :func:`_recoller`). Default 0.20 m: this is
        the value that maximises retention on MSD (22%), the measured median
        gap between neighbouring rooms being 0.067 m and the median partition
        thickness 0.209 m.
    excluded_types : frozenset of str, optional
        ``area`` subtypes discarded. See :data:`EXCLUDED_TYPES`.
    stats : LoadStatistics or None, optional
        Accumulator updated as iteration proceeds: number read, number kept,
        and breakdown of rejection reasons.
    limit : int or None, optional
        Stop after this many **kept** apartments.

    Yields
    ------
    MSDApartment
        Straightened plan, context, merges to pass to ``legalize``.

    Raises
    ------
    InvariantViolation
        File missing, or missing the expected columns.

    Notes
    -----
    The returned geometry is **exact in the corpus's sense**, not legalized: it
    may perfectly well violate ``verify_exactly``. This is precisely what a
    benchmark must measure before correction.
    """
    path = Path(path)
    if not path.is_file():
        raise InvariantViolation((f"MSD corpus not found: {path}",))
    stats = stats if stats is not None else LoadStatistics()
    active_regulation = (
        regulation if regulation is not None else Regulation(min_areas=(), min_width=0.0)
    )
    groups = _read_groups(path, excluded_types)

    for id, entities in groups.items():
        stats.read += 1
        if limit is not None and stats.kept >= limit:
            return
        result = _convert(
            id,
            entities,
            active_regulation=active_regulation,
            max_rooms=max_rooms,
            max_rectangles=max_rectangles,
            snap_tolerance=snap_tolerance,
            stitch_tolerance=stitch_tolerance,
        )
        if isinstance(result, str):
            stats.rejections[result] += 1
            continue
        stats.kept += 1
        yield result


def _decomposition_rejection(failure: InvariantViolation) -> str:
    """The loading-statistics reason for a room :func:`decompose` refused.

    Matches the messages ``decompose`` raises today. The match used to look for the
    French messages of before the English rename, so every refusal fell through to
    "room not decomposable".

    Parameters
    ----------
    failure : InvariantViolation
        The refusal raised by :func:`archlux.geom.rectilinear.decompose`.

    Returns
    -------
    str
        ``"room not axis-aligned"``, ``"room over-fragmented"`` or
        ``"room not decomposable"``.
    """
    reason = str(failure.violations[0])
    if "diagonal edge" in reason:
        return "room not axis-aligned"
    if "too many rectangles" in reason:
        return "room over-fragmented"
    return "room not decomposable"


def _convert(
    id: str,
    entities: list[tuple[str, str, str, str, str]],
    *,
    active_regulation: Regulation,
    max_rooms: int,
    max_rectangles: int,
    snap_tolerance: float,
    stitch_tolerance: float,
) -> MSDApartment | str:
    """Convert an apartment, or return the **rejection reason** in plain text."""
    raw_rooms: list[tuple[str, Polygon]] = []
    source_areas: list[str] = []
    raw_walls: list[Polygon] = []
    raw_columns: list[Polygon] = []
    raw_windows: list[Polygon] = []
    site = next((s for _, _, _, _, s in entities if s), "")
    for kind, subtype, text, area_id, _site in entities:
        try:
            shape = wkt.loads(text)
        except (ShapelyError, TypeError):  # unreadable third-party WKT: a rejection, not a bug
            return "unreadable wkt"
        if not isinstance(shape, Polygon) or shape.is_empty:
            continue
        if kind == "area":
            raw_rooms.append((subtype, shape))
            source_areas.append(area_id)
        elif subtype == "WALL":
            raw_walls.append(shape)
        elif subtype == "COLUMN":
            raw_columns.append(shape)
        else:
            raw_windows.append(shape)

    if not raw_rooms:
        return "no habitable room"
    if len(raw_rooms) > max_rooms:
        return "too many rooms before decomposition"

    angles, lengths = _angles_and_lengths(  # lang-ok: kept private identifier
        raw_walls or [shape for _, shape in raw_rooms]
    )
    if not angles:
        return "no usable edge"
    try:
        theta = dominant_direction(angles, lengths, period=90.0)
    except InvariantViolation:
        return "no dominant direction"

    def straighten(shape: Polygon) -> Polygon:
        return _snap(affinity.rotate(shape, -theta, origin=(0.0, 0.0)), snap_tolerance)

    straightened = [straighten(shape) for _, shape in raw_rooms]
    if any(not d.is_valid or d.area <= _EPS for d in straightened):
        return "room degenerate after snapping to axes"
    # Snap back together BEFORE decomposing: decomposition assumes exact edges, and
    # it is the snapping step that makes neighbouring rooms contiguous.
    room_polygons = _stitch(straightened, stitch_tolerance)
    if not room_polygons:
        return "degenerate re-snapping"
    if any(not d.is_valid or d.area <= _EPS for d in room_polygons):
        return "room degenerate after re-snapping"

    rooms: list[Room] = []
    merges: list[RectilinearRoom] = []
    for rank, ((subtype, _), straight) in enumerate(zip(raw_rooms, room_polygons, strict=True)):
        try:
            fragment = decompose(
                straight,
                id=f"p{rank:03d}",
                room_type=subtype.lower(),
                max_rectangles=max_rectangles,
            )
        except InvariantViolation as failure:
            return _decomposition_rejection(failure)
        rooms.extend(fragment.rectangles)
        if len(fragment.rectangles) > 1:
            merges.append(fragment)

    if len(rooms) > max_rooms:
        return "too many sub-rectangles after decomposition"

    outline = _simple_outline(room_polygons)
    if outline is None:
        return "outline not simple"

    walls = _walls_from_polygons(
        [straighten(m) for m in raw_walls],
        [float(m.minimum_rotated_rectangle.length / 4.0) for m in raw_walls],
    )
    openings = tuple(
        opening
        for opening in (
            _opening_from_window(straighten(b), walls, rank) for rank, b in enumerate(raw_windows)
        )
        if opening is not None
    )
    columns = tuple(
        (float(straighten(p).centroid.x), float(straighten(p).centroid.y)) for p in raw_columns
    )

    plan = Plan(rooms=tuple(rooms), walls=walls, openings=openings, outline=outline)
    context = Context(
        # MSD does not annotate load-bearing status: no wall is declared load-bearing.
        structure=Structure(load_bearing_walls=(), columns=columns),
        orientation=Orientation(deg=theta),
        outline=outline,
        regulation=active_regulation,
        program=tuple(sorted({subtype.lower() for subtype, _ in raw_rooms})),
    )
    return MSDApartment(
        id=id,
        plan=plan,
        context=context,
        site_id=site,
        source_areas=tuple(source_areas),
        merges=tuple(merges),
        straightening_angle=theta,
    )


# ======================================================================================
# Swiss Dwellings labels
# ======================================================================================


def _flux_simulations(path: Path) -> Iterator[dict[str, str]]:
    """Read ``simulations.csv``, from the Zenodo zip or from the bare CSV."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [
                name for name in archive.namelist() if name.lower().endswith("simulations.csv")
            ]
            if not names:
                raise InvariantViolation((f"no simulations.csv in {path}",))
            with archive.open(names[0]) as raw:
                envelope = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
                yield from csv.DictReader(envelope)
        return
    with path.open(encoding="utf-8", errors="replace", newline="") as file:
        yield from csv.DictReader(file)


@renamed_parameters({"chemin": "path", "colonne": "column"})
def load_sd_labels(
    path: Path | str, *, column: str = DEFAULT_SUN_COLUMN
) -> dict[tuple[str, str], tuple[float, float]]:
    """Read the Swiss Dwellings simulations, indexed by ``(apartment, room)``.

    Parameters
    ----------
    path : Path or str
        ``swiss-dwellings-v3.0.0.zip`` as downloaded from Zenodo, or the
        extracted ``simulations.csv``.
    column : str, optional
        Irradiance column to keep. See :data:`DEFAULT_SUN_COLUMN` — and its
        warning: **this is not an sDA**.

    Returns
    -------
    dict
        ``(apartment_id, area_id) -> (value, area)``. The area comes from
        ``layout_area`` and is used to weight the per-apartment aggregation.

    Raises
    ------
    InvariantViolation
        File missing, archive without ``simulations.csv``, or unknown column.

    Notes
    -----
    The ``area_id`` values are normalized: MSD writes them as a float, Swiss
    Dwellings as an integer. Without this normalization the join yields 0%.
    """
    path = Path(path)
    if not path.is_file():
        raise InvariantViolation((f"simulations not found: {path}",))
    table: dict[tuple[str, str], tuple[float, float]] = {}
    known = False
    for row in _flux_simulations(path):
        if not known:
            if column not in row:
                raise InvariantViolation((f"column {column!r} missing from the simulations",))
            known = True
        try:
            value = float(row[column])
            surface = float(row.get("layout_area") or 0.0)
        except (TypeError, ValueError):
            continue
        table[(row["apartment_id"], _identifier(row["area_id"]))] = (
            value,
            surface,
        )
    if not table:
        raise InvariantViolation((f"no simulation read from {path}",))
    return table


@renamed_parameters(
    {"appartement": "apartment", "etiquettes": "labels", "couverture_min": "min_coverage"}
)
def label(
    apartment: MSDApartment,
    labels: dict[tuple[str, str], tuple[float, float]],
    *,
    min_coverage: float = 1.0,
) -> float | None:
    """Aggregate the irradiance of an apartment's rooms, weighted by area.

    Parameters
    ----------
    apartment : MSDApartment
        Must carry ``source_areas`` — the ``area_id`` values from before
        decomposition.
    labels : dict
        Table returned by :func:`load_sd_labels`.
    min_coverage : float, optional
        Minimum share of rooms that must be matched. Default ``1.0``: **all**
        of them. A partially simulated apartment gives an average over a
        subset chosen by data availability, not by chance — accepting it
        would introduce a silent bias into the target.

    Returns
    -------
    float or None
        Weighted average, or ``None`` if coverage is insufficient or if the
        matched areas are all zero.

    Notes
    -----
    Technical spaces — shafts, elevator cages — have **no** simulation: there
    is no light to simulate there. They are already excluded upstream by
    :data:`EXCLUDED_TYPES`, so coverage bears only on habitable rooms, matched
    at 98-99.5% depending on type.
    """
    if not apartment.source_areas:
        return None
    found = [
        labels[(apartment.id, area)]
        for area in apartment.source_areas
        if (apartment.id, area) in labels
    ]
    coverage = len(found) / len(apartment.source_areas)
    if coverage < min_coverage or not found:
        return None
    weights = np.array([surface for _, surface in found], dtype=float)
    values = np.array([value for value, _ in found], dtype=float)
    if float(weights.sum()) <= 0.0:
        return None
    return float(np.average(values, weights=weights))


@renamed_parameters({"appartements": "apartments"})
def split_by_site(
    apartments: Sequence[MSDApartment],
    *,
    seed: int,
    parts: tuple[float, float, float] = (0.6, 0.2, 0.2),
) -> tuple[list[MSDApartment], list[MSDApartment], list[MSDApartment]]:
    """Split into train / calibration / test **by site**, never by plan.

    Two apartments on the same site share urban mask, climate and orientation.
    Assigning them at random would leak this information between train and
    calibration: the announced conformal coverage would then be too
    optimistic, and **nothing would signal it** — the silent error that
    `ARCHITECTURE.md` §10 declares fatal. The split therefore operates on
    ``site_id``.

    Parameters
    ----------
    apartments : sequence of MSDApartment
        Corpus to split. Those without ``site_id`` are rejected rather than
        placed in a shared dummy site, which would be the very leak this
        avoids.
    seed : int
        Seed, **mandatory and with no default** (`ARCHITECTURE.md` §7).
    parts : tuple of float, optional
        Targeted proportions, in **sites**. The apartment count deviates from
        them, since sites do not all have the same size.

    Returns
    -------
    tuple
        ``(train, calibration, test)``.

    Raises
    ------
    InvariantViolation
        Missing ``site_id``, non-positive proportions, or fewer than three
        sites.
    """
    if not apartments:
        raise InvariantViolation(("empty corpus: nothing to split",))
    if any(not a.site_id for a in apartments):
        raise InvariantViolation(("missing site_id: split impossible",))
    if any(p <= 0.0 for p in parts) or abs(sum(parts) - 1.0) > 1e-9:
        raise InvariantViolation((f"invalid parts: {parts}",))
    sites = sorted({a.site_id for a in apartments})
    if len(sites) < 3:
        raise InvariantViolation((f"{len(sites)} site(s): three-way split impossible",))
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(sites))
    shuffled = [sites[int(i)] for i in order]
    n_train = max(1, round(parts[0] * len(shuffled)))
    n_cal = max(1, round(parts[1] * len(shuffled)))
    n_cal = min(n_cal, len(shuffled) - n_train - 1)
    attribution = {s: 0 for s in shuffled[:n_train]}
    test_start = n_train + n_cal
    attribution.update({s: 1 for s in shuffled[n_train:test_start]})
    attribution.update({s: 2 for s in shuffled[test_start:]})
    batches: tuple[list[MSDApartment], list[MSDApartment], list[MSDApartment]] = (
        [],
        [],
        [],
    )
    for apartment in apartments:
        batches[attribution[apartment.site_id]].append(apartment)
    return batches


__getattr__ = lazy_aliases(
    __name__,
    {
        "AppartementMSD": Alias(MSDApartment, "archlux.data.loaders.MSDApartment"),
        "StatistiquesChargement": Alias(LoadStatistics, "archlux.data.loaders.LoadStatistics"),
        "charger_msd": Alias(load_msd, "archlux.data.loaders.load_msd"),
        "charger_etiquettes_sd": Alias(load_sd_labels, "archlux.data.loaders.load_sd_labels"),
        "etiqueter": Alias(label, "archlux.data.loaders.label"),
        "decouper_par_site": Alias(split_by_site, "archlux.data.loaders.split_by_site"),
        "COLONNE_SOLEIL_DEFAUT": Alias(
            DEFAULT_SUN_COLUMN, "archlux.data.loaders.DEFAULT_SUN_COLUMN"
        ),
        "TYPES_EXCLUS": Alias(EXCLUDED_TYPES, "archlux.data.loaders.EXCLUDED_TYPES"),
    },
)
