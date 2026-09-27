"""Calibration set: three directories, one token after the weights are frozen.

`ARCHITECTURE.md` §10: reading the calibration set at training time makes the
conformal coverage false, and **nothing signals it**. The token is the structural
barrier.

Real scope of the barrier
--------------------------
The token is a **verifiable discipline, not an inviolable lock**. Say so plainly in
any publication; presenting it as a proof would be one guarantee more than the code
actually holds. The known bypasses, all one line each:

1. :func:`issue_token` is public and accepts any fingerprint and any timestamp.
   Nothing attests that the freeze actually happened, nor that it precedes the
   opening.
2. :meth:`CalibrationToken.verify` recomputes ``blake2b(fingerprint|timestamp)``:
   this is an **unkeyed checksum**, not a signature. It detects corruption, never
   forgery — the material is entirely inside the token.
3. :attr:`DataManagement.racine` is a public field: ``gestion.racine / "calibration"``
   opens the directory without going through :meth:`DataManagement.for_calibration`.
4. ``model`` is **optional** in :meth:`DataManagement.for_calibration`; omitted, no
   fingerprint is compared and the token is no longer bound to anything.
5. :class:`archlux.uq.conforme.ConformalCalibrator` calibrates from raw arrays: the
   path that actually produces the guarantee requires no token at all, and neither
   :class:`~archlux.uq.conforme.Calibration` nor
   :class:`archlux.types.PerformanceBound` carries it through to the certificate.

What the mechanism does bring anyway: accidental access becomes noisy, and the
weights' fingerprint becomes publishable with the result. Making the barrier real
would need a key held outside the repository (HMAC or signature) and a timestamp
attested by a third party, plus propagating the token all the way to
``PerformanceBound``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from archlux._deprecation import Alias, lazy_aliases
from archlux.errors import CalibrationLocked, InvariantViolation, ModelModified

__all__ = [
    "CalibrationToken",
    "DataManagement",
    "freeze_and_issue",
    "issue_token",
    "open_calibration",
]


@dataclass(frozen=True, slots=True)
class CalibrationToken:
    """Proof that the weights were frozen before any access to the calibration set."""

    weights_fingerprint: str
    freeze_timestamp: str
    signature: str

    def verify(self) -> None:
        """Reject a token whose signature does not match the announced freeze.

        **Integrity** check, not authenticity: the signature is an unkeyed
        ``blake2b`` of the token's two public fields, hence reproducible by anyone
        via :func:`issue_token`. See the real scope at the top of the module.
        """
        expected = issue_token(self.weights_fingerprint, self.freeze_timestamp)
        if self.signature != expected.signature:
            raise CalibrationLocked("invalid calibration token signature")


def _model_fingerprint(model: object) -> str:
    """SHA-256 fingerprint of the weights, without importing ``torch`` or ``light``."""
    explicit = getattr(model, "weights_fingerprint", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    buffers: list[bytes] = []
    weights = getattr(model, "weights", None)
    if isinstance(weights, np.ndarray):
        buffers.append(np.ascontiguousarray(weights, dtype=float).tobytes())
    for name in ("W1", "b1", "W2", "b2", "W3"):
        val = getattr(model, name, None)
        if isinstance(val, np.ndarray):
            buffers.append(np.ascontiguousarray(val, dtype=float).tobytes())
    b3 = getattr(model, "b3", None)
    if isinstance(b3, (int, float)):
        buffers.append(np.asarray(float(b3), dtype=float).tobytes())
    if not buffers:
        raise InvariantViolation(("model has no hashable weights: cannot freeze",))
    return hashlib.sha256(b"".join(buffers)).hexdigest()


def freeze_and_issue(model: object, *, timestamp: str | None = None) -> CalibrationToken:
    """Issue the token **after** the weights are frozen, never before.

    Parameters
    ----------
    model : object
        Surrogate whose weights (numpy arrays ``weights`` / ``W*``) are frozen. An
        already computed ``weights_fingerprint`` attribute is used as is.
    timestamp : str or None, optional
        ISO 8601 UTC instant. Default: now, UTC timezone.

    Returns
    -------
    CalibrationToken
        Token whose fingerprint will still have to match at the opening of the set.
    """
    instant = (
        timestamp if timestamp is not None else datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    return issue_token(_model_fingerprint(model), instant)


def issue_token(weights_fingerprint: str, freeze_timestamp: str) -> CalibrationToken:
    """Issue a token for a frozen model.

    Parameters
    ----------
    weights_fingerprint : str
        ``sha256`` of the frozen weights.
    freeze_timestamp : str
        Instant of the freeze, ISO 8601 UTC.

    Returns
    -------
    CalibrationToken
        Deterministic token: same arguments, same signature.
    """
    if not weights_fingerprint or not freeze_timestamp:
        raise InvariantViolation(("freeze fingerprint and timestamp are both mandatory",))
    material = f"{weights_fingerprint}|{freeze_timestamp}".encode()
    signature = hashlib.blake2b(material, digest_size=16).hexdigest()
    return CalibrationToken(weights_fingerprint, freeze_timestamp, signature)


def open_calibration(racine: Path, token: CalibrationToken) -> Path:
    """Open the calibration directory; a valid token is required.

    Raises
    ------
    CalibrationLocked
        Missing or invalid token, or missing directory.
    """
    token.verify()
    dossier = Path(racine) / "calibration"
    if not dossier.is_dir():
        raise CalibrationLocked(f"missing calibration directory: {dossier}")
    return dossier


@dataclass(frozen=True, slots=True)
class DataManagement:
    """Three separate directories. Only ``for_calibration`` requires a token."""

    racine: Path

    def for_training(self) -> Path:
        """``train/`` directory — the only exposed path to fit the weights."""
        dossier = Path(self.racine) / "train"
        if not dossier.is_dir():
            raise InvariantViolation((f"missing training directory: {dossier}",))
        return dossier

    def for_test(self) -> Path:
        """``test/`` directory, opened only once for the final measurement."""
        dossier = Path(self.racine) / "test"
        if not dossier.is_dir():
            raise InvariantViolation((f"missing test directory: {dossier}",))
        return dossier

    def for_calibration(self, token: CalibrationToken, model: object | None = None) -> Path:
        """``calibration/`` directory, only after the model is frozen.

        Parameters
        ----------
        token : CalibrationToken
            Proof of the freeze.
        model : object or None, optional
            If given, its current fingerprint must match the token's.
        """
        if model is not None and _model_fingerprint(model) != token.weights_fingerprint:
            raise ModelModified("model weights changed after the freeze")
        return open_calibration(self.racine, token)


__getattr__ = lazy_aliases(
    __name__,
    {
        "GestionDonnees": Alias(DataManagement, "archlux.uq.gestion.DataManagement"),
        "JetonCalibration": Alias(CalibrationToken, "archlux.uq.gestion.CalibrationToken"),
        "emettre_jeton": Alias(issue_token, "archlux.uq.gestion.issue_token"),
        "geler_et_emettre": Alias(  # lang-ok: French alias name
            freeze_and_issue, "archlux.uq.gestion.freeze_and_issue"
        ),
        "ouvrir_calibration": Alias(open_calibration, "archlux.uq.gestion.open_calibration"),
    },
)
