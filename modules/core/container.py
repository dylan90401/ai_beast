"""
Minimal dependency injection container.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Container:
    def __init__(self) -> None:
        self._providers: dict[str, Callable[[], Any]] = {}
        self._singletons: dict[str, Any] = {}

    def register(
        self, name: str, provider: Callable[[], Any], *, singleton: bool = True
    ) -> None:
        self._providers[name] = (provider, singleton)

    def resolve(self, name: str) -> Any:
        if name in self._singletons:
            return self._singletons[name]
        if name not in self._providers:
            raise KeyError(f"Unknown dependency: {name}")
        provider, singleton = self._providers[name]
        value = provider()
        if singleton:
            self._singletons[name] = value
        return value
