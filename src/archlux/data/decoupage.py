"""Découpage figé 60 / 20 / 20. Dédupliquer **avant**, sinon les quasi-doublons fuient."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from archlux.erreurs import InvariantViole

__all__ = ["Decoupage", "charger_decoupage"]


@dataclass(frozen=True, slots=True)
class Decoupage:
    """Trois jeux disjoints : 60 / 20 / 20, publiés sous forme de listes d'identifiants."""

    nom: str
    entrainement: tuple[str, ...]
    calibration: tuple[str, ...]
    test: tuple[str, ...]
    empreinte: str


def _lignes(chemin: Path) -> tuple[str, ...]:
    """Lire des identifiants, un par ligne, sans doublon ni commentaire."""
    if not chemin.is_file():
        raise InvariantViole((f"fichier de découpage absent : {chemin}",))
    vus: list[str] = []
    deja: set[str] = set()
    for brute in chemin.read_text(encoding="utf-8").splitlines():
        identifiant = brute.strip()
        if not identifiant or identifiant.startswith("#"):
            continue
        if identifiant in deja:
            raise InvariantViole(
                (f"identifiant répété dans {chemin.name} : {identifiant}",)
            )
        deja.add(identifiant)
        vus.append(identifiant)
    return tuple(vus)


def charger_decoupage(chemin: Path) -> Decoupage:
    """Charger un découpage figé et vérifier la disjonction des trois jeux.

    ``chemin`` est un répertoire contenant ``train.txt``, ``calibration.txt``
    et ``test.txt`` (un identifiant par ligne).

    Raises
    ------
    InvariantViole
        Un identifiant apparaît dans deux jeux, ou un fichier manque.
    """
    racine = Path(chemin)
    train = _lignes(racine / "train.txt")
    calib = _lignes(racine / "calibration.txt")
    test = _lignes(racine / "test.txt")
    s_train, s_calib, s_test = set(train), set(calib), set(test)
    conflits: list[str] = []
    if s_train & s_calib:
        conflits.append("train ∩ calibration")
    if s_train & s_test:
        conflits.append("train ∩ test")
    if s_calib & s_test:
        conflits.append("calibration ∩ test")
    if conflits:
        raise InvariantViole(
            (f"identifiants partagés entre jeux : {', '.join(conflits)}",)
        )
    materiau = "\n".join((*train, "---", *calib, "---", *test)).encode()
    empreinte = hashlib.blake2b(materiau, digest_size=16).hexdigest()
    return Decoupage(
        nom=racine.name,
        entrainement=train,
        calibration=calib,
        test=test,
        empreinte=empreinte,
    )
