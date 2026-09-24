# Installation

```bash
pip install archlux                # noyau : aucune dépendance d'apprentissage
pip install "archlux[appris]"      # + substitut entraîné (torch)
pip install "archlux[ml]"          # alias de ``appris``
# ``archlux[sim]`` : extra vide (Radiance). Hors chemin critique ; la CI
# utilise ``OracleSplitFlux`` (forme fermée).
```

Python 3.11 ou supérieur. Le noyau n'importe jamais `torch` : `import archlux` reste
léger, même avec l'extra installé.
