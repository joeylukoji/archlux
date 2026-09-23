# Schéma JSON des plans — version `1`

Format d'échange lu et écrit par `Plan.from_json` et `Plan.to_json`. Unités : **mètres**,
mètres carrés, degrés d'azimut. Origine au coin bas-gauche du contour, axe `y` vers le
nord géographique.

## Règles du format

- **La version est obligatoire.** Un fichier dont `schema` n'est pas `"1"` est refusé par
  `InvariantViole` : mieux vaut refuser bruyamment que deviner le format, car un plan mal
  relu produit un certificat faux.
- **L'écriture est déterministe.** Clés triées, UTF-8, indentation 2, fin de ligne `\n`.
  Deux écritures du même plan donnent les mêmes octets — sans quoi l'empreinte inscrite
  dans un manifeste n'identifie plus rien.
- **Aucune position absolue d'ouverture.** Une baie est décrite par `mur_id`, `s` et
  `largeur_rel` ; sa position se dérive du mur. C'est l'invariant qui empêche fenêtres et
  cloisons de se désynchroniser quand le solveur déplace un mur.
- **`null` explicite plutôt que clé absente.** `"performance": null` signifie « aucune
  garantie de performance affirmée » — une information, pas un oubli.
- **Les plages sont vérifiées à la lecture.** `s ∈ [0, 1]`, `largeur_rel ∈ ]0, 1]`,
  dimensions et épaisseurs strictement positives, et **aucune valeur non finie** —
  `json.loads` accepte pourtant les littéraux `NaN` et `Infinity`. Un fichier fautif est
  refusé avec **la liste complète** de ses violations, pas seulement la première.

## Champs

| Champ | Type | Sens |
|---|---|---|
| `schema` | `"1"` | Version du format. Refusée si différente |
| `contour` | liste de `[x, y]` | Enveloppe du logement |
| `pieces[]` | `id`, `type`, `x`, `y`, `w`, `h` | Rectangle, coin bas-gauche en `(x, y)` |
| `murs[]` | `id`, `a`, `b`, `porteur`, `epaisseur` | Segment ; `porteur: true` = figé par le solveur |
| `ouvertures[]` | `id`, `mur_id`, `s`, `largeur_rel`, `hauteur_allege`, `hauteur_linteau` | `s` = abscisse **du centre** le long du mur, dans `[0, 1]` ; `largeur_rel` en fraction de la longueur du mur |
| `certificat` | objet ou `null` | `null` pour un plan proposé ; toujours présent sur un plan légalisé |

### Le certificat

Deux garanties de natures différentes, séparées par construction — voir
[Les deux garanties](../concepts/deux-garanties.md).

| Champ | Nature | Sens |
|---|---|---|
| `geometrie` | **exacte** | Les quatre prédicats vérifiés indépendamment du solveur, et `deplacement_max` |
| `performance` | **probabiliste** | Intervalle conforme, avec `couverture` et `n_calibration`. `null` en légalisation classique |
| `duaux` | diagnostic | Paires `[libellé, coût]` : quelle contrainte relâcher, et ce qu'elle coûte |
| `manifeste` | trace | Version, graine, empreintes — ce qui rend l'exécution rejouable |

`geometrie` ne contient **aucun** champ de probabilité, et ne doit jamais en contenir.

## Exemple complet

Un T2 légalisé, produit par `Plan.to_json` — ce n'est pas un exemple recopié à la main :

```json
{
  "certificat": {
    "duaux": [],
    "geometrie": {
      "chevauchement": false,
      "deplacement_max": 0.21,
      "jours": false,
      "structure_preservee": true,
      "surfaces_ok": true,
      "valide": true,
      "violations": []
    },
    "manifeste": null,
    "performance": null
  },
  "contour": [[0.0, 0.0], [6.0, 0.0], [6.0, 3.5], [0.0, 3.5]],
  "murs": [
    {
      "a": [0.0, 0.0],
      "b": [6.0, 0.0],
      "epaisseur": 0.1,
      "id": "m_sud",
      "porteur": true
    }
  ],
  "ouvertures": [
    {
      "hauteur_allege": 1.0,
      "hauteur_linteau": 2.15,
      "id": "f1",
      "largeur_rel": 0.25,
      "mur_id": "m_sud",
      "s": 0.3
    }
  ],
  "pieces": [
    { "h": 3.5, "id": "sejour", "type": "sejour", "w": 4.0, "x": 0.0, "y": 0.0 },
    { "h": 2.5, "id": "sdb", "type": "sdb", "w": 2.0, "x": 4.0, "y": 0.0 }
  ],
  "schema": "1"
}
```

> Le contour et les points sont écrits en listes imbriquées ; l'exemple ci-dessus est
> reformaté sur une ligne par point pour la lisibilité. Le fichier réellement produit
> place un nombre par ligne, ce qui rend les différences Git lisibles point par point.

## Compatibilité

Un plan écrit par `0.1.x` doit rester lisible par `0.2.x`. Tout changement incompatible
incrémente `VERSION_SCHEMA` et fait l'objet d'une entrée au
[CHANGELOG](https://keepachangelog.com/fr/1.1.0/).
