# CubiCasa5K

Le versant **baies** de l'appariement : portes et fenêtres annotées finement, là
où les corpus simulés les omettent souvent.

## Fiche

| Point | Valeur |
|---|---|
| Auteurs | Kalervo, A., Ylioinas, J., Häikiö, M., Karhu, A., Kannala, J. (2019) |
| Article | [arXiv:1904.01920](https://arxiv.org/abs/1904.01920) |
| Code et téléchargement | <https://github.com/CubiCasa/CubiCasa5k> |
| Volume | 5 000 plans annotés, > 80 catégories d'objets |
| Format | **SVG vectoriel** par image, annotations sémantiques *et* géométriques |
| Licence | **usage recherche / non commercial** — lire la licence du dépôt avant tout téléchargement |
| Redistribué ici | **non** |

## Ce qu'il apporte

Les annotations sont **vectorielles**, pas raster : les segments de fenêtre sont
directement projetables en `Ouverture(mur_id, s, largeur_rel)`. C'est le seul
corpus de cette liste qui permet de mesurer l'écart entre baies **observées** et
baies **imputées** — la mesure exigée par [imputation](imputation.md).

## Ce qu'il n'apporte pas

- Aucune simulation d'éclairement.
- Aucune orientation cardinale fiable (plans finlandais, nord non garanti dans
  l'annotation) : `Orientation` reste à renseigner ou à traiter comme manquante.
- Échelle en pixels à convertir en mètres avant tout usage
  (`ARCHITECTURE.md` §7 : unités en mètres, sans exception).

!!! warning "Licence"
    La licence non commerciale de CubiCasa5K contamine tout modèle entraîné
    dessus. Si le substitut publié doit être réutilisable, entraîner sur
    [Swiss Dwellings](swiss-dwellings.md) (CC BY 4.0) / [MSD](msd.md) (CC BY-SA 4.0) et ne se
    servir de CubiCasa5K que pour l'**étude d'ablation** sur les baies.

## Citer

> Kalervo, A., Ylioinas, J., Häikiö, M., Karhu, A. & Kannala, J. (2019).
> *CubiCasa5K: A Dataset and an Improved Multi-Task Model for Floorplan Image
> Analysis*. SCIA 2019. [arXiv:1904.01920](https://arxiv.org/abs/1904.01920)

**Voir aussi :** [imputation](imputation.md), [vérité terrain](verite-terrain.md).
