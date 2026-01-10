"""
File system watcher for automatic cache invalidation.

Monitors model directories, config files, and triggers cache clearing
when changes are detected. Provides automatic cache management for
frequently changing resources.

Features:
- Pattern-based file watching
- Automatic cache invalidation on file changes
- Debounced event handling to prevent thrashing
- Support for recursive directory watching
- Thread-safe operation

Example:
    from modules.cache.watcher import CacheManager

    cache_mgr = CacheManager()

    # Create a cache for model metadata
    model_cache = cache_mgr.create_cache("models")
    model_cache["llama3"] = {"size": "8B", "format": "gguf"}

    # Watch model directory
    cache_mgr.watch_directory(
        Path("models/"),
        cache_key="models",
        patterns={"*.gguf", "*.bin"}
    )

    # Start watching (cache auto-invalidates on changes)
    cache_mgr.start()
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from watchdog.events import (
        DirMovedEvent,
        FileMovedEvent,
        FileSystemEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers import Observer
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object

import builtins

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


class WatchEventType(Enum):
    """Types of file system events we care about."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class WatchEvent:
    """Represents a file system watch event."""
    event_type: WatchEventType
    path: Path
    is_directory: bool
    timestamp: float = field(default_factory=time.time)
    src_path: Path | None = None  # For move events
    dest_path: Path | None = None  # For move events

    def __str__(self) -> str:
        if self.event_type == WatchEventType.MOVED:
            return f"{self.event_type.value}: {self.src_path} -> {self.dest_path}"
        return f"{self.event_type.value}: {self.path}"


@dataclass
class WatchConfig:
    """Configuration for file system watching."""
    patterns: set[str] = field(default_factory=lambda: set())
    ignore_patterns: set[str] = field(default_factory=lambda: {
        "*.tmp", "*.swp", "*.lock", ".DS_Store", "*.pyc",
        "*.pyo", "__pycache__", ".git", ".gitignore", "*.log"
    })
    recursive: bool = True
    debounce_seconds: float = 0.5
    case_sensitive: bool = True


class CacheInvalidationHandler(FileSystemEventHandler):
    """
    Handles file system events and triggers cache invalidation.

    Implements debouncing to prevent excessive cache invalidation
    when multiple rapid file changes occur.

    Example:
        handler = CacheInvalidationHandler(
            on_event=lambda e: print(f"Event: {e}"),
            patterns={"*.gguf", "*.bin"}
        )
    """

    def __init__(
        self,
        on_event: Callable[[WatchEvent], None],
        config: WatchConfig | None = None,
    ):
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog is required for file watching. "
                "Install with: pip install watchdog"
            )
        super().__init__()
        self.on_event = on_event
        self.config = config or WatchConfig()

        # Debouncing state
        self._pending_events: dict[Path, WatchEvent] = {}
        self._debounce_timers: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()

    def _should_process(self, path: Path) -> bool:
        """Check if this path matches our patterns."""
        name = path.name

        # Ignore patterns take precedence
        for pattern in self.config.ignore_patterns:
            if self._matches_pattern(name, pattern):
                return False

        # If no patterns specified, process everything
        if not self.config.patterns:
            return True

        # Check if matches any include pattern
        for pattern in self.config.patterns:
            if self._matches_pattern(name, pattern):
                return True

        return False

    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches a glob pattern."""
        import fnmatch
        if self.config.case_sensitive:
            return fnmatch.fnmatch(name, pattern)
        return fnmatch.fnmatch(name.lower(), pattern.lower())

    def _schedule_event(self, event: WatchEvent):
        """Schedule an event with debouncing."""
        with self._lock:
            path = event.path

            # Cancel existing timer if any
            if path in self._debounce_timers:
                self._debounce_timers[path].cancel()

            # Store pending event
            self._pending_events[path] = event

            # Schedule new timer
            timer = threading.Timer(
                self.config.debounce_seconds,
                self._fire_event,
                args=[path]
            )
            self._debounce_timers[path] = timer
            timer.start()

    def _fire_event(self, path: Path):
        """Fire a debounced event."""
        with self._lock:
            event = self._pending_events.pop(path, None)
            self._debounce_timers.pop(path, None)

        if event:
            try:
                self.on_event(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    def _create_event(
        self,
        fs_event: FileSystemEvent,
        event_type: WatchEventType,
    ) -> WatchEvent | None:
        """Create a WatchEvent from a file system event."""
        path = Path(fs_event.src_path)

        if not self._should_process(path):
            return None

        watch_event = WatchEvent(
            event_type=event_type,
            path=path,
            is_directory=fs_event.is_directory,
        )

        # Handle move events specially
        if isinstance(fs_event, (FileMovedEvent, DirMovedEvent)):
            watch_event.src_path = path
            watch_event.dest_path = Path(fs_event.dest_path)

        return watch_event

    def on_created(self, event: FileSystemEvent):
        """Handle file/directory creation."""
        watch_event = self._create_event(event, WatchEventType.CREATED)
        if watch_event:
            logger.debug(f"File created: {watch_event.path}")
            self._schedule_event(watch_event)

    def on_modified(self, event: FileSystemEvent):
        """Handle file/directory modification."""
        watch_event = self._create_event(event, WatchEventType.MODIFIED)
        if watch_event:
            logger.debug(f"File modified: {watch_event.path}")
            self._schedule_event(watch_event)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file/directory deletion."""
        watch_event = self._create_event(event, WatchEventType.DELETED)
        if watch_event:
            logger.debug(f"File deleted: {watch_event.path}")
            self._schedule_event(watch_event)

    def on_moved(self, event: FileSystemEvent):
        """Handle file/directory move/rename."""
        watch_event = self._create_event(event, WatchEventType.MOVED)
        if watch_event:
            logger.debug(f"File moved: {watch_event}")
            self._schedule_event(watch_event)

    def cancel_pending(self):
        """Cancel all pending debounced events."""
        with self._lock:
            for timer in self._debounce_timers.values():
                timer.cancel()
            self._debounce_timers.clear()
            self._pending_events.clear()


class FileSystemWatcher:
    """
    Watches directories for changes and triggers callbacks.

    Thread-safe file system watcher with support for multiple
    directories and pattern-based filtering.

    Example:
        watcher = FileSystemWatcher()
        watcher.watch(
            Path("models/"),
            on_event=handle_model_change,
            patterns={"*.gguf"}
        )
        watcher.start()

        # ... later ...
        watcher.stop()
    """

    def __init__(self):
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog is required for file watching. "
                "Install with: pip install watchdog"
            )

        self.observer = Observer()
        self._handlers: list[tuple[Path, CacheInvalidationHandler]] = []
        self._running = False
        self._lock = threading.Lock()

    def watch(
        self,
        path: Path | str,
        on_event: Callable[[WatchEvent], None],
        patterns: set[str] | None = None,
        ignore_patterns: set[str] | None = None,
        recursive: bool = True,
        debounce_seconds: float = 0.5,
    ):
        """
        Add a directory to watch.

        Args:
            path: Directory to watch
            on_event: Callback for file system events
            patterns: File patterns to include (e.g., {"*.gguf", "*.bin"})
            ignore_patterns: File patterns to ignore
            recursive: Watch subdirectories
            debounce_seconds: Delay before firing events (prevents thrashing)

        Raises:
            ValueError: If path doesn't exist or isn't a directory
        """
        path = Path(path)

        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")

        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")

        config = WatchConfig(
            patterns=patterns or set(),
            ignore_patterns=ignore_patterns or WatchConfig().ignore_patterns,
            recursive=recursive,
            debounce_seconds=debounce_seconds,
        )

        handler = CacheInvalidationHandler(
            on_event=on_event,
            config=config,
        )

        with self._lock:
            self.observer.schedule(handler, str(path), recursive=recursive)
            self._handlers.append((path, handler))

        logger.info(
            f"Watching {path} (recursive={recursive}, "
            f"patterns={patterns or 'all'})"
        )

    def unwatch(self, path: Path | str):
        """Stop watching a directory."""
        path = Path(path)

        with self._lock:
            to_remove = []
            for watch_path, handler in self._handlers:
                if watch_path == path:
                    handler.cancel_pending()
                    to_remove.append((watch_path, handler))

            for item in to_remove:
                self._handlers.remove(item)

        logger.info(f"Stopped watching {path}")

    def start(self):
        """Start watching."""
        with self._lock:
            if self._running:
                logger.warning("Watcher already running")
                return

            self.observer.start()
            self._running = True

        logger.info("File system watcher started")

    def stop(self, timeout: float = 5.0):
        """Stop watching."""
        with self._lock:
            if not self._running:
                return

            # Cancel pending events
            for _, handler in self._handlers:
                handler.cancel_pending()

            self.observer.stop()
            self.observer.join(timeout=timeout)
            self._running = False

        logger.info("File system watcher stopped")

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    @property
    def watched_paths(self) -> list[Path]:
        """Get list of watched paths."""
        with self._lock:
            return [path for path, _ in self._handlers]

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class CacheManager:
    """
    Manages caches with automatic invalidation based on file changes.

    Provides a high-level interface for creating caches that
    automatically invalidate when watched files change.

    Example:
        cache = CacheManager()

        # Create and watch model cache
        model_cache = cache.create_cache("models")
        model_cache["llama3"] = {"size": "8B"}

        cache.watch_directory(
            Path("models/"),
            cache_key="models",
            patterns={"*.gguf"}
        )

        cache.on_invalidate("models", lambda: print("Cache cleared!"))

        cache.start()
    """

    def __init__(self, auto_start: bool = False):
        """
        Initialize the cache manager.

        Args:
            auto_start: Start watching immediately
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning(
                "watchdog not installed. File watching disabled. "
                "Install with: pip install watchdog"
            )
            self._watcher = None
        else:
            self._watcher = FileSystemWatcher()

        self._caches: dict[str, dict[str, Any]] = {}
        self._invalidation_callbacks: dict[str, list[Callable]] = defaultdict(list)
        self._stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"invalidations": 0, "sets": 0, "gets": 0, "hits": 0}
        )
        self._lock = threading.Lock()

        if auto_start and self._watcher:
            self._watcher.start()

    def create_cache(self, key: str) -> dict[str, Any]:
        """
        Create a new cache with the given key.

        Args:
            key: Unique identifier for this cache

        Returns:
            Dict that can be used as a cache
        """
        with self._lock:
            if key in self._caches:
                logger.warning(f"Cache '{key}' already exists, returning existing")
                return self._caches[key]

            self._caches[key] = {}
            logger.info(f"Created cache: {key}")
            return self._caches[key]

    def get_cache(self, key: str) -> dict[str, Any] | None:
        """
        Get a cache by key.

        Args:
            key: Cache identifier

        Returns:
            Cache dict or None if not found
        """
        with self._lock:
            return self._caches.get(key)

    def set(self, cache_key: str, item_key: str, value: Any):
        """Set a value in a cache."""
        with self._lock:
            if cache_key not in self._caches:
                self._caches[cache_key] = {}

            self._caches[cache_key][item_key] = value
            self._stats[cache_key]["sets"] += 1

    def get(self, cache_key: str, item_key: str, default: Any = None) -> Any:
        """Get a value from a cache."""
        with self._lock:
            self._stats[cache_key]["gets"] += 1

            cache = self._caches.get(cache_key, {})
            if item_key in cache:
                self._stats[cache_key]["hits"] += 1
                return cache[item_key]

            return default

    def invalidate(self, key: str, run_callbacks: bool = True):
        """
        Invalidate a cache.

        Args:
            key: Cache key to invalidate
            run_callbacks: Whether to call invalidation callbacks
        """
        with self._lock:
            if key not in self._caches:
                logger.warning(f"Cache '{key}' does not exist")
                return

            old_size = len(self._caches[key])
            self._caches[key].clear()
            self._stats[key]["invalidations"] += 1

            callbacks = list(self._invalidation_callbacks.get(key, []))

        logger.info(f"Invalidated cache '{key}' ({old_size} entries)")

        if run_callbacks:
            for callback in callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error in invalidation callback for '{key}': {e}")

    def on_invalidate(self, key: str, callback: Callable):
        """
        Register a callback to be called when cache is invalidated.

        Args:
            key: Cache key to watch
            callback: Function to call on invalidation
        """
        with self._lock:
            self._invalidation_callbacks[key].append(callback)
            logger.debug(f"Registered invalidation callback for cache '{key}'")

    def watch_directory(
        self,
        path: Path | str,
        cache_key: str,
        patterns: builtins.set[str] | None = None,
        ignore_patterns: builtins.set[str] | None = None,
        recursive: bool = True,
        debounce_seconds: float = 0.5,
    ):
        """
        Watch a directory and invalidate cache when changes occur.

        Args:
            path: Directory to watch
            cache_key: Cache key to invalidate on changes
            patterns: File patterns to watch
            ignore_patterns: File patterns to ignore
            recursive: Watch subdirectories
            debounce_seconds: Delay before invalidating
        """
        if self._watcher is None:
            logger.warning("Watcher not available, directory watching disabled")
            return

        path = Path(path)

        # Ensure cache exists
        with self._lock:
            if cache_key not in self._caches:
                self._caches[cache_key] = {}

        def on_event(event: WatchEvent):
            logger.info(
                f"File system change detected: {event}, "
                f"invalidating cache '{cache_key}'"
            )
            self.invalidate(cache_key)

        self._watcher.watch(
            path=path,
            on_event=on_event,
            patterns=patterns,
            ignore_patterns=ignore_patterns,
            recursive=recursive,
            debounce_seconds=debounce_seconds,
        )

    def start(self):
        """Start watching directories."""
        if self._watcher:
            self._watcher.start()

    def stop(self):
        """Stop watching directories."""
        if self._watcher:
            self._watcher.stop()

    def stats(self, cache_key: str | None = None) -> dict[str, Any]:
        """
        Get cache statistics.

        Args:
            cache_key: Specific cache key, or None for all caches

        Returns:
            Statistics dict
        """
        with self._lock:
            if cache_key:
                stats = dict(self._stats.get(cache_key, {}))
                cache = self._caches.get(cache_key, {})
                stats["size"] = len(cache)
                stats["hit_rate"] = (
                    stats["hits"] / stats["gets"]
                    if stats["gets"] > 0
                    else 0.0
                )
                return stats

            # All caches
            all_stats = {}
            for key in self._caches:
                all_stats[key] = self.stats(key)

            return all_stats

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Singleton cache manager
_cache_manager: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# Model-specific caching utilities
class ModelCacheManager:
    """
    Specialized cache manager for AI model files.

    Pre-configured with common model file patterns and
    sensible defaults for AI Beast model management.
    """

    MODEL_PATTERNS = {
        "*.gguf",      # GGML/GGUF models
        "*.bin",       # PyTorch/generic binary
        "*.safetensors",  # SafeTensors format
        "*.onnx",      # ONNX models
        "*.pt",        # PyTorch
        "*.pth",       # PyTorch
        "*.h5",        # Keras/TensorFlow
        "*.pb",        # TensorFlow protobuf
        "config.json", # Model config
        "tokenizer.json",  # Tokenizer
    }

    def __init__(
        self,
        models_dir: Path | None = None,
        ollama_models_dir: Path | None = None,
    ):
        self._manager = get_cache_manager()
        self._models_dir = models_dir
        self._ollama_models_dir = ollama_models_dir

        # Create model-specific caches
        self._model_metadata_cache = self._manager.create_cache("model_metadata")
        self._model_list_cache = self._manager.create_cache("model_list")
        self._ollama_cache = self._manager.create_cache("ollama_models")

        # Setup watches if directories provided
        if models_dir and models_dir.exists():
            self._manager.watch_directory(
                models_dir,
                cache_key="model_metadata",
                patterns=self.MODEL_PATTERNS,
                recursive=True,
            )
            self._manager.watch_directory(
                models_dir,
                cache_key="model_list",
                patterns=self.MODEL_PATTERNS,
                recursive=True,
            )

        if ollama_models_dir and ollama_models_dir.exists():
            self._manager.watch_directory(
                ollama_models_dir,
                cache_key="ollama_models",
                recursive=True,
            )

    def get_model_metadata(self, model_id: str) -> dict[str, Any] | None:
        """Get cached model metadata."""
        return self._manager.get("model_metadata", model_id)

    def set_model_metadata(self, model_id: str, metadata: dict[str, Any]):
        """Cache model metadata."""
        self._manager.set("model_metadata", model_id, metadata)

    def get_model_list(self) -> list[dict[str, Any]] | None:
        """Get cached model list."""
        return self._manager.get("model_list", "all")

    def set_model_list(self, models: list[dict[str, Any]]):
        """Cache model list."""
        self._manager.set("model_list", "all", models)

    def invalidate_all(self):
        """Invalidate all model caches."""
        self._manager.invalidate("model_metadata")
        self._manager.invalidate("model_list")
        self._manager.invalidate("ollama_models")

    def on_models_changed(self, callback: Callable):
        """Register callback for when models change."""
        self._manager.on_invalidate("model_metadata", callback)
        self._manager.on_invalidate("model_list", callback)

    def on_ollama_changed(self, callback: Callable):
        """Register callback for when Ollama models change."""
        self._manager.on_invalidate("ollama_models", callback)

    def start(self):
        """Start file watching."""
        self._manager.start()

    def stop(self):
        """Stop file watching."""
        self._manager.stop()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "model_metadata": self._manager.stats("model_metadata"),
            "model_list": self._manager.stats("model_list"),
            "ollama_models": self._manager.stats("ollama_models"),
        }
