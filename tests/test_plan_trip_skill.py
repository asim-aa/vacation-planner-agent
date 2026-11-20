import importlib.util
from pathlib import Path

from agents.compile_itinerary import compile_itinerary_node

_p = Path(__file__).resolve().parents[1] / ".claude/skills/plan-trip/scripts/verify_itinerary.py"
_spec = importlib.util.spec_from_file_location("verify_itinerary", _p)
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)


def _state(**over):
    s = {
        "destination_city": "Paris", "destination_country": "France",
        "travel_month": "April", "duration_days": 4, "budget_total": 2000.0,
        "flight_cost_estimate": 800.0, "lodging_cost_estimate": 600.0,
        "activities_cost_estimate": 100.0,
        "flight_results": [{"x": 1}], "hotel_results": [{"HotelName": "H"}],
        "spot_results": [{"Destination Name": "Louvre"}, {"Destination Name": "Eiffel"}],
    }
    s.update(over)
    s.update(compile_itinerary_node(s))
    return s


def test_valid_itinerary_passes():
    assert v.verify(_state())[0] == []


def test_tampered_total_fails():
    s = _state()
    s["total_cost_estimate"] = 1.0
    assert any("total" in e for e in v.verify(s)[0])


def test_wrong_budget_status_fails():
    s = _state()
    s["budget_total"] = 100.0  # md still claims within budget
    assert any("within budget" in e for e in v.verify(s)[0])


def test_missing_day_fails():
    s = _state()
    s["itinerary_markdown"] = s["itinerary_markdown"].replace("**Day 2:**", "**Dy 2:**")
    assert any("days" in e for e in v.verify(s)[0])


def test_empty_results_warn_not_fail():
    errs, warns = v.verify(_state(flight_results=[]))
    assert errs == [] and warns


def test_all_sources_empty_fails():
    s = _state(flight_results=[], hotel_results=[], spot_results=[])
    assert any("every data source" in e for e in v.verify(s)[0])
