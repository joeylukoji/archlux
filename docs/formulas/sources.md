# Verified bibliography

Only **accessible** books and articles, with a location
(chapter, theorem, DOI). Mentions such as "according to X" without a reference are refused.

## Convex and linear optimization

1. Boyd, S. & Vandenberghe, L. (2004). *Convex Optimization*. Cambridge University Press.
   ISBN 978-0-521-83378-3.
   - §2.2.4: polyhedra as intersections of half-spaces.
   - §3.1.5: concavity of \(\log\); composition.
   - §3.1.6: superlevel sets of a concave function.
   - [doi:10.1017/CBO9780511804441](https://doi.org/10.1017/CBO9780511804441)

2. Bertsimas, D. & Tsitsiklis, J. N. (1997). *Introduction to Linear Optimization*.
   Athena Scientific. ISBN 978-1-886529-19-9.
   - §1.3: linearization of \(\lvert x\rvert\) by an epigraph.
   - ch. 4: duality; Farkas' lemma as a theorem of the alternative.

3. Kelley, J. E., Jr. (1960). The cutting-plane method for solving convex programs.
   *Journal of the Society for Industrial and Applied Mathematics*, 8(4), 703–712.
   [doi:10.1137/0108053](https://doi.org/10.1137/0108053)

4. Schrijver, A. (1986). *Theory of Linear and Integer Programming*. Wiley.
   ISBN 978-0-471-90854-8. §7.3: Farkas' lemma.

## Inequalities

5. Hardy, G. H., Littlewood, J. E. & P&oacute;lya, G. (1952). *Inequalities* (2nd ed.).
   Cambridge University Press. Theorem 16: arithmetic–geometric mean.

## Graphs and floorplan compaction

6. Otten, R. H. J. M. (1982). Automatic floorplan design. *Proceedings of the 19th
   Design Automation Conference*, 261–267.
   [doi:10.1145/800263.809216](https://doi.org/10.1145/800263.809216)

7. Lengauer, T. (1990). *Combinatorial Algorithms for Integrated Circuit Layout*.
   Teubner / Wiley. ISBN 3-519-02115-X. Ch. 10: compaction by constraint graph
   (\(x_a + w_a \le x_b\)).

8. Aho, A. V., Garey, M. R. & Ullman, J. D. (1972). The transitive reduction of a
   directed graph. *SIAM Journal on Computing*, 1(2), 131–137.
   [doi:10.1137/0201008](https://doi.org/10.1137/0201008)

## Computational geometry (proof)

9. Vatti, B. R. (1992). A generic solution to polygon clipping. *Communications of the
   ACM*, 35(7), 56–63. [doi:10.1145/129902.129906](https://doi.org/10.1145/129902.129906)
   (algorithm underlying GEOS / Shapely for polygon intersection).

10. Halmos, P. R. (1950). *Measure Theory*. Van Nostrand. Ch. 9: additivity of the
    Lebesgue measure — a disjoint tiling satisfies
    \(\lambda(\bigcup R_i)=\sum\lambda(R_i)\).

## Statistics (milestones 3 and 5, **not** milestone 2)

11. Mardia, K. V. & Jupp, P. E. (2000). *Directional Statistics*. Wiley.
    [doi:10.1002/9780470316979](https://doi.org/10.1002/9780470316979)
    — circular statistics (orientation). See [circular](circular.md).

12. Vovk, V., Gammerman, A. & Shafer, G. (2005). *Algorithmic Learning in a Random
    World*. Springer. [doi:10.1007/b106715](https://doi.org/10.1007/b106715)
    — conformal prediction. See [statistics](statistics.md).

13. Frank, M. & Wolfe, P. (1956). An algorithm for quadratic programming.
    *Naval Research Logistics Quarterly*, 3(1–2), 95–110.
    [doi:10.1002/nav.3800030109](https://doi.org/10.1002/nav.3800030109)

14. Lacoste-Julien, S. & Jaggi, M. (2015). On the global linear convergence of
    Frank-Wolfe optimization variants. *NeurIPS*.
    [https://arxiv.org/abs/1511.05932](https://arxiv.org/abs/1511.05932)
    — away steps. See [Frank-Wolfe](frank-wolfe.md).

## Daylight (milestone 3, **no guarantee**)

15. CIBSE (2014). *Lighting Guide 10: Daylighting — a guide for designers*.
    Chartered Institution of Building Services Engineers, London.
    — empirical useful-depth rule \(\approx 2.5\times\) head
    height. See [analytic surrogate](analytic-surrogate.md).
    It is **not** a statistical coverage.

16. Littlefair, P. J. (2011). *Site layout planning for daylight and sunlight:
    a guide to good practice* (BRE 209, 2nd ed.). IHS BRE Press.
    — average split-flux DF, overcast sky. See [split-flux](split-flux.md).
    It is **not** an LM-83 sDA.

17. Nocedal, J. & Wright, S. J. (2006). *Numerical Optimization* (2nd ed.).
    Springer. §8.1: centred finite differences.
    See [gradient validation](gradient-validation.md).

## Benchmark inference (milestone 6)

18. Wilson, E. B. (1927). Probable inference, the law of succession, and statistical
    inference. *Journal of the American Statistical Association*, 22(158), 209–212.
    [doi:10.1080/01621459.1927.10502953](https://doi.org/10.1080/01621459.1927.10502953)
    — score interval for a proportion. See [export](bim-export.md).

19. Brown, L. D., Cai, T. T. & DasGupta, A. (2001). Interval estimation for a binomial
    proportion. *Statistical Science*, 16(2), 101–133.
    [doi:10.1214/ss/1009213286](https://doi.org/10.1214/ss/1009213286)
    — why the Wald interval must be avoided; recommendation of Wilson.

20. Efron, B. & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*.
    Chapman & Hall. ISBN 978-0-412-04231-7. Ch. 13: percentile intervals.
    — `bench.stats.paired_bootstrap`. See [benchmark](benchmark.md).

21. Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure and the
    power approach for assessing the equivalence of average bioavailability.
    *Journal of Pharmacokinetics and Biopharmaceutics*, 15(6), 657–680.
    [doi:10.1007/BF01068419](https://doi.org/10.1007/BF01068419)
    — TOST. **Non-rejection ≠ equivalence**: it is the equivalence test that concludes,
    not the absence of significance.

22. Holm, S. (1979). A simple sequentially rejective multiple test procedure.
    *Scandinavian Journal of Statistics*, 6(2), 65–70.
    [jstor:4615733](https://www.jstor.org/stable/4615733)
    — FWER control without an independence assumption. `bench.stats.holm`.

23. Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences*
    (2nd ed.). Lawrence Erlbaum. Ch. 2: power of the \(t\) test, Cohen's \(d\).
    — `bench.stats.power`.

## Density estimation and active learning (milestone 6)

24. Scott, D. W. (1992). *Multivariate Density Estimation: Theory, Practice, and
    Visualization*. Wiley. [doi:10.1002/9780470316849](https://doi.org/10.1002/9780470316849)
    §6.3: bandwidth rule \(h \propto n^{-1/(d+4)}\).
    — `active.densite.kernel_density`.

25. Silverman, B. W. (1986). *Density Estimation for Statistics and Data Analysis*.
    Chapman & Hall. §4.3: isotropic Gaussian kernel, curse of dimensionality.

26. Settles, B. (2009). *Active Learning Literature Survey*. Computer Sciences
    Technical Report 1648, University of Wisconsin–Madison.
    — uncertainty sampling; density weighting (§6.3.2), which is
    exactly the product \(\hat\sigma \times \hat f\) of
    [active learning](active-learning.md).

27. Lei, J., G'Sell, M., Rinaldo, A., Tibshirani, R. J. & Wasserman, L. (2018).
    Distribution-free predictive inference for regression. *JASA*, 113(523), 1094–1111.
    [doi:10.1080/01621459.2017.1307116](https://doi.org/10.1080/01621459.2017.1307116)
    — **split** conformal prediction and **normalized** scores
    \(|y-\hat y|/\hat\sigma\): this is the variant actually implemented by
    `uq.conformal`, more precise than reference no. 12 alone.
    See [statistics](statistics.md).

28. Angelopoulos, A. N. & Bates, S. (2023). Conformal prediction: a gentle
    introduction. *Foundations and Trends in Machine Learning*, 16(4), 494–591.
    [doi:10.1561/2200000101](https://doi.org/10.1561/2200000101)
    — marginal coverage bracketed: \(1-\alpha \le P \le 1-\alpha+\tfrac{1}{n+1}\).
