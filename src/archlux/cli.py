"""Command line: ``archlux legalize``, ``archlux verify``, ``archlux feasible`` (PLAN.md 5.2).

A plan file holds no :class:`~archlux.types.Context`, so the command line builds one from
the plan and the options: the load-bearing structure is the plan's walls marked
``load_bearing``, the outline is the plan's, and the regulation comes from
``--min-width`` and ``--min-area TYPE=M2``.

Exit codes: ``0`` valid (or feasible, or legalized), ``1`` invalid (or infeasible), ``2``
error (unreadable file, rejected input, no valid plan found).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from archlux.errors import ArchluxError
from archlux.types import Context, GeometricProof, Orientation, Plan, Regulation, Structure

__all__ = ["main"]


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
    try:
        value = float(area)
    except ValueError:
        value = None
    if not sep or not room_type or value is None:
        raise argparse.ArgumentTypeError(f"expected TYPE=M2, got {text!r}")
    return room_type, value


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
            type=float,
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
            type=float,
            default=0.0,
            metavar="DEG",
            help="azimuth of the plan, in degrees (default 0)",
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
        orientation=Orientation(deg=args.orientation),
        regulation=Regulation(min_areas=tuple(args.min_area), min_width=args.min_width),
        program=tuple(sorted({room.type for room in plan.rooms})),
        outline=plan.outline,
    )


def _describe(proof: GeometricProof) -> str:
    """Plain-text verdict of an exact check.

    Parameters
    ----------
    proof : GeometricProof
        Result of :func:`archlux.certify.proof.verify_exactly`.

    Returns
    -------
    str
        One line per finding.
    """
    lines = ["valid" if proof.valid else "invalid"]
    checks = (
        (not proof.overlap, "no overlap", "rooms overlap"),
        (not proof.gaps, "no gap", "gaps between rooms"),
        (proof.areas_ok, "areas and widths met", "areas or widths below the regulation"),
        (proof.structure_kept, "structure kept", "load-bearing structure moved"),
    )
    lines += [f"  {'ok ' if ok else 'NO '} {good if ok else bad}" for ok, good, bad in checks]
    lines += [f"  - {violation}" for violation in proof.violations]
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
    if args.report and fixed.certificate is not None:
        print(_describe(fixed.certificate.geometry))
    return 0


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
    plan = Plan.from_json(args.plan)
    ctx = _context(plan, args)
    if args.command == "legalize":
        return _legalize(plan, ctx, args)
    if args.command == "verify":
        from archlux.certify.proof import verify_exactly

        proof = verify_exactly(plan, ctx)
        print(_describe(proof))
        return 0 if proof.valid else 1
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
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except (ArchluxError, OSError) as error:
        print(f"archlux: error: {error}", file=sys.stderr)
        return 2
