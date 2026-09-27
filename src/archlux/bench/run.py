"""Bench orchestration: manifest -> raw rows -> result (no aggregation)."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from archlux._deprecation import Alias, lazy_aliases
from archlux.bench.manifeste import emit
from archlux.errors import InvariantViolation
from archlux.io.json_io import manifest_to_dict
from archlux.light.protocole import Surrogate
from archlux.types import Manifest, ModelTrace, Orientation, Plan

__all__ = ["Manifest", "RawRow", "Result", "run"]


@dataclass(frozen=True, slots=True)
class RawRow:
    """A measurement before any aggregation."""

    plan_id: str
    method: str
    orientation_deg: float
    score: float


@dataclass(frozen=True, slots=True)
class Result:
    """Output of :func:`run`: manifest + paths + raw rows."""

    manifest: Manifest
    raw_path: Path
    manifest_path: Path
    rows: tuple[RawRow, ...]


def run(
    *,
    plans: Sequence[Plan],
    orientations: Sequence[Orientation],
    methods: Sequence[Surrogate],
    evaluate_by: Callable[[Plan, Surrogate], float],
    seed: int,
    data_fingerprint: str,
    split: str,
    model: ModelTrace,
    directory: Path | str,
    parameters: Mapping[str, str] | None = None,
) -> Result:
    """Run the bench: write the manifest, then the raw rows, then return.

    The order is binding (`MILESTONE-6.md` §5): no aggregate before the raw rows.
    """
    if len(plans) != len(orientations):
        raise InvariantViolation(("plans and orientations must have the same length",))
    if not methods:
        raise InvariantViolation(("at least one method is required",))

    dossier = Path(directory)
    dossier.mkdir(parents=True, exist_ok=True)

    manifest = emit(
        seed=seed,
        data_fingerprint=data_fingerprint,
        split=split,
        parameters=dict(parameters) if parameters else None,
        model=model,
    )
    manifest_path = dossier / "manifest.json"
    _ecrire_manifeste(manifest_path, manifest)

    rows: list[RawRow] = []
    for plan, orientation in zip(plans, orientations, strict=True):
        # ``room_ids`` is sorted: the bench identifier does not depend on the
        # insertion order of the ``rooms`` tuple.
        plan_id = "-".join(plan.room_ids) if plan.room_ids else "vide"
        for method in methods:
            name = type(method).__name__
            score = float(evaluate_by(plan, method))
            rows.append(
                RawRow(
                    plan_id=plan_id,
                    method=name,
                    orientation_deg=float(orientation.deg),
                    score=score,
                )
            )

    raw_path = dossier / "resultats_bruts.csv"
    _ecrire_bruts(raw_path, rows)

    return Result(
        manifest=manifest,
        raw_path=raw_path,
        manifest_path=manifest_path,
        rows=tuple(rows),
    )


def _ecrire_manifeste(path: Path, manifest: Manifest) -> None:
    # Same shape as the certificates' JSON schema (`io.json_io`) — a single truth.
    """Write the manifest as JSON, sorted keys, before any result."""
    payload = manifest_to_dict(manifest)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ecrire_bruts(path: Path, rows: Sequence[RawRow]) -> None:
    """Write the raw measurements as CSV, before any aggregation."""
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["plan_id", "methode", "orientation_deg", "score"])
        for ligne in rows:
            w.writerow(
                [ligne.plan_id, ligne.method, f"{ligne.orientation_deg:.6f}", f"{ligne.score:.8f}"]
            )


__getattr__ = lazy_aliases(
    __name__,
    {
        "LigneBrute": Alias(RawRow, "archlux.bench.run.RawRow"),
        "Resultat": Alias(Result, "archlux.bench.run.Result"),
    },
)
