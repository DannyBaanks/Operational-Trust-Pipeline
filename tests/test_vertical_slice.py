from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

from otp.canonical import canonical_json
from otp.channels import CalleChannel, DummyChannel, MockChannel
from otp.domain import ActionStatus, FindingStatus, LeaseState
from otp.evidence import append_ledger, make_receipt, verify_ledger, verify_receipt
from otp.pipeline import AckLeasePolicy, FixedClock, run_ack_lease
from otp.roadstar import RoadStarAdapter

ROOT = Path(__file__).resolve().parents[1]

def raw(): return json.loads((ROOT / "fixtures/roadstar/ack_assignment.json").read_text())
def event(): return RoadStarAdapter().normalize(raw())
def run(allowed=True, channel=None): return run_ack_lease(event(), FixedClock("2026-09-10T08:16:00Z"), channel or MockChannel(), {"communication_allowed": allowed, "channel": "mock"})

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
    assert verify_ledger(path) == (True, "PASS")  # Unanchored self-contained chains cannot see a missing tail.

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

import pytest
@pytest.mark.skipif(os.getenv("OTP_LIVE_TEST") != "1", reason="live CALL-E requires explicit OTP_LIVE_TEST=1 and human authorization")
def test_live_calle_is_not_run_by_default():
    pytest.fail("A live test needs separately authorized credentials and target configuration.")
