"""JSON round trip of plans. Versioned schema, deterministic serialization.

The schema carries a version number: a plan written by ``0.1.x`` must stay readable by
``0.2.x``. The keys are sorted at write time, otherwise two identical runs produce two
different fingerprints and the announced reproducibility is not held.

The conversion is written **by hand**, field by field, rather than derived by
introspection of the ``dataclass`` types. It is longer and that is deliberate: adding a
field to the model must force a decision about what it becomes in the published format,
instead of silently appearing in files that other tools already read.

The JSON keys are those of schema v1 (French names such as ``"porteur"`` or ``"jours"``):
the Python names of the model are English, and this module is the mapping between the two.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import InvariantViolation
from archlux.types import (
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
    "SCHEMA_VERSION",
    "from_dict",
    "load",
    "manifest_to_dict",
    "to_dict",
    "write",
]

SCHEMA_VERSION = "1"
"""Version of the JSON schema. Incremented on any non backward compatible change."""


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
    for room in data["pieces"]:
        for field in ("w", "h"):
            value = _real(room[field], f"room {room['id']}.{field}")
            if value <= 0.0:
                violations.append(f"room {room['id']}: {field} = {value}; expected > 0")
    for wall in data["murs"]:
        thickness = _real(wall["epaisseur"], f"mur {wall['id']}.epaisseur")
        if thickness <= 0.0:
            violations.append(f"mur {wall['id']} : epaisseur = {thickness} ; attendu > 0")
    for opening in data["ouvertures"]:
        s = _real(opening["s"], f"ouverture {opening['id']}.s")
        width = _real(opening["largeur_rel"], f"ouverture {opening['id']}.largeur_rel")
        if not 0.0 <= s <= 1.0:
            violations.append(f"opening {opening['id']}: s = {s}; expected in [0, 1]")
        if not 0.0 < width <= 1.0:
            violations.append(f"opening {opening['id']}: largeur_rel = {width}; expected in ]0, 1]")
    if violations:
        raise InvariantViolation(tuple(violations))


# ======================================================================================
# Certificat
# ======================================================================================


def _proof_to_dict(proof: GeometricProof) -> dict[str, Any]:
    """Serialize a geometric proof; no probability field enters it."""
    return {
        "valide": proof.valid,
        "chevauchement": proof.overlap,
        "jours": proof.gaps,
        "surfaces_ok": proof.areas_ok,
        "structure_preservee": proof.structure_kept,
        "deplacement_max": proof.max_displacement,
        "violations": list(proof.violations),
    }


def _proof_from_dict(data: Any) -> GeometricProof:
    """Rebuild a geometric proof from its JSON form."""
    return GeometricProof(
        valid=bool(data["valide"]),
        overlap=bool(data["chevauchement"]),
        gaps=bool(data["jours"]),
        areas_ok=bool(data["surfaces_ok"]),
        structure_kept=bool(data["structure_preservee"]),
        max_displacement=_real(data["deplacement_max"], "preuve.deplacement_max"),
        violations=tuple(str(v) for v in data["violations"]),
    )


def _bound_to_dict(bound: PerformanceBound) -> dict[str, Any]:
    """Serialize a performance bound, coverage and n_calibration included."""
    return {
        "indicateur": bound.indicator,
        "valeur": bound.value,
        "borne_inf": bound.lower,
        "borne_sup": bound.upper,
        "couverture": bound.coverage,
        "n_calibration": bound.n_calibration,
        "regime": bound.regime,
    }


def _regime(data: Any) -> Regime:
    """The regime of a serialized bound; missing or unknown is refused."""
    regime = data.get("regime") if isinstance(data, dict) else None
    if regime not in REGIMES:
        raise InvariantViolation((f"borne.regime: expected one of {REGIMES}, got {regime!r}",))
    return regime  # type: ignore[no-any-return]


def _bound_from_dict(data: Any) -> PerformanceBound:
    """Rebuild a performance bound; refuse an unknown indicator."""
    indicator = data["indicateur"]
    if indicator not in ("sDA", "ASE", "UDI", "vue"):
        raise InvariantViolation((f"unknown indicator: {indicator!r}",))
    return PerformanceBound(
        indicator=indicator,
        value=_real(data["valeur"], "borne.valeur"),
        lower=_real(data["borne_inf"], "borne.borne_inf"),
        upper=_real(data["borne_sup"], "borne.borne_sup"),
        coverage=_real(data["couverture"], "borne.couverture"),
        n_calibration=int(data["n_calibration"]),
        # Files written before batch 1.6 carry no regime. They could only come from a
        # hand-built bound (legalize never filled one), so none is assumed: reading
        # such a bound as "exchangeable" would upgrade an unknown guarantee.
        regime=_regime(data),
    )


def manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    """Serialize a :class:`~archlux.types.Manifest` (single JSON / benchmark form)."""
    modele = manifest.model
    return {
        "version": manifest.version,
        "horodatage": manifest.timestamp,
        "graine": manifest.seed,
        "empreinte_donnees": manifest.data_fingerprint,
        "decoupage": manifest.split,
        "environnement": [list(p) for p in manifest.environment],
        "parametres": [list(p) for p in manifest.parameters],
        "modele": None
        if modele is None
        else {
            "poids": modele.weights_fingerprint,
            "calibration_n": modele.calibration_n,
            "alpha": modele.alpha,
        },
    }


def _manifest_from_dict(data: Any) -> Manifest:
    """Rebuild a manifest, ``ModelTrace`` included if present."""
    brut = data.get("modele")
    modele = None
    if brut is not None:
        modele = ModelTrace(
            weights_fingerprint=str(brut["poids"]),
            calibration_n=int(brut["calibration_n"]),
            alpha=float(brut["alpha"]),
        )
    return Manifest(
        version=str(data["version"]),
        timestamp=str(data["horodatage"]),
        seed=int(data["graine"]),
        data_fingerprint=data["empreinte_donnees"],
        split=data["decoupage"],
        environment=_pairs(data["environnement"]),
        parameters=_pairs(data["parametres"]),
        model=modele,
    )


def _certificate_to_dict(certificate: Certificate | None) -> dict[str, Any] | None:
    """Serialize a certificate; ``None`` for performance stays explicit."""
    if certificate is None:
        return None
    performance = certificate.performance
    manifest = certificate.manifest
    return {
        "geometrie": _proof_to_dict(certificate.geometry),
        # An explicit `None` rather than an absent key: "no performance guarantee" is
        # information, not a serialization oversight.
        "performance": None if performance is None else _bound_to_dict(performance),
        "duaux": [[libelle, cout] for libelle, cout in certificate.duals],
        "manifeste": None if manifest is None else manifest_to_dict(manifest),
    }


def _certificate_from_dict(data: Any) -> Certificate | None:
    """Rebuild a certificate, or ``None`` if the plan carries none."""
    if data is None:
        return None
    performance = data["performance"]
    manifest = data["manifeste"]
    return Certificate(
        geometry=_proof_from_dict(data["geometrie"]),
        performance=None if performance is None else _bound_from_dict(performance),
        duals=tuple(
            (str(libelle), _real(cout, f"dual {libelle}")) for libelle, cout in data["duaux"]
        ),
        manifest=None if manifest is None else _manifest_from_dict(manifest),
    )


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
        "contour": [[x, y] for x, y in plan.outline],
        "pieces": [
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
        "murs": [
            {
                "id": m.id,
                "a": [m.a[0], m.a[1]],
                "b": [m.b[0], m.b[1]],
                "porteur": m.load_bearing,
                "epaisseur": m.thickness,
            }
            for m in plan.walls
        ],
        "ouvertures": [
            {
                "id": o.id,
                "mur_id": o.wall_id,
                "s": o.s,
                "largeur_rel": o.relative_width,
                "hauteur_allege": o.sill_height,
                "hauteur_linteau": o.head_height,
            }
            for o in plan.openings
        ],
        "certificat": _certificate_to_dict(plan.certificate),
    }


def from_dict(data: dict[str, Any]) -> Plan:
    """Rebuild a plan from a JSON-compatible structure.

    Parameters
    ----------
    donnees : dict
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
    if version != SCHEMA_VERSION:
        raise InvariantViolation((f"unknown JSON schema {version!r}, expected {SCHEMA_VERSION!r}",))
    try:
        # Before building: ``Opening`` refuses an out-of-range ``s`` itself, which would
        # hide every other violation of the file behind the first one.
        _check_ranges(data)
        plan = Plan(
            rooms=tuple(
                Room(
                    id=str(p["id"]),
                    type=str(p["type"]),
                    x=_real(p["x"], f"piece {p['id']}.x"),
                    y=_real(p["y"], f"piece {p['id']}.y"),
                    w=_real(p["w"], f"piece {p['id']}.w"),
                    h=_real(p["h"], f"piece {p['id']}.h"),
                )
                for p in data["pieces"]
            ),
            walls=tuple(
                Wall(
                    id=str(m["id"]),
                    a=_point(m["a"], f"mur {m['id']}.a"),
                    b=_point(m["b"], f"mur {m['id']}.b"),
                    load_bearing=bool(m["porteur"]),
                    thickness=_real(m["epaisseur"], f"mur {m['id']}.epaisseur"),
                )
                for m in data["murs"]
            ),
            openings=tuple(
                Opening(
                    id=str(o["id"]),
                    wall_id=str(o["mur_id"]),
                    s=_real(o["s"], f"ouverture {o['id']}.s"),
                    relative_width=_real(o["largeur_rel"], f"ouverture {o['id']}.largeur_rel"),
                    sill_height=_real(o["hauteur_allege"], f"ouverture {o['id']}.hauteur_allege"),
                    head_height=_real(o["hauteur_linteau"], f"ouverture {o['id']}.hauteur_linteau"),
                )
                for o in data["ouvertures"]
            ),
            outline=tuple(_point(pt, f"contour[{i}]") for i, pt in enumerate(data["contour"])),
            certificate=_certificate_from_dict(data["certificat"]),
        )
    except (KeyError, TypeError, ValueError) as cause:
        raise InvariantViolation((f"invalid JSON structure: {cause}",)) from cause
    return plan


def load(path: Path | str) -> Plan:
    """Read a plan from a JSON file.

    Parameters
    ----------
    chemin : Path or str
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
        texte = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError as cause:
        raise InvariantViolation((f"{path} is not UTF-8 encoded: {cause}",)) from cause
    try:
        data = json.loads(texte)
    except json.JSONDecodeError as cause:
        raise InvariantViolation((f"{path} is not valid JSON: {cause}",)) from cause
    if not isinstance(data, dict):
        raise InvariantViolation((f"{path} does not contain a JSON object",))
    return from_dict(data)


def write(plan: Plan, path: Path | str) -> None:
    r"""Write a plan as JSON, sorted keys, UTF-8 encoding, ``\n`` line ending.

    The sorted keys and the fixed line ending are not cosmetic: without them, two writes
    of the same plan give different bytes, and the fingerprint recorded in a manifest
    stops identifying anything.

    Parameters
    ----------
    plan : Plan
        Plan to write.
    chemin : Path or str
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
        texte = json.dumps(
            to_dict(plan),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    except ValueError as cause:
        raise InvariantViolation((f"non-finite value in the plan: {cause}",)) from cause
    Path(path).write_text(texte + "\n", encoding="utf-8", newline="\n")


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
