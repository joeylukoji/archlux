# Export IFC / DXF et survie

**Code :** `export.to_ifc`, `export.to_dxf`, `export.survival_rate`.

## Énoncé

Un plan est **exportable** s'il ne présente aucune pathologie bloquante
(aréte nulle, sommets dupliqués, auto-intersection, solide non fermé,
chevauchement, dimension non positive).

Le **taux de survie** d'un échantillon de \(n\) plans est

\[
\hat p = \frac{k}{n},
\]

où \(k\) est le nombre d'exportables. L'intervalle de confiance est celui de
**Wilson** (pas l'approximation normale) :

\[
\frac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n}+\frac{z^2}{4n^2}}}{1+\frac{z^2}{n}}.
\]

Les bornes restent dans \([0,1]\) même pour de petits \(n\) ou \(\hat p\) extrême.

## Hypothèses

- Géométrie rectangulaire (pièces = boîtes) ; IFC4 SPF minimal sans `bim`.
- Extra ``archlux[bim]`` charge `ifcopenshell` si disponible (écriture reste SPF
  déterministe en CI).
- Le certificat éventuel est annexé en `Pset_Archlux` (texte), pas recalculé.

## Code

| Symbole | Fonction |
|---|---|
| diagnostic | `diagnostiquer` |
| IFC | `to_ifc` → `RapportExport` |
| DXF | `to_dxf` |
| Wilson | `intervalle_wilson` |
| survie | `survival_rate` |

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Publier \((\hat p, [lo, hi])\) Wilson | Intervalle normal (bornes négatives) |
| Refuser l'écriture si `validate=True` | Exporter un plan pathologique « en silence » |
| Annexer le rapport de certificat | Mélanger garantie exacte et performance dans l'IFC |

## Source

Wilson, E. B. (1927), *JASA* 22(158), 209-212 - [bibliographie](sources.md)
n° 18. Pourquoi pas l'intervalle de Wald : Brown, Cai & DasGupta (2001),
*Statistical Science* 16(2), n° 19. Protocole du dépôt : `MILESTONE-6.md` §4.
