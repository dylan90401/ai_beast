"""
Lightweight in-process event bus.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def on(self, name: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def emit(self, name: str, payload: dict[str, Any]) -> None:
        for handler in self._handlers.get(name, []):
            handler(payload)
