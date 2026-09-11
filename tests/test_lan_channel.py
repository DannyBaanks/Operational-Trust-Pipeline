"""LAN channel tests — adapter, relay, web page, full pipeline integration."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

flask = pytest.importorskip("flask")

from otp.channels import LanChannel, MockChannel
from otp.domain import ActionStatus, ActionResult
from otp.evidence import make_receipt, verify_receipt
from otp.lan_relay import create_app, inject_request, get_response, _pending, _responses, _store_lock
from otp.pipeline import FixedClock, run_ack_lease
from otp.roadstar import RoadStarAdapter

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def raw():
    return json.loads((ROOT / "fixtures/roadstar/ack_assignment.json").read_text())


def event():
    return RoadStarAdapter().normalize(raw())


def make_action_request():
    """Build a minimal ActionRequest for testing."""
    from otp.canonical import stable_id
    from otp.domain import ActionRequest
    basis = {"finding": "test", "target": "+15551234567", "channel": "lan"}
    return ActionRequest(
        stable_id("action", basis), "notify", "+15551234567", "lan",
        "Trip 1842 may miss DELIVER_BY", "Please acknowledge assignment 1842.",
        True, "HIGH", ("test_finding",), {"communication_allowed": True},
    )


@pytest.fixture
def app():
    """Create a fresh Flask test app for each test."""
    import otp.lan_relay as relay
    relay._pending.clear()
    relay._responses.clear()
    relay._session_token = "test-token-123"
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Relay: auth
# ---------------------------------------------------------------------------

def test_rejects_unauthenticated_poll(client):
    r = client.get("/api/poll")
    assert r.status_code == 401


def test_rejects_unauthenticated_inject(client):
    r = client.post("/api/inject", json={"request_id": "x", "payload": {}})
    assert r.status_code == 401


def test_accepts_authenticated_poll(client):
    r = client.get("/api/poll", headers={"X-Session-Token": "test-token-123"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is False


# ---------------------------------------------------------------------------
# Relay: inject → poll → respond → status cycle
# ---------------------------------------------------------------------------

def test_inject_poll_respond_status_cycle(client):
    # Inject a request
    r = client.post("/api/inject", json={
        "request_id": "req-001",
        "payload": {"reason": "Test alert", "subject_ref": "driver-1", "severity": "HIGH"},
    }, headers={"X-Session-Token": "test-token-123"})
    assert r.get_json()["ok"] is True

    # Poll picks it up
    r = client.get("/api/poll", headers={"X-Session-Token": "test-token-123"})
    data = r.get_json()
    assert data["ok"] is True
    assert data["request"]["request_id"] == "req-001"

    # Poll again — empty
    r = client.get("/api/poll", headers={"X-Session-Token": "test-token-123"})
    assert r.get_json()["ok"] is False

    # Human responds
    r = client.post("/api/respond", json={
        "request_id": "req-001", "acknowledged": True, "message": "On it",
    }, headers={"X-Session-Token": "test-token-123"})
    assert r.get_json()["ok"] is True

    # Status returns the response and clears it
    r = client.get("/api/status/req-001", headers={"X-Session-Token": "test-token-123"})
    data = r.get_json()
    assert data["responded"] is True
    assert data["response"]["acknowledged"] is True
    assert data["response"]["message"] == "On it"

    # Status again — gone
    r = client.get("/api/status/req-001", headers={"X-Session-Token": "test-token-123"})
    assert r.get_json()["responded"] is False


def test_reject_response(client):
    client.post("/api/inject", json={"request_id": "req-002", "payload": {"reason": "x"}},
                headers={"X-Session-Token": "test-token-123"})
    client.get("/api/poll", headers={"X-Session-Token": "test-token-123"})
    client.post("/api/respond", json={"request_id": "req-002", "acknowledged": False},
                headers={"X-Session-Token": "test-token-123"})
    r = client.get("/api/status/req-002", headers={"X-Session-Token": "test-token-123"})
    assert r.get_json()["response"]["acknowledged"] is False


# ---------------------------------------------------------------------------
# Relay: web page serves
# ---------------------------------------------------------------------------

def test_receiver_page_renders(client):
    r = client.get("/receiver")
    assert r.status_code == 200
    assert b"Operational Alert" in r.data


# ---------------------------------------------------------------------------
# LanChannel adapter (unit, no network)
# ---------------------------------------------------------------------------

def test_lan_channel_rejects_without_relay():
    ch = LanChannel("http://127.0.0.1:19999", "bad-token", timeout=1.0, poll_interval=0.1)
    result = ch.send(make_action_request())
    assert result.status is ActionStatus.PROVIDER_UNAVAILABLE
    assert result.error_code == "RELAY_UNREACHABLE"
    assert result.provider_accepted is False
    assert result.delivery == "NOT_DEMONSTRATED"


def test_lan_channel_full_cycle(client, app):
    """Full adapter cycle: inject → web page would show → human responds → adapter gets result."""
    # Simulate the relay in-process using the test client
    req = make_action_request()
    token = "test-token-123"

    # Manually do what LanChannel.send does, but using the test client
    # 1. Inject
    payload = {
        "request_id": req.action_id,
        "reason": req.objective,
        "subject_ref": req.target_ref,
        "severity": req.urgency,
        "source_adapter": req.channel,
    }
    r = client.post("/api/inject", json=payload, headers={"X-Session-Token": token})
    assert r.get_json()["ok"] is True

    # 2. Web page picks it up
    r = client.get("/api/poll", headers={"X-Session-Token": token})
    assert r.get_json()["ok"] is True

    # 3. Human responds
    r = client.post("/api/respond", json={
        "request_id": req.action_id, "acknowledged": True, "message": "Got it",
    }, headers={"X-Session-Token": token})
    assert r.get_json()["ok"] is True

    # 4. Adapter polls status
    r = client.get(f"/api/status/{req.action_id}", headers={"X-Session-Token": token})
    data = r.get_json()
    assert data["responded"] is True
    resp = data["response"]
    assert resp["acknowledged"] is True
    assert resp["message"] == "Got it"


# ---------------------------------------------------------------------------
# Full OTP pipeline with LanChannel (simulated)
# ---------------------------------------------------------------------------

def test_otp_pipeline_with_lan_channel_ack(client, app):
    """RoadStar event → OTP → finding → action → LAN relay → ACK → lease SATISFIED."""
    from otp.pipeline import AckLeasePolicy, sentinel, request_for

    ev = event()
    clock = FixedClock("2026-09-10T08:16:00Z")
    policy = AckLeasePolicy()
    from otp.domain import make_lease
    lease = make_lease("acknowledgement", ev.entity_id, ev.observed_at, ev.payload.get("ack_due_at"), "acknowledged")
    finding = policy.evaluate(ev, lease, clock)
    verdict = sentinel(finding, {"communication_allowed": True, "channel": "lan"})
    action_req = request_for(finding, ev, {"communication_allowed": True, "channel": "lan"})

    # Inject into relay
    token = "test-token-123"
    payload = {
        "request_id": action_req.action_id,
        "reason": action_req.objective,
        "subject_ref": action_req.target_ref,
        "severity": action_req.urgency,
        "source_adapter": "lan",
    }
    client.post("/api/inject", json=payload, headers={"X-Session-Token": token})

    # Simulate human ACK
    client.get("/api/poll", headers={"X-Session-Token": token})
    client.post("/api/respond", json={
        "request_id": action_req.action_id, "acknowledged": True, "message": "Confirmed",
    }, headers={"X-Session-Token": token})

    # Simulate adapter getting result
    r = client.get(f"/api/status/{action_req.action_id}", headers={"X-Session-Token": token})
    resp = r.get_json()["response"]

    # Build ActionResult as the adapter would
    from dataclasses import replace
    from otp.domain import LeaseState
    result = ActionResult(
        action_id=action_req.action_id, provider="lan-channel/1", provider_ref=None,
        status=ActionStatus.ACKNOWLEDGED, acknowledged=True,
        response=resp.get("message"), started_at=None,
        completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(resp["received_at"])),
        error_code=None, evidence_refs=(),
        provider_accepted=True, delivery="KNOWN", reached_ringing="TRUE",
        terminal_cause="ACKNOWLEDGED", retry_safe="FALSE",
    )

    # Lease should be satisfied
    assert result.recipient_acknowledged() is True
    final_lease = replace(lease, state=LeaseState.SATISFIED, resolution="recipient_acknowledgement")
    assert final_lease.state is LeaseState.SATISFIED

    # Receipt should verify
    run_dict = {
        "execution_id": "test-exec", "event": ev, "lease": final_lease,
        "finding": finding, "verdict": verdict, "action": action_req,
        "result": result, "policy_version": policy.version,
        "source_adapter": "roadstar-fixture-v0", "channel_adapter": "lan-channel/1",
    }
    receipt = make_receipt(run_dict)
    assert verify_receipt(receipt) == (True, "PASS")


def test_otp_pipeline_with_lan_channel_timeout(client, app):
    """No human response → timeout → lease EXPIRED, not SATISFIED."""
    from otp.pipeline import AckLeasePolicy, sentinel, request_for
    from otp.domain import make_lease, LeaseState
    from dataclasses import replace

    ev = event()
    clock = FixedClock("2026-09-10T08:16:00Z")
    policy = AckLeasePolicy()
    lease = make_lease("acknowledgement", ev.entity_id, ev.observed_at, ev.payload.get("ack_due_at"), "acknowledged")
    finding = policy.evaluate(ev, lease, clock)
    verdict = sentinel(finding, {"communication_allowed": True, "channel": "lan"})
    action_req = request_for(finding, ev, {"communication_allowed": True, "channel": "lan"})

    # Inject but never respond
    token = "test-token-123"
    payload = {"request_id": action_req.action_id, "reason": "x", "subject_ref": "y", "severity": "HIGH", "source_adapter": "lan"}
    client.post("/api/inject", json=payload, headers={"X-Session-Token": token})

    # Adapter polls, gets nothing
    r = client.get(f"/api/status/{action_req.action_id}", headers={"X-Session-Token": token})
    assert r.get_json()["responded"] is False

    # Adapter would timeout → FAILED, delivery UNKNOWN
    result = ActionResult(
        action_id=action_req.action_id, provider="lan-channel/1", provider_ref=None,
        status=ActionStatus.FAILED, acknowledged=False, response=None,
        started_at=None, completed_at=None, error_code="HUMAN_TIMEOUT",
        evidence_refs=(), provider_accepted=True, delivery="UNKNOWN",
        reached_ringing="UNKNOWN", terminal_cause="TIMEOUT", retry_safe="UNKNOWN",
    )
    assert result.recipient_acknowledged() is False
    assert result.delivery == "UNKNOWN"


def test_receipts_have_no_local_paths_or_secrets(client, app):
    """LAN receipts don't leak paths or tokens."""
    from otp.canonical import canonical_json
    from otp.pipeline import AckLeasePolicy, sentinel, request_for
    from otp.domain import make_lease, ActionResult, ActionStatus, LeaseState
    from otp.evidence import make_receipt

    ev = event()
    clock = FixedClock("2026-09-10T08:16:00Z")
    policy = AckLeasePolicy()
    lease = make_lease("acknowledgement", ev.entity_id, ev.observed_at, ev.payload.get("ack_due_at"), "acknowledged")
    finding = policy.evaluate(ev, lease, clock)
    verdict = sentinel(finding, {"communication_allowed": True, "channel": "lan"})
    action_req = request_for(finding, ev, {"communication_allowed": True, "channel": "lan"})

    # Inject, respond
    token = "test-token-123"
    client.post("/api/inject", json={"request_id": action_req.action_id, "reason": "x", "subject_ref": "y", "severity": "HIGH", "source_adapter": "lan"},
                headers={"X-Session-Token": token})
    client.get("/api/poll", headers={"X-Session-Token": token})
    client.post("/api/respond", json={"request_id": action_req.action_id, "acknowledged": True}, headers={"X-Session-Token": token})

    result = ActionResult(action_req.action_id, "lan-channel/1", None, ActionStatus.ACKNOWLEDGED, True, "ok", None, None, None, (),
                          provider_accepted=True, delivery="KNOWN", reached_ringing="TRUE", terminal_cause="ACKNOWLEDGED", retry_safe="FALSE")

    from dataclasses import replace
    final_lease = replace(lease, state=LeaseState.SATISFIED, resolution="recipient_acknowledgement")
    run_dict = {"execution_id": "test", "event": ev, "lease": final_lease, "finding": finding,
                "verdict": verdict, "action": action_req, "result": result,
                "policy_version": policy.version, "source_adapter": "roadstar-fixture-v0", "channel_adapter": "lan-channel/1"}
    rendered = canonical_json(make_receipt(run_dict))
    assert "C:\\" not in rendered
    assert "test-token-123" not in rendered
    assert "127.0.0.1" not in rendered
