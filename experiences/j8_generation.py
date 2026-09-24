"""Jalon 8 — legaliser des plans **reellement generes**, pas des plans corrompus.

Ce que ce jalon ajoute au jalon 7
---------------------------------
`j7_msd_reparation.py` mesure la reparation de plans MSD **corrompus a la main**.
La faute y est connue, ce qui est ideal pour attribuer un echec — mais les
amplitudes ne sont calibrees sur aucun generateur reel (`data.corruption` le dit).
Ici les entrees sortent d'un modele publie, jamais abimees par nous : c'est le
controle de **validite externe** de la table du jalon 7.

Le generateur
-------------
HouseDiffusion (Shabani, Hosseini, Furukawa, CVPR 2023), poids officiels
`model250000.pt`, entraine sur RPLAN. Le modele rend des coordonnees vectorielles,
donc aucune vectorisation d'image ne vient s'interposer entre lui et nous.

**Il est echantillonne sur 1000 pas, sans reechantillonnage.** Ce n'est pas un
detail de confort : `gaussian_diffusion.py:270` n'active la branche de debruitage
**discret** — la contribution meme du papier, celle qui aligne les coins sur la
grille — que pour ``t < 32``. Sous-echantillonner la trajectoire la court-circuite
et fabrique un desalignement qui n'appartient pas au modele. Mesure de l'ecart
median d'un coin a son rectangle axe, selon le nombre de pas :

===== ==========
pas    ecart
===== ==========
20     0,750 m
80     0,188 m
200    0,000 m
1000   0,000 m
===== ==========

A 1000 pas les pieces generees sont **exactement** axees : aucune approximation
par boite englobante n'entre dans la mesure qui suit.

Frontiere de licence
--------------------
HouseDiffusion est sous **GPL v3, usage commercial interdit**. archlux est sous
Apache-2.0 et ne l'importe pas : l'echantillonnage vit dans un script separe
(`vendor/j8_generer.py`, hors depot) et la frontiere entre les deux est le fichier
JSONL lu ici.

Usage : j8_generation.py [plans.jsonl] [n_max] [etiquette]
"""

from __future__ import annotations

import csv as csvmod
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from shapely.geometry import box
from shapely.ops import unary_union

import archlux as ax
from archlux.certify.proof import verify_exactly
from archlux.export.wilson import intervalle_wilson
from archlux.geom.diagnostic import Diagnostic, diagnostiquer
from archlux.types import (
    Contexte,
    Orientation,
    Piece,
    Plan,
    Referentiel,
    Structure,
)

DEFAUT = Path("D:/archlux-donnees/j8_plans.jsonl")

# Aire mediane d'un appartement MSD, mesuree sur 1200 appartements : 79,0 m2.
# Les coordonnees RPLAN sont sans unite ; on fixe l'echelle pour que l'aire
# mediane generee vaille celle de MSD, afin que les deplacements des jalons 7 et 8
# soient comparables. Aucun taux de validite n'en depend : chevauchement et jour
# sont invariants d'echelle.
AIRE_CIBLE_M2 = 79.0
COTE_MIN_M = 0.05  # sous ce seuil une piece est degeneree, pas etroite

# Budgets balayes. Le defaut d'`api.legalize` est 4, cale sur des plans corrompus.
# Une sortie de generateur releve d'un autre regime : on mesure la courbe entiere
# plutot que de reporter le seul point qui arrange.
BUDGETS = (0, 4, 8, 16)

# Largeur minimale d'une piece, en metres. Ce parametre n'est PAS un detail de
# conformite ici : sans plancher strictement positif, le moyen le moins couteux de
# fermer un jour est de reduire une piece a zero, et le plan sort « valide » avec
# une piece annihilee. Mesure a `largeur_min = 0` : 61 % des plans reputes repares
# contenaient au moins une piece de cote exactement nul.
#
# Le jalon 7 posait 0,0 pour une bonne raison — un seuil a 1,80 m cassait 52 plans
# MSD **deja valides** sur 60. Cette prudence ne s'applique pas ici : 0 / 740 plans
# generes sont valides au depart, donc le seuil ne peut rien casser.
LARGEUR_DEFAUT = 0.50
LARGEURS = (0.0, 0.25, 1.00, 1.80)

# Sous ce cote, ce n'est plus une piece mais un residu que le trace ne montre meme
# pas. Sert a distinguer « valide » de « valide ET programme preserve ».
COTE_INTACT_M = 0.50

CHAMPS = (
    "plan_id",
    "programme",
    "graphe",
    "n_pieces",
    "mode",
    "budget",
    "largeur_min",
    "valide_avant",
    "valide_apres",
    "n_pieces_apres",
    "cote_min_apres",
    "intact",
    "cellules",
    "recouvrements_avant",
    "part_jour_avant",
    "part_trou_avant",
    "morceaux_avant",
    "cote_m",
    "deplacement_max_m",
    "deplacement_relatif",
    "temps_ms",
    "statut",
)


def _boites(plan_json: dict, echelle: float) -> list[tuple[str, tuple[float, ...]]]:
    """(type, (x, y, w, h)) en metres, une entree par piece generee."""
    out = []
    for piece in plan_json["pieces"]:
        coins = np.asarray(piece["coins"], dtype=float) * echelle
        x0, y0 = float(coins[:, 0].min()), float(coins[:, 1].min())
        x1, y1 = float(coins[:, 0].max()), float(coins[:, 1].max())
        out.append((str(piece["type"]), (x0, y0, x1 - x0, y1 - y0)))
    return out


def _echelle(lignes: list[dict]) -> float:
    """Facteur unite -> metre calant l'aire mediane generee sur celle de MSD."""
    aires = []
    for plan_json in lignes:
        formes = [box(x, y, x + w, y + h) for _, (x, y, w, h) in _boites(plan_json, 1.0)]
        union = unary_union(formes)
        if not union.is_empty:
            aires.append(union.area)
    return float(np.sqrt(AIRE_CIBLE_M2 / np.median(aires)))


def _construire(plan_json: dict, echelle: float) -> tuple[Plan, Contexte, Diagnostic] | str:
    """Plan archlux + diagnostic d'entree, ou le motif de rejet en clair."""
    boites = _boites(plan_json, echelle)
    if any(w < COTE_MIN_M or h < COTE_MIN_M for _, (_, _, w, h) in boites):
        return "piece degeneree"

    pieces = tuple(
        Piece(id=f"p{rang:03d}", type=type_piece, x=x, y=y, w=w, h=h)
        for rang, (type_piece, (x, y, w, h)) in enumerate(boites)
    )
    formes = [box(p.x, p.y, p.x + p.w, p.y + p.h) for p in pieces]
    union = unary_union(formes)
    if union.is_empty:
        return "union vide"

    # Le contour vise est la **boite englobante** de l'union. HouseDiffusion ne
    # recoit aucune enveloppe en condition : il invente son emprise. Imposer le
    # pavage de cette boite, c'est donc aussi equarrir l'emprise — c'est assume,
    # et le deplacement rapporte en donne le cout.
    x0, y0, x1, y1 = union.bounds
    contour = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))

    plan = Plan(pieces=pieces, murs=(), ouvertures=(), contour=contour)
    contexte = Contexte(
        structure=Structure(murs_porteurs=(), poteaux=()),
        orientation=Orientation(deg=0.0),
        contour=contour,
        # Le referentiel est remplace essai par essai : voir LARGEUR_DEFAUT.
        referentiel=Referentiel(aires_min=(), largeur_min=LARGEUR_DEFAUT),
        programme=tuple(sorted(set(plan_json["programme"]))),
    )
    return plan, contexte, diagnostiquer(plan)


def _resumer(brut: Path, echelle: float, rejets: dict[str, int]) -> str:
    """Table de synthese, intervalles de Wilson compris."""
    with brut.open(encoding="utf-8") as flux:
        rangs = list(csvmod.DictReader(flux))
    plans = {r["plan_id"] for r in rangs}
    avant = sum(r["valide_avant"] == "True" for r in rangs if r["mode"] == "base")
    # Les tables principales portent sur la largeur nominale ; le balayage des
    # largeurs a sa propre table plus bas.
    nominal = f"{LARGEUR_DEFAUT:.2f}"
    a_nominal = [r for r in rangs if r["largeur_min"] == nominal]
    diag = [r for r in a_nominal if r["mode"] == "base"]
    cellules = np.asarray([float(r["cellules"]) for r in diag])
    recouv = np.asarray([float(r["recouvrements_avant"]) for r in diag])
    jour = np.asarray([float(r["part_jour_avant"]) for r in diag])
    trou = np.asarray([float(r["part_trou_avant"]) for r in diag])
    morceaux = np.asarray([float(r["morceaux_avant"]) for r in diag])

    lignes = [
        "| mode | budget | n | réparés | IC 95 % | t médian | déplacement médian |",
        "|---|--:|--:|--:|:--:|--:|--:|",
    ]
    for mode, budget in [("base", "")] + [("pavage", str(b)) for b in BUDGETS]:
        lot = [r for r in a_nominal if r["mode"] == mode and r["budget"] == budget]
        if not lot:
            continue
        ok = sum(r["valide_apres"] == "True" for r in lot)
        bas, haut = intervalle_wilson(ok, len(lot))
        temps = np.median([float(r["temps_ms"]) for r in lot])
        depl = [float(r["deplacement_max_m"]) for r in lot if r["deplacement_max_m"]]
        rel = [float(r["deplacement_relatif"]) for r in lot if r["deplacement_relatif"]]
        med_depl = f"{np.median(depl):.2f} m ({np.median(rel):.0%} du côté)" if depl else "—"
        etiquette = "`legalize` seul" if mode == "base" else "`pavage=True`"
        lignes.append(
            f"| {etiquette} | {budget or '—'} | {len(lot)} | "
            f"**{100 * ok / len(lot):.1f} %** | [{100 * bas:.1f}, {100 * haut:.1f}] | "
            f"{temps:.1f} ms | {med_depl} |"
        )

    # Coupe par nombre de pieces. C'est elle qui explique le taux, pas la
    # connexite : a budget fixe la reparation bornee corrige un nombre borne de
    # cellules, et la trame enfle en (2n-1)^2 quand aucun bord ne coincide.
    dernier = str(BUDGETS[-1])
    lot_final = [r for r in a_nominal if r["mode"] == "pavage" and r["budget"] == dernier]

    # Balayage de la largeur minimale. C'est la table decisive : sans plancher
    # strictement positif, fermer un jour en reduisant une piece a zero est la
    # solution la moins couteuse, et le plan sort « valide » amoute d'une piece.
    largeurs = [
        "| `largeur_min` | n | valides | **dont aucune pièce écrasée** | "
        "plus petit côté | déplacement médian |",
        "|--:|--:|--:|--:|--:|--:|",
    ]
    for largeur in sorted({*LARGEURS, LARGEUR_DEFAUT}):
        cle = f"{largeur:.2f}"
        lot = [
            r
            for r in rangs
            if r["mode"] == "pavage" and r["budget"] == dernier and r["largeur_min"] == cle
        ]
        if not lot:
            continue
        ok = sum(r["valide_apres"] == "True" for r in lot)
        sains = sum(r["intact"] == "True" for r in lot)
        b1, h1 = intervalle_wilson(ok, len(lot))
        b2, h2 = intervalle_wilson(sains, len(lot))
        cotes = [float(r["cote_min_apres"]) for r in lot if r["cote_min_apres"]]
        rel = [float(r["deplacement_relatif"]) for r in lot if r["deplacement_relatif"]]
        marque = " *(nominal)*" if largeur == LARGEUR_DEFAUT else ""
        largeurs.append(
            f"| {largeur:.2f} m{marque} | {len(lot)} | "
            f"{100 * ok / len(lot):.1f} % [{100 * b1:.1f}, {100 * h1:.1f}] | "
            f"**{100 * sains / len(lot):.1f} %** [{100 * b2:.1f}, {100 * h2:.1f}] | "
            f"{(f'{np.median(cotes):.3f} m' if cotes else '—')} | "
            f"{(f'{np.median(rel):.0%}' if rel else '—')} |"
        )
    par_n: dict[int, list[dict[str, str]]] = {}
    for r in lot_final:
        par_n.setdefault(int(r["n_pieces"]), []).append(r)
    coupe = [
        f"| pièces | n | réparés (budget {dernier}) | cellules médianes |",
        "|--:|--:|--:|--:|",
    ]
    for k in sorted(par_n):
        rangs_k = par_n[k]
        ok = sum(x["valide_apres"] == "True" for x in rangs_k)
        cel = np.median([float(x["cellules"]) for x in rangs_k])
        coupe.append(f"| {k} | {len(rangs_k)} | {100 * ok / len(rangs_k):.1f} % | {cel:.0f} |")

    # Coupe par topologie du graphe d'acces. Le `door_mask` de HouseDiffusion en
    # derive : c'est une entree du modele, pas une mise en scene. Si le taux y
    # etait sensible, aucun chiffre global ne serait interpretable.
    par_topo: dict[str, list[dict[str, str]]] = {}
    for r in lot_final:
        par_topo.setdefault(r["graphe"], []).append(r)
    topo = [
        f"| topologie | n | réparés (budget {dernier}) | jour méd. | "
        "recouvr. méd. | morceaux méd. |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for cle in sorted(par_topo):
        rangs_t = par_topo[cle]
        ok = sum(x["valide_apres"] == "True" for x in rangs_t)
        topo.append(
            f"| `{cle}` | {len(rangs_t)} | {100 * ok / len(rangs_t):.1f} % | "
            f"{np.median([float(x['part_jour_avant']) for x in rangs_t]):.1%} | "
            f"{np.median([float(x['recouvrements_avant']) for x in rangs_t]):.2f} | "
            f"{np.median([float(x['morceaux_avant']) for x in rangs_t]):.0f} |"
        )

    motifs: dict[str, int] = {}
    for r in rangs:
        if r["statut"] != "ok":
            cle = f"{r['mode']}{r['budget']}:{r['statut']}"
            motifs[cle] = motifs.get(cle, 0) + 1

    return (
        "# Jalon 8 — légaliser des plans **réellement générés**\n\n"
        f"HouseDiffusion (CVPR 2023), poids officiels `model250000.pt`, RPLAN, "
        f"**1000 pas** sans rééchantillonnage. {len(plans)} plans, "
        f"{len(plans) and int(np.sum([float(r['n_pieces']) for r in diag]))} pièces. "
        f"Échelle {echelle:.3f} m/unité, calée sur l'aire médiane MSD (79,0 m²).\n\n"
        f"**{avant} plan(s) sur {len(plans)} sont valides avant correction.**\n\n"
        "## État des sorties du générateur\n\n"
        "| | médiane | moyenne | p95 |\n|---|--:|--:|--:|\n"
        f"| pièces recouvertes par pièce | {np.median(recouv):.2f} | "
        f"{recouv.mean():.2f} | {np.quantile(recouv, 0.95):.2f} |\n"
        f"| part de jour dans l'enveloppe | {np.median(jour):.1%} | "
        f"{jour.mean():.1%} | {np.quantile(jour, 0.95):.1%} |\n"
        f"| dont trous **intérieurs** | {np.median(trou):.1%} | "
        f"{trou.mean():.1%} | {np.quantile(trou, 0.95):.1%} |\n"
        f"| morceaux disjoints de l'union | {np.median(morceaux):.0f} | "
        f"{morceaux.mean():.2f} | {np.quantile(morceaux, 0.95):.0f} |\n"
        f"| cellules de la trame implicite | {np.median(cellules):.0f} | "
        f"{cellules.mean():.0f} | {np.quantile(cellules, 0.95):.0f} |\n\n"
        "## Réparation\n\n"
        f"Référentiel `largeur_min = {LARGEUR_DEFAUT:.2f} m`.\n\n" + "\n".join(lignes) + "\n\n"
        "## Ce que coûte — et rapporte — un plancher sur la largeur\n\n"
        + "\n".join(largeurs)
        + "\n\n"
        "## Réparation par taille de programme\n\n" + "\n".join(coupe) + "\n\n"
        "## Réparation par topologie du graphe d'accès\n\n" + "\n".join(topo) + "\n\n"
        f"## Échecs\n\n{motifs}\n\n"
        f"## Rejets à la construction\n\n{rejets or 'aucun'}\n"
    )


def main() -> None:
    # La ligne de commande est lue ICI et pas au niveau module : `j8_visuels`
    # importe `_construire` et `_echelle`, et un parsing a l'import ferait
    # echouer l'import sur ses propres arguments.
    plans = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAUT
    n_max = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
    # Etiquette de sortie : deux conditionnements de graphe sont mesures, et
    # leurs resultats ne doivent pas s'ecraser l'un l'autre.
    etiquette = sys.argv[3] if len(sys.argv) > 3 else plans.stem
    lignes = [
        json.loads(ligne)
        for ligne in plans.read_text(encoding="utf-8").splitlines()[:n_max]
        if ligne.strip()
    ]
    if not lignes:
        raise SystemExit(f"aucun plan dans {plans}")
    echelle = _echelle(lignes)
    print(f"{len(lignes)} plans generes, echelle {echelle:.4f} m/unite")

    Path("resultats").mkdir(exist_ok=True)
    sortie = Path(f"resultats/j8_{etiquette}_brut.csv")
    rejets: dict[str, int] = {}
    with sortie.open("w", newline="", encoding="utf-8") as flux:
        ecrivain = csvmod.DictWriter(flux, fieldnames=CHAMPS)
        ecrivain.writeheader()
        for plan_json in lignes:
            bati = _construire(plan_json, echelle)
            if isinstance(bati, str):
                rejets[bati] = rejets.get(bati, 0) + 1
                continue
            plan, contexte, diagnostic = bati
            avant = verify_exactly(plan, contexte).valide
            # Deux balayages, pas leur produit : les budgets a largeur nominale,
            # puis les largeurs au meilleur budget. Le second existe parce que
            # `largeur_min = 0` laisse le LP annihiler une piece pour fermer un
            # jour — il faut pouvoir montrer ce que ce seuil coute et rapporte.
            essais = [("base", 0, LARGEUR_DEFAUT)]
            essais += [("pavage", b, LARGEUR_DEFAUT) for b in BUDGETS]
            essais += [
                ("pavage", BUDGETS[-1], largeur)
                for largeur in LARGEURS
                if largeur != LARGEUR_DEFAUT
            ]
            for mode, budget, largeur in essais:
                debut = time.perf_counter()
                statut, valide, deplacement, n_apres = "ok", False, "", ""
                cote_min, intact = "", ""
                contexte_essai = replace(
                    contexte,
                    referentiel=Referentiel(aires_min=(), largeur_min=largeur),
                )
                try:
                    corrige = ax.legalize(
                        plan,
                        contexte_essai,
                        pavage=(mode == "pavage"),
                        budget_reparation=budget,
                    )
                    valide = corrige.certificat.geometrie.valide
                    deplacement = f"{corrige.certificat.geometrie.deplacement_max:.6f}"
                    n_apres = str(len(corrige.pieces))
                    petit = min(min(p.w, p.h) for p in corrige.pieces)
                    cote_min = f"{petit:.4f}"
                    # « Intact » = valide ET aucune piece reduite a un residu.
                    # Compter les pieces ne suffit pas : une piece ecrasee a
                    # 0 m reste dans le compte.
                    intact = str(bool(valide and petit >= COTE_INTACT_M))
                except ax.Infaisable:
                    statut = "infaisable"
                except ax.InvariantViole as echec:
                    statut = (
                        "trame"
                        if mode == "pavage" and "structurel" in str(echec)
                        else "invariant_viole"
                    )
                ecrivain.writerow(
                    {
                        "plan_id": plan_json["id"],
                        "programme": "+".join(plan_json["programme"]),
                        # Absent des premiers JSONL : le champ n'existait pas encore.
                        "graphe": plan_json.get("graphe", "etoile"),
                        "n_pieces": len(plan.pieces),
                        "mode": mode,
                        "budget": budget if mode == "pavage" else "",
                        "largeur_min": f"{largeur:.2f}",
                        "valide_avant": avant,
                        "valide_apres": valide,
                        "n_pieces_apres": n_apres,
                        "cote_min_apres": cote_min,
                        "intact": intact,
                        "cellules": diagnostic.cellules,
                        "recouvrements_avant": f"{diagnostic.recouvrements:.3f}",
                        "part_jour_avant": f"{diagnostic.part_jour:.4f}",
                        "part_trou_avant": f"{diagnostic.part_trou:.4f}",
                        "morceaux_avant": diagnostic.morceaux,
                        "cote_m": f"{diagnostic.cote:.3f}",
                        "deplacement_max_m": deplacement,
                        "deplacement_relatif": (
                            f"{float(deplacement) / diagnostic.cote:.4f}" if deplacement else ""
                        ),
                        "temps_ms": f"{(time.perf_counter() - debut) * 1000:.3f}",
                        "statut": statut,
                    }
                )
    print("bruts ecrits :", sortie)
    resume = Path(f"resultats/j8_{etiquette}.md")
    resume.write_text(_resumer(sortie, echelle, rejets), encoding="utf-8")
    print("resume ecrit :", resume)
    if rejets:
        print("rejets :", rejets)


if __name__ == "__main__":
    main()
