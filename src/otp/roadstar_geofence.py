"""RoadStar geofence and detention tracking.

Pure tracker and detention calculator plus a tiny SQLite visit store.
Timestamps are persisted before any external action request.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

FREE_DETENTION_MINUTES = 120
DEFAULT_DETENTION_RATE_PER_HOUR = 75.0  # demo rate in CAD; not an official tariff


@dataclass(frozen=True)
class FacilityVisit:
    facility_id: str
    truck_id: str
    trip_ref: str
    arrival_at: str
    departure_at: str | None
    wait_minutes: int
    billable_minutes: int
    rate_per_hour: float
    estimated_charge: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def calculate_detention(
    arrival_at: str,
    departure_at: str,
    rate_per_hour: float = DEFAULT_DETENTION_RATE_PER_HOUR,
) -> tuple[int, int, float]:
    """Return (wait_minutes, billable_minutes, estimated_charge)."""
    wait = int((_parse(departure_at) - _parse(arrival_at)).total_seconds() // 60)
    wait = max(0, wait)
    billable = max(0, wait - FREE_DETENTION_MINUTES)
    charge = round(billable / 60 * rate_per_hour, 2)
    return wait, billable, charge


class GeofenceTracker:
    """Consume Telemetry samples and emit completed facility visits.

    Idempotent: repeated ENTERED while inside is ignored; repeated DEPARTED
    while outside is ignored. Re-entry starts a new visit.
    """

    def __init__(self, rate_per_hour: float = DEFAULT_DETENTION_RATE_PER_HOUR) -> None:
        self.rate_per_hour = rate_per_hour
        self._open: dict[str, Any] | None = None
        self.visits: list[FacilityVisit] = []

    @property
    def open_visit(self) -> dict[str, Any] | None:
        return dict(self._open) if self._open else None

    def feed(self, telemetry: Any) -> list[FacilityVisit]:
        """Feed one Telemetry sample. Returns newly completed visits."""
        event = getattr(telemetry, "geofence_event", None)
        facility = getattr(telemetry, "facility_id", None)
        observed = getattr(telemetry, "observed_at", "")
        truck = getattr(telemetry, "truck_id", "")
        trip = getattr(telemetry, "trip_ref", "")
        completed: list[FacilityVisit] = []

        if event == "ENTERED" and facility:
            if self._open is None:
                self._open = {
                    "facility_id": facility,
                    "truck_id": truck,
                    "trip_ref": trip,
                    "arrival_at": observed,
                }
            # else: GPS jitter / duplicate ENTERED while inside -> ignore
        elif event == "DEPARTED":
            if self._open is not None:
                arrival = self._open["arrival_at"]
                wait, billable, charge = calculate_detention(arrival, observed, self.rate_per_hour)
                completed.append(
                    FacilityVisit(
                        facility_id=self._open["facility_id"],
                        truck_id=self._open["truck_id"],
                        trip_ref=self._open["trip_ref"],
                        arrival_at=arrival,
                        departure_at=observed,
                        wait_minutes=wait,
                        billable_minutes=billable,
                        rate_per_hour=self.rate_per_hour,
                        estimated_charge=charge,
                    )
                )
                self._open = None
            # else: DEPARTED while outside -> ignore
        self.visits.extend(completed)
        return completed


def init_geofence_store(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS geofence_visits (
                facility_id TEXT NOT NULL,
                arrival_at TEXT NOT NULL,
                truck_id TEXT NOT NULL,
                trip_ref TEXT NOT NULL,
                departure_at TEXT,
                wait_minutes INTEGER NOT NULL DEFAULT 0,
                billable_minutes INTEGER NOT NULL DEFAULT 0,
                rate_per_hour REAL NOT NULL DEFAULT 75.0,
                estimated_charge REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (facility_id, arrival_at)
            )"""
        )
        conn.commit()


def record_visit(path: Path, visit: FacilityVisit) -> None:
    """Upsert a visit. Arrival is stored first; departure completes it."""
    init_geofence_store(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """INSERT INTO geofence_visits
               (facility_id, arrival_at, truck_id, trip_ref, departure_at,
                wait_minutes, billable_minutes, rate_per_hour, estimated_charge)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(facility_id, arrival_at) DO UPDATE SET
                 departure_at=excluded.departure_at,
                 wait_minutes=excluded.wait_minutes,
                 billable_minutes=excluded.billable_minutes,
                 rate_per_hour=excluded.rate_per_hour,
                 estimated_charge=excluded.estimated_charge""",
            (
                visit.facility_id, visit.arrival_at, visit.truck_id, visit.trip_ref,
                visit.departure_at, visit.wait_minutes, visit.billable_minutes,
                visit.rate_per_hour, visit.estimated_charge,
            ),
        )
        conn.commit()


def record_arrival(
    path: Path,
    *,
    facility_id: str,
    truck_id: str,
    trip_ref: str,
    arrival_at: str,
    rate_per_hour: float = DEFAULT_DETENTION_RATE_PER_HOUR,
) -> None:
    """Persist an arrival timestamp before any external action."""
    record_visit(
        path,
        FacilityVisit(
            facility_id=facility_id, truck_id=truck_id, trip_ref=trip_ref,
            arrival_at=arrival_at, departure_at=None, wait_minutes=0,
            billable_minutes=0, rate_per_hour=rate_per_hour, estimated_charge=0.0,
        ),
    )


def list_visits(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM geofence_visits ORDER BY arrival_at"
        ).fetchall()
    return [dict(row) for row in rows]


def detention_ack_raw(
    visit: FacilityVisit,
    contact_ref: str = "dispatch@roadstar.local",
    ack_minutes: int = 30,
) -> dict[str, Any]:
    """Build a RoadStar ack-assignment raw record for a detention visit.

    The dispatcher must acknowledge the detention observation. Reuses the
    tested ack-lease pipeline without changing the core.
    """
    arrival = _parse(visit.arrival_at)
    due = _iso(arrival + timedelta(minutes=ack_minutes))
    assignment = f"DET-{visit.facility_id}-{visit.arrival_at}"
    return {
        "assignment_id": assignment,
        "trip_id": visit.trip_ref,
        "driver_ref": visit.truck_id,
        "assigned_at": visit.arrival_at,
        "ack_due_at": due,
        "acknowledged_at": None,
        "contact_ref": contact_ref,
    }
