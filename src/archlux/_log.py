"""Structured debug events, silent unless the application turns logging on.

PLAN.md phase 4, block 17, item 47. Events go to the standard :mod:`logging` module,
at ``DEBUG`` level, under the ``archlux.<package>`` logger names: a library must not
print by default, nor configure the application's logging. ``structlog`` is not
imported here (it costs about 0.4 s and, unconfigured, prints every event to stdout);
an application that uses it can route standard logging through it.

Each record carries the event name and its fields twice: as attributes
(``record.event``, ``record.fields``) for structured handlers, and in the message as
``event key=value ...`` for plain ones. Fields are formatted only when the logger is
enabled, and loggers are cached per name, so a disabled event costs a dictionary
lookup and a level check (about a microsecond), negligible next to an LP solve.

This module imports only ``logging``: every layer may depend on it.
"""

from __future__ import annotations

import logging

__all__ = ["event"]

_LOGGERS: dict[str, logging.Logger] = {}
"""Loggers by name: ``logging.getLogger`` takes a lock on every call."""


def event(logger: str, name: str, *, level: int = logging.DEBUG, **fields: object) -> None:
    """Emit one structured event, ``DEBUG`` unless ``level`` says otherwise.

    Parameters
    ----------
    logger
        Logger name, ``archlux.<package>`` by convention.
    name
        Event name, dotted (``"frank_wolfe.iteration"``).
    level
        Logging level. ``logging.WARNING`` for a condition the caller should see
        (standard logging shows warnings on stderr when nothing is configured).
    **fields
        Values attached to the event.

    Examples
    --------
    >>> event("archlux.solve", "frank_wolfe.stop", status="converged", iterations=3)
    """
    log = _LOGGERS.get(logger)
    if log is None:
        log = _LOGGERS.setdefault(logger, logging.getLogger(logger))
    if not log.isEnabledFor(level):
        return
    text = " ".join(f"{key}={value!r}" for key, value in sorted(fields.items()))
    log.log(level, "%s %s", name, text, extra={"event": name, "fields": dict(fields)})
