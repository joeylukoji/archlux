"""Fixed 60 / 20 / 20 split. Deduplicate **before**, otherwise near-duplicates leak across."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from archlux._deprecation import Alias, lazy_aliases, renamed_parameters
from archlux.errors import InvariantViolation

__all__ = ["Split", "load_split"]


@dataclass(frozen=True, slots=True)
class Split:
    """Three disjoint sets: 60 / 20 / 20, published as lists of identifiers."""

    name: str
    train: tuple[str, ...]
    calibration: tuple[str, ...]
    test: tuple[str, ...]
    fingerprint: str


def _lines(path: Path) -> tuple[str, ...]:
    """Read identifiers, one per line, without duplicates or comments."""
    if not path.is_file():
        raise InvariantViolation((f"missing split file: {path}",))
    seen: list[str] = []
    already: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        id = raw.strip()
        if not id or id.startswith("#"):
            continue
        if id in already:
            raise InvariantViolation((f"repeated identifier in {path.name}: {id}",))
        already.add(id)
        seen.append(id)
    return tuple(seen)


@renamed_parameters({"chemin": "path"})
def load_split(path: Path) -> Split:
    """Load a fixed split and verify that the three sets are disjoint.

    ``path`` is a directory containing ``train.txt``, ``calibration.txt``
    and ``test.txt`` (one identifier per line).

    Raises
    ------
    InvariantViolation
        An identifier appears in two sets, or a file is missing.
    """
    root = Path(path)
    train = _lines(root / "train.txt")
    calib = _lines(root / "calibration.txt")
    test = _lines(root / "test.txt")
    s_train, s_calib, s_test = set(train), set(calib), set(test)
    conflicts: list[str] = []
    if s_train & s_calib:
        conflicts.append("train ∩ calibration")
    if s_train & s_test:
        conflicts.append("train ∩ test")
    if s_calib & s_test:
        conflicts.append("calibration ∩ test")
    if conflicts:
        raise InvariantViolation((f"identifiers shared between sets: {', '.join(conflicts)}",))
    material = "\n".join((*train, "---", *calib, "---", *test)).encode()
    fingerprint = hashlib.blake2b(material, digest_size=16).hexdigest()
    return Split(
        name=root.name,
        train=train,
        calibration=calib,
        test=test,
        fingerprint=fingerprint,
    )


__getattr__ = lazy_aliases(
    __name__,
    {
        "Decoupage": Alias(Split, "archlux.data.splits.Split"),
        "charger_decoupage": Alias(load_split, "archlux.data.splits.load_split"),
    },
)
