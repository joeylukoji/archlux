"""Jalon 8 — dossier de comparaison **avant / après**, un plan par fiche.

Pourquoi ce script existe
-------------------------
`j8_generation.py` rend des taux. Un taux ne dit pas à quoi ressemble une
réparation, et deux chiffres justes du jalon 8 — « 60,9 % de plans valides » et
« déplacement médian de 56 % du côté » — laissent croire à des choses opposées.
Ce dossier permet de trancher en regardant.

Chaque fiche porte le SVG des deux états à la **même échelle**, et le fichier de
métriques correspondant : diagnostic géométrique avant, verdict de certification
après, déplacement. Les échecs sont inclus au même titre que les réussites — un
dossier qui ne montrerait que ce qui marche ne servirait à rien.

Usage : j8_visuels.py [plans.jsonl] [etiquette] [n_par_categorie]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import archlux as ax
from archlux.certify.preuve import verifier_exactement
from archlux.export.svg import comparer, rendre

sys.path.insert(0, str(Path(__file__).resolve().parent))
from j8_generation import BUDGETS, _construire, _echelle

PLANS = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/archlux-donnees/j8_plans.jsonl")
ETIQUETTE = sys.argv[2] if len(sys.argv) > 2 else "etoile"
PAR_CATEGORIE = int(sys.argv[3]) if len(sys.argv) > 3 else 8
BUDGET = BUDGETS[-1]
RACINE = Path("resultats/visuels") / ETIQUETTE


def _fiche(
    plan_id: str, plan, diag, preuve, corrige, statut: str, echelle: float
) -> str:
    """Métriques d'un plan, avant et après, en Markdown."""
    lignes = [
        f"# {plan_id}",
        "",
        f"Conditionnement `{ETIQUETTE}`, budget de réparation {BUDGET}, "
        f"échelle {echelle:.3f} m/unité.",
        "",
        f"**Issue : {statut}**",
        "",
        "## Avant — diagnostic géométrique",
        "",
        "| grandeur | valeur |",
        "|---|--:|",
        f"| pièces | {len(plan.pieces)} |",
        f"| pièces recouvertes par pièce | {diag.recouvrements:.2f} |",
        f"| part de jour dans l'enveloppe | {diag.part_jour:.1%} |",
        f"| dont trous intérieurs | {diag.part_trou:.1%} |",
        f"| morceaux disjoints | {diag.morceaux} |",
        f"| cellules de la trame implicite | {diag.cellules} |",
        f"| côté caractéristique | {diag.cote:.2f} m |",
        "",
        "## Avant — vérification exacte",
        "",
        f"valide : **{preuve.valide}**",
        "",
    ]
    lignes += [f"- {v}" for v in preuve.violations] or ["*aucune violation*"]
    lignes += ["", "## Après — correction", ""]
    if corrige is None:
        lignes += [
            f"Aucun plan produit : `{statut}`.",
            "",
            "Ce n'est pas un plantage. Un refus de trame signifie que la "
            "réparation bornée ne suffit pas à rendre la partition cohérente ; "
            "une infaisabilité est **prouvée**, certificat de Farkas à l'appui.",
        ]
    else:
        geo = corrige.certificat.geometrie
        lignes += [
            "| grandeur | valeur |",
            "|---|--:|",
            f"| valide | **{geo.valide}** |",
            f"| déplacement max | {geo.deplacement_max:.3f} m |",
            f"| rapporté au côté | {geo.deplacement_max / diag.cote:.0%} |",
            f"| pièces | {len(corrige.pieces)} |",
        ]
    return "\n".join(lignes) + "\n"


def main() -> None:
    lignes = [
        json.loads(x)
        for x in PLANS.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    echelle = _echelle(lignes)
    compte: dict[str, int] = {}
    index: list[tuple[str, str, str, str]] = []

    for plan_json in lignes:
        bati = _construire(plan_json, echelle)
        if isinstance(bati, str):
            continue
        plan, contexte, diag = bati
        preuve = verifier_exactement(plan, contexte)
        corrige, statut = None, "réparé"
        try:
            corrige = ax.legalize(
                plan, contexte, pavage=True, budget_reparation=BUDGET
            )
            if not corrige.certificat.geometrie.valide:
                statut = "corrigé mais invalide"
        except ax.Infaisable:
            statut = "infaisable (prouvé)"
        except ax.InvariantViole as echec:
            statut = (
                "trame irrécupérable"
                if "structurel" in str(echec)
                else "invariant violé"
            )
        # Quota par issue : un dossier qui ne montrerait que les reussites
        # donnerait une image fausse du jalon.
        if compte.get(statut, 0) >= PAR_CATEGORIE:
            continue
        compte[statut] = compte.get(statut, 0) + 1

        dossier = RACINE / statut.replace(" ", "-").replace("(", "").replace(")", "")
        dossier.mkdir(parents=True, exist_ok=True)
        avant = (
            f"{len(plan.pieces)} pièces, jour {diag.part_jour:.0%}, "
            f"{diag.morceaux} morceaux"
        )
        if corrige is None:
            # Un seul panneau. Redessiner le plan d'entree a droite se lirait
            # « rien n'a change », alors qu'aucun plan n'a ete produit du tout.
            svg = rendre(
                plan,
                contour=contexte.contour,
                titre=f"{statut} — {avant}",
            )
        else:
            svg = comparer(
                plan,
                corrige,
                contour=contexte.contour,
                titres=(
                    f"avant — {avant}",
                    f"après — {statut}, déplacement "
                    f"{corrige.certificat.geometrie.deplacement_max:.2f} m",
                ),
            )
        nom = plan_json["id"]
        (dossier / f"{nom}.svg").write_text(svg, encoding="utf-8")
        (dossier / f"{nom}.md").write_text(
            _fiche(nom, plan, diag, preuve, corrige, statut, echelle),
            encoding="utf-8",
        )
        index.append((statut, nom, f"{diag.part_jour:.0%}", str(diag.morceaux)))

    RACINE.mkdir(parents=True, exist_ok=True)
    table = [
        f"# Comparaisons avant / après — conditionnement `{ETIQUETTE}`",
        "",
        f"Budget de réparation {BUDGET}. Au plus {PAR_CATEGORIE} plans par issue, "
        "échecs compris.",
        "",
        "| issue | plan | jour avant | morceaux avant | fiche |",
        "|---|---|--:|--:|---|",
    ]
    for statut, nom, jour, morceaux in sorted(index):
        rep = statut.replace(" ", "-").replace("(", "").replace(")", "")
        table.append(
            f"| {statut} | `{nom}` | {jour} | {morceaux} | "
            f"[svg]({rep}/{nom}.svg) · [métriques]({rep}/{nom}.md) |"
        )
    (RACINE / "index.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(f"{len(index)} fiches -> {RACINE}")
    print("issues :", compte)


if __name__ == "__main__":
    main()
