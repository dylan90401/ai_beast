"""
Lightweight dependency container.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class Container:
    """Minimal DI container with singleton providers."""

    def __init__(self) -> None:
        self._providers: dict[str, Callable[[], Any]] = {}
        self._instances: dict[str, Any] = {}

    def register(self, name: str, provider: Callable[[], Any]) -> None:
        if not name:
            raise ValueError("name is required")
        self._providers[name] = provider

    def register_instance(self, name: str, instance: Any) -> None:
        if not name:
            raise ValueError("name is required")
        self._instances[name] = instance

    def get(self, name: str) -> Any:
        if name in self._instances:
            return self._instances[name]
        provider = self._providers.get(name)
        if not provider:
            raise KeyError(f"no provider for {name}")
        instance = provider()
        self._instances[name] = instance
        return instance
