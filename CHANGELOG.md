# Journal des modifications

Format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnement semantique.

> Regle propre au projet : tout changement de comportement de l'oracle (`lmo`) ou du
> certificat (`certify`) est une **version majeure**. Un certificat produit en `1.2.0`
> doit rester reproductible en `1.2.x`.

## [Non publie]

### Remediation — PLAN.md phase 1 (in progress)

#### Fixed — load-bearing walls (batch 1.1, certificate behaviour change)
- **The structure predicate verified nothing.** It compared each load-bearing wall with
  itself; walls are not decision variables, so it was always true and a room could
  cross a load-bearing wall under a certificate reading "structure preserved: yes"
  (benchmark baseline: 35 false certificates out of 200 in performance mode).
  `certify.preuve` now rejects any room whose interior contains a stretch of a
  load-bearing wall, oblique walls included.
- **The solver now keeps every room on its side of every load-bearing wall**, treated
  as a fixed obstacle: `deduire_ordre(plan, structure=...)` reads the side from the
  proposed plan (`OrdreRelatif.porteurs`, `WallSide`) and `construire_polytope` adds one
  linear row per room and wall. Classic, tiling and performance modes all inherit it.
- A plan no longer has to repeat the structure in `plan.murs`; a declared wall of the
  same id must still match it.
- After review: the side kept is the half-plane the room penetrates **least** among
  those with room before the outline. A room overflowing the end of a partial wall by
  1 cm is moved 1 cm past the end, no longer sent across the wall (false refusals:
  7 of 200 in the partial-wall benchmark mode). Zero-length walls are ignored and
  nearly axis-aligned walls (noise below 1e-7 m) are accepted.
- `export.svg.rendre/comparer/planche` take `walls=` to draw the load-bearing structure
  even when the plan does not repeat it.

#### Fixed — minimum areas in performance mode (batch 1.2)
- **Frank-Wolfe went below minimum areas.** It mixed a valid start with vertices of an
  *outer* approximation of `w h >= a` (tangent cuts), so iterates could break the
  minimum; `legalize` then raised `InvariantViole` (benchmark: 167 of 200 in
  performance mode). It now works on an **inner** polyhedral approximation
  (`lmo.coupes.inner_area_constraints`: chords of the hyperbola around the start),
  included in `{w h >= a}`: every iterate keeps every minimum area. Nodes follow
  1.1^k, k = -24..24 (width 0.10 to 9.85 times the start), so each chord asks for at
  most (r-1)^2/(4r) = 0.23 % of extra area. Against a 235-node reference grid on the
  200 benchmark scenarios: median 0.9985 of the reference gain, >= 0.95 of it in 96 %
  of scenarios, +4 ms median.
- After review: nodes are no longer filtered by the variable bounds, which froze the
  width of a room whose height a contact had fixed (no gain in 7 of 120 scenarios); a
  start below a minimum area by more than the proof tolerance is refused.
- Frank-Wolfe no longer needs tangent cuts, which disabled the LP warm start.
- New performance budget with tight minimum areas (15 rooms: about 50 ms of 500), and a
  scaling test at 15, 50 and 100 rooms (all used to raise `InvariantViole`).
- Property test: every Frank-Wolfe iterate passes the independent checker.
- `api._coupes_surface_plan` removed: no longer needed. The tangent-cut path of
  `frank_wolfe` has no caller left and is documented as legacy.

#### Fixed — Frank-Wolfe reports what it achieved (batch 1.4)
- The gap started at 0, so a run whose first LP failed read as "optimum reached"; it
  now starts at infinity.
- On a run ending at `max_iter`, the gap described the previous point; it is now
  computed at the returned point (one extra LP, which also gives the duals).
- New `FrankWolfeResult.status` and `Trace.status`: `converged`, `line_search_failed`,
  `lp_not_optimal` or `max_iter`. `iterations` counts iterations, not the initial entry.
- The gap is documented as a stationarity measure: no shipped surrogate is concave, so
  it never bounds the distance to the optimum.
- **The displacement budget was spent twice**: the Frank-Wolfe box was centred on the
  L1 point, so the total move from the proposal reached up to twice the budget
  (measured: 0.55 m for 0.3 m). It is now centred on the proposed plan
  (`solve.frank_wolfe.restrict_to_budget`), and `verifier_exactement(..., budget=)`
  makes a plan moved beyond it invalid; `legalize` passes the budget to the proof.
- The certification budget of ARCHITECTURE.md §9 (5 ms, 15 rooms) is measured at last:
  about 1.5 ms.

#### Changed — `solve` migrated to English (track E, batch E9; no behaviour change)
- `ResultatFW` -> `FrankWolfeResult` (`valeur` -> `value`, `duaux` -> `duals`);
  `frank_wolfe(poly, surrogate, orientation, start, ..., cuts=, rooms=, glazing=)`;
  `Iteration` fields `value`, `step`, `lp_ms`, `n_cuts`; `Trace.iterates`, `gaps`,
  `values`, `total_lp_ms`. The French names of `Trace` (reachable through
  `Plan.trace`) remain as deprecated aliases until 1.0.0. Outputs are byte-for-byte
  identical (SHA-256 over 200 Frank-Wolfe runs and all their iterates).

#### Fixed — `Daylight` objective (batch 1.3)
- `legalize(objective=Daylight(...))` raised `TypeError`: `Daylight` did not accept the
  `baies` keyword of the `Substitut` protocol, which Frank-Wolfe always passes, yet
  `isinstance(..., Substitut)` was true (it only checks method names). `Daylight` now
  accepts and forwards `baies` in `evaluer`, `gradient`, `incertitude`, `__call__` and
  the finite-difference gradient of the uncertainty; it is also frozen, like every
  type. A conformance test compares the signatures of all five surrogates with the
  protocol. Benchmark: 200 crashes out of 200 before.

#### Added
- `export.svg` draws walls: load-bearing walls thick and dark (class
  `wall-load-bearing`), other walls thin and grey (class `wall`). A room crossing a
  load-bearing wall is now visible. First tests of `export.svg` (it had none).
- `UnsupportedInput` (`ArchluxError`): raised for an oblique load-bearing wall instead of
  ignoring it.
- `tests/test_hygiene.py`: no invisible control character in tracked text files.
- `benchmarks/guarantees/`: a before/after benchmark of the exact guarantees, measured by
  the independent checker of `tests/checkers.py` on 200 deterministic scenarios and five
  modes; it counts false certificates (plans certified valid that break a guarantee).

### Remediation — PLAN.md phase 0 (new entries are written in English)

#### Changed
- **Development version `0.10.0.dev0`.** `1.0.0` (never published) is withdrawn: it
  promised a stable, usable API while the README quick start did not run and the
  performance mode failed on realistic plans (see `AUDIT.md`). `0.9.0` is not reused
  either, since it already names an earlier state. 1.0.0 will be tagged at the end of
  PLAN.md phase 5.
- **Single source of truth for the version**: `src/archlux/_version.py`, read by hatch
  (`dynamic = ["version"]`). The certificate header used installed metadata and could
  print a stale `0.0.0`; it now prints the source version.
- **English-first project** (ADR 0001, `docs/glossary.md`): new code is English; the
  existing French code is migrated batch by batch.

#### Fixed
- `export.ifc` and `bench.manifeste` imported the root package, which loaded the whole
  legalization chain; they now import `archlux._version`.
- `tests/test_dependances.py` ignored `from archlux import ...`; it now rejects it,
  rejects relative imports, and checks that the leaf modules import nothing.
- Seven `docs/donnees/` pages were never versioned (an unanchored ignore pattern);
  `mkdocs build --strict` failed on a clean checkout.
- Budget tests crashed under `--benchmark-disable`; an unmeasured budget is now skipped.

#### Added
- `LICENSE` (Apache-2.0), `.gitattributes` (LF), git history, pre-commit hooks.
- CI: `ruff format --check`, pre-commit hooks, coverage ratchet (84 %); ruff and
  hypothesis versions pinned.
- `archlux/tolerances.py`: registry of the numerical tolerances in use (usages are
  migrated in phase 1.5).
- Tests that execute the user-facing documentation examples (6 pages broken today,
  recorded as strict xfails).
- Property tests under realistic contexts (load-bearing wall, tight minimum areas)
  with an independent checker. They reproduce three audit defects, recorded as strict
  xfails: performance mode goes below minimum areas, crosses load-bearing walls
  unnoticed, and rejects `Daylight`.
- A strict xfail pinning an inconsistency found while building the registry: the
  cutting-plane loop tolerates 1e-6 m² under a minimum area, the proof only 1e-9 m².
- Language check on files already migrated to English.

### RUPTURE — le protocole `Substitut` recoit les baies

`evaluer`, `gradient` et `incertitude` prennent un argument **nomme et optionnel**
`baies: Baies | None = None`. Toute implementation tierce doit l'accepter : c'est une
rupture de contrat public, donc une **version 2.0** au sens de la regle du projet.

**Pourquoi.** Le vecteur de decision ne porte que `(x, y, w, h)` par piece. Il ne dit
rien des ouvertures — or ce sont elles qui determinent l'eclairement. Mesure sur 369
appartements suisses, cible = irradiance simulee par lancer de rayons, decoupage par
site : analytique `R2 = -0,000`, perceptron `R2 = -0,557`. Au niveau, ou sous, la
simple moyenne. Ce n'etait pas un defaut de capacite mais **un defaut d'entree** : le
tokeniseur produisait deja des jetons de baie que le protocole ne laissait pas passer.

`Baies` est volontairement pauvre — murs et ouvertures relatives — et **invariante
pendant l'optimisation** : seules les cloisons bougent sous Frank-Wolfe, les baies
suivent sans synchronisation. Elle se construit une fois et se transmet inchangee.

`None` signifie « information absente » : l'implementation se rabat sur son hypothese
par defaut, exactement comme avant. `SubstitutAnalytique` et `SimulateurExact`
l'ignorent d'ailleurs — leur WWR est une constante du modele.

### Ajoute

- `light.protocole.Baies`.
- `light.jetons.vecteur_vers_jetons(x, orientation, baies)` : les jetons de baie,
  jusqu'ici produits par `plan_vers_jetons` seulement, sont desormais accessibles
  depuis un vecteur de decision.
- `light.base.descripteurs(x, orientation, baies)` : six descripteurs de fenestration
  en fin de vecteur (82 -> 88 composantes). Les 82 premieres sont **inchangees**, et
  les six dernieres sont nulles sans baies : un modele entraine sans reste lisible.
- `SubstitutDense.ajuster(..., baies=...)`.
- `api.legalize` construit les `Baies` du plan corrige et les transmet a Frank-Wolfe.
- `data.chargeurs` : `charger_etiquettes_sd`, `etiqueter`, `decouper_par_site`,
  `COLONNE_SOLEIL_DEFAUT`. `AppartementMSD` porte `site_id` et `aires_sources`.
- `experiences/j7_sd_etiquettes.py`, `resultats/j7_sd_etiquettes.md`.

### Corrige

- `light.base.SubstitutDense` apprenait le residu a l'analytique **en supposant les
  deux a la meme echelle**. Vrai contre `SimulateurExact`, construit sur la meme base ;
  faux contre une simulation reelle, ou l'analytique rend ~300 en unites arbitraires
  quand la cible vaut ~0,7. Le reseau depensait sa capacite a annuler une constante.
  Recalage affine `y ~= a.f(x) + b` ajuste par moindres carres sur le train, persiste
  dans le `npz`. Des poids anterieurs se relisent avec `a = 1, b = 0`, comportement
  inchange. **MAE sur donnees reelles : 1810 -> 0,367.**

### Mesure — substitut contre simulations reelles

Cible `sun_201803211200_mean` (Swiss Dwellings v3.0.0, CC BY 4.0), moyenne ponderee
par surface. Decoupage **par site** — 133 / 44 / 45 sites disjoints, jamais par
appartement : deux logements d'un meme site partagent masque urbain et orientation.

| modele | MAE | MAE relative | R2 |
|---|--:|--:|--:|
| constante (moyenne du train) | 0,267 | 39,5 % | 0,000 |
| analytique recale | 0,268 | 39,6 % | **-0,000** |
| perceptron sans baies | 0,353 | 52,2 % | -0,557 |
| perceptron **avec baies** | 0,307 | 45,4 % | **-0,220** |

Conforme a alpha = 0,10 : **couverture mesuree 90,2 %** pour 90 % vises, largeur
moyenne 1,534, n_calibration 426.

Trois lectures. **L'analytique n'a aucun pouvoir predictif** : la pente du recalage
tombe a -0,0000, les moindres carres l'ecrasent en constante. La regle de profondeur
CIBSE et la table a huit secteurs n'expliquent rien de l'irradiance simulee.

**Les baies comblent 60 % de l'ecart** (R2 -0,557 -> -0,220) sans qu'aucun autre
parametre change : meme modele, memes hyperparametres, meme graine. L'entree etait
bien le goulot. Elle ne suffit pas : le masque urbain, que Swiss Dwellings simule et
qu'`archlux` ne represente pas, reste absent.

**La garantie conforme tient** — 90,2 % pour 90 % — et le dit honnetement par la
largeur : 1,534 pour une cible de moyenne 0,677, soit un intervalle 2,3 fois la
valeur. Quand le substitut ne sait rien, la borne le declare au lieu de pretendre.
C'est la validation empirique de la these du projet, obtenue par la negative.

### Limites

Une colonne sur 126, 2 000 appartements parcourus, une irradiance a instant fixe qui
**n'est pas un sDA**. Le champ `indicateur` doit se lire comme le nom de la cible
apprise, jamais comme la metrique IES.


### Ajoute — contrainte de pavage exact (jalon 7)

`geom.pavage` et `legalize(..., pavage=True)`. Defaut `False` : contrat 1.x inchange.

**Le probleme.** Les separations du polytope sont des inegalites : elles interdisent
le chevauchement, jamais le trou. Un plan troue est deja le point le plus proche de
lui-meme, donc l'optimum L1 le laisse tel quel et `certify.preuve` le rejette.
Mesure : 68,1 % de chevauchements repares contre **9,8 % de jours**.

**Le resultat.** Dans une dissection rectangulaire, tout bord est porte par une
ligne de trame ; la piece i s'ecrit `[v_l, v_r] x [h_b, h_t]` et couvre les cellules
`l <= a < r`, `b <= B < t`. **La condition de pavage ne porte que sur les indices**,
jamais sur les coordonnees : si ces familles partitionnent les cellules interieures
au contour, alors toute suite croissante de lignes donne un pavage exact. Il suffit
donc d'imposer « ces bords partagent une ligne » — des egalites affines dans les
variables existantes. Un jour cesse d'etre representable.

Deux proprietes en decoulent : le systeme **reste faisable** (les positions de trame
de reference sont toujours admissibles ; aucun LP infaisable observe), et la garantie
est structurelle, pas numerique.

**Recuperer la trame d'un plan fautif** se fait par le **support** d'une ligne — le
nombre de bords qu'elle porte — et non par une tolerance metrique, qui echoue dans
les deux sens (3,8 % de reparation). Une ligne orpheline est resorbee dans sa voisine,
sauf si cela ecrase une piece. Aucun seuil en metres : un jour de 2 m se rattrape
comme un jour de 5 cm, une cloison de 40 cm survit.

Fiche : `docs/formules/pavage.md`. Sources : Otten (1982), Lengauer (1990) ch. 10.

### Mesure — 3 597 corruptions de 300 appartements MSD reels

| Faute | `legalize` | `pavage=True` | repli |
|---|--:|--:|--:|
| jour | 10,0 % | 97,6 % | **98,0 %** |
| sous-dimension | 4,8 % | 96,0 % | **96,3 %** |
| chevauchement | 68,2 % | 90,3 % | **91,2 %** |
| decalage | 60,8 % | 88,1 % | **90,0 %** |
| **toutes** | **35,9 %** | 93,0 % | **93,9 %** [93,2 - 94,5] |

0,0 % de plans valides avant correction. Temps median 6,5 ms, sous le budget §9.
Par amplitude : 96,8 % a 10 cm, 96,9 % a 25 cm, 93,2 % a 50 cm, 88,6 % a 1 m.

**Reparation bornee de la partition.** Apres resorption des lignes orphelines, il
subsiste des defauts locaux — une cellule vide ou doublement couverte, cas dominant
sur MSD. On agrandit ou retrecit une piece **d'un cran**, ce qui la laisse
rectangulaire par construction, et seulement si les cellules concernees sont toutes
manquantes ou toutes en exces. Le budget (defaut 4) distingue la reparation de la
reconstruction ; il sature a 4 (recuperation de trame : 77,8 % a budget 0, 98,5 % a
2, 99,2 % a 4 et 8).

Consequence semantique documentee : fermer un jour, c'est agrandir quelqu'un. La
reparation peut **absorber une piece manquante dans sa voisine**, et le plan sort
avec une piece de moins que prevu. `budget_reparation=0` verifie sans retoucher.

### Corrige

- `geom.pavage._consolider` : la ligne voisine la plus proche pouvant se trouver de
  l'autre cote du bord deplace, tester l'egalite des indices ne suffisait pas. Une
  piece pouvait ressortir avec ses bords **inverses** (`gauche > droite`) et passer
  silencieusement en LP. Ordre strict exige, plus un filet final sur les incidences.
  Trouve par le test de propriete « toute trame rendue est une partition valide ».

### Ajoute — modele de corruption

`data.corruption.corrompre` : quatre familles de fautes (`deplacer`, `elargir`,
`retrecir`, `aplatir`), graine obligatoire, amplitude **reellement appliquee**
rapportee comme verite terrain. Ces perturbations ne modelisent aucun generateur
particulier : elles reproduisent les familles de fautes de la litterature sans en
calibrer les frequences, et doivent etre completees par un generateur public.


### Ajoute — corpus reel (jalon 7)

- `data.chargeurs.charger_msd` : CSV MSD (WKT) -> `Plan` + `Contexte`. Redressement
  par direction dominante, calage sur les axes, recollage sur trame commune,
  decomposition rectilineaire, baies projetees en relatif. Retention mesuree
  32,1 % sur MSD, mediane 10 sous-rectangles.
- `orient.circulaire.direction_dominante` : moyenne directionnelle d'ordre *p*
  pour donnees axiales (Mardia & Jupp §2.3.3), ponderee par les longueurs. Une
  moyenne circulaire ordinaire annule les axes a 90 deg les uns des autres.
- `geom.rectilineaire.MAX_RECTANGLES` et `decomposer(..., max_rectangles=)` :
  le plafond de 4 sous-rectangles devient un parametre. Defaut inchange.
- `ARCHITECTURE.md` §5 : `data` peut lire `geom` et `orient` (chargeurs de corpus
  uniquement), jamais `lmo`, `solve` ni `light`. Aucun cycle : `geom` et `orient`
  n'importent pas `data`.
- `uq.conforme.n_minimal_conforme(alpha)` : plus petite taille de calibration
  admissible, `n >= ceil(1/alpha) - 1`, soit 9 a 90 % et 19 a 95 %. Remplace un
  seuil `>= 8` code en dur qui echouait systematiquement au premier cycle.
- `active.boucle.Loop.run(..., calibration=)` : jeu de calibration **independant**.
  A defaut, `part_calibration` reserve une fraction des points acquis, qui n'entre
  jamais dans `ajuster`. `RapportActif.calibration_independante` dit si la
  couverture est publiable. Corrige l'anti-pattern §10 commis par le module.
- `experiences/j7_msd_idempotence.py` et `resultats/j7_msd_idempotence.md`.

### Corrige

- `geom.rectilineaire._coupe_verticale` : GEOS rend l'intersection en morceaux
  colineaires (arete de bord et corde interieure, jointives au sommet reflexe).
  Le premier morceau etait retenu, c'est-a-dire une arete du polygone, qui ne
  separe rien. **1 219 pieces MSD sur 4 456** echouaient sur ce seul defaut.
  Les morceaux touchant le pivot sont desormais reunis.
- `geom.rectilineaire._decouper` : repli sur coupe horizontale quand aucune
  verticale ne separe (U couche, T couche, Z). La convention verticale garde la
  priorite, donc les decompositions anterieures sont inchangees.
  **Taux de decomposition sur MSD : 44,8 % -> 80,8 %.**

### Mesure

Sur 400 appartements MSD reels (mediane 10 sous-rectangles, max 15) :
398/400 valides avant `legalize`, **400/400 apres**, 0 echec, deplacement maximal
median **0,000000 m** (idempotence), 7,1 ms median et 10,7 ms au p90 — sous le
budget de 20 ms du §9, sur geometrie reelle.

### Piege documente

`Referentiel.largeur_min` vaut 1,80 m par defaut et s'applique a **chaque
sous-rectangle**, y compris aux bandes issues d'une decomposition en L — or un
sous-rectangle est un artefact de decoupe, pas une piece. Herite en silence sur un
corpus sans reglementation, il fait sortir le plan de son propre polytope :
`legalize` elargit les bandes, le pavage se dechire, `certify.preuve` rejette pour
« jour ». Mesure : **87 % d'echecs avec le defaut, 0 % avec `largeur_min=0`**.
`charger_msd` neutralise donc le seuil par defaut.


Passe de revue et refactor (agents `review-and-refactor`), documentation technique et
mathematique mise a jour.

### Corrige (comportement du certificat)

> **Ces trois points changent ce que `certify` affirme.** Au sens de la regle du
> projet, la publication qui les embarque est une **version majeure** : un certificat
> emis avant ces correctifs n'est pas comparable a un certificat emis apres.

- `certify.preuve` : `_jours` comparait `aire(union) == aire(contour)`. L'egalite des
  aires est **necessaire mais pas suffisante** : un trou interieur de *a* m2 compense
  par une piece de *a* m2 situee entierement hors du contour laissait les aires egales
  et le test de chevauchement vide. Une piece flottant a 8 m du batiment etait
  certifiee `[EXACT]` valide. Les deux differences ensemblistes sont desormais testees
  separement (`aire non couverte`, `debord hors contour`).
- `uq.conforme` : `borner` et `CalibrateurConforme.borne` acceptaient une incertitude
  nulle ou negative, publiant un intervalle de largeur nulle assorti d'une couverture
  de 90 %, ou un intervalle inverse (`borne_inf > borne_sup`). Refuse desormais par
  `InvariantViole`.
- `lmo.solveur` : `_certificat_farkas` lisait les duaux du probleme auxiliaire sans
  verifier son statut. Quand l'infaisabilite venait des bornes ou de `A_eq`, un vecteur
  sans signification etait presente comme certificat de Farkas. Rend un vecteur nul.

### Corrige (autres)

- `geom.polytope` : une enveloppe plus etroite que `referentiel.largeur_min` produisait
  des bornes inversees, donc `InvariantViole` (« bogue interne ») au lieu d'`Infaisable`
  avec ses origines lisibles.
- `export.wilson` : en `p = 0` / `p = 1`, l'arrondi flottant sortait des bornes hors de
  `[0, taux]` (24 cas pour n <= 60). Extremites posees exactement.
- `export.ifc` : trois ecarts au schema IFC4, dont `IfcSpace` place dans
  `IfcRelContainedInSpatialStructure` (interdit) et des murs rattaches a aucune
  structure spatiale. Le champ `moteur` n'annonce plus `ifcopenshell` quand aucune ligne
  n'en provient (nouveau champ `ifcopenshell_disponible`).
- `light.base` : `sauver()` calculait l'empreinte d'un chemin sans suffixe alors que
  `numpy.savez` ecrit `.npz` — `FileNotFoundError` sur le chemin de reproductibilite.
  `assert` d'invariant remplace par `InvariantViole` (§7).
- `io.json_io`, `data.synthese`, `data.dedup`, `bench.protocole` : quatre exceptions
  nues (`UnicodeDecodeError`, `IndexError`, `ValueError`) et une mesure fabriquee sur
  corpus vide, toutes hors du contrat d'erreurs §7.
- `bench.rapport` : 199 replications bootstrap ecrasaient le defaut de 9 999 ; l'erreur
  Monte-Carlo dominait la largeur publiee. Porte a 2 000.
- `active.boucle.Loop` : `seed` avait une valeur par defaut, en violation du §7.

### Ajoute

- `light.analytique.facteur_secteur` et `light.analytique.FACTEURS_SECTEUR` : la table
  a 8 secteurs devient une fonction de module (elle etait atteinte depuis `simulateur`
  en construisant une instance jetable pour appeler une methode privee). L'alias
  `SubstitutAnalytique.FACTEURS_SECTEUR` est conserve : contrat public inchange.
- `bench.stats.holm` : correction de Holm-Bonferroni (FWER, sans hypothese
  d'independance). **Pas encore branchee** dans le pipeline de table.
- `uq.fiabilite.diagramme_fiabilite(..., scores_calibration=)` : permet de mesurer la
  couverture hors echantillon. Le mode par defaut est une tautologie et ne doit fonder
  aucune figure publiee.
- `data.synthese.TAILLE_MAX` : plafond explicite du generateur (90 coupes).
- `docs/donnees/verite-terrain.md` : d'ou viennent reellement les etiquettes
  d'eclairement, et les trois sources possibles.

### Documente (sans changement de comportement)

- `Certificat.duaux` est **structurellement vide en mode performantiel** :
  `figer_contacts` deplace les lignes saturees vers `A_eq`, dont les duaux ne sont
  jamais collectes. Le diagnostic dual ne fonctionne qu'en legalisation classique.
- `active.boucle.Loop` calibre le conforme **sur les points d'entrainement** : c'est
  l'anti-pattern `ARCHITECTURE.md` §10. La largeur d'intervalle rendue n'est pas
  publiable.
- `light.analytique.FACTEURS_SECTEUR` ne vient d'aucune source citee : CIBSE LG10 donne
  une profondeur limite independante de l'azimut, et le split-flux BRE travaille sous
  ciel couvert CIE, donc sans azimut. A presenter comme un a priori de modelisation.
- `light.simulateur` : `wwr` n'est pas un window-to-wall ratio (hauteur de bandeau
  comptee deux fois) ; `ECHELLE_DF = 100` annule exactement la division par 100 et
  n'est pas un reglage libre ; `theta = 65` est une hypothese d'obstruction non mesuree.
- `light.base.gradient` : differences finies, **18,4 ms par gradient a 15 pieces**, soit
  ~920 ms pour 50 iterations Frank-Wolfe contre un budget §9 de 500 ms. Le benchmark de
  CI passe parce qu'il cable `SubstitutAnalytique`, jamais le substitut appris.
- `light.appris._charger_torch` leve **inconditionnellement** : le transformeur du
  jalon 4 n'existe pas.
- `uq.gestion` : le verrou de calibration est une discipline avec somme de controle,
  pas une barriere cryptographique. Cinq contournements d'une ligne sont documentes.
- `lmo.coupes._resserrer_bornes` restreint le domaine : le statut `"optimal"` porte sur
  un domaine plus petit que le vrai.
- `data.decoupage` : l'empreinte couvre les identifiants et leur ordre, jamais la
  geometrie des plans.
- `feasibility` : le certificat de Farkas n'est jamais verifie contre les conditions du
  lemme ; c'est un certificat par confiance envers le solveur.

## [1.0.0] — 2026-09-09 — WITHDRAWN, never published

> Withdrawn on 2026-09-23: the README quick start did not run and several announced
> guarantees did not hold (AUDIT.md). The number is not reused; development continues
> as `0.10.0.dev0` and 1.0.0 will be a new release.

Gel de l'API publique (jalon 6, étape 7). Toute rupture devient `2.0`.

### Ajoute
- `archlux.feasibility.is_feasible` / `Verdict` / `CertificatFaisabilite`
  (Farkas exact, sans lumière).
- Exports paresseux : `ax.light`, `ax.bench`, `ax.feasibility`
  (`import archlux` ne charge toujours pas `torch`).
- `light` : `SubstitutAnalytique`, `SimulateurExact` (`ExactSimulator`),
  `Daylight`, `Substitut` — sans importer `appris`.
- `test_api_publique_stable` ; `CITATION.cff` ; `docs/publication-1.0.md`.

### Garanties
- Géométrie : exacte (inchangé).
- Performance : probabiliste / `NON EVALUABLE` (inchangé).

### Non inclus (processus)
- Tag Git / DOI Zenodo, upload PyPI, preuve d'usage tiers, historique ≥ 6 mois.

## [0.9.0] — 2026-09-09

Jalon 6, étape 5 : documentation complète (galerie, tutoriels, contribution).

### Ajoute
- `CONTRIBUTING.md` : dépendances `ARCHITECTURE.md`, gouvernance, revue, semver.
- `docs/tutoriels/premiers-pas.md` (remplace le stub).
- `docs/limites.md` enrichi (échangeabilité, NON EVALUABLE, hors périmètre auto).

### Change
- Tutoriel performantiel et galerie 01 : enveloppe corpus 12×9 m explicite.
- Checklist `MILESTONE-6.md` §6 cochée.

## [0.8.0] — 2026-09-09

Jalon 6, étape 4 : banc d'essai reproductible (manifeste, bruts, stats).

### Ajoute
- `types.ModeleTrace` (poids, calibration_n, alpha) sur `Manifeste.modele`.
- `bench.run` : manifeste puis `resultats_bruts.csv`, puis `Resultat`.
- `bench.report` : stratification par orientation imposée (8 secteurs).
- `bench.stats` : bootstrap apparié, TOST, analyse de puissance.
- `compare(..., evaluate_by=)` sans défaut (TypeError si omis).
- Tests `test_manifeste_complet`, `test_evaluate_by_obligatoire`.

### Change
- Sérialisation JSON du champ `modele` (rétrocompatible si absent).

## [0.7.0] — 2026-09-09

Jalon 6, étape 3 : export IFC / DXF et taux de survie (Wilson).

### Ajoute
- `export.pathologie` : taxonomie bloquante avant écriture.
- `export.to_ifc` : SPF IFC4 minimal (CI) ; extra `bim` optionnel.
- `export.to_dxf` : LWPOLYLINE ASCII sans dépendance.
- `export.survival_rate` / `intervalle_wilson`.
- Tests Hypothesis `plans_valides` → export valide ; Wilson dans `[0, 1]`.
- `docs/formules/export-bim.md`, `experiences/j6_survie_ifc.py`.

### Change
- `ARCHITECTURE.md` / `tests/test_dependances.py` : couche `export`
  ← `types`, `erreurs`.

## [0.6.0] — 2026-09-09

Jalon 6, étape 2 : apprentissage actif. Priorité = incertitude × densité
optimiseur (produit). Recalibrage conforme après chaque cycle.

### Ajoute
- `active.selection` : `UncertaintyTimesDensity`, `Aleatoire`.
- `active.densite.densite_noyau` (Scott).
- `active.boucle.Loop` / `RapportActif`.
- Tests : produit nul, actif bat l'aléatoire (oracle synthétique contrôlé).
- `docs/formules/apprentissage-actif.md`, `experiences/j6_actif.py`.

### Change
- `ARCHITECTURE.md` / `tests/test_dependances.py` : couche `active`
  ← `types`, `light.protocole`, `uq`.

## [0.5.0] — 2026-09-09

Jalon 6, étape 1 : géométries rectilinéaires (pièces en L). Convention de coupe
**verticale à gauche d'abord**, documentée et testée.

### Ajoute
- `geom.rectilineaire` : `decomposer`, `recomposer`, `etendre_fusions`,
  `PieceRectilineaire`.
- `legalize(..., fusions=)` : égalités de solidarisation dans ``A_eq``.
- `docs/formules/rectilineaire.md`.

### Garanties
- Géométrie : exacte (partition + fusions linéaires).
- Performance : inchangée (jalon 5).

## [0.4.0] — 2026-09-09

Garantie **probabiliste** sur l'oracle gelé (`SimulateurExact`, split-flux) :
quantile conforme à échantillon fini, certificat à deux natures, diagnostic dual.
(Radiance) reste hors chemin critique.

### Ajoute
- `uq.conforme` : `quantile_conforme` (rang \(\lceil(n+1)(1-\alpha)\rceil\)),
  `CalibrateurConforme`, `borner`.
- `uq.fiabilite` : CRPS gaussien, diagramme `(nominal, empirique)`, stratification
  à 8 orientations.
- `uq.derive` : test d'échangeabilité (permutation), `mesurer_derive` sur tableaux.
- `uq.gestion.geler_et_emettre` / `ModeleModifie` si les poids bougent après le gel.
- `light.objectif.Daylight` : \(J=\hat\mu-q̂\hat\sigma\), sans importer `uq`.
- `certify.borne.construire_borne` : `None` si la dérive invalide l'échangeabilité.
- `certify.dual.traduire_duaux` : phrases avec intervalle de validité locale.
- `certify.rapport.rendre` : `[EXACT]` / `[PREDICTION]`, `NON EVALUABLE` toujours présent.
- Docs : `concepts/deux-garanties.md`, `prediction-conforme.md`, galerie 04–05,
  tutoriel de calibration, `formules/statistique.md`.

### Change
- `BornePerformance` refuse `n_calibration < 1`.
- `legalize` traduit les duaux via `certify.dual` ; `performance` reste `None`
  (`api` n'importe pas `uq`).

### Garanties
- Géométrie : inchangée (exacte).
- Performance : couverture \(\ge 1-\alpha\) **sous échangeabilité** avec le jeu
  de calibration, contre l'oracle split-flux — pas un sDA LM-83.

## [0.3.1] — 2026-09-09

Oracle `SimulateurExact` : le terme d'aire \(\times\sin 2\theta\) (jouet) est
remplacé par un **facteur de lumière du jour split-flux** (BRE / Littlefair).
(Radiance) reste hors chemin critique.

### Ajoute
- `light.simulateur.facteur_lumiere_jour` : DF moyen, WWR sur la façade sud.
- Tests métier : profondeur, sud/nord, WWR ; pièce canonique 6 m × 4 m (1–5 %).
- `docs/formules/split-flux.md`.

### Change
- `SimulateurExact.evaluer` / `.gradient` : analytique CIBSE + \(\sum 100\cdot\mathrm{DF}\cdot\mathrm{aire}\).
- Champ `wwr` (défaut \(0{,}30\)), sans élargir le protocole `Substitut`.

## [0.3.0] — 2026-09-09

Substitut **appris** (perceptron numpy, transformeur derrière `torch` paresseux)
et **point de contrôle du gradient**. Vérité terrain = `SimulateurExact`
(forme fermée). (Radiance) est hors chemin critique : extra `sim` vide, jamais
exigé par la CI ni par les jalons 5–6.

### Ajoute
- `data` : dédup Hausdorff \(0{,}02\,\mathrm{m}\), corpus synthétique, imputation
  de baies, `splits/v1/` (54 / 18 / 18).
- `uq.gestion` : jeton de calibration après gel ; `GestionDonnees`.
- `light.jetons` : ensemble continu, test anti-image (2 cm).
- `light.simulateur.SimulateurExact` : déterministe, protocole `Substitut`.
- `light.base.SubstitutDense` : 3 couches, Huber, sans `torch`.
- `light.appris.SubstitutAppris` : `npz` dense ; `.pt` charge `torch` localement.
- `light.validation.valider_gradient` : accord de signe, seuil 0,80 bloquant.
- `bench.compare(..., evaluate_by=)` obligatoire.
- `scripts/{preparer_donnees,simuler,valider_gradient}.py`,
  `experiences/j4_gradient.py`, `docs/donnees/`,
  `docs/concepts/pourquoi-pas-une-image.md`.

### Garanties
- Géométrie : inchangée (exacte).
- Score du réseau : **sans couverture** jusqu'au jalon 5.
- Le jeu de calibration n'est pas lu à l'entraînement.

## [0.2.0] — 2026-09-09

Légalisation performantielle **sans apprentissage** : le même oracle LP, un autre \(c\).

### Ajoute
- `orient.circulaire` : harmoniques, moyenne / variance, Rayleigh, régression, 8 secteurs.
- `light.analytique.SubstitutAnalytique` : profondeur utile saturée, 8 secteurs, sud géographique.
- `solve.frank_wolfe` : `depart=x`, pas \(2/(k+2)\), écartement, gap, coupes Kelley, duaux.
- `geom.polytope.figer_contacts` : contacts L1 saturés → égalités, et collage
  \(x,y\) au contour ; les largeurs min restent libres.
- `api.legalize(..., objective=Substitut, trace=True)` ; `objective=None` inchangé.
  Sortie FW revérifiée : un itéré invalide lève `InvariantViole`, sans repli L1.
- Expérience `experiences/j3_orientation.py`, `resultats/j3_orientation.csv` / `.svg`.
- Fiches `docs/formules/{circulaire,substitut-analytique,frank-wolfe}.md`, galerie 02,
  `docs/concepts/oracle-partage.md`.

## [0.1.0] — 2026-09-09

Premier livrable publiable : un plan entre, un plan valide et sa preuve exacte sortent.

### Ajoute — jalon 2, etapes 4–7
- `lmo.coupes` : tangentes d'appui a `{wh ≥ a_min}` (Boyd–Vandenberghe §3.1.5–3.1.6,
  AM-GM Hardy–Littlewood–Polya th. 16, Kelley 1960). Projection sur l'hyperbole avant
  d'ecrire la coupe, sinon un point infaisable exclut des rectangles admissibles.
- `geom.polytope.etendre_ecarts_l1` : epigraphe de `‖x − x̂‖₁` (Bertsimas–Tsitsiklis §1.3).
  Les `x̂_i` sont dans les contraintes, `c = (0_n, 1_n)`.
- `certify.preuve.verifier_exactement` : chevauchement, jours, surfaces, structure —
  independant du solveur. `valide` est la conjonction, sans aucun champ probabiliste.
- `api.legalize` / `api.gradient_distance` : legalisation classique. `objective` non nul
  reste le jalon 3. Infaisabilite = `Infaisable` avec certificat de Farkas et origines.
- `experiences/j2_taux_validite.py` et `resultats/j2_brut.csv` : protocole de mesure.
- Galerie 01 et 03, `docs/concepts/polytope.md`.
- `docs/formules/` : énoncé, dérivation, source et cas d'usage de chaque résultat
  du jalon 2 (ordre, polytope, L1, coupes, Farkas, preuve).

### Ajoute — jalon 1
- `types.Referentiel.a_min` : seuil reglementaire par type de piece ; un type inconnu
  rend `0.0` plutot que de lever.
- `types.Ouverture.segment_absolu` : la position d'une baie est **derivee** de son mur.
  Une baie suit desormais sa cloison quand le solveur la deplace.
- `io.json_io` : schema JSON versionne (`VERSION_SCHEMA = "1"`), aller-retour sans perte
  certificat compris, ecriture deterministe (cles triees, UTF-8, fin de ligne `\n`).
- `bench.graines.deriver` : sous-graines nommees, stables d'une machine a l'autre
  (BLAKE2b, jamais `hash()` qui est randomise par processus). Valeurs epinglees par test.
- `bench.manifeste.emettre` : manifeste de reproductibilite, graine obligatoire.
- `tests/proprietes/strategies.py` : `plans_quelconques` operationnelle, partagee par
  les jalons suivants.
- `docs/reference/schema-json.md` : le format d'echange documente.

### Ajoute
- Squelette du projet : arborescence, configuration qualite, CI, contrats de modules.
- `tests/test_dependances.py` : les regles de dependance de `ARCHITECTURE.md` §5 sont
  verifiees automatiquement des le premier commit, `__init__.py` compris.
- `tests/unites/test_protocole_substitut.py` : verifie que chaque implementation de
  `Substitut` respecte le protocole, signatures comprises.

### Modifie
- API publique : le chargement et le rendu passent par `Plan.from_json`, `Plan.to_json`
  et `Certificat.rapport()`, conformement a `DOCUMENTATION.md` §3 et §5. Les fonctions
  libres `charger` / `ecrire` ne sont plus exportees (voir ADR-5 du blueprint).
- Les documents contraignants sont regroupes dans `docs/specification/` et publies avec
  le site. `AGENTS.md` et `CLAUDE.md` restent a la racine : les outils les y decouvrent.

### Ajoute — jalon 2, etape 3 : oracle lineaire
- `lmo.solveur.resoudre` : backend OR-Tools GLOP, signature du §4 respectee a la lettre
  (`depart`, `coupes`, `duaux`). Le module **ignore toujours d'ou vient `c`**.
- Demarrage a chaud par reutilisation du modele GLOP, indexee par le polytope. Mesure :
  **0,206 ms a chaud contre 0,746 ms a froid, soit x3,6** — le facteur annonce au §10.
- Certificat de Farkas par probleme auxiliaire, multiplicateurs rendus sous forme
  canonique positive. Sur un cas reel, il designe `separation horizontale A|B` et
  `contour droit B` : deux pieces de 2 m ne tiennent pas dans 3 m.
- Prix duaux extraits sur demande, dans l'ordre des lignes de `A` — c'est cet ordre qui
  les rend appariables avec `origines`.
- `lmo.solveur.vider_cache` : garantit un depart a froid pour les mesures.
- Budgets du §9 actives : LP a froid **0,75 ms** (budget 10 ms), a chaud **0,21 ms**
  (budget 3 ms).

### Corrige — GLOP confond « infaisable » et « non borne »
- GLOP rend le code `INFEASIBLE` pour un probleme non borne. `resoudre` aurait donc leve
  « le programme ne tient pas dans l'enveloppe » sur un domaine ouvert. Un LP de
  faisabilite a objectif nul tranche desormais : il ne peut pas etre non borne, donc s'il
  trouve un point, l'echec venait de l'objectif.
- Le probleme auxiliaire relache aussi les coupes. Sans cela, une coupe impossible le
  rendait lui-meme infaisable et ses duaux ne voulaient plus rien dire.
- `test_warm_start_est_plus_rapide` echouait environ une fois sur sept : une somme de
  mesures laissait un seul pic d'ordonnancement decider. Mesures desormais entrelacees et
  comparees par leur mediane. Un test instable est pire qu'un test qui echoue.

### Ajoute — jalon 2, etape 2 : polytope
- `geom.polytope.construire_polytope` : assemblage `A x <= b`, bornes, `index` et
  `origines`. Graphe **reduit transitivement** avant assemblage.
- `Polytope.contient` : verification naive et directe, independante de tout solveur.
- `geom.polytope.vectoriser` / `devectoriser` : les ouvertures traversent la
  devectorisation intactes, sans resynchronisation a ecrire.
- Premier budget du §9 active : construction du polytope **1,08 ms** pour 15 pieces,
  contre 5 ms autorisees.
- `A_eq` reste vide, de forme correcte — voir ADR-7, question ouverte.

### Corrige — `deduire_ordre` choisissait le mauvais axe
- L'axe retenu est desormais celui sur lequel les pieces sont **reellement disjointes**,
  et non celui du plus grand ecart entre centres. Deux pieces separees en x mais
  recouvrantes en y recevaient une contrainte verticale que le plan d'origine violait :
  `legalize` aurait deplace des murs sur un plan sans defaut. Defaut trouve par le test
  de propriete du polytope, pas par relecture.
- Tolerance de contact `1e-9 m` : `1.0 + 3.47` vaut `4.470000000000001`, si bien que deux
  pieces jointives passaient pour recouvrantes de 1e-16 et basculaient dans le cas
  degrade. Le cas survient des qu'un mur separe deux pieces adjacentes.

### Ajoute — jalon 2, etape 1 : graphe de contraintes
- `geom.graphe.deduire_ordre` : extrait l'ordre relatif d'un plan propose en comparant
  les centres, axe du plus grand ecart. **Acyclique par construction** — sur chaque axe
  l'arete suit l'ordre total de la cle `(coordonnee, identifiant)`.
- `geom.graphe.construire_graphe` : deux `DiGraph` valides, cycles rejetes par
  `OrdreIncoherent` (avec l'axe et le cycle), paires non separees par
  `SeparationManquante`.
- `geom.graphe.reduction_transitive` : retire les aretes impliquees, conserve les noeuds
  isoles que `networkx.transitive_reduction` laisse tomber.
- `GrapheContraintes.fermeture()` : information d'ordre reelle, qui permet de prouver que
  la reduction ne perd rien.
- `tests/proprietes/strategies.ordres_valides` : ordres construits **sans reutiliser**
  `deduire_ordre`, pour que les tests de propriete ne soient pas tautologiques.

### Ajoute — validation a la frontiere (ADR-6)
- `io.json_io.depuis_dict` verifie les plages de `ARCHITECTURE.md` §6 : `s` dans
  `[0, 1]`, `largeur_rel` dans `]0, 1]`, dimensions et epaisseurs strictement positives.
  **Toutes** les violations sont rapportees ensemble, pas seulement la premiere.
- Les valeurs non finies sont refusees a la lecture : `json.loads` accepte les litteraux
  `NaN` et `Infinity`, ce qui aurait injecte des `NaN` dans le solveur depuis un fichier
  produit par un autre outil.
- La validation reste **a la frontiere** : les constructeurs ne verifient rien, pour que
  `solve` puisse traverser des etats intermediaires sans payer une verification par
  construction dans une boucle de Frank-Wolfe.

### Corrige — revue du jalon 1
- `io.json_io.ecrire` laissait remonter un `ValueError` de la bibliotheque standard sur
  une valeur non finie ; il leve desormais `InvariantViole`, conformement a
  `ARCHITECTURE.md` §7. `NaN` est precisement ce que produit un solveur bogue.
- `tests/proprietes/strategies.py` ne generait jamais de `violations` non vides ni de
  `performance` non nulle : la moitie probabiliste de la serialisation du certificat
  n'etait **jamais executee**, malgre 200 exemples Hypothesis. Generateur elargi.
- Couverture des modules du jalon 1 portee a 100 % (`types`, `erreurs`, `io`, `bench`).

### Corrige
- `pyproject.toml` declarait `readme = "README.md"` alors que le fichier s'appelait
  `README (2).md` : le paquet ne se construisait pas du tout.
- `testpaths` omettait `benchmarks/` : le job « budgets » de la CI ne collectait aucun
  test et passait au vert sans rien mesurer.
- `python_version = "3.11"` cote mypy faisait echouer l'analyse sur les stubs de numpy
  avant d'atteindre le code du projet.
