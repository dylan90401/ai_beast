"""
Cache module for AI Beast.

Provides:
- File system watching for automatic cache invalidation
- LRU request caching with TTL
- Cache management utilities
"""

from __future__ import annotations

from .watcher import (
    FileSystemWatcher,
    CacheManager,
    CacheInvalidationHandler,
    WatchEvent,
    WatchEventType,
)
from .request_cache import (
    RequestCache,
    CacheEntry,
    CacheStats,
    get_embedding_cache,
    get_ollama_cache,
)

__all__ = [
    # Watcher
    "FileSystemWatcher",
    "CacheManager",
    "CacheInvalidationHandler",
    "WatchEvent",
    "WatchEventType",
    # Request cache
    "RequestCache",
    "CacheEntry",
    "CacheStats",
    "get_embedding_cache",
    "get_ollama_cache",
]
