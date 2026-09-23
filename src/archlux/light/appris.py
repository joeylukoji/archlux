"""Substitut appris — seul module du projet autorisé à importer ``torch``.

L'import est local et paresseux : ``import archlux`` ne doit jamais charger ``torch``,
et ``tests/test_dependances.py`` en fait un test bloquant de la CI.

Ce module ne connaît ni ``geom``, ni ``lmo``, ni ``solve`` : il ne voit qu'un vecteur et
une orientation, et rend un nombre, un gradient et une incertitude.

Tant que les poids sont un ``npz`` du perceptron (:class:`~archlux.light.base.SubstitutDense`),
``torch`` n'est pas chargé. Un fichier ``.pt`` déclenche le transformeur.

État réel du transformeur
-------------------------
**Il n'existe pas.** Aucune architecture, aucun poids, aucun entraînement dans ce dépôt.
:meth:`SubstitutAppris._charger_torch` lève **toujours** :class:`~archlux.erreurs.InvariantViole`,
quel que soit le contenu du ``.pt`` : son type de retour est ``NoReturn``, et le contrôle
de taille contre :data:`MAX_PARAMETRES` qu'elle exécute d'abord ne peut donc que changer
le message d'erreur, jamais laisser passer un modèle. Le seul substitut appris réellement
servi par :class:`SubstitutAppris` est le perceptron numpy de
:mod:`archlux.light.base`, chargé depuis un ``npz``.

Conséquence pour la lecture des résultats : tout chiffre de « substitut appris » produit
par ce dépôt vient du perceptron dense sur descripteurs, jamais d'un transformeur sur
jetons. Le jalon 4 décrit une cible, pas un état livré.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn

from archlux.erreurs import InvariantViole
from archlux.light.base import SubstitutDense
from archlux.light.protocole import Baies

if TYPE_CHECKING:
    import numpy as np

    from archlux.types import Orientation

__all__ = ["MAX_PARAMETRES", "SubstitutAppris"]

MAX_PARAMETRES = 2_000_000
"""Plafond `MILESTONE-4.md` : au-delà, le modèle mémorise hors distribution."""


@lru_cache(maxsize=8)
def _dense_depuis_disque(chemin: str, empreinte: str) -> SubstitutDense:
    """Charger un ``npz`` une fois par ``(chemin, empreinte)``, après contrôle SHA-256."""
    actuel = hashlib.sha256(Path(chemin).read_bytes()).hexdigest()
    if actuel != empreinte:
        raise InvariantViole((f"empreinte des poids divergente pour {chemin}",))
    return SubstitutDense.charger(Path(chemin))


@dataclass(frozen=True, slots=True)
class SubstitutAppris:
    """Tête publique du substitut entraîné.

    Attributes
    ----------
    empreinte_poids : str
        ``sha256`` des poids, reporté dans le manifeste. Sans lui, un résultat publié
        n'est pas reproductible.
    gele : bool
        Une fois les poids gelés, l'accès au jeu de calibration devient possible — et
        pas avant (voir :mod:`archlux.uq.gestion`).
    """

    chemin_poids: Path
    empreinte_poids: str
    gele: bool = False
    indicateur_vise: Literal["sDA", "ASE", "UDI", "vue"] = "sDA"

    @property
    def indicateur(self) -> str:
        """Nom de l'indicateur modélisé."""
        return self.indicateur_vise

    def _backend(self) -> SubstitutDense:
        chemin = Path(self.chemin_poids)
        if chemin.suffix.lower() == ".pt":
            self._charger_torch()
        return _dense_depuis_disque(str(chemin.resolve()), self.empreinte_poids)

    def _charger_torch(self) -> NoReturn:
        """Refuser un ``.pt``. ``torch`` n'est importé qu'ici, et seulement alors.

        Lève **inconditionnellement** : le transformeur n'existe pas (voir l'en-tête du
        module). Le contrôle contre :data:`MAX_PARAMETRES` est conservé pour que
        l'erreur nomme la vraie cause quand le fichier est aussi hors gabarit, mais il
        ne conditionne aucun chemin de succès.
        """
        import torch

        etat = torch.load(self.chemin_poids, map_location="cpu", weights_only=True)
        n_params = int(sum(p.numel() for p in etat.values())) if isinstance(etat, dict) else 0
        if n_params >= MAX_PARAMETRES:
            raise InvariantViole((f"modèle trop grand : {n_params} ≥ {MAX_PARAMETRES}",))
        raise InvariantViole(
            ("poids .pt : le transformeur n'est servi que hors CI ; utiliser un npz dense",)
        )

    def evaluer(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """Estimer l'indicateur. Charge ``torch`` seulement pour un fichier ``.pt``."""
        return self._backend().evaluer(x, orientation, baies=baies)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> np.ndarray:
        """Gradient par différences finies du backend, ramené en ``numpy``."""
        return self._backend().gradient(x, orientation, baies=baies)

    def incertitude(
        self, x: np.ndarray, orientation: Orientation, *, baies: Baies | None = None
    ) -> float:
        """Écart-type prédictif appris."""
        return self._backend().incertitude(x, orientation, baies=baies)

    def n_parametres(self) -> int:
        """Taille du modèle chargé."""
        return self._backend().n_parametres()
