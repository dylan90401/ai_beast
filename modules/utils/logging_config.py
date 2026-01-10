"""Logging helpers.

This repo uses structured logging patterns (e.g. ``logger.info("event", key=value)``).
To keep the codebase resilient, we support:
- `structlog` when installed (preferred)
- a lightweight stdlib fallback when it is not

The fallback preserves the call signature used across modules.
"""

from __future__ import annotations

import logging
from typing import Any


_CONFIGURED = False


def _ensure_configured() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _CONFIGURED = True


def _format_event(event: str, kwargs: dict[str, Any]) -> str:
    if not kwargs:
        return event
    parts = [event]
    for key in sorted(kwargs.keys()):
        value = kwargs[key]
        parts.append(f"{key}={value!r}")
    return " ".join(parts)


class _KVLogger:
    """Stdlib logger shim that mimics structlog-style kwargs."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def debug(self, event: str, **kwargs: Any) -> None:
        self._logger.debug(_format_event(event, kwargs))

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info(_format_event(event, kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning(_format_event(event, kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error(_format_event(event, kwargs))

    def exception(self, event: str, **kwargs: Any) -> None:
        self._logger.exception(_format_event(event, kwargs))


def get_logger(name: str):
    """Return a logger compatible with the repo's structured logging style."""
    _ensure_configured()

    try:
        import structlog  # type: ignore

        return structlog.get_logger(name)
    except Exception:
        return _KVLogger(logging.getLogger(name))
