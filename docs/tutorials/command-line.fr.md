# Ligne de commande

La commande `archlux` exécute les trois opérations principales sur un fichier de plan
(le format `Plan.to_json`), sans écrire de Python. Le dépôt fournit trois plans pour
l'essayer, dans `examples/`.

## Le contexte vient du plan et des options

Un fichier de plan ne porte pas de contexte ; la commande en construit un : les murs du
plan marqués `load_bearing` forment la structure, son contour est la parcelle, et la
réglementation vient de `--min-width` (mètres) et de `--min-area TYPE=M2`
(répétable). `--orientation` donne l'azimut en degrés.

## Vérifier un plan

```bash
archlux verify examples/t2.json --min-width 0.90 --min-area bedroom=9
```

```text
invalid
  NO  rooms overlap
  ok  no gap
  ok  minimum areas met
  ok  minimum widths met
  ok  structure kept
  - overlap bedroom|living: 0.36 m² (exact)
  - overlap bathroom|living: 0.2 m² (exact)
  max displacement: 0.000 m
```

La vérification exacte porte sur les chevauchements, les trous, les surfaces minimales et
la structure porteuse. La ligne de commande y ajoute la largeur : chaque rectangle de
pièce, y compris chaque sous-rectangle d'une pièce en L, doit mesurer au moins
`--min-width` dans les deux directions, la borne même qu'impose la légalisation. Une
pièce trop étroite est nommée, par exemple `width corridor: 0.50 m < 0.90 m`.

## Le légaliser

```bash
archlux legalize examples/t2.json --tiling --min-width 0.90 -o fixed.json --svg fixed.svg --report
archlux verify fixed.json --min-width 0.90 --min-area bedroom=9
```

`-o` écrit le plan corrigé (il peut écraser le fichier d'entrée), `--svg` un dessin,
et `--report` affiche le même verdict pour le résultat, ou signale qu'il ne porte aucun
certificat. `--tiling` ferme aussi les trous : les pièces pavent le contour.

## Demander si le programme est faisable

```bash
archlux feasible examples/t2.json --min-width 0.90 --min-area bedroom=9
```

## Codes de sortie et options refusées

| Code | Sens |
|---|---|
| 0 | valide, faisable ou légalisé |
| 1 | invalide ou infaisable |
| 2 | erreur : fichier illisible, option refusée, aucun plan valide trouvé |

Les trois commandes vérifient leurs options de la même façon, avant tout calcul :
`--min-width` et chaque valeur de `--min-area` doivent être finies et positives ou
nulles ; un type de `--min-area` doit être l'un des types de pièces du plan (casse
comprise) et n'apparaître qu'une fois ; `--orientation` doit être finie et est prise
modulo 360 (`-90` vaut `270`). Une option refusée affiche une ligne et sort avec le
code 2 :

```text
archlux: error: --min-area: no room of type 'Bedroom' in the plan; its types are bathroom, bedroom, living_room
```
