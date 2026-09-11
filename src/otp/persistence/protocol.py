"""Persistence backend protocol and status enum."""
from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, Mapping


class PersistenceStatus(Enum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"
    CORRUPT = "CORRUPT"
    SCHEMA_UNSUPPORTED = "SCHEMA_UNSUPPORTED"
    CONFLICT = "CONFLICT"
    WRITE_FAILED = "WRITE_FAILED"
    READ_FAILED = "READ_FAILED"


class PersistenceBackend(Protocol):
    """Backend-agnostic persistence contract.

    Domain code must not import sqlite3 or any specific backend.
    Only the backend implementation knows its storage mechanism.
    """

    def initialize(self) -> None:
        """Create directory and schema if absent. Idempotent."""
        ...

    def close(self) -> None:
        """Release resources. Safe to call multiple times."""
        ...

    def get(self, namespace: str, key: str) -> Mapping[str, Any] | None:
        """Retrieve a record. Returns None if absent."""
        ...

    def put(self, namespace: str, key: str, value: Mapping[str, Any]) -> None:
        """Insert or idempotently update a record."""
        ...

    def put_immutable(self, namespace: str, key: str, data_json: str) -> None:
        """Insert immutable record. Idempotent if identical, ConflictError if different."""
        ...

    def upsert_stateful(self, namespace: str, key: str, data_json: str,
                         state: str) -> None:
        """Insert or transition a stateful record. ConflictError on illegal transition."""
        ...

    def delete(self, namespace: str, key: str) -> None:
        """Delete a record. No-op if absent."""
        ...

    def list_all(self, namespace: str) -> list[Mapping[str, Any]]:
        """List all records in a namespace. Deterministic order."""
        ...

    def list_where(self, namespace: str, field: str, value: Any) -> list[Mapping[str, Any]]:
        """List records matching a field value."""
        ...

    def count(self, namespace: str) -> int:
        """Count records in a namespace."""
        ...

    def execute_raw(self, sql: str, params: tuple = ()) -> list[tuple]:
        """Execute raw SQL for verification. Only for backend-specific checks."""
        ...

    def update_fields(self, namespace: str, key: str, updates: Mapping[str, Any]) -> None:
        """Update specific fields of a record. No-op if absent."""
        ...
