# Pavage exact

**Code :** `geom.pavage.deduire_trame`, `etendre_pavage` ; `api.legalize(..., pavage=True)`.

## Le problème

Le [polytope d'ordre](polytope-separe.md) est un **relaxé** : \(x_a+w_a\le x_b\)
interdit le chevauchement, jamais le trou. Si l'entrée porte un jour, le plan
troué est déjà le point le plus proche de lui-même : l'optimum de
[l'épigraphe L1](epigraphe-l1.md) le laisse tel quel, et
[la vérification exacte](preuve-exacte.md) le rejette.

Mesuré sur MSD : `legalize` répare 68,2 % des chevauchements et **10,0 %** des jours.

## Énoncé

Dans une dissection rectangulaire, tout bord de pièce est porté par une **ligne de
trame**. Soient \(v_0<\dots<v_p\) les lignes verticales, \(h_0<\dots<h_q\) les
horizontales. La pièce \(i\) s'écrit

\[
R_i=[\,v_{l(i)},\,v_{r(i)}\,]\times[\,h_{b(i)},\,h_{t(i)}\,],
\qquad l(i)<r(i),\; b(i)<t(i),
\]

et couvre exactement les **cellules** \(C_{\alpha\beta}=[v_\alpha,v_{\alpha+1}]\times
[h_\beta,h_{\beta+1}]\) telles que \(l(i)\le\alpha<r(i)\) et \(b(i)\le\beta<t(i)\).

> **Proposition.** Soit \(\mathcal{K}\) l'ensemble des cellules intérieures au
> contour. Si les familles \(\{(\alpha,\beta)\}_i\) forment une **partition** de
> \(\mathcal{K}\), alors pour *toute* suite strictement croissante
> \((v_\alpha)\), \((h_\beta)\), l'union des \(R_i\) pave exactement le contour.

*Démonstration.* Les cellules sont d'intérieurs deux à deux disjoints et leur
union est le contour. Chaque \(R_i\) est l'union des cellules de sa famille. Une
partition des familles donne donc
\(\lambda(\bigcup_i R_i)=\sum_i\lambda(R_i)=\lambda(\mathcal{K})\) et
\(\lambda(R_i\cap R_j)=0\) pour \(i\neq j\) (additivité, Halmos 1950). ∎

**La condition de pavage ne porte que sur les indices, jamais sur les
coordonnées.** C'est un fait combinatoire, vérifié une fois pour toutes.

Il suffit alors d'imposer *« ces bords partagent une ligne »*, soit des égalités
affines dans les variables existantes :

\[
x_i = x_j \quad\text{ou}\quad x_i = x_j + w_j
\quad\text{selon le côté},
\]

et de **figer** les lignes portant un sommet du contour, qui est une donnée
d'entrée. Tout point admissible est dès lors un pavage exact : **un jour cesse
d'être représentable**.

## Hypothèses

- Le contour est **rectilinéaire**, et tous ses sommets entrent dans la trame :
  sans quoi une cellule chevaucherait le bord et le masque n'aurait pas de sens.
- La partition porte sur les cellules **intérieures au contour**. Exiger le pavage
  de la boîte englobante rejetterait tout appartement en L.
- La stricte croissance des lignes n'est pas imposée : elle découle des
  séparations et de \(w\ge 0\). Deux lignes peuvent coïncider, écrasant une pièce ;
  l'objectif L1 l'évite en pratique, `largeur_min > 0` l'interdit.

## Récupérer la trame depuis un plan fautif

La trame doit être lue sur le plan **proposé**, qui est justement invalide.

Une tolérance métrique **ne convient pas** : trop large elle écrase les cloisons
étroites, trop étroite elle ne récupère rien. Mesuré : 3,8 % de réparation.

Le bon critère est le **support** d'une ligne — le nombre de bords qu'elle porte.
Dans un plan sain, une ligne intérieure en porte au moins deux : un mur sépare
deux pièces. Déplacer une pièce fait quitter sa ligne à un bord et en crée une
nouvelle, portée par lui seul. On résorbe donc les lignes **orphelines**
(support \(<2\)) dans leur voisine la plus proche, en refusant toute fusion qui
écraserait une pièce.

Aucun seuil en mètres n'intervient : un jour de \(2\,\mathrm{m}\) se rattrape
aussi bien qu'un jour de \(5\,\mathrm{cm}\), et une cloison de \(40\,\mathrm{cm}\)
survit.

**Réparation bornée.** Après consolidation il subsiste des défauts *locaux* : une
cellule non couverte, ou couverte deux fois — le cas dominant sur MSD. On agrandit
ou rétrécit alors une pièce **d'un cran**, ce qui la laisse rectangulaire par
construction. Une extension n'est retenue que si **toutes** les cellules gagnées
sont manquantes ; une réduction, que si toutes celles libérées sont en excès. Rien
n'est inventé : on rend à une pièce ce qu'une faute lui avait pris.

Le budget (défaut 4) est ce qui distingue une réparation d'une reconstruction. Il
sature vite — 8 ne gagne rien sur 4 :

| budget | 0 | 2 | 4 | 8 |
|---|--:|--:|--:|--:|
| trame récupérée | 77,8 % | 98,5 % | **99,2 %** | 99,2 % |

!!! warning "Conséquence sémantique"
    Fermer un jour, c'est agrandir quelqu'un : la réparation peut **absorber une
    pièce manquante dans sa voisine**, et le plan sort avec une pièce de moins que
    le générateur n'en avait prévu. Un appelant qui doit préserver le programme
    pièce par pièce passe ``budget_reparation=0`` — la partition est alors vérifiée,
    jamais retouchée.

## Deux propriétés

1. **Le système reste faisable.** Les positions de trame du plan de référence sont
   toujours un point admissible. Geler des contacts *approximativement* saturés
   (`figer_contacts`) n'offre aucune garantie de ce genre : 8 % de LP infaisables
   mesurés, pour 41,5 % de réparation seulement.
2. **La garantie est structurelle.** Elle ne dépend d'aucune tolérance à
   l'exécution : la vérification de partition a déjà eu lieu.

## Résultats

4 796 corruptions de 300 appartements MSD réels ; bruts et table dans
`resultats/j7_reparation_brut.csv` et `resultats/j7_reparation.md` :

| Faute | `legalize` | `pavage=True` | repli |
|---|--:|--:|--:|
| jour | 10,0 % | 97,6 % | **98,0 %** |
| sous-dimension | 4,8 % | 96,0 % | **96,3 %** |
| chevauchement | 68,2 % | 90,3 % | **91,2 %** |
| décalage | 60,8 % | 88,1 % | **90,0 %** |
| **toutes** | 35,9 % | 93,0 % | **93,9 %** |

IC 95 % sur le repli global : [93,2 – 94,5]. Temps médian 6,5 ms, sous le budget de
20 ms d'`ARCHITECTURE.md` §9. Par amplitude de faute : 96,8 % à 10 cm, 96,9 % à
25 cm, 93,2 % à 50 cm, 88,6 % à 1 m.

Le repli n'ajoute qu'un point : la contrainte de pavage domine presque partout à
elle seule. Il reste utile là où la corruption détruit la structure combinatoire —
`deduire_trame` refuse alors plutôt que de deviner, et le L1 seul reprend la main.

## Cas d'utilisation

| Faire | Ne pas faire |
|---|---|
| Activer dès que l'entrée peut porter un jour (sortie de générateur) | L'activer sur une entrée dont la structure est inconnue sans prévoir le repli |
| Lire le diagnostic : il nomme les cellules fautives | Élargir la tolérance pour « faire passer » — elle n'est pas le levier |
| Garder le repli sur `legalize` seul | Croire que le pavage domine partout |

## Source

Formulation par coordonnées de murs des dissections rectangulaires :
Otten (1982), [bibliographie](sources.md) n° 6 ; Lengauer (1990) ch. 10, n° 7.
Additivité : Halmos (1950), n° 10.
