# Formules des jalons 2 et 3

Ce dossier est le **formulaire** : chaque résultat utilisé dans le code y est énoncé,
dérivé, sourcé, et rattaché à une fonction. Un chercheur doit pouvoir refaire le calcul
sur papier sans ouvrir l'implémentation.

Les pages `concepts/` expliquent *pourquoi* l'architecture est ainsi.
Les pages `formules/` expliquent *quelle égalité* est codée, et d'où elle vient.

## Carte jalon 2 → pages

| Étape | Module | Page | Garantie |
|---|---|---|---|
| Ordre relatif | `geom.graphe` | [Ordre et graphe](ordre-relatif.md) | exacte |
| Polytope | `geom.polytope` | [Séparations linéaires](polytope-separe.md) | exacte |
| Objectif L1 | `geom.polytope`, `api` | [Épigraphe L1](epigraphe-l1.md) | exacte (reformulation) |
| Surfaces | `lmo.coupes` | [Coupes de surface](coupes-surface.md) | exacte (appui convexe) |
| Oracle LP | `lmo.solveur` | [Simplexe, duaux, Farkas](farkas.md) | exacte (LP) |
| Preuve | `certify.proof` | [Vérification exacte](preuve-exacte.md) | exacte (inspection) |
| Chaîne | `api.legalize` | [Pipeline](pipeline.md) | exacte en sortie |
| Orientation | `orient.circulaire` | [Statistiques circulaires](circulaire.md) | exacte (trigo) |
| Substitut J3 | `light.analytique` | [Substitut analytique](substitut-analytique.md) | **sans garantie** |
| Split-flux J4 | `light.simulateur` | [Facteur de lumière du jour](split-flux.md) | **sans garantie** (pas un sDA) |
| Rectilinéaire J6 | `geom.rectilineaire` | [Décomposition L](rectilineaire.md) | exacte (partition + fusions) |
| Actif J6 | `active` | [Apprentissage actif](apprentissage-actif.md) | budget de sims |
| Export J6 | `export` | [IFC / DXF / Wilson](export-bim.md) | exacte (pathologies) ; Wilson |
| Banc J6 | `bench` | [Banc d'essai](banc-essai.md) | trace + stats |
| Jetons J4 | `light.jetons` | [Jetons](jetons.md) | continu (anti-image) |
| Substitut appris J4 | `light.base` | — (perceptron `numpy`) | **sans garantie** ; cible = résidu analytique |
| Gradient J4 | `light.validation` | [Validation du gradient](validation-gradient.md) | accord de signe |
| Frank-Wolfe | `solve.frank_wolfe` | [Frank-Wolfe](frank-wolfe.md) | itérés exacts ; gap d'opt. |
| Statistique J5 | `uq.conforme` | [Prédiction conforme](statistique.md) | probabiliste |

## Comment lire une fiche

Chaque fiche a la même structure :

1. **Énoncé** — la formule, seule.
2. **Hypothèses** — ce qui doit être vrai pour que l'égalité tienne.
3. **Dérivation** — assez de pas pour la reconstruire.
4. **Code** — fonction et fichiers.
5. **Cas d'utilisation** — quand l'appliquer, quand elle est **fausse**.
6. **Source** — édition, section ou théorème, DOI si l'article en a un.

Les sources sont regroupées dans [la bibliographie](sources.md). Une citation sans
localisation (chapitre, théorème, DOI) n'est pas retenue.

## Exact vs probabiliste

Au jalon 2, les formules géométriques et d'optimisation linéaire sont **exactes**.
Au jalon 3, les itérés de Frank-Wolfe restent dans le polytope (garantie exacte) ;
le score du substitut analytique **n'a aucune couverture**. Au jalon 5, la
prédiction conforme borne l'oracle gelé : voir [statistique](statistique.md).
Ce n'est pas une preuve géométrique.

!!! warning "Ce que « l'oracle gelé » veut dire"
    `SplitFluxOracle` est une **forme fermée**, pas une mesure ni un lancer de
    rayons. Une couverture calculée contre lui est une couverture *sur cette
    formule*. Aucune fiche de ce dossier ne prétend le contraire, et
    [vérité terrain](../donnees/verite-terrain.md) dit où trouver de vraies
    étiquettes.
