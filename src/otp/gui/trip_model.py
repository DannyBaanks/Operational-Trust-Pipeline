"""TripItem data model and state computation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TripState(str, Enum):
    CRITICAL = "CRITICAL"
    AT_RISK = "AT_RISK"
    WAITING_ACK = "WAITING_ACK"
    DELIVERY_UNCERTAIN = "DELIVERY_UNCERTAIN"
    ON_TIME = "ON_TIME"
    RESOLVED = "RESOLVED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


STATE_SEVERITY = {
    TripState.CRITICAL: 0,
    TripState.AT_RISK: 1,
    TripState.WAITING_ACK: 2,
    TripState.DELIVERY_UNCERTAIN: 3,
    TripState.ON_TIME: 4,
    TripState.RESOLVED: 5,
    TripState.BLOCKED: 6,
    TripState.UNKNOWN: 7,
}


STATE_LABELS = {
    TripState.CRITICAL: "CRITICAL",
    TripState.AT_RISK: "AT RISK",
    TripState.WAITING_ACK: "WAITING ACK",
    TripState.DELIVERY_UNCERTAIN: "DELIVERY UNCERTAIN",
    TripState.ON_TIME: "ON TIME",
    TripState.RESOLVED: "RESOLVED",
    TripState.BLOCKED: "BLOCKED",
    TripState.UNKNOWN: "UNKNOWN",
}


STATE_ACTIONS = {
    TripState.CRITICAL: "ACK NOW",
    TripState.AT_RISK: "MONITOR",
    TripState.WAITING_ACK: "WAITING",
    TripState.DELIVERY_UNCERTAIN: "RETRY?",
    TripState.ON_TIME: "\u2014",
    TripState.RESOLVED: "\u2713 DONE",
    TripState.BLOCKED: "\u2014",
    TripState.UNKNOWN: "REVIEW",
}


@dataclass
class TripItem:
    trip_id: str
    driver_id: str
    assignment_id: str
    eta: str | None = None
    deliver_by: str | None = None
    delta_minutes: int | None = None
    state: TripState = TripState.UNKNOWN
    finding_code: str = ""
    finding_message: str = ""
    finding_severity: str = "INFO"
    channel_status: str = "NONE"
    ack_status: str = "none"
    last_attempt: str | None = None
    receipt_hash: str | None = None
    receipt_verified: bool = False
    remaining_hos: float | None = None
    operation_status: str | None = None
    raw_event: Any = field(default=None, repr=False)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _format_time(value: str | None) -> str:
    dt = _parse_time(value)
    if dt is None:
        return "\u2014"
    return dt.strftime("%H:%M")


def _format_delta(minutes: int | None) -> str:
    if minutes is None:
        return "\u2014"
    sign = "+" if minutes > 0 else ""
    return f"{sign}{minutes}m"


def compute_state(item: TripItem) -> TripState:
    if item.ack_status == "acknowledged":
        return TripState.RESOLVED
    if item.ack_status == "waiting":
        return TripState.WAITING_ACK
    if item.delta_minutes is not None and item.delta_minutes > 0:
        return TripState.CRITICAL
    if item.delta_minutes is not None and item.delta_minutes > -30:
        return TripState.AT_RISK
    if item.delta_minutes is not None:
        return TripState.ON_TIME
    return TripState.UNKNOWN


def trip_fromRoadStar_dispatch(row: dict[str, Any], driver_hos: dict[str, float] | None = None) -> TripItem:
    """Build TripItem from a normalized RoadStar dispatch row."""
    eta_str = row.get("_eta_iso") or row.get("expected_at") or row.get("LS_EXPECTED_DATE", "")
    due_str = row.get("_due_iso") or row.get("due_at") or row.get("DELIVER_BY", "")

    eta_dt = _parse_time(eta_str)
    due_dt = _parse_time(due_str)
    delta = None
    if eta_dt and due_dt:
        delta = int((eta_dt - due_dt).total_seconds() / 60)

    trip_id = str(row.get("trip_ref") or row.get("TRIP_NUMBER") or "")
    driver_id = str(row.get("assignee_ref") or row.get("driver_id") or row.get("DRIVER_ID") or "")
    assignment_id = str(row.get("leg_ref") or row.get("LS_LEG_ID") or "")
    remaining = None
    if driver_hos and driver_id in driver_hos:
        remaining = driver_hos[driver_id]

    return TripItem(
        trip_id=trip_id,
        driver_id=driver_id,
        assignment_id=assignment_id,
        eta=eta_str or None,
        deliver_by=due_str or None,
        delta_minutes=delta,
        state=TripState.UNKNOWN,
        finding_code="",
        finding_message="",
        finding_severity="INFO",
        remaining_hos=remaining,
        operation_status=row.get("operation_status") or row.get("STATUS"),
    )
