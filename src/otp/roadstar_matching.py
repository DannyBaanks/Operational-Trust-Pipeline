"""Minimal deterministic load matching for RoadStar.

Ranks unassigned Tlorder loads against a truck position. Explainable score,
hard rejects with reason codes, UNKNOWN when critical inputs are missing.
Historical workbook loads are used as return-load opportunities for the demo;
they are not live offers.

The sheet DISTANCE column contains negative values, so distances are computed
with haversine from city coordinates instead of trusting that column.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .roadstar_simulator import distance_km

CITY_COORDS: dict[str, tuple[float, float]] = {
    "MILTON": (43.5183, -79.8774),
    "LONDON": (42.9849, -81.2453),
    "KITCHENER": (43.4516, -80.4925),
    "WATERLOO": (43.4643, -80.5204),
    "CAMBRIDGE": (43.3616, -80.3144),
    "GUELPH": (43.5448, -80.2482),
    "BARRIE": (44.3894, -79.6903),
    "PETERBOROUGH": (44.3091, -78.3197),
    "PICKERING": (43.8354, -79.0891),
    "WHITBY": (43.8975, -78.9429),
    "OSHAWA": (43.8971, -78.8658),
    "TORONTO": (43.6532, -79.3832),
    "NORTH YORK": (43.7615, -79.4111),
    "MISSISSAUGA": (43.5890, -79.6441),
    "BRAMPTON": (43.7315, -79.7624),
    "WOODBRIDGE": (43.6890, -79.5845),
    "VAUGHAN": (43.8563, -79.5085),
    "HALTON HILLS": (43.6315, -79.9552),
    "HAMILTON": (43.2557, -79.8711),
    "COBOURG": (43.9592, -78.1656),
    "NIAGARA FALLS": (43.0896, -79.0849),
    "SUDBURY": (46.4917, -80.9930),
    "PORT HURON": (42.9709, -82.4249),
    "NEWARK": (40.7357, -74.1724),
    "ELIZABETH": (40.6640, -74.2107),
    "LOCKPORT": (43.1706, -78.6903),
    "SCOTTSVILLE": (43.0178, -77.7511),
}

AVG_SPEED_KPH = 80.0
DISPATCH_BUFFER_HOURS = 1.0


@dataclass(frozen=True)
class Load:
    load_id: str
    origin: str
    destination: str
    weight_lbs: float | None
    temp_controlled: bool
    sheet_distance: float | None = None


@dataclass
class MatchResult:
    load: Load
    accepted: bool
    reason_code: str
    reasons: list[str] = field(default_factory=list)
    deadhead_km: float = 0.0
    trip_km: float = 0.0
    score: float = float("inf")


def load_from_tlorder(row: dict[str, Any]) -> Load | None:
    """Build a Load from a Tlorder row. Returns None when unavailable."""
    if row.get("CURRENTLY_ASSIGNED") is True:
        return None
    origin = str(row.get("ORIGCITY") or "").strip()
    destination = str(row.get("DESTCITY") or "").strip()
    if not origin or not destination or origin == "ORIGCITY":
        return None
    weight = row.get("WEIGHT_LBS")
    try:
        weight = float(weight) if weight is not None else None
    except (TypeError, ValueError):
        weight = None
    distance = row.get("DISTANCE")
    try:
        distance = float(distance) if distance is not None and float(distance) > 0 else None
    except (TypeError, ValueError):
        distance = None
    return Load(
        load_id=str(row.get("BILL_NUMBER")),
        origin=origin,
        destination=destination,
        weight_lbs=weight,
        temp_controlled=bool(row.get("TEMP_CONTROLLED")),
        sheet_distance=distance,
    )


def iter_available_loads(workbook: Path) -> list[Load]:
    """Read unassigned Tlorder loads from the official workbook."""
    import openpyxl
    ws = openpyxl.load_workbook(workbook, read_only=True, data_only=True)["Tlorder"]
    headers = next(ws.values)
    loads: list[Load] = []
    for values in ws.values:
        row = dict(zip(headers, values, strict=True))
        load = load_from_tlorder(row)
        if load is not None:
            loads.append(load)
    return loads


def rank_loads(
    loads: list[Load],
    *,
    truck_city: str,
    trailer_temp_controlled: bool = False,
    capacity_lbs: float | None = None,
    hos_remaining_hours: float | None = None,
    top_n: int = 3,
) -> list[MatchResult]:
    """Rank loads for a truck. Deterministic: sorts by (score, load_id)."""
    truck_city = (truck_city or "").upper()
    truck_pos = CITY_COORDS.get(truck_city)
    results: list[MatchResult] = []
    for load in loads:
        origin_pos = CITY_COORDS.get(load.origin.upper())
        dest_pos = CITY_COORDS.get(load.destination.upper())
        if truck_pos is None:
            results.append(MatchResult(load, False, "TRUCK_CITY_UNKNOWN",
                                       [f"truck city {truck_city!r} has no coordinates"]))
            continue
        if origin_pos is None or dest_pos is None:
            unknown = load.origin if origin_pos is None else load.destination
            results.append(MatchResult(load, False, "CITY_UNKNOWN",
                                       [f"city {unknown!r} has no coordinates"]))
            continue
        if load.temp_controlled and not trailer_temp_controlled:
            results.append(MatchResult(load, False, "EQUIPMENT_MISMATCH",
                                       ["reefer load requires temp-controlled trailer"]))
            continue
        if capacity_lbs is not None and load.weight_lbs is not None and load.weight_lbs > capacity_lbs:
            results.append(MatchResult(load, False, "OVERWEIGHT",
                                       [f"{load.weight_lbs:.0f} lbs exceeds capacity {capacity_lbs:.0f} lbs"]))
            continue
        deadhead = distance_km(truck_pos, origin_pos)
        trip = load.sheet_distance if load.sheet_distance else distance_km(origin_pos, dest_pos)
        estimated_hours = (deadhead + trip) / AVG_SPEED_KPH + DISPATCH_BUFFER_HOURS
        if hos_remaining_hours is None:
            results.append(MatchResult(load, False, "HOS_UNKNOWN",
                                       ["HOS remaining is missing"], deadhead, trip))
            continue
        if hos_remaining_hours < estimated_hours:
            results.append(MatchResult(
                load, False, "HOS_INSUFFICIENT",
                [f"needs {estimated_hours:.1f} h, has {hos_remaining_hours:.1f} h"],
                deadhead, trip))
            continue
        score = deadhead
        reasons = [f"deadhead {deadhead:.1f} km"]
        hos_margin = hos_remaining_hours - estimated_hours
        if hos_margin <= 1.0:
            score += 50.0
            reasons.append(f"HOS margin tight ({hos_margin:.1f} h)")
        results.append(MatchResult(load, True, "MATCH", reasons, deadhead, trip, score))

    accepted = sorted(
        (r for r in results if r.accepted), key=lambda r: (r.score, r.load.load_id))
    rejected = sorted(
        (r for r in results if not r.accepted), key=lambda r: (r.load.load_id,))
    return accepted[:top_n] + rejected
