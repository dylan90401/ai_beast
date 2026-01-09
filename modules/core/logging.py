"""
Structured logging helpers using structlog when available.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import structlog
except ImportError:  # pragma: no cover - falls back when structlog missing.
    structlog = None  # type: ignore[assignment]


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    if structlog:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


def get_logger(name: str) -> Any:
    if structlog:
        return structlog.get_logger(name)
    return logging.getLogger(name)
