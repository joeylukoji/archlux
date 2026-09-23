# Corpus

Les jeux **train / calibration / test** sont des listes d'identifiants publiées
dans `splits/v1/`. **Dédupliquer avant de découper**, jamais l'inverse.

| Fiche | Ce qu'elle apporte | Licence | Dans ce dépôt |
|---|---|---|---|
| [**Vérité terrain**](verite-terrain.md) | **où sont les étiquettes d'éclairement** | — | méthode |
| [Synthétique](synthetique.md) | pavages 2×2 déterministes, substitut de CI | Apache-2.0 | oui, générateur |
| [Swiss Dwellings](swiss-dwellings.md) | **géométrie ↔ lumière appariées**, 367 colonnes de simulation | CC BY 4.0 | non redistribué |
| [MSD](msd.md) | murs porteurs, non-Manhattan, orientation cardinale | **CC BY-SA 4.0** | non redistribué |
| [CubiCasa5K](cubicasa.md) | baies annotées, SVG vectoriel | recherche / non commercial | non redistribué |
| [Imputation des baies](imputation.md) | corpus lacunaire → baies par défaut | — | méthode |

!!! warning "Commencer par la vérité terrain"
    Le corpus livré (90 plans synthétiques, étiquettes issues d'une forme fermée)
    fait tourner la chaîne, **pas une évaluation**. Avant d'annoncer un chiffre de
    couverture, lire [vérité terrain](verite-terrain.md) : elle dit d'où viennent
    réellement les étiquettes et ce qu'on a le droit d'en conclure.

Le jeu de calibration n'est lisible qu'avec un jeton émis **après** le gel des
poids (`uq.gestion`).
