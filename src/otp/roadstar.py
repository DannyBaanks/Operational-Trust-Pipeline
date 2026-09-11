"""RoadStar workbook adapter; source column names terminate at this boundary."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

from .domain import OperationalEvent, make_event


class RoadStarAdapter:
    identity = "roadstar-workbook-v0"
    required = {"assignment_id", "trip_id", "driver_ref", "assigned_at", "ack_due_at", "acknowledged_at", "contact_ref"}

    def normalize(self, raw: dict) -> OperationalEvent:
        if raw.get("record_type") == "dispatch":
            return self.normalize_dispatch(raw)
        if raw.get("record_type") == "driver":
            return self.normalize_driver(raw)
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

    def normalize_dispatch(self, raw: dict[str, Any]) -> OperationalEvent:
        self._require(raw, {"TRIP_NUMBER", "LS_LEG_ID", "LS_EXPECTED_DATE", "DELIVER_BY", "LS_LAST_FB_STATUS_DATE", "STATUS"})
        observed = raw["LS_LAST_FB_STATUS_DATE"] or raw["LS_EXPECTED_DATE"] or raw["DELIVER_BY"]
        payload = {
            "trip_ref": str(raw["TRIP_NUMBER"]), "leg_ref": str(raw["LS_LEG_ID"]),
            "expected_at": self._iso(raw["LS_EXPECTED_DATE"]), "due_at": self._iso(raw["DELIVER_BY"]),
            "latest_state_at": self._iso(raw["LS_LAST_FB_STATUS_DATE"]), "operation_status": str(raw["STATUS"]),
        }
        return make_event(schema_version="operational-event/1", source="roadstar", source_event_type="dispatch.leg_observed",
                          source_ref=f"{payload['trip_ref']}:{payload['leg_ref']}", entity_type="dispatch_leg", entity_id=payload["leg_ref"],
                          observed_at=self._iso(observed), payload=payload)

    def normalize_driver(self, raw: dict[str, Any]) -> OperationalEvent:
        self._require(raw, {"DRIVER_ID", "REMAINING_HOURS", "STATUS", "HOURS_UPDATED"})
        payload = {"remaining_hours": raw["REMAINING_HOURS"], "operation_status": str(raw["STATUS"]),
                   "trip_ref": str(raw.get("CURRENT_TRIP") or ""), "contact_ref": str(raw.get("EMAIL") or "")}
        return make_event(schema_version="operational-event/1", source="roadstar", source_event_type="driver.hos_observed",
                          source_ref=str(raw["DRIVER_ID"]), entity_type="driver", entity_id=str(raw["DRIVER_ID"]),
                          observed_at=self._iso(raw["HOURS_UPDATED"]), payload=payload)

    def dispatch_rows(self, workbook: Path) -> Iterator[dict[str, Any]]:
        yield from self._rows(workbook, "Dispatch", "dispatch")

    def driver_rows(self, workbook: Path) -> Iterator[dict[str, Any]]:
        yield from self._rows(workbook, "Driver", "driver")

    @staticmethod
    def _rows(workbook: Path, sheet: str, record_type: str) -> Iterator[dict[str, Any]]:
        import openpyxl
        ws = openpyxl.load_workbook(workbook, read_only=True, data_only=True)[sheet]
        headers = next(ws.values)
        for values in ws.values:
            raw = dict(zip(headers, values, strict=True))
            if raw.get(headers[0]) != headers[0]:
                raw["record_type"] = record_type
                yield raw

    @staticmethod
    def _iso(value: Any) -> str:
        if isinstance(value, datetime): return value.isoformat() + "Z"
        if isinstance(value, date): return datetime.combine(value, datetime.min.time()).isoformat() + "Z"
        if value is None: return ""
        return str(value)

    @staticmethod
    def _require(raw: dict[str, Any], fields: set[str]) -> None:
        missing = fields.difference(raw)
        if missing: raise ValueError(f"RoadStar record missing fields: {sorted(missing)}")
