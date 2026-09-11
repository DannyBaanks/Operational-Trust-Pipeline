"""OTP persistence layer.

Backend-agnostic. Default is SQLite at ~/.otp/otp.db.
Memory backend available for tests and explicit ephemeral runs.
"""
from __future__ import annotations

from pathlib import Path

from .errors import ConflictError, CorruptionError, PersistenceError, SchemaUnsupportedError
from .protocol import PersistenceBackend, PersistenceStatus

CONFIG_DIR = Path.home() / ".otp"
DEFAULT_DB = CONFIG_DIR / "otp.db"


def default_backend() -> PersistenceBackend:
    """SQLite at ~/.otp/otp.db. Auto-created on first write."""
    from .sqlite import SQLiteBackend
    return SQLiteBackend(DEFAULT_DB)


def memory_backend() -> PersistenceBackend:
    """In-memory backend for tests and ephemeral runs."""
    from .memory import MemoryBackend
    return MemoryBackend()


__all__ = [
    "PersistenceBackend", "PersistenceStatus",
    "PersistenceError", "ConflictError", "CorruptionError", "SchemaUnsupportedError",
    "CONFIG_DIR", "DEFAULT_DB",
    "default_backend", "memory_backend",
]
