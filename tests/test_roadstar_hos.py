"""Canadian HOS policy tests."""
from __future__ import annotations

from otp.domain import FindingStatus, make_event
from otp.roadstar_hos import evaluate_hos, hos_payload_from_telemetry
from otp.roadstar_simulator import RoadStarSimulator


def event_with(payload):
    return make_event(
        schema_version="operational-event/1", source="roadstar-simulator",
        source_event_type="telemetry.hos_observed", source_ref="TRUCK-017",
        entity_type="truck", entity_id="TRUCK-017",
        observed_at="2026-09-12T09:40:00Z", payload=payload,
    )


def base_payload(**overrides):
    payload = {
        "driving_hours_remaining": 6.0,
        "on_duty_hours_remaining": 2.4,
        "elapsed_window_hours_remaining": 8.0,
        "cycle_hours_remaining": 50.6,
        "off_duty_hours": 10.0,
        "core_rest_hours": 8.0,
    }
    payload.update(overrides)
    return payload


def test_within_limits_pass():
    finding = evaluate_hos(event_with(base_payload()))
    assert finding.status is FindingStatus.PASS
    assert finding.reason_code == "HOS_WITHIN_LIMITS"
    assert finding.action_recommended is False


def test_each_limit_exhausted():
    for field in ("driving_hours_remaining", "on_duty_hours_remaining",
                  "elapsed_window_hours_remaining", "cycle_hours_remaining"):
        finding = evaluate_hos(event_with(base_payload(**{field: 0.0})))
        assert finding.status is FindingStatus.FAIL
        assert finding.reason_code == "HOS_LIMIT_EXHAUSTED"
        assert finding.severity == "HIGH"
        assert finding.action_recommended is True


def test_negative_remaining_is_exhausted():
    finding = evaluate_hos(event_with(base_payload(on_duty_hours_remaining=-0.5)))
    assert finding.reason_code == "HOS_LIMIT_EXHAUSTED"


def test_at_risk_uses_medium_severity():
    finding = evaluate_hos(event_with(base_payload(on_duty_hours_remaining=0.5)))
    assert finding.status is FindingStatus.FAIL
    assert finding.reason_code == "HOS_LIMIT_AT_RISK"
    assert finding.severity == "MEDIUM"
    assert finding.action_recommended is True


def test_at_risk_boundary():
    assert evaluate_hos(event_with(base_payload(on_duty_hours_remaining=1.0))).reason_code == "HOS_LIMIT_AT_RISK"
    assert evaluate_hos(event_with(base_payload(on_duty_hours_remaining=1.01))).reason_code == "HOS_WITHIN_LIMITS"


def test_missing_data_is_unknown_never_pass():
    for field in ("driving_hours_remaining", "on_duty_hours_remaining",
                  "elapsed_window_hours_remaining"):
        payload = base_payload()
        del payload[field]
        finding = evaluate_hos(event_with(payload))
        assert finding.status is FindingStatus.UNKNOWN
        assert finding.reason_code == "HOS_DATA_UNKNOWN"
        assert finding.action_recommended is False


def test_rest_incomplete():
    finding = evaluate_hos(event_with(base_payload(off_duty_hours=6.0)))
    assert finding.reason_code == "HOS_REST_INCOMPLETE"
    finding = evaluate_hos(event_with(base_payload(core_rest_hours=4.0)))
    assert finding.reason_code == "HOS_REST_INCOMPLETE"


def test_collision_predicted_before_exhaustion():
    payload = base_payload(on_duty_hours_remaining=0.4,
                           estimated_additional_on_duty_hours=0.5)
    finding = evaluate_hos(event_with(payload))
    assert finding.reason_code == "HOS_EXHAUSTION_DURING_DETENTION"
    assert finding.severity == "HIGH"
    assert "on-duty" in finding.reason


def test_no_collision_when_margin_sufficient():
    payload = base_payload(on_duty_hours_remaining=2.4,
                           estimated_additional_on_duty_hours=0.5)
    finding = evaluate_hos(event_with(payload))
    assert finding.reason_code == "HOS_WITHIN_LIMITS"


def test_simulator_collision_sample():
    samples = {s.scenario_event: s for s in RoadStarSimulator().stream()}
    collision = samples["HOS_COLLISION"]
    payload = hos_payload_from_telemetry(collision)
    finding = evaluate_hos(event_with(payload))
    assert finding.reason_code == "HOS_LIMIT_EXHAUSTED"

    threshold = samples["DETENTION_THRESHOLD"]
    payload = hos_payload_from_telemetry(
        threshold, estimated_additional_on_duty_hours=0.5)
    finding = evaluate_hos(event_with(payload))
    assert finding.reason_code == "HOS_EXHAUSTION_DURING_DETENTION"
