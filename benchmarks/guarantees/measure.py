"""Measure how often ``legalize`` keeps its exact guarantees, and how often it lies.

Usage (from the repository root)::

    python -m benchmarks.guarantees.measure --label baseline --seed 17
    python -m benchmarks.guarantees.measure --label after-1.1 --n 200 --seed 17

Each run writes ``results/<label>.json`` and an SVG gallery of failing cases in
``results/<label>/``, then regenerates ``README.md`` from every stored run, so that the
effect of each PLAN.md batch can be read as a before/after table.

Every output is checked by the independent checker of ``tests/checkers.py``, never by
``certify``. Outcomes:

- ``ok``: a plan came out and keeps every guarantee;
- ``false_certificate``: a plan came out, its certificate says *valid*, and the
  independent checker finds a violation. The worst outcome: a proof that lies;
- ``invalid_but_flagged``: a plan came out with violations, and its certificate says so;
- ``refused_infeasible``: ``legalize`` raised ``Infaisable``, an honest refusal;
- ``refused_invariant``: ``legalize`` raised another ``ArchluxError`` (typically
  ``InvariantViole``: the proof caught a defective solver output). Safe, but a defect;
- ``crash``: any other exception.

Input preparation (corruption, noise) happens before and outside the measured call, so
that a failure there is never counted against ``legalize``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import subprocess
import time
import zlib
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from benchmarks.guarantees.scenarios import Scenario, WallKind, generate, perturb
from tests import checkers

import archlux
from archlux.data.corruption import corrompre
from archlux.erreurs import ArchluxError, Infaisable
from archlux.export.svg import comparer
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.types import Contexte, Plan

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
GALLERY_PER_MODE = 3

Outcome = Literal[
    "ok",
    "false_certificate",
    "invalid_but_flagged",
    "refused_infeasible",
    "refused_invariant",
    "crash",
]
OUTCOMES: tuple[Outcome, ...] = (
    "ok",
    "false_certificate",
    "invalid_but_flagged",
    "refused_infeasible",
    "refused_invariant",
    "crash",
)


@dataclass(frozen=True, slots=True)
class Mode:
    """One way of calling ``legalize`` on one family of scenarios."""

    description: str
    family: WallKind
    prepare: Callable[[Scenario], Plan]
    run: Callable[[Plan, Contexte], Plan]


@dataclass(slots=True)
class Case:
    """The measured outcome of one scenario in one mode."""

    scenario: str
    ms: float
    outcome: Outcome
    kinds: list[str] = field(default_factory=list)
    detail: str = ""


def _as_is(s: Scenario) -> Plan:
    return s.plan


def _one_fault(s: Scenario) -> Plan:
    """AUDIT.md J7 regime: one room off by up to 25 cm, the grid still exists."""
    corrupted, _ = corrompre(s.plan, seed=zlib.crc32(s.name.encode()), amplitude=0.25)
    return corrupted


def _noisy(s: Scenario) -> Plan:
    """AUDIT.md J8 regime: every coordinate moved, no shared grid line survives."""
    # crc32, not hash(): str hashes change between processes (PYTHONHASHSEED).
    return perturb(s.plan, seed=zlib.crc32(s.name.encode()))


def _classic(plan: Plan, ctx: Contexte) -> Plan:
    return archlux.legalize(plan, ctx)


def _classic_tiling(plan: Plan, ctx: Contexte) -> Plan:
    return archlux.legalize(plan, ctx, pavage=True)


def _performance(plan: Plan, ctx: Contexte) -> Plan:
    return archlux.legalize(plan, ctx, objective=SubstitutAnalytique())


def _daylight(plan: Plan, ctx: Contexte) -> Plan:
    objective = Daylight(SubstitutAnalytique(), q_chapeau=1.0)
    return archlux.legalize(plan, ctx, objective=objective)


MODES: dict[str, Mode] = {
    "classic": Mode("classic, valid input", "full", _as_is, _classic),
    "classic_one_fault": Mode(
        "classic + tiling, one room off by up to 25 cm", "full", _one_fault, _classic_tiling
    ),
    "classic_noisy": Mode(
        "classic + tiling, every coordinate moved by up to 3 cm", "full", _noisy, _classic_tiling
    ),
    "performance": Mode(
        "performance (analytic surrogate), valid input", "full", _as_is, _performance
    ),
    "daylight": Mode("performance (Daylight objective), valid input", "full", _as_is, _daylight),
    "partial_one_fault": Mode(
        "partial load-bearing wall; classic + tiling, one room off by up to 25 cm",
        "partial",
        _one_fault,
        _classic_tiling,
    ),
    "partial_performance": Mode(
        "partial load-bearing wall; performance (analytic surrogate), valid input",
        "partial",
        _as_is,
        _performance,
    ),
}


def _git_revision() -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=HERE, check=False
        ).stdout.strip()

    # Dirty = a tracked file differs from HEAD, the benchmark's own outputs excepted.
    changed = git(
        "status",
        "--porcelain",
        "--untracked-files=no",
        "--",
        ":/",
        ":(exclude,top)benchmarks/guarantees/results",
        ":(exclude,top)benchmarks/guarantees/README.md",
    )
    return git("rev-parse", "--short", "HEAD") + ("-dirty" if changed else "")


def _refusal(scenario: Scenario, start: float, outcome: Outcome, error: Exception) -> Case:
    return Case(
        scenario=scenario.name,
        ms=round((time.perf_counter() - start) * 1000, 2),
        outcome=outcome,
        detail=f"{type(error).__name__}: {error}"[:200],
    )


def _run_case(scenario: Scenario, mode: Mode) -> tuple[Case, tuple[Plan, Plan] | None]:
    """Measure one call; also return (input, output) when a plan came out."""
    given = mode.prepare(scenario)  # outside the measured call on purpose
    start = time.perf_counter()
    try:
        result = mode.run(given, scenario.context)
    except Infaisable as error:
        return _refusal(scenario, start, "refused_infeasible", error), None
    except ArchluxError as error:
        return _refusal(scenario, start, "refused_invariant", error), None
    except Exception as error:  # a crash is exactly what this benchmark must record
        return _refusal(scenario, start, "crash", error), None
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    found = checkers.violations(result, scenario.context)
    certified = bool(result.certificat and result.certificat.geometrie.valide)
    outcome: Outcome = (
        "ok" if not found else "false_certificate" if certified else "invalid_but_flagged"
    )
    case = Case(
        scenario=scenario.name,
        ms=elapsed_ms,
        outcome=outcome,
        kinds=sorted({v.kind for v in found}),
        detail="; ".join(v.detail for v in found)[:200],
    )
    return case, (given, result)


def _summary(cases: list[Case]) -> dict[str, Any]:
    outcomes = Counter(case.outcome for case in cases)
    kinds = Counter(kind for case in cases for kind in case.kinds)
    return {
        "n": len(cases),
        "outcomes": {outcome: outcomes.get(outcome, 0) for outcome in OUTCOMES},
        "violations_by_kind": {kind: kinds.get(kind, 0) for kind in checkers.KINDS},
        "median_ms": round(statistics.median(case.ms for case in cases), 2),
    }


def _gallery(
    label: str,
    key: str,
    measured: list[tuple[Case, tuple[Plan, Plan] | None]],
    context_of: dict[str, Contexte],
) -> list[str]:
    folder = RESULTS / label
    written: list[str] = []
    for case, plans in measured:
        if plans is None or case.outcome == "ok" or len(written) >= GALLERY_PER_MODE:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        given, result = plans
        name = f"{key}-{case.scenario}.svg"
        svg = comparer(
            given,
            result,
            contour=context_of[case.scenario].contour,
            walls=context_of[case.scenario].structure.murs_porteurs,
            titres=("input", f"output: {case.outcome} ({', '.join(case.kinds)})"),
        )
        _write(folder / name, svg)
        written.append(name)
    return written


def measure(label: str, n: int, seed: int) -> dict[str, Any]:
    """Run every mode on ``n`` scenarios per family and store the result under ``label``."""
    families: tuple[WallKind, ...] = ("full", "partial")
    scenarios = {
        family: [generate(seed=seed, index=i, wall=family) for i in range(n)] for family in families
    }
    context_of = {s.name: s.context for family in scenarios.values() for s in family}
    modes: dict[str, Any] = {}
    for key, mode in MODES.items():
        measured = [_run_case(s, mode) for s in scenarios[mode.family]]
        cases = [case for case, _ in measured]
        modes[key] = {
            "description": mode.description,
            "summary": _summary(cases),
            "gallery": _gallery(label, key, measured, context_of),
            "cases": [asdict(case) for case in cases],
        }
    report: dict[str, Any] = {
        "label": label,
        "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "revision": _git_revision(),
        "archlux": archlux.__version__,
        "seed": seed,
        "n": n,
        "modes": modes,
    }
    RESULTS.mkdir(exist_ok=True)
    _write(RESULTS / f"{label}.json", json.dumps(report, indent=1))
    write_readme()
    return report


_SPLIT = ("refused_infeasible", "refused_invariant")
"""Outcomes introduced when refusals were split; unknown for earlier runs."""


def _count(summary: dict[str, Any], outcome: str) -> int | None:
    """Count of ``outcome``; ``None`` if the run predates that outcome.

    Earlier runs stored only non-zero outcomes, so a missing key means zero, except for
    the split refusal outcomes, which they did not distinguish.
    """
    stored: dict[str, int] = summary["outcomes"]
    if outcome in _SPLIT and "refused" in stored:  # an earlier run with refusals
        return None
    return int(stored.get(outcome, 0))


def _refused(summary: dict[str, Any]) -> int:
    """All refusals; runs before the split stored them as a single ``refused``."""
    stored: dict[str, int] = summary["outcomes"]
    keys = ("refused", "refused_infeasible", "refused_invariant")
    return sum(int(stored.get(key, 0)) for key in keys)


def _cell(count: int | None, n: int) -> str:
    return "n/a" if count is None else f"{count} ({100 * count / n:.1f} %)"


def write_readme() -> None:
    """Regenerate README.md from every stored run, oldest first."""
    runs = sorted(
        (json.loads(p.read_text(encoding="utf-8")) for p in RESULTS.glob("*.json")),
        key=lambda r: str(r["date"]),
    )
    lines = [
        "# Guarantee benchmark",
        "",
        "Generated by `python -m benchmarks.guarantees.measure --label <name> --seed 17`;",
        "do not edit. The docstring of `measure.py` defines the protocol and each outcome.",
        "**`false certificate` must reach 0**: it counts plans certified valid that break a",
        "guarantee according to the independent checker (`tests/checkers.py`).",
        "`of which invariant` counts refusals where the proof caught a defective solver",
        "output (safe, but a defect); `n/a` marks runs made before that split.",
        "",
    ]
    for key, mode in MODES.items():
        lines += [
            f"## {key}: {mode.description}",
            "",
            "| run | revision | n | ok | false certificate | invalid, flagged | refused | "
            "of which invariant | crash | overlap | coverage | area | wall | median ms |",
            "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
        ]
        for run in runs:
            stored = run["modes"].get(key)
            if stored is None:
                continue
            s = stored["summary"]
            v, n = s["violations_by_kind"], int(s["n"])
            gallery = f" ([cases]({run['label']}/))" if stored["gallery"] else ""
            lines.append(
                f"| {run['label']}{gallery} | `{run['revision']}` | {n} "
                f"| {_cell(_count(s, 'ok'), n)} "
                f"| {_cell(_count(s, 'false_certificate'), n)} "
                f"| {_cell(_count(s, 'invalid_but_flagged'), n)} "
                f"| {_cell(_refused(s), n)} "
                f"| {_cell(_count(s, 'refused_invariant'), n)} "
                f"| {_cell(_count(s, 'crash'), n)} "
                f"| {v['overlap']} | {v['coverage']} | {v['area']} | {v['wall']} "
                f"| {s['median_ms']} |"
            )
        lines.append("")
    _write(HERE / "README.md", "\n".join(lines))


def _write(path: Path, text: str) -> None:
    """Write UTF-8 with LF endings and exactly one final newline, on every platform.

    Without ``newline``, Windows writes CRLF; without the final newline, the pre-commit
    hooks rewrite every output after each run.
    """
    path.write_text(text.rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--label", required=True, help="name of this run, e.g. baseline")
    parser.add_argument("--n", type=int, default=200, help="number of scenarios per family")
    parser.add_argument("--seed", type=int, required=True, help="series seed (no default)")
    args = parser.parse_args()
    report = measure(args.label, args.n, args.seed)
    for key, stored in report["modes"].items():
        nonzero = {k: v for k, v in stored["summary"]["outcomes"].items() if v}
        print(f"{key:20s} {nonzero}")


if __name__ == "__main__":
    main()
