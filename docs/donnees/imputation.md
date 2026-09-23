# Imputation des ouvertures

**Code :** `data.imputation.imputer_ouvertures`.

Le corpus simulé n'a souvent pas les baies ; celui qui a les baies n'a pas les
simulations.

Règle : baie centrée (`s=0.5`) sur chaque mur sans ouverture, largeur relative
\(0{,}30\) (`RATIO_BAIE_DEFAUT`). Les baies déjà présentes sont intactes.

Pour mesurer l'effet : calibrer (jalon 5) séparément sur le sous-jeu aux baies
observées et sur le jeu imputé, et **publier les deux** couvertures. Une
couverture obtenue seulement sur l'imputé n'est pas une couverture sur le réel.
