"""Compatibility shim.

Prefer importing `get_logger` from `modules.utils.logging_config`.
This file exists to keep legacy imports working.
"""

from __future__ import annotations

from modules.utils.logging_config import get_logger

__all__ = ["get_logger"]
