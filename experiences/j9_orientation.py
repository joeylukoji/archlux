"""Jalon 9 — deplacer les pieces selon l'orientation du soleil.

Ce que ce jalon montre
----------------------
`legalize(..., objective=Substitut)` enchaine Frank-Wolfe depuis le point L1 **sans
sortir du polytope**. Chaque variante produite est donc un plan geometriquement
valide et certifie : on explore l'espace des dispositions admissibles, on n'en
sort jamais. Faire varier `Contexte.orientation` fait varier l'objectif, donc la
disposition retenue.

L'entree est un plan **genere** (jalon 8) puis legalise : la chaine complete va
donc de la sortie brute d'un modele a une famille de variantes certifiees.

Ce que ce jalon ne montre PAS
-----------------------------
**L'objectif optimise n'est pas l'eclairement reel.** `SubstitutAnalytique` a ete
mesure contre 4 239 pieces simulees de Swiss Dwellings : une fois normalise par
l'aire, son rang tombe a `rho = +0,085`, l'aire au sol seule le bat
(`rho = +0,590` contre `+0,403`), et sur des sites disjoints de l'entrainement le
rang **s'inverse** (`-0,342`). Voir `resultats/j7_sd_par_piece.md`.

Ces variantes sont donc « ce que le substitut croit », pas « ce que la lumiere
fait ». Ce qui est garanti ici est **geometrique** : chaque variante pave son
contour, et le certificat le prouve. La garantie lumineuse, elle, porte sur
l'oracle gele et non sur un sDA LM-83 (`docs/limites.md`).

Usage : j9_orientation.py [plans.jsonl] [n_plans] [budget_m]
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import archlux as ax
from archlux.export.svg import planche
from archlux.geom.graphe import deduire_ordre
from archlux.geom.polytope import construire_polytope, vectoriser
from archlux.light.analytique import SubstitutAnalytique
from archlux.types import Orientation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from j8_generation import BUDGETS, LARGEUR_DEFAUT, _construire, _echelle

DEFAUT = Path("D:/archlux-donnees/j8_plans_divers.jsonl")
AZIMUTS = tuple(range(0, 360, 45))
RACINE = Path("resultats/orientation")


def _score(plan, contexte, substitut) -> float:
    """Valeur du substitut pour ce plan sous cette orientation."""
    poly = construire_polytope(deduire_ordre(plan), contexte)
    return float(substitut.evaluer(vectoriser(plan, poly.index), contexte.orientation))


def main() -> None:
    plans_src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAUT
    n_plans = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0

    lignes = [
        json.loads(x)
        for x in plans_src.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    echelle = _echelle(lignes)
    substitut = SubstitutAnalytique(indicateur_vise="sDA")
    RACINE.mkdir(parents=True, exist_ok=True)

    index = [
        "# Jalon 9 — variantes par azimut solaire\n",
        f"Budget de deplacement {budget:.1f} m (norme infinie autour du point L1), "
        f"`largeur_min = {LARGEUR_DEFAUT:.2f} m`.\n",
        "**L'objectif optimise n'est pas l'eclairement reel** : voir l'en-tete de "
        "`experiences/j9_orientation.py`. Ce qui est garanti est geometrique.\n",
        "| plan | pieces | azimut du meilleur sDA | gain | deplacement | "
        "plus petit cote | variantes valides |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]

    retenus = 0
    for plan_json in lignes:
        if retenus >= n_plans:
            break
        bati = _construire(plan_json, echelle)
        if isinstance(bati, str):
            continue
        propose, contexte, diag = bati
        try:
            valide = ax.legalize(
                propose, contexte, pavage=True, budget_reparation=BUDGETS[-1]
            )
        except (ax.Infaisable, ax.InvariantViole):
            continue
        if not valide.certificat.geometrie.valide or len(valide.pieces) < 4:
            continue
        retenus += 1

        volets: list[tuple[object, str]] = []
        scores: list[tuple[int, float, float, float]] = []
        for azimut in AZIMUTS:
            ctx_az = replace(contexte, orientation=Orientation(deg=float(azimut)))
            avant = _score(valide, ctx_az, substitut)
            try:
                variante = ax.legalize(
                    valide, ctx_az, objective=substitut, budget=budget
                )
            except (ax.Infaisable, ax.InvariantViole):
                volets.append((valide, f"{azimut}° — pas de variante"))
                continue
            apres = _score(variante, ctx_az, substitut)
            bouge = max(
                max(abs(a.x - b.x), abs(a.y - b.y), abs(a.w - b.w), abs(a.h - b.h))
                for a, b in zip(valide.pieces, variante.pieces, strict=True)
            )
            cotes = [min(q.w, q.h) for q in variante.pieces]
            aires = [q.aire for q in variante.pieces]
            scores.append((
                azimut, avant, apres, bouge, min(cotes), min(aires), max(aires)
            ))
            gain = 100 * (apres - avant) / max(abs(avant), 1e-9)
            volets.append((variante, f"{azimut}° — sDA {apres:.0f} ({gain:+.0f} %)"))

        nom = plan_json["id"]
        (RACINE / f"{nom}.svg").write_text(
            planche(tuple(volets), contour=contexte.contour, colonnes=4),
            encoding="utf-8",
        )
        fiche = [
            f"# {nom} — variantes par azimut\n",
            f"{len(valide.pieces)} pieces, cote caracteristique {diag.cote:.2f} m, "
            f"budget {budget:.1f} m.\n",
            "| azimut | sDA legalise | sDA variante | gain | deplacement | "
            "plus petit cote | aire min | aire max |",
            "|--:|--:|--:|--:|--:|--:|--:|--:|",
        ]
        for azimut, avant, apres, bouge, cote, amin, amax in scores:
            fiche.append(
                f"| {azimut}° | {avant:.2f} | {apres:.2f} | "
                f"{100 * (apres - avant) / max(abs(avant), 1e-9):+.1f} % | "
                f"{bouge:.2f} m | {cote:.2f} m | {amin:.1f} m² | {amax:.1f} m² |"
            )
        fiche.append(
            "\nToutes les variantes listees sont **certifiees valides** : "
            "Frank-Wolfe ne sort pas du polytope.\n"
        )
        fiche.append(
            "Les trois dernieres colonnes ne sont pas decoratives. "
            "`Substitut.evaluer` rend **une somme sur les pieces** : la maximiser "
            "recompense donc de concentrer l'aire dans la piece la mieux orientee "
            "et de ramener les autres au plancher `largeur_min`. C'est le probleme "
            "de granularite documente dans `docs/limites.md`, rendu visible — un "
            "indicateur **par piece**, comme l'est un vrai sDA, ne se comporterait "
            "pas ainsi.\n"
        )
        (RACINE / f"{nom}.md").write_text("\n".join(fiche) + "\n", encoding="utf-8")

        if scores:
            meilleur = max(scores, key=lambda s: s[2])
            index.append(
                f"| [`{nom}`]({nom}.md) | {len(valide.pieces)} | {meilleur[0]}° | "
                f"{100 * (meilleur[2] - meilleur[1]) / max(abs(meilleur[1]), 1e-9):+.0f} % | "
                f"{meilleur[3]:.2f} m | {min(s[4] for s in scores):.2f} m | "
                f"{len(scores)} / {len(AZIMUTS)} |"
            )

    (RACINE / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"{retenus} plans -> {RACINE}")


if __name__ == "__main__":
    main()
