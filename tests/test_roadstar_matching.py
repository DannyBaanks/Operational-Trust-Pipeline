"""Minimal load-matching tests, including the official workbook."""
from __future__ import annotations

from pathlib import Path

from otp.roadstar_matching import Load, iter_available_loads, rank_loads

WORKBOOK = Path(__file__).resolve().parents[1] / "fixtures" / "roadstar" / "Hackathon_Data.xlsx"


def truck(**overrides):
    params = {
        "truck_city": "LONDON",
        "trailer_temp_controlled": False,
        "capacity_lbs": 45000.0,
        "hos_remaining_hours": 8.0,
    }
    params.update(overrides)
    return params


def test_rejects_equipment_weight_hos_and_unknown():
    loads = [
        Load("L1", "MILTON", "KITCHENER", 30000.0, True),   # reefer vs dry
        Load("L2", "MILTON", "KITCHENER", 60000.0, False),  # overweight
        Load("L3", "NOWHERE", "KITCHENER", 10000.0, False),  # unknown city
    ]
    results = rank_loads(loads, **truck())
    codes = {r.load.load_id: r.reason_code for r in results}
    assert codes == {"L1": "EQUIPMENT_MISMATCH", "L2": "OVERWEIGHT", "L3": "CITY_UNKNOWN"}
    assert all(r.accepted is False for r in results)


def test_hos_insufficient_and_unknown():
    loads = [Load("L1", "MILTON", "KITCHENER", 30000.0, False)]
    [result] = rank_loads(loads, **truck(hos_remaining_hours=0.5))
    assert result.reason_code == "HOS_INSUFFICIENT"
    [result] = rank_loads(loads, **truck(hos_remaining_hours=None))
    assert result.reason_code == "HOS_UNKNOWN"


def test_deterministic_ordering():
    loads = [
        Load("B", "MILTON", "KITCHENER", 30000.0, False),
        Load("A", "MILTON", "KITCHENER", 30000.0, False),
    ]
    first = [r.load.load_id for r in rank_loads(loads, **truck())]
    second = [r.load.load_id for r in rank_loads(loads, **truck())]
    assert first == second == ["A", "B"]


def test_workbook_london_truck_finds_kitchener_return():
    loads = iter_available_loads(WORKBOOK)
    assert len(loads) > 4000
    results = rank_loads(loads, **truck(), top_n=5000)
    accepted = [r for r in results if r.accepted]
    assert accepted, "no acceptable return load for a London truck"
    kitchener = [r for r in accepted if r.load.destination.upper() == "KITCHENER"]
    assert kitchener, "no KITCHENER-bound load accepted"
    top = kitchener[0]
    assert top.reasons and top.deadhead_km > 0
    # Dispatcher decides: result carries reasons, never auto-assigns.
    assert top.reason_code == "MATCH"
    # Local LONDON->LONDON moves win on deadhead; Kitchener follows behind.
    first = accepted[0]
    assert first.deadhead_km <= top.deadhead_km
