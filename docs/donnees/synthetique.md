# Corpus synthétique

**Code :** `data.synthese.generer_corpus`.

Pavages 2×2 dans une enveloppe 12 m × 9 m, identifiants `syn-0000` … `syn-0089`.
Graine obligatoire. Sert de substitut CI aux corpus immobiliers non
redistribuables.

Découpage figé : `splits/v1/{train,calibration,test}.txt` (54 / 18 / 18).
`syn-0053` reprend la géométrie de `syn-0000` (même split train) pour le test
de déduplication trans-frontière.

Ce n'est **pas** un sDA mesuré. Le score vient de `SimulateurExact`
(analytique CIBSE + split-flux BRE ; Radiance hors chemin critique).
