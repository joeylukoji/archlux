# Installation

```bash
pip install archlux                # core: no learning dependency
pip install "archlux[appris]"      # + trained surrogate (torch)
pip install "archlux[ml]"          # alias of ``appris``
# ``archlux[sim]``: empty extra (Radiance). Off the critical path; CI
# uses ``SplitFluxOracle`` (closed form).
```

Python 3.11 ou supérieur. Le noyau n'importe jamais `torch` : `import archlux` reste
léger, même avec l'extra installé.
