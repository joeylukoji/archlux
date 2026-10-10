"""Command line: ``archlux legalize``, ``archlux verify``, ``archlux feasible`` (PLAN.md 5.2).

A plan file holds no :class:`~archlux.types.Context`, so the command line builds one from
the plan and the options: the load-bearing structure is the plan's walls marked
``load_bearing``, the outline is the plan's, and the regulation comes from
``--min-width`` and ``--min-area TYPE=M2``.

``verify_exactly`` checks overlaps, gaps, areas and the structure, not widths: the width
rule is a bound of the polytope, enforced only while legalizing. ``verify`` and
``legalize --report`` therefore also measure every rectangle of the plan against
``--min-width``, as the polytope bounds each rectangle (the sub-rectangles of a fused L
room included), within :data:`~archlux.tolerances.SNAP_M`.

Options are validated the same way for the three subcommands: ``--min-width`` and every
``--min-area`` value must be finite and non-negative, a ``--min-area`` type must be one of
the plan's room types (case-sensitive) and appear once, and ``--orientation`` must be
finite; it is an azimuth, so it is taken modulo 360 (``-90`` is ``270``).

Exit codes: ``0`` valid (or feasible, or legalized), ``1`` invalid (or infeasible), ``2``
error (unreadable file, rejected input, no valid plan found).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Sequence

from archlux.errors import ArchluxError, InvariantViolation
from archlux.tolerances import SNAP_M
from archlux.types import Context, GeometricProof, Orientation, Plan, Regulation, Structure

__all__ = ["main"]


class _InputError(Exception):
    """A plan file or an option the command line rejects (exit code 2)."""


def _finite(text: str) -> float:
    """Parse a finite number.

    Parameters
    ----------
    text : str
        The option value.

    Returns
    -------
    float
        The number.
    """
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"expected a finite number, got {text!r}")
    return value


def _length(text: str) -> float:
    """Parse a finite, non-negative length or area.

    Parameters
    ----------
    text : str
        The option value.

    Returns
    -------
    float
        The value.
    """
    value = _finite(text)
    if value < 0.0:
        raise argparse.ArgumentTypeError(f"expected a value >= 0, got {text!r}")
    return value


def _min_area(text: str) -> tuple[str, float]:
    """Parse one ``--min-area`` value.

    Parameters
    ----------
    text : str
        ``TYPE=M2``, for example ``bedroom=9``.

    Returns
    -------
    tuple of (str, float)
        The room type and its minimum area, in square metres.
    """
    room_type, sep, area = text.partition("=")
    if not sep or not room_type:
        raise argparse.ArgumentTypeError(f"expected TYPE=M2, got {text!r}")
    return room_type, _length(area)


def _check_min_areas(plan: Plan, min_areas: list[tuple[str, float]]) -> None:
    """Reject a ``--min-area`` type given twice or absent from the plan.

    Parameters
    ----------
    plan : Plan
        The plan read from the file.
    min_areas : list of (str, float)
        Parsed ``--min-area`` values.

    Raises
    ------
    _InputError
        A type is repeated, or no room of the plan has it.
    """
    known = sorted({room.type for room in plan.rooms})
    seen: set[str] = set()
    for room_type, _ in min_areas:
        if room_type in seen:
            raise _InputError(f"--min-area: type {room_type!r} given twice")
        if room_type not in known:
            raise _InputError(
                f"--min-area: no room of type {room_type!r} in the plan; "
                f"its types are {', '.join(known)}"
            )
        seen.add(room_type)


def _parser() -> argparse.ArgumentParser:
    """Command-line parser of the three subcommands.

    Returns
    -------
    argparse.ArgumentParser
        The parser.
    """
    parser = argparse.ArgumentParser(
        prog="archlux",
        description="Legalize, verify or check the feasibility of a floor plan.",
        epilog="Exit codes: 0 valid, 1 invalid or infeasible, 2 error.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, summary in (
        ("legalize", "repair a plan with the smallest displacement"),
        ("verify", "check a plan exactly; exit 1 if it is invalid"),
        ("feasible", "decide whether the program admits a valid plan; exit 1 if not"),
    ):
        sub = commands.add_parser(name, help=summary, description=summary)
        sub.add_argument("plan", help="plan file (JSON, see Plan.from_json)")
        sub.add_argument(
            "--min-width",
            type=_length,
            default=Regulation(
                (),
            ).min_width,
            help="minimum room width, in metres (default %(default)s)",
        )
        sub.add_argument(
            "--min-area",
            type=_min_area,
            action="append",
            default=[],
            metavar="TYPE=M2",
            help="minimum area of a room type; repeatable",
        )
        sub.add_argument(
            "--orientation",
            type=_finite,
            default=0.0,
            metavar="DEG",
            help="azimuth of the plan, in degrees, taken modulo 360 (default 0)",
        )
    legalize = commands.choices["legalize"]
    legalize.add_argument("-o", "--output", help="write the legalized plan here (JSON)")
    legalize.add_argument("--svg", help="write an SVG drawing of the legalized plan here")
    legalize.add_argument("--report", action="store_true", help="print the certificate")
    legalize.add_argument(
        "--tiling", action="store_true", help="also close gaps: the rooms must tile the outline"
    )
    legalize.add_argument(
        "--repair-budget",
        type=int,
        default=4,
        metavar="N",
        help="grid repair budget with --tiling (default 4)",
    )
    return parser


def _context(plan: Plan, args: argparse.Namespace) -> Context:
    """Context built from the plan and the options, see the module docstring.

    Parameters
    ----------
    plan : Plan
        The plan read from the file.
    args : argparse.Namespace
        Parsed options.

    Returns
    -------
    Context
        Its structure, orientation and regulation.
    """
    return Context(
        structure=Structure(load_bearing_walls=tuple(w for w in plan.walls if w.load_bearing)),
        orientation=Orientation(deg=args.orientation % 360.0),
        regulation=Regulation(min_areas=tuple(args.min_area), min_width=args.min_width),
        program=tuple(sorted({room.type for room in plan.rooms})),
        outline=plan.outline,
    )


def _narrow_rooms(plan: Plan, min_width: float) -> tuple[str, ...]:
    """Rectangles narrower than ``min_width``, the bound the polytope puts on ``w`` and ``h``.

    Parameters
    ----------
    plan : Plan
        The plan to measure.
    min_width : float
        Minimum width, in metres.

    Returns
    -------
    tuple of str
        One message per rectangle whose smaller side is below ``min_width - SNAP_M``.
    """
    return tuple(
        f"width {room.id}: {min(room.w, room.h):.2f} m < {min_width:.2f} m"
        for room in plan.rooms
        if min(room.w, room.h) < min_width - SNAP_M
    )


def _describe(proof: GeometricProof, narrow: tuple[str, ...]) -> str:
    """Plain-text verdict of an exact check and of the width check.

    Parameters
    ----------
    proof : GeometricProof
        Result of :func:`archlux.certify.proof.verify_exactly`.
    narrow : tuple of str
        Result of :func:`_narrow_rooms`.

    Returns
    -------
    str
        One line per finding.
    """
    lines = ["valid" if proof.valid and not narrow else "invalid"]
    checks = (
        (not proof.overlap, "no overlap", "rooms overlap"),
        (not proof.gaps, "no gap", "gaps between rooms"),
        (proof.areas_ok, "minimum areas met", "areas below the regulation"),
        (not narrow, "minimum widths met", "rooms narrower than the regulation"),
        (proof.structure_kept, "structure kept", "load-bearing structure moved"),
    )
    lines += [f"  {'ok ' if ok else 'NO '} {good if ok else bad}" for ok, good, bad in checks]
    lines += [f"  - {violation}" for violation in (*proof.violations, *narrow)]
    lines.append(f"  max displacement: {proof.max_displacement:.3f} m")
    return "\n".join(lines)


def _legalize(plan: Plan, ctx: Context, args: argparse.Namespace) -> int:
    """Run ``archlux legalize``.

    Parameters
    ----------
    plan : Plan
        The plan read from the file.
    ctx : Context
        Its context.
    args : argparse.Namespace
        Parsed options.

    Returns
    -------
    int
        The exit code.
    """
    from archlux.api import legalize
    from archlux.export import render_svg

    fixed = legalize(plan, ctx, tiling=args.tiling, repair_budget=args.repair_budget)
    if args.output:
        fixed.to_json(args.output)
    if args.svg:
        with open(args.svg, "w", encoding="utf-8") as stream:
            stream.write(render_svg(fixed, outline=plan.outline, walls=fixed.walls))
    if args.report:
        certificate = fixed.certificate
        print(
            "no certificate: the legalized plan carries none"
            if certificate is None
            else _describe(certificate.geometry, _narrow_rooms(fixed, args.min_width))
        )
    return 0


def _read(path: str) -> Plan:
    """Read the plan file, naming the file and the field in an error.

    Parameters
    ----------
    path : str
        The plan file.

    Returns
    -------
    Plan
        The plan.

    Raises
    ------
    _InputError
        The file is not a valid plan.
    """
    try:
        return Plan.from_json(path)
    except InvariantViolation as error:
        cause = error.__cause__
        if isinstance(cause, KeyError):
            raise _InputError(f"{path}: missing field {cause.args[0]!r}") from error
        if isinstance(cause, (TypeError, ValueError)) and not isinstance(
            cause, (json.JSONDecodeError, UnicodeDecodeError)
        ):
            raise _InputError(f"{path}: not a valid plan: {cause}") from error
        raise _InputError("; ".join(error.violations)) from error


def _message(error: Exception) -> str:
    """Plain-text message of an error, without errno codes.

    Parameters
    ----------
    error : Exception
        The error to report.

    Returns
    -------
    str
        ``file: reason`` for a file-system error, the error's own text otherwise.
    """
    if isinstance(error, OSError) and error.filename and error.strerror:
        return f"{error.filename}: {error.strerror.lower()}"
    return str(error)


def _run(args: argparse.Namespace) -> int:
    """Read the plan and dispatch to the subcommand.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed options.

    Returns
    -------
    int
        The exit code.
    """
    plan = _read(args.plan)
    _check_min_areas(plan, args.min_area)
    ctx = _context(plan, args)
    if args.command == "legalize":
        return _legalize(plan, ctx, args)
    if args.command == "verify":
        from archlux.certify.proof import verify_exactly

        proof = verify_exactly(plan, ctx)
        narrow = _narrow_rooms(plan, args.min_width)
        print(_describe(proof, narrow))
        return 0 if proof.valid and not narrow else 1
    from archlux.feasibility import is_feasible

    verdict = is_feasible(plan, ctx.structure, ctx)
    print("feasible" if verdict.feasible else "infeasible")
    return 0 if verdict.feasible else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the ``archlux`` command.

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments without the program name; ``sys.argv[1:]`` when omitted.

    Returns
    -------
    int
        The exit code, see the module docstring.
    """
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:  # argparse exits on --help and on a rejected option
        return stop.code if isinstance(stop.code, int) else 2
    try:
        return _run(args)
    except (ArchluxError, OSError, _InputError) as error:
        print(f"archlux: error: {_message(error)}", file=sys.stderr)
        return 2
