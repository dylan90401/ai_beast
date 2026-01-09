"""
Database module for AI Beast.

Provides:
- SQLite connection pooling
- Database utilities and helpers
"""

from __future__ import annotations

from .pool import (
    ConnectionPool,
    PoolConfig,
    PooledConnection,
    PoolManager,
    get_pool,
    get_pool_manager,
)

__all__ = [
    "ConnectionPool",
    "PoolConfig", 
    "PooledConnection",
    "PoolManager",
    "get_pool",
    "get_pool_manager",
]
