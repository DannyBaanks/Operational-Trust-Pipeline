"""Fixture schema adapter. Field names are limited to the checked-in fixture."""
from __future__ import annotations

from .domain import OperationalEvent, make_event


class RoadStarAdapter:
    identity = "roadstar-fixture-v0"
    required = {"assignment_id", "trip_id", "driver_ref", "assigned_at", "ack_due_at", "acknowledged_at", "contact_ref"}

    def normalize(self, raw: dict) -> OperationalEvent:
        missing = self.required.difference(raw)
        if missing:
            raise ValueError(f"RoadStar fixture missing fields: {sorted(missing)}")
        payload = {
            "assignment_ref": raw["assignment_id"], "trip_ref": raw["trip_id"],
            "assignee_ref": raw["driver_ref"], "ack_due_at": raw["ack_due_at"],
            "acknowledged_at": raw["acknowledged_at"], "contact_ref": raw["contact_ref"],
        }
        return make_event(schema_version="operational-event/1", source="roadstar", source_event_type="assignment.created",
                          source_ref=str(raw["assignment_id"]), entity_type="assignment", entity_id=str(raw["assignment_id"]),
                          observed_at=str(raw["assigned_at"]), payload=payload)
