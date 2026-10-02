"""JSON round trip of plans. Versioned schema, deterministic serialization.

The schema carries a version number: a plan written by ``0.1.x`` must stay readable by
``0.2.x``. The keys are sorted at write time, otherwise two identical runs produce two
different fingerprints and the announced reproducibility is not held.

The conversion is written **by hand**, field by field, rather than derived by
introspection of the ``dataclass`` types. It is longer and that is deliberate: adding a
field to the model must force a decision about what it becomes in the published format,
instead of silently appearing in files that other tools already read.

The JSON keys are those of schema v1 (French names such as ``"load_bearing"`` or ``"gaps"``):
the Python names of the model are English, and this module is the mapping between the two.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvariantViolation
from archlux.types import (
    INDICATOR_SENSE,
    REGIMES,
    Certificate,
    GeometricProof,
    Manifest,
    ModelTrace,
    Opening,
    PerformanceBound,
    Plan,
    Point,
    Regime,
    Room,
    Wall,
)

__all__ = [
    "SCHEMA_VERSION",
    "from_dict",
    "load",
    "manifest_to_dict",
    "to_dict",
    "upgrade_v1",
    "write",
]

SCHEMA_VERSION = "2"
"""Version of the JSON schema. Incremented on any non backward compatible change."""


_TYPES_FROM_V1 = {
    "sejour": "living_room",
    "chambre": "bedroom",
    "cuisine": "kitchen",
    "sdb": "bathroom",
    "wc": "toilet",
    "couloir": "corridor",
}
"""The French room types of schema v1 files, and the English types of the model."""


# ======================================================================================
# Elementary conversions
# ======================================================================================


def _real(value: Any, where: str) -> float:
    """Read a **finite** float.

    ``json.loads`` accepts the literals ``NaN`` and ``Infinity``. Without this guard, a
    file produced by another tool would bring non-finite values into the solver, where
    they propagate silently up to an absurd certificate. ``write`` already refuses to
    write them, so reading must refuse to read them.
    """
    real = float(value)
    if not math.isfinite(real):
        raise InvariantViolation((f"{where}: non-finite value ({value!r})",))
    return real


def _point(value: Any, where: str = "point") -> Point:
    """Read a point ``[x, y]``, refusing anything that is not one."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise InvariantViolation((f"expected a point as [x, y], got {value!r}",))
    return (_real(value[0], f"{where}.x"), _real(value[1], f"{where}.y"))


def _pairs(value: Any) -> tuple[tuple[str, str], ...]:
    """Normalize a JSON list of pairs into a tuple of string pairs."""
    return tuple((str(cle), str(val)) for cle, val in value)


def _check_ranges(data: Any) -> None:
    """Check the ranges documented by `ARCHITECTURE.md` §6.

    **The validation happens here and not in the constructors** (ADR-6, amended for
    ``Opening`` and ``GeometricProof``). The JSON boundary is where data comes from the
    outside, so that is where to refuse it. Validating in ``__post_init__`` for every type
    would forbid the solver to cross an out-of-range intermediate state, and would make
    every construction pay a check in a Frank-Wolfe loop that builds thousands of them.

    All the violations are reported together: fixing a file one error at a time is a
    torment, and nothing requires returning only the first.

    Raises
    ------
    InvariantViolation
        At least one value is out of its range. ``violations`` lists them all.

    Complexity
    ----------
    O(n) in the number of elements of the plan.
    """
    violations: list[str] = []
    for room in data["rooms"]:
        for field in ("w", "h"):
            value = _real(room[field], f"room {room['id']}.{field}")
            if value <= 0.0:
                violations.append(f"room {room['id']}: {field} = {value}; expected > 0")
    for wall in data["walls"]:
        thickness = _real(wall["thickness"], f"wall {wall['id']}.thickness")
        if thickness <= 0.0:
            violations.append(f"wall {wall['id']}: thickness = {thickness}; expected > 0")
    for opening in data["openings"]:
        s = _real(opening["s"], f"opening {opening['id']}.s")
        width = _real(opening["relative_width"], f"opening {opening['id']}.relative_width")
        if not 0.0 <= s <= 1.0:
            violations.append(f"opening {opening['id']}: s = {s}; expected in [0, 1]")
        if not 0.0 < width <= 1.0:
            violations.append(
                f"opening {opening['id']}: relative_width = {width}; expected in ]0, 1]"
            )
    if violations:
        raise InvariantViolation(tuple(violations))


# ======================================================================================
# Certificat
# ======================================================================================


def _proof_to_dict(proof: GeometricProof) -> dict[str, Any]:
    """Serialize a geometric proof; no probability field enters it."""
    return {
        "valid": proof.valid,
        "overlap": proof.overlap,
        "gaps": proof.gaps,
        "areas_ok": proof.areas_ok,
        "structure_kept": proof.structure_kept,
        "max_displacement": proof.max_displacement,
        "violations": list(proof.violations),
    }


def _proof_from_dict(data: Any) -> GeometricProof:
    """Rebuild a geometric proof from its JSON form."""
    return GeometricProof(
        valid=bool(data["valid"]),
        overlap=bool(data["overlap"]),
        gaps=bool(data["gaps"]),
        areas_ok=bool(data["areas_ok"]),
        structure_kept=bool(data["structure_kept"]),
        max_displacement=_real(data["max_displacement"], "preuve.deplacement_max"),
        violations=tuple(str(v) for v in data["violations"]),
    )


def _bound_to_dict(bound: PerformanceBound) -> dict[str, Any]:
    """Serialize a performance bound, coverage and n_calibration included."""
    return {
        "indicator": bound.indicator,
        "value": bound.value,
        "lower": bound.lower,
        "upper": bound.upper,
        "coverage": bound.coverage,
        "n_calibration": bound.n_calibration,
        "regime": bound.regime,
    }


def _regime(data: Any) -> Regime:
    """The regime of a serialized bound; missing or unknown is refused."""
    regime = data.get("regime") if isinstance(data, dict) else None
    if regime not in REGIMES:
        raise InvariantViolation((f"bound.regime: expected one of {REGIMES}, got {regime!r}",))
    return regime  # type: ignore[no-any-return]


def _bound_from_dict(data: Any) -> PerformanceBound:
    """Rebuild a performance bound; refuse an unknown indicator."""
    indicator = data["indicator"]
    if indicator not in INDICATOR_SENSE:
        raise InvariantViolation((f"unknown indicator: {indicator!r}",))
    return PerformanceBound(
        indicator=indicator,
        value=_real(data["value"], "bound.valeur"),
        lower=_real(data["lower"], "bound.borne_inf"),
        upper=_real(data["upper"], "bound.borne_sup"),
        coverage=_real(data["coverage"], "bound.couverture"),
        n_calibration=int(data["n_calibration"]),
        # Files written before batch 1.6 carry no regime. They could only come from a
        # hand-built bound (legalize never filled one), so none is assumed: reading
        # such a bound as "exchangeable" would upgrade an unknown guarantee.
        regime=_regime(data),
    )


@renamed_parameters({"manifeste": "manifest"})
def manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    """Serialize a :class:`~archlux.types.Manifest` (single JSON / benchmark form)."""
    model = manifest.model
    return {
        "version": manifest.version,
        "timestamp": manifest.timestamp,
        "seed": manifest.seed,
        "data_fingerprint": manifest.data_fingerprint,
        "split": manifest.split,
        "environment": [list(p) for p in manifest.environment],
        "parameters": [list(p) for p in manifest.parameters],
        "model": None
        if model is None
        else {
            "weights_fingerprint": model.weights_fingerprint,
            "calibration_n": model.calibration_n,
            "alpha": model.alpha,
        },
    }


def _manifest_from_dict(data: Any) -> Manifest:
    """Rebuild a manifest, ``ModelTrace`` included if present."""
    raw = data.get("model")
    model = None
    if raw is not None:
        model = ModelTrace(
            weights_fingerprint=str(raw["weights_fingerprint"]),
            calibration_n=int(raw["calibration_n"]),
            alpha=float(raw["alpha"]),
        )
    return Manifest(
        version=str(data["version"]),
        timestamp=str(data["timestamp"]),
        seed=int(data["seed"]),
        data_fingerprint=data["data_fingerprint"],
        split=data["split"],
        environment=_pairs(data["environment"]),
        parameters=_pairs(data["parameters"]),
        model=model,
    )


def _certificate_to_dict(certificate: Certificate | None) -> dict[str, Any] | None:
    """Serialize a certificate; ``None`` for performance stays explicit."""
    if certificate is None:
        return None
    performance = certificate.performance
    manifest = certificate.manifest
    return {
        "geometry": _proof_to_dict(certificate.geometry),
        # An explicit `None` rather than an absent key: "no performance guarantee" is
        # information, not a serialization oversight.
        "performance": None if performance is None else _bound_to_dict(performance),
        "duals": [[label, cost] for label, cost in certificate.duals],
        "manifest": None if manifest is None else manifest_to_dict(manifest),
    }


def _certificate_from_dict(data: Any) -> Certificate | None:
    """Rebuild a certificate, or ``None`` if the plan carries none."""
    if data is None:
        return None
    performance = data["performance"]
    manifest = data["manifest"]
    return Certificate(
        geometry=_proof_from_dict(data["geometry"]),
        performance=None if performance is None else _bound_from_dict(performance),
        duals=tuple((str(label), _real(cost, f"dual {label}")) for label, cost in data["duals"]),
        manifest=None if manifest is None else _manifest_from_dict(manifest),
    )


# ======================================================================================
# Schema v1 to v2
# ======================================================================================

_V1_KEYS: dict[str, dict[str, str]] = {
    "plan": {
        "contour": "outline",
        "pieces": "rooms",
        "murs": "walls",
        "ouvertures": "openings",
        "certificat": "certificate",
    },
    "wall": {"porteur": "load_bearing", "epaisseur": "thickness"},
    "opening": {
        "mur_id": "wall_id",
        "largeur_rel": "relative_width",
        "hauteur_allege": "sill_height",
        "hauteur_linteau": "head_height",
    },
    "certificate": {"geometrie": "geometry", "duaux": "duals", "manifeste": "manifest"},
    "geometry": {
        "valide": "valid",
        "chevauchement": "overlap",
        "jours": "gaps",
        "surfaces_ok": "areas_ok",
        "structure_preservee": "structure_kept",
        "deplacement_max": "max_displacement",
    },
    "performance": {
        "indicateur": "indicator",
        "valeur": "value",
        "borne_inf": "lower",
        "borne_sup": "upper",
        "couverture": "coverage",
    },
    "manifest": {
        "horodatage": "timestamp",
        "graine": "seed",
        "empreinte_donnees": "data_fingerprint",
        "decoupage": "split",
        "environnement": "environment",
        "parametres": "parameters",
        "modele": "model",
    },
    "model": {"poids": "weights_fingerprint"},
}
"""The French keys of a schema v1 file, section by section, and their v2 names."""


def _rename_keys(section: Any, kind: str) -> Any:
    """A copy of ``section`` with the v1 keys of ``kind`` renamed; anything else is kept."""
    if not isinstance(section, dict):
        return section
    mapping = _V1_KEYS[kind]
    return {mapping.get(key, key): value for key, value in section.items()}


def _room_from_v1(room: Any) -> Any:
    """A v1 room with its French type mapped; a malformed room is returned unchanged."""
    if not isinstance(room, dict) or not isinstance(room.get("type"), str):
        return room
    return {**room, "type": _TYPES_FROM_V1.get(room["type"], room["type"])}


def upgrade_v1(data: dict[str, Any]) -> dict[str, Any]:
    """Convert a schema v1 document into the equivalent schema v2 document.

    Renames the French keys to their English names, maps the six French room types to the
    English ones (any other type passes through) and sets ``"schema"`` to ``"2"``. A
    malformed document is converted as far as it goes: the v2 reader then reports what is
    wrong with it. The input is not modified.

    Parameters
    ----------
    data : dict
        A decoded schema v1 document.

    Returns
    -------
    dict
        The same plan as a schema v2 document.
    """
    plan: dict[str, Any] = _rename_keys(data, "plan")
    plan["schema"] = SCHEMA_VERSION
    # Only well-formed parts are converted; anything else passes through unchanged, so
    # that the v2 reader refuses it with a typed error, never a bare TypeError.
    rooms = plan.get("rooms", [])
    if isinstance(rooms, list):
        plan["rooms"] = [_room_from_v1(room) for room in rooms]
    for key, kind in (("walls", "wall"), ("openings", "opening")):
        items = plan.get(key, [])
        if isinstance(items, list):
            plan[key] = [_rename_keys(item, kind) for item in items]
    certificate = _rename_keys(plan.get("certificate"), "certificate")
    if isinstance(certificate, dict):
        certificate["geometry"] = _rename_keys(certificate.get("geometry"), "geometry")
        certificate["performance"] = _rename_keys(certificate.get("performance"), "performance")
        manifest = _rename_keys(certificate.get("manifest"), "manifest")
        if isinstance(manifest, dict):
            manifest["model"] = _rename_keys(manifest.get("model"), "model")
        certificate["manifest"] = manifest
    plan["certificate"] = certificate
    return plan


# ======================================================================================
# Plan
# ======================================================================================


def to_dict(plan: Plan) -> dict[str, Any]:
    """Project a plan onto a JSON-compatible structure, in a stable order.

    Parameters
    ----------
    plan : Plan
        Plan to encode, proposed or legalized.

    Returns
    -------
    dict
        A structure carrying ``schema``, the geometry and the certificate if any.

    Guarantees
    ----------
    - None: this function only transcribes. The guarantees of a plan are carried by its
      ``certificate``, transcribed as is.

    Complexity
    ----------
    O(n) in the number of elements of the plan.
    """
    return {
        "schema": SCHEMA_VERSION,
        "outline": [[x, y] for x, y in plan.outline],
        "rooms": [
            {
                "id": p.id,
                "type": p.type,
                "x": p.x,
                "y": p.y,
                "w": p.w,
                "h": p.h,
            }
            for p in plan.rooms
        ],
        "walls": [
            {
                "id": m.id,
                "a": [m.a[0], m.a[1]],
                "b": [m.b[0], m.b[1]],
                "load_bearing": m.load_bearing,
                "thickness": m.thickness,
            }
            for m in plan.walls
        ],
        "openings": [
            {
                "id": o.id,
                "wall_id": o.wall_id,
                "s": o.s,
                "relative_width": o.relative_width,
                "sill_height": o.sill_height,
                "head_height": o.head_height,
            }
            for o in plan.openings
        ],
        "certificate": _certificate_to_dict(plan.certificate),
    }


@renamed_parameters({"donnees": "data"})
def from_dict(data: dict[str, Any]) -> Plan:
    """Rebuild a plan from a JSON-compatible structure.

    Parameters
    ----------
    data : dict
        Structure as returned by :func:`to_dict`.

    Returns
    -------
    Plan
        The rebuilt plan, certificate included if present.

    Raises
    ------
    InvariantViolation
        Missing or unknown schema version, or malformed field. The format is refused
        loudly rather than guessed: a misread plan would produce a false certificate.

    Complexity
    ----------
    O(n) in the number of elements of the plan.
    """
    version = data.get("schema")
    if version == "1":
        data = upgrade_v1(data)
    elif version != SCHEMA_VERSION:
        raise InvariantViolation(
            (f"unknown JSON schema {version!r}, expected {SCHEMA_VERSION!r} or '1'",)
        )
    try:
        # Before building: ``Opening`` refuses an out-of-range ``s`` itself, which would
        # hide every other violation of the file behind the first one.
        _check_ranges(data)
        plan = Plan(
            rooms=tuple(
                Room(
                    id=str(p["id"]),
                    type=str(p["type"]),
                    x=_real(p["x"], f"room {p['id']}.x"),
                    y=_real(p["y"], f"room {p['id']}.y"),
                    w=_real(p["w"], f"room {p['id']}.w"),
                    h=_real(p["h"], f"room {p['id']}.h"),
                )
                for p in data["rooms"]
            ),
            walls=tuple(
                Wall(
                    id=str(m["id"]),
                    a=_point(m["a"], f"wall {m['id']}.a"),
                    b=_point(m["b"], f"wall {m['id']}.b"),
                    load_bearing=bool(m["load_bearing"]),
                    thickness=_real(m["thickness"], f"wall {m['id']}.thickness"),
                )
                for m in data["walls"]
            ),
            openings=tuple(
                Opening(
                    id=str(o["id"]),
                    wall_id=str(o["wall_id"]),
                    s=_real(o["s"], f"opening {o['id']}.s"),
                    relative_width=_real(o["relative_width"], f"opening {o['id']}.relative_width"),
                    sill_height=_real(o["sill_height"], f"opening {o['id']}.sill_height"),
                    head_height=_real(o["head_height"], f"opening {o['id']}.head_height"),
                )
                for o in data["openings"]
            ),
            outline=tuple(_point(pt, f"outline[{i}]") for i, pt in enumerate(data["outline"])),
            certificate=_certificate_from_dict(data["certificate"]),
        )
    except (KeyError, TypeError, ValueError) as cause:
        raise InvariantViolation((f"invalid JSON structure: {cause}",)) from cause
    return plan


@renamed_parameters({"chemin": "path"})
def load(path: Path | str) -> Plan:
    """Read a plan from a JSON file.

    Parameters
    ----------
    path : Path or str
        Source file, UTF-8 encoded.

    Returns
    -------
    Plan
        The rebuilt plan, certificate included if present.

    Raises
    ------
    InvariantViolation
        The file is not UTF-8, is not JSON, or does not respect the declared schema. A
        file written in ISO-8859-1 by another tool used to surface as a bare
        ``UnicodeDecodeError``, outside the error domain of the project
        (`ARCHITECTURE.md` §7).
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as cause:
        raise InvariantViolation((f"{path} is not UTF-8 encoded: {cause}",)) from cause
    try:
        data = json.loads(text)
    except json.JSONDecodeError as cause:
        raise InvariantViolation((f"{path} is not valid JSON: {cause}",)) from cause
    if not isinstance(data, dict):
        raise InvariantViolation((f"{path} does not contain a JSON object",))
    return from_dict(data)


@renamed_parameters({"chemin": "path"})
def write(plan: Plan, path: Path | str) -> None:
    r"""Write a plan as JSON, sorted keys, UTF-8 encoding, ``\n`` line ending.

    The sorted keys and the fixed line ending are not cosmetic: without them, two writes
    of the same plan give different bytes, and the fingerprint recorded in a manifest
    stops identifying anything.

    Parameters
    ----------
    plan : Plan
        Plan to write.
    path : Path or str
        Destination file; its parent directory must exist.

    Raises
    ------
    InvariantViolation
        The plan contains a non-finite value (``NaN`` or infinity). This is typically what
        a buggy solver produces; ``allow_nan=False`` refuses to write it, and the error is
        retyped to stay in the error domain of the project (`ARCHITECTURE.md` §7) rather
        than surface as a ``ValueError`` of the standard library.
    """
    try:
        text = json.dumps(
            to_dict(plan),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    except ValueError as cause:
        raise InvariantViolation((f"non-finite value in the plan: {cause}",)) from cause
    Path(path).write_text(text + "\n", encoding="utf-8", newline="\n")


__getattr__ = lazy_aliases(
    __name__,
    {
        "VERSION_SCHEMA": Alias(SCHEMA_VERSION, "archlux.io.json_io.SCHEMA_VERSION"),
        "charger": Alias(load, "archlux.io.json_io.load"),
        "ecrire": Alias(write, "archlux.io.json_io.write"),
        "vers_dict": Alias(to_dict, "archlux.io.json_io.to_dict"),
        "depuis_dict": Alias(from_dict, "archlux.io.json_io.from_dict"),
        "manifeste_vers_dict": Alias(manifest_to_dict, "archlux.io.json_io.manifest_to_dict"),
    },
)
