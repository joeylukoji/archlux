"""Substitut appris — seul module du projet autorisé à importer ``torch``.

L'import est local et paresseux : ``import archlux`` ne doit jamais charger ``torch``,
et ``tests/test_dependances.py`` en fait un test bloquant de la CI.

Ce module ne connaît ni ``geom``, ni ``lmo``, ni ``solve`` : il ne voit qu'un vecteur et
une orientation, et rend un nombre, un gradient et une incertitude.

Tant que les poids sont un ``npz`` du perceptron (:class:`~archlux.light.base.DenseSurrogate`),
``torch`` n'est pas chargé. Un fichier ``.pt`` déclenche le transformeur.

État réel du transformeur
-------------------------
**Il n'existe pas.** Aucune architecture, aucun poids, aucun entraînement dans ce dépôt.
:meth:`SubstitutAppris._charger_torch` lève **toujours**
:class:`~archlux.errors.InvariantViolation`, quel que soit le contenu du ``.pt`` : son
type de retour est ``NoReturn``, et le contrôle
de taille contre :data:`MAX_PARAMETRES` qu'elle exécute d'abord ne peut donc que changer
le message d'erreur, jamais laisser passer un modèle. Le seul substitut appris réellement
servi par :class:`LearnedSurrogate` est le perceptron numpy de
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
from typing import TYPE_CHECKING, NoReturn

from archlux._deprecation import Alias, lazy_aliases, renamed_attributes
from archlux.errors import InvariantViolation
from archlux.light.base import DenseSurrogate
from archlux.light.protocol import Glazing
from archlux.types import Indicator

if TYPE_CHECKING:
    import numpy as np

    from archlux.types import Indicator, Orientation

__all__ = ["MAX_PARAMETERS", "LearnedSurrogate"]

MAX_PARAMETERS = 2_000_000
"""Plafond `MILESTONE-4.md` : au-delà, le modèle mémorise hors distribution."""


@lru_cache(maxsize=8)
def _dense_from_disk(path: str, fingerprint: str) -> DenseSurrogate:
    """Charger un ``npz`` une fois par ``(chemin, empreinte)``, après contrôle SHA-256."""
    current = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if current != fingerprint:
        raise InvariantViolation((f"empreinte des poids divergente pour {path}",))
    return DenseSurrogate.load(Path(path))


@renamed_attributes(
    {
        "chemin_poids": "weights_path",
        "empreinte_poids": "weights_fingerprint",
        "gele": "frozen",
        "indicateur_vise": "target_indicator",
    }
)
@dataclass(frozen=True, slots=True)
class LearnedSurrogate:
    """Tête publique du substitut entraîné.

    Attributes
    ----------
    empreinte_poids : str
        ``sha256`` des poids, reporté dans le manifeste. Sans lui, un résultat publié
        n'est pas reproductible.
    gele : bool
        Une fois les poids gelés, l'accès au jeu de calibration devient possible — et
        pas avant (voir :mod:`archlux.uq.registry`).
    """

    weights_path: Path
    weights_fingerprint: str
    frozen: bool = False
    target_indicator: Indicator = "sDA"

    @property
    def indicator(self) -> Indicator:
        """Nom de l'indicateur modélisé."""
        return self.target_indicator

    def _backend(self) -> DenseSurrogate:
        path = Path(self.weights_path)
        if path.suffix.lower() == ".pt":
            self._load_torch()
        return _dense_from_disk(str(path.resolve()), self.weights_fingerprint)

    def _load_torch(self) -> NoReturn:
        """Refuser un ``.pt``. ``torch`` n'est importé qu'ici, et seulement alors.

        Lève **inconditionnellement** : le transformeur n'existe pas (voir l'en-tête du
        module). Le contrôle contre :data:`MAX_PARAMETRES` est conservé pour que
        l'erreur nomme la vraie cause quand le fichier est aussi hors gabarit, mais il
        ne conditionne aucun chemin de succès.
        """
        import torch

        state = torch.load(self.weights_path, map_location="cpu", weights_only=True)
        n_params = int(sum(p.numel() for p in state.values())) if isinstance(state, dict) else 0
        if n_params >= MAX_PARAMETERS:
            raise InvariantViolation((f"modèle trop grand : {n_params} ≥ {MAX_PARAMETERS}",))
        raise InvariantViolation(
            ("poids .pt : le transformeur n'est servi que hors CI ; utiliser un npz dense",)
        )

    def evaluate(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Estimer l'indicateur. Charge ``torch`` seulement pour un fichier ``.pt``."""
        return self._backend().evaluate(x, orientation, glazing=glazing)

    def gradient(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> np.ndarray:
        """Gradient par différences finies du backend, ramené en ``numpy``."""
        return self._backend().gradient(x, orientation, glazing=glazing)

    def uncertainty(
        self, x: np.ndarray, orientation: Orientation, *, glazing: Glazing | None = None
    ) -> float:
        """Écart-type prédictif appris."""
        return self._backend().uncertainty(x, orientation, glazing=glazing)

    def n_parameters(self) -> int:
        """Taille du modèle chargé."""
        return self._backend().n_parameters()


__getattr__ = lazy_aliases(
    __name__,
    {
        "MAX_PARAMETRES": Alias(MAX_PARAMETERS, "archlux.light.learned.MAX_PARAMETERS"),
        "SubstitutAppris": Alias(LearnedSurrogate, "archlux.light.learned.LearnedSurrogate"),
    },
)
