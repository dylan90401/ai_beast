"""
Metadata store for tool runs and operational state.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from modules.core.logging import get_logger

logger = get_logger(__name__)


class MetadataDB:
    def __init__(self, dsn: str | Path | None = None) -> None:
        self.dsn = self._resolve_dsn(dsn)
        self._backend = "sqlite" if self.dsn.startswith("sqlite://") else "postgres"
        if self._backend == "sqlite":
            path = self._sqlite_path(self.dsn)
            self._sqlite_path = path
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self._sqlite_path = None
        self._init_db()

    @staticmethod
    def _resolve_dsn(dsn: str | Path | None) -> str:
        if dsn is None:
            return _default_postgres_dsn()
        if isinstance(dsn, Path):
            return f"sqlite://{dsn}"
        return dsn

    @staticmethod
    def _sqlite_path(dsn: str) -> Path:
        raw = dsn.replace("sqlite://", "", 1)
        if raw == ":memory:":
            return Path(":memory:")
        return Path(raw)

    def _connect(self):
        if self._backend == "sqlite":
            return sqlite3.connect(self._sqlite_path)
        import psycopg

        return psycopg.connect(self.dsn)

    def _init_db(self) -> None:
        schema = """
            CREATE TABLE IF NOT EXISTS tool_runs (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                ok BOOLEAN NOT NULL,
                returncode INTEGER,
                duration_ms INTEGER,
                meta TEXT,
                created_at TEXT NOT NULL
            )
        """
        events_schema = """
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL
            )
        """
        registry_schema = """
            CREATE TABLE IF NOT EXISTS model_registry (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                kind TEXT,
                current_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        versions_schema = """
            CREATE TABLE IF NOT EXISTS model_versions (
                id SERIAL PRIMARY KEY,
                model_id INTEGER NOT NULL,
                version TEXT NOT NULL,
                path TEXT,
                checksum TEXT,
                source_url TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(model_id, version)
            )
        """
        if self._backend == "sqlite":
            schema = """
                CREATE TABLE IF NOT EXISTS tool_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    returncode INTEGER,
                    duration_ms INTEGER,
                    meta TEXT,
                    created_at TEXT NOT NULL
                )
            """
            events_schema = """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL
                )
            """
            registry_schema = """
                CREATE TABLE IF NOT EXISTS model_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    kind TEXT,
                    current_version TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            versions_schema = """
                CREATE TABLE IF NOT EXISTS model_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id INTEGER NOT NULL,
                    version TEXT NOT NULL,
                    path TEXT,
                    checksum TEXT,
                    source_url TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(model_id, version)
                )
            """
        with self._connect() as conn:
            conn.execute(schema)
            conn.execute(events_schema)
            conn.execute(registry_schema)
            conn.execute(versions_schema)
            conn.commit()

    def record_tool_run(
        self,
        name: str,
        ok: bool,
        returncode: int | None = None,
        duration_ms: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(meta or {})
        created_at = datetime.now(UTC).isoformat()
        if self._backend == "sqlite":
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO tool_runs (name, ok, returncode, duration_ms, meta, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, 1 if ok else 0, returncode, duration_ms, payload, created_at),
                )
                conn.commit()
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_runs (name, ok, returncode, duration_ms, meta, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (name, ok, returncode, duration_ms, payload, created_at),
            )
            conn.commit()

    def list_tool_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(500, int(limit)))
        if self._backend == "sqlite":
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT name, ok, returncode, duration_ms, meta, created_at
                    FROM tool_runs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT name, ok, returncode, duration_ms, meta, created_at
                    FROM tool_runs
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
        results = []
        for name, ok, returncode, duration_ms, meta, created_at in rows:
            results.append(
                {
                    "name": name,
                    "ok": bool(ok),
                    "returncode": returncode,
                    "duration_ms": duration_ms,
                    "meta": json.loads(meta or "{}"),
                    "created_at": created_at,
                }
            )
        return results

    def record_event(self, category: str, name: str, payload: dict[str, Any] | None = None) -> None:
        if not category or not name:
            raise ValueError("category and name are required")
        created_at = datetime.now(UTC).isoformat()
        data = json.dumps(payload or {})
        if self._backend == "sqlite":
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO events (category, name, payload, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (category, name, data, created_at),
                )
                conn.commit()
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (category, name, payload, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (category, name, data, created_at),
            )
            conn.commit()

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(500, int(limit)))
        if self._backend == "sqlite":
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT category, name, payload, created_at
                    FROM events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT category, name, payload, created_at
                    FROM events
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
        results = []
        for category, name, payload, created_at in rows:
            results.append(
                {
                    "category": category,
                    "name": name,
                    "payload": json.loads(payload or "{}"),
                    "created_at": created_at,
                }
            )
        return results

    def register_model(
        self,
        name: str,
        version: str,
        kind: str = "",
        path: str = "",
        checksum: str = "",
        source_url: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        if not name or not version:
            raise ValueError("name and version are required")
        created_at = datetime.now(UTC).isoformat()
        if self._backend == "sqlite":
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO model_registry (name, kind, current_version, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        kind=excluded.kind,
                        current_version=excluded.current_version,
                        updated_at=excluded.updated_at
                    """,
                    (name, kind, version, created_at, created_at),
                )
                model_id = conn.execute(
                    "SELECT id FROM model_registry WHERE name = ?",
                    (name,),
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO model_versions (model_id, version, path, checksum, source_url, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(model_id, version) DO UPDATE SET
                        path=excluded.path,
                        checksum=excluded.checksum,
                        source_url=excluded.source_url,
                        notes=excluded.notes
                    """,
                    (model_id, version, path, checksum, source_url, notes, created_at),
                )
                conn.commit()
            return {"ok": True, "name": name, "version": version}

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO model_registry (name, kind, current_version, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(name) DO UPDATE SET
                    kind=EXCLUDED.kind,
                    current_version=EXCLUDED.current_version,
                    updated_at=EXCLUDED.updated_at
                """,
                (name, kind, version, created_at, created_at),
            )
            model_id = conn.execute(
                "SELECT id FROM model_registry WHERE name = %s",
                (name,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO model_versions (model_id, version, path, checksum, source_url, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(model_id, version) DO UPDATE SET
                    path=EXCLUDED.path,
                    checksum=EXCLUDED.checksum,
                    source_url=EXCLUDED.source_url,
                    notes=EXCLUDED.notes
                """,
                (model_id, version, path, checksum, source_url, notes, created_at),
            )
            conn.commit()
        return {"ok": True, "name": name, "version": version}

    def list_models(self) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT mr.id, mr.name, mr.kind, mr.current_version,
                           mv.path, mv.checksum, mv.source_url, mv.notes, mv.created_at
                    FROM model_registry mr
                    LEFT JOIN model_versions mv
                      ON mv.model_id = mr.id AND mv.version = mr.current_version
                    ORDER BY mr.name
                    """
                ).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT mr.id, mr.name, mr.kind, mr.current_version,
                           mv.path, mv.checksum, mv.source_url, mv.notes, mv.created_at
                    FROM model_registry mr
                    LEFT JOIN model_versions mv
                      ON mv.model_id = mr.id AND mv.version = mr.current_version
                    ORDER BY mr.name
                    """
                ).fetchall()
        results = []
        for row in rows:
            (
                model_id,
                name,
                kind,
                current_version,
                path,
                checksum,
                source_url,
                notes,
                created_at,
            ) = row
            results.append(
                {
                    "id": model_id,
                    "name": name,
                    "kind": kind,
                    "current_version": current_version,
                    "path": path,
                    "checksum": checksum,
                    "source_url": source_url,
                    "notes": notes,
                    "version_created_at": created_at,
                }
            )
        return results

    def list_versions(self, name: str) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM model_registry WHERE name = ?",
                    (name,),
                ).fetchone()
                if not row:
                    return []
                model_id = row[0]
                rows = conn.execute(
                    """
                    SELECT version, path, checksum, source_url, notes, created_at
                    FROM model_versions
                    WHERE model_id = ?
                    ORDER BY created_at DESC
                    """,
                    (model_id,),
                ).fetchall()
        else:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM model_registry WHERE name = %s",
                    (name,),
                ).fetchone()
                if not row:
                    return []
                model_id = row[0]
                rows = conn.execute(
                    """
                    SELECT version, path, checksum, source_url, notes, created_at
                    FROM model_versions
                    WHERE model_id = %s
                    ORDER BY created_at DESC
                    """,
                    (model_id,),
                ).fetchall()
        return [
            {
                "version": v,
                "path": path,
                "checksum": checksum,
                "source_url": source_url,
                "notes": notes,
                "created_at": created_at,
            }
            for v, path, checksum, source_url, notes, created_at in rows
        ]

    def rollback_model(self, name: str, version: str) -> dict[str, Any]:
        if not name or not version:
            raise ValueError("name and version are required")
        if self._backend == "sqlite":
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT mr.id FROM model_registry mr
                    JOIN model_versions mv ON mv.model_id = mr.id
                    WHERE mr.name = ? AND mv.version = ?
                    """,
                    (name, version),
                ).fetchone()
                if not row:
                    return {"ok": False, "error": "version not found"}
                conn.execute(
                    "UPDATE model_registry SET current_version = ?, updated_at = ? WHERE name = ?",
                    (version, datetime.now(UTC).isoformat(), name),
                )
                conn.commit()
            return {"ok": True, "name": name, "version": version}

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT mr.id FROM model_registry mr
                JOIN model_versions mv ON mv.model_id = mr.id
                WHERE mr.name = %s AND mv.version = %s
                """,
                (name, version),
            ).fetchone()
            if not row:
                return {"ok": False, "error": "version not found"}
            conn.execute(
                "UPDATE model_registry SET current_version = %s, updated_at = %s WHERE name = %s",
                (version, datetime.now(UTC).isoformat(), name),
            )
            conn.commit()
        return {"ok": True, "name": name, "version": version}

    def status(self) -> dict[str, Any]:
        info = {"backend": self._backend, "dsn": _redact_dsn(self.dsn)}
        try:
            if self._backend == "sqlite":
                with self._connect() as conn:
                    conn.execute("SELECT 1")
            else:
                with self._connect() as conn:
                    conn.execute("SELECT 1")
            info["ok"] = True
        except Exception as exc:
            info["ok"] = False
            info["error"] = str(exc)
        return info


def _default_postgres_dsn() -> str:
    user = os.environ.get("POSTGRES_USER", "aibeast")
    password = os.environ.get("POSTGRES_PASSWORD", "aibeast_dev")
    database = os.environ.get("POSTGRES_DB", "aibeast")
    host = os.environ.get("POSTGRES_HOST") or os.environ.get("AI_BEAST_BIND_ADDR", "127.0.0.1")
    port = os.environ.get("PORT_POSTGRES", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def _redact_dsn(dsn: str) -> str:
    if dsn.startswith("sqlite://"):
        return dsn
    if "://" not in dsn:
        return dsn
    scheme, rest = dsn.split("://", 1)
    if "@" not in rest:
        return dsn
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://***@{host}"


_DEFAULT_DB: MetadataDB | None = None


def get_metadata_db() -> MetadataDB:
    global _DEFAULT_DB
    if _DEFAULT_DB is None:
        dsn = os.environ.get("METADATA_DB_URL")
        try:
            _DEFAULT_DB = MetadataDB(dsn=dsn)
        except Exception as exc:
            logger.warning("Falling back to sqlite metadata store", exc_info=exc)
            fallback = Path("outputs/metadata.db")
            _DEFAULT_DB = MetadataDB(dsn=f"sqlite://{fallback}")
    return _DEFAULT_DB
