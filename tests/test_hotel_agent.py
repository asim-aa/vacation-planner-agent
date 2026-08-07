"""
hotel_agent_node calls fast-hotels (real network call). These tests
monkeypatch search_hotels -- the same "inject a fake instead of the real
dependency" pattern used for the LLM and flight agent -- so the agent's
control flow (date computation, cost math, zero-result handling) is
verified without any network call.
"""

import agents.hotel_agent as hotel_agent_module
from agents.hotel_agent import build_hotel_output, hotel_agent_node
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


def test_build_hotel_output_discards_hallucinated_city_for_template(monkeypatch):
    monkeypatch.setattr(hotel_agent_module, "search_hotels", lambda *a, **k: FAKE_RESULTS)
    llm = FakeLLM("A cozy stay near the beaches of Miami.")

    result = build_hotel_output(FAKE_RESULTS, duration_days=4, llm=llm)

    assert "Miami" not in result["hotel_recommendation"]
    assert "Cheap Inn" in result["hotel_recommendation"]
    assert "Paris" in result["hotel_recommendation"]


def test_build_hotel_output_keeps_recommendation_without_hallucination(monkeypatch):
    monkeypatch.setattr(hotel_agent_module, "search_hotels", lambda *a, **k: FAKE_RESULTS)
    llm = FakeLLM("Cheap Inn in Paris offers free Wi-Fi at a great price.")

    result = build_hotel_output(FAKE_RESULTS, duration_days=4, llm=llm)

    assert result["hotel_recommendation"] == "Cheap Inn in Paris offers free Wi-Fi at a great price."


def test_optimize_for_quality_picks_better_rated_hotel_and_reorders_results(monkeypatch):
    monkeypatch.setattr(hotel_agent_module, "search_hotels", lambda *a, **k: FAKE_RESULTS)
    llm = RecordingFakeLLM("Great pick!")

    state = {"destination_city": "Paris", "duration_days": 4, "travel_month": "April"}
    result = hotel_agent_node(state, llm=llm, optimize_for="quality")

    # Pricier Hotel (4.8) outranks Cheap Inn (4.2) in quality mode, even
    # though it's not the cheapest -- it's still within the same
    # already-budget-filtered results, not a new/higher-ceiling search.
    assert result["hotel_results"][0]["HotelName"] == "Pricier Hotel"
    assert result["hotel_results"][1]["HotelName"] == "Cheap Inn"
    assert result["lodging_cost_estimate"] == round(150.0 * 4, 2)
    assert "Pricier Hotel" in llm.prompts[0]
    assert "best-rated" in llm.prompts[0]


def test_build_hotel_output_reselects_without_searching_again(monkeypatch):
    # Regression test: a budget-reallocation follow-up (see app.py's
    # refine_hotel_for_quality) must re-pick from ALREADY-fetched results
    # without calling search_hotels again -- a fresh Google Hotels scrape
    # is live and non-deterministic, so re-searching could silently swap
    # in a totally different set of hotels instead of "spending more on
    # what we already found".
    def fail_if_called(*a, **k):
        raise AssertionError("build_hotel_output must not search again")

    monkeypatch.setattr(hotel_agent_module, "search_hotels", fail_if_called)

    result = build_hotel_output(FAKE_RESULTS, duration_days=4, optimize_for="quality", llm=FakeLLM())

    assert result["hotel_results"][0]["HotelName"] == "Pricier Hotel"
    assert result["lodging_cost_estimate"] == round(150.0 * 4, 2)


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
