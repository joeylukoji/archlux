"""Graines dérivées et manifeste : ce qui rend une exécution rejouable.

`ARCHITECTURE.md` §7 exige une graine obligatoire sans défaut, et le README un manifeste
à chaque exécution. Ces deux exigences n'ont de valeur que si elles sont testées.
"""

from __future__ import annotations

import datetime as dt

import pytest

from archlux.bench.manifest import emit
from archlux.bench.seeds import derive


class TestDeriver:
    """Dérivation de sous-graines nommées à partir d'une graine racine."""

    def test_est_deterministe(self) -> None:
        """Deux appels identiques rendent la même sous-graine."""
        assert derive(17, "calibration") == derive(17, "calibration")

    def test_deux_flux_ne_partagent_pas_leur_alea(self) -> None:
        """Le point de la dérivation : `calibration` et `permutation` divergent.

        Sans cela, deux composantes tirent la même suite et leurs résultats sont
        corrélés sans que rien ne le montre.
        """
        assert derive(17, "calibration") != derive(17, "permutation")

    def test_deux_executions_ne_partagent_pas_leur_alea(self) -> None:
        """Changer la graine racine change tous les flux."""
        assert derive(17, "calibration") != derive(18, "calibration")

    def test_rend_une_graine_utilisable(self) -> None:
        """Un entier positif, dans la plage acceptée par ``numpy.random``."""
        graine = derive(17, "calibration")
        assert isinstance(graine, int)
        assert 0 <= graine < 2**32

    @pytest.mark.parametrize(
        ("name", "attendu"),
        [
            ("calibration", 313_024_199),
            ("permutation", 2_943_214_233),
            ("entrainement", 2_097_524_390),
        ],
    )
    def test_les_valeurs_sont_gelees(self, name: str, attendu: int) -> None:
        """Valeurs **épinglées** : changer la dérivation change tous les résultats publiés.

        Ce test n'a pas de source de vérité externe — il ne peut pas en avoir. Son rôle
        est d'obliger à toucher ce fichier, donc à voir la rupture en revue, le jour où
        quelqu'un modifie la fonction de hachage. Une exécution archivée doit rester
        rejouable ; ces trois nombres sont ce qui l'exige.
        """
        assert derive(17, name) == attendu


class TestManifeste:
    """Manifeste de reproductibilité émis à chaque exécution."""

    def test_reporte_la_graine(self) -> None:
        """La graine est la première chose qu'on relit six mois plus tard."""
        assert emit(seed=17).seed == 17

    def test_la_graine_est_obligatoire(self) -> None:
        """Aucune valeur par défaut : une graine implicite est une graine perdue."""
        with pytest.raises(TypeError):
            emit()  # type: ignore[call-arg]

    def test_horodatage_utc_lisible(self) -> None:
        """L'horodatage est de l'ISO 8601 en UTC, pas une heure locale ambiguë."""
        horodatage = emit(seed=17).timestamp
        instant = dt.datetime.fromisoformat(horodatage)
        assert instant.tzinfo is not None
        assert instant.utcoffset() == dt.timedelta(0)

    def test_reporte_l_environnement(self) -> None:
        """La version de Python figure au manifeste ; sans elle il n'identifie rien."""
        environnement = dict(emit(seed=17).environment)
        assert "python" in environnement

    def test_les_parametres_sont_geles_et_ordonnes(self) -> None:
        """Les paramètres deviennent des paires triées : l'empreinte doit être stable."""
        manifeste = emit(seed=17, parameters={"max_iter": "50", "budget": "0.25"})
        assert manifeste.parameters == (("budget", "0.25"), ("max_iter", "50"))
