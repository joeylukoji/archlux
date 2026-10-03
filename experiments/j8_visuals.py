"""Milestone 8: **before / after** comparison folder, one plan per sheet.

Why this script exists
----------------------
`j8_generation.py` returns rates. A rate does not say what a repair looks like, and two
correct figures of milestone 8, "60.9 % of plans valid" and "median displacement of
56 % of the side", suggest opposite things. This folder settles it by looking.

Each sheet carries the SVG of both states at the **same scale**, and the matching
metrics file: geometric diagnostic before, certification verdict after, displacement.
Failures are included just like successes: a folder that showed only what works
would be useless.

Usage: j8_visuals.py [plans.jsonl] [label] [n_per_category]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.errors import GridNotRecoverable
from archlux.export.svg import compare, render

sys.path.insert(0, str(Path(__file__).resolve().parent))
from j8_generation import BUDGETS, _build, _scale

PLANS = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/archlux-donnees/j8_plans.jsonl")
LABEL = sys.argv[2] if len(sys.argv) > 2 else "etoile"
PER_CATEGORY = int(sys.argv[3]) if len(sys.argv) > 3 else 8
BUDGET = BUDGETS[-1]
ROOT = Path("results/visuals") / LABEL


def _folder(status: str) -> str:
    """Sub-folder of an outcome: `proven infeasible` -> `proven-infeasible`."""
    return status.replace(" ", "-")


def _sheet(plan_id: str, plan, diag, proof, fixed, status: str, scale: float) -> str:
    """Metrics of a plan, before and after, in Markdown."""
    rows = [
        f"# {plan_id}",
        "",
        f"Conditioning `{LABEL}`, repair budget {BUDGET}, scale {scale:.3f} m/unit.",
        "",
        f"**Outcome: {status}**",
        "",
        "## Before: geometric diagnostic",
        "",
        "| quantity | value |",
        "|---|--:|",
        f"| rooms | {len(plan.rooms)} |",
        f"| rooms overlapped per room | {diag.overlaps:.2f} |",
        f"| gap share of the envelope | {diag.gap_share:.1%} |",
        f"| of which interior holes | {diag.hole_share:.1%} |",
        f"| disjoint fragments | {diag.fragments} |",
        f"| cells of the implicit grid | {diag.cells} |",
        f"| characteristic side | {diag.size:.2f} m |",
        "",
        "## Before: exact verification",
        "",
        f"valid: **{proof.valid}**",
        "",
    ]
    rows += [f"- {v}" for v in proof.violations] or ["*no violation*"]
    rows += ["", "## After: correction", ""]
    if fixed is None:
        rows += [
            f"No plan produced: `{status}`.",
            "",
            "This is not a crash. A grid refusal means that the bounded repair is not "
            "enough to make the partition consistent; an infeasibility is **proven**, "
            "with a Farkas certificate.",
        ]
    else:
        geo = fixed.certificate.geometry
        rows += [
            "| quantity | value |",
            "|---|--:|",
            f"| valid | **{geo.valid}** |",
            f"| max displacement | {geo.max_displacement:.3f} m |",
            f"| relative to the side | {geo.max_displacement / diag.size:.0%} |",
            f"| rooms | {len(fixed.rooms)} |",
        ]
    return "\n".join(rows) + "\n"


def main() -> None:
    rows = [json.loads(x) for x in PLANS.read_text(encoding="utf-8").splitlines() if x.strip()]
    scale = _scale(rows)
    count: dict[str, int] = {}
    index: list[tuple[str, str, str, str]] = []

    for plan_json in rows:
        built = _build(plan_json, scale)
        if isinstance(built, str):
            continue
        plan, context, diag = built
        proof = verify_exactly(plan, context)
        fixed, status = None, "repaired"
        try:
            fixed = ax.legalize(plan, context, tiling=True, repair_budget=BUDGET)
            if not fixed.certificate.geometry.valid:
                status = "corrected but invalid"
        except ax.Infeasible:
            status = "proven infeasible"
        except GridNotRecoverable:
            status = "unrecoverable grid"
        except ax.InvariantViolation:
            status = "invariant violation"
        # Quota per outcome: a folder showing only the successes would give a false
        # picture of the milestone.
        if count.get(status, 0) >= PER_CATEGORY:
            continue
        count[status] = count.get(status, 0) + 1

        folder = ROOT / _folder(status)
        folder.mkdir(parents=True, exist_ok=True)
        before = f"{len(plan.rooms)} rooms, gap {diag.gap_share:.0%}, {diag.fragments} fragments"
        if fixed is None:
            # A single panel. Redrawing the input plan on the right would read as
            # "nothing changed", whereas no plan was produced at all.
            svg = render(
                plan,
                outline=context.outline,
                title=f"{status} — {before}",
            )
        else:
            svg = compare(
                plan,
                fixed,
                outline=context.outline,
                titles=(
                    f"before — {before}",
                    f"after — {status}, displacement "
                    f"{fixed.certificate.geometry.max_displacement:.2f} m",
                ),
            )
        name = plan_json["id"]
        (folder / f"{name}.svg").write_text(svg, encoding="utf-8")
        (folder / f"{name}.md").write_text(
            _sheet(name, plan, diag, proof, fixed, status, scale),
            encoding="utf-8",
        )
        index.append((status, name, f"{diag.gap_share:.0%}", str(diag.fragments)))

    ROOT.mkdir(parents=True, exist_ok=True)
    table = [
        f"# Before / after comparisons: conditioning `{LABEL}`",
        "",
        f"Repair budget {BUDGET}. At most {PER_CATEGORY} plans per outcome, failures included.",
        "",
        "| outcome | plan | gap before | fragments before | sheet |",
        "|---|---|--:|--:|---|",
    ]
    for status, name, gap, fragments in sorted(index):
        sub = _folder(status)
        table.append(
            f"| {status} | `{name}` | {gap} | {fragments} | "
            f"[svg]({sub}/{name}.svg) · [metrics]({sub}/{name}.md) |"
        )
    (ROOT / "index.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(f"{len(index)} sheets -> {ROOT}")
    print("outcomes:", count)


if __name__ == "__main__":
    main()
