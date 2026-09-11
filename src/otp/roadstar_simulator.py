"""Deterministic RoadStar telemetry simulator for the hackathon demo.

The simulator is deliberately independent from the GUI and policy engine. It
produces immutable telemetry samples which another adapter can turn into OTP
events.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Iterator


@dataclass(frozen=True)
class FacilityGeofence:
    facility_id: str
    name: str
    latitude: float
    longitude: float
    radius_km: float


@dataclass(frozen=True)
class Telemetry:
    sequence: int
    observed_at: str
    truck_id: str
    trip_ref: str
    latitude: float
    longitude: float
    speed_kph: float
    distance_km: float
    odometer_km: float
    duty_status: str
    driving_hours_remaining: float
    on_duty_hours_remaining: float
    elapsed_window_hours_remaining: float
    cycle_hours_remaining: float
    facility_id: str | None
    geofence_event: str | None
    dock_wait_minutes: int
    elapsed_minutes: int
    scenario_event: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "observed_at": self.observed_at,
            "truck_id": self.truck_id,
            "trip_ref": self.trip_ref,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed_kph": self.speed_kph,
            "distance_km": self.distance_km,
            "odometer_km": self.odometer_km,
            "duty_status": self.duty_status,
            "driving_hours_remaining": self.driving_hours_remaining,
            "on_duty_hours_remaining": self.on_duty_hours_remaining,
            "elapsed_window_hours_remaining": self.elapsed_window_hours_remaining,
            "cycle_hours_remaining": self.cycle_hours_remaining,
            "facility_id": self.facility_id,
            "geofence_event": self.geofence_event,
            "dock_wait_minutes": self.dock_wait_minutes,
            "elapsed_minutes": self.elapsed_minutes,
            "scenario_event": self.scenario_event,
        }


MILTON = (43.5183, -79.8774)
LONDON = (42.9849, -81.2453)
LONDON_FACILITY = FacilityGeofence(
    "london-dc-01", "London Distribution Centre", 42.9854, -81.2460, 0.8
)


def distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    """Return approximate great-circle distance between two coordinates."""
    earth_radius_km = 6371.0
    lat1, lon1 = radians(first[0]), radians(first[1])
    lat2, lon2 = radians(second[0]), radians(second[1])
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * earth_radius_km * asin(sqrt(a))


def inside_geofence(latitude: float, longitude: float, geofence: FacilityGeofence) -> bool:
    return distance_km((latitude, longitude), (geofence.latitude, geofence.longitude)) <= geofence.radius_km


class RoadStarSimulator:
    """Finite deterministic simulator for the Dock/HOS Collision scenario."""

    def __init__(
        self,
        *,
        start_at: str = "2026-09-12T08:00:00Z",
        truck_id: str = "TRUCK-017",
        trip_ref: str = "TRIP-MILTON-LONDON-001",
        seed: int = 17,
        geofence: FacilityGeofence = LONDON_FACILITY,
    ) -> None:
        if seed != 17:
            raise ValueError("only deterministic seed 17 is supported")
        self.start_at = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
        self.truck_id = truck_id
        self.trip_ref = trip_ref
        self.seed = seed
        self.geofence = geofence
        self._index = 0
        self._odometer_km = 120_000.0
        self._distance_km = 0.0
        self._previous_position: tuple[float, float] | None = None

    @property
    def done(self) -> bool:
        return self._index >= len(self._route())

    def reset(self) -> None:
        self._index = 0
        self._odometer_km = 120_000.0
        self._distance_km = 0.0
        self._previous_position = None

    def tick(self) -> Telemetry:
        if self.done:
            raise StopIteration("RoadStar scenario is complete")

        sample = self._route()[self._index]
        position = (sample["latitude"], sample["longitude"])
        increment = 0.0 if self._previous_position is None else distance_km(self._previous_position, position)
        self._distance_km += increment
        self._odometer_km += increment

        previous_inside = (
            self._previous_position is not None
            and inside_geofence(*self._previous_position, self.geofence)
        )
        current_inside = inside_geofence(*position, self.geofence)
        geofence_event = None
        if current_inside and not previous_inside:
            geofence_event = "ENTERED"
        elif previous_inside and not current_inside:
            geofence_event = "DEPARTED"

        observed_at = self.start_at + timedelta(minutes=int(sample["elapsed_minutes"]))
        telemetry = Telemetry(
            sequence=self._index,
            observed_at=observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            truck_id=self.truck_id,
            trip_ref=self.trip_ref,
            latitude=position[0],
            longitude=position[1],
            speed_kph=sample["speed_kph"],
            distance_km=round(self._distance_km, 3),
            odometer_km=round(self._odometer_km, 3),
            duty_status=sample["duty_status"],
            driving_hours_remaining=sample["driving_hours_remaining"],
            on_duty_hours_remaining=sample["on_duty_hours_remaining"],
            elapsed_window_hours_remaining=sample["elapsed_window_hours_remaining"],
            cycle_hours_remaining=sample["cycle_hours_remaining"],
            facility_id=self.geofence.facility_id if current_inside else None,
            geofence_event=geofence_event,
            dock_wait_minutes=sample["dock_wait_minutes"],
            elapsed_minutes=int(sample["elapsed_minutes"]),
            scenario_event=sample["scenario_event"],
        )
        self._previous_position = position
        self._index += 1
        return telemetry

    def stream(self) -> Iterator[Telemetry]:
        while not self.done:
            yield self.tick()

    def _route(self) -> list[dict[str, object]]:
        """Return a fixed route with a slowdown and a 140-minute dock wait."""
        near_london = (43.0200, -81.1900)
        outside_facility = (42.9950, -81.2700)
        inside_facility = (42.9854, -81.2460)
        return [
            self._sample(*MILTON, 82.0, "DRIVING", 7.5, 8.0, 9.5, 52.0, 0, 0, None),
            self._sample(43.4000, -79.7000, 78.0, "DRIVING", 7.1, 7.7, 9.2, 51.7, 0, 20, None),
            self._sample(43.2200, -80.9000, 22.0, "DRIVING", 6.8, 7.4, 8.9, 51.4, 0, 40, "401_SLOWDOWN"),
            self._sample(43.0800, -81.1000, 18.0, "DRIVING", 6.5, 7.1, 8.6, 51.1, 0, 60, "401_SLOWDOWN"),
            self._sample(*near_london, 62.0, "DRIVING", 6.2, 6.8, 8.3, 50.8, 0, 80, None),
            self._sample(*outside_facility, 12.0, "DRIVING", 6.0, 6.6, 8.1, 50.6, 0, 90, None),
            self._sample(*inside_facility, 0.0, "ON_DUTY", 6.0, 2.4, 8.0, 50.6, 0, 100, "DOCK_ARRIVAL"),
            self._sample(*inside_facility, 0.0, "ON_DUTY", 6.0, 1.4, 7.0, 49.6, 60, 160, "DOCK_WAIT"),
            self._sample(*inside_facility, 0.0, "ON_DUTY", 6.0, 0.4, 6.0, 48.6, 120, 220, "DETENTION_THRESHOLD"),
            self._sample(*inside_facility, 0.0, "ON_DUTY", 6.0, 0.0, 5.67, 48.27, 140, 240, "HOS_COLLISION"),
            self._sample(*outside_facility, 15.0, "DRIVING", 5.8, 0.0, 5.5, 48.1, 140, 250, "DOCK_DEPARTURE"),
        ]

    @staticmethod
    def _sample(
        latitude: float,
        longitude: float,
        speed_kph: float,
        duty_status: str,
        driving_hours_remaining: float,
        on_duty_hours_remaining: float,
        elapsed_window_hours_remaining: float,
        cycle_hours_remaining: float,
        dock_wait_minutes: int,
        elapsed_minutes: int,
        scenario_event: str | None,
    ) -> dict[str, object]:
        return {
            "latitude": latitude,
            "longitude": longitude,
            "speed_kph": speed_kph,
            "duty_status": duty_status,
            "driving_hours_remaining": driving_hours_remaining,
            "on_duty_hours_remaining": on_duty_hours_remaining,
            "elapsed_window_hours_remaining": elapsed_window_hours_remaining,
            "cycle_hours_remaining": cycle_hours_remaining,
            "dock_wait_minutes": dock_wait_minutes,
            "elapsed_minutes": elapsed_minutes,
            "scenario_event": scenario_event,
        }
