# Schéma JSON des plans, version `2`

Format d'échange lu et écrit par `Plan.from_json` et `Plan.to_json`. Unités : **mètres**,
mètres carrés, azimut en degrés. Origine au coin inférieur gauche du contour, axe `y`
vers le nord géographique.

Le schéma **v2** a des clés anglaises et des types de pièces anglais. Les fichiers du
schéma **v1** (clés et types de pièces français) sont toujours lus : voir
[Lire le schéma v1](#lire-le-schema-v1).

## Règles du format

- **La version est obligatoire.** Un fichier dont le `schema` n'est ni `"2"` ni `"1"` est
  refusé avec `InvariantViolation` : mieux vaut refuser bruyamment que deviner le format,
  car un plan mal lu produit un faux certificat.
- **L'écriture est déterministe.** Clés triées, UTF-8, indentation 2, fin de ligne `\n`.
  Deux écritures du même plan donnent les mêmes octets ; sans cela, l'empreinte
  enregistrée dans un manifeste n'identifie rien.
- **Aucune position absolue d'une ouverture.** Une ouverture est décrite par `wall_id`,
  `s` et `relative_width` ; sa position se déduit du mur. C'est l'invariant qui empêche
  fenêtres et cloisons de se désynchroniser quand le solveur déplace un mur.
- **Un `null` explicite plutôt qu'une clé absente.** `"performance": null` signifie
  « aucune garantie de performance revendiquée » : une information, pas un oubli.
- **Les plages sont vérifiées à la lecture.** `s` dans `[0, 1]`, `relative_width` dans
  `]0, 1]`, dimensions et épaisseurs strictement positives, et **aucune valeur non
  finie**, bien que `json.loads` accepte les littéraux `NaN` et `Infinity`. Un fichier
  fautif est refusé avec la **liste complète** de ses violations, pas seulement la
  première.

## Schéma publié

Le format est décrit par un **JSON Schema** (draft 2020-12) livré avec le paquet :
`archlux/io/plan-v2.schema.json` (et `plan-v1.schema.json` pour l'ancien format). Un
tiers peut valider un fichier sans exécuter archlux :

```python
import json
from importlib import resources

import jsonschema

schema = json.loads(resources.files("archlux.io").joinpath("plan-v2.schema.json").read_text())
plan = {"schema": "2", "outline": [[0, 0], [4, 0], [4, 3], [0, 3]],
        "rooms": [{"id": "a", "type": "living_room", "x": 0, "y": 0, "w": 4, "h": 3}],
        "walls": [], "openings": [], "certificate": None}
jsonschema.validate(plan, schema)
```

Le schéma et le lecteur refusent les mêmes plages (test `test_json_schema.py`), à une
exception près : JSON Schema ne sait pas exprimer « nombre fini », donc seul le lecteur
refuse `NaN` et `Infinity`. Toute sortie de `Plan.to_json` est valide pour le schéma,
certificat et `regime` compris.

## Champs

| Champ | Type | Signification |
|---|---|---|
| `schema` | `"2"` | Version du format |
| `outline` | liste de `[x, y]` | Enveloppe du logement |
| `rooms[]` | `id`, `type`, `x`, `y`, `w`, `h` | Rectangle, coin inférieur gauche en `(x, y)` |
| `walls[]` | `id`, `a`, `b`, `load_bearing`, `thickness` | Segment ; `load_bearing: true` signifie fixé pour le solveur |
| `openings[]` | `id`, `wall_id`, `s`, `relative_width`, `sill_height`, `head_height` | `s` = abscisse **du centre** le long du mur, dans `[0, 1]` ; `relative_width` en fraction de la longueur du mur |
| `certificate` | objet ou `null` | `null` pour un plan proposé ; toujours présent sur un plan légalisé |

Le `type` de pièce est un texte libre. Les valeurs que la bibliothèque connaît sont
`living_room`, `bedroom`, `kitchen`, `bathroom`, `toilet` et `corridor` ; tout autre type
est conservé tel quel et ne reçoit aucune surface minimale d'un `Regulation` qui ne le
liste pas.

### Le certificat

Deux garanties de natures différentes, séparées par construction ; voir
[Les deux garanties](../concepts/two-guarantees.md).

| Champ | Nature | Signification |
|---|---|---|
| `geometry` | **exacte** | Les quatre prédicats vérifiés indépendamment du solveur (`overlap`, `gaps`, `areas_ok`, `structure_kept`), `valid` et `max_displacement` |
| `performance` | **probabiliste** | Intervalle conforme, avec `coverage`, `n_calibration` et `regime` (`"exchangeable"` ou `"selected"`, obligatoire : un fichier sans `regime` est refusé). `coverage` est **nominale** : elle n'est garantie que si `regime` vaut `"exchangeable"`. `null` en légalisation classique |
| `duals` | diagnostic | Paires `[label, cost]` : quelle contrainte relâcher, et ce qu'elle coûte |
| `manifest` | trace | Version, graine, empreintes : ce qui rend l'exécution rejouable |

`geometry` ne contient **aucun** champ de probabilité, et ne doit jamais en contenir.

## Exemple complet

Un appartement légalisé, produit par `Plan.to_json` (pas un exemple recopié à la main) :

```json
{
  "certificate": {
    "duals": [],
    "geometry": {
      "areas_ok": true,
      "gaps": false,
      "max_displacement": 0.21,
      "overlap": false,
      "structure_kept": true,
      "valid": true,
      "violations": []
    },
    "manifest": null,
    "performance": null
  },
  "openings": [
    {
      "head_height": 2.15,
      "id": "w1",
      "relative_width": 0.25,
      "s": 0.3,
      "sill_height": 1.0,
      "wall_id": "south"
    }
  ],
  "outline": [
    [
      0.0,
      0.0
    ],
    [
      6.0,
      0.0
    ],
    [
      6.0,
      3.5
    ],
    [
      0.0,
      3.5
    ]
  ],
  "rooms": [
    {
      "h": 3.5,
      "id": "living",
      "type": "living_room",
      "w": 4.0,
      "x": 0.0,
      "y": 0.0
    },
    {
      "h": 2.5,
      "id": "bath",
      "type": "bathroom",
      "w": 2.0,
      "x": 4.0,
      "y": 0.0
    }
  ],
  "schema": "2",
  "walls": [
    {
      "a": [
        0.0,
        0.0
      ],
      "b": [
        6.0,
        0.0
      ],
      "id": "south",
      "load_bearing": true,
      "thickness": 0.1
    }
  ]
}
```

> Le contour et les points sont écrits ici en listes imbriquées ; le vrai fichier met un
> nombre par ligne, ce qui rend les différences Git lisibles point par point.

## Lire le schéma v1

Un fichier du schéma v1 est lu par une mise à niveau explicite
(`archlux.io.json_io.upgrade_v1`), et l'écrivain n'émet jamais que du v2 : charger puis
enregistrer un fichier v1 le convertit.

| v1 (français) | v2 |
|---|---|
| `contour`, `pieces`, `murs`, `ouvertures`, `certificat` | `outline`, `rooms`, `walls`, `openings`, `certificate` |
| `porteur`, `epaisseur` | `load_bearing`, `thickness` |
| `mur_id`, `largeur_rel`, `hauteur_allege`, `hauteur_linteau` | `wall_id`, `relative_width`, `sill_height`, `head_height` |
| `geometrie`, `duaux`, `manifeste` | `geometry`, `duals`, `manifest` |
| `valide`, `chevauchement`, `jours`, `surfaces_ok`, `structure_preservee`, `deplacement_max` | `valid`, `overlap`, `gaps`, `areas_ok`, `structure_kept`, `max_displacement` |
| `indicateur`, `valeur`, `borne_inf`, `borne_sup`, `couverture` | `indicator`, `value`, `lower`, `upper`, `coverage` |
| `horodatage`, `graine`, `empreinte_donnees`, `decoupage`, `environnement`, `parametres`, `modele`, `poids` | `timestamp`, `seed`, `data_fingerprint`, `split`, `environment`, `parameters`, `model`, `weights_fingerprint` |
| types de pièces `sejour`, `chambre`, `cuisine`, `sdb`, `wc`, `couloir` | `living_room`, `bedroom`, `kitchen`, `bathroom`, `toilet`, `corridor` |

Les types de pièces anglais s'appliquent aussi aux fichiers v1 : un type inconnu passe
inchangé.

## Compatibilité

Un fichier écrit par une version antérieure doit rester lisible par une version plus
récente. Tout changement incompatible incrémente `SCHEMA_VERSION` et fait l'objet d'une
entrée dans le CHANGELOG ; le format précédent est lu par une fonction de mise à niveau
jusqu'à ce qu'une version en annonce le retrait.
