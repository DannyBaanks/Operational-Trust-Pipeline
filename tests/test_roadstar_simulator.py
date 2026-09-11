"""Deterministic RoadStar simulator tests."""
from __future__ import annotations

import pytest

from otp.roadstar_simulator import (
    LONDON_FACILITY,
    RoadStarSimulator,
    distance_km,
    inside_geofence,
)


def test_same_seed_produces_same_telemetry():
    first = [item.as_dict() for item in RoadStarSimulator(seed=17).stream()]
    second = [item.as_dict() for item in RoadStarSimulator(seed=17).stream()]
    assert first == second


def test_stream_has_monotonic_time_distance_and_odometer():
    samples = list(RoadStarSimulator().stream())
    assert len(samples) == 11
    assert [sample.sequence for sample in samples] == list(range(11))
    assert [sample.observed_at for sample in samples] == sorted(sample.observed_at for sample in samples)
    assert [sample.distance_km for sample in samples] == sorted(sample.distance_km for sample in samples)
    assert [sample.odometer_km for sample in samples] == sorted(sample.odometer_km for sample in samples)


def test_scenario_contains_slowdown_dock_threshold_and_hos_collision():
    events = [sample.scenario_event for sample in RoadStarSimulator().stream()]
    assert "401_SLOWDOWN" in events
    assert "DOCK_ARRIVAL" in events
    assert "DETENTION_THRESHOLD" in events
    assert "HOS_COLLISION" in events


def test_geofence_transitions_are_single_entry_and_departure():
    samples = list(RoadStarSimulator().stream())
    assert [sample.geofence_event for sample in samples].count("ENTERED") == 1
    assert [sample.geofence_event for sample in samples].count("DEPARTED") == 1
    inside = [sample for sample in samples if sample.facility_id == LONDON_FACILITY.facility_id]
    assert inside
    assert all(inside_geofence(sample.latitude, sample.longitude, LONDON_FACILITY) for sample in inside)


def test_dock_wait_crosses_two_hour_threshold():
    waits = [sample.dock_wait_minutes for sample in RoadStarSimulator().stream()]
    assert max(waits) == 140
    assert 120 in waits
    assert all(left >= 0 for left in waits)


def test_dock_wait_duration_matches_simulated_timestamps():
    samples = list(RoadStarSimulator().stream())
    arrival = next(sample for sample in samples if sample.geofence_event == "ENTERED")
    threshold = next(sample for sample in samples if sample.scenario_event == "DETENTION_THRESHOLD")
    collision = next(sample for sample in samples if sample.scenario_event == "HOS_COLLISION")
    assert threshold.dock_wait_minutes == 120
    assert collision.dock_wait_minutes == 140
    assert arrival.observed_at == "2026-09-12T09:40:00Z"
    assert threshold.observed_at == "2026-09-12T11:40:00Z"
    assert collision.observed_at == "2026-09-12T12:00:00Z"


def test_distance_and_geofence_helpers():
    assert distance_km((43.0, -81.0), (43.0, -81.0)) == 0
    assert inside_geofence(42.9854, -81.2460, LONDON_FACILITY)
    assert not inside_geofence(43.5183, -79.8774, LONDON_FACILITY)


def test_reset_replays_sequence():
    simulator = RoadStarSimulator()
    first = simulator.tick()
    list(simulator.stream())
    simulator.reset()
    assert simulator.tick() == first


def test_only_supported_seed_is_accepted():
    with pytest.raises(ValueError, match="seed 17"):
        RoadStarSimulator(seed=1)
