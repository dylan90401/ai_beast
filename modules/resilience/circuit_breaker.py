"""
Circuit breaker pattern implementation for fault tolerance.

Prevents cascading failures by temporarily blocking requests
to failing services, allowing them time to recover.

Features:
- Configurable failure thresholds
- Automatic recovery with half-open state
- Async and sync support
- Decorator for easy integration
- Metrics and state monitoring
- Registry for managing multiple breakers

Example:
    from modules.resilience.circuit_breaker import circuit_breaker

    @circuit_breaker(name="ollama", failure_threshold=5)
    async def call_ollama(prompt: str):
        return await ollama_client.generate(prompt)

    # Or with manual control
    breaker = CircuitBreaker("external_api")

    async with breaker:
        response = await external_api.call()
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    TypeVar,
)

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """
    Circuit breaker states.

    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing, requests are blocked
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open and request is blocked."""

    def __init__(
        self,
        name: str,
        state: CircuitState,
        message: str | None = None,
    ):
        self.name = name
        self.state = state
        self.message = message or f"Circuit breaker '{name}' is {state.value}"
        super().__init__(self.message)


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker behavior.

    Args:
        failure_threshold: Number of failures before opening
        success_threshold: Number of successes in half-open before closing
        timeout: Time in seconds before trying half-open
        half_open_max_calls: Max concurrent calls in half-open state
        exclude_exceptions: Exceptions that don't count as failures
    """

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: float = 30.0
    half_open_max_calls: int = 1
    exclude_exceptions: tuple = ()

    def __post_init__(self):
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if self.timeout <= 0:
            raise ValueError("timeout must be > 0")


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "state_changes": self.state_changes,
            "success_rate": (
                self.successful_calls / self.total_calls
                if self.total_calls > 0
                else 0.0
            ),
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat() if self.last_success_time else None
            ),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.

    Monitors failures and prevents cascading failures by
    temporarily blocking requests to failing services.

    States:
    - CLOSED: Normal operation. Failures are counted.
    - OPEN: Service is failing. Requests are blocked.
    - HALF_OPEN: Testing recovery. Limited requests allowed.

    Example:
        breaker = CircuitBreaker("external_service")

        # Use as context manager
        async with breaker:
            result = await external_call()

        # Or manually
        if breaker.allow_request():
            try:
                result = await external_call()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure(e)
                raise
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        fallback: Callable[..., Any] | None = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Unique identifier for this breaker
            config: Circuit breaker configuration
            fallback: Optional fallback function when open
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback

        # State
        self._state = CircuitState.CLOSED
        self._last_state_change = time.time()
        self._half_open_calls = 0

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._stats = CircuitBreakerStats()

        # Callbacks
        self._on_state_change: list[Callable[[CircuitState, CircuitState], None]] = []

        logger.info(f"Created circuit breaker: {name}")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_timeout()
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        with self._lock:
            return CircuitBreakerStats(**vars(self._stats))

    def _check_timeout(self):
        """Check if timeout has elapsed and transition to half-open."""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_state_change
            if elapsed >= self.config.timeout:
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self._state

        if old_state == new_state:
            return

        self._state = new_state
        self._last_state_change = time.time()
        self._stats.state_changes += 1

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        logger.info(
            f"Circuit breaker '{self.name}' state change: "
            f"{old_state.value} -> {new_state.value}"
        )

        # Notify callbacks
        for callback in self._on_state_change:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

    def on_state_change(
        self,
        callback: Callable[[CircuitState, CircuitState], None],
    ):
        """
        Register callback for state changes.

        Args:
            callback: Function(old_state, new_state)
        """
        self._on_state_change.append(callback)

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.

        Returns:
            True if request is allowed
        """
        with self._lock:
            self._check_timeout()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                return False

            # HALF_OPEN: allow limited calls
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True

            self._stats.rejected_calls += 1
            return False

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = datetime.now()
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self, exception: Exception | None = None):
        """
        Record a failed call.

        Args:
            exception: The exception that occurred
        """
        with self._lock:
            # Check if exception should be excluded
            if exception and self.config.exclude_exceptions:
                if isinstance(exception, self.config.exclude_exceptions):
                    # Don't count as failure
                    self._stats.total_calls += 1
                    return

            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.last_failure_time = datetime.now()
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.HALF_OPEN:
                # Single failure in half-open goes back to open
                self._transition_to(CircuitState.OPEN)

    def reset(self):
        """Reset circuit breaker to initial state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._stats = CircuitBreakerStats()
            self._half_open_calls = 0
            logger.info(f"Circuit breaker '{self.name}' reset")

    def force_open(self):
        """Force circuit breaker to open state."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            logger.warning(f"Circuit breaker '{self.name}' forced open")

    def force_close(self):
        """Force circuit breaker to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            logger.info(f"Circuit breaker '{self.name}' forced closed")

    @asynccontextmanager
    async def __aenter__(self):
        """Async context manager entry."""
        if not self.allow_request():
            if self.fallback:
                yield self.fallback
                return
            raise CircuitBreakerError(self.name, self._state)

        try:
            yield self
        except Exception as e:
            self.record_failure(e)
            raise
        else:
            self.record_success()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    @contextmanager
    def __enter__(self):
        """Sync context manager entry."""
        if not self.allow_request():
            if self.fallback:
                yield self.fallback
                return
            raise CircuitBreakerError(self.name, self._state)

        try:
            yield self
        except Exception as e:
            self.record_failure(e)
            raise
        else:
            self.record_success()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        pass

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result or fallback result

        Raises:
            CircuitBreakerError: If circuit is open and no fallback
        """
        if not self.allow_request():
            if self.fallback:
                return self.fallback(*args, **kwargs)
            raise CircuitBreakerError(self.name, self._state)

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise

    async def call_async(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result or fallback result

        Raises:
            CircuitBreakerError: If circuit is open and no fallback
        """
        if not self.allow_request():
            if self.fallback:
                result = self.fallback(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            raise CircuitBreakerError(self.name, self._state)

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise

    def status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        with self._lock:
            self._check_timeout()

            return {
                "name": self.name,
                "state": self._state.value,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout,
                },
                "stats": self._stats.to_dict(),
                "time_since_state_change": time.time() - self._last_state_change,
            }


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Provides centralized access and monitoring of all
    circuit breakers in the system.

    Example:
        registry = CircuitBreakerRegistry()

        # Register breakers
        registry.register(CircuitBreaker("ollama"))
        registry.register(CircuitBreaker("qdrant"))

        # Get breaker
        breaker = registry.get("ollama")

        # Check all statuses
        statuses = registry.status_all()
    """

    _instance: CircuitBreakerRegistry | None = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._breakers = {}
            return cls._instance

    def register(
        self,
        breaker: CircuitBreaker,
    ) -> CircuitBreaker:
        """
        Register a circuit breaker.

        Args:
            breaker: Circuit breaker to register

        Returns:
            The registered breaker
        """
        with self._lock:
            if breaker.name in self._breakers:
                logger.warning(f"Replacing existing circuit breaker: {breaker.name}")
            self._breakers[breaker.name] = breaker
            return breaker

    def get(self, name: str) -> CircuitBreaker | None:
        """
        Get a circuit breaker by name.

        Args:
            name: Breaker name

        Returns:
            CircuitBreaker or None if not found
        """
        return self._breakers.get(name)

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        fallback: Callable | None = None,
    ) -> CircuitBreaker:
        """
        Get existing breaker or create new one.

        Args:
            name: Breaker name
            config: Config for new breaker
            fallback: Fallback for new breaker

        Returns:
            Existing or new circuit breaker
        """
        with self._lock:
            if name not in self._breakers:
                breaker = CircuitBreaker(name, config, fallback)
                self._breakers[name] = breaker
            return self._breakers[name]

    def remove(self, name: str) -> bool:
        """
        Remove a circuit breaker.

        Args:
            name: Breaker name

        Returns:
            True if breaker was found and removed
        """
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False

    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def status_all(self) -> dict[str, dict[str, Any]]:
        """
        Get status of all circuit breakers.

        Returns:
            Dict mapping names to status dicts
        """
        return {name: breaker.status() for name, breaker in self._breakers.items()}

    def list_names(self) -> list[str]:
        """Get list of all breaker names."""
        return list(self._breakers.keys())

    def __iter__(self):
        """Iterate over breakers."""
        return iter(self._breakers.values())


# Global registry
_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
    fallback: Callable | None = None,
) -> CircuitBreaker:
    """
    Get or create a circuit breaker from the global registry.

    Args:
        name: Breaker name
        config: Config for new breaker
        fallback: Fallback for new breaker

    Returns:
        Circuit breaker instance
    """
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry()
    return _registry.get_or_create(name, config, fallback)


def circuit_breaker(
    name: str | None = None,
    failure_threshold: int = 5,
    success_threshold: int = 3,
    timeout: float = 30.0,
    exclude_exceptions: tuple = (),
    fallback: Callable | None = None,
):
    """
    Decorator to protect a function with a circuit breaker.

    Args:
        name: Breaker name (defaults to function name)
        failure_threshold: Failures before opening
        success_threshold: Successes to close
        timeout: Seconds before half-open
        exclude_exceptions: Exceptions that don't count as failures
        fallback: Fallback function

    Returns:
        Decorated function

    Example:
        @circuit_breaker(name="ollama", failure_threshold=5)
        async def call_ollama(prompt: str):
            return await client.generate(prompt)

        @circuit_breaker(fallback=lambda x: {"cached": True})
        def get_data(key: str):
            return external_service.get(key)
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout=timeout,
        exclude_exceptions=exclude_exceptions,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker_name = name or func.__name__
        breaker = get_circuit_breaker(breaker_name, config, fallback)

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await breaker.call_async(func, *args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return breaker.call(func, *args, **kwargs)

            return sync_wrapper

    return decorator


# Convenience functions for common services
def ollama_circuit_breaker(
    base_url: str = "http://localhost:11434",
    failure_threshold: int = 5,
    timeout: float = 30.0,
) -> CircuitBreaker:
    """Create circuit breaker for Ollama service."""
    return get_circuit_breaker(
        f"ollama:{base_url}",
        CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout=timeout,
        ),
    )


def qdrant_circuit_breaker(
    base_url: str = "http://localhost:6333",
    failure_threshold: int = 5,
    timeout: float = 30.0,
) -> CircuitBreaker:
    """Create circuit breaker for Qdrant service."""
    return get_circuit_breaker(
        f"qdrant:{base_url}",
        CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout=timeout,
        ),
    )
