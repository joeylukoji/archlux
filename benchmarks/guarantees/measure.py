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
  independent checker finds a violation — the worst outcome, a proof that lies;
- ``invalid_but_flagged``: a plan came out with violations, but its certificate says
  so (not valid);
- ``refused``: ``legalize`` raised a typed ``ArchluxError`` (an honest refusal);
- ``crash``: any other exception.
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
from pathlib import Path

from benchmarks.guarantees.scenarios import Scenario, generate, perturb
from tests import checkers

import archlux
from archlux.data.corruption import corrompre
from archlux.erreurs import ArchluxError
from archlux.export.svg import comparer
from archlux.light.analytique import SubstitutAnalytique
from archlux.light.objectif import Daylight
from archlux.types import Contexte, Plan

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
GALLERY_PER_MODE = 3

Mode = Callable[[Scenario], tuple[Plan, Plan]]
"""Scenario -> (input given to legalize, output of legalize)."""


def _classic(s: Scenario) -> tuple[Plan, Plan]:
    return s.plan, archlux.legalize(s.plan, s.context)


def _classic_one_fault_tiling(s: Scenario) -> tuple[Plan, Plan]:
    """The AUDIT.md J7 regime: one room off by up to 25 cm, the grid still exists."""
    corrupted, _ = corrompre(s.plan, seed=zlib.crc32(s.name.encode()), amplitude=0.25)
    return corrupted, archlux.legalize(corrupted, s.context, pavage=True)


def _classic_perturbed_tiling(s: Scenario) -> tuple[Plan, Plan]:
    """The AUDIT.md J8 regime: every coordinate moved, no shared grid line survives."""
    # crc32, not hash(): str hashes change between processes (PYTHONHASHSEED).
    noisy = perturb(s.plan, seed=zlib.crc32(s.name.encode()))
    return noisy, archlux.legalize(noisy, s.context, pavage=True)


def _performance_analytic(s: Scenario) -> tuple[Plan, Plan]:
    return s.plan, archlux.legalize(s.plan, s.context, objective=SubstitutAnalytique())


def _performance_daylight(s: Scenario) -> tuple[Plan, Plan]:
    objective = Daylight(SubstitutAnalytique(), q_chapeau=1.0)
    return s.plan, archlux.legalize(s.plan, s.context, objective=objective)


MODES: dict[str, tuple[str, Mode]] = {
    "classic": ("classic, valid input", _classic),
    "classic_one_fault": (
        "classic + tiling, one room off by up to 25 cm",
        _classic_one_fault_tiling,
    ),
    "classic_noisy": (
        "classic + tiling, every coordinate moved by up to 3 cm",
        _classic_perturbed_tiling,
    ),
    "performance": ("performance (analytic surrogate), valid input", _performance_analytic),
    "daylight": ("performance (Daylight objective), valid input", _performance_daylight),
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


def _run_case(scenario: Scenario, mode: Mode) -> dict[str, object]:
    start = time.perf_counter()
    try:
        given, result = mode(scenario)
    except ArchluxError as error:
        outcome, detail = "refused", f"{type(error).__name__}: {error}"
        given = result = None
    except Exception as error:  # a crash is exactly what this benchmark must record
        outcome, detail = "crash", f"{type(error).__name__}: {error}"
        given = result = None
    elapsed_ms = (time.perf_counter() - start) * 1000

    row: dict[str, object] = {"scenario": scenario.name, "ms": round(elapsed_ms, 2)}
    if result is None:
        return row | {"outcome": outcome, "detail": detail[:200], "kinds": []}
    found = checkers.violations(result, scenario.context)
    certified = bool(result.certificat and result.certificat.geometrie.valide)
    if not found:
        outcome = "ok"
    elif certified:
        outcome = "false_certificate"
    else:
        outcome = "invalid_but_flagged"
    row |= {
        "outcome": outcome,
        "kinds": sorted({v.kind for v in found}),
        "detail": "; ".join(v.detail for v in found)[:200],
    }
    row["_plans"] = (given, result)  # kept in memory for the gallery, never serialized
    return row


def _summary(rows: list[dict[str, object]]) -> dict[str, object]:
    outcomes = Counter(str(r["outcome"]) for r in rows)
    kinds = Counter(k for r in rows for k in r["kinds"])
    return {
        "n": len(rows),
        "outcomes": dict(sorted(outcomes.items())),
        "violations_by_kind": {k: kinds.get(k, 0) for k in checkers.KINDS},
        "median_ms": round(statistics.median(float(r["ms"]) for r in rows), 2),
    }


def _gallery(
    label: str, mode: str, rows: list[dict[str, object]], context_of: dict[str, Contexte]
) -> list[str]:
    folder = RESULTS / label
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    worst = [r for r in rows if r["outcome"] in ("false_certificate", "invalid_but_flagged")]
    for row in worst[:GALLERY_PER_MODE]:
        given, result = row["_plans"]
        name = f"{mode}-{row['scenario']}.svg"
        svg = comparer(
            given,
            result,
            contour=context_of[str(row["scenario"])].contour,
            titres=("input", f"output — {row['outcome']}: {', '.join(row['kinds'])}"),
        )
        (folder / name).write_text(svg, encoding="utf-8")
        written.append(name)
    return written


def measure(label: str, n: int, seed: int) -> dict[str, object]:
    """Run every mode on ``n`` scenarios and store the result under ``label``."""
    scenarios = [generate(seed=seed, index=i) for i in range(n)]
    context_of = {s.name: s.context for s in scenarios}
    report: dict[str, object] = {
        "label": label,
        "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "revision": _git_revision(),
        "archlux": archlux.__version__,
        "seed": seed,
        "n": n,
        "modes": {},
    }
    for key, (description, mode) in MODES.items():
        rows = [_run_case(s, mode) for s in scenarios]
        report["modes"][key] = {
            "description": description,
            "summary": _summary(rows),
            "gallery": _gallery(label, key, rows, context_of),
            "cases": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
        }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{label}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    write_readme()
    return report


def _cell(summary: dict[str, object], outcome: str) -> str:
    count = summary["outcomes"].get(outcome, 0)
    return f"{count} ({100 * count / summary['n']:.1f} %)"


def write_readme() -> None:
    """Regenerate README.md from every stored run, oldest first."""
    runs = sorted(
        (json.loads(p.read_text(encoding="utf-8")) for p in RESULTS.glob("*.json")),
        key=lambda r: r["date"],
    )
    lines = [
        "# Guarantee benchmark",
        "",
        "Generated by `python -m benchmarks.guarantees.measure --label <name>`; do not edit.",
        "See the docstring of `measure.py` for the protocol and the meaning of each outcome.",
        "**`false_certificate` must reach 0**: it counts plans certified valid that break a",
        "guarantee according to the independent checker (`tests/checkers.py`).",
        "",
    ]
    for key, (description, _) in MODES.items():
        lines += [
            f"## {key} — {description}",
            "",
            "| run | revision | n | ok | false certificate | refused | crash | "
            "overlap | coverage | area | wall | median ms |",
            "|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
        ]
        for run in runs:
            mode = run["modes"].get(key)
            if mode is None:
                continue
            s, v = mode["summary"], mode["summary"]["violations_by_kind"]
            gallery = f" ([cases]({run['label']}/))" if mode["gallery"] else ""
            lines.append(
                f"| {run['label']}{gallery} | `{run['revision']}` | {s['n']} | {_cell(s, 'ok')} | "
                f"{_cell(s, 'false_certificate')} | {_cell(s, 'refused')} | {_cell(s, 'crash')} | "
                f"{v['overlap']} | {v['coverage']} | {v['area']} | {v['wall']} | {s['median_ms']} |"
            )
        lines.append("")
    (HERE / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", required=True, help="name of this run, e.g. baseline")
    parser.add_argument("--n", type=int, default=200, help="number of scenarios")
    parser.add_argument("--seed", type=int, required=True, help="series seed (no default)")
    args = parser.parse_args()
    report = measure(args.label, args.n, args.seed)
    for key, mode in report["modes"].items():
        print(f"{key:14s} {mode['summary']['outcomes']}")


if __name__ == "__main__":
    main()
