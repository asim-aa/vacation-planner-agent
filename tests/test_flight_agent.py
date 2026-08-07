"""
flight_agent_node calls fast-flights (real network, no quota, but still
worth keeping out of the deterministic default suite). These tests
monkeypatch resolve_city_to_iata/search_flights -- the same
"inject a fake instead of the real dependency" pattern used for the LLM
-- so the agent's control flow (resolution, date computation, cost math,
zero-result handling) is verified without any network call.
"""

import agents.flight_agent as flight_agent_module
from agents.date_utils import next_occurrence_of_month
from agents.flight_agent import flight_agent_node
from tests.fake_llm import FakeLLM, RecordingFakeLLM

FAKE_RESULTS = [
    {"Airline": "Delta", "Departure_Airport": "JFK", "Arrival_Airport": "ATL",
     "Seat_Class": "Economy", "Price_USD": 100.0, "Departure_Time": "t1",
     "Arrival_Time": "t2", "Stops": 0},
    {"Airline": "United", "Departure_Airport": "JFK", "Arrival_Airport": "ATL",
     "Seat_Class": "Economy", "Price_USD": 150.0, "Departure_Time": "t3",
     "Arrival_Time": "t4", "Stops": 1},
]


def test_next_occurrence_of_month_returns_future_date():
    result = next_occurrence_of_month("April")
    assert result.endswith("-04-15")


def test_known_destination_airport_skips_city_resolution(monkeypatch):
    called_city_resolve = []
    monkeypatch.setattr(
        flight_agent_module, "resolve_city_to_iata",
        lambda city, country=None: called_city_resolve.append(city) or "ATL",
    )
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)

    state = {
        "destination_city": "Atlanta",
        "origin_airport": "JFK",
        "destination_airport": "ATL",
        "travel_month": "September",
    }
    result = flight_agent_node(state, llm=FakeLLM())

    assert called_city_resolve == []  # never called -- known airport skipped it
    assert result["flight_results"] == FAKE_RESULTS


def test_unknown_destination_falls_back_to_city_resolution(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", lambda city, country=None: "CDG")
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)

    state = {
        "destination_city": "Paris",
        "destination_country": "France",
        "origin_airport": "JFK",
        "destination_airport": None,
        "travel_month": "September",
    }
    result = flight_agent_node(state, llm=FakeLLM())

    assert result["flight_results"] == FAKE_RESULTS


def test_unresolvable_destination_returns_empty_without_crashing(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", lambda city, country=None: None)
    llm = RecordingFakeLLM()

    state = {
        "destination_city": "Nowhereland",
        "origin_airport": "JFK",
        "destination_airport": None,
        "travel_month": "September",
    }
    result = flight_agent_node(state, llm=llm)

    assert result["flight_results"] == []
    assert result["flight_cost_estimate"] == 0.0
    assert llm.prompts == []  # never called


def test_zero_search_results_short_circuits_without_calling_llm(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: [])
    llm = RecordingFakeLLM()

    state = {
        "destination_city": "Atlanta",
        "origin_airport": "JFK",
        "destination_airport": "ATL",
        "travel_month": "September",
    }
    result = flight_agent_node(state, llm=llm)

    assert result["flight_results"] == []
    assert result["flight_cost_estimate"] == 0.0
    assert llm.prompts == []


def test_cost_estimate_is_cheapest_result_doubled(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)

    state = {
        "destination_city": "Atlanta",
        "origin_airport": "JFK",
        "destination_airport": "ATL",
        "travel_month": "September",
    }
    result = flight_agent_node(state, llm=FakeLLM())

    assert result["flight_cost_estimate"] == 200.0  # cheapest (100.0) * 2


def test_recommendation_prompt_only_describes_the_cheapest_flight(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)
    llm = RecordingFakeLLM()

    state = {
        "destination_city": "Atlanta",
        "origin_airport": "JFK",
        "destination_airport": "ATL",
        "travel_month": "September",
    }
    flight_agent_node(state, llm=llm)

    assert len(llm.prompts) == 1
    assert "Delta" in llm.prompts[0]
    assert "United" not in llm.prompts[0]
