"""Structured logging configuration for AI Beast.

Uses structlog for structured, context-rich logging with
support for both console and JSON output formats.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TextIO

import structlog


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    log_file: Path | None = None,
    colors: bool = True,
) -> None:
    """Configure structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Whether to output JSON format
        log_file: Optional file to log to
        colors: Whether to use colors in console output
    """
    # Determine output stream
    stream: TextIO = sys.stderr
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        stream = open(log_file, "a")  # noqa: SIM115

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=stream,
        level=getattr(logging, level.upper()),
        force=True,
    )

    # Configure structlog processors
    processors: list[structlog.types.Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=colors))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def configure_from_context(
    verbose: bool = False,
    json_output: bool = False,
    log_dir: Path | None = None,
) -> None:
    """Configure logging from application context.

    Args:
        verbose: Enable verbose (DEBUG) logging
        json_output: Use JSON output format
        log_dir: Directory for log files
    """
    level = "DEBUG" if verbose else "INFO"
    log_file = None
    if log_dir is not None:
        log_file = log_dir / "ai_beast.log"

    configure_logging(
        level=level,
        json_output=json_output,
        log_file=log_file,
        colors=not json_output,
    )


# Usage example:
# from modules.logging_config import get_logger
#
# logger = get_logger(__name__)
#
# logger.info("model_downloaded",
#             model_name="llama-3.2-3b",
#             size_bytes=2_000_000_000,
#             duration_ms=45000,
#             location="internal")
