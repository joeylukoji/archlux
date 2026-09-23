# DOCUMENTATION — conventions et obligations

> Contexte pour agents de code. **À lire avec `ARCHITECTURE.md`.**
> La documentation fait partie de la définition de « terminé ». Une fonction publique
> non documentée est une fonction non terminée.

---

## 1. Principe

**On écrit la documentation dans l'ordre inverse de l'envie.**

| Priorité | Niveau | Pourquoi |
|:--:|---|---|
| **1** | **Galerie d'exemples** | Premier facteur d'adoption. Un utilisateur regarde un exemple, se dit « c'est ce qu'il me faut », installe |
| 2 | Tutoriels | Parcours guidés pour les 3–4 usages principaux |
| 3 | Référence d'API | Nécessaire, mais personne ne l'ouvre pour découvrir un outil |

L'envie naturelle est d'écrire la référence d'abord parce qu'elle se génère automatiquement. **C'est l'ordre le moins utile.**

---

## 2. Structure

```
docs/
├── index.md                 # la phrase de positionnement + exemple 5 lignes
├── installation.md
├── galerie/                 # PRIORITÉ 1 — un fichier par exemple, autonome
│   ├── 01-corriger-un-plan.md
│   ├── 02-comparer-deux-methodes.md
│   ├── 03-detecter-une-infaisabilite.md
│   ├── 04-lire-un-certificat.md
│   └── 05-diagnostic-dual.md
├── tutoriels/
│   ├── premiers-pas.md
│   ├── legalisation-performantielle.md
│   └── calibrer-un-substitut.md
├── concepts/                # le POURQUOI, pas le comment
│   ├── deux-garanties.md
│   ├── polytope.md
│   ├── oracle-partage.md
│   └── prediction-conforme.md
├── formules/                # énoncé, dérivation, source, cas d'usage (jalon 2+)
│   ├── index.md
│   └── sources.md
├── reference/               # généré depuis les docstrings
└── limites.md               # ce que le système NE fait PAS
```

**`concepts/deux-garanties.md` est la page la plus importante du site.** Elle explique
qu'un certificat porte une preuve et une prédiction, de natures logiquement différentes.
Tout le reste en découle.

**`limites.md` est obligatoire, pas optionnel.** Un système qui produit des chiffres
réglementaires doit dire explicitement ce qu'il ne vérifie pas.

---

## 3. Docstrings — le gabarit obligatoire

Style **NumPy**. Toute fonction publique doit avoir les sections marquées ✱.

```python
def legalize(plan: Plan, ctx: Contexte, *, objective=None,
             budget: float | None = None) -> Plan:
    """Corrige un plan vers le plan valide le plus proche.          ✱ résumé 1 ligne

    Avec ``objective=None``, minimise le déplacement des murs        ✱ description
    (légalisation classique). Avec un objectif, maximise celui-ci
    sous contrainte de validité et de budget de déplacement.

    Parameters                                                       ✱
    ----------
    plan : Plan
        Plan proposé, éventuellement invalide.
    ctx : Contexte
        Structure porteuse, orientation, contour, référentiel.
    objective : Substitut | None, optional
        Objectif à maximiser. ``None`` = proximité géométrique.
    budget : float | None, optional
        Déplacement maximal autorisé, en mètres.

    Returns                                                          ✱
    -------
    Plan
        Plan valide portant son ``certificat``.

    Raises                                                           ✱
    ------
    Infaisable
        Le programme ne tient pas dans l'enveloppe. L'exception porte
        ``certificat`` : les contraintes en conflit.
    InvariantViole
        Le solveur a produit une sortie invalide (bogue interne).

    Guarantees                                                       ✱ SPÉCIFIQUE PROJET
    ----------
    - Géométrique : **exacte**. ``resultat.certificat.geometrie.valide``
      est vérifié indépendamment du solveur avant retour.
    - Performance : **probabiliste** si ``objective`` est fourni.
      Couverture ≥ 1−α, sous hypothèse d'échangeabilité avec le jeu
      de calibration.

    Complexity                                                       ✱ SPÉCIFIQUE PROJET
    ----------
    O(n²) contraintes, un appel LP. ~15 ms pour n=15 pièces.

    Examples                                                         ✱
    --------
    >>> plan = Plan.from_json("propose.json")
    >>> q = legalize(plan, ctx)
    >>> q.certificat.geometrie.valide
    True
    """
```

### Les deux sections propres à ce projet

**`Guarantees`** — obligatoire sur toute fonction qui rend un `Plan` ou un `Certificat`.
Elle dit **de quelle nature** est chaque garantie. C'est la thèse du projet inscrite
dans la documentation, au même titre que dans les types.

**`Complexity`** — obligatoire sur `geom`, `lmo`, `solve`. Le projet vend de la vitesse ;
elle doit être documentée, pas supposée.

---

## 4. Règles de rédaction

- [ ] Une fonction publique sans docstring = **échec CI**
- [ ] Le résumé tient sur **une ligne**, à l'impératif ou à l'indicatif présent
- [ ] Tout `raise` documenté dans `Raises`
- [ ] Tout paramètre `seed` documenté avec sa portée exacte
- [ ] Tout exemple est un **doctest exécutable**, pas du pseudo-code
- [ ] Les fonctions privées (`_nom`) : une ligne suffit
- [ ] **Jamais** de garantie affirmée sans dire de quelle nature elle est

---

## 5. Galerie — le gabarit d'un exemple

Chaque fichier de `docs/galerie/` est **autonome** et tient sur un écran.

````markdown
# Corriger un plan généré

**Problème.** Le modèle a produit un plan où deux cloisons se chevauchent de 3 cm
et où la salle de bains fait 4,6 m² au lieu des 5 m² réglementaires.

**Solution.**

```python
import archlux as ax

plan = ax.Plan.from_json("sortie_generateur.json")
ctx  = ax.Contexte(structure=..., orientation=ax.Orientation(deg=12), ...)

q = ax.legalize(plan, ctx)
print(q.certificat.rapport())
```

**Résultat.**

```
GEOMETRIE                                       [EXACT]
  Chevauchement          aucun         verifie
  Surfaces minimales     6/6           verifie
  Deplacement maximal    0,21 m
```

**Ce qu'il faut retenir.** La disposition proposée est conservée ; seules les
dimensions sont ajustées. Déplacement maximal : 21 cm.

**Voir aussi :** [Lire un certificat](04-lire-un-certificat.md)
````

**Structure imposée :** Problème → Solution → Résultat → Ce qu'il faut retenir → Voir aussi.
Un exemple qui n'énonce pas d'abord un problème concret ne sert à rien.

---

## 6. Vérification automatique

```yaml
# .github/workflows/ci.yml — extrait
- run: uv run pytest --doctest-modules src/archlux    # les exemples s'exécutent
- run: uv run ruff check --select D src/              # pydocstyle
- run: uv run interrogate -f 95 src/archlux           # couverture docstrings
- run: uv run mkdocs build --strict                   # liens morts = échec
```

- [ ] Les doctests s'exécutent en CI — un exemple faux casse la construction
- [ ] Couverture de docstrings ≥ 95 % sur `src/`
- [ ] `mkdocs build --strict` : tout lien mort échoue
- [ ] Vérifier que la galerie tourne sur un plan réel, pas fictif

---

## 7. Ce qui se documente à chaque jalon

| Jalon | Documentation à produire |
|---|---|
| 1 | `README.md`, `installation.md`, schéma JSON |
| **2** | **Galerie 01 et 03, `concepts/polytope.md`, `formules/`, docstrings `geom`/`lmo`/`certify`** |
| 3 | Galerie 02, `concepts/oracle-partage.md`, tutoriel légalisation performantielle |
| 4 | Tutoriel substitut, doc du protocole `Substitut`, **doc de `valider_gradient`** |
| 5 | Galerie 04 et 05, `concepts/deux-garanties.md`, `concepts/prediction-conforme.md` |
| 6 | `limites.md`, guide de contribution, notes de version 1.0 |

**Règle : la documentation d'un jalon est écrite pendant le jalon, pas après.**
Un jalon dont la doc manque n'est pas terminé.

---

## 8. CHANGELOG

Format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnement sémantique.

```markdown
## [0.2.0] — 2026-11-14

### Ajouté
- `light.SubstitutAnalytique` : modèle de lumière en formes fermées, sans apprentissage.
- `solve.frank_wolfe` avec pas d'écartement.

### Modifié
- `lmo.resoudre` accepte `depart=` pour le démarrage à chaud (×3 sur le temps).

### Corrigé
- Les coupes de surface pouvaient s'accumuler sans borne (#42).
```

**Règle propre au projet :** tout changement de comportement de l'oracle ou du
certificat est une **version majeure**. Un certificat produit en `1.2.0` doit rester
reproductible en `1.2.x`.

---

## 9. Anti-patterns

| Anti-pattern | Pourquoi |
|---|---|
| Écrire la référence d'API en premier | Ordre le moins utile pour l'adoption |
| Exemples en pseudo-code | Ils pourrissent sans que personne ne s'en aperçoive |
| Garantie affirmée sans sa nature | Confond preuve et prédiction — faute centrale du projet |
| Documentation reportée « à la fin » | Elle est alors écrite dans l'urgence et ne sert personne |
| Pas de page `limites.md` | Un outil réglementaire qui ne dit pas ce qu'il ne vérifie pas est dangereux |
| Doctests non exécutés en CI | Ils deviennent faux en trois semaines |
| Exemples sur des plans fictifs | Ne prouvent rien, et cachent les cas réels difficiles |
