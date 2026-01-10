"""
Database connection pooling for SQLite.

Provides thread-safe connection management with automatic cleanup,
idle connection handling, and WAL mode for better concurrency.

Features:
- Connection reuse to reduce overhead
- Automatic idle connection cleanup
- WAL mode for better write concurrency
- Thread-safe operation
- Context manager support
- Health checking
- Multiple pool management

Example:
    from modules.db.pool import get_pool

    # Get a connection pool
    pool = get_pool("data/catalog.db")

    # Use connection with context manager
    with pool.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM models")
        results = cursor.fetchall()

    # Connection automatically returned to pool
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from modules.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PoolConfig:
    """Configuration for connection pool."""

    # Pool size limits
    min_size: int = 2
    max_size: int = 10

    # Connection lifecycle
    max_idle_time: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    max_lifetime: timedelta = field(default_factory=lambda: timedelta(hours=1))

    # Timeouts
    acquire_timeout: float = 30.0

    # SQLite settings
    check_same_thread: bool = False
    enable_wal: bool = True
    enable_foreign_keys: bool = True
    busy_timeout: int = 5000  # milliseconds
    cache_size: int = -2000  # 2MB page cache (negative = KB)

    # Health check
    health_check_query: str = "SELECT 1"
    health_check_interval: timedelta = field(
        default_factory=lambda: timedelta(minutes=1)
    )

    def __post_init__(self):
        if self.min_size < 1:
            raise ValueError("min_size must be >= 1")
        if self.max_size < self.min_size:
            raise ValueError("max_size must be >= min_size")


@dataclass
class PooledConnection:
    """Wrapper for a pooled database connection."""

    conn: sqlite3.Connection
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    last_health_check: datetime = field(default_factory=datetime.now)
    use_count: int = 0
    in_use: bool = False
    _id: int = field(default_factory=lambda: id(object()))

    @property
    def idle_time(self) -> timedelta:
        """Time since last use."""
        return datetime.now() - self.last_used

    @property
    def age(self) -> timedelta:
        """Total age of the connection."""
        return datetime.now() - self.created_at

    def mark_used(self):
        """Mark connection as currently in use."""
        self.last_used = datetime.now()
        self.use_count += 1
        self.in_use = True

    def mark_returned(self):
        """Mark connection as returned to pool."""
        self.last_used = datetime.now()
        self.in_use = False

    def is_healthy(self, config: PoolConfig) -> bool:
        """Check if connection is still healthy."""
        # Check if too old
        if self.age > config.max_lifetime:
            return False

        # Run health check query
        try:
            self.conn.execute(config.health_check_query)
            self.last_health_check = datetime.now()
            return True
        except sqlite3.Error:
            return False

    def close(self):
        """Close the underlying connection."""
        try:
            self.conn.close()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")


class ConnectionPool:
    """
    Thread-safe SQLite connection pool.

    Manages a pool of database connections with automatic
    creation, reuse, and cleanup.

    Example:
        pool = ConnectionPool("db.sqlite", config=PoolConfig(max_size=5))

        with pool.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM table")
            rows = cursor.fetchall()

        # For write operations, commit is automatic on success
        with pool.get_connection() as conn:
            conn.execute("INSERT INTO table (col) VALUES (?)", (val,))
            # Commits on successful exit, rolls back on exception
    """

    def __init__(
        self,
        db_path: Path | str,
        config: PoolConfig | None = None,
    ):
        """
        Initialize the connection pool.

        Args:
            db_path: Path to SQLite database
            config: Pool configuration
        """
        self.db_path = Path(db_path)
        self.config = config or PoolConfig()

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Pool state
        self._pool: Queue[PooledConnection] = Queue(maxsize=self.config.max_size)
        self._all_connections: list[PooledConnection] = []
        self._lock = threading.Lock()
        self._closed = False

        # Stats
        self._stats = {
            "connections_created": 0,
            "connections_closed": 0,
            "acquires": 0,
            "releases": 0,
            "timeouts": 0,
            "health_check_failures": 0,
        }

        # Background cleanup
        self._cleanup_interval = min(
            self.config.max_idle_time.total_seconds() / 2,
            60  # Max 1 minute
        )
        self._last_cleanup = time.time()

        # Pre-create minimum connections
        self._initialize_pool()

        logger.info(
            f"Created connection pool for {self.db_path} "
            f"(min={self.config.min_size}, max={self.config.max_size})"
        )

    def _initialize_pool(self):
        """Pre-create minimum connections."""
        for _ in range(self.config.min_size):
            try:
                conn = self._create_connection()
                self._pool.put(conn)
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")

    def _create_connection(self) -> PooledConnection:
        """Create a new database connection."""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=self.config.check_same_thread,
            timeout=self.config.acquire_timeout,
        )

        # Configure connection
        if self.config.enable_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")

        if self.config.enable_wal:
            conn.execute("PRAGMA journal_mode = WAL")

        conn.execute(f"PRAGMA busy_timeout = {self.config.busy_timeout}")
        conn.execute(f"PRAGMA cache_size = {self.config.cache_size}")

        # Row factory for dict-like access
        conn.row_factory = sqlite3.Row

        pooled = PooledConnection(conn=conn)

        with self._lock:
            self._all_connections.append(pooled)
            self._stats["connections_created"] += 1

        logger.debug(
            f"Created new connection "
            f"(total: {len(self._all_connections)}/{self.config.max_size})"
        )

        return pooled

    def _cleanup_idle_connections(self):
        """Close connections that have been idle too long."""
        now = time.time()

        # Only run cleanup periodically
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now

        with self._lock:
            # Get connections from pool to check
            connections_to_check = []
            while not self._pool.empty():
                try:
                    pooled = self._pool.get_nowait()
                    connections_to_check.append(pooled)
                except Empty:
                    break

            connections_to_keep = []
            connections_to_close = []

            for pooled in connections_to_check:
                should_close = False

                # Check idle time
                if (
                    pooled.idle_time > self.config.max_idle_time
                    and len(self._all_connections) > self.config.min_size
                ):
                    should_close = True
                    logger.debug(
                        f"Closing idle connection "
                        f"(idle: {pooled.idle_time.total_seconds():.1f}s)"
                    )

                # Check max lifetime
                elif pooled.age > self.config.max_lifetime:
                    should_close = True
                    logger.debug(
                        f"Closing aged connection "
                        f"(age: {pooled.age.total_seconds():.1f}s)"
                    )

                # Health check
                elif not pooled.is_healthy(self.config):
                    should_close = True
                    self._stats["health_check_failures"] += 1
                    logger.debug("Closing unhealthy connection")

                if should_close:
                    connections_to_close.append(pooled)
                else:
                    connections_to_keep.append(pooled)

            # Close old connections
            for pooled in connections_to_close:
                pooled.close()
                self._all_connections.remove(pooled)
                self._stats["connections_closed"] += 1

            # Return healthy connections to pool
            for pooled in connections_to_keep:
                try:
                    self._pool.put_nowait(pooled)
                except Exception:  # Queue.Full or other queue exceptions
                    pass

    def _return_connection(self, pooled: PooledConnection):
        """Return a connection to the pool."""
        pooled.mark_returned()

        with self._lock:
            self._stats["releases"] += 1

        # Check if connection is still healthy
        if not pooled.is_healthy(self.config):
            with self._lock:
                pooled.close()
                if pooled in self._all_connections:
                    self._all_connections.remove(pooled)
                self._stats["connections_closed"] += 1
                self._stats["health_check_failures"] += 1
            return

        # Return to pool
        try:
            self._pool.put_nowait(pooled)
        except Exception:  # Queue.Full or other queue exceptions
            # Pool is full, close this connection
            with self._lock:
                pooled.close()
                if pooled in self._all_connections:
                    self._all_connections.remove(pooled)
                self._stats["connections_closed"] += 1

    @contextmanager
    def get_connection(
        self,
        autocommit: bool = True,
    ) -> Generator[sqlite3.Connection, None, None]:
        """
        Get a connection from the pool.

        Args:
            autocommit: Commit on successful exit, rollback on exception

        Yields:
            sqlite3.Connection: Database connection

        Raises:
            RuntimeError: If pool is closed
            TimeoutError: If no connection available within timeout

        Example:
            with pool.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM table")
                results = cursor.fetchall()
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        pooled = None

        try:
            # Run periodic cleanup
            self._cleanup_idle_connections()

            # Try to get from pool
            try:
                pooled = self._pool.get(timeout=self.config.acquire_timeout)
            except Empty as err:
                # Pool exhausted, try to create new connection
                with self._lock:
                    if len(self._all_connections) < self.config.max_size:
                        pooled = self._create_connection()
                    else:
                        self._stats["timeouts"] += 1
                        raise TimeoutError(
                            f"No connection available within "
                            f"{self.config.acquire_timeout}s "
                            f"(pool size: {len(self._all_connections)}/"
                            f"{self.config.max_size})"
                        ) from err

            pooled.mark_used()

            with self._lock:
                self._stats["acquires"] += 1

            yield pooled.conn

            # Commit on success if autocommit
            if autocommit:
                pooled.conn.commit()

        except Exception:
            # Rollback on exception
            if pooled and autocommit:
                try:
                    pooled.conn.rollback()
                except Exception:
                    pass
            raise

        finally:
            if pooled:
                self._return_connection(pooled)

    def execute(
        self,
        sql: str,
        params: tuple = (),
    ) -> list[sqlite3.Row]:
        """
        Execute SQL and return results.

        Convenience method for simple queries.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            List of result rows
        """
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def executemany(
        self,
        sql: str,
        params_list: list[tuple],
    ) -> int:
        """
        Execute SQL for multiple parameter sets.

        Args:
            sql: SQL statement
            params_list: List of parameter tuples

        Returns:
            Total number of rows affected
        """
        with self.get_connection() as conn:
            cursor = conn.executemany(sql, params_list)
            return cursor.rowcount

    def executescript(self, script: str):
        """
        Execute SQL script.

        Args:
            script: SQL script (multiple statements)
        """
        with self.get_connection() as conn:
            conn.executescript(script)

    @property
    def size(self) -> int:
        """Current number of connections in pool."""
        with self._lock:
            return len(self._all_connections)

    @property
    def available(self) -> int:
        """Number of available connections."""
        return self._pool.qsize()

    @property
    def in_use(self) -> int:
        """Number of connections currently in use."""
        with self._lock:
            return sum(1 for c in self._all_connections if c.in_use)

    def stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                **self._stats,
                "pool_size": len(self._all_connections),
                "available": self._pool.qsize(),
                "in_use": sum(1 for c in self._all_connections if c.in_use),
                "max_size": self.config.max_size,
                "db_path": str(self.db_path),
            }

    def close(self):
        """Close all connections in the pool."""
        if self._closed:
            return

        self._closed = True

        with self._lock:
            for pooled in self._all_connections:
                try:
                    pooled.close()
                    self._stats["connections_closed"] += 1
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

            self._all_connections.clear()

        logger.info(f"Connection pool closed for {self.db_path}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class PoolManager:
    """
    Manages multiple connection pools.

    Provides centralized management of database connection pools
    for different databases.

    Example:
        manager = PoolManager()

        # Get pools for different databases
        catalog_pool = manager.get_pool("catalog.db")
        version_pool = manager.get_pool("versions.db")

        # Use pools
        with catalog_pool.get_connection() as conn:
            ...

        # Close all when done
        manager.close_all()
    """

    def __init__(self, default_config: PoolConfig | None = None):
        """
        Initialize the pool manager.

        Args:
            default_config: Default configuration for new pools
        """
        self.default_config = default_config or PoolConfig()
        self._pools: dict[Path, ConnectionPool] = {}
        self._lock = threading.Lock()

    def get_pool(
        self,
        db_path: Path | str,
        config: PoolConfig | None = None,
    ) -> ConnectionPool:
        """
        Get or create a connection pool for a database.

        Args:
            db_path: Path to database
            config: Optional pool configuration

        Returns:
            ConnectionPool for the database
        """
        db_path = Path(db_path).resolve()

        with self._lock:
            if db_path not in self._pools:
                pool_config = config or self.default_config
                self._pools[db_path] = ConnectionPool(db_path, pool_config)
                logger.info(f"Created connection pool for {db_path}")

            return self._pools[db_path]

    def close_pool(self, db_path: Path | str):
        """Close a specific pool."""
        db_path = Path(db_path).resolve()

        with self._lock:
            if db_path in self._pools:
                self._pools[db_path].close()
                del self._pools[db_path]

    def close_all(self):
        """Close all connection pools."""
        with self._lock:
            for pool in self._pools.values():
                pool.close()
            self._pools.clear()

        logger.info("All connection pools closed")

    def stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all pools."""
        with self._lock:
            return {
                str(path): pool.stats()
                for path, pool in self._pools.items()
            }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()


# Global pool manager instance
_pool_manager: PoolManager | None = None
_pool_manager_lock = threading.Lock()


def get_pool_manager() -> PoolManager:
    """Get the global pool manager instance."""
    global _pool_manager

    with _pool_manager_lock:
        if _pool_manager is None:
            _pool_manager = PoolManager()

    return _pool_manager


def get_pool(
    db_path: Path | str,
    config: PoolConfig | None = None,
) -> ConnectionPool:
    """
    Convenience function to get a connection pool.

    Args:
        db_path: Path to database
        config: Optional pool configuration

    Returns:
        ConnectionPool for the database
    """
    return get_pool_manager().get_pool(db_path, config)


def close_all_pools():
    """Close all connection pools."""
    global _pool_manager

    with _pool_manager_lock:
        if _pool_manager:
            _pool_manager.close_all()
            _pool_manager = None
