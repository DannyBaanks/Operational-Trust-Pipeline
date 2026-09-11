"""M7: Dock/HOS Collision vertical slice end to end.

Simulator -> geofence -> detention -> HOS collision prediction ->
bounded acknowledgement -> lease SATISFIED -> verified receipt ->
London->Kitchener return match. Runs twice to prove determinism.
"""
from __future__ import annotations

from pathlib import Path

from otp.channels import MockChannel
from otp.domain import LeaseState
from otp.evidence import make_receipt, verify_receipt
from otp.pipeline import FixedClock, resolve_ack_lease, run_ack_lease
from otp.roadstar import RoadStarAdapter
from otp.roadstar_geofence import GeofenceTracker, detention_ack_raw, record_visit, list_visits
from otp.roadstar_hos import evaluate_hos, hos_payload_from_telemetry
from otp.roadstar_matching import Load, rank_loads
from otp.domain import make_event

WORKBOOK = Path(__file__).resolve().parents[1] / "fixtures" / "roadstar" / "Hackathon_Data.xlsx"


def run_collision_once(tmp_path):
    from otp.roadstar_simulator import RoadStarSimulator
    simulator = RoadStarSimulator()
    tracker = GeofenceTracker()
    samples = list(simulator.stream())
    for telemetry in samples:
        tracker.feed(telemetry)
    assert len(tracker.visits) == 1
    visit = tracker.visits[0]

    # Persist arrival first, then the completed visit (crash-recovery order).
    db = tmp_path / "visits.db"
    record_visit(db, visit)
    assert len(list_visits(db)) == 1

    # HOS collision predicted at the detention threshold sample.
    by_event = {s.scenario_event: s for s in samples}
    threshold = by_event["DETENTION_THRESHOLD"]
    payload = hos_payload_from_telemetry(
        threshold, estimated_additional_on_duty_hours=0.5)
    hos_event = make_event(
        schema_version="operational-event/1", source="roadstar-simulator",
        source_event_type="telemetry.hos_observed", source_ref="TRUCK-017",
        entity_type="truck", entity_id="TRUCK-017",
        observed_at=threshold.observed_at, payload=payload)
    finding = evaluate_hos(hos_event)
    assert finding.reason_code == "HOS_EXHAUSTION_DURING_DETENTION"

    # Bounded acknowledgement through the tested ack-lease pipeline.
    raw = detention_ack_raw(visit)
    event = RoadStarAdapter().normalize(raw)
    run = run_ack_lease(
        event, FixedClock("2026-09-12T10:15:00Z"), MockChannel(),
        {"communication_allowed": True, "channel": "mock"})
    assert run["finding"].reason_code == "ACK_LEASE_EXPIRED"
    assert run["result"] is not None
    assert run["result"].recipient_acknowledged()
    lease = resolve_ack_lease(run["lease"], run["finding"], run["result"],
                              FixedClock("2026-09-12T10:16:00Z"))
    assert lease.state is LeaseState.SATISFIED

    # Receipt verifies and carries the satisfied lease.
    run["lease"] = lease
    receipt = make_receipt(run)
    ok, reason = verify_receipt(receipt)
    assert ok, reason

    # Return-load match for the London truck.
    candidates = [
        Load("DEMO-LOCAL", "LONDON", "LONDON", 20000.0, False),
        Load("DEMO-KITCHENER", "MILTON", "KITCHENER", 30000.0, False),
    ]
    results = rank_loads(
        candidates, truck_city="LONDON", capacity_lbs=45000.0,
        hos_remaining_hours=8.0, top_n=5)
    accepted = [r for r in results if r.accepted]
    assert {r.load.load_id for r in accepted} == {"DEMO-LOCAL", "DEMO-KITCHENER"}

    return {
        "visit": visit.as_dict(),
        "finding": finding.reason_code,
        "lease": lease.state.value,
        "receipt": receipt["receipt_sha256"],
        "matches": sorted(r.load.load_id for r in accepted),
    }


def test_dock_hos_collision_slice(tmp_path):
    first = run_collision_once(tmp_path / "run1")
    second = run_collision_once(tmp_path / "run2")
    assert first["visit"] == second["visit"]
    assert first["finding"] == second["finding"] == "HOS_EXHAUSTION_DURING_DETENTION"
    assert first["lease"] == second["lease"] == "SATISFIED"
    assert first["matches"] == second["matches"]
    assert first["receipt"] == second["receipt"]
