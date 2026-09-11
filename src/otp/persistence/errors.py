"""Persistence errors."""
from __future__ import annotations


class PersistenceError(Exception):
    """Base persistence error."""


class ConflictError(PersistenceError):
    """Same ID, different canonical content. Never silently overwrite."""


class CorruptionError(PersistenceError):
    """Data integrity violation."""


class SchemaUnsupportedError(PersistenceError):
    """Database has a schema version this code cannot safely operate on."""
