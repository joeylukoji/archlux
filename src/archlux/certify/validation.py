r"""Independent validation of a final plan, one explicit constraint at a time.

:func:`verify_exactly` answers *is this plan valid?* with five booleans. This module
answers *which rule was checked, how, against which tolerance, and with what result*, so
that a certificate can say exactly what it covers. It re-checks the **final** plan from
its coordinates alone: it reads nothing the solver produced (no LP status, no polytope,
no trace), and a plan the optimizer called admissible is accepted only if every hard
constraint below holds again here.

Constraint schema
=================
Every rule is a :class:`ConstraintSpec`: an identifier, a description, a kind (``hard``:
never violated by an accepted plan; ``soft``: reported, never blocking), parameters, a
severity and a verification method. Checking it yields a :class:`ConstraintResult`:
``satisfied``, ``violated`` or ``unknown``, with the measured worst case, the tolerance
and a reason. A check that cannot run (malformed input, a missing reference, a crash of
the geometry library) is ``unknown``, never ``satisfied``.

Hard constraints
----------------
``rooms.finite`` (dimensions finite, :math:`w, h > 0`), ``rooms.non_degenerate``
(:math:`\min(w, h) > \tau_s`), ``ids.unique``, ``rooms.no_overlap``
(:math:`\max_{i<j} |R_i \cap R_j| \le \tau_o`), ``outline.covered``
(:math:`\lambda(C \setminus U) \le \tau_g`), ``outline.contains_rooms``
(:math:`\lambda(U \setminus C) \le \tau_g`), ``rooms.min_area``
(:math:`w h \ge a_{\min} - \tau_a`, a fused room as a whole), ``rooms.min_width``
(:math:`\min(w, h) \ge w_{\min} - \tau_s` for every rectangle),
``structure.not_crossed``, ``structure.not_moved``, ``walls.non_degenerate``,
``openings.on_known_wall``, ``openings.within_wall``, ``openings.disjoint``,
``openings.sill_below_head`` and, when a budget is given, ``displacement.budget``. Any
extra constraint added during optimization (a cut, a frozen contact) is passed as an
:class:`ExtraConstraint` and checked with the same rules.

Soft constraint
---------------
``rooms.connected``: the rooms form one piece through shared edges.

Nature of the evidence
======================
Each result names its method. ``exact_rational`` means the stored floats were read as
exact rationals (:class:`fractions.Fraction`) and compared in exact arithmetic against a
declared tolerance: nothing is rounded, but the tolerance is part of the claim.
``geos_tolerance`` means a floating-point computation (GEOS / Shapely) compared with a
tolerance: a **numerical validation**, not a proof. :attr:`ValidationReport.evidence`
is ``"exact"`` only when every hard constraint was settled by ``exact_rational``.

Scope
=====
The report is about the explicit geometric model above, nothing else. It does **not**
establish compliance with a building code, accessibility, fire safety, structural
soundness or constructibility, and it says nothing about daylight
(:data:`NOT_COVERED`).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import pairwise
from math import isfinite
from typing import Literal, Protocol, TypeVar

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from archlux.certify.proof import (
    _fused_area,
    _interiors,
    _outline_polygon,
    _rectangle,
    _rectangular_outline,
    _same_wall,
    _share_an_edge,
)
from archlux.errors import ArchluxError, InvalidInput
from archlux.geom.rectilinear import RectilinearRoom
from archlux.tolerances import AREA_PROOF_M2, GAP_M2, OVERLAP_M2, SNAP_M, WALL_M
from archlux.types import Context, Opening, Plan, Room, Wall

__all__ = [
    "NOT_COVERED",
    "ConstraintKind",
    "ConstraintResult",
    "ConstraintSpec",
    "ConstraintStatus",
    "Evidence",
    "ExtraConstraint",
    "Method",
    "ValidationReport",
    "linear_constraint",
    "plan_fingerprint",
    "validate_plan",
]

ConstraintKind = Literal["hard", "soft"]
"""``hard``: an accepted plan never violates it; ``soft``: reported, never blocking."""

ConstraintStatus = Literal["satisfied", "violated", "unknown"]
"""Outcome of one check; ``unknown`` when the check could not be carried out."""

Method = Literal["exact_rational", "geos_tolerance"]
"""How a result was obtained (see the module docstring)."""

Evidence = Literal["exact", "numeric", "refused"]
"""Nature of a whole report: exact arithmetic, numerical validation, or no validity."""

NOT_COVERED: tuple[str, ...] = (
    "building code compliance",
    "accessibility",
    "fire safety",
    "structural soundness",
    "constructibility",
    "daylight performance",
)
"""What a :class:`ValidationReport` never establishes, whatever its verdict."""

_REPORT_VERSION = 1

_T = TypeVar("_T", bound=str)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConstraintSpec:
    """Declaration of one checked rule.

    Attributes
    ----------
    id : str
        Stable identifier (``rooms.no_overlap``, ``cut.area_bedroom``...).
    description : str
        What the rule requires, in one sentence.
    kind : ConstraintKind
        ``hard`` or ``soft``.
    severity : str
        ``error`` for a hard rule, ``warning`` for a soft one.
    method : Method
        How the rule is checked.
    tolerance : float
        Declared tolerance of the check, in ``unit``.
    unit : str
        Unit of the measure and of the tolerance (``m``, ``m2``, ``count``).
    params : tuple of (str, str)
        Parameters of the rule (a budget, a minimum), as text.
    """

    id: str
    description: str
    kind: ConstraintKind
    severity: str
    method: Method
    tolerance: float
    unit: str
    params: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ConstraintResult:
    """Result of checking one :class:`ConstraintSpec` on one plan.

    Attributes
    ----------
    spec : ConstraintSpec
        The rule checked.
    status : ConstraintStatus
        ``satisfied``, ``violated`` or ``unknown``.
    measure : float or None
        Worst case measured, in ``spec.unit`` (``None`` when nothing could be measured).
    reason : str
        Why the status holds, in one sentence; the offending elements when violated.
    """

    spec: ConstraintSpec
    status: ConstraintStatus
    measure: float | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Serialize to JSON-compatible values.

        Returns
        -------
        dict
            The result, its spec flattened alongside.
        """
        spec = self.spec
        return {
            "id": spec.id,
            "description": spec.description,
            "kind": spec.kind,
            "severity": spec.severity,
            "method": spec.method,
            "tolerance": spec.tolerance,
            "unit": spec.unit,
            "params": [list(pair) for pair in spec.params],
            "status": self.status,
            "measure": self.measure,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ConstraintResult:
        """Rebuild a result from :meth:`to_dict`.

        Parameters
        ----------
        data : dict
            Output of :meth:`to_dict`.

        Returns
        -------
        ConstraintResult
            The same result.
        """
        params = data["params"]
        assert isinstance(params, list)
        measure = data["measure"]
        spec = ConstraintSpec(
            id=str(data["id"]),
            description=str(data["description"]),
            kind=_literal(data["kind"], ("hard", "soft")),
            severity=str(data["severity"]),
            method=_literal(data["method"], ("exact_rational", "geos_tolerance")),
            tolerance=float(str(data["tolerance"])),
            unit=str(data["unit"]),
            params=tuple((str(k), str(v)) for k, v in params),
        )
        return cls(
            spec=spec,
            status=_literal(data["status"], ("satisfied", "violated", "unknown")),
            measure=None if measure is None else float(str(measure)),
            reason=str(data["reason"]),
        )


def _literal(value: object, allowed: tuple[_T, ...]) -> _T:
    """Narrow a deserialized string to one of the allowed literals.

    Parameters
    ----------
    value : object
        Value read back.
    allowed : tuple of str
        Accepted values.

    Returns
    -------
    str
        ``value``, typed as the literal.

    Raises
    ------
    InvalidInput
        If ``value`` is not allowed: a tampered report is refused, not reinterpreted.
    """
    for candidate in allowed:
        if value == candidate:
            return candidate
    raise InvalidInput("report", f"{value!r} is not one of {allowed}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationReport:
    """Every constraint checked on one plan, and what follows from them.

    Attributes
    ----------
    results : tuple of ConstraintResult
        One result per constraint checked, in a fixed order.
    not_applicable : tuple of (str, str)
        Constraints skipped, with the reason (no budget given, no opening...).
    plan_fingerprint : str
        :func:`plan_fingerprint` of the plan checked: the report is about that plan only.
    scope : tuple of str
        What the report does not establish (:data:`NOT_COVERED`).
    """

    results: tuple[ConstraintResult, ...]
    not_applicable: tuple[tuple[str, str], ...] = ()
    plan_fingerprint: str = ""
    scope: tuple[str, ...] = field(default=NOT_COVERED)

    @property
    def valid(self) -> bool:
        """``True`` iff every hard constraint is ``satisfied`` (none violated nor unknown).

        Returns
        -------
        bool
            The verdict of the report.
        """
        return all(r.status == "satisfied" for r in self.results if r.spec.kind == "hard")

    @property
    def violated(self) -> tuple[ConstraintResult, ...]:
        """Hard and soft results that are ``violated``.

        Returns
        -------
        tuple of ConstraintResult
            The violated constraints, in check order.
        """
        return tuple(r for r in self.results if r.status == "violated")

    @property
    def unknown(self) -> tuple[ConstraintResult, ...]:
        """Results that could not be established.

        Returns
        -------
        tuple of ConstraintResult
            The constraints left ``unknown``, in check order.
        """
        return tuple(r for r in self.results if r.status == "unknown")

    @property
    def evidence(self) -> Evidence:
        """``exact`` when every hard result is exact, ``numeric`` otherwise; ``refused``.

        Returns
        -------
        Evidence
            ``refused`` for an invalid plan; ``exact`` when every hard constraint was
            settled in exact rational arithmetic; ``numeric`` when at least one relied on
            a floating-point computation with tolerance.
        """
        if not self.valid:
            return "refused"
        hard = (r for r in self.results if r.spec.kind == "hard")
        return "exact" if all(r.spec.method == "exact_rational" for r in hard) else "numeric"

    def result(self, constraint_id: str) -> ConstraintResult:
        """The result of one constraint, by identifier.

        Parameters
        ----------
        constraint_id : str
            Identifier of the constraint.

        Returns
        -------
        ConstraintResult
            Its result.

        Raises
        ------
        KeyError
            If that constraint was not checked.
        """
        for r in self.results:
            if r.spec.id == constraint_id:
                return r
        raise KeyError(constraint_id)

    def matches(self, plan: Plan) -> bool:
        """Whether this report was computed on ``plan`` (same geometry, bit for bit).

        Parameters
        ----------
        plan : Plan
            Plan the report is claimed for.

        Returns
        -------
        bool
            ``True`` iff the fingerprints agree.
        """
        return self.plan_fingerprint == plan_fingerprint(plan)

    def summary(self) -> str:
        """Plain-text summary: verdict, evidence, then one line per constraint.

        Returns
        -------
        str
            A few lines, stating the scope limits last.
        """
        verdict = "VALID" if self.valid else "NOT VALID"
        lines = [f"Geometric validation: {verdict} (evidence: {self.evidence})"]
        for r in self.results:
            measure = "-" if r.measure is None else f"{r.measure:.6g} {r.spec.unit}"
            lines.append(
                f"  [{r.spec.kind}] {r.spec.id:<26} {r.status:<9} {measure} "
                f"(tol {r.spec.tolerance:g}, {r.spec.method}): {r.reason}"
            )
        lines.extend(f"  [n/a] {cid}: {why}" for cid, why in self.not_applicable)
        lines.append("Not established: " + ", ".join(self.scope))
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        """Serialize to JSON-compatible values.

        Returns
        -------
        dict
            The report, with its verdict and evidence for readers without archlux.
        """
        return {
            "version": _REPORT_VERSION,
            "valid": self.valid,
            "evidence": self.evidence,
            "plan_fingerprint": self.plan_fingerprint,
            "results": [r.to_dict() for r in self.results],
            "not_applicable": [list(pair) for pair in self.not_applicable],
            "scope": list(self.scope),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ValidationReport:
        """Rebuild a report from :meth:`to_dict`; the verdict is recomputed, not trusted.

        Parameters
        ----------
        data : dict
            Output of :meth:`to_dict`.

        Returns
        -------
        ValidationReport
            The same report.

        Raises
        ------
        InvalidInput
            If the stored verdict or evidence disagrees with the stored results.
        """
        results, skipped, scope = data["results"], data["not_applicable"], data["scope"]
        assert isinstance(results, list) and isinstance(skipped, list)
        assert isinstance(scope, list)
        report = cls(
            results=tuple(ConstraintResult.from_dict(r) for r in results),
            not_applicable=tuple((str(a), str(b)) for a, b in skipped),
            plan_fingerprint=str(data["plan_fingerprint"]),
            scope=tuple(str(s) for s in scope),
        )
        if data.get("valid") != report.valid or data.get("evidence") != report.evidence:
            raise InvalidInput("report.valid", "stored verdict disagrees with the stored results")
        return report


class ExtraConstraint(Protocol):
    """A constraint added during optimization, checked with the original ones."""

    @property
    def spec(self) -> ConstraintSpec:
        """Declaration of the constraint."""
        ...

    def check(self, plan: Plan, ctx: Context) -> ConstraintResult:
        """Check the constraint on the final plan.

        Parameters
        ----------
        plan : Plan
            Final plan.
        ctx : Context
            Its context.

        Returns
        -------
        ConstraintResult
            The result, its ``spec`` being :attr:`spec`.
        """
        ...


_FIELDS = ("x", "y", "w", "h")


@dataclass(frozen=True, slots=True)
class _Linear:
    """``sum(coefficient * room.field) <= rhs + tolerance``, checked exactly."""

    spec: ConstraintSpec
    terms: tuple[tuple[str, str, float], ...]
    rhs: float

    def check(self, plan: Plan, ctx: Context) -> ConstraintResult:
        """Evaluate the left-hand side exactly on the plan.

        Parameters
        ----------
        plan : Plan
            Final plan.
        ctx : Context
            Unused: a linear constraint only reads room coordinates.

        Returns
        -------
        ConstraintResult
            ``unknown`` if a room is missing, the excess over ``rhs`` otherwise.
        """
        del ctx
        by_id = {room.id: room for room in plan.rooms}
        missing = sorted({room_id for room_id, _, _ in self.terms} - set(by_id))
        if missing:
            return _unknown(self.spec, f"rooms not in the plan: {missing}")
        lhs = sum(
            (Fraction(c) * Fraction(getattr(by_id[r], f)) for r, f, c in self.terms),
            Fraction(0),
        )
        excess = lhs - Fraction(self.rhs)
        ok = excess <= Fraction(self.spec.tolerance)
        return _result(self.spec, ok, float(excess), f"lhs - rhs = {float(excess):.6g}")


def linear_constraint(
    constraint_id: str,
    terms: tuple[tuple[str, str, float], ...],
    rhs: float,
    *,
    description: str = "",
    tolerance: float = SNAP_M,
) -> ExtraConstraint:
    """A hard linear inequality over room coordinates, for constraints added on the way.

    Parameters
    ----------
    constraint_id : str
        Identifier, e.g. ``cut.area_bed``.
    terms : tuple of (str, str, float)
        ``(room id, field, coefficient)``; ``field`` is one of ``x``, ``y``, ``w``, ``h``.
    rhs : float
        Right-hand side: the constraint is ``sum(coefficient * field) <= rhs``.
    description : str, optional
        Human description; a default one is derived from the terms.
    tolerance : float, optional
        Accepted excess over ``rhs``, in the unit of the terms (metres by default).

    Returns
    -------
    ExtraConstraint
        A constraint to pass to :func:`validate_plan` through ``extra``.

    Raises
    ------
    InvalidInput
        If a field is not one of ``x``, ``y``, ``w``, ``h``.

    Examples
    --------
    >>> from archlux.types import Plan, Room
    >>> cut = linear_constraint("cut.width_a", (("a", "w", -1.0),), -2.0)
    >>> plan = Plan(rooms=(Room(id="a", type="bedroom", x=0.0, y=0.0, w=3.0, h=3.0),))
    >>> cut.check(plan, None).status  # doctest: +SKIP
    'satisfied'
    """
    bad = [f for _, f, _ in terms if f not in _FIELDS]
    if bad:
        raise InvalidInput("terms", f"unknown room fields {bad}: expected one of {_FIELDS}")
    text = " + ".join(f"{c:g}*{r}.{f}" for r, f, c in terms) + f" <= {rhs:g}"
    spec = ConstraintSpec(
        id=constraint_id,
        description=description or text,
        kind="hard",
        severity="error",
        method="exact_rational",
        tolerance=tolerance,
        unit="m",
        params=(("inequality", text),),
    )
    return _Linear(spec, terms, rhs)


# --- helpers -----------------------------------------------------------------------


def _result(spec: ConstraintSpec, ok: bool, measure: float | None, reason: str) -> ConstraintResult:
    status: ConstraintStatus = "satisfied" if ok else "violated"
    return ConstraintResult(spec=spec, status=status, measure=measure, reason=reason)


def _unknown(spec: ConstraintSpec, reason: str) -> ConstraintResult:
    return ConstraintResult(spec=spec, status="unknown", measure=None, reason=reason)


def _hard(
    cid: str, description: str, method: Method, tolerance: float, unit: str, **params: object
) -> ConstraintSpec:
    return ConstraintSpec(
        id=cid,
        description=description,
        kind="hard",
        severity="error",
        method=method,
        tolerance=tolerance,
        unit=unit,
        params=tuple((k, str(v)) for k, v in params.items()),
    )


def _q(value: float) -> Fraction:
    """The float read as an exact rational.

    Parameters
    ----------
    value : float
        Stored coordinate or tolerance.

    Returns
    -------
    Fraction
        Its exact value: no rounding happens.
    """
    return Fraction(value)


def _box(room: Room) -> tuple[Fraction, Fraction, Fraction, Fraction]:
    x0, y0 = _q(room.x), _q(room.y)
    return x0, y0, x0 + _q(room.w), y0 + _q(room.h)


def _listing(items: list[str], limit: int = 5) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def _finite_rooms(plan: Plan) -> bool:
    return all(
        all(isfinite(v) for v in (r.x, r.y, r.w, r.h)) and r.w > 0.0 and r.h > 0.0
        for r in plan.rooms
    )


def _merged_ids(merges: tuple[RectilinearRoom, ...]) -> set[str]:
    return {rect.id for fused in merges for rect in fused.rectangles}


def plan_fingerprint(plan: Plan) -> str:
    """SHA-256 of the plan geometry, bit for bit (``float.hex``), certificate excluded.

    Parameters
    ----------
    plan : Plan
        Plan to fingerprint.

    Returns
    -------
    str
        Hex digest; any change of a coordinate, an id, a type or an opening changes it.
    """
    parts: list[str] = []
    for r in sorted(plan.rooms, key=lambda r: r.id):
        parts.append(
            "R|" + "|".join([r.id, r.type, *(float(v).hex() for v in (r.x, r.y, r.w, r.h))])
        )
    for w in sorted(plan.walls, key=lambda w: w.id):
        coords = (*w.a, *w.b, w.thickness)
        parts.append(
            "W|" + "|".join([w.id, str(w.load_bearing), *(float(v).hex() for v in coords)])
        )
    for o in sorted(plan.openings, key=lambda o: o.id):
        values = (o.s, o.relative_width, o.sill_height, o.head_height)
        parts.append("O|" + "|".join([o.id, o.wall_id, *(float(v).hex() for v in values)]))
    parts.extend("C|" + float(x).hex() + "|" + float(y).hex() for x, y in plan.outline)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# --- room checks -------------------------------------------------------------------


def _check_finite(plan: Plan) -> ConstraintResult:
    spec = _hard(
        "rooms.finite",
        "every room has finite x, y and positive finite w, h",
        "exact_rational",
        0.0,
        "count",
    )
    bad = [
        r.id
        for r in plan.rooms
        if not (all(isfinite(v) for v in (r.x, r.y, r.w, r.h)) and r.w > 0.0 and r.h > 0.0)
    ]
    return _result(
        spec,
        not bad,
        float(len(bad)),
        f"malformed rooms: {_listing(bad)}" if bad else "all rooms well formed",
    )


def _check_ids(plan: Plan) -> ConstraintResult:
    spec = _hard(
        "ids.unique",
        "room, wall and opening identifiers are unique",
        "exact_rational",
        0.0,
        "count",
    )
    duplicates: list[str] = []
    for kind, ids in (
        ("room", [r.id for r in plan.rooms]),
        ("wall", [w.id for w in plan.walls]),
        ("opening", [o.id for o in plan.openings]),
    ):
        counts = Counter(ids)
        duplicates.extend(f"{kind} {i}" for i, n in sorted(counts.items()) if n > 1)
    return _result(
        spec,
        not duplicates,
        float(len(duplicates)),
        f"duplicates: {_listing(duplicates)}" if duplicates else "no duplicate",
    )


def _check_non_degenerate(plan: Plan) -> ConstraintResult:
    spec = _hard(
        "rooms.non_degenerate",
        "no room side is shorter than the snapping tolerance",
        "exact_rational",
        SNAP_M,
        "m",
    )
    if not plan.rooms:
        return _result(spec, True, None, "no room")
    smallest = min(min(_q(r.w), _q(r.h)) for r in plan.rooms)
    bad = [r.id for r in plan.rooms if min(_q(r.w), _q(r.h)) <= _q(SNAP_M)]
    return _result(
        spec,
        not bad,
        float(smallest),
        f"near-zero rooms: {_listing(bad)}" if bad else "every side is long enough",
    )


def _check_overlap(plan: Plan) -> ConstraintResult:
    spec = _hard(
        "rooms.no_overlap", "no two rooms share interior area", "exact_rational", OVERLAP_M2, "m2"
    )
    boxes = [(r.id, _box(r)) for r in plan.rooms]
    worst, offenders = Fraction(0), []
    for i, (a_id, (ax0, ay0, ax1, ay1)) in enumerate(boxes):
        for b_id, (bx0, by0, bx1, by1) in boxes[i + 1 :]:
            dx, dy = min(ax1, bx1) - max(ax0, bx0), min(ay1, by1) - max(ay0, by0)
            if dx <= 0 or dy <= 0:
                continue
            area = dx * dy
            worst = max(worst, area)
            if area > _q(OVERLAP_M2):
                offenders.append(f"{a_id}|{b_id} ({float(area):.3g} m2)")
    return _result(
        spec,
        not offenders,
        float(worst),
        f"overlapping pairs: {_listing(offenders)}" if offenders else "no overlap",
    )


def _covered_lengths(
    intervals: list[tuple[Fraction, Fraction]], low: Fraction, high: Fraction
) -> tuple[Fraction, Fraction]:
    """Length of the union of ``intervals``, and of its part inside ``[low, high]``.

    Parameters
    ----------
    intervals : list of (Fraction, Fraction)
        Closed intervals, possibly overlapping.
    low, high : Fraction
        Window of the outline on the same axis.

    Returns
    -------
    tuple of Fraction
        ``(union length, union length inside the window)``, exact.
    """
    total, inside = Fraction(0), Fraction(0)
    start: Fraction | None = None
    end = Fraction(0)
    for a, b in [*sorted(intervals), (None, None)]:
        if start is not None and (a is None or a > end):
            total += end - start
            inside += max(Fraction(0), min(end, high) - max(start, low))
            start = None
        if a is None or b is None:
            break
        if start is None:
            start, end = a, b
        else:
            end = max(end, b)
    return total, inside


def _exact_coverage(
    plan: Plan, bounds: tuple[Fraction, Fraction, Fraction, Fraction]
) -> tuple[Fraction, Fraction]:
    """Exact uncovered area of a rectangular outline, and exact overhang outside it.

    A sweep over the x-slabs between consecutive vertical edges: in each slab, the union
    of the y-intervals of the rooms spanning it is merged exactly.

    Parameters
    ----------
    plan : Plan
        Plan whose rooms are swept.
    bounds : tuple of Fraction
        ``(x0, y0, x1, y1)`` of the rectangular outline.

    Returns
    -------
    tuple of Fraction
        ``(uncovered area, overhang area)``, in square metres.
    """
    x0, y0, x1, y1 = bounds
    boxes = [_box(r) for r in plan.rooms]
    xs = sorted({x0, x1, *(b[0] for b in boxes), *(b[2] for b in boxes)})
    union, inside = Fraction(0), Fraction(0)
    for left, right in pairwise(xs):
        spans = [(b[1], b[3]) for b in boxes if b[0] <= left and b[2] >= right]
        total, within = _covered_lengths(spans, y0, y1)
        width = right - left
        union += width * total
        if x0 <= left and right <= x1:
            inside += width * within
    outline_area = (x1 - x0) * (y1 - y0)
    return outline_area - inside, union - inside


def _coverage(plan: Plan, ctx: Context) -> tuple[Method, float, float]:
    """``(method, uncovered, overhang)`` areas, exact on a rectangular outline.

    Parameters
    ----------
    plan : Plan
        Plan to measure.
    ctx : Context
        Context providing the outline.

    Returns
    -------
    tuple
        The method used and the two areas, in square metres.

    Raises
    ------
    InvalidInput
        If the outline is degenerate.
    """
    bounds = _rectangular_outline(ctx.outline)
    if bounds is not None:
        uncovered, overhang = _exact_coverage(plan, bounds)
        return "exact_rational", float(uncovered), float(overhang)
    envelope = _outline_polygon(ctx.outline)
    if envelope is None:
        raise InvalidInput("ctx.outline", "degenerate outline: no tiling can be defined")
    union = unary_union([_rectangle(r) for r in plan.rooms]) if plan.rooms else Polygon()
    return (
        "geos_tolerance",
        float(envelope.difference(union).area),
        float(union.difference(envelope).area),
    )


def _check_coverage(plan: Plan, ctx: Context) -> tuple[ConstraintResult, ConstraintResult]:
    method: Method = "exact_rational" if _rectangular_outline(ctx.outline) else "geos_tolerance"
    covered = _hard(
        "outline.covered", "the rooms cover the whole outline (no gap)", method, GAP_M2, "m2"
    )
    contained = _hard(
        "outline.contains_rooms", "no room lies outside the outline", method, GAP_M2, "m2"
    )
    try:
        method, uncovered, overhang = _coverage(plan, ctx)
    except (ValueError, ArithmeticError) as err:
        return _unknown(covered, str(err)), _unknown(contained, str(err))
    return (
        _result(covered, uncovered <= GAP_M2, uncovered, f"uncovered area {uncovered:.6g} m2"),
        _result(contained, overhang <= GAP_M2, overhang, f"area outside {overhang:.6g} m2"),
    )


def _plain_area_margins(
    plan: Plan, ctx: Context, fused: set[str]
) -> tuple[list[Fraction], list[str]]:
    """Exact margin ``w h - a_min`` of every plain room with a minimum, and the offenders.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    ctx : Context
        Context providing the minimum areas.
    fused : set of str
        Sub-rectangles of fused rooms, checked as a whole elsewhere.

    Returns
    -------
    tuple of (list of Fraction, list of str)
        The margins, and one message per room below its minimum.
    """
    slack: list[Fraction] = []
    offenders: list[str] = []
    for room in plan.rooms:
        minimum = ctx.regulation.min_area(room.type)
        if room.id in fused or minimum <= 0.0:
            continue
        margin = _q(room.w) * _q(room.h) - _q(minimum)
        slack.append(margin)
        if margin + _q(AREA_PROOF_M2) < 0:
            offenders.append(f"{room.id} ({float(margin):.3g} m2 short)")
    return slack, offenders


def _check_min_area(
    plan: Plan, ctx: Context, merges: tuple[RectilinearRoom, ...]
) -> ConstraintResult:
    method: Method = "geos_tolerance" if merges else "exact_rational"
    spec = _hard(
        "rooms.min_area",
        "every room reaches the minimum area of its type",
        method,
        AREA_PROOF_M2,
        "m2",
    )
    slack, offenders = _plain_area_margins(plan, ctx, _merged_ids(merges))
    by_id = {room.id: room for room in plan.rooms}
    for fused_room in merges:
        if any(rect.id in by_id for rect in fused_room.rectangles):
            offenders.extend(_fused_area(fused_room, by_id, ctx))
    worst = float(min(slack)) if slack else None
    return _result(
        spec,
        not offenders,
        worst,
        f"below minimum: {_listing(offenders)}" if offenders else "every minimum met",
    )


def _check_min_width(plan: Plan, ctx: Context) -> ConstraintResult:
    width = ctx.regulation.min_width
    spec = _hard(
        "rooms.min_width",
        "every rectangle is at least the minimum width wide",
        "exact_rational",
        SNAP_M,
        "m",
        min_width=width,
    )
    if not plan.rooms:
        return _result(spec, True, None, "no room")
    margins = {r.id: min(_q(r.w), _q(r.h)) - _q(width) for r in plan.rooms}
    bad = [f"{rid} ({float(m):.3g} m)" for rid, m in margins.items() if m + _q(SNAP_M) < 0]
    return _result(
        spec,
        not bad,
        float(min(margins.values())),
        f"too narrow: {_listing(bad)}" if bad else f"all at least {width:g} m wide",
    )


# --- structure and walls -----------------------------------------------------------


def _check_walls(plan: Plan, ctx: Context) -> ConstraintResult:
    spec = _hard(
        "walls.non_degenerate",
        "every wall has a length above the snapping tolerance",
        "exact_rational",
        SNAP_M,
        "m",
    )
    walls = (*plan.walls, *ctx.structure.load_bearing_walls)
    if not walls:
        return _result(spec, True, None, "no wall")
    lengths = {w.id: _wall_length(w) for w in walls}
    bad = [wid for wid, length in lengths.items() if length <= SNAP_M]
    return _result(
        spec,
        not bad,
        min(lengths.values()),
        f"degenerate walls: {_listing(bad)}" if bad else "every wall has a length",
    )


def _wall_length(wall: Wall) -> float:
    (ax, ay), (bx, by) = wall.a, wall.b
    return float(abs(bx - ax) + abs(by - ay)) if ax == bx or ay == by else wall.length


def _check_not_moved(plan: Plan, ctx: Context) -> ConstraintResult:
    spec = _hard(
        "structure.not_moved",
        "a load-bearing wall the plan declares matches the structure",
        "exact_rational",
        WALL_M,
        "m",
    )
    declared = {w.id: w for w in plan.walls}
    moved = [
        w.id
        for w in ctx.structure.load_bearing_walls
        if w.id in declared and not _same_wall(w, declared[w.id])
    ]
    return _result(
        spec,
        not moved,
        float(len(moved)),
        f"moved: {_listing(moved)}" if moved else "no load-bearing wall moved",
    )


def _axis_crossing(wall: Wall, room: Room) -> Fraction:
    """Exact length of an axis-aligned wall inside the room shrunk by ``WALL_M``.

    Parameters
    ----------
    wall : Wall
        Axis-aligned load-bearing wall.
    room : Room
        Plain rectangular room.

    Returns
    -------
    Fraction
        Length of the wall strictly inside the shrunk room, in metres.
    """
    tol = _q(WALL_M)
    x0, y0, x1, y1 = _box(room)
    x0, y0, x1, y1 = x0 + tol, y0 + tol, x1 - tol, y1 - tol
    (ax, ay), (bx, by) = (tuple(map(_q, wall.a)), tuple(map(_q, wall.b)))
    if ax == bx:
        inside = x0 < ax < x1
        lo, hi = min(ay, by), max(ay, by)
        return max(Fraction(0), min(hi, y1) - max(lo, y0)) if inside else Fraction(0)
    inside = y0 < ay < y1
    lo, hi = min(ax, bx), max(ax, bx)
    return max(Fraction(0), min(hi, x1) - max(lo, x0)) if inside else Fraction(0)


def _crossings(
    plan: Plan, walls: tuple[Wall, ...], merges: tuple[RectilinearRoom, ...]
) -> Iterator[tuple[str, str, float]]:
    """``(room id, wall id, length inside)`` for every room-wall pair.

    Exact for an axis-aligned wall against a plain rectangle; GEOS for an oblique wall,
    and for a fused room, whose interior includes the seams between its parts.

    Parameters
    ----------
    plan : Plan
        Plan to check.
    walls : tuple of Wall
        Load-bearing walls.
    merges : tuple of RectilinearRoom
        Fused rooms.

    Yields
    ------
    tuple of (str, str, float)
        Room id, wall id and length of the wall inside the room, in metres.
    """
    fused_ids = {f.id for f in merges}
    fused_parts = _merged_ids(merges)
    interiors = dict(_interiors(plan, merges, WALL_M)) if merges or not _all_axis(walls) else {}
    for wall in walls:
        line = LineString([wall.a, wall.b])
        for room in plan.rooms:
            if room.id in fused_parts:
                continue
            if _is_axis(wall):
                yield room.id, wall.id, float(_axis_crossing(wall, room))
            elif room.id in interiors:
                yield room.id, wall.id, float(line.intersection(interiors[room.id]).length)
        for room_id in fused_ids & interiors.keys():
            yield room_id, wall.id, float(line.intersection(interiors[room_id]).length)


def _is_axis(wall: Wall) -> bool:
    return wall.a[0] == wall.b[0] or wall.a[1] == wall.b[1]


def _all_axis(walls: tuple[Wall, ...]) -> bool:
    return all(_is_axis(w) for w in walls)


def _check_not_crossed(
    plan: Plan, ctx: Context, merges: tuple[RectilinearRoom, ...]
) -> ConstraintResult:
    walls = ctx.structure.load_bearing_walls
    exact = not merges and _all_axis(walls)
    method: Method = "exact_rational" if exact else "geos_tolerance"
    spec = _hard(
        "structure.not_crossed",
        "no room interior contains a stretch of load-bearing wall",
        method,
        WALL_M,
        "m",
    )
    if not walls:
        return _result(spec, True, None, "no load-bearing wall")
    worst, offenders = 0.0, []
    for room_id, wall_id, length in _crossings(plan, walls, merges):
        worst = max(worst, length)
        if length > WALL_M:
            offenders.append(f"{room_id} x {wall_id} ({length:.3g} m)")
    return _result(
        spec,
        not offenders,
        worst,
        f"crossings: {_listing(offenders)}" if offenders else "no room crosses the structure",
    )


# --- openings ----------------------------------------------------------------------


def _wall_index(plan: Plan, ctx: Context) -> dict[str, Wall]:
    return {w.id: w for w in (*ctx.structure.load_bearing_walls, *plan.walls)}


def _check_on_known_wall(plan: Plan, ctx: Context) -> ConstraintResult:
    spec = _hard(
        "openings.on_known_wall",
        "every opening refers to an existing, non-degenerate wall",
        "exact_rational",
        SNAP_M,
        "m",
    )
    walls = _wall_index(plan, ctx)
    bad = [
        o.id
        for o in plan.openings
        if o.wall_id not in walls or _wall_length(walls[o.wall_id]) <= SNAP_M
    ]
    return _result(
        spec,
        not bad,
        float(len(bad)),
        f"orphan openings: {_listing(bad)}" if bad else "every opening has its wall",
    )


def _extent(opening: Opening, wall: Wall) -> tuple[Fraction, Fraction]:
    """Ends of the opening along the wall, in metres from ``wall.a``, exactly.

    Parameters
    ----------
    opening : Opening
        Opening, relative to its wall.
    wall : Wall
        Its wall.

    Returns
    -------
    tuple of Fraction
        ``(start, end)`` along the wall, in metres.
    """
    length = _q(_wall_length(wall))
    middle, half = _q(opening.s) * length, _q(opening.relative_width) * length / 2
    return middle - half, middle + half


def _check_within_wall(plan: Plan, ctx: Context) -> ConstraintResult:
    spec = _hard(
        "openings.within_wall",
        "every opening lies entirely on its wall",
        "exact_rational",
        SNAP_M,
        "m",
    )
    walls = _wall_index(plan, ctx)
    worst, bad = Fraction(0), []
    for o in plan.openings:
        wall = walls.get(o.wall_id)
        if wall is None:
            continue  # reported by openings.on_known_wall
        start, end = _extent(o, wall)
        excess = max(Fraction(0), -start, end - _q(_wall_length(wall)))
        worst = max(worst, excess)
        if excess > _q(SNAP_M):
            bad.append(f"{o.id} ({float(excess):.3g} m beyond)")
    return _result(
        spec,
        not bad,
        float(worst),
        f"overhanging openings: {_listing(bad)}" if bad else "every opening on its wall",
    )


def _check_openings_disjoint(plan: Plan, ctx: Context) -> ConstraintResult:
    spec = _hard(
        "openings.disjoint",
        "two openings on the same wall do not overlap",
        "exact_rational",
        SNAP_M,
        "m",
    )
    walls = _wall_index(plan, ctx)
    spans: dict[str, list[tuple[str, Fraction, Fraction]]] = {}
    for o in plan.openings:
        if o.wall_id in walls:
            spans.setdefault(o.wall_id, []).append((o.id, *_extent(o, walls[o.wall_id])))
    worst, bad = Fraction(0), []
    for items in spans.values():
        for i, (a, a0, a1) in enumerate(items):
            for b, b0, b1 in items[i + 1 :]:
                shared = min(a1, b1) - max(a0, b0)
                worst = max(worst, shared)
                if shared > _q(SNAP_M):
                    bad.append(f"{a}|{b} ({float(shared):.3g} m)")
    return _result(
        spec,
        not bad,
        float(worst),
        f"overlapping openings: {_listing(bad)}" if bad else "no two openings overlap",
    )


def _check_sill(plan: Plan) -> ConstraintResult:
    spec = _hard(
        "openings.sill_below_head",
        "0 <= sill height < head height for every opening",
        "exact_rational",
        0.0,
        "m",
    )
    bad = [
        o.id
        for o in plan.openings
        if not (isfinite(o.sill_height) and isfinite(o.head_height))
        or o.sill_height < 0.0
        or o.sill_height >= o.head_height
    ]
    return _result(
        spec,
        not bad,
        float(len(bad)),
        f"inconsistent heights: {_listing(bad)}" if bad else "heights consistent",
    )


# --- displacement and connectivity -------------------------------------------------


def _check_budget(plan: Plan, reference: Plan | None, budget: float) -> ConstraintResult:
    spec = _hard(
        "displacement.budget",
        "no room coordinate moved more than the budget",
        "exact_rational",
        SNAP_M,
        "m",
        budget=budget,
    )
    if reference is None:
        return _unknown(spec, "a budget was given without the reference plan to measure it")
    by_id = {r.id: r for r in reference.rooms}
    worst = Fraction(0)
    for room in plan.rooms:
        origin = by_id.get(room.id)
        if origin is None:
            continue
        for name in _FIELDS:
            worst = max(worst, abs(_q(getattr(room, name)) - _q(getattr(origin, name))))
    ok = worst <= _q(budget) + _q(SNAP_M)
    return _result(spec, ok, float(worst), f"max displacement {float(worst):.6g} m vs {budget:g} m")


def _check_connected(plan: Plan) -> ConstraintResult:
    spec = ConstraintSpec(
        id="rooms.connected",
        description="the rooms form one piece through shared edges",
        kind="soft",
        severity="warning",
        method="exact_rational",
        tolerance=SNAP_M,
        unit="count",
    )
    rooms = list(plan.rooms)
    if not rooms:
        return _result(spec, True, 0.0, "no room")
    unreached, components = set(range(len(rooms))), 0
    while unreached:
        components += 1
        frontier = [unreached.pop()]
        while frontier:
            current = rooms[frontier.pop()]
            linked = {k for k in unreached if _share_an_edge(current, rooms[k])}
            unreached -= linked
            frontier.extend(linked)
    return _result(spec, components == 1, float(components), f"{components} connected component(s)")


# --- entry point -------------------------------------------------------------------

_Check = Callable[[], "ConstraintResult | tuple[ConstraintResult, ...]"]


def _guarded(spec_id: str, check: _Check) -> tuple[ConstraintResult, ...]:
    """Run one check; a crash of the check is ``unknown``, never ``satisfied``.

    Parameters
    ----------
    spec_id : str
        Identifier reported if the check crashes.
    check : callable
        The check, without arguments.

    Returns
    -------
    tuple of ConstraintResult
        Its results, or one ``unknown`` result naming the exception.
    """
    try:
        out = check()
    except (ArchluxError, ArithmeticError, ValueError, AttributeError) as err:
        spec = _hard(spec_id, "check could not run", "exact_rational", 0.0, "count")
        return (_unknown(spec, f"check failed: {type(err).__name__}: {err}"),)
    return out if isinstance(out, tuple) else (out,)


def _geometric_checks(
    plan: Plan, ctx: Context, merges: tuple[RectilinearRoom, ...]
) -> list[tuple[str, _Check]]:
    return [
        ("rooms.non_degenerate", lambda: _check_non_degenerate(plan)),
        ("rooms.no_overlap", lambda: _check_overlap(plan)),
        ("outline", lambda: _check_coverage(plan, ctx)),
        ("rooms.min_area", lambda: _check_min_area(plan, ctx, merges)),
        ("rooms.min_width", lambda: _check_min_width(plan, ctx)),
        ("structure.not_crossed", lambda: _check_not_crossed(plan, ctx, merges)),
    ]


def _unknown_geometry(reason: str) -> tuple[ConstraintResult, ...]:
    ids = (
        "rooms.non_degenerate",
        "rooms.no_overlap",
        "outline.covered",
        "outline.contains_rooms",
        "rooms.min_area",
        "rooms.min_width",
        "structure.not_crossed",
    )
    return tuple(
        _unknown(_hard(i, "not checked", "exact_rational", 0.0, "count"), reason) for i in ids
    )


def validate_plan(
    plan: Plan,
    ctx: Context,
    *,
    reference: Plan | None = None,
    budget: float | None = None,
    merges: tuple[RectilinearRoom, ...] = (),
    extra: tuple[ExtraConstraint, ...] = (),
) -> ValidationReport:
    """Check every explicit constraint on a final plan, independently of the optimizer.

    Parameters
    ----------
    plan : Plan
        Final plan to check (its certificate, if any, is ignored).
    ctx : Context
        Outline, load-bearing structure and regulation the plan must respect.
    reference : Plan or None, optional
        Proposed plan, needed only to check ``budget``.
    budget : float or None, optional
        Maximum displacement of any room coordinate from ``reference``, in metres.
        ``None`` leaves ``displacement.budget`` not applicable.
    merges : tuple of RectilinearRoom, optional
        Fused rooms, checked as a whole for their minimum area.
    extra : tuple of ExtraConstraint, optional
        Constraints added during optimization (cuts, frozen contacts...).

    Returns
    -------
    ValidationReport
        One result per constraint. ``valid`` is ``False`` as soon as one hard constraint
        is violated **or unknown**.

    Guarantees
    ----------
    - Geometric: exact rational comparisons against declared tolerances on a
      rectangular outline without fused rooms; GEOS with tolerances otherwise, which the
      report labels ``numeric``. See :data:`NOT_COVERED` for what is never covered.
    - Performance: **none**.

    Examples
    --------
    >>> from archlux.types import Context, Orientation, Plan, Regulation, Room, Structure
    >>> ctx = Context(structure=Structure(()), orientation=Orientation(0.0),
    ...               regulation=Regulation((), min_width=1.0),
    ...               outline=((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)))
    >>> plan = Plan(rooms=(Room(id="a", type="bedroom", x=0.0, y=0.0, w=4.0, h=3.0),))
    >>> report = validate_plan(plan, ctx)
    >>> report.valid, report.evidence
    (True, 'exact')
    """
    results: list[ConstraintResult] = [_check_finite(plan), _check_ids(plan)]
    if _finite_rooms(plan):
        for spec_id, check in _geometric_checks(plan, ctx, merges):
            results.extend(_guarded(spec_id, check))
    else:
        results.extend(_unknown_geometry("rooms are malformed: no geometric check is meaningful"))
    for spec_id, check in (
        ("structure.not_moved", lambda: _check_not_moved(plan, ctx)),
        ("walls.non_degenerate", lambda: _check_walls(plan, ctx)),
    ):
        results.extend(_guarded(spec_id, check))
    skipped: list[tuple[str, str]] = []
    if plan.openings:
        for spec_id, check in (
            ("openings.on_known_wall", lambda: _check_on_known_wall(plan, ctx)),
            ("openings.within_wall", lambda: _check_within_wall(plan, ctx)),
            ("openings.disjoint", lambda: _check_openings_disjoint(plan, ctx)),
            ("openings.sill_below_head", lambda: _check_sill(plan)),
        ):
            results.extend(_guarded(spec_id, check))
    else:
        skipped.append(("openings.*", "the plan has no opening"))
    if budget is None:
        skipped.append(("displacement.budget", "no budget given"))
    else:
        results.append(_check_budget(plan, reference, budget))
    for constraint in extra:
        results.extend(_guarded(constraint.spec.id, lambda c=constraint: c.check(plan, ctx)))  # type: ignore[misc]
    results.extend(_guarded("rooms.connected", lambda: _check_connected(plan)))
    return ValidationReport(
        results=tuple(results),
        not_applicable=tuple(skipped),
        plan_fingerprint=plan_fingerprint(plan),
    )
