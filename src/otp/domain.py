"""Source- and channel-neutral immutable domain values."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .canonical import sha256, stable_id


class LeaseState(str, Enum):
    OPEN = "OPEN"
    SATISFIED = "SATISFIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class FindingStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class SentinelVerdict(str, Enum):
    NO_ACTION = "NO_ACTION"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


class ActionStatus(str, Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


@dataclass(frozen=True)
class OperationalEvent:
    event_id: str
    schema_version: str
    source: str
    source_event_type: str
    source_ref: str
    entity_type: str
    entity_id: str
    observed_at: str
    payload: dict[str, Any]
    payload_sha256: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Lease:
    lease_id: str
    kind: str
    subject_ref: str
    opened_at: str
    due_at: str | None
    state: LeaseState
    required_condition: str
    resolution: str | None = None
    closed_at: str | None = None


@dataclass(frozen=True)
class Finding:
    finding_id: str
    rule_id: str
    status: FindingStatus
    severity: str
    subject_ref: str
    reason_code: str
    reason: str
    evidence_refs: tuple[str, ...]
    action_recommended: bool


@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    action_type: str
    target_ref: str
    channel: str
    objective: str
    message: str
    require_ack: bool
    urgency: str
    source_finding_ids: tuple[str, ...]
    authority_context: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    action_id: str
    provider: str
    provider_ref: str | None
    status: ActionStatus
    acknowledged: bool
    response: str | None
    started_at: str | None
    completed_at: str | None
    error_code: str | None
    evidence_refs: tuple[str, ...] = ()


def make_event(**kwargs: Any) -> OperationalEvent:
    payload = kwargs["payload"]
    basis = {key: value for key, value in kwargs.items() if key != "event_id"}
    return OperationalEvent(event_id=stable_id("evt", basis), payload_sha256=sha256(payload), **kwargs)


def make_lease(kind: str, subject_ref: str, opened_at: str, due_at: str | None, required_condition: str) -> Lease:
    basis = {"kind": kind, "subject_ref": subject_ref, "opened_at": opened_at, "due_at": due_at, "required_condition": required_condition}
    return Lease(stable_id("lease", basis), kind, subject_ref, opened_at, due_at, LeaseState.OPEN, required_condition)
