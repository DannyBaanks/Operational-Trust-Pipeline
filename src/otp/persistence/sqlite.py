"""SQLite persistence backend. Stdlib only. Auto-initializes schema."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Mapping

from .errors import ConflictError, CorruptionError, SchemaUnsupportedError

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operational_events (
    event_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_requests (
    action_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_results (
    result_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES action_requests(action_id),
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leases (
    lease_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leases_state ON leases(state);
CREATE INDEX IF NOT EXISTS idx_executions_state ON executions(state);
CREATE INDEX IF NOT EXISTS idx_executions_created ON executions(created_at, execution_id);
CREATE INDEX IF NOT EXISTS idx_action_results_action ON action_results(action_id);
"""

LEGAL_LEASE_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"SATISFIED", "EXPIRED", "CANCELLED"},
    "SATISFIED": set(),
    "EXPIRED": set(),
    "CANCELLED": set(),
    "UNKNOWN": set(),
}

LEGAL_EXECUTION_TRANSITIONS: dict[str, set[str]] = {
    "RUN_STARTED": {"LEASE_OPEN"},
    "LEASE_OPEN": {"FINDING_CREATED"},
    "FINDING_CREATED": {"ACTION_REQUESTED", "LEASE_EVALUATED"},
    "ACTION_REQUESTED": {"ACTION_RESULT_RECORDED"},
    "ACTION_RESULT_RECORDED": {"LEASE_EVALUATED"},
    "LEASE_EVALUATED": {"RUN_COMPLETED"},
    "RUN_COMPLETED": set(),
    "RECOVERY_REQUIRED": set(),
}

IMMUTABLE_TABLES = {"operational_events", "findings", "action_requests", "action_results"}
STATEFUL_TABLES = {"leases", "executions"}
TABLE_PK = {
    "operational_events": "event_id",
    "findings": "finding_id",
    "action_requests": "action_id",
    "action_results": "result_id",
    "leases": "lease_id",
    "executions": "execution_id",
}


class SQLiteBackend:
    """SQLite persistence. Thread-safe via lock. Auto-creates DB + schema."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), timeout=10.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)
        self._validate_schema()
        self._conn.commit()
        self._initialized = True

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.initialize()
        assert self._conn is not None
        return self._conn

    def _validate_schema(self) -> None:
        conn = self._get_conn()
        row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_meta (key, value) VALUES ('version', ?)",
                         (str(SCHEMA_VERSION),))
            return
        version = int(row[0])
        if version > SCHEMA_VERSION:
            raise SchemaUnsupportedError(
                f"Database schema v{version} is newer than supported v{SCHEMA_VERSION}"
            )
        if version < SCHEMA_VERSION:
            raise SchemaUnsupportedError(
                f"Database schema v{version} is older than supported v{SCHEMA_VERSION}. "
                "Cannot safely migrate."
            )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        table = namespace
        pk = TABLE_PK.get(table)
        if not pk:
            return None
        with self._lock:
            row = conn.execute(f"SELECT * FROM {table} WHERE {pk} = ?", (key,)).fetchone()
            if row is None:
                return None
            return self._row_to_dict(table, row)

    def put(self, namespace: str, key: str, value: Mapping[str, Any]) -> None:
        conn = self._get_conn()
        table = namespace
        pk = TABLE_pk(table)
        now = _now()
        with self._lock:
            existing = conn.execute(f"SELECT 1 FROM {table} WHERE {pk} = ?", (key,)).fetchone()
            if existing is None:
                # Auto-fill created_at if not provided
                data = dict(value)
                if "created_at" not in data and table in IMMUTABLE_TABLES:
                    data["created_at"] = now
                cols = [pk] + list(data.keys())
                vals = [key] + list(data.values())
                placeholders = ", ".join(["?"] * len(vals))
                conn.execute(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                    vals,
                )
            else:
                sets = ", ".join(f"{k} = ?" for k in value)
                vals = list(value.values()) + [key]
                conn.execute(f"UPDATE {table} SET {sets} WHERE {pk} = ?", vals)
            conn.commit()

    def put_immutable(self, namespace: str, key: str, data_json: str) -> None:
        conn = self._get_conn()
        table = namespace
        pk = TABLE_pk(table)
        now = _now()
        with self._lock:
            row = conn.execute(f"SELECT data FROM {table} WHERE {pk} = ?", (key,)).fetchone()
            if row is None:
                # Build INSERT with all required columns
                if table == "action_results":
                    # action_id must be extracted from data_json
                    data = json.loads(data_json)
                    action_id = data.get("action_id", "")
                    conn.execute(
                        f"INSERT INTO {table} (result_id, action_id, data, created_at) "
                        f"VALUES (?, ?, ?, ?)",
                        (key, action_id, data_json, now),
                    )
                else:
                    conn.execute(
                        f"INSERT INTO {table} ({pk}, data, created_at) VALUES (?, ?, ?)",
                        (key, data_json, now),
                    )
            elif row[0] == data_json:
                pass  # idempotent
            else:
                raise ConflictError(f"{table}/{key}: content mismatch")
            conn.commit()

    def upsert_stateful(self, namespace: str, key: str, data_json: str,
                         state: str) -> None:
        conn = self._get_conn()
        table = namespace
        pk = TABLE_pk(table)
        legal = (LEGAL_LEASE_TRANSITIONS if table == "leases"
                 else LEGAL_EXECUTION_TRANSITIONS)
        with self._lock:
            row = conn.execute(f"SELECT state, data FROM {table} WHERE {pk} = ?", (key,)).fetchone()
            now = _now()
            if row is None:
                conn.execute(
                    f"INSERT INTO {table} ({pk}, data, state, created_at, updated_at) "
                    f"VALUES (?, ?, ?, ?, ?)",
                    (key, data_json, state, now, now),
                )
            else:
                current_state, current_data = row
                if current_state == state and current_data == data_json:
                    return  # idempotent
                allowed = legal.get(current_state, set())
                if state not in allowed:
                    raise ConflictError(
                        f"Illegal transition: {table}/{key} {current_state} → {state}"
                    )
                conn.execute(
                    f"UPDATE {table} SET data = ?, state = ?, updated_at = ? WHERE {pk} = ?",
                    (data_json, state, now, key),
                )
            conn.commit()

    def delete(self, namespace: str, key: str) -> None:
        conn = self._get_conn()
        table = namespace
        pk = TABLE_PK.get(table)
        if not pk:
            return
        with self._lock:
            conn.execute(f"DELETE FROM {table} WHERE {pk} = ?", (key,))
            conn.commit()

    def list_all(self, namespace: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        table = namespace
        with self._lock:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY created_at, {TABLE_PK[table]}").fetchall()
            return [self._row_to_dict(table, r) for r in rows]

    def list_where(self, namespace: str, field: str, value: Any) -> list[dict[str, Any]]:
        conn = self._get_conn()
        table = namespace
        with self._lock:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {field} = ? ORDER BY created_at, {TABLE_PK[table]}",
                (value,),
            ).fetchall()
            return [self._row_to_dict(table, r) for r in rows]

    def count(self, namespace: str) -> int:
        conn = self._get_conn()
        table = namespace
        with self._lock:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return row[0] if row else 0

    def execute_raw(self, sql: str, params: tuple = ()) -> list[tuple]:
        conn = self._get_conn()
        with self._lock:
            return conn.execute(sql, params).fetchall()

    def update_fields(self, namespace: str, key: str, updates: Mapping[str, Any]) -> None:
        conn = self._get_conn()
        table = namespace
        pk = TABLE_PK.get(table)
        if not pk or not updates:
            return
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [key]
        with self._lock:
            conn.execute(f"UPDATE {table} SET {sets} WHERE {pk} = ?", vals)
            conn.commit()

    def _row_to_dict(self, table: str, row: tuple) -> dict[str, Any]:
        if table == "operational_events":
            return {"event_id": row[0], "data": row[1], "created_at": row[2]}
        if table == "findings":
            return {"finding_id": row[0], "data": row[1], "created_at": row[2]}
        if table == "action_requests":
            return {"action_id": row[0], "data": row[1], "created_at": row[2]}
        if table == "action_results":
            return {"result_id": row[0], "action_id": row[1], "data": row[2], "created_at": row[3]}
        if table == "leases":
            return {"lease_id": row[0], "data": row[1], "state": row[2],
                    "created_at": row[3], "updated_at": row[4]}
        if table == "executions":
            return {
                "execution_id": row[0], "data": row[1],
                "state": row[2], "created_at": row[3], "updated_at": row[4],
            }
        return {}


def TABLE_pk(table: str) -> str:
    return TABLE_PK[table]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Needed for action_results put_immutable
import json
