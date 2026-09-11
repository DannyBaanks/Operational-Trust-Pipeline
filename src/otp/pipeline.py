from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .canonical import sha256, stable_id
from .contracts import ChannelProvider, Clock
from .domain import ActionRequest, ActionResult, Finding, FindingStatus, Lease, LeaseState, OperationalEvent, SentinelVerdict, make_lease


class FixedClock:
    def __init__(self, instant: str) -> None: self.instant = datetime.fromisoformat(instant.replace("Z", "+00:00"))
    def now(self) -> datetime: return self.instant


class AckLeasePolicy:
    version = "ack-lease-v0"
    def evaluate(self, event: OperationalEvent, lease: Lease, clock: Clock) -> Finding:
        due = datetime.fromisoformat((lease.due_at or "").replace("Z", "+00:00")) if lease.due_at else None
        acknowledged = event.payload.get("acknowledged_at")
        if due is None:
            status, code, reason, action = FindingStatus.UNKNOWN, "ACK_DUE_UNKNOWN", "Acknowledgement deadline is missing.", False
        elif acknowledged:
            status, code, reason, action = FindingStatus.PASS, "ACK_OBSERVED", "Acknowledgement observed.", False
        elif clock.now() < due:
            status, code, reason, action = FindingStatus.PASS, "ACK_LEASE_OPEN", "Acknowledgement lease remains open.", False
        else:
            status, code, reason, action = FindingStatus.FAIL, "ACK_LEASE_EXPIRED", "Acknowledgement was not observed by the deadline.", True
        basis = {"rule": self.version, "event": event.event_id, "lease": lease.lease_id, "code": code}
        return Finding(stable_id("finding", basis), self.version, status, "HIGH" if action else "INFO", lease.subject_ref, code, reason, (event.event_id, lease.lease_id), action)


class DeliveryTimingPolicy:
    version = "roadstar-delivery-timing-v0"
    def evaluate(self, event: OperationalEvent) -> Finding:
        due, expected, latest = event.payload.get("due_at"), event.payload.get("expected_at"), event.payload.get("latest_state_at")
        if not due or (not expected and not latest):
            status, code, reason, action = FindingStatus.UNKNOWN, "DELIVERY_TIMING_UNKNOWN", "Delivery timing inputs are incomplete.", False
        elif expected and expected > due:
            status, code, reason, action = FindingStatus.FAIL, "ETA_THRESHOLD_EXCEEDED", "Expected arrival is after the delivery deadline.", True
        elif latest and latest > due:
            status, code, reason, action = FindingStatus.FAIL, "DELIVERY_WINDOW_EXCEEDED", "Latest observed state is after the delivery deadline.", True
        else:
            status, code, reason, action = FindingStatus.PASS, "DELIVERY_TIMING_WITHIN_WINDOW", "Observed timing is within the delivery window.", False
        basis = {"rule": self.version, "event": event.event_id, "code": code}
        return Finding(stable_id("finding", basis), self.version, status, "HIGH" if action else "INFO", event.entity_id, code, reason, (event.event_id,), action)


class HosCapacityPolicy:
    version = "roadstar-hos-capacity-v0"
    active_statuses = frozenset({"ASSGN", "DISP", "DEPSHIP", "ARRSHIP", "DEPCONS", "ARRCONS"})
    def evaluate(self, event: OperationalEvent) -> Finding:
        remaining, status = event.payload.get("remaining_hours"), event.payload.get("operation_status")
        if not isinstance(remaining, (int, float)):
            outcome, code, reason, action = FindingStatus.UNKNOWN, "HOS_CAPACITY_UNKNOWN", "Remaining HOS capacity is missing or invalid.", False
        elif remaining <= 0 and status in self.active_statuses:
            outcome, code, reason, action = FindingStatus.FAIL, "HOS_CAPACITY_EXHAUSTED", "Active driver has no remaining reported HOS capacity.", True
        else:
            outcome, code, reason, action = FindingStatus.PASS, "HOS_CAPACITY_AVAILABLE", "No active capacity exhaustion is observed.", False
        basis = {"rule": self.version, "event": event.event_id, "code": code}
        return Finding(stable_id("finding", basis), self.version, outcome, "HIGH" if action else "INFO", event.entity_id, code, reason, (event.event_id,), action)


def sentinel(finding: Finding, authority_context: dict[str, Any]) -> SentinelVerdict:
    if finding.status is FindingStatus.UNKNOWN: return SentinelVerdict.NEEDS_REVIEW
    if not finding.action_recommended: return SentinelVerdict.NO_ACTION
    return SentinelVerdict.ACTION_REQUESTED if authority_context.get("communication_allowed") is True else SentinelVerdict.BLOCKED


def request_for(finding: Finding, event: OperationalEvent, authority_context: dict[str, Any]) -> ActionRequest:
    basis = {"finding": finding.finding_id, "target": event.payload["contact_ref"], "channel": authority_context.get("channel", "mock")}
    return ActionRequest(stable_id("action", basis), "notify", event.payload["contact_ref"], authority_context.get("channel", "mock"),
                         "Request acknowledgement for an overdue operational assignment.", "Please acknowledge assignment " + event.source_ref + ".",
                         True, "HIGH", (finding.finding_id,), dict(authority_context))


def execution_id(event: OperationalEvent, lease: Lease, policy: AckLeasePolicy) -> str:
    return stable_id("exec", {"event": sha256(event), "state": sha256(lease), "policy": policy.version, "operation": "evaluate"})


def run_ack_lease(event: OperationalEvent, clock: Clock, channel: ChannelProvider, authority_context: dict[str, Any]) -> dict[str, Any]:
    lease = make_lease("acknowledgement", event.entity_id, event.observed_at, event.payload.get("ack_due_at"), "acknowledged")
    policy = AckLeasePolicy(); finding = policy.evaluate(event, lease, clock); verdict = sentinel(finding, authority_context)
    action = request_for(finding, event, authority_context) if verdict is SentinelVerdict.ACTION_REQUESTED else None
    result = channel.send(action) if action else None
    # Recipient-side acknowledgement only. Provider-side "accepted" or
    # "NO ANSWER / 0s" does not satisfy an acknowledgement lease.
    if result and result.recipient_acknowledged():
        lease = replace(lease, state=LeaseState.SATISFIED, resolution="recipient_acknowledgement", closed_at=clock.now().isoformat().replace("+00:00", "Z"))
    elif finding.reason_code == "ACK_LEASE_EXPIRED":
        lease = replace(lease, state=LeaseState.EXPIRED)
    return {"execution_id": execution_id(event, lease, policy), "event": event, "lease": lease, "finding": finding,
            "verdict": verdict, "action": action, "result": result, "policy_version": policy.version, "source_adapter": "roadstar-fixture-v0", "channel_adapter": channel.identity}
