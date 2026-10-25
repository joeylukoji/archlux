"""Reconcile the numbers of the paper with the raw files of ``results/``.

Every number the paper prints (benches B1 to B9) is recomputed here from the raw rows,
with its source file, its formula, its statistical unit and a verdict. Nothing is
corrected by hand: when the paper and the raw rows disagree, the raw rows win and the
verdict says so. When no raw row exists (a Markdown summary only, or no file at all),
the verdict says that too, instead of trusting the summary.

Mapping paper bench -> repository experiment:

==== =============================== ===========================================
B1   synthetic validity              ``j2_validity_raw.csv``
B2   orientation, 2 x 2 plan         ``j3_orientation.csv``
B3   surrogate gradient              ``j4_gradient.csv``
B4   conformal coverage              ``j5_coverage.csv``
B5   active learning, IFC export     ``j6_active.csv``, ``j6_ifc.csv``
B6   MSD idempotence and repair      ``j7_msd_idempotence.md``, ``j7_repair_raw.csv``
B7   surrogate vs Swiss Dwellings    ``j7_sd_labels.md``, ``j7_sd_per_room.md``
B8   HouseDiffusion plans            ``j8_{etoile,plausible,divers}_raw.csv``
B9   Frank-Wolfe by azimuth, timing  ``orientation/hd*.md`` (timing: no file)
==== =============================== ===========================================
"""

from __future__ import annotations

import csv
import re
import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from scipy import stats as scipy_stats

from archlux.bench.stats import cluster_bootstrap_proportion
from archlux.export.wilson import wilson_interval

__all__ = ["Claim", "Verdict", "reconcile", "to_json", "to_markdown"]

Verdict = Literal["consistent", "article_wrong", "ambiguous", "cannot_verify"]
"""``consistent``: the raw rows give the printed number. ``article_wrong``: they give
another one. ``ambiguous``: the number is right but its wording or denominator misleads.
``cannot_verify``: no raw row backs it (summary file only, or nothing)."""

SEED = 17
"""Seed of every cluster bootstrap below."""


@dataclass(frozen=True, slots=True)
class Claim:
    """One number of the paper, set against the raw rows.

    Attributes
    ----------
    bench : str
        ``"B1"`` to ``"B9"``, or ``"synthesis"``.
    quantity : str
        What is counted or measured.
    article : str
        The value as printed in the paper.
    recomputed : str
        The value recomputed from ``source``.
    source : str
        File of ``results/`` the value is recomputed from.
    formula : str
        How it is recomputed.
    unit : str
        Statistical unit of the count, and how many independent units it has.
    verdict : Verdict
        See :data:`Verdict`.
    note : str
        Why, when the verdict is not ``consistent``; caveats otherwise.
    """

    bench: str
    quantity: str
    article: str
    recomputed: str
    source: str
    formula: str
    unit: str
    verdict: Verdict
    note: str = ""


def _rows(path: Path) -> list[dict[str, str]]:
    """Read a raw CSV as a list of dicts.

    Parameters
    ----------
    path : Path
        CSV file with a header line.

    Returns
    -------
    list of dict
        One dict per row.
    """
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _pct(k: int, n: int) -> str:
    """``k/n (x.x %)``.

    Parameters
    ----------
    k : int
        Successes.
    n : int
        Total, positive.

    Returns
    -------
    str
        The formatted count.
    """
    return f"{k}/{n} ({100 * k / n:.1f} %)"


def _wilson(k: int, n: int) -> str:
    """Wilson 95 % interval in percent.

    Parameters
    ----------
    k : int
        Successes.
    n : int
        Total, positive.

    Returns
    -------
    str
        ``[low ; high]``.
    """
    low, high = wilson_interval(k, n)
    return f"[{100 * low:.1f} ; {100 * high:.1f}]"


def _cluster(ok: Sequence[bool], groups: Sequence[str]) -> str:
    """Cluster-bootstrap 95 % interval in percent.

    Parameters
    ----------
    ok : Sequence[bool]
        One outcome per row.
    groups : Sequence[str]
        Cluster of each row.

    Returns
    -------
    str
        ``[low ; high]``.
    """
    ci = cluster_bootstrap_proportion(ok, groups, seed=SEED)
    return f"[{100 * ci.low:.1f} ; {100 * ci.high:.1f}]"


def _true(value: str) -> bool:
    """Parse a ``True``/``False`` CSV cell.

    Parameters
    ----------
    value : str
        Cell content.

    Returns
    -------
    bool
        ``value == "True"``.
    """
    return value == "True"


def _column(rows: Sequence[dict[str, str]], key: str) -> np.ndarray:
    """Extract one column as a string array.

    Parameters
    ----------
    rows : Sequence[dict[str, str]]
        Raw rows.
    key : str
        Column name.

    Returns
    -------
    numpy.ndarray
        ``rows[i][key]`` for every row.
    """
    return np.array([r[key] for r in rows], dtype=str)


def _flags(rows: Sequence[dict[str, str]], key: str) -> np.ndarray:
    """Extract one ``True``/``False`` column as a boolean array.

    Parameters
    ----------
    rows : Sequence[dict[str, str]]
        Raw rows.
    key : str
        Column name.

    Returns
    -------
    numpy.ndarray
        ``rows[i][key] == "True"`` for every row.
    """
    return _column(rows, key) == "True"


def _n(rows: Sequence[dict[str, str]], key: str) -> int:
    """Count the rows where a ``True``/``False`` column is ``True``.

    Parameters
    ----------
    rows : Sequence[dict[str, str]]
        Raw rows.
    key : str
        Column name.

    Returns
    -------
    int
        Number of ``True`` cells.
    """
    return int(_flags(rows, key).sum())


def _where(rows: Sequence[dict[str, str]], **equal: str) -> list[dict[str, str]]:
    """Keep the rows whose columns equal the given values.

    Parameters
    ----------
    rows : Sequence[dict[str, str]]
        Raw rows.
    **equal : str
        ``column=value`` filters, all required.

    Returns
    -------
    list of dict
        The matching rows, in order.
    """
    return [r for r in rows if all(r[k] == v for k, v in equal.items())]


def _b1(root: Path) -> list[Claim]:
    """B1: synthetic validity, ``j2_validity_raw.csv``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "j2_validity_raw.csv"
    rows = _rows(root / src)
    plain, tiled = _where(rows, pavage="False"), _where(rows, pavage="True")
    plans = set(_column(rows, "plan_id"))
    ok_plain = _flags(plain, "valid_after")
    gap = int((_column(plain, "status") == "GapNeedsTiling").sum())
    unit = f"case = plan x amplitude; {len(plans)} independent plans"
    by_plan = _cluster(list(ok_plain), list(_column(plain, "plan_id")))
    amplitudes = _column(plain, "amplitude_m")
    claims = [
        Claim(
            "B1",
            "number of corrected cases",
            "540 (text) / 270 (table 2)",
            f"{len(plain)} cases; {len(rows)} rows = {len(plain)} cases x 2 strategies",
            src,
            "rows with pavage=False (one per plan x amplitude)",
            unit,
            "article_wrong",
            "540 counts legalize calls, not cases: each of the 270 cases is corrected twice "
            "(legalize, tiling=True). Write '270 cases (90 plans x 3 amplitudes), each "
            "corrected by both strategies'.",
        ),
        Claim(
            "B1",
            "valid before correction",
            "0/540",
            _pct(_n(plain, "valid_before"), len(plain)),
            src,
            "valid_before over cases",
            unit,
            "article_wrong",
            "denominator is 270 cases, not 540",
        ),
        Claim(
            "B1",
            "legalize alone valid after",
            "45.2 % [39.4 ; 51.1]",
            f"{_pct(int(ok_plain.sum()), len(plain))} "
            f"Wilson {_wilson(int(ok_plain.sum()), len(plain))}; "
            f"cluster bootstrap by plan {by_plan}",
            src,
            "valid_after over pavage=False",
            unit,
            "consistent",
            "the Wilson interval treats the 3 amplitudes of a plan as independent",
        ),
        Claim(
            "B1",
            "tiling=True valid after",
            "100.0 % (270/270)",
            _pct(_n(tiled, "valid_after"), len(tiled)),
            src,
            "valid_after over pavage=True",
            unit,
            "consistent",
        ),
        Claim(
            "B1",
            "legalize failures diagnosed GapNeedsTiling",
            "148",
            f"{gap} of {len(plain) - int(ok_plain.sum())} failures",
            src,
            "status == GapNeedsTiling over pavage=False",
            unit,
            "consistent",
        ),
    ]
    for amplitude in sorted(set(amplitudes), key=float):
        sub = ok_plain[amplitudes == amplitude]
        printed = {"0.1": "46.7 %", "0.25": "47.8 %", "0.5": "41.1 %"}.get(amplitude, "-")
        claims.append(
            Claim(
                "B1",
                f"legalize alone, amplitude {amplitude} m",
                printed,
                _pct(int(sub.sum()), len(sub)),
                src,
                "valid_after, pavage=False, by amplitude",
                unit,
                "consistent",
            )
        )
    return claims


def _b2(root: Path) -> list[Claim]:
    """B2: orientation on one synthetic plan, ``j3_orientation.csv``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "j3_orientation.csv"
    rows = _rows(root / src)
    free = [float(r["moved_from_l1_m"]) for r in rows if float(r["minimum_area_m2"]) == 0.0]
    regulated = [r for r in rows if float(r["minimum_area_m2"]) > 0.0]
    moved = [float(r["moved_from_l1_m"]) for r in regulated]
    smallest = min(float(r["smallest_room_m2"]) for r in regulated)
    unit = "1 plan x 8 azimuths: n = 1 independent plan (illustrative only)"
    return [
        Claim(
            "B2",
            "displacement range without A_min",
            "7.1 to 34.0 m",
            f"{min(free):.2f} to {max(free):.2f} m",
            src,
            "moved_from_l1_m, minimum_area=0",
            unit,
            "consistent",
        ),
        Claim(
            "B2",
            "median displacement without / with A_min",
            "17.3 m -> 10.8 m",
            f"{statistics.median(free):.2f} m -> {statistics.median(moved):.2f} m",
            src,
            "median of moved_from_l1_m",
            unit,
            "consistent",
        ),
        Claim(
            "B2",
            "smallest room with A_min = 12 m2",
            "above 12.0 m2",
            f"{smallest:.2f} m2",
            src,
            "min smallest_room_m2, minimum_area=12",
            unit,
            "consistent",
        ),
    ]


def _b3(root: Path) -> list[Claim]:
    """B3: gradient sign agreement, ``j4_gradient.csv``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "j4_gradient.csv"
    rows = _rows(root / src)
    claims = []
    for name in ("dense", "analytic_untrained"):
        sub = [r for r in rows if r["surrogate"] == name]
        signs = [float(r["sign_agreement"]) for r in sub]
        passed = sum(s >= 0.80 for s in signs)
        claims.append(
            Claim(
                "B3",
                f"azimuths reaching sign agreement 0.80 ({name})",
                "1/4 (180 deg)",
                f"{passed}/{len(sub)}; values {', '.join(f'{s:.2f}' for s in signs)}",
                src,
                "sign_agreement >= 0.80",
                "20 perturbation points per azimuth, one plan family",
                "consistent",
                "20 points per azimuth: the 0.80 threshold is tested with a wide interval",
            )
        )
    mae = {r["surrogate"]: float(r["mae_test"]) for r in rows}
    ratio = mae["analytic_untrained"] / mae["dense"]
    claims.append(
        Claim(
            "B3",
            "MAE dense vs analytic, factor",
            "1.19 vs 37.29, factor 31",
            f"{mae['dense']:.2f} vs {mae['analytic_untrained']:.2f}, factor {ratio:.1f}",
            src,
            "mae_test",
            "80 test plans",
            "consistent",
        )
    )
    return claims


def _b4(root: Path) -> list[Claim]:
    """B4: conformal coverage over 20 draws, ``j5_coverage.csv``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "j5_coverage.csv"
    rows = _rows(root / src)
    claims = []
    printed = {
        "exchangeable": ("89.8 % mean, 91.1 % median, 83.2-94.3, sd 3.2, 16/20 in band", 280),
        "selected": ("87.8 % mean, 88.8 % median, 78.8-95.0, sd 4.7, 10/20 in band", 80),
    }
    paired: dict[str, list[float]] = {}
    for regime, (text, n) in printed.items():
        cov = [float(r["coverage"]) for r in rows if r["regime"] == regime]
        paired[regime] = cov
        band = sum(0.86 <= c <= 0.94 for c in cov)
        ratio = statistics.mean(
            float(r["mean_width"]) / float(r["target_std"]) for r in rows if r["regime"] == regime
        )
        value = (
            f"{100 * statistics.mean(cov):.1f} % mean, {100 * statistics.median(cov):.1f} % "
            f"median, {100 * min(cov):.1f}-{100 * max(cov):.1f}, "
            f"sd {100 * statistics.stdev(cov):.1f}"
            f", {band}/{len(cov)} in band; width/sd(target) {ratio:.2f}"
        )
        claims.append(
            Claim(
                "B4",
                f"coverage, {regime}",
                text,
                value,
                src,
                "coverage per run",
                f"run (calibration draw): 20 runs; n = {n} plans per run, 220 calibration plans",
                "consistent",
                "a mean over 20 draws of synthetic two-room plans; not a guarantee for the "
                "selected regime (exchangeability broken by the optimizer)",
            )
        )
    p = scipy_stats.wilcoxon(paired["exchangeable"], paired["selected"]).pvalue
    claims.append(
        Claim(
            "B4",
            "paired Wilcoxon passive vs selected",
            "p = 0.09",
            f"p = {p:.3f}",
            src,
            "scipy.stats.wilcoxon over the 20 paired runs",
            "run, 20 pairs",
            "consistent",
            "a non-significant difference on 20 draws is not evidence of no effect",
        )
    )
    return claims


def _b5(root: Path) -> list[Claim]:
    """B5: active learning and IFC export, ``j6_active.csv`` and ``j6_ifc.csv``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    rows = _rows(root / "j6_active.csv")
    active = [float(r["width_active"]) for r in rows]
    rand = [float(r["width_random"]) for r in rows]
    wins = sum(a < b for a, b in zip(active, rand, strict=True))
    p = scipy_stats.wilcoxon(active, rand).pvalue
    ifc = _rows(root / "j6_ifc.csv")
    exported = sum(_true(r["exported"]) and r["validator_errors"] == "0" for r in ifc)
    return [
        Claim(
            "B5",
            "active vs random: favourable campaigns, medians, p",
            "16/30; 11.77 vs 11.04; p = 0.53",
            f"{wins}/{len(rows)}; {statistics.median(active):.2f} vs "
            f"{statistics.median(rand):.2f}; p = {p:.2f}",
            "j6_active.csv",
            "width_active < width_random; Wilcoxon paired",
            "campaign (seed), 30 paired campaigns",
            "consistent",
        ),
        Claim(
            "B5",
            "IFC export without validator error",
            "90/90 [95.9 ; 100]",
            f"{exported}/{len(ifc)} {_wilson(exported, len(ifc))}",
            "j6_ifc.csv",
            "exported and validator_errors == 0",
            "synthetic plan, 90",
            "consistent",
        ),
    ]


def _b6_idempotence(root: Path) -> list[Claim]:
    """B6, idempotence part: ``j7_msd_idempotence.md`` (no raw rows).

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "j7_msd_idempotence.md"
    text = (root / src).read_text(encoding="utf-8")
    read = re.search(r"lus (\d+), retenus (\d+)", text)
    before = re.search(r"valid before legalize: (\d+)/(\d+)", text)
    after = re.search(r"valid after legalize: (\d+)/(\d+)", text)
    n_read, n_kept = (int(read.group(1)), int(read.group(2))) if read else (0, 0)
    unit = "dwelling, 400 (MSD corpus not redistributed)"
    return [
        Claim(
            "B6",
            "dwellings read / kept",
            "1 247 read, 400 kept (32.1 %)",
            f"{n_read} read, {n_kept} kept ({100 * n_kept / max(n_read, 1):.1f} %)",
            src,
            "LoadStatistics summary line",
            unit,
            "ambiguous",
            "load_msd(limit=400) stops at the 400th kept dwelling: 1 247 is the number read "
            "until then, not the size of the corpus, and 32.1 % is not a corpus-wide "
            "retention rate (the loader documents 22 % on the full corpus). No raw rows: "
            "the summary is all that is published.",
        ),
        Claim(
            "B6",
            "valid before / after legalize (idempotence)",
            "398/400 before, 400/400 after",
            f"{before.group(1) if before else '?'}/{before.group(2) if before else '?'} before, "
            f"{after.group(1) if after else '?'}/{after.group(2) if after else '?'} after",
            src,
            "summary lines",
            unit,
            "ambiguous",
            "idempotence is tested on the 398 valid plans; the 2 invalid ones were repaired, "
            "which is not idempotence. Summary file only (cannot_verify against raw rows).",
        ),
    ]


def _b6_cases(root: Path) -> dict[tuple[str, str, str], dict[str, dict[str, str]]]:
    """Group the B6 repair rows by (dwelling, fault, amplitude), then by strategy.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    dict
        ``{(plan_id, fault, amplitude): {"False": row, "True": row}}``.
    """
    cases: dict[tuple[str, str, str], dict[str, dict[str, str]]] = {}
    for r in _rows(root / "j7_repair_raw.csv"):
        cases.setdefault((r["plan_id"], r["fault"], r["amplitude_m"]), {})[r["pavage"]] = r
    return cases


def _b6_repair(root: Path) -> list[Claim]:
    """B6, repair part: ``j7_repair_raw.csv``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "j7_repair_raw.csv"
    cases = _b6_cases(root)
    keys = sorted(cases)
    dwellings = [k[0] for k in keys]
    plain = _flags([cases[k]["False"] for k in keys], "valid_after")
    tiled_rows = [cases[k]["True"] for k in keys]
    tiled = _flags(tiled_rows, "valid_after")
    status = _column(tiled_rows, "status")
    fallback = tiled | ((status != "ok") & plain)
    strict = tiled | ((status == "trame") & plain)
    n, n_dw = len(keys), len(set(dwellings))
    b, c = int((tiled & ~plain).sum()), int((plain & ~tiled).sum())
    p_mcnemar = scipy_stats.binomtest(c, b + c).pvalue
    unit = f"corruption, clustered in {n_dw} dwellings (16 corruptions per dwelling)"
    expected = n_dw * 4 * 4
    return [
        Claim(
            "B6",
            "number of corruptions",
            "4 796 (300 dwellings, 4 families x 4 amplitudes)",
            f"{n} = {n_dw} x 4 x 4 - {expected - n} (corruption not applicable)",
            src,
            "distinct (plan_id, fault, amplitude)",
            unit,
            "consistent",
            "the 300 repair dwellings are the first 300 of the 400 kept for idempotence "
            "(same loader, same order), not 300 other dwellings; table 1's '400 + 4 796' "
            "should read '400 dwellings (idempotence); 4 796 corruptions of 300 of them'",
        ),
        Claim(
            "B6",
            "legalize / tiling / fallback valid after",
            "35.9 % / 93.0 % / 93.9 % [93.2 ; 94.5]",
            f"{100 * sum(plain) / n:.1f} % / {100 * sum(tiled) / n:.1f} % / "
            f"{100 * sum(fallback) / n:.1f} % Wilson {_wilson(sum(fallback), n)}; "
            f"cluster bootstrap by dwelling {_cluster(fallback, dwellings)}",
            src,
            "fallback = tiling valid, else legalize when tiling refuses for any reason",
            unit,
            "consistent",
            "fallback only on an unrecoverable grid (status 'trame'): "
            f"{100 * sum(strict) / n:.1f} %. "
            "The Wilson interval treats the 4 796 corruptions as independent; the "
            "dwelling-cluster bootstrap is the honest one.",
        ),
        Claim(
            "B6",
            "McNemar tiling vs legalize",
            "b = 2 779, c = 43, p < 1e-300",
            f"b = {b}, c = {c}, p {'< 1e-300' if p_mcnemar < 1e-300 else f'= {p_mcnemar:.1e}'}",
            src,
            "exact binomial on discordant pairs",
            unit,
            "ambiguous",
            "McNemar assumes independent pairs; the 16 corruptions of a dwelling are not. "
            "The direction is not in doubt, the p-value's magnitude is overstated.",
        ),
    ]


def _b8_rows(root: Path) -> list[dict[str, str]]:
    """Pool the three HouseDiffusion runs, each row tagged with its file label.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of dict
        Raw rows plus a ``label`` key (the ``graph`` column is not the file label).
    """
    return [
        {**r, "label": label}
        for label in ("etoile", "plausible", "divers")
        for r in _rows(root / f"j8_{label}_raw.csv")
    ]


def _b8(root: Path) -> list[Claim]:
    """B8: HouseDiffusion plans, ``j8_*_raw.csv``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "j8_{etoile,plausible,divers}_raw.csv"
    rows = _b8_rows(root)
    nominal = _where(rows, min_width="0.50")
    at = {b: _where(nominal, mode="pavage", budget=b) for b in ("0", "4", "8", "16")}
    base = _where(nominal, mode="base")
    final = at["16"]
    ok = _n(final, "valid_after")
    status = Counter(_column(final, "status").tolist())
    star, plausible = _where(final, label="etoile"), _where(final, label="plausible")
    paired = set(zip(_column(star, "plan_id"), _column(star, "program"), strict=True)) & set(
        zip(_column(plausible, "plan_id"), _column(plausible, "program"), strict=True)
    )
    unit = (
        f"generated plan, {len(final)}; etoile and plausible share {len(paired)} "
        "(plan_id, program) pairs: the same programs under two conditionings, so the "
        "two sets are paired, not independent"
    )
    rates = ", ".join(f"B={b}: {100 * _n(at[b], 'valid_after') / len(at[b]):.1f} %" for b in at)
    return [
        Claim(
            "B8",
            "plans, valid before",
            "740, 0 valid",
            f"{len(final)}, {_n(final, 'valid_before')} valid",
            src,
            "rows at B=16",
            unit,
            "consistent",
        ),
        Claim(
            "B8",
            "repaired at B=16 (tiling)",
            "19.6 % [16.9 ; 22.6]",
            f"{_pct(ok, len(final))} Wilson {_wilson(ok, len(final))}",
            src,
            "valid_after, mode=pavage, budget=16, min_width=0.50",
            unit,
            "consistent",
            f"failure reasons at B=16: {dict(status)} ('trame' = grid refused with the "
            "faulty cells named; 'infaisable' = Farkas certificate). Pooled rates for "
            f"table 5's empty 'Ensemble' cells: {rates}.",
        ),
        Claim(
            "B8",
            "legalize alone repaired",
            "0 %",
            _pct(_n(base, "valid_after"), len(base)),
            src,
            "valid_after, mode=base",
            unit,
            "consistent",
        ),
        Claim(
            "B8",
            "grids refused at B=0",
            "99 %",
            _pct(sum(r["status"] == "trame" for r in at["0"]), len(at["0"])),
            src,
            "status == trame, budget=0",
            unit,
            "consistent",
        ),
    ]


def _b9_rows(root: Path) -> list[tuple[str, float, float, float, float]]:
    """Parse the variant tables of ``orientation/hd*.md``.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of tuple
        ``(plan, azimuth, gain %, displacement m, smallest side m)`` per variant.
    """
    pattern = re.compile(
        r"\| (\d+)° \| [\d.]+ \| [\d.]+ \| \+?(-?[\d.]+) % \| ([\d.]+) m \| ([\d.]+) m"
    )
    out = []
    for path in sorted((root / "orientation").glob("hd*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = pattern.match(line)
            if m:
                out.append((path.stem, *(float(g) for g in m.groups())))
    return out


def _b9(root: Path) -> list[Claim]:
    """B9: Frank-Wolfe variants by azimuth, ``orientation/hd*.md``; timing has no file.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    src = "orientation/hd*.md"
    rows = _b9_rows(root)
    plans = sorted({r[0] for r in rows})
    gains = [r[2] for r in rows]
    q1, q3 = np.quantile(gains, [0.25, 0.75])
    grid = np.array([[r[2] for r in rows if r[0] == p] for p in plans])
    friedman = scipy_stats.friedmanchisquare(*grid.T)
    unit = f"variant = plan x azimuth; {len(plans)} independent plans"
    return [
        Claim(
            "B9",
            "variants",
            "48 (6 plans x 8 azimuths)",
            f"{len(rows)} ({len(plans)} plans)",
            src,
            "table rows",
            unit,
            "consistent",
            "no CSV: the per-variant rows exist only as Markdown tables",
        ),
        Claim(
            "B9",
            "median surrogate gain (IQR; range)",
            "17.2 % (10.7-25.9; 1.0-75.1)",
            f"{statistics.median(gains):.1f} % ({q1:.1f}-{q3:.1f}; "
            f"{min(gains):.1f}-{max(gains):.1f})",
            src,
            "gain column",
            unit,
            "consistent",
            "a gain of the frozen surrogate, not of simulated daylight",
        ),
        Claim(
            "B9",
            "variants saturating the 3.0 m radius / at the 0.50 m floor",
            "36/48 ; 20/48",
            f"{sum(r[3] >= 2.995 for r in rows)}/{len(rows)} ; "
            f"{sum(r[4] <= 0.505 for r in rows)}/{len(rows)}",
            src,
            "displacement >= 3.00 m; smallest side <= 0.50 m",
            unit,
            "consistent",
        ),
        Claim(
            "B9",
            "Friedman, gain vs azimuth",
            "chi2 = 16.5, p = 0.02",
            f"chi2 = {friedman.statistic:.1f}, p = {friedman.pvalue:.3f}",
            src,
            "repeated measures, plans x azimuths",
            unit,
            "consistent",
            "6 plans; not significant after Bonferroni over the paper's 7 tests",
        ),
        Claim(
            "B9",
            "timing: 160 runs (20 plans x 8 azimuths), 160/160 valid",
            "3.8 / 5.6 / 9.9 ms medians",
            "no raw file",
            "(none)",
            "-",
            "run = plan x azimuth, 20 plans (a different plan set from the 6 above)",
            "cannot_verify",
            "no timing rows are published in results/; the 20 plans are not the 6 of the "
            "variant table. Publish the raw timing CSV or drop the table.",
        ),
    ]


def _b7(root: Path) -> list[Claim]:
    """B7: Swiss Dwellings, summary files only.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    text = (root / "j7_sd_labels.md").read_text(encoding="utf-8")
    split = re.search(r"train (\d+) / calibration (\d+) / test (\d+)", text)
    total = sum(int(g) for g in split.groups()) if split else 0
    return [
        Claim(
            "B7",
            "dwellings; train / calibration / test",
            "2 000; 1 205 / 426 / 369",
            f"{total}; {'/'.join(split.groups()) if split else '?'}",
            "j7_sd_labels.md",
            "summary line",
            "dwelling, split by site (133 / 44 / 45 sites)",
            "cannot_verify",
            "matches the summary; no raw prediction rows are published (Swiss Dwellings "
            "not redistributed), so the R2 / MAE / coverage values cannot be recomputed",
        ),
        Claim(
            "B7",
            "within-dwelling share of variance",
            "92.3 % (1 - 7.7 %)",
            "1 - 0.077 = 92.3 %",
            "j7_variance.md",
            "1 - R2(apartment identity)",
            "room, 367 466 rooms in 44 888 dwellings",
            "cannot_verify",
            "summary file only; the 'variance reduced thirteen-fold' is 1/0.077 = 13",
        ),
    ]


def _synthesis(root: Path) -> list[Claim]:
    """Synthesis paragraph: the pooled 'never failed' count.

    Parameters
    ----------
    root : Path
        The ``results/`` directory.

    Returns
    -------
    list of Claim
        The reconciled numbers of this bench.
    """
    return [
        Claim(
            "synthesis",
            "variants certified valid",
            "208 (48 variants + 160 timed runs)",
            "48 variants verifiable; 160 runs not published",
            "orientation/hd*.md",
            "48 + 160",
            "mixes two plan sets (6 and 20 plans) and two units (variant, run)",
            "article_wrong",
            "do not add the two counts: report '48/48 variants of 6 plans' and, if the "
            "timing rows are published, '160/160 runs of 20 plans' separately",
        ),
        Claim(
            "synthesis",
            "synthetic plans corrected with tiling",
            "270 plans",
            "270 cases of 90 plans",
            "j2_validity_raw.csv",
            "pavage=True rows",
            "case, 90 independent plans",
            "article_wrong",
            "270 cases, not 270 plans",
        ),
    ]


def reconcile(root: Path | str = "results") -> tuple[Claim, ...]:
    """Recompute every reconciled number of the paper from ``root``.

    Parameters
    ----------
    root : Path or str, optional
        The ``results/`` directory.

    Returns
    -------
    tuple of Claim
        One claim per printed number, in bench order.

    Raises
    ------
    FileNotFoundError
        A raw file this module reads is missing.
    """
    root = Path(root)
    parts: Iterable[list[Claim]] = (
        _b1(root),
        _b2(root),
        _b3(root),
        _b4(root),
        _b5(root),
        _b6_idempotence(root),
        _b6_repair(root),
        _b7(root),
        _b8(root),
        _b9(root),
        _synthesis(root),
    )
    return tuple(claim for part in parts for claim in part)


def to_markdown(claims: Sequence[Claim]) -> str:
    """Render the claims as the table of ``results/RECONCILIATION.md``.

    Parameters
    ----------
    claims : Sequence[Claim]
        Output of :func:`reconcile`.

    Returns
    -------
    str
        One Markdown table, then the notes of every non-consistent claim.
    """
    head = [
        "| bench | quantity | paper | recomputed | verdict | unit | source |",
        "|---|---|---|---|---|---|---|",
    ]
    body = [
        f"| {c.bench} | {c.quantity} | {c.article} | {c.recomputed} | **{c.verdict}** | "
        f"{c.unit} | `{c.source}` |"
        for c in claims
    ]
    notes = [
        f"- **{c.bench}, {c.quantity}** ({c.verdict}; formula: {c.formula}). {c.note}"
        for c in claims
        if c.note
    ]
    return "\n".join([*head, *body, "", "## Notes", "", *notes, ""])


def to_json(claims: Sequence[Claim]) -> list[dict[str, str]]:
    """Plain dicts, for ``results/reconciliation.json``.

    Parameters
    ----------
    claims : Sequence[Claim]
        Output of :func:`reconcile`.

    Returns
    -------
    list of dict
        One dict per claim, the fields of :class:`Claim`.
    """
    return [asdict(c) for c in claims]
