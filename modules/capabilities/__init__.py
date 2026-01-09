"""
Capability registry for AI Beast.

Defines high-level capabilities (text→image/video/audio/music, RAG, code runner)
and provides validation checks with safe defaults.
"""

from .registry import (  # noqa: F401
    list_capabilities,
    load_capabilities,
    run_capability_checks,
)
