"""
Request-level caching with TTL and size limits.

Provides LRU caching for expensive operations like embeddings,
model inferences, and API calls to improve response times.

Features:
- LRU (Least Recently Used) eviction
- TTL (Time-To-Live) for automatic expiration
- Size-based limits (entries and bytes)
- Persistent caching to disk
- Thread-safe operations
- Decorator for easy function caching
- Async support

Example:
    from modules.cache.request_cache import RequestCache

    cache = RequestCache(max_entries=1000, ttl=timedelta(hours=1))

    @cache.cached()
    def expensive_operation(x, y):
        # This result will be cached
        return complex_computation(x, y)

    # Or use directly
    cache.set("key", expensive_data)
    data = cache.get("key")
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import pickle
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    ParamSpec,
    TypeVar,
    Union,
)

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class CacheEntry:
    """
    Represents a cached value with metadata.
    
    Tracks creation time, access patterns, and estimated size
    for intelligent cache management.
    """
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    size_bytes: int = 0
    ttl_override: Optional[timedelta] = None

    @property
    def age(self) -> timedelta:
        """Age of the cache entry."""
        return datetime.now() - self.created_at

    @property
    def idle_time(self) -> timedelta:
        """Time since last access."""
        return datetime.now() - self.last_accessed

    def mark_accessed(self):
        """Mark entry as accessed."""
        self.last_accessed = datetime.now()
        self.access_count += 1

    def is_expired(self, default_ttl: timedelta) -> bool:
        """Check if entry has expired."""
        ttl = self.ttl_override or default_ttl
        return self.age > ttl


@dataclass
class CacheStats:
    """Cache statistics for monitoring and debugging."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    size_bytes: int = 0
    entry_count: int = 0
    oldest_entry_age: Optional[timedelta] = None
    
    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def total_requests(self) -> int:
        """Total cache requests."""
        return self.hits + self.misses

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "evictions": self.evictions,
            "expirations": self.expirations,
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_bytes / (1024 * 1024), 2),
            "entry_count": self.entry_count,
            "oldest_entry_seconds": (
                self.oldest_entry_age.total_seconds()
                if self.oldest_entry_age else None
            ),
        }


class RequestCache:
    """
    LRU cache with TTL and size limits.
    
    Thread-safe implementation with support for:
    - Entry count limits
    - Memory size limits
    - Time-based expiration
    - Persistence to disk
    - Function result caching via decorator

    Example:
        cache = RequestCache(
            max_entries=1000,
            max_size_bytes=100 * 1024 * 1024,  # 100 MB
            ttl=timedelta(hours=1),
        )

        # Method 1: Decorator
        @cache.cached()
        def expensive_api_call(param):
            return call_api(param)

        # Method 2: Direct usage
        cache.set("my_key", {"data": "value"})
        result = cache.get("my_key")

        # Method 3: Get-or-compute
        result = cache.get_or_set(
            "computed_key",
            lambda: compute_expensive_result()
        )
    """

    def __init__(
        self,
        max_entries: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,  # 100 MB
        ttl: timedelta = timedelta(hours=1),
        persist_path: Optional[Path] = None,
        namespace: str = "default",
    ):
        """
        Initialize the cache.
        
        Args:
            max_entries: Maximum number of entries
            max_size_bytes: Maximum total size in bytes
            ttl: Default time-to-live for entries
            persist_path: Optional path to persist cache
            namespace: Cache namespace for isolation
        """
        self.max_entries = max_entries
        self.max_size_bytes = max_size_bytes
        self.ttl = ttl
        self.persist_path = persist_path
        self.namespace = namespace

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
        
        # Cleanup settings
        self._cleanup_interval = min(ttl.total_seconds() / 2, 300)  # Max 5 min
        self._last_cleanup = time.time()

        # Load persisted cache
        if persist_path and persist_path.exists():
            self._load()

    def _make_key(
        self,
        func_name: str,
        args: tuple,
        kwargs: dict,
        key_prefix: Optional[str] = None,
    ) -> str:
        """
        Create a cache key from function name and arguments.
        
        Uses deterministic hashing to ensure consistent keys
        across calls with the same arguments.
        """
        key_parts = {
            "namespace": self.namespace,
            "func": func_name,
            "args": self._serialize_for_key(args),
            "kwargs": self._serialize_for_key(sorted(kwargs.items())),
        }
        
        if key_prefix:
            key_parts["prefix"] = key_prefix
        
        serialized = json.dumps(key_parts, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _serialize_for_key(self, obj: Any) -> Any:
        """Serialize object for key generation."""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._serialize_for_key(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._serialize_for_key(v) for k, v in sorted(obj.items())}
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        if isinstance(obj, (Path,)):
            return str(obj)
        if hasattr(obj, "__dict__"):
            return self._serialize_for_key(obj.__dict__)
        return str(obj)

    def _estimate_size(self, obj: Any) -> int:
        """Estimate size of object in bytes."""
        try:
            return len(pickle.dumps(obj))
        except (pickle.PicklingError, TypeError):
            # Fallback for unpicklable objects
            return len(str(obj).encode())

    def _evict_lru(self) -> bool:
        """
        Evict least recently used entry.
        
        Returns:
            True if an entry was evicted
        """
        if not self._cache:
            return False

        # Remove oldest entry (first in OrderedDict)
        key, entry = self._cache.popitem(last=False)
        self._stats.size_bytes -= entry.size_bytes
        self._stats.entry_count -= 1
        self._stats.evictions += 1

        logger.debug(
            f"Evicted LRU entry: {key[:16]}... "
            f"(age: {entry.age}, accesses: {entry.access_count})"
        )
        return True

    def _evict_expired(self) -> int:
        """
        Evict expired entries.
        
        Returns:
            Number of entries evicted
        """
        now = datetime.now()
        to_remove = []

        for key, entry in self._cache.items():
            if entry.is_expired(self.ttl):
                to_remove.append(key)

        for key in to_remove:
            entry = self._cache.pop(key)
            self._stats.size_bytes -= entry.size_bytes
            self._stats.entry_count -= 1
            self._stats.expirations += 1
            logger.debug(f"Evicted expired entry: {key[:16]}...")

        return len(to_remove)

    def _enforce_limits(self):
        """Enforce cache size limits."""
        # Periodic cleanup of expired entries
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._evict_expired()
            self._last_cleanup = now

        # Evict LRU entries if over limits
        while (
            len(self._cache) > self.max_entries
            or self._stats.size_bytes > self.max_size_bytes
        ):
            if not self._evict_lru():
                break

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            default: Value to return if not found
            
        Returns:
            Cached value or default
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return default

            # Check if expired
            if entry.is_expired(self.ttl):
                self._cache.pop(key)
                self._stats.size_bytes -= entry.size_bytes
                self._stats.entry_count -= 1
                self._stats.expirations += 1
                self._stats.misses += 1
                return default

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            entry.mark_accessed()

            self._stats.hits += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None,
    ):
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override for this entry
        """
        with self._lock:
            size = self._estimate_size(value)

            # Remove existing entry if present
            if key in self._cache:
                old_entry = self._cache.pop(key)
                self._stats.size_bytes -= old_entry.size_bytes
                self._stats.entry_count -= 1

            # Create new entry
            entry = CacheEntry(
                key=key,
                value=value,
                size_bytes=size,
                ttl_override=ttl,
            )

            self._cache[key] = entry
            self._stats.size_bytes += size
            self._stats.entry_count += 1

            # Enforce limits
            self._enforce_limits()

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[timedelta] = None,
    ) -> T:
        """
        Get value from cache or compute and store it.
        
        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Optional TTL override
            
        Returns:
            Cached or computed value
        """
        # Try cache first
        value = self.get(key)
        if value is not None:
            return value

        # Compute value
        value = factory()

        # Store in cache
        self.set(key, value, ttl=ttl)

        return value

    async def get_or_set_async(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[timedelta] = None,
    ) -> Any:
        """
        Async version of get_or_set.
        
        Args:
            key: Cache key
            factory: Async function to compute value if not cached
            ttl: Optional TTL override
            
        Returns:
            Cached or computed value
        """
        # Try cache first
        value = self.get(key)
        if value is not None:
            return value

        # Compute value (await if coroutine)
        result = factory()
        if asyncio.iscoroutine(result):
            value = await result
        else:
            value = result

        # Store in cache
        self.set(key, value, ttl=ttl)

        return value

    def delete(self, key: str) -> bool:
        """
        Remove a specific key from the cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if key was found and removed
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._stats.size_bytes -= entry.size_bytes
                self._stats.entry_count -= 1
                return True
            return False

    def invalidate(self, key: str):
        """Alias for delete() for compatibility."""
        return self.delete(key)

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: Glob-style pattern
            
        Returns:
            Number of keys invalidated
        """
        import fnmatch
        
        with self._lock:
            to_remove = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            
            for key in to_remove:
                entry = self._cache.pop(key)
                self._stats.size_bytes -= entry.size_bytes
                self._stats.entry_count -= 1
            
            return len(to_remove)

    def clear(self):
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._stats = CacheStats()
            logger.info(f"Cleared cache '{self.namespace}'")

    def stats(self) -> CacheStats:
        """
        Get cache statistics.
        
        Returns:
            CacheStats object with current metrics
        """
        with self._lock:
            stats = CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expirations=self._stats.expirations,
                size_bytes=self._stats.size_bytes,
                entry_count=len(self._cache),
            )
            
            if self._cache:
                oldest = next(iter(self._cache.values()))
                stats.oldest_entry_age = oldest.age
            
            return stats

    def cached(
        self,
        ttl: Optional[timedelta] = None,
        key_prefix: Optional[str] = None,
        key_func: Optional[Callable[..., str]] = None,
    ):
        """
        Decorator to cache function results.
        
        Args:
            ttl: Optional TTL override
            key_prefix: Optional prefix for cache keys
            key_func: Optional custom key generation function
            
        Example:
            @cache.cached(ttl=timedelta(minutes=30))
            def expensive_function(x, y):
                return x + y
                
            @cache.cached(key_func=lambda user_id: f"user:{user_id}")
            def get_user_data(user_id):
                return fetch_user(user_id)
        """
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                # Generate cache key
                if key_func:
                    key = key_func(*args, **kwargs)
                else:
                    key = self._make_key(
                        func.__name__,
                        args,
                        kwargs,
                        key_prefix,
                    )

                # Try to get from cache
                cached_value = self.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached_value

                # Compute value
                logger.debug(f"Cache miss for {func.__name__}, computing...")
                value = func(*args, **kwargs)

                # Store in cache
                self.set(key, value, ttl=ttl)

                return value

            # Attach cache control methods
            wrapper.cache_key = lambda *a, **kw: (
                key_func(*a, **kw) if key_func
                else self._make_key(func.__name__, a, kw, key_prefix)
            )
            wrapper.cache_invalidate = lambda *a, **kw: self.delete(
                wrapper.cache_key(*a, **kw)
            )

            return wrapper

        return decorator

    def cached_async(
        self,
        ttl: Optional[timedelta] = None,
        key_prefix: Optional[str] = None,
        key_func: Optional[Callable[..., str]] = None,
    ):
        """
        Decorator to cache async function results.
        
        Similar to cached() but for async functions.
        """
        def decorator(func: Callable[P, T]) -> Callable[P, T]:
            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                # Generate cache key
                if key_func:
                    key = key_func(*args, **kwargs)
                else:
                    key = self._make_key(
                        func.__name__,
                        args,
                        kwargs,
                        key_prefix,
                    )

                # Try to get from cache
                cached_value = self.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for async {func.__name__}")
                    return cached_value

                # Compute value
                logger.debug(f"Cache miss for async {func.__name__}, computing...")
                value = await func(*args, **kwargs)

                # Store in cache
                self.set(key, value, ttl=ttl)

                return value

            return wrapper

        return decorator

    def _save(self):
        """Persist cache to disk."""
        if not self.persist_path:
            return

        with self._lock:
            try:
                self.persist_path.parent.mkdir(parents=True, exist_ok=True)

                # Convert cache to serializable format
                data = {
                    "namespace": self.namespace,
                    "created": datetime.now().isoformat(),
                    "entries": {},
                }
                
                for key, entry in self._cache.items():
                    try:
                        data["entries"][key] = {
                            "value": entry.value,
                            "created_at": entry.created_at.isoformat(),
                            "size_bytes": entry.size_bytes,
                        }
                    except (pickle.PicklingError, TypeError):
                        # Skip unpicklable entries
                        continue

                with open(self.persist_path, "wb") as f:
                    pickle.dump(data, f)

                logger.info(
                    f"Persisted cache '{self.namespace}' to {self.persist_path} "
                    f"({len(data['entries'])} entries)"
                )
            except Exception as e:
                logger.error(f"Failed to persist cache: {e}")

    def _load(self):
        """Load cache from disk."""
        if not self.persist_path or not self.persist_path.exists():
            return

        with self._lock:
            try:
                with open(self.persist_path, "rb") as f:
                    data = pickle.load(f)

                # Restore entries
                for key, entry_data in data.get("entries", {}).items():
                    created_at = datetime.fromisoformat(entry_data["created_at"])
                    
                    # Skip expired entries
                    if datetime.now() - created_at > self.ttl:
                        continue
                    
                    entry = CacheEntry(
                        key=key,
                        value=entry_data["value"],
                        created_at=created_at,
                        last_accessed=created_at,
                        size_bytes=entry_data.get("size_bytes", 0),
                    )
                    
                    self._cache[key] = entry
                    self._stats.size_bytes += entry.size_bytes

                self._stats.entry_count = len(self._cache)

                logger.info(
                    f"Loaded cache '{self.namespace}' from {self.persist_path} "
                    f"({self._stats.entry_count} entries)"
                )
            except Exception as e:
                logger.error(f"Failed to load cache: {e}")

    def save(self):
        """Explicit save to disk."""
        self._save()

    def __del__(self):
        """Save cache on deletion if persistence enabled."""
        try:
            self._save()
        except Exception:
            pass

    def __len__(self) -> int:
        """Return number of entries in cache."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        with self._lock:
            return key in self._cache


# Global cache instances for different use cases
_embedding_cache: Optional[RequestCache] = None
_ollama_cache: Optional[RequestCache] = None
_api_cache: Optional[RequestCache] = None


def get_embedding_cache() -> RequestCache:
    """
    Get the global embedding cache.
    
    Pre-configured for caching embedding vectors with:
    - Large entry limit (10,000)
    - 500 MB size limit
    - 7 day TTL
    - Persistent storage
    """
    global _embedding_cache
    if _embedding_cache is None:
        cache_dir = Path(os.environ.get(
            "AI_BEAST_CACHE_DIR",
            Path.home() / ".cache" / "ai_beast"
        ))
        _embedding_cache = RequestCache(
            max_entries=10000,
            max_size_bytes=500 * 1024 * 1024,  # 500 MB
            ttl=timedelta(days=7),
            persist_path=cache_dir / "embeddings.cache",
            namespace="embeddings",
        )
    return _embedding_cache


def get_ollama_cache() -> RequestCache:
    """
    Get the global Ollama response cache.
    
    Pre-configured for caching Ollama API responses with:
    - 1,000 entry limit
    - 100 MB size limit  
    - 1 hour TTL
    - Persistent storage
    """
    global _ollama_cache
    if _ollama_cache is None:
        cache_dir = Path(os.environ.get(
            "AI_BEAST_CACHE_DIR",
            Path.home() / ".cache" / "ai_beast"
        ))
        _ollama_cache = RequestCache(
            max_entries=1000,
            max_size_bytes=100 * 1024 * 1024,  # 100 MB
            ttl=timedelta(hours=1),
            persist_path=cache_dir / "ollama.cache",
            namespace="ollama",
        )
    return _ollama_cache


def get_api_cache() -> RequestCache:
    """
    Get the global API response cache.
    
    Pre-configured for caching external API responses with:
    - 500 entry limit
    - 50 MB size limit
    - 30 minute TTL
    - Persistent storage
    """
    global _api_cache
    if _api_cache is None:
        cache_dir = Path(os.environ.get(
            "AI_BEAST_CACHE_DIR",
            Path.home() / ".cache" / "ai_beast"
        ))
        _api_cache = RequestCache(
            max_entries=500,
            max_size_bytes=50 * 1024 * 1024,  # 50 MB
            ttl=timedelta(minutes=30),
            persist_path=cache_dir / "api.cache",
            namespace="api",
        )
    return _api_cache


def clear_all_caches():
    """Clear all global caches."""
    global _embedding_cache, _ollama_cache, _api_cache
    
    for cache in [_embedding_cache, _ollama_cache, _api_cache]:
        if cache:
            cache.clear()
    
    logger.info("Cleared all global caches")


def save_all_caches():
    """Persist all global caches to disk."""
    global _embedding_cache, _ollama_cache, _api_cache
    
    for cache in [_embedding_cache, _ollama_cache, _api_cache]:
        if cache:
            cache.save()
    
    logger.info("Saved all global caches")


def get_all_cache_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all global caches."""
    global _embedding_cache, _ollama_cache, _api_cache
    
    stats = {}
    
    caches = [
        ("embeddings", _embedding_cache),
        ("ollama", _ollama_cache),
        ("api", _api_cache),
    ]
    
    for name, cache in caches:
        if cache:
            stats[name] = cache.stats().to_dict()
    
    return stats
