"""
hotel_agent_node calls fast-hotels (real network call). These tests
monkeypatch search_hotels -- the same "inject a fake instead of the real
dependency" pattern used for the LLM and flight agent -- so the agent's
control flow (date computation, cost math, zero-result handling) is
verified without any network call.
"""

import agents.hotel_agent as hotel_agent_module
from agents.hotel_agent import hotel_agent_node
from tests.fake_llm import FakeLLM, RecordingFakeLLM

FAKE_RESULTS = [
    {"HotelName": "Cheap Inn", "cityName": "Paris", "EstimatedPriceUSD": 80.0,
     "GuestRating": 4.2, "Amenities": ["Free Wi-Fi"], "URL": "http://example.com/1"},
    {"HotelName": "Pricier Hotel", "cityName": "Paris", "EstimatedPriceUSD": 150.0,
     "GuestRating": 4.8, "Amenities": ["Pool"], "URL": "http://example.com/2"},
]


def test_zero_result_short_circuits_without_calling_llm(monkeypatch):
    monkeypatch.setattr(hotel_agent_module, "search_hotels", lambda *a, **k: [])
    llm = RecordingFakeLLM()

    state = {"destination_city": "Nonexistentville", "duration_days": 5, "travel_month": "April"}
    result = hotel_agent_node(state, llm=llm)

    assert result["hotel_results"] == []
    assert result["lodging_cost_estimate"] == 0.0
    assert llm.prompts == []


def test_lodging_cost_uses_cheapest_result_times_duration(monkeypatch):
    monkeypatch.setattr(hotel_agent_module, "search_hotels", lambda *a, **k: FAKE_RESULTS)
    llm = FakeLLM("Great pick!")

    state = {"destination_city": "Paris", "duration_days": 4, "travel_month": "April"}
    result = hotel_agent_node(state, llm=llm)

    assert result["lodging_cost_estimate"] == round(80.0 * 4, 2)


def test_recommendation_prompt_only_describes_the_cheapest_hotel(monkeypatch):
    monkeypatch.setattr(hotel_agent_module, "search_hotels", lambda *a, **k: FAKE_RESULTS)
    llm = RecordingFakeLLM("Great pick!")

    state = {"destination_city": "Paris", "duration_days": 4, "travel_month": "April"}
    hotel_agent_node(state, llm=llm)

    assert len(llm.prompts) == 1
    assert "Cheap Inn" in llm.prompts[0]
    assert "Pricier Hotel" not in llm.prompts[0]


def test_checkin_checkout_dates_passed_through(monkeypatch):
    captured = {}

    def fake_search_hotels(city, checkin_date, checkout_date, max_price=None, limit=10):
        captured["checkin"] = checkin_date
        captured["checkout"] = checkout_date
        return FAKE_RESULTS

    monkeypatch.setattr(hotel_agent_module, "search_hotels", fake_search_hotels)

    state = {"destination_city": "Paris", "duration_days": 4, "travel_month": "April"}
    hotel_agent_node(state, llm=FakeLLM())

    assert captured["checkin"].endswith("-04-15")
    # checkout should be checkin + duration_days
    from datetime import date
    checkin = date.fromisoformat(captured["checkin"])
    checkout = date.fromisoformat(captured["checkout"])
    assert (checkout - checkin).days == 4
