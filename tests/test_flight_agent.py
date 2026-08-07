"""
flight_agent_node calls fast-flights (real network, no quota, but still
worth keeping out of the deterministic default suite). These tests
monkeypatch resolve_city_to_iata/search_flights -- the same
"inject a fake instead of the real dependency" pattern used for the LLM
-- so the agent's control flow (resolution, date computation, cost math,
zero-result handling) is verified without any network call.

Both origin and destination are resolved via resolve_city_to_iata --
there is no fixed airport list on either side (that was a leftover
restriction from the RapidAPI-era design, fixed after testing surfaced
that origin was still silently defaulting to JFK for any unlisted city).
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

BASE_STATE = {
    "destination_city": "Atlanta",
    "destination_country": "USA",
    "origin_city": "New York",
    "origin_country": "USA",
    "travel_month": "September",
}


def _resolver(mapping):
    return lambda city, country=None: mapping.get(city)


def test_next_occurrence_of_month_returns_future_date():
    result = next_occurrence_of_month("April")
    assert result.endswith("-04-15")


def test_resolves_both_origin_and_destination_by_city_name(monkeypatch):
    resolved = []
    monkeypatch.setattr(
        flight_agent_module, "resolve_city_to_iata",
        lambda city, country=None: resolved.append(city) or {"New York": "JFK", "Atlanta": "ATL"}[city],
    )
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)

    result = flight_agent_node(BASE_STATE, llm=FakeLLM())

    assert set(resolved) == {"New York", "Atlanta"}  # neither side skipped resolution
    assert result["flight_results"] == FAKE_RESULTS


def test_any_real_city_works_not_just_a_fixed_list(monkeypatch):
    # e.g. Berlin was never in the old hardcoded 8-airport list.
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", _resolver({"Berlin": "BER", "Rome": "FCO"}))
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)

    state = {**BASE_STATE, "origin_city": "Berlin", "destination_city": "Rome"}
    result = flight_agent_node(state, llm=FakeLLM())

    assert result["flight_results"] == FAKE_RESULTS


def test_unresolvable_origin_returns_empty_without_crashing(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", lambda city, country=None: None)
    llm = RecordingFakeLLM()

    result = flight_agent_node(BASE_STATE, llm=llm)

    assert result["flight_results"] == []
    assert result["flight_cost_estimate"] == 0.0
    assert llm.prompts == []  # never called


def test_unresolvable_destination_returns_empty_without_crashing(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", _resolver({"New York": "JFK"}))
    llm = RecordingFakeLLM()

    result = flight_agent_node(BASE_STATE, llm=llm)

    assert result["flight_results"] == []
    assert result["flight_cost_estimate"] == 0.0
    assert llm.prompts == []


def test_zero_search_results_short_circuits_without_calling_llm(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", _resolver({"New York": "JFK", "Atlanta": "ATL"}))
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: [])
    llm = RecordingFakeLLM()

    result = flight_agent_node(BASE_STATE, llm=llm)

    assert result["flight_results"] == []
    assert result["flight_cost_estimate"] == 0.0
    assert llm.prompts == []


def test_cost_estimate_is_cheapest_result_doubled(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", _resolver({"New York": "JFK", "Atlanta": "ATL"}))
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)

    result = flight_agent_node(BASE_STATE, llm=FakeLLM())

    assert result["flight_cost_estimate"] == 200.0  # cheapest (100.0) * 2


def test_recommendation_prompt_only_describes_the_cheapest_flight(monkeypatch):
    monkeypatch.setattr(flight_agent_module, "resolve_city_to_iata", _resolver({"New York": "JFK", "Atlanta": "ATL"}))
    monkeypatch.setattr(flight_agent_module, "search_flights", lambda *a, **k: FAKE_RESULTS)
    llm = RecordingFakeLLM()

    flight_agent_node(BASE_STATE, llm=llm)

    assert len(llm.prompts) == 1
    assert "Delta" in llm.prompts[0]
    assert "United" not in llm.prompts[0]
