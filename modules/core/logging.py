"""
Structured logging helpers.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

try:
    import structlog
except Exception:  # pragma: no cover - optional fallback
    structlog = None

_configured = False


def init_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
    )
    if structlog:
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    _configured = True


def get_logger(name: str | None = None) -> Any:
    init_logging()
    if structlog:
        return structlog.get_logger(name or "ai_beast")
    return logging.getLogger(name or "ai_beast")
