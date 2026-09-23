# Bibliographie vérifiée

Uniquement des ouvrages et articles **consultables**, avec une localisation
(chapitre, théorème, DOI). Les mentions « d'après X » sans référence sont refusées.

## Optimisation convexe et linéaire

1. Boyd, S. & Vandenberghe, L. (2004). *Convex Optimization*. Cambridge University Press.
   ISBN 978-0-521-83378-3.
   - §2.2.4 : polyèdres comme intersection de demi-espaces.
   - §3.1.5 : concavité de \(\log\) ; composition.
   - §3.1.6 : super-niveaux d'une fonction concave.
   - [doi:10.1017/CBO9780511804441](https://doi.org/10.1017/CBO9780511804441)

2. Bertsimas, D. & Tsitsiklis, J. N. (1997). *Introduction to Linear Optimization*.
   Athena Scientific. ISBN 978-1-886529-19-9.
   - §1.3 : linéarisation de \(\lvert x\rvert\) par un épigraphe.
   - ch. 4 : dualité ; lemme de Farkas sous forme d'alternative.

3. Kelley, J. E., Jr. (1960). The cutting-plane method for solving convex programs.
   *Journal of the Society for Industrial and Applied Mathematics*, 8(4), 703–712.
   [doi:10.1137/0108053](https://doi.org/10.1137/0108053)

4. Schrijver, A. (1986). *Theory of Linear and Integer Programming*. Wiley.
   ISBN 978-0-471-90854-8. §7.3 : lemme de Farkas.

## Inégalités

5. Hardy, G. H., Littlewood, J. E. & Pólya, G. (1952). *Inequalities* (2e éd.).
   Cambridge University Press. Théorème 16 : moyenne arithmétique–géométrique.

## Graphes et compaction de plans

6. Otten, R. H. J. M. (1982). Automatic floorplan design. *Proceedings of the 19th
   Design Automation Conference*, 261–267.
   [doi:10.1145/800263.809216](https://doi.org/10.1145/800263.809216)

7. Lengauer, T. (1990). *Combinatorial Algorithms for Integrated Circuit Layout*.
   Teubner / Wiley. ISBN 3-519-02115-X. Ch. 10 : compaction par graphe de contraintes
   (\(x_a + w_a \le x_b\)).

8. Aho, A. V., Garey, M. R. & Ullman, J. D. (1972). The transitive reduction of a
   directed graph. *SIAM Journal on Computing*, 1(2), 131–137.
   [doi:10.1137/0201008](https://doi.org/10.1137/0201008)

## Géométrie algorithmique (preuve)

9. Vatti, B. R. (1992). A generic solution to polygon clipping. *Communications of the
   ACM*, 35(7), 56–63. [doi:10.1145/129902.129906](https://doi.org/10.1145/129902.129906)
   (algorithme sous-jacent à GEOS / Shapely pour l'intersection de polygones).

10. Halmos, P. R. (1950). *Measure Theory*. Van Nostrand. Ch. 9 : additivité de la
    mesure de Lebesgue — un pavage disjoint vérifie
    \(\lambda(\bigcup R_i)=\sum\lambda(R_i)\).

## Statistique (jalons 3 et 5, **pas** le jalon 2)

11. Mardia, K. V. & Jupp, P. E. (2000). *Directional Statistics*. Wiley.
    [doi:10.1002/9780470316979](https://doi.org/10.1002/9780470316979)
    — statistiques circulaires (orientation). Voir [circulaire](circulaire.md).

12. Vovk, V., Gammerman, A. & Shafer, G. (2005). *Algorithmic Learning in a Random
    World*. Springer. [doi:10.1007/b106715](https://doi.org/10.1007/b106715)
    — prédiction conforme. Voir [statistique](statistique.md).

13. Frank, M. & Wolfe, P. (1956). An algorithm for quadratic programming.
    *Naval Research Logistics Quarterly*, 3(1–2), 95–110.
    [doi:10.1002/nav.3800030109](https://doi.org/10.1002/nav.3800030109)

14. Lacoste-Julien, S. & Jaggi, M. (2015). On the global linear convergence of
    Frank-Wolfe optimization variants. *NeurIPS*.
    [https://arxiv.org/abs/1511.05932](https://arxiv.org/abs/1511.05932)
    — pas d'écartement. Voir [Frank-Wolfe](frank-wolfe.md).

## Éclairement (jalon 3, **sans garantie**)

15. CIBSE (2014). *Lighting Guide 10 : Daylighting — a guide for designers*.
    Chartered Institution of Building Services Engineers, Londres.
    — règle empirique de profondeur utile \(\approx 2{,}5\times\) hauteur de
    linteau. Voir [substitut analytique](substitut-analytique.md).
    Ce n'est **pas** une couverture statistique.

16. Littlefair, P. J. (2011). *Site layout planning for daylight and sunlight :
    a guide to good practice* (BRE 209, 2e éd.). IHS BRE Press.
    — DF moyen split-flux, ciel couvert. Voir [split-flux](split-flux.md).
    Ce n'est **pas** un sDA LM-83.

17. Nocedal, J. & Wright, S. J. (2006). *Numerical Optimization* (2e éd.).
    Springer. §8.1 : différences finies centrées.
    Voir [validation du gradient](validation-gradient.md).

## Inférence du banc d'essai (jalon 6)

18. Wilson, E. B. (1927). Probable inference, the law of succession, and statistical
    inference. *Journal of the American Statistical Association*, 22(158), 209–212.
    [doi:10.1080/01621459.1927.10502953](https://doi.org/10.1080/01621459.1927.10502953)
    — intervalle de score pour une proportion. Voir [export](export-bim.md).

19. Brown, L. D., Cai, T. T. & DasGupta, A. (2001). Interval estimation for a binomial
    proportion. *Statistical Science*, 16(2), 101–133.
    [doi:10.1214/ss/1009213286](https://doi.org/10.1214/ss/1009213286)
    — pourquoi l'intervalle de Wald est à proscrire ; recommandation de Wilson.

20. Efron, B. & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*.
    Chapman & Hall. ISBN 978-0-412-04231-7. Ch. 13 : intervalles par percentiles.
    — `bench.stats.bootstrap_apparie`. Voir [banc d'essai](banc-essai.md).

21. Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure and the
    power approach for assessing the equivalence of average bioavailability.
    *Journal of Pharmacokinetics and Biopharmaceutics*, 15(6), 657–680.
    [doi:10.1007/BF01068419](https://doi.org/10.1007/BF01068419)
    — TOST. **Non-rejet ≠ équivalence** : c'est le test d'équivalence qui conclut,
    pas l'absence de significativité.

22. Holm, S. (1979). A simple sequentially rejective multiple test procedure.
    *Scandinavian Journal of Statistics*, 6(2), 65–70.
    [jstor:4615733](https://www.jstor.org/stable/4615733)
    — contrôle du FWER sans hypothèse d'indépendance. `bench.stats.holm`.

23. Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences*
    (2e éd.). Lawrence Erlbaum. Ch. 2 : puissance du test \(t\), \(d\) de Cohen.
    — `bench.stats.puissance`.

## Estimation de densité et apprentissage actif (jalon 6)

24. Scott, D. W. (1992). *Multivariate Density Estimation: Theory, Practice, and
    Visualization*. Wiley. [doi:10.1002/9780470316849](https://doi.org/10.1002/9780470316849)
    §6.3 : règle de la largeur de bande \(h \propto n^{-1/(d+4)}\).
    — `active.densite.densite_noyau`.

25. Silverman, B. W. (1986). *Density Estimation for Statistics and Data Analysis*.
    Chapman & Hall. §4.3 : noyau gaussien isotrope, fléau de la dimension.

26. Settles, B. (2009). *Active Learning Literature Survey*. Computer Sciences
    Technical Report 1648, University of Wisconsin–Madison.
    — échantillonnage par incertitude ; pondération par densité (§6.3.2), qui est
    exactement le produit \(\hat\sigma \times \hat f\) de
    [apprentissage actif](apprentissage-actif.md).

27. Lei, J., G'Sell, M., Rinaldo, A., Tibshirani, R. J. & Wasserman, L. (2018).
    Distribution-free predictive inference for regression. *JASA*, 113(523), 1094–1111.
    [doi:10.1080/01621459.2017.1307116](https://doi.org/10.1080/01621459.2017.1307116)
    — conforme **par découpage** (split conformal) et scores **normalisés**
    \(|y-\hat y|/\hat\sigma\) : c'est la variante réellement implémentée par
    `uq.conforme`, plus précise que la référence n° 12 seule.
    Voir [statistique](statistique.md).

28. Angelopoulos, A. N. & Bates, S. (2023). Conformal prediction: a gentle
    introduction. *Foundations and Trends in Machine Learning*, 16(4), 494–591.
    [doi:10.1561/2200000101](https://doi.org/10.1561/2200000101)
    — couverture marginale encadrée : \(1-\alpha \le P \le 1-\alpha+\tfrac{1}{n+1}\).
