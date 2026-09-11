"""Geofence tracker, detention boundaries, persistence, and receipt."""
from __future__ import annotations

from types import SimpleNamespace

from otp.channels import MockChannel
from otp.evidence import make_receipt, verify_receipt
from otp.pipeline import FixedClock, run_ack_lease
from otp.roadstar import RoadStarAdapter
from otp.roadstar_geofence import (
    DEFAULT_DETENTION_RATE_PER_HOUR,
    GeofenceTracker,
    calculate_detention,
    detention_ack_raw,
    init_geofence_store,
    list_visits,
    record_arrival,
    record_visit,
)
from otp.roadstar_simulator import RoadStarSimulator


def sample(seq, event, facility, observed, truck="TRUCK-017", trip="TRIP-001"):
    return SimpleNamespace(
        sequence=seq, geofence_event=event, facility_id=facility,
        observed_at=observed, truck_id=truck, trip_ref=trip,
    )


def test_detention_boundaries():
    arrival = "2026-09-12T09:40:00Z"
    assert calculate_detention(arrival, "2026-09-12T11:39:59Z")[:2] == (119, 0)
    assert calculate_detention(arrival, "2026-09-12T11:40:00Z")[:2] == (120, 0)
    wait, billable, charge = calculate_detention(arrival, "2026-09-12T11:40:01Z")
    assert (wait, billable) == (120, 0)  # whole-minute truncation at the edge
    wait, billable, charge = calculate_detention(arrival, "2026-09-12T11:41:00Z")
    assert (wait, billable) == (121, 1)
    assert charge == round(1 / 60 * DEFAULT_DETENTION_RATE_PER_HOUR, 2)


def test_tracker_ignores_duplicate_entered():
    tracker = GeofenceTracker()
    tracker.feed(sample(0, "ENTERED", "london-dc-01", "2026-09-12T09:40:00Z"))
    tracker.feed(sample(1, "ENTERED", "london-dc-01", "2026-09-12T09:41:00Z"))
    assert tracker.open_visit is not None
    assert tracker.visits == []
    done = tracker.feed(sample(2, "DEPARTED", None, "2026-09-12T12:00:00Z"))
    assert len(done) == 1
    assert done[0].wait_minutes == 140
    assert done[0].billable_minutes == 20


def test_tracker_ignores_departed_while_outside():
    tracker = GeofenceTracker()
    assert tracker.feed(sample(0, "DEPARTED", None, "2026-09-12T08:00:00Z")) == []
    assert tracker.open_visit is None


def test_reentry_starts_new_visit():
    tracker = GeofenceTracker()
    tracker.feed(sample(0, "ENTERED", "london-dc-01", "2026-09-12T09:40:00Z"))
    first = tracker.feed(sample(1, "DEPARTED", None, "2026-09-12T10:00:00Z"))
    tracker.feed(sample(2, "ENTERED", "london-dc-01", "2026-09-12T11:00:00Z"))
    second = tracker.feed(sample(3, "DEPARTED", None, "2026-09-12T11:30:00Z"))
    assert len(first) == 1 and len(second) == 1
    assert first[0].arrival_at != second[0].arrival_at
    assert len(tracker.visits) == 2


def test_simulator_scenario_produces_one_billable_visit():
    tracker = GeofenceTracker()
    for telemetry in RoadStarSimulator().stream():
        tracker.feed(telemetry)
    assert len(tracker.visits) == 1
    visit = tracker.visits[0]
    assert visit.facility_id == "london-dc-01"
    assert visit.arrival_at == "2026-09-12T09:40:00Z"
    assert visit.departure_at == "2026-09-12T12:10:00Z"
    assert visit.wait_minutes == 150
    assert visit.billable_minutes == 30


def test_arrival_persisted_before_departure_and_recoverable(tmp_path):
    db = tmp_path / "visits.db"
    record_arrival(
        db, facility_id="london-dc-01", truck_id="TRUCK-017",
        trip_ref="TRIP-001", arrival_at="2026-09-12T09:40:00Z",
    )
    stored = list_visits(db)
    assert len(stored) == 1
    assert stored[0]["departure_at"] is None

    # Simulate restart: a fresh tracker observes the stored arrival, then departure
    tracker = GeofenceTracker()
    tracker.feed(sample(0, "ENTERED", "london-dc-01", stored[0]["arrival_at"]))
    done = tracker.feed(sample(1, "DEPARTED", None, "2026-09-12T12:00:00Z"))
    record_visit(db, done[0])
    stored = list_visits(db)
    assert stored[0]["departure_at"] == "2026-09-12T12:00:00Z"
    assert stored[0]["wait_minutes"] == 140
    assert stored[0]["billable_minutes"] == 20


def test_detention_receipt_verifies():
    tracker = GeofenceTracker()
    for telemetry in RoadStarSimulator().stream():
        tracker.feed(telemetry)
    visit = tracker.visits[0]
    raw = detention_ack_raw(visit)
    event = RoadStarAdapter().normalize(raw)
    run = run_ack_lease(
        event, FixedClock("2026-09-12T09:45:00Z"), MockChannel(),
        {"communication_allowed": True, "channel": "mock"},
    )
    receipt = make_receipt(run)
    ok, reason = verify_receipt(receipt)
    assert ok, reason
    assert receipt["components"]["event"]["source_ref"].startswith("DET-london-dc-01-")


def test_store_upsert_is_idempotent(tmp_path):
    db = tmp_path / "visits.db"
    init_geofence_store(db)
    record_arrival(
        db, facility_id="london-dc-01", truck_id="TRUCK-017",
        trip_ref="TRIP-001", arrival_at="2026-09-12T09:40:00Z",
    )
    record_arrival(
        db, facility_id="london-dc-01", truck_id="TRUCK-017",
        trip_ref="TRIP-001", arrival_at="2026-09-12T09:40:00Z",
    )
    assert len(list_visits(db)) == 1
