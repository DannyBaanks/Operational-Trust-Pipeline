"""Driver duty actions on the LAN receiver."""
from __future__ import annotations

import pytest

flask = pytest.importorskip("flask")

from otp.lan_relay import create_app


@pytest.fixture
def client():
    import otp.lan_relay as relay
    relay._pending.clear()
    relay._responses.clear()
    relay._session_token = "test-token-123"
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def auth():
    return {"X-Session-Token": "test-token-123"}


def test_receiver_page_requires_token(client):
    r = client.get("/receiver")
    assert r.status_code == 401


def test_receiver_page_has_duty_actions(client):
    r = client.get("/receiver?token=test-token-123")
    assert r.status_code == 200
    for label in (b"ACCEPT LOAD", b"REJECT LOAD", b"ARRIVED", b"DEPARTED", b"ACKNOWLEDGE"):
        assert label in r.data


def test_accept_load_resolves_to_ack(client):
    client.post("/api/inject", json={"request_id": "req-accept", "payload": {}},
                headers=auth())
    client.get("/api/poll", headers=auth())
    r = client.post("/api/respond", json={
        "request_id": "req-accept", "acknowledged": True, "action": "ACCEPT LOAD",
        "message": "Taking the London run",
    }, headers=auth())
    assert r.get_json()["ok"] is True
    r = client.get("/api/status/req-accept", headers=auth())
    data = r.get_json()
    assert data["responded"] is True
    assert data["response"]["acknowledged"] is True
    assert data["response"]["action"] == "ACCEPT LOAD"


def test_reject_load_resolves_to_reject(client):
    client.post("/api/inject", json={"request_id": "req-reject", "payload": {}},
                headers=auth())
    client.get("/api/poll", headers=auth())
    client.post("/api/respond", json={
        "request_id": "req-reject", "acknowledged": False,
        "action": "REJECT LOAD", "message": "HOS short",
    }, headers=auth())
    r = client.get("/api/status/req-reject", headers=auth())
    assert r.get_json()["response"]["action"] == "REJECT LOAD"
    assert r.get_json()["response"]["acknowledged"] is False


def test_arrived_and_departed(client):
    for action in ("ARRIVED", "DEPARTED"):
        rid = f"req-{action.lower()}"
        client.post("/api/inject", json={"request_id": rid, "payload": {}},
                    headers=auth())
        client.get("/api/poll", headers=auth())
        client.post("/api/respond", json={
            "request_id": rid, "acknowledged": True, "action": action,
        }, headers=auth())
        r = client.get(f"/api/status/{rid}", headers=auth())
        assert r.get_json()["response"]["action"] == action


def test_retry_same_action_overwrites_without_duplicate(client):
    client.post("/api/inject", json={"request_id": "req-retry", "payload": {}},
                headers=auth())
    client.get("/api/poll", headers=auth())
    for _ in range(3):
        client.post("/api/respond", json={
            "request_id": "req-retry", "acknowledged": True, "action": "ACCEPT LOAD",
        }, headers=auth())
    r = client.get("/api/status/req-retry", headers=auth())
    assert r.get_json()["responded"] is True
    # Second status read is empty: the response is consumed exactly once.
    r = client.get("/api/status/req-retry", headers=auth())
    assert r.get_json()["responded"] is False


def test_default_action_derived_from_ack(client):
    client.post("/api/inject", json={"request_id": "req-default", "payload": {}},
                headers=auth())
    client.get("/api/poll", headers=auth())
    client.post("/api/respond", json={
        "request_id": "req-default", "acknowledged": True,
    }, headers=auth())
    r = client.get("/api/status/req-default", headers=auth())
    assert r.get_json()["response"]["action"] == "ACK"
