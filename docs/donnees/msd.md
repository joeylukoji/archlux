# MSD — Modified Swiss Dwellings

Le corpus de **géométrie** de référence de la littérature récente : murs porteurs
et poteaux annotés, graphes de zonage, orientation cardinale conservée, géométrie
non-Manhattan. **Il ne contient aucune simulation d'éclairement** — c'est son
corpus parent, [Swiss Dwellings](swiss-dwellings.md), qui les porte.

## Fiche

| Point | Valeur |
|---|---|
| Auteurs | van Engelenburg, C., Mostafavi, F. *et al.* (2024), ECCV |
| Article | [arXiv:2407.10121](https://arxiv.org/abs/2407.10121) · [doi:10.1007/978-3-031-73636-0_4](https://doi.org/10.1007/978-3-031-73636-0_4) |
| Page projet | <https://caspervanengelenburg.github.io/msd-eccv24-page/> |
| Code | <https://github.com/CasperVanEngelenburg/MSD> |
| Téléchargement | Kaggle : `caspervanengelenburg/modified-swiss-dwellings` |
| Volume | 5 372 plans d'étage, > 18 900 appartements distincts |
| Dérivé de | Swiss Dwellings **v3.0.0** |
| Licence | **CC BY-SA 4.0** (fiche Kaggle, vérifiée par l'API). **Pas** la CC BY 4.0 du corpus parent |
| Redistribué ici | **non** |

!!! warning "Partage à l'identique"
    MSD est sous **CC BY-SA 4.0**, alors que son corpus parent
    [Swiss Dwellings](swiss-dwellings.md) est sous CC BY 4.0. Le `SA` est une clause
    de **partage à l'identique** : elle se propage aux œuvres dérivées. Si le modèle
    ou les résultats publiés doivent rester librement réutilisables sans cette
    contrainte, entraîner sur Swiss Dwellings directement et n'employer MSD que pour
    la géométrie de comparaison.

## Contenu

Trois modalités liées : **image**, **géométrie**, **graphe**. Le graphe
(`networkx.Graph` ou `torch_geometric.data.Data`) porte forme et type de pièce sur
les nœuds, type de connexion sur les arêtes, image du plan complet au niveau graphe.

Pour `archlux`, seule la modalité **géométrie** est utilisable : l'image est un
raster, et un substitut à entrée raster a un gradient nul presque partout
(`ARCHITECTURE.md` §10, premier anti-pattern).

## Ce que MSD apporte à `archlux`

- **Murs porteurs annotés** → `Structure.murs_porteurs`, donc des égalités `A_eq`
  réelles et un `structure_preservee` qui veut dire quelque chose.
- **Géométrie non-Manhattan** → exerce `geom.rectilineaire.decomposer` sur autre
  chose qu'un cas de test.
- **Orientation cardinale conservée** → `Orientation` cesse d'être tirée au sort.
- **Complexes multi-logements** → des ordres relatifs autrement plus riches que
  les pavages 2×2 du [corpus synthétique](synthetique.md).

## Ce qu'il n'apporte pas

Aucune étiquette d'éclairement. L'appariement se fait par les identifiants Swiss
Dwellings dont MSD est dérivé — c'est la voie recommandée, et elle est décrite
dans [vérité terrain](verite-terrain.md).

## Citer

> van Engelenburg, C., Mostafavi, F., *et al.* (2024). *MSD: A Benchmark Dataset
> for Floor Plan Generation of Building Complexes*. ECCV 2024.
> [doi:10.1007/978-3-031-73636-0_4](https://doi.org/10.1007/978-3-031-73636-0_4)

**Voir aussi :** [Swiss Dwellings](swiss-dwellings.md),
[imputation](imputation.md), [vérité terrain](verite-terrain.md).
