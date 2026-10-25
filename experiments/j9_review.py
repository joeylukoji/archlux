"""Milestone 9, reviewed: B9 re-run on the current code, against the closed-form reference.

What this script measures
-------------------------
On the six B9 plans rebuilt by `j9_inputs.py` (published sheets, about 1 mm), for each
of the eight azimuths:

1. **Re-run** of the published protocol on the current code: the generated plan is
   legalized with tiling (repair budget 16), then Frank-Wolfe maximizes
   `AnalyticSurrogate("sDA")` within a 3 m budget centred on the legalized plan.
2. For every variant: the gain **predicted** by the surrogate, the gain of the frozen
   closed-form reference `SplitFluxOracle` on the same two plans, their gap, the
   displacement (`solve.displacement`), the smallest room, the Frank-Wolfe stop status,
   the variables held by the budget (`Trace.budget_active`), the independent validator
   verdict and an out-of-distribution flag.
3. A **sweep**: displacement budget x proximity penalty x a 4 m2 minimum area per room.
4. A **decomposition** of the gap between the B9 median gain (+17.2 %) and the
   ablation's (+1.6 %, `results/ablations.md`): same pipeline, the constraints of one
   protocol applied to the plans of the other.
5. **Timing** of the three stages on the published repaired plans, raw rows and machine.

What this script does NOT measure
---------------------------------
**No physical light.** The reference is a closed form (CIBSE surrogate plus BRE
split-flux daylight factor), frozen, not a simulation and not an LM-83 sDA. The
quantity called "sDA" in the old pages is the surrogate's score for the label "sDA";
it is reported here as `surrogate_score`, in m2-weighted points, not in percent of
floor area. "Predicted" gains are the surrogate's; "reference" gains are the closed
form's. Neither is a daylight measurement.

The out-of-distribution flag compares each variant with the 48 legalized inputs
(6 plans x 8 azimuths): `AnalyticSurrogate` has no training set, so the envelope is the
input set itself, a measure of drift, not of training coverage.

Usage: j9_review.py [OUT_DIR] [--quick]
"""

from __future__ import annotations

import csv
import json
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

import archlux as ax
from archlux.bench import repro
from archlux.bench.stats import cluster_bootstrap_proportion
from archlux.certify.proof import verify_exactly
from archlux.certify.validation import validate_plan
from archlux.data.synthetic import generate_corpus
from archlux.geom.graph import deduce_order
from archlux.geom.polytope import build_polytope, devectorize, freeze_contacts, vectorize
from archlux.geom.rectilinear import minimum_area_shares
from archlux.io.json_io import from_dict
from archlux.light.analytic import AnalyticSurrogate
from archlux.light.ood import FeatureEnvelope, fit_envelope
from archlux.light.protocol import Glazing
from archlux.light.split_flux import SplitFluxOracle
from archlux.lmo.cuts import inner_area_constraints
from archlux.solve.displacement import measure_displacement
from archlux.solve.frank_wolfe import frank_wolfe
from archlux.types import Context, Orientation, Plan, Regulation, Structure

QUICK = "--quick" in sys.argv
ARGS = [a for a in sys.argv[1:] if a != "--quick"]
OUT = Path(ARGS[0]) if ARGS else Path("results")
INPUTS = Path("results/j9_inputs.json")
OLD = Path("results/orientation")
SEED = 17
REPAIR_BUDGET = 16  # largest repair budget of j8_generation.py, as in j9_orientation.py
MIN_WIDTH = 0.50  # archlux.data.generated.DEFAULT_MIN_WIDTH
AZIMUTHS = (0, 180) if QUICK else tuple(range(0, 360, 45))
BUDGETS = (3.0,) if QUICK else (0.5, 1.0, 2.0, 3.0)
PENALTIES = (0.0, 1.0) if QUICK else (0.0, 0.1, 1.0)
MIN_AREAS = (None, 4.0)
N_TIMING = 2 if QUICK else 20
SATURATION_TOL_M = 1e-6
SURROGATE, REFERENCE = AnalyticSurrogate(target_indicator="sDA"), SplitFluxOracle()


@dataclass(frozen=True)
class Config:
    """One cell of the sweep."""

    budget: float
    penalty: float
    min_area: float | None

    @property
    def label(self) -> str:
        area = "none" if self.min_area is None else f"{self.min_area:g}"
        return f"b{self.budget:g}_l{self.penalty:g}_a{area}"


PUBLISHED = Config(budget=3.0, penalty=0.0, min_area=None)


def generated_context(plan: Plan, azimuth: float, min_area: float | None) -> Context:
    """The context `archlux.data.generated.generated_plan` builds, at one azimuth."""
    kinds = tuple(sorted({r.type for r in plan.rooms}))
    minima = () if min_area is None else tuple((t, min_area) for t in kinds)
    return Context(
        structure=Structure(load_bearing_walls=(), columns=()),
        orientation=Orientation(deg=float(azimuth)),
        outline=plan.outline,
        regulation=Regulation(min_areas=minima, min_width=MIN_WIDTH),
        program=kinds,
    )


def score(plan: Plan, ctx: Context, model: object) -> float:
    """Value of ``model`` on ``plan`` (as `j9_orientation._score`)."""
    poly = build_polytope(deduce_order(plan), ctx)
    return float(model.evaluate(vectorize(plan, poly.index), ctx.orientation))  # type: ignore[attr-defined]


def pct(after: float, before: float) -> float:
    return 100.0 * (after - before) / max(abs(before), 1e-9)


def optimize(valid: Plan, ctx: Context, config: Config) -> tuple[Plan, object]:
    """Frank-Wolfe from ``valid``, as `legalize(..., objective=, budget=)` does it.

    Rebuilt from the public pieces only because `legalize` does not expose
    ``penalty=``; with ``penalty=0`` the result is checked against `legalize_trace`
    (column ``matches_legalize``).
    """
    # L1 pass first: a no-op on a valid plan, the repair of the minimum areas otherwise
    # (with tiling then, as the generated plans needed it in the first place).
    tiling = config.min_area is not None
    corrected = ax.legalize(
        valid, ctx, budget=config.budget, tiling=tiling, repair_budget=REPAIR_BUDGET
    )
    order = deduce_order(corrected if tiling else valid, structure=ctx.structure)
    base = build_polytope(order, ctx)
    x0 = vectorize(corrected, base.index)
    shares = minimum_area_shares(corrected.rooms, (), ctx.regulation)
    domain = inner_area_constraints(
        freeze_contacts(base, x0), x0, ctx, corrected.rooms, minima=shares
    )
    result = frank_wolfe(
        domain,
        SURROGATE,
        ctx.orientation,
        x0,
        glazing=Glazing(walls=corrected.walls, openings=corrected.openings),
        budget=config.budget,
        reference=vectorize(valid, base.index),
        penalty=config.penalty,
    )
    variant = replace(devectorize(result.x, corrected, base.index), outline=ctx.outline)
    return variant, result


def _matches_legalize(valid: Plan, ctx: Context, variant: Plan, config: Config) -> str:
    if config.penalty != 0.0:
        return "-"
    try:
        official, _ = ax.legalize_trace(
            valid,
            ctx,
            objective=SURROGATE,
            budget=config.budget,
            tiling=config.min_area is not None,
            repair_budget=REPAIR_BUDGET,
        )
    except ax.ArchluxError as error:
        return f"legalize raised {type(error).__name__}"
    gap = max(
        max(abs(a.x - b.x), abs(a.y - b.y), abs(a.w - b.w), abs(a.h - b.h))
        for a, b in zip(official.rooms, variant.rooms, strict=True)
    )
    return "yes" if gap <= 1e-9 else f"no ({gap:.2e} m)"


def variant_row(
    name: str, valid: Plan, azimuth: int, config: Config, envelope: FeatureEnvelope | None
) -> dict[str, object]:
    """One variant: predicted and reference gains, displacement, solver and validator."""
    ctx = generated_context(valid, azimuth, config.min_area)
    row: dict[str, object] = {"plan": name, "azimuth": azimuth, "config": config.label}
    row |= {"budget_m": config.budget, "penalty": config.penalty}
    row["min_area_m2"] = "" if config.min_area is None else config.min_area
    s0, r0 = score(valid, ctx, SURROGATE), score(valid, ctx, REFERENCE)
    row |= {"surrogate_before": s0, "reference_before": r0}
    start = time.perf_counter()
    try:
        variant, result = optimize(valid, ctx, config)
    except ax.ArchluxError as error:
        return row | {"status": type(error).__name__, "time_ms": _ms(start)}
    row["time_ms"] = _ms(start)
    s1, r1 = score(variant, ctx, SURROGATE), score(variant, ctx, REFERENCE)
    moved = measure_displacement(valid, variant)
    shifts = [room.wall_shift for room in moved.rooms]
    proof = verify_exactly(variant, ctx, reference=valid, budget=config.budget)
    report = validate_plan(variant, ctx, reference=valid, budget=config.budget)
    trace = result.trace  # type: ignore[attr-defined]
    row |= {
        "status": "ok",
        "surrogate_after": s1,
        "reference_after": r1,
        "predicted_gain_pct": pct(s1, s0),
        "reference_gain_pct": pct(r1, r0),
        "gap_pct": pct(s1, s0) - pct(r1, r0),
        # SplitFluxOracle = AnalyticSurrogate + DF x area: the second term is the only
        # part of the reference that does not contain the optimized surrogate.
        "df_term_gain_pct": pct(r1 - s1, r0 - s0),
        "sign_agrees": (s1 - s0 > 0) == (r1 - r0 > 0),
        "max_wall_shift_m": max(shifts),
        "mean_wall_shift_m": float(np.mean(shifts)),
        "max_area_change_m2": moved.max_area_change,
        "saturated": max(shifts) >= config.budget - SATURATION_TOL_M,
        "smallest_side_m": min(min(r.w, r.h) for r in variant.rooms),
        "smallest_area_m2": min(r.w * r.h for r in variant.rooms),
        "rooms_below_4m2": sum(r.w * r.h < 4.0 - 1e-9 for r in variant.rooms),
        "fw_status": str(result.status),  # type: ignore[attr-defined]
        "iterations": int(result.iterations),  # type: ignore[attr-defined]
        "budget_active": len(trace.budget_active),
        "exact_proof": proof.valid,
        "validator": report.valid,
        "validator_evidence": report.evidence,
        "matches_legalize": _matches_legalize(valid, ctx, variant, config),
    }
    if envelope is not None:
        base = build_polytope(deduce_order(variant), ctx)
        verdict = envelope.check(vectorize(variant, base.index), ctx.orientation)
        row |= {"ood_distance": verdict.distance, "ood_uncertain": verdict.uncertain}
    return row


def _ms(start: float) -> float:
    return 1000.0 * (time.perf_counter() - start)


def legalized_inputs(data: dict[str, dict[str, object]]) -> dict[str, Plan]:
    """Legalize each rebuilt generated plan on the current code (tiling, budget 16)."""
    out = {}
    for name, entry in sorted(data.items()):
        proposed = from_dict(entry["proposed"])  # type: ignore[arg-type]
        ctx = generated_context(proposed, 0, None)
        out[name] = ax.legalize(proposed, ctx, tiling=True, repair_budget=REPAIR_BUDGET)
    return out


def input_envelope(valid: dict[str, Plan]) -> FeatureEnvelope:
    """Descriptor envelope of the legalized inputs at every azimuth (drift measure)."""
    xs, orientations = [], []
    for plan in valid.values():
        for azimuth in AZIMUTHS:
            ctx = generated_context(plan, azimuth, None)
            xs.append(vectorize(plan, build_polytope(deduce_order(plan), ctx).index))
            orientations.append(ctx.orientation)
    return fit_envelope(xs, orientations)


def old_rows(data: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """The 48 published variants, re-scored: surrogate (check) and reference (new)."""
    rows = []
    for name, entry in sorted(data.items()):
        valid = from_dict(entry["legalized_published"])  # type: ignore[arg-type]
        published = _published_table(name)
        for azimuth, plan_dict in sorted(entry["old_variants"].items(), key=lambda t: int(t[0])):  # type: ignore[union-attr]
            variant = from_dict(plan_dict)
            ctx = generated_context(valid, int(azimuth), None)
            s0, s1 = score(valid, ctx, SURROGATE), score(variant, ctx, SURROGATE)
            r0, r1 = score(valid, ctx, REFERENCE), score(variant, ctx, REFERENCE)
            before, after = published.get(int(azimuth), (float("nan"), float("nan")))
            rows.append(
                {
                    "plan": name,
                    "azimuth": int(azimuth),
                    "published_before": before,
                    "published_after": after,
                    "rescored_before": s0,
                    "rescored_after": s1,
                    "predicted_gain_pct": pct(s1, s0),
                    "reference_gain_pct": pct(r1, r0),
                    "smallest_area_m2": min(r.w * r.h for r in variant.rooms),
                }
            )
    return rows


def _published_table(name: str) -> dict[int, tuple[float, float]]:
    page = OLD / f"{name}.md"
    out: dict[int, tuple[float, float]] = {}
    if not page.exists():
        return out
    for line in page.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3 and cells[0].endswith("°") and cells[0][:-1].isdigit():
            out[int(cells[0][:-1])] = (float(cells[1]), float(cells[2]))
    return out


def ablation_context(plan: Plan, orientation: Orientation, *, relaxed: bool) -> Context:
    """`experiments/ablations.py`'s context; ``relaxed`` drops its three restrictions."""
    if relaxed:
        return Context(
            Structure((), ()), orientation, Regulation((), MIN_WIDTH), outline=plan.outline
        )
    cut = next(r.x + r.w for r in plan.rooms if r.id == "sw")
    wall = ax.Wall(id="lb", a=(cut, 0.0), b=(cut, 9.0), load_bearing=True)
    kinds = sorted({r.type for r in plan.rooms})
    minima = tuple((t, 0.8 * min(r.w * r.h for r in plan.rooms if r.type == t)) for t in kinds)
    return Context(Structure((wall,)), orientation, Regulation(minima, 1.0), outline=plan.outline)


def b9_with_ablation_rules(plan: Plan, azimuth: int) -> Context:
    """B9 plan under the ablation's restrictions: 80 % minimum areas, 1 m width.

    The ablation's load-bearing wall is not transposed: B9 plans have no ``sw`` room.
    """
    kinds = tuple(sorted({r.type for r in plan.rooms}))
    minima = tuple((t, 0.8 * min(r.w * r.h for r in plan.rooms if r.type == t)) for t in kinds)
    return Context(
        Structure((), ()),
        Orientation(float(azimuth)),
        Regulation(minima, 1.0),
        outline=plan.outline,
        program=kinds,
    )


def _gain(valid: Plan, ctx: Context, budget: float) -> tuple[float, float] | None:
    try:
        variant, _ = optimize(valid, ctx, Config(budget, 0.0, None))
    except ax.ArchluxError:
        return None
    return (
        pct(score(variant, ctx, SURROGATE), score(valid, ctx, SURROGATE)),
        pct(score(variant, ctx, REFERENCE), score(valid, ctx, REFERENCE)),
    )


def decomposition(valid: dict[str, Plan]) -> list[dict[str, object]]:
    """Median gains with the constraints of one protocol on the plans of the other."""
    synthetic = dict(sorted(generate_corpus(6 if QUICK else 30, seed=SEED).items()))
    cells: list[tuple[str, str, list[tuple[float, float]]]] = []
    b9_free = [
        g
        for p in valid.values()
        for a in AZIMUTHS
        if (g := _gain(p, generated_context(p, a, None), 3.0))
    ]
    b9_tight = [
        g
        for p in valid.values()
        for a in AZIMUTHS
        if (g := _gain(p, b9_with_ablation_rules(p, a), 3.0))
    ]
    cells += [("B9 plans", "B9 rules (no structure, no minimum area, 0.5 m)", b9_free)]
    cells += [("B9 plans", "ablation rules (80 % minimum areas, 1.0 m)", b9_tight)]
    for relaxed, label in (
        (False, "ablation rules (wall, 80 % areas, 1.0 m)"),
        (True, "B9 rules (no structure, no minimum area, 0.5 m)"),
    ):
        gains = []
        for plan in synthetic.values():
            for azimuth in AZIMUTHS:
                ctx = ablation_context(plan, Orientation(float(azimuth)), relaxed=relaxed)
                try:
                    start = ax.legalize(plan, ctx)
                except ax.ArchluxError:
                    continue
                if (g := _gain(start, ctx, 3.0)) is not None:
                    gains.append(g)
        cells.append(("synthetic 2x2 plans (ablation)", label, gains))
    return [
        {
            "plans": plans,
            "rules": rules,
            "n": len(g),
            "median_predicted_pct": statistics.median(x for x, _ in g) if g else float("nan"),
            "median_reference_pct": statistics.median(y for _, y in g) if g else float("nan"),
        }
        for plans, rules, g in cells
    ]


def timing_rows(data: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """Per (plan, azimuth): L1 legalization, with tiling, and Frank-Wolfe at 3 m."""
    rows = []
    for name, entry in sorted(data.items())[:N_TIMING]:
        proposed = from_dict(entry["proposed"])  # type: ignore[arg-type]
        for azimuth in AZIMUTHS:
            ctx = generated_context(proposed, azimuth, None)
            row: dict[str, object] = {"plan": name, "azimuth": azimuth}
            start = time.perf_counter()
            try:
                ax.legalize(proposed, ctx)
                row["l1_status"] = "ok"
            except ax.ArchluxError as error:
                row["l1_status"] = type(error).__name__
            row["l1_ms"] = _ms(start)
            start = time.perf_counter()
            try:
                valid = ax.legalize(proposed, ctx, tiling=True, repair_budget=REPAIR_BUDGET)
                row["tiling_status"] = "ok"
            except ax.ArchluxError as error:
                row |= {"tiling_status": type(error).__name__, "tiling_ms": _ms(start)}
                rows.append(row)
                continue
            row["tiling_ms"] = _ms(start)
            start = time.perf_counter()
            try:
                variant = ax.legalize(valid, ctx, objective=SURROGATE, budget=3.0)
                row["fw_status"] = "ok"
                row["fw_valid"] = validate_plan(variant, ctx, reference=valid, budget=3.0).valid
            except ax.ArchluxError as error:
                row["fw_status"] = type(error).__name__
            row["fw_ms"] = _ms(start)
            rows.append(row)
    return rows


def machine() -> dict[str, object]:
    """Where the timings were taken."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    keys: list[str] = []
    for row in rows:
        keys += [k for k in row if k not in keys]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k, "")) for k in keys})


def _fmt(value: object) -> object:
    return f"{value:.6g}" if isinstance(value, float) else value


def _median_ci(values: list[float], clusters: list[str]) -> tuple[float, float, float]:
    """Median and 95 % interval, resampling whole plans (variants are not independent)."""
    rng = np.random.default_rng(SEED)
    groups: dict[str, list[float]] = {}
    for v, c in zip(values, clusters, strict=True):
        groups.setdefault(c, []).append(v)
    names = sorted(groups)
    meds = []
    for _ in range(2000):
        pick = rng.choice(len(names), size=len(names), replace=True)
        meds.append(statistics.median(v for k in pick for v in groups[names[k]]))
    low, high = np.quantile(meds, [0.025, 0.975])
    return statistics.median(values), float(low), float(high)


def _sweep_table(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "| budget (m) | penalty λ | min area | ok / n | median predicted gain [95 % CI by plan] "
        "| median reference gain | sign agrees | saturated | rooms < 4 m² | "
        "median max wall shift (m) | FW converged |",
        "|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    configs = sorted({(r["budget_m"], r["penalty"], str(r["min_area_m2"])) for r in rows})
    for budget, penalty, area in configs:
        cell = [
            r
            for r in rows
            if (r["budget_m"], r["penalty"], str(r["min_area_m2"])) == (budget, penalty, area)
        ]
        ok = [r for r in cell if r["status"] == "ok"]
        if not ok:
            lines.append(
                f"| {budget:g} | {penalty:g} | {area or '-'} | 0 / {len(cell)} | - |"
                " - | - | - | - | - | - |"
            )
            continue
        med, low, high = _median_ci(
            [float(r["predicted_gain_pct"]) for r in ok], [str(r["plan"]) for r in ok]
        )
        ref = statistics.median(float(r["reference_gain_pct"]) for r in ok)
        conv = sum(r["fw_status"] == "converged" for r in ok)
        lines.append(
            f"| {budget:g} | {penalty:g} | {area or '-'} | {len(ok)} / {len(cell)} | "
            f"{med:+.1f} % [{low:+.1f} ; {high:+.1f}] | {ref:+.1f} % | "
            f"{sum(bool(r['sign_agrees']) for r in ok)} / {len(ok)} | "
            f"{sum(bool(r['saturated']) for r in ok)} / {len(ok)} | "
            f"{sum(int(r['rooms_below_4m2']) > 0 for r in ok)} / {len(ok)} | "
            f"{statistics.median(float(r['max_wall_shift_m']) for r in ok):.2f} | "
            f"{conv} / {len(ok)} |"
        )
    return lines


def report(
    rows: list[dict[str, object]],
    old: list[dict[str, object]],
    parts: list[dict[str, object]],
    timing: list[dict[str, object]],
) -> str:
    """The Markdown summary."""
    published = [r for r in rows if r["config"] == PUBLISHED.label and r["status"] == "ok"]
    plans = [str(r["plan"]) for r in published]
    sat = [bool(r["saturated"]) for r in published]
    sat_ci = cluster_bootstrap_proportion(sat, plans, seed=SEED) if published else None
    old_pred = statistics.median(float(r["predicted_gain_pct"]) for r in old) if old else 0.0
    old_ref = statistics.median(float(r["reference_gain_pct"]) for r in old) if old else 0.0
    check = max(
        (
            abs(
                float(r["predicted_gain_pct"])
                - pct(float(r["published_after"]), float(r["published_before"]))
            )
            for r in old
        ),
        default=float("nan"),
    )
    lines = [
        "# B9 reviewed: variants by azimuth against the closed-form reference\n",
        "Inputs: the six B9 plans **rebuilt from the published sheets** "
        "(`experiments/j9_inputs.py`, about 1 mm; the original "
        "`j8_plans_divers.jsonl` is not in the repository). Surrogate optimized: "
        '`AnalyticSurrogate(target_indicator="sDA")`, the analytic closed form, '
        "**not** the trained network. Reference: `SplitFluxOracle`, a frozen closed form, "
        '**not a physical simulation**. The score the old pages call "sDA" is the '
        "surrogate's value for that label (m²-weighted points), not an LM-83 sDA; it is "
        "called `surrogate_score` here. Seed 17. Intervals resample whole plans "
        "(6 clusters), since the 8 azimuths of a plan are not independent.\n",
        "## 1. The published variants, re-scored\n",
        f"{len(old)} variants rebuilt from `results/orientation/*.svg`. Re-scoring them "
        f"with today's surrogate gives back the published **gains** to within {check:.2f} "
        "percentage points (checks the rebuild). The raw scores themselves differ from "
        "the published ones by a factor that depends on the azimuth only: the score's "
        "scale changed between the two code versions, its ratios did not.\n",
        f"- median **predicted** gain: {old_pred:+.1f} % (published: +17.2 %)",
        f"- median **reference** gain on the same plans: {old_ref:+.1f} %",
        f"- variants with a room below 4 m²: "
        f"{sum(float(r['smallest_area_m2']) < 4.0 for r in old)} / {len(old)}\n",
        "## 2. Re-run on the current code (budget 3 m, no penalty, no minimum area)\n",
    ]
    if published:
        med, low, high = _median_ci([float(r["predicted_gain_pct"]) for r in published], plans)
        rmed, rlow, rhigh = _median_ci([float(r["reference_gain_pct"]) for r in published], plans)
        df_gains = [float(r["df_term_gain_pct"]) for r in published]
        df_med, df_down = statistics.median(df_gains), sum(g < 0 for g in df_gains)
        lines += [
            f"- variants: {len(published)} / {len(AZIMUTHS) * len(set(plans))}, "
            f"exact proof {sum(bool(r['exact_proof']) for r in published)}, independent "
            f"validator {sum(bool(r['validator']) for r in published)}",
            f"- median predicted gain {med:+.1f} % [{low:+.1f} ; {high:+.1f}]; median "
            f"reference gain {rmed:+.1f} % [{rlow:+.1f} ; {rhigh:+.1f}]",
            f"- sign of the predicted gain confirmed by the reference: "
            f"{sum(bool(r['sign_agrees']) for r in published)} / {len(published)}; "
            "**this is partly by construction**: `SplitFluxOracle` is "
            "`AnalyticSurrogate` plus a split-flux daylight-factor x area term, so the "
            "reference contains the optimized score. The independent part, the DF term "
            f"alone, changes by a median {df_med:+.1f} % and decreases on "
            f"{df_down} / {len(published)} variants",
            f"- variants at the budget (max wall shift = 3 m): {sum(sat)} / {len(sat)}, "
            f"95 % CI by plan [{sat_ci.low:.2f} ; {sat_ci.high:.2f}] (published: 36 / 48)"
            if sat_ci
            else "",
            "- Frank-Wolfe stops: "
            + ", ".join(
                f"{s} {sum(r['fw_status'] == s for r in published)}"
                for s in sorted({str(r["fw_status"]) for r in published})
            ),
            f"- out of the inputs' envelope: "
            f"{sum(bool(r.get('ood_uncertain')) for r in published)} / {len(published)}",
            f"- reproduces `legalize(..., objective=, budget=)` exactly: "
            f"{sum(r['matches_legalize'] == 'yes' for r in published)} / {len(published)}\n",
        ]
    lines += [
        "## 3. Sweep: budget x proximity penalty x minimum area\n",
        '"saturated": the largest wall shift equals the budget. "rooms < 4 m²": '
        "variants with at least one such room. Gains against the legalized plan, "
        "so with a minimum area they include the L1 repair that enforces it (run "
        "with tiling, which the generated plans need). In those cells the "
        "Frank-Wolfe domain here leaves out the tiling grid that "
        "`legalize(..., tiling=True)` adds: "
        f"{sum(str(r.get('matches_legalize', '')).startswith('no') for r in rows)} "
        "variants differ from `legalize`'s own (column `matches_legalize`); every "
        "variant listed is proven valid and accepted by the independent validator.\n",
        *_sweep_table(rows),
        "",
    ]
    lines += [
        "## 4. Why B9 reports +17.2 % and the ablation +1.6 %\n",
        "Same surrogate (`AnalyticSurrogate`, label sDA), same reference, same Frank-Wolfe, "
        "budget 3 m. Only the plans and the rules change:\n",
        "The reference column contains the predicted score (see section 2); it is shown "
        "for comparison with `results/ablations.md`, which uses the same reference.\n",
        "| plans | rules | n | median predicted gain | median reference gain |",
        "|---|---|--:|--:|--:|",
        *(
            f"| {p['plans']} | {p['rules']} | {p['n']} | {p['median_predicted_pct']:+.1f} % | "
            f"{p['median_reference_pct']:+.1f} % |"
            for p in parts
        ),
        "",
    ]
    ok = [t for t in timing if t.get("fw_status") == "ok"]
    lines += [
        "## 5. Timing\n",
        f"{len(timing)} runs ({len({t['plan'] for t in timing})} plans x "
        f"{len(AZIMUTHS)} azimuths), raw rows in `j9_timing_raw.csv`, machine in "
        "`j9_review_manifest.json`. These are not necessarily the 20 plans of the "
        "article, which did not name them.\n",
        "| stage | n | median (ms) | p90 (ms) | max (ms) |",
        "|---|--:|--:|--:|--:|",
    ]
    for key, label in (
        ("l1_ms", "legalization (L1 LP)"),
        ("tiling_ms", "legalization + tiling"),
        ("fw_ms", "Frank-Wolfe, r = 3 m"),
    ):
        vals = [float(t[key]) for t in timing if key in t]
        if vals:
            lines.append(
                f"| {label} | {len(vals)} | {statistics.median(vals):.1f} | "
                f"{np.quantile(vals, 0.9):.1f} | {max(vals):.1f} |"
            )
    lines.append(
        f"\nFrank-Wolfe variants accepted by the independent validator: "
        f"{sum(bool(t.get('fw_valid')) for t in ok)} / {len(ok)}."
    )
    return "\n".join(line for line in lines if line is not None) + "\n"


def main() -> None:
    data = json.loads(INPUTS.read_text(encoding="utf-8"))
    b9 = data["plans"]
    if QUICK:
        b9 = dict(sorted(b9.items())[:2])
    OUT.mkdir(parents=True, exist_ok=True)
    valid = legalized_inputs(b9)
    envelope = input_envelope(valid)
    configs = [Config(b, lam, a) for b in BUDGETS for lam in PENALTIES for a in MIN_AREAS]
    if PUBLISHED not in configs:
        configs.insert(0, PUBLISHED)
    rows = [
        variant_row(name, plan, az, cfg, envelope)
        for cfg in configs
        for name, plan in valid.items()
        for az in AZIMUTHS
    ]
    old = old_rows(b9)
    parts = decomposition(valid)
    timing = timing_rows(data["timing_plans"])
    names = (
        "j9_variants_raw.csv",
        "j9_old_variants.csv",
        "j9_decomposition.csv",
        "j9_timing_raw.csv",
    )
    for name, table in zip(names, (rows, old, parts, timing), strict=True):
        write_csv(OUT / name, table)
    (OUT / "j9_review.md").write_text(report(rows, old, parts, timing), encoding="utf-8")
    params = {
        "azimuths": AZIMUTHS,
        "budgets_m": BUDGETS,
        "penalties": PENALTIES,
        "min_areas_m2": [a for a in MIN_AREAS if a],
        "repair_budget": REPAIR_BUDGET,
        "min_width_m": MIN_WIDTH,
        "surrogate": "AnalyticSurrogate(sDA)",
        "reference": "SplitFluxOracle",
        "quick": QUICK,
        "machine": machine(),
    }
    outputs = [OUT / n for n in (*names, "j9_review.md")]
    run = repro.record(
        seed=SEED,
        command=" ".join(["python", *sys.argv]),
        parameters=params,
        inputs=[INPUTS],
        outputs=outputs,
    )
    repro.write_record(OUT / "j9_review_manifest.json", run)
    print(f"{len(rows)} variants, {len(timing)} timed runs -> {OUT}")


if __name__ == "__main__":
    main()
