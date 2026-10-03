"""Milestone 9: move the rooms according to the sun orientation.

What this milestone shows
-------------------------
`legalize(..., objective=Surrogate)` chains Frank-Wolfe from the L1 point **without
leaving the polytope**. Every variant produced is therefore a geometrically valid and
certified plan: the space of admissible layouts is explored, never left. Varying
`Context.orientation` varies the objective, hence the chosen layout.

The input is a **generated** plan (milestone 8), then legalized: the full chain thus
goes from the raw output of a model to a family of certified variants.

What this milestone does NOT show
---------------------------------
**The optimized objective is not real daylight.** `AnalyticSurrogate` was measured
against 4,239 simulated rooms of Swiss Dwellings: once normalized by area, its rank
drops to `rho = +0.085`, floor area alone beats it (`rho = +0.590` against `+0.403`),
and on sites disjoint from training the rank **reverses** (`-0.342`). See
`results/j7_sd_per_room.md`.

These variants are therefore "what the surrogate believes", not "what light does".
What is guaranteed here is **geometric**: every variant tiles its outline, and the
certificate proves it. The daylight guarantee covers the frozen oracle, not an LM-83
sDA (`docs/limitations.md`).

Usage: j9_orientation.py [plans.jsonl] [n_plans] [budget_m]
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import archlux as ax
from archlux.export.svg import sheet
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, vectorize
from archlux.light.analytic import AnalyticSurrogate
from archlux.types import Orientation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from j8_generation import BUDGETS, DEFAULT_WIDTH, _build, _scale

DEFAULT = Path("D:/archlux-donnees/j8_plans_divers.jsonl")
AZIMUTHS = tuple(range(0, 360, 45))
ROOT = Path("results/orientation")


def _score(plan, context, surrogate) -> float:
    """Value of the surrogate for this plan under this orientation."""
    poly = build_polytope(deduce_order(plan), context)
    return float(surrogate.evaluate(vectorize(plan, poly.index), context.orientation))


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    n_plans = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0

    rows = [json.loads(x) for x in source.read_text(encoding="utf-8").splitlines() if x.strip()]
    scale = _scale(rows)
    surrogate = AnalyticSurrogate(target_indicator="sDA")
    ROOT.mkdir(parents=True, exist_ok=True)

    index = [
        "# Milestone 9: variants by solar azimuth\n",
        f"Displacement budget {budget:.1f} m (infinity norm around the L1 point), "
        f"`min_width = {DEFAULT_WIDTH:.2f} m`.\n",
        "**The optimized objective is not real daylight**: see the header of "
        "`experiments/j9_orientation.py`. What is guaranteed is geometric.\n",
        "| plan | rooms | azimuth of the best sDA | gain | displacement | "
        "smallest side | valid variants |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]

    kept = 0
    for plan_json in rows:
        if kept >= n_plans:
            break
        built = _build(plan_json, scale)
        if isinstance(built, str):
            continue
        proposed, context, diag = built
        try:
            valid = ax.legalize(proposed, context, tiling=True, repair_budget=BUDGETS[-1])
        except ax.ArchluxError:
            continue
        if not valid.certificate.geometry.valid or len(valid.rooms) < 4:
            continue
        kept += 1

        panels: list[tuple[object, str]] = []
        scores: list[tuple[int, float, float, float, float, float, float]] = []
        for azimuth in AZIMUTHS:
            ctx_az = replace(context, orientation=Orientation(deg=float(azimuth)))
            before = _score(valid, ctx_az, surrogate)
            try:
                variant = ax.legalize(valid, ctx_az, objective=surrogate, budget=budget)
            except ax.ArchluxError:
                panels.append((valid, f"{azimuth}° — no variant"))
                continue
            after = _score(variant, ctx_az, surrogate)
            moved = max(
                max(abs(a.x - b.x), abs(a.y - b.y), abs(a.w - b.w), abs(a.h - b.h))
                for a, b in zip(valid.rooms, variant.rooms, strict=True)
            )
            sides = [min(q.w, q.h) for q in variant.rooms]
            areas = [q.area for q in variant.rooms]
            scores.append((azimuth, before, after, moved, min(sides), min(areas), max(areas)))
            gain = 100 * (after - before) / max(abs(before), 1e-9)
            panels.append((variant, f"{azimuth}° — sDA {after:.0f} ({gain:+.0f} %)"))

        name = plan_json["id"]
        (ROOT / f"{name}.svg").write_text(
            sheet(tuple(panels), outline=context.outline, columns=4),
            encoding="utf-8",
        )
        page = [
            f"# {name}: variants by azimuth\n",
            f"{len(valid.rooms)} rooms, characteristic side {diag.size:.2f} m, "
            f"budget {budget:.1f} m.\n",
            "| azimuth | legalized sDA | variant sDA | gain | displacement | "
            "smallest side | min area | max area |",
            "|--:|--:|--:|--:|--:|--:|--:|--:|",
        ]
        for azimuth, before, after, moved, size, amin, amax in scores:
            page.append(
                f"| {azimuth}° | {before:.2f} | {after:.2f} | "
                f"{100 * (after - before) / max(abs(before), 1e-9):+.1f} % | "
                f"{moved:.2f} m | {size:.2f} m | {amin:.1f} m² | {amax:.1f} m² |"
            )
        page.append(
            "\nAll listed variants are **certified valid**: "
            "Frank-Wolfe does not leave the polytope.\n"
        )
        page.append(
            "The last three columns are not decorative. "
            "`Surrogate.evaluate` returns **a sum over the rooms**: maximizing it "
            "therefore rewards concentrating the area in the best-oriented room and "
            "pushing the others down to the `min_width` floor. This is the granularity "
            "problem documented in `docs/limitations.md`, made visible: a **per-room** "
            "indicator, as a real sDA is, would not behave this way.\n"
        )
        (ROOT / f"{name}.md").write_text("\n".join(page) + "\n", encoding="utf-8")

        if scores:
            best = max(scores, key=lambda s: s[2])
            index.append(
                f"| [`{name}`]({name}.md) | {len(valid.rooms)} | {best[0]}° | "
                f"{100 * (best[2] - best[1]) / max(abs(best[1]), 1e-9):+.0f} % | "
                f"{best[3]:.2f} m | {min(s[4] for s in scores):.2f} m | "
                f"{len(scores)} / {len(AZIMUTHS)} |"
            )

    (ROOT / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"{kept} plans -> {ROOT}")


if __name__ == "__main__":
    main()
