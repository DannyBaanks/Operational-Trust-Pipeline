"""Canadian Hours-of-Service decision support for RoadStar.

Modeled from the South-of-60 limits in the challenge brief. This is decision
support, not ELD certification and not a legal compliance guarantee.

AT_RISK is expressed as Finding status FAIL with severity MEDIUM and a
reason_code ending in _AT_RISK, because the shared FindingStatus enum only
carries PASS/FAIL/UNKNOWN (and the C portable maps the same three values).
Exhaustion uses severity HIGH.
"""
from __future__ import annotations

from typing import Any

from .canonical import stable_id
from .domain import Finding, FindingStatus, OperationalEvent

VERSION = "roadstar-hos-ca-v0"

DRIVING_LIMIT = 13.0
ON_DUTY_LIMIT = 14.0
ELAPSED_LIMIT = 16.0
OFF_DUTY_REQUIRED = 10.0
CORE_REST_REQUIRED = 8.0
AT_RISK_THRESHOLD = 1.0


def _num(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) else None


def evaluate_hos(event: OperationalEvent) -> Finding:
    """Evaluate Canadian HOS remaining-hours payload. Never invents data."""
    payload = event.payload or {}
    driving = _num(payload.get("driving_hours_remaining"))
    on_duty = _num(payload.get("on_duty_hours_remaining"))
    elapsed = _num(payload.get("elapsed_window_hours_remaining"))
    cycle = _num(payload.get("cycle_hours_remaining"))
    off_duty = _num(payload.get("off_duty_hours"))
    core_rest = _num(payload.get("core_rest_hours"))
    extra = _num(payload.get("estimated_additional_on_duty_hours"))

    if driving is None or on_duty is None or elapsed is None:
        return _finding(event, FindingStatus.UNKNOWN, "INFO", "HOS_DATA_UNKNOWN",
                        "Required HOS remaining-hours inputs are missing.", False)

    exhausted = [
        ("driving", driving, DRIVING_LIMIT),
        ("on-duty", on_duty, ON_DUTY_LIMIT),
        ("elapsed window", elapsed, ELAPSED_LIMIT),
    ]
    for name, remaining, _ in exhausted:
        if remaining <= 0:
            return _finding(event, FindingStatus.FAIL, "HIGH", "HOS_LIMIT_EXHAUSTED",
                            f"{name} limit exhausted ({remaining:.2f} h remaining).", True)
    if cycle is not None and cycle <= 0:
        return _finding(event, FindingStatus.FAIL, "HIGH", "HOS_LIMIT_EXHAUSTED",
                        "Cycle limit exhausted (0 h remaining).", True)
    if off_duty is not None and off_duty < OFF_DUTY_REQUIRED:
        return _finding(event, FindingStatus.FAIL, "HIGH", "HOS_REST_INCOMPLETE",
                        f"Off-duty {off_duty:.2f} h is below the required {OFF_DUTY_REQUIRED:.0f} h.", True)
    if core_rest is not None and core_rest < CORE_REST_REQUIRED:
        return _finding(event, FindingStatus.FAIL, "HIGH", "HOS_REST_INCOMPLETE",
                        f"Core rest {core_rest:.2f} h is below the required {CORE_REST_REQUIRED:.0f} h.", True)

    if extra is not None and extra > 0:
        margins = {"on-duty": on_duty, "elapsed window": elapsed, "driving": driving}
        if cycle is not None:
            margins["cycle"] = cycle
        limit, margin = min(margins.items(), key=lambda item: item[1])
        if margin - extra <= 0:
            return _finding(
                event, FindingStatus.FAIL, "HIGH", "HOS_EXHAUSTION_DURING_DETENTION",
                f"Driver will exhaust the {limit} limit during detention "
                f"({margin:.2f} h remaining, {extra:.2f} h estimated).", True)

    at_risk = [
        ("driving", driving),
        ("on-duty", on_duty),
        ("elapsed window", elapsed),
    ]
    if cycle is not None:
        at_risk.append(("cycle", cycle))
    for name, remaining in at_risk:
        if remaining <= AT_RISK_THRESHOLD:
            return _finding(event, FindingStatus.FAIL, "MEDIUM", "HOS_LIMIT_AT_RISK",
                            f"{name} limit at risk ({remaining:.2f} h remaining).", True)

    return _finding(event, FindingStatus.PASS, "INFO", "HOS_WITHIN_LIMITS",
                    "HOS remaining-hours are within modeled limits.", False)


def hos_payload_from_telemetry(telemetry: Any, **extra: Any) -> dict[str, Any]:
    """Build an HOS payload from a simulator Telemetry sample."""
    payload = {
        "driving_hours_remaining": getattr(telemetry, "driving_hours_remaining", None),
        "on_duty_hours_remaining": getattr(telemetry, "on_duty_hours_remaining", None),
        "elapsed_window_hours_remaining": getattr(telemetry, "elapsed_window_hours_remaining", None),
        "cycle_hours_remaining": getattr(telemetry, "cycle_hours_remaining", None),
        "dock_wait_minutes": getattr(telemetry, "dock_wait_minutes", None),
        "facility_id": getattr(telemetry, "facility_id", None),
        "trip_ref": getattr(telemetry, "trip_ref", None),
    }
    payload.update(extra)
    return payload


def _finding(
    event: OperationalEvent,
    status: FindingStatus,
    severity: str,
    code: str,
    reason: str,
    action: bool,
) -> Finding:
    basis = {"rule": VERSION, "event": event.event_id, "code": code}
    return Finding(stable_id("finding", basis), VERSION, status, severity,
                   event.entity_id, code, reason, (event.event_id,), action)
