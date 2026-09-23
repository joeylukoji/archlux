"""Jeu de calibration : trois répertoires, un jeton après gel des poids.

`ARCHITECTURE.md` §10 : lire la calibration à l'entraînement rend la couverture
conforme fausse, et **rien ne le signale**. Le jeton est la barrière structurelle.

Portée réelle de la barrière
----------------------------
Le jeton est une **discipline vérifiable, pas un verrou inviolable**. Il faut le dire
tel quel dans toute publication ; le présenter comme une preuve serait une garantie de
plus que le code ne tient pas. Les contournements connus, tous à une ligne :

1. :func:`emettre_jeton` est publique et accepte n'importe quelle empreinte et n'importe
   quel horodatage. Rien n'atteste que le gel a eu lieu, ni qu'il précède l'ouverture.
2. :meth:`JetonCalibration.verifier` recalcule ``blake2b(empreinte|horodatage)`` : c'est
   une **somme de contrôle non clefée**, pas une signature. Elle détecte une corruption,
   jamais une falsification — le matériau est entièrement dans le jeton.
3. :attr:`GestionDonnees.racine` est un champ public : ``gestion.racine / "calibration"``
   ouvre le répertoire sans passer par :meth:`GestionDonnees.pour_calibration`.
4. ``modele`` est **facultatif** dans :meth:`GestionDonnees.pour_calibration` ; omis,
   aucune empreinte n'est comparée et le jeton n'est plus lié à quoi que ce soit.
5. :class:`archlux.uq.conforme.CalibrateurConforme` calibre à partir de tableaux nus :
   le chemin qui produit réellement la garantie n'exige aucun jeton, et ni
   :class:`~archlux.uq.conforme.Calibration` ni
   :class:`archlux.types.BornePerformance` ne transportent celui-ci jusqu'au certificat.

Ce que le dispositif apporte malgré tout : un accès accidentel devient bruyant, et
l'empreinte des poids devient publiable avec le résultat. Rendre la barrière réelle
demanderait une clef détenue hors du dépôt (HMAC ou signature) et un horodatage attesté
par un tiers, plus la propagation du jeton jusqu'à ``BornePerformance``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from archlux.erreurs import CalibrationVerrouillee, InvariantViole, ModeleModifie

__all__ = [
    "GestionDonnees",
    "JetonCalibration",
    "emettre_jeton",
    "geler_et_emettre",
    "ouvrir_calibration",
]


@dataclass(frozen=True, slots=True)
class JetonCalibration:
    """Preuve que les poids étaient gelés avant tout accès à la calibration."""

    empreinte_poids: str
    horodatage_gel: str
    signature: str

    def verifier(self) -> None:
        """Rejeter un jeton dont la signature ne correspond pas au gel annoncé.

        Contrôle d'**intégrité**, pas d'authenticité : la signature est un ``blake2b``
        non clefé des deux champs publics du jeton, donc reproductible par quiconque
        via :func:`emettre_jeton`. Voir la portée réelle en tête de module.
        """
        attendu = emettre_jeton(self.empreinte_poids, self.horodatage_gel)
        if self.signature != attendu.signature:
            raise CalibrationVerrouillee("signature du jeton de calibration invalide")


def _empreinte_modele(modele: object) -> str:
    """Empreinte sha256 des poids, sans importer ``torch`` ni ``light``."""
    explicite = getattr(modele, "empreinte_poids", None)
    if isinstance(explicite, str) and explicite:
        return explicite
    tampons: list[bytes] = []
    poids = getattr(modele, "poids", None)
    if isinstance(poids, np.ndarray):
        tampons.append(np.ascontiguousarray(poids, dtype=float).tobytes())
    for nom in ("W1", "b1", "W2", "b2", "W3"):
        val = getattr(modele, nom, None)
        if isinstance(val, np.ndarray):
            tampons.append(np.ascontiguousarray(val, dtype=float).tobytes())
    b3 = getattr(modele, "b3", None)
    if isinstance(b3, (int, float)):
        tampons.append(np.asarray(float(b3), dtype=float).tobytes())
    if not tampons:
        raise InvariantViole(("modèle sans poids hashables : impossible de geler",))
    return hashlib.sha256(b"".join(tampons)).hexdigest()


def geler_et_emettre(modele: object, *, horodatage: str | None = None) -> JetonCalibration:
    """Émettre le jeton **après** gel des poids, jamais avant.

    Parameters
    ----------
    modele : object
        Substitut dont les poids (tableaux numpy ``poids`` / ``W*``) sont gelés.
        Un attribut ``empreinte_poids`` déjà calculé est utilisé tel quel.
    horodatage : str or None, optional
        Instant ISO 8601 UTC. Défaut : maintenant, fuseau UTC.

    Returns
    -------
    JetonCalibration
        Jeton dont l'empreinte devra encore correspondre à l'ouverture du jeu.
    """
    instant = (
        horodatage if horodatage is not None else datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    return emettre_jeton(_empreinte_modele(modele), instant)


def emettre_jeton(empreinte_poids: str, horodatage_gel: str) -> JetonCalibration:
    """Émettre un jeton pour un modèle gelé.

    Parameters
    ----------
    empreinte_poids : str
        ``sha256`` des poids gelés.
    horodatage_gel : str
        Instant du gel, ISO 8601 UTC.

    Returns
    -------
    JetonCalibration
        Jeton déterministe : mêmes arguments, même signature.
    """
    if not empreinte_poids or not horodatage_gel:
        raise InvariantViole(("empreinte et horodatage de gel sont obligatoires",))
    materiau = f"{empreinte_poids}|{horodatage_gel}".encode()
    signature = hashlib.blake2b(materiau, digest_size=16).hexdigest()
    return JetonCalibration(empreinte_poids, horodatage_gel, signature)


def ouvrir_calibration(racine: Path, jeton: JetonCalibration) -> Path:
    """Ouvrir le répertoire de calibration, jeton valide exigé.

    Raises
    ------
    CalibrationVerrouillee
        Jeton absent, invalide, ou répertoire manquant.
    """
    jeton.verifier()
    dossier = Path(racine) / "calibration"
    if not dossier.is_dir():
        raise CalibrationVerrouillee(f"répertoire de calibration absent : {dossier}")
    return dossier


@dataclass(frozen=True, slots=True)
class GestionDonnees:
    """Trois répertoires séparés. Seul ``pour_calibration`` exige un jeton."""

    racine: Path

    def pour_entrainement(self) -> Path:
        """Répertoire ``train/`` — seul chemin exposé pour ajuster les poids."""
        dossier = Path(self.racine) / "train"
        if not dossier.is_dir():
            raise InvariantViole((f"répertoire d'entraînement absent : {dossier}",))
        return dossier

    def pour_test(self) -> Path:
        """Répertoire ``test/``, ouvert une seule fois pour la mesure finale."""
        dossier = Path(self.racine) / "test"
        if not dossier.is_dir():
            raise InvariantViole((f"répertoire de test absent : {dossier}",))
        return dossier

    def pour_calibration(self, jeton: JetonCalibration, modele: object | None = None) -> Path:
        """Répertoire ``calibration/``, uniquement après gel du modèle.

        Parameters
        ----------
        jeton : JetonCalibration
            Preuve du gel.
        modele : object or None, optional
            Si fourni, son empreinte actuelle doit coincider avec celle du jeton.
        """
        if modele is not None and _empreinte_modele(modele) != jeton.empreinte_poids:
            raise ModeleModifie("poids du modèle modifiés après le gel")
        return ouvrir_calibration(self.racine, jeton)
