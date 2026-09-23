"""Orchestration du banc : manifeste → bruts → résultat (sans agrégation)."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from archlux.bench.manifeste import emettre
from archlux.erreurs import InvariantViole
from archlux.io.json_io import manifeste_vers_dict
from archlux.light.protocole import Substitut
from archlux.types import Manifeste, ModeleTrace, Orientation, Plan

__all__ = ["LigneBrute", "Manifest", "Resultat", "run"]

Manifest = Manifeste  # alias wording `MILESTONE-6.md`


@dataclass(frozen=True, slots=True)
class LigneBrute:
    """Une mesure avant toute agrégation."""

    plan_id: str
    methode: str
    orientation_deg: float
    score: float


@dataclass(frozen=True, slots=True)
class Resultat:
    """Sortie de :func:`run` : manifeste + chemins + lignes brutes."""

    manifest: Manifeste
    chemin_bruts: Path
    chemin_manifeste: Path
    lignes: tuple[LigneBrute, ...]


def run(
    *,
    plans: Sequence[Plan],
    orientations: Sequence[Orientation],
    methods: Sequence[Substitut],
    evaluate_by: Callable[[Plan, Substitut], float],
    seed: int,
    empreinte_donnees: str,
    decoupage: str,
    modele: ModeleTrace,
    repertoire: Path | str,
    parametres: Mapping[str, str] | None = None,
) -> Resultat:
    """Exécuter le banc : écrire le manifeste, puis les bruts, puis retourner.

    L'ordre est contraignant (`MILESTONE-6.md` §5) : aucun agrégat avant les bruts.
    """
    if len(plans) != len(orientations):
        raise InvariantViole(("plans et orientations doivent avoir la même longueur",))
    if not methods:
        raise InvariantViole(("au moins une méthode est requise",))

    dossier = Path(repertoire)
    dossier.mkdir(parents=True, exist_ok=True)

    manifeste = emettre(
        seed=seed,
        empreinte_donnees=empreinte_donnees,
        decoupage=decoupage,
        parametres=dict(parametres) if parametres else None,
        modele=modele,
    )
    chemin_manifeste = dossier / "manifeste.json"
    _ecrire_manifeste(chemin_manifeste, manifeste)

    lignes: list[LigneBrute] = []
    for plan, orientation in zip(plans, orientations, strict=True):
        # ``ids_pieces`` est trié : l'identifiant de banc ne dépend pas de l'ordre
        # d'insertion du tuple ``pieces``.
        plan_id = "-".join(plan.ids_pieces) if plan.ids_pieces else "vide"
        for methode in methods:
            nom = type(methode).__name__
            score = float(evaluate_by(plan, methode))
            lignes.append(
                LigneBrute(
                    plan_id=plan_id,
                    methode=nom,
                    orientation_deg=float(orientation.deg),
                    score=score,
                )
            )

    chemin_bruts = dossier / "resultats_bruts.csv"
    _ecrire_bruts(chemin_bruts, lignes)

    return Resultat(
        manifest=manifeste,
        chemin_bruts=chemin_bruts,
        chemin_manifeste=chemin_manifeste,
        lignes=tuple(lignes),
    )


def _ecrire_manifeste(chemin: Path, manifeste: Manifeste) -> None:
    # Même forme que le schéma JSON des certificats (`io.json_io`) — une seule vérité.
    """Ecrire le manifeste en JSON, cles triees, avant tout resultat."""
    payload = manifeste_vers_dict(manifeste)
    chemin.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ecrire_bruts(chemin: Path, lignes: Sequence[LigneBrute]) -> None:
    """Ecrire les mesures brutes en CSV, avant toute agregation."""
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["plan_id", "methode", "orientation_deg", "score"])
        for ligne in lignes:
            w.writerow(
                [ligne.plan_id, ligne.methode, f"{ligne.orientation_deg:.6f}", f"{ligne.score:.8f}"]
            )
