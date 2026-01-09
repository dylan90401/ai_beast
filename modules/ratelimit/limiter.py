"""
Rate limiting implementation for API protection.

Provides multiple rate limiting algorithms:
- Token Bucket: Smooth rate limiting with burst allowance
- Sliding Window: Precise rate limiting with rolling window

Features:
- Configurable limits (requests per second/minute/hour)
- Multiple storage backends (in-memory, Redis)
- Per-key rate limiting (by IP, user, API key)
- Decorator for easy integration
- Async and sync support
- Automatic cleanup of expired entries

Example:
    from modules.ratelimit.limiter import rate_limit

    @rate_limit(requests=100, window=60)  # 100 per minute
    async def api_endpoint(request):
        return process_request(request)

    # Or with manual control
    limiter = RateLimiter(limit=10, window=1.0)
    
    if limiter.allow("user-123"):
        process_request()
    else:
        raise RateLimitExceeded()
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from modules.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        key: str,
        limit: int,
        window: float,
        retry_after: float,
        message: Optional[str] = None,
    ):
        self.key = key
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        self.message = message or (
            f"Rate limit exceeded for '{key}': "
            f"{limit} requests per {window}s. "
            f"Retry after {retry_after:.1f}s"
        )
        super().__init__(self.message)


@dataclass
class RateLimitConfig:
    """
    Configuration for rate limiting.
    
    Args:
        requests: Maximum number of requests
        window: Time window in seconds
        burst: Allow bursting above limit (for token bucket)
        key_prefix: Prefix for storage keys
    """
    requests: int = 100
    window: float = 60.0  # seconds
    burst: int = 0  # Additional burst allowance
    key_prefix: str = "ratelimit"
    
    def __post_init__(self):
        if self.requests < 1:
            raise ValueError("requests must be >= 1")
        if self.window <= 0:
            raise ValueError("window must be > 0")


@dataclass
class RateLimitInfo:
    """Information about current rate limit status."""
    allowed: bool
    remaining: int
    limit: int
    window: float
    reset_time: float
    retry_after: float = 0.0
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP rate limit headers."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_time)),
            **({"Retry-After": str(int(self.retry_after) + 1)} if not self.allowed else {}),
        }


class StorageBackend(ABC):
    """Abstract base class for rate limit storage."""
    
    @abstractmethod
    def get(self, key: str) -> Any:
        """Get value for key."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value with optional TTL."""
        pass
    
    @abstractmethod
    def incr(self, key: str, amount: int = 1) -> int:
        """Increment value and return new value."""
        pass
    
    @abstractmethod
    def expire(self, key: str, ttl: float):
        """Set expiration time on key."""
        pass
    
    @abstractmethod
    def delete(self, key: str):
        """Delete key."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up expired entries."""
        pass


@dataclass
class StorageEntry:
    """Entry in in-memory storage."""
    value: Any
    expires_at: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class InMemoryStorage(StorageBackend):
    """
    In-memory storage backend for rate limiting.
    
    Suitable for single-process applications.
    Uses a dict with TTL support and automatic cleanup.
    """
    
    def __init__(self, cleanup_interval: float = 60.0):
        """
        Initialize in-memory storage.
        
        Args:
            cleanup_interval: Seconds between cleanup runs
        """
        self._data: Dict[str, StorageEntry] = {}
        self._lock = threading.RLock()
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    def get(self, key: str) -> Any:
        """Get value for key."""
        with self._lock:
            self._maybe_cleanup()
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._data[key]
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value with optional TTL."""
        with self._lock:
            expires_at = time.time() + ttl if ttl else None
            self._data[key] = StorageEntry(value=value, expires_at=expires_at)

    def incr(self, key: str, amount: int = 1) -> int:
        """Increment value and return new value."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None or entry.is_expired():
                self._data[key] = StorageEntry(value=amount)
                return amount
            entry.value = int(entry.value) + amount
            return entry.value

    def expire(self, key: str, ttl: float):
        """Set expiration time on key."""
        with self._lock:
            entry = self._data.get(key)
            if entry:
                entry.expires_at = time.time() + ttl

    def delete(self, key: str):
        """Delete key."""
        with self._lock:
            self._data.pop(key, None)

    def cleanup(self):
        """Clean up expired entries."""
        with self._lock:
            now = time.time()
            expired_keys = [
                key for key, entry in self._data.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._data[key]
            self._last_cleanup = now
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")

    def _maybe_cleanup(self):
        """Run cleanup if interval has elapsed."""
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self.cleanup()


class RedisStorage(StorageBackend):
    """
    Redis storage backend for rate limiting.
    
    Suitable for distributed applications with multiple
    processes or servers sharing rate limits.
    """
    
    def __init__(
        self,
        url: str = "redis://localhost:6379",
        db: int = 0,
    ):
        """
        Initialize Redis storage.
        
        Args:
            url: Redis connection URL
            db: Redis database number
        """
        self._url = url
        self._db = db
        self._client: Optional[Any] = None
        self._lock = threading.Lock()

    def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    try:
                        import redis
                        self._client = redis.from_url(self._url, db=self._db)
                    except ImportError:
                        raise RuntimeError(
                            "redis package required for RedisStorage. "
                            "Install with: pip install redis"
                        )
        return self._client

    def get(self, key: str) -> Any:
        """Get value for key."""
        client = self._get_client()
        value = client.get(key)
        if value is not None:
            return int(value)
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value with optional TTL."""
        client = self._get_client()
        if ttl:
            client.setex(key, int(ttl) + 1, value)
        else:
            client.set(key, value)

    def incr(self, key: str, amount: int = 1) -> int:
        """Increment value and return new value."""
        client = self._get_client()
        return client.incrby(key, amount)

    def expire(self, key: str, ttl: float):
        """Set expiration time on key."""
        client = self._get_client()
        client.expire(key, int(ttl) + 1)

    def delete(self, key: str):
        """Delete key."""
        client = self._get_client()
        client.delete(key)

    def cleanup(self):
        """Clean up expired entries (handled by Redis TTL)."""
        pass  # Redis handles expiration automatically


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""
    
    @abstractmethod
    def allow(self, key: str) -> bool:
        """Check if request is allowed."""
        pass
    
    @abstractmethod
    def check(self, key: str) -> RateLimitInfo:
        """Check rate limit status without consuming."""
        pass
    
    @abstractmethod
    def reset(self, key: str):
        """Reset rate limit for key."""
        pass


class TokenBucketLimiter(RateLimiter):
    """
    Token bucket rate limiter.
    
    Allows smooth rate limiting with burst handling.
    Tokens are added at a fixed rate, requests consume tokens.
    
    Features:
    - Smooth rate limiting
    - Allows bursts when tokens are available
    - Configurable refill rate
    
    Example:
        # 10 requests per second with burst of 5
        limiter = TokenBucketLimiter(
            capacity=10,
            refill_rate=10.0,  # 10 tokens per second
            storage=InMemoryStorage(),
        )
        
        if limiter.allow("user-123"):
            process_request()
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        storage: Optional[StorageBackend] = None,
        key_prefix: str = "bucket",
    ):
        """
        Initialize token bucket limiter.
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
            storage: Storage backend (defaults to in-memory)
            key_prefix: Prefix for storage keys
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.storage = storage or InMemoryStorage()
        self.key_prefix = key_prefix
        self._lock = threading.RLock()

    def _get_bucket_key(self, key: str) -> str:
        """Get storage key for bucket."""
        return f"{self.key_prefix}:{key}:bucket"

    def _get_timestamp_key(self, key: str) -> str:
        """Get storage key for last refill timestamp."""
        return f"{self.key_prefix}:{key}:ts"

    def _get_bucket_state(self, key: str) -> Tuple[float, float]:
        """
        Get current bucket state.
        
        Returns:
            Tuple of (tokens, last_refill_time)
        """
        bucket_key = self._get_bucket_key(key)
        ts_key = self._get_timestamp_key(key)
        
        tokens = self.storage.get(bucket_key)
        last_refill = self.storage.get(ts_key)
        
        if tokens is None:
            return float(self.capacity), time.time()
        
        return float(tokens), float(last_refill or time.time())

    def _refill_tokens(self, key: str) -> float:
        """
        Refill tokens based on elapsed time.
        
        Returns:
            Current number of tokens
        """
        bucket_key = self._get_bucket_key(key)
        ts_key = self._get_timestamp_key(key)
        
        tokens, last_refill = self._get_bucket_state(key)
        now = time.time()
        
        # Calculate tokens to add
        elapsed = now - last_refill
        new_tokens = min(
            self.capacity,
            tokens + (elapsed * self.refill_rate)
        )
        
        # Update storage
        self.storage.set(bucket_key, new_tokens)
        self.storage.set(ts_key, now)
        
        return new_tokens

    def allow(self, key: str, cost: int = 1) -> bool:
        """
        Check if request is allowed and consume tokens.
        
        Args:
            key: Rate limit key
            cost: Number of tokens to consume
            
        Returns:
            True if request is allowed
        """
        with self._lock:
            tokens = self._refill_tokens(key)
            
            if tokens >= cost:
                bucket_key = self._get_bucket_key(key)
                self.storage.set(bucket_key, tokens - cost)
                return True
            
            return False

    def check(self, key: str) -> RateLimitInfo:
        """Check rate limit status without consuming."""
        with self._lock:
            tokens = self._refill_tokens(key)
            remaining = int(tokens)
            
            # Calculate reset time
            if remaining >= self.capacity:
                reset_time = time.time()
            else:
                tokens_needed = self.capacity - remaining
                reset_time = time.time() + (tokens_needed / self.refill_rate)
            
            # Calculate retry after
            retry_after = 0.0
            if remaining < 1:
                retry_after = 1.0 / self.refill_rate
            
            return RateLimitInfo(
                allowed=remaining >= 1,
                remaining=remaining,
                limit=self.capacity,
                window=self.capacity / self.refill_rate,
                reset_time=reset_time,
                retry_after=retry_after,
            )

    def reset(self, key: str):
        """Reset rate limit for key."""
        bucket_key = self._get_bucket_key(key)
        ts_key = self._get_timestamp_key(key)
        self.storage.delete(bucket_key)
        self.storage.delete(ts_key)


class SlidingWindowLimiter(RateLimiter):
    """
    Sliding window rate limiter.
    
    Provides precise rate limiting using a sliding time window.
    More accurate than fixed windows but uses more memory.
    
    Features:
    - Precise rate limiting
    - No boundary issues like fixed windows
    - Configurable window size
    
    Example:
        # 100 requests per minute
        limiter = SlidingWindowLimiter(
            limit=100,
            window=60.0,
            storage=InMemoryStorage(),
        )
        
        if limiter.allow("user-123"):
            process_request()
    """

    def __init__(
        self,
        limit: int,
        window: float,
        storage: Optional[StorageBackend] = None,
        key_prefix: str = "window",
    ):
        """
        Initialize sliding window limiter.
        
        Args:
            limit: Maximum requests per window
            window: Window size in seconds
            storage: Storage backend (defaults to in-memory)
            key_prefix: Prefix for storage keys
        """
        self.limit = limit
        self.window = window
        self.storage = storage or InMemoryStorage()
        self.key_prefix = key_prefix
        self._lock = threading.RLock()
        
        # For sliding window log
        self._timestamps: Dict[str, List[float]] = defaultdict(list)

    def _get_counter_key(self, key: str) -> str:
        """Get storage key for counter."""
        return f"{self.key_prefix}:{key}:count"

    def _get_window_start_key(self, key: str) -> str:
        """Get storage key for window start."""
        return f"{self.key_prefix}:{key}:start"

    def _clean_old_requests(self, key: str) -> int:
        """
        Clean old request timestamps and return current count.
        
        Returns:
            Number of requests in current window
        """
        now = time.time()
        window_start = now - self.window
        
        # Clean old timestamps
        self._timestamps[key] = [
            ts for ts in self._timestamps[key]
            if ts > window_start
        ]
        
        return len(self._timestamps[key])

    def allow(self, key: str) -> bool:
        """
        Check if request is allowed and record it.
        
        Args:
            key: Rate limit key
            
        Returns:
            True if request is allowed
        """
        with self._lock:
            count = self._clean_old_requests(key)
            
            if count < self.limit:
                self._timestamps[key].append(time.time())
                return True
            
            return False

    def check(self, key: str) -> RateLimitInfo:
        """Check rate limit status without consuming."""
        with self._lock:
            count = self._clean_old_requests(key)
            remaining = self.limit - count
            
            # Calculate reset time
            if self._timestamps[key]:
                oldest = min(self._timestamps[key])
                reset_time = oldest + self.window
            else:
                reset_time = time.time()
            
            # Calculate retry after
            retry_after = 0.0
            if remaining <= 0 and self._timestamps[key]:
                oldest = min(self._timestamps[key])
                retry_after = (oldest + self.window) - time.time()
                retry_after = max(0, retry_after)
            
            return RateLimitInfo(
                allowed=remaining > 0,
                remaining=remaining,
                limit=self.limit,
                window=self.window,
                reset_time=reset_time,
                retry_after=retry_after,
            )

    def reset(self, key: str):
        """Reset rate limit for key."""
        with self._lock:
            self._timestamps.pop(key, None)
            counter_key = self._get_counter_key(key)
            self.storage.delete(counter_key)


class FixedWindowLimiter(RateLimiter):
    """
    Fixed window rate limiter.
    
    Simple rate limiting using fixed time windows.
    Less memory than sliding window but has boundary issues.
    
    Features:
    - Simple implementation
    - Low memory usage
    - Good for Redis backend
    
    Example:
        # 100 requests per minute
        limiter = FixedWindowLimiter(
            limit=100,
            window=60.0,
            storage=RedisStorage(),
        )
        
        if limiter.allow("user-123"):
            process_request()
    """

    def __init__(
        self,
        limit: int,
        window: float,
        storage: Optional[StorageBackend] = None,
        key_prefix: str = "fixed",
    ):
        """
        Initialize fixed window limiter.
        
        Args:
            limit: Maximum requests per window
            window: Window size in seconds
            storage: Storage backend (defaults to in-memory)
            key_prefix: Prefix for storage keys
        """
        self.limit = limit
        self.window = window
        self.storage = storage or InMemoryStorage()
        self.key_prefix = key_prefix

    def _get_window_key(self, key: str) -> str:
        """Get storage key for current window."""
        window_num = int(time.time() / self.window)
        return f"{self.key_prefix}:{key}:{window_num}"

    def allow(self, key: str) -> bool:
        """
        Check if request is allowed and record it.
        
        Args:
            key: Rate limit key
            
        Returns:
            True if request is allowed
        """
        window_key = self._get_window_key(key)
        count = self.storage.incr(window_key)
        
        if count == 1:
            # New window, set TTL
            self.storage.expire(window_key, self.window)
        
        return count <= self.limit

    def check(self, key: str) -> RateLimitInfo:
        """Check rate limit status without consuming."""
        window_key = self._get_window_key(key)
        count = self.storage.get(window_key) or 0
        remaining = self.limit - count
        
        # Calculate reset time
        window_num = int(time.time() / self.window)
        reset_time = (window_num + 1) * self.window
        
        # Calculate retry after
        retry_after = 0.0
        if remaining <= 0:
            retry_after = reset_time - time.time()
        
        return RateLimitInfo(
            allowed=remaining > 0,
            remaining=remaining,
            limit=self.limit,
            window=self.window,
            reset_time=reset_time,
            retry_after=retry_after,
        )

    def reset(self, key: str):
        """Reset rate limit for key."""
        window_key = self._get_window_key(key)
        self.storage.delete(window_key)


# Global limiter registry
_limiters: Dict[str, RateLimiter] = {}
_limiter_lock = threading.Lock()


def get_rate_limiter(
    name: str,
    limit: int = 100,
    window: float = 60.0,
    algorithm: str = "sliding",
    storage: Optional[StorageBackend] = None,
) -> RateLimiter:
    """
    Get or create a rate limiter from the global registry.
    
    Args:
        name: Limiter name
        limit: Maximum requests per window
        window: Window size in seconds
        algorithm: "sliding", "fixed", or "token"
        storage: Storage backend
        
    Returns:
        Rate limiter instance
    """
    with _limiter_lock:
        if name not in _limiters:
            storage = storage or InMemoryStorage()
            
            if algorithm == "sliding":
                limiter = SlidingWindowLimiter(limit, window, storage, name)
            elif algorithm == "fixed":
                limiter = FixedWindowLimiter(limit, window, storage, name)
            elif algorithm == "token":
                limiter = TokenBucketLimiter(limit, limit / window, storage, name)
            else:
                raise ValueError(f"Unknown algorithm: {algorithm}")
            
            _limiters[name] = limiter
        
        return _limiters[name]


def rate_limit(
    requests: int = 100,
    window: float = 60.0,
    key_func: Optional[Callable[..., str]] = None,
    algorithm: str = "sliding",
    on_exceeded: Optional[Callable[[str, RateLimitInfo], Any]] = None,
):
    """
    Decorator to apply rate limiting to a function.
    
    Args:
        requests: Maximum requests per window
        window: Window size in seconds
        key_func: Function to extract rate limit key from arguments
        algorithm: "sliding", "fixed", or "token"
        on_exceeded: Callback when limit exceeded
        
    Returns:
        Decorated function
        
    Example:
        @rate_limit(requests=100, window=60)
        async def api_endpoint(request):
            return process_request(request)
            
        # With custom key extraction
        @rate_limit(
            requests=10,
            window=1.0,
            key_func=lambda req: req.client_ip
        )
        async def api_endpoint(request):
            return process_request(request)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        limiter = get_rate_limiter(
            func.__name__,
            limit=requests,
            window=window,
            algorithm=algorithm,
        )
        
        def get_key(*args, **kwargs) -> str:
            if key_func:
                return str(key_func(*args, **kwargs))
            return "default"
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = get_key(*args, **kwargs)
                info = limiter.check(key)
                
                if not limiter.allow(key):
                    if on_exceeded:
                        result = on_exceeded(key, info)
                        if asyncio.iscoroutine(result):
                            return await result
                        return result
                    raise RateLimitExceeded(
                        key=key,
                        limit=requests,
                        window=window,
                        retry_after=info.retry_after,
                    )
                
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                key = get_key(*args, **kwargs)
                info = limiter.check(key)
                
                if not limiter.allow(key):
                    if on_exceeded:
                        return on_exceeded(key, info)
                    raise RateLimitExceeded(
                        key=key,
                        limit=requests,
                        window=window,
                        retry_after=info.retry_after,
                    )
                
                return func(*args, **kwargs)
            return sync_wrapper
    
    return decorator


# Convenience functions for common use cases
def ip_rate_limiter(
    requests: int = 100,
    window: float = 60.0,
) -> RateLimiter:
    """Create rate limiter for IP-based limiting."""
    return get_rate_limiter(
        f"ip_limit:{requests}:{window}",
        limit=requests,
        window=window,
        algorithm="sliding",
    )


def api_key_rate_limiter(
    requests: int = 1000,
    window: float = 3600.0,
) -> RateLimiter:
    """Create rate limiter for API key-based limiting."""
    return get_rate_limiter(
        f"api_key_limit:{requests}:{window}",
        limit=requests,
        window=window,
        algorithm="sliding",
    )


def user_rate_limiter(
    requests: int = 500,
    window: float = 3600.0,
) -> RateLimiter:
    """Create rate limiter for user-based limiting."""
    return get_rate_limiter(
        f"user_limit:{requests}:{window}",
        limit=requests,
        window=window,
        algorithm="sliding",
    )
