# Swiss Dwellings

**C'est le seul corpus public qui porte le couple géométrie ↔ lumière.** Les autres
donnent des plans sans vérité lumineuse. Sans lui, le substitut n'apprend rien
d'autre qu'une formule fermée déjà connue — voir [vérité terrain](verite-terrain.md).

## Fiche

| Point | Valeur |
|---|---|
| Producteur | Archilyse AG |
| Version courante | **v3.0.0** (2023-03-31) |
| Volume | ≈ 45 000 appartements, ≈ 250 000 pièces, ≈ 3 100 bâtiments |
| Licence | **CC BY 4.0** — usage recherche *et* commercial, attribution obligatoire |
| DOI (concept) | [10.5281/zenodo.7070951](https://doi.org/10.5281/zenodo.7070951) |
| DOI (v3.0.0) | [10.5281/zenodo.7788422](https://doi.org/10.5281/zenodo.7788422) |
| Redistribué ici | **non** |

## Contenu

Un zip, quatre CSV :

| Fichier | Granularité | Contenu |
|---|---|---|
| `geometries.csv` | élément | géométries **WKT en mètres** : pièces, murs, **ouvertures**, équipements |
| `simulations.csv` | pièce (`area`) | **367 colonnes de simulation** par pièce |
| `locations.csv` | bâtiment | climat, contexte, accessibilité |
| `location_ratings.csv` | bâtiment | notes de situation |

Jointure : `site_id + building_id + floor_id + apartment_id + unit_id + area_id`
pour relier `geometries` à `simulations` ; `building_id` pour `locations`.

## Ce qui sert de vérité terrain

`simulations.csv` contient une famille **soleil / disponibilité lumineuse**, nommée
`<catégorie>_<dimension>_<agrégation>` (agrégations `min`, `max`, `mean`, `std`,
`median`, `p20`, `p80`), et des colonnes datées de la forme `sun_AAAAMMJJHHMM`
(ex. `sun_201803210800` = 21 mars, 8 h ; `sun_201806210600` = 21 juin, 6 h) —
équinoxe de printemps et solstice d'été, calculées par lancer de rayons sur une
tesselation hexagonale du sol, soleil direct **et** diffus.

!!! warning "Ce n'est pas un sDA LM-83"
    Ces colonnes sont des **agrégats d'irradiance à des instants donnés**, pas la
    part du sol au-dessus de 300 lux pendant 50 % des heures d'occupation. Deux
    conséquences, à écrire noir sur blanc dans toute publication :

    1. calibrer sur ces colonnes borne **ces colonnes**, pas un sDA ;
    2. l'indicateur `Literal["sDA", …]` de `archlux.types` doit alors être lu
       comme l'**étiquette de la cible apprise**, pas comme la métrique IES.

## Pipeline d'ingestion

1. Télécharger depuis Zenodo (compte non requis, fichiers de l'ordre du Go).
2. Reconstruire les `Plan` : WKT `POLYGON` des pièces → rectangles englobants ou
   décomposition rectilinéaire (`geom.rectilineaire.decomposer`) ; WKT des
   ouvertures → `Ouverture(mur_id, s, largeur_rel)` par projection sur le mur
   porteur le plus proche — **jamais de coordonnées absolues**
   (`ARCHITECTURE.md` §10).
3. Dédupliquer : `data.dedup`, distance de Hausdorff \(0{,}02\,\mathrm{m}\).
4. **Puis seulement** découper (`data.decoupage`). Jamais l'inverse : un doublon
   à cheval sur entraînement et calibration fausse silencieusement la couverture
   conforme.
5. `scripts/preparer_donnees.py` écrit les trois répertoires.

## Citer

> Standfest, M. *et al.* (2022–2023). *Swiss Dwellings: A large dataset of
> apartment models including aggregated geolocation-based simulation results
> covering viewshed, natural light, traffic noise, centrality and geometric
> analysis*. Zenodo. [doi:10.5281/zenodo.7070951](https://doi.org/10.5281/zenodo.7070951)

**Voir aussi :** [MSD](msd.md) (dérivé de ce corpus),
[vérité terrain](verite-terrain.md), [imputation](imputation.md).
