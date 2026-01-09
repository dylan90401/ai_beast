"""
Event bus foundation for lightweight, in-process event dispatch.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def subscribe(self, event: str, handler: Callable[[dict[str, Any]], None]) -> None:
        if not event:
            raise ValueError("event is required")
        self._handlers.setdefault(event, []).append(handler)

    def publish(self, event: str, payload: dict[str, Any] | None = None) -> None:
        for handler in self._handlers.get(event, []):
            handler(payload or {})

    async def publish_async(self, event: str, payload: dict[str, Any] | None = None) -> None:
        for handler in self._handlers.get(event, []):
            handler(payload or {})
