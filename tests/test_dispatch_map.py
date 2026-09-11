"""Dispatch map page and scenario endpoints."""
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


def test_dispatch_page_renders(client):
    r = client.get("/dispatch")
    assert r.status_code == 200
    assert b"RoadStar Dispatch" in r.data
    assert b"leaflet" in r.data.lower()
    assert b"Satellite" in r.data


def test_scenario_requires_auth(client):
    assert client.get("/api/scenario").status_code == 401


def test_scenario_returns_deterministic_stream(client):
    r = client.get("/api/scenario", headers={"X-Session-Token": "test-token-123"})
    data = r.get_json()
    assert data["ok"] is True
    samples = data["samples"]
    assert len(samples) == 11
    assert samples[0]["observed_at"] == "2026-09-12T08:00:00Z"
    assert samples[-1]["scenario_event"] == "DOCK_DEPARTURE"
    events = [s["scenario_event"] for s in samples]
    assert "401_SLOWDOWN" in events
    assert "HOS_COLLISION" in events
    geofence_events = [s["geofence_event"] for s in samples]
    assert geofence_events.count("ENTERED") == 1
    assert geofence_events.count("DEPARTED") == 1


def test_geofence_endpoint(client):
    r = client.get("/api/geofence", headers={"X-Session-Token": "test-token-123"})
    data = r.get_json()
    assert data["ok"] is True
    assert data["geofence"]["facility_id"] == "london-dc-01"
    assert data["geofence"]["radius_km"] == 0.8
