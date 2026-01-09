"""
Resilience module for AI Beast.

Provides fault tolerance patterns including circuit breakers,
retries, and fallback mechanisms.
"""

from __future__ import annotations

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitState",
    "circuit_breaker",
    "get_circuit_breaker",
]
