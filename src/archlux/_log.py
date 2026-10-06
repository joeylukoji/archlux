"""Structured debug events, silent unless the application turns logging on.

PLAN.md phase 4, block 17, item 47. Events go to the standard :mod:`logging` module,
at ``DEBUG`` level, under the ``archlux.<package>`` logger names: a library must not
print by default, nor configure the application's logging. ``structlog`` is not
imported here (it costs about 0.4 s and, unconfigured, prints every event to stdout);
an application that uses it can route standard logging through it.

Each record carries the event name and its fields twice: as attributes
(``record.event``, ``record.fields``) for structured handlers, and in the message as
``event key=value ...`` for plain ones. Fields are formatted only when the logger is
enabled, so a disabled event costs one level check.

This module imports only ``logging``: every layer may depend on it.
"""

from __future__ import annotations

import logging

__all__ = ["event"]


def event(logger: str, name: str, **fields: object) -> None:
    """Emit one structured ``DEBUG`` event.

    Parameters
    ----------
    logger
        Logger name, ``archlux.<package>`` by convention.
    name
        Event name, dotted (``"frank_wolfe.iteration"``).
    **fields
        Values attached to the event.

    Examples
    --------
    >>> event("archlux.solve", "frank_wolfe.stop", status="converged", iterations=3)
    """
    log = logging.getLogger(logger)
    if not log.isEnabledFor(logging.DEBUG):
        return
    text = " ".join(f"{key}={value!r}" for key, value in sorted(fields.items()))
    log.debug("%s %s", name, text, extra={"event": name, "fields": dict(fields)})
