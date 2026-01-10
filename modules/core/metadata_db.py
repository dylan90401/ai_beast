"""
Metadata database for audit trails.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MetadataDB:
    dsn: str | None = None
    backend: str = "sqlite"

    def __post_init__(self) -> None:
        if self.dsn:
            self.backend = "postgres"
        self._conn = None
        self._init_db()

    def _sqlite_path(self) -> Path:
        return Path("outputs/metadata.db")

    def _init_db(self) -> None:
        if self.backend == "postgres":
            self._conn = None
        else:
            db_path = self._sqlite_path()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path)
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts TEXT, source TEXT, name TEXT, payload TEXT)"
            )
            self._conn.commit()

    def record_event(self, source: str, name: str, payload: dict[str, Any]) -> None:
        if self.backend == "postgres":
            # Placeholder for a real driver (psycopg) integration.
            return
        if not self._conn:
            return
        self._conn.execute(
            "INSERT INTO events (ts, source, name, payload) VALUES (datetime('now'), ?, ?, ?)",
            (source, name, json.dumps(payload)),
        )
        self._conn.commit()

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        if self.backend == "postgres":
            return []
        if not self._conn:
            return []
        cur = self._conn.execute(
            "SELECT ts, source, name, payload FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = []
        for ts, source, name, payload in cur.fetchall():
            rows.append(
                {
                    "ts": ts,
                    "source": source,
                    "name": name,
                    "payload": json.loads(payload or "{}"),
                }
            )
        return rows


_db: MetadataDB | None = None


def get_metadata_db() -> MetadataDB:
    global _db
    if _db is None:
        dsn = os.environ.get("METADATA_DB_URL")
        _db = MetadataDB(dsn=dsn)
    return _db
