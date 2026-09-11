from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

from otp.canonical import canonical_json
from otp.channels import CalleChannel, DummyChannel, MockChannel
from otp.domain import ActionStatus, ActionResult, FindingStatus, LeaseState
from otp.evidence import append_ledger, make_receipt, verify_ledger, verify_receipt
from otp.pipeline import AckLeasePolicy, DeliveryTimingPolicy, FixedClock, HosCapacityPolicy, run_ack_lease
from otp.roadstar import RoadStarAdapter

ROOT = Path(__file__).resolve().parents[1]

def raw(): return json.loads((ROOT / "fixtures/roadstar/ack_assignment.json").read_text())
def event(): return RoadStarAdapter().normalize(raw())
def run(allowed=True, channel=None): return run_ack_lease(event(), FixedClock("2026-09-10T08:16:00Z"), channel or MockChannel(), {"communication_allowed": allowed, "channel": "mock"})


# ---------------------------------------------------------------------------
# Regression: NO ANSWER zero-duration channel
# ---------------------------------------------------------------------------

class NoAnswerChannel:
    """Simulates a CALL-E result with NO ANSWER, 0s duration, no ringing.
    This is the concrete case from the live test to +525615009116."""
    identity = "no-answer-channel/1"
    def send(self, request):
        return ActionResult(
            action_id=request.action_id,
            provider="calle-channel/1",
            provider_ref="mock-no-answer",
            status=ActionStatus.FAILED,
            acknowledged=False,
            response="NO ANSWER",
            started_at="2026-09-10T15:15:00Z",
            completed_at="2026-09-10T15:15:00Z",
            error_code="NO_ANSWER",
            evidence_refs=(),
            provider_accepted=True,
            delivery="UNKNOWN",
            reached_ringing="UNKNOWN",
            terminal_cause="ByCallee",
            retry_safe="UNKNOWN",
        )


class AnsweredChannel:
    """Simulates a successful call with ringing and answer."""
    identity = "answered-channel/1"
    def send(self, request):
        return ActionResult(
            action_id=request.action_id,
            provider="calle-channel/1",
            provider_ref="mock-answered",
            status=ActionStatus.ACKNOWLEDGED,
            acknowledged=True,
            response="Call answered",
            started_at="2026-09-10T15:15:00Z",
            completed_at="2026-09-10T15:15:45Z",
            error_code=None,
            evidence_refs=(),
            provider_accepted=True,
            delivery="KNOWN",
            reached_ringing="TRUE",
            terminal_cause="SUCCESS",
            retry_safe="FALSE",
        )


# --- Original tests (14) ---

def test_canonical_event_and_execution_are_deterministic():
    assert event() == event()
    assert run()["execution_id"] == run()["execution_id"]
    assert canonical_json(event()) == canonical_json(event())

def test_lease_expiry_is_injected_and_exact():
    initial = run_ack_lease(event(), FixedClock("2026-09-10T08:14:59Z"), MockChannel(), {"communication_allowed": True})
    assert initial["lease"].state is LeaseState.OPEN and initial["finding"].reason_code == "ACK_LEASE_OPEN"
    due = run(); assert due["finding"].reason_code == "ACK_LEASE_EXPIRED"

def test_missing_required_deadline_is_unknown_not_pass():
    broken = replace(event(), payload={**event().payload, "ack_due_at": None})
    outcome = run_ack_lease(broken, FixedClock("2026-09-10T08:16:00Z"), MockChannel(), {"communication_allowed": True})
    assert outcome["finding"].status is FindingStatus.UNKNOWN and outcome["verdict"].value == "NEEDS_REVIEW"

def test_finding_does_not_dispatch_when_sentinel_denies():
    channel = MockChannel(); outcome = run(False, channel)
    assert outcome["finding"].action_recommended and outcome["verdict"].value == "BLOCKED"
    assert outcome["result"] is None and channel.requests == []

def test_mock_result_resolves_only_its_lease():
    outcome = run(); assert outcome["result"].status is ActionStatus.ACKNOWLEDGED
    assert outcome["lease"].state is LeaseState.SATISFIED

def test_receipt_detects_mutated_components():
    receipt = make_receipt(run()); assert verify_receipt(receipt) == (True, "PASS")
    for component, field in (("event", "source"), ("finding", "reason"), ("action", "message"), ("result", "response")):
        altered = make_receipt(run()); altered["components"][component][field] = "tampered"
        assert verify_receipt(altered)[0] is False

def test_ledger_detects_reorder_insert_and_middle_deletion(tmp_path):
    path = tmp_path / "ledger.jsonl"
    for _ in range(3): append_ledger(path, make_receipt(run()))
    assert verify_ledger(path) == (True, "PASS")
    lines = path.read_text().splitlines(); path.write_text("\n".join(reversed(lines)) + "\n")
    assert verify_ledger(path)[0] is False
    path.write_text("\n".join(lines[:1] + lines[:1] + lines[1:]) + "\n")
    assert verify_ledger(path)[0] is False
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert verify_ledger(path)[0] is False

def test_tail_truncation_is_documented_limit(tmp_path):
    path = tmp_path / "ledger.jsonl"; append_ledger(path, make_receipt(run())); append_ledger(path, make_receipt(run()))
    path.write_text(path.read_text().splitlines()[0] + "\n")
    assert verify_ledger(path) == (True, "PASS")

def test_channel_provider_swap_and_calle_stays_offline():
    assert run(channel=MockChannel())["result"].provider == "mock-channel/1"
    assert run(channel=DummyChannel())["result"].provider == "dummy-channel/1"
    calle = CalleChannel(); result = calle.send(run()["action"])
    assert result.status is ActionStatus.NOT_DEMONSTRATED and result.error_code == "LIVE_DISABLED"

def test_receipts_have_no_local_paths_or_secrets_and_mock_is_not_live():
    rendered = canonical_json(make_receipt(run()))
    assert "C:\\" not in rendered and "api_key" not in rendered.lower() and "live" not in run()["result"].provider

def test_policy_consumes_normalized_event_not_roadstar_columns():
    normalized = event()
    assert "assignment_id" not in normalized.payload
    assert AckLeasePolicy().evaluate(normalized, run()["lease"], FixedClock("2026-09-10T08:16:00Z")).rule_id == "ack-lease-v0"

def test_official_roadstar_dispatch_maps_and_finds_late_eta():
    adapter = RoadStarAdapter()
    source = ROOT / "fixtures/roadstar/Hackathon_Data.xlsx"
    row = next(row for row in adapter.dispatch_rows(source) if row["LS_EXPECTED_DATE"] and row["DELIVER_BY"] and row["LS_EXPECTED_DATE"] > row["DELIVER_BY"])
    normalized = adapter.normalize(row)
    finding = DeliveryTimingPolicy().evaluate(normalized)
    assert normalized.source_event_type == "dispatch.leg_observed"
    assert "LS_EXPECTED_DATE" not in normalized.payload
    assert finding.reason_code == "ETA_THRESHOLD_EXCEEDED"

def test_official_roadstar_driver_maps_and_finds_active_hos_exhaustion():
    adapter = RoadStarAdapter()
    source = ROOT / "fixtures/roadstar/Hackathon_Data.xlsx"
    row = next(row for row in adapter.driver_rows(source) if row["REMAINING_HOURS"] == 0 and row["STATUS"] == "DISP")
    finding = HosCapacityPolicy().evaluate(adapter.normalize(row))
    assert finding.reason_code == "HOS_CAPACITY_EXHAUSTED"


# --- Delivery-uncertainty regression tests (5) ---

def test_no_answer_zero_duration_does_not_satisfy_lease():
    """NO ANSWER + 0s + no ringing = DELIVERY_UNCERTAIN, lease NOT SATISFIED."""
    outcome = run_ack_lease(event(), FixedClock("2026-09-10T08:16:00Z"), NoAnswerChannel(),
                            {"communication_allowed": True, "channel": "no-answer"})
    assert outcome["result"].status is ActionStatus.FAILED
    assert outcome["result"].delivery == "UNKNOWN"
    assert outcome["result"].reached_ringing == "UNKNOWN"
    assert outcome["result"].terminal_cause == "ByCallee"
    assert outcome["result"].provider_accepted is True
    assert outcome["result"].recipient_acknowledged() is False
    assert outcome["lease"].state is LeaseState.EXPIRED

def test_no_answer_zero_duration_is_not_recipient_acknowledged():
    """provider_accepted=True but delivery=UNKNOWN must not count as recipient ack."""
    result = NoAnswerChannel().send(run()["action"])
    assert result.recipient_acknowledged() is False
    assert result.provider_accepted is True
    assert result.delivery == "UNKNOWN"

def test_answered_call_satisfies_lease():
    """Successful call with delivery=KNOWN satisfies the lease."""
    outcome = run_ack_lease(event(), FixedClock("2026-09-10T08:16:00Z"), AnsweredChannel(),
                            {"communication_allowed": True, "channel": "answered"})
    assert outcome["result"].status is ActionStatus.ACKNOWLEDGED
    assert outcome["result"].delivery == "KNOWN"
    assert outcome["result"].reached_ringing == "TRUE"
    assert outcome["result"].recipient_acknowledged() is True
    assert outcome["lease"].state is LeaseState.SATISFIED
    assert outcome["lease"].resolution == "recipient_acknowledgement"

def test_no_answer_after_deadline_expires_not_satisfied():
    """NO ANSWER after deadline: lease is EXPIRED, not SATISFIED."""
    outcome = run_ack_lease(event(), FixedClock("2026-09-10T08:16:00Z"), NoAnswerChannel(),
                            {"communication_allowed": True, "channel": "no-answer"})
    assert outcome["lease"].state is LeaseState.EXPIRED
    assert outcome["result"].delivery == "UNKNOWN"
    assert outcome["result"].recipient_acknowledged() is False

def test_no_answer_before_deadline_no_action_dispatched():
    """Before deadline, NO ANSWER does not trigger dispatch (lease stays OPEN)."""
    outcome = run_ack_lease(event(), FixedClock("2026-09-10T08:14:59Z"), NoAnswerChannel(),
                            {"communication_allowed": True, "channel": "no-answer"})
    assert outcome["lease"].state is LeaseState.OPEN
    assert outcome["result"] is None  # no action dispatched before expiry
    assert outcome["verdict"].value == "NO_ACTION"

def test_calle_offline_delivery_is_not_demonstrated():
    """CalleChannel with live=False produces delivery=NOT_DEMONSTRATED."""
    calle = CalleChannel()
    result = calle.send(run()["action"])
    assert result.delivery == "NOT_DEMONSTRATED"
    assert result.recipient_acknowledged() is False
    assert result.provider_accepted is False


import pytest
@pytest.mark.skipif(os.getenv("OTP_LIVE_TEST") != "1", reason="live CALL-E requires explicit OTP_LIVE_TEST=1 and human authorization")
def test_live_calle_is_not_run_by_default():
    pytest.fail("A live test needs separately authorized credentials and target configuration.")
