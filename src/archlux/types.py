"""Data model. No dependency: everyone depends on this module.

Absolute rules (`ARCHITECTURE.md` §6), checked by the property tests:

- every type is ``frozen=True, slots=True``: never any in-place mutation;
- the **absolute** position of an opening is never stored, always derived;
- a legalized plan **always** carries its certificate;
- :class:`GeometricProof` has **no** probability field;
- :class:`PerformanceBound` **always** carries ``coverage`` and ``n_calibration``.

Units: metres, square metres, azimuth in degrees. Origin at the bottom-left corner of the
outline, ``y`` axis towards geographic north.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal, Protocol, runtime_checkable

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvalidInput, InvariantViolation

if TYPE_CHECKING:
    from archlux.arrays import VecteurF
    from archlux.export import ExportReport

__all__ = [
    "FIELDS_VECTOR",
    "INDICATOR_SENSE",
    "Certificate",
    "Context",
    "Fingerprintable",
    "GeometricProof",
    "Indicator",
    "Manifest",
    "ModelTrace",
    "Opening",
    "Orientation",
    "PerformanceBound",
    "Plan",
    "Point",
    "Regulation",
    "Room",
    "Structure",
    "Wall",
    "indicator_sign",
    "vectorize",
]

Point = tuple[float, float]

Indicator = Literal["sDA", "ASE", "UDI", "vue"]
"""Daylight indicator modelled by a surrogate and bounded by a certificate. Written once:
``PerformanceBound``, the ``Surrogate`` protocol, the surrogates and the calibration all
share it."""

INDICATOR_SENSE: Final[MappingProxyType[Indicator, str]] = MappingProxyType(
    {"sDA": ">=", "ASE": "<=", "UDI": ">=", "vue": ">="}
)
"""Comparison direction of each indicator: ``\"<=\"`` where lower is better (ASE, glare),
``\">=\"`` otherwise. Single source for the sign flip and the report/calibration
formatting that used to each spell out ``indicator == "ASE"`` (PLAN.md phase 4, block 6)."""


def indicator_sign(indicator: Indicator) -> float:
    """``-1.0`` where lower is better (ASE), ``1.0`` otherwise: the surrogates' sign flip."""
    return -1.0 if INDICATOR_SENSE[indicator] == "<=" else 1.0


@runtime_checkable
class Fingerprintable(Protocol):
    """A model that can name its own weights fingerprint.

    :func:`archlux.uq.gestion._model_fingerprint` reads this attribute first, before
    falling back to guessing at hardcoded attribute names (``W1``, ``b1``, ...): a
    model implementing this protocol survives an internal rename that the guessing
    would silently miss. Third-party models (e.g. a raw ``torch`` module) are not
    expected to implement it; the guessing fallback stays for them.
    """

    @property
    def weights_fingerprint(self) -> str:
        """SHA-256 of the trained weights, stable for identical weights."""
        ...


# ======================================================================================
# Geometry
# ======================================================================================


@dataclass(frozen=True, slots=True, kw_only=True)
class Room:
    """Rectangular room, in metres, bottom-left corner at ``(x, y)``.

    Attributes
    ----------
    id : str
        Stable identifier, unique within a plan. It is a sort key: the iteration order
        is always explicit, never that of a ``set``.
    type : str
        Program category (``"living_room"``, ``"bathroom"``, ...). Determines the regulatory
        thresholds through :class:`Regulation`.
    x, y, w, h : float
        Position and dimensions, in metres.
    """

    id: str
    type: str
    x: float
    y: float
    w: float
    h: float

    @property
    def area(self) -> float:
        """Area, in square metres."""
        return self.w * self.h

    @property
    def center(self) -> Point:
        """Geometric center, used by ``geom.graphe.deduce_order``."""
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)


@dataclass(frozen=True, slots=True, kw_only=True)
class Wall:
    """Wall segment between two points, load-bearing or not.

    Attributes
    ----------
    porteur : bool
        A load-bearing wall is fixed: ``geom`` keeps every room on its side (one
        inequality per room, see :class:`archlux.geom.graphe.WallSide`), and
        ``certify.proof`` checks that no room crosses it.
    """

    id: str
    a: Point
    b: Point
    load_bearing: bool = False
    thickness: float = 0.10

    @property
    def length(self) -> float:
        """Length of the segment, in metres."""
        return math.dist(self.a, self.b)


@dataclass(frozen=True, slots=True, kw_only=True)
class Opening:
    """Opening defined **relatively to its wall**, never in absolute coordinates.

    Storing an absolute position desynchronizes walls and windows as soon as the solver
    moves a partition: `ARCHITECTURE.md` §10 makes it a fatal anti-pattern. The absolute
    position is derived on demand by :meth:`absolute_segment`.

    Attributes
    ----------
    s : float
        Abscissa of the center along the wall, in ``[0, 1]``.
    largeur_rel : float
        Width as a fraction of the wall length, in ``]0, 1]``.
    """

    id: str
    wall_id: str
    s: float
    relative_width: float
    sill_height: float = 1.00
    head_height: float = 2.15

    def __post_init__(self) -> None:
        """Refuse ``s`` outside ``[0, 1]`` and ``relative_width`` outside ``]0, 1]``."""
        for name in ("s", "relative_width"):  # a string compared with a float is a TypeError
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise InvalidInput(
                    f"openings[{self.id}].{name}", f"must be a number, got {value!r}"
                )
        if not 0.0 <= self.s <= 1.0:
            raise InvalidInput(f"openings[{self.id}].s", f"must be in [0, 1], got {self.s}")
        if not 0.0 < self.relative_width <= 1.0:
            raise InvalidInput(
                f"openings[{self.id}].relative_width",
                f"must be in ]0, 1], got {self.relative_width}",
            )

    def absolute_segment(self, wall: Wall) -> tuple[Point, Point]:
        """Derive the two ends of the opening on ``wall``.

        Parameters
        ----------
        wall : Mur
            The wall carrying this opening; its ``id`` must equal ``self.wall_id``.

        Returns
        -------
        tuple of Point
            Ends of the opening, in absolute coordinates.

        Raises
        ------
        InvariantViolation
            If ``wall.id`` does not match ``self.wall_id``.

        Complexity
        ----------
        O(1).

        Examples
        --------
        >>> from archlux.types import Opening, Wall
        >>> wall = Wall(id="m", a=(0.0, 0.0), b=(10.0, 0.0))
        >>> Opening(id="f", wall_id="m", s=0.5, relative_width=0.2).absolute_segment(wall)
        ((4.0, 0.0), (6.0, 0.0))
        """
        if wall.id != self.wall_id:
            raise InvariantViolation(
                (f"opening {self.id} carried by {self.wall_id}, derived on {wall.id}",)
            )
        (ax, ay), (bx, by) = wall.a, wall.b
        length = wall.length
        # Unit direction of the wall; a degenerate wall would divide by zero, which the
        # guard below turns into a violated invariant rather than a NaN.
        if length == 0.0:
            raise InvariantViolation((f"wall {wall.id} has zero length",))
        ux, uy = (bx - ax) / length, (by - ay) / length
        cx, cy = ax + (bx - ax) * self.s, ay + (by - ay) * self.s
        half = self.relative_width * length / 2.0
        return ((cx - half * ux, cy - half * uy), (cx + half * ux, cy + half * uy))


@dataclass(frozen=True, slots=True)
class Plan:
    """An apartment plan, proposed or legalized.

    A **legalized** plan always carries its ``certificate``; a proposed plan never does.
    The field is therefore the marker of the state of the plan, not a decoration.

    ``trace`` holds the Frank-Wolfe sequence only on the deprecated path
    ``legalize(..., trace=True)``; its replacement, :func:`~archlux.api.legalize_trace`,
    returns the trace instead. **Not serialized** (not part of the JSON schema).
    """

    rooms: tuple[Room, ...]
    walls: tuple[Wall, ...] = ()
    openings: tuple[Opening, ...] = ()
    outline: tuple[Point, ...] = ()
    certificate: Certificate | None = None
    # Typed ``object`` on purpose: ``solve.Trace`` would add a ``types → solve`` edge,
    # which is forbidden. The trace is not serialized; only the deprecated ``trace=True``
    # path fills it (``legalize_trace`` is the replacement).
    # ``compare=False``: the trace is a diagnostic, not part of the plan's identity. With
    # it in the comparison, ``hash(plan)`` failed on the trace's arrays.
    trace: object | None = field(default=None, compare=False, repr=False)

    @property
    def room_ids(self) -> tuple[str, ...]:
        """Room identifiers, **sorted**: guarantees determinism."""
        return tuple(sorted(p.id for p in self.rooms))

    @classmethod
    def from_json(cls, path: Path | str) -> Plan:
        """Read a plan from a JSON file.

        Facade over :func:`archlux.io.json_io.charger`. The import is **local**, at call
        time: ``types`` depends on nothing at import, and no cycle exists. See ADR-5 of
        the blueprint and the nominal exemption of
        ``tests/test_dependances.py``.

        Parameters
        ----------
        path : Path or str
            Fichier source.

        Returns
        -------
        Plan
            The rebuilt plan, certificate included if present.

        Raises
        ------
        InvariantViolation
            The file does not respect the declared schema.
        """
        from archlux.io.json_io import load

        return load(path)

    def to_json(self, path: Path | str) -> None:
        """Write this plan as JSON, sorted keys, UTF-8 encoding."""
        from archlux.io.json_io import write

        write(self, path)

    def to_dxf(self, path: Path | str) -> None:
        """Write the rooms as ``LWPOLYLINE`` and the walls as ``LINE`` in a DXF file.

        Facade over :func:`archlux.export.dxf.to_dxf`, by local import, like
        :meth:`from_json` (ADR-5 exemption).

        Raises
        ------
        InvariantViolation
            The plan has a blocking geometric pathology (overlap, gap...).
        """
        from archlux.export import to_dxf

        to_dxf(self, path)

    def to_ifc(self, path: Path | str, *, validate: bool = True) -> ExportReport:
        """Write the plan as IFC4 and return the report of the export.

        Facade over :func:`archlux.export.ifc.to_ifc`. With ``validate`` (default), a
        pathological plan is not written: the report says why, nothing is raised.
        """
        from archlux.export import to_ifc

        return to_ifc(self, path, validate=validate)

    def to_svg(self, path: Path | str, *, title: str = "", walls: tuple[Wall, ...] = ()) -> None:
        """Draw the plan as a standalone SVG file, valid or not (the diagnostic use).

        Facade over :func:`archlux.export.svg.render` (exported as ``render_svg``).
        ``walls`` adds walls to draw, typically ``ctx.structure.load_bearing_walls``.
        """
        from archlux.export import render_svg

        Path(path).write_text(render_svg(self, titre=title, walls=walls), encoding="utf-8")


FIELDS_VECTOR = ("x", "y", "w", "h")
"""Per-room fields of :func:`vectorize`'s output, in order."""


def vectorize(plan: Plan) -> VecteurF:
    """Flatten a plan to ``(x, y, w, h)`` per room, in ``plan.rooms`` order.

    The plain conversion, with no solver-specific layout: a caller that only wants a
    numeric encoding of the geometry does not need to reach into ``geom`` for it. The
    decision-vector encoding a polytope actually solves against, ordered by a specific
    index and possibly counting slack variables, stays
    :func:`archlux.geom.polytope.vectorize`; the two are not interchangeable.

    Parameters
    ----------
    plan : Plan
        Plan to encode.

    Returns
    -------
    numpy.ndarray
        Shape ``(4 * len(plan.rooms),)``, ``FIELDS_VECTOR`` repeated once per room.

    Examples
    --------
    >>> plan = Plan(rooms=(Room(id="a", type="living_room", x=0.0, y=0.0, w=3.0, h=4.0),))
    >>> vectorize(plan)
    array([0., 0., 3., 4.])
    """
    # Local import: numpy is not part of `import archlux`'s budget (PLAN.md 3.13), and
    # `types` is loaded eagerly by the package root.
    import numpy as np

    return np.array([(room.x, room.y, room.w, room.h) for room in plan.rooms], dtype=float).ravel()


# ======================================================================================
# Contexte
# ======================================================================================


@dataclass(frozen=True, slots=True)
class Orientation:
    """Azimuth of the plan, in degrees. A **circular** variable: see :mod:`archlux.orient`.

    Treating 359° and 1° as far apart gives wrong conclusions. Every statistic on this
    field goes through :mod:`archlux.orient.circulaire`.
    """

    deg: float


@dataclass(frozen=True, slots=True)
class Regulation:
    """Regulatory thresholds: minimum areas and widths per room type.

    A regulation is **data**, not code: changing the regulations must never require
    changing ``geom`` or ``lmo``.
    """

    min_areas: tuple[tuple[str, float], ...]
    min_width: float = 1.80

    def min_area(self, room_type: str) -> float:
        """Minimum area required for ``room_type``, in square metres.

        Parameters
        ----------
        room_type : str
            Program category, as carried by :attr:`Room.type`.

        Returns
        -------
        float
            The threshold, or ``0.0`` if the type is not regulated. An unknown type does
            not raise: "no threshold" and "zero threshold" have the same effect on the
            polytope, and telling them apart would push the nuance onto every caller.

        Complexity
        ----------
        O(k), k = number of regulated types: a handful in practice.
        """
        for known_type, threshold in self.min_areas:
            if known_type == room_type:
                return threshold
        return 0.0


@dataclass(frozen=True, slots=True)
class Structure:
    """Load-bearing structure: what the solver may not move."""

    load_bearing_walls: tuple[Wall, ...]
    columns: tuple[Point, ...] = ()


@dataclass(frozen=True, slots=True)
class Context:
    """Everything that is not the plan: structure, orientation, outline, regulation.

    Separating ``Plan`` and ``Context`` is what lets ``legalize`` have two arguments and
    not twelve, and makes the context reusable over a batch of plans.
    """

    structure: Structure
    orientation: Orientation
    regulation: Regulation
    program: tuple[str, ...] = ()
    outline: tuple[Point, ...] = field(default=(), kw_only=True)
    """Outline of the site. Empty means "the outline of the plan": ``legalize`` takes
    ``plan.outline`` then (an outline given here wins over the plan's)."""


# ======================================================================================
# Certificate: the two guarantees, separated by construction
# ======================================================================================


@dataclass(frozen=True, slots=True)
class GeometricProof:
    """**Exact** guarantee, verified independently of the solver.

    This type holds **no probability field** and must never hold one. It is the thesis of
    the project written into the type system: a proof and a prediction are not of the
    same kind, and nothing must allow them to be mixed.
    """

    valid: bool
    overlap: bool
    gaps: bool
    areas_ok: bool
    structure_kept: bool
    max_displacement: float
    violations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """A valid proof reports no fault; a displacement is never negative or NaN.

        ``inf`` is allowed: an unbounded displacement is how an invalid proof reports a
        NaN reference.
        """
        if not self.max_displacement >= 0.0:
            raise InvalidInput("max_displacement", f"must be >= 0, got {self.max_displacement}")
        if self.valid and (
            self.overlap
            or self.gaps
            or not self.areas_ok
            or not self.structure_kept
            or self.violations
        ):
            raise InvalidInput(
                "valid", "a valid proof cannot report an overlap, a gap or any violation"
            )


Regime = Literal["exchangeable", "selected"]
"""Under which assumption a conformal bound was computed (PLAN.md batch 1.6).

- ``"exchangeable"``: the plan is exchangeable with the calibration set (for example a
  held-out plan). The nominal coverage ``1 - alpha`` is guaranteed, marginally.
- ``"selected"``: the plan was chosen by the optimizer to maximize the prediction.
  Exchangeability is broken twice, by distribution shift and by the winner's curse (the
  argmax goes where the surrogate overestimates), so the nominal coverage is **not**
  guaranteed until the chosen plan is re-evaluated by the oracle (AUDIT.md §5.3).
"""

REGIMES: tuple[Regime, ...] = ("exchangeable", "selected")


@dataclass(frozen=True, slots=True)
class PerformanceBound:
    """**Probabilistic** guarantee: an interval with coverage ``≥ 1 − α``.

    ``coverage`` and ``n_calibration`` are mandatory: a conformal bound without its
    coverage level or its calibration size cannot be verified, hence is worthless.
    ``regime`` is mandatory for the same reason: a coverage computed for an exchangeable
    plan does not hold for a plan the optimizer selected (:data:`Regime`).
    """

    indicator: Indicator
    value: float
    lower: float
    upper: float
    coverage: float
    n_calibration: int
    regime: Regime

    def __post_init__(self) -> None:
        """Refuse a bound without calibration, an out-of-range coverage or regime."""
        if self.n_calibration < 1:
            raise InvariantViolation(("n_calibration must be >= 1",))
        if not 0.0 < self.coverage <= 1.0:
            raise InvariantViolation((f"couverture hors ]0, 1] : {self.coverage}",))
        if self.regime not in REGIMES:
            raise InvariantViolation((f"unknown regime {self.regime!r}, expected {REGIMES}",))
        if not self.lower <= self.upper:
            raise InvariantViolation((f"inverted interval: {self.lower} > {self.upper}",))

    @property
    def coverage_guaranteed(self) -> bool:
        """True only when the nominal coverage holds: an exchangeable plan."""
        return self.regime == "exchangeable"


@dataclass(frozen=True, slots=True)
class ModelTrace:
    """Model fingerprint and calibration size: fields of the benchmark manifest.

    ``weights_fingerprint`` is a fingerprint (SHA), never the tensor itself.
    """

    weights_fingerprint: str
    calibration_n: int
    alpha: float

    def __post_init__(self) -> None:
        """Validate fingerprint, calibration size and level α."""
        if not self.weights_fingerprint:
            raise InvariantViolation(("weights fingerprint is required",))
        if self.calibration_n < 1:
            raise InvariantViolation(("calibration_n must be >= 1",))
        if not 0.0 < self.alpha < 1.0:
            raise InvariantViolation((f"alpha hors ]0, 1[ : {self.alpha}",))

    def __getitem__(self, key: str) -> str | int | float:
        """Dictionary access for manifest assertions (`MILESTONE-6`)."""
        try:
            return getattr(self, key)  # type: ignore[no-any-return]
        except AttributeError as exc:
            raise KeyError(key) from exc


@dataclass(frozen=True, slots=True)
class Manifest:
    """Reproducibility trace emitted at every run, without exception.

    The fields are tuples of pairs, not ``dict``: the manifest is frozen and must
    serialize in a stable order, otherwise its fingerprint is not reproducible.
    """

    version: str
    timestamp: str
    seed: int
    data_fingerprint: str | None = None
    split: str | None = None
    environment: tuple[tuple[str, str], ...] = ()
    parameters: tuple[tuple[str, str], ...] = ()
    model: ModelTrace | None = None


@dataclass(frozen=True, slots=True)
class Certificate:
    """Preuve exacte + borne probabiliste optionnelle + diagnostic dual.

    ``performance`` is ``None`` in classic legalization: there is then nothing
    probabilistic to claim, and the certificate must say so rather than suggest it.

    Attributes
    ----------
    duaux : tuple of (str, float)
        Dual prices **already translated** through ``Polytope.origins``:
        ``("load-bearing wall p1 at x = 6 m: ...", 4.1)``. Never a bare row index.
    """

    geometry: GeometricProof
    performance: PerformanceBound | None = None
    duals: tuple[tuple[str, float], ...] = ()
    manifest: Manifest | None = None

    def report(self) -> str:
        """Render the certificate as text, ``[EXACT]`` and ``[PREDICTION]`` sections.

        Facade over :func:`archlux.certify.rapport.render`, by local import: same pattern
        as :meth:`Plan.from_json`, same nominal exemption (ADR-5). The rendering itself
        stays in ``certify``: this type does not know how to format, only whom to ask.

        Returns
        -------
        str
            A readable report. The two kinds of guarantee are always visually separated
            and never aggregated into a single score.
        """
        from archlux.certify.rapport import render

        return render(self)


DEPRECATED_NAMES: Final = MappingProxyType(
    {
        "Piece": "Room",
        "Mur": "Wall",
        "Ouverture": "Opening",
        "Contexte": "Context",
        "Referentiel": "Regulation",
        "Certificat": "Certificate",
        "PreuveGeometrique": "GeometricProof",
        "BornePerformance": "PerformanceBound",
        "Manifeste": "Manifest",
        "ModeleTrace": "ModelTrace",
        "Indicateur": "Indicator",
    }
)
"""Former French names of the model classes, kept as deprecated aliases until 1.0.0 (ADR 0001,
PLAN.md 3.9 wave 2). Not part of ``__all__``."""

__getattr__ = lazy_aliases(
    __name__,
    {old: Alias(globals()[new], f"archlux.types.{new}") for old, new in DEPRECATED_NAMES.items()},
)
