"""
spots_weather_agent_node calls tools.spots_weather_tool.search_destinations,
which hits real network services (Nominatim + Overpass). These tests
monkeypatch search_destinations -- the same "inject a fake instead of the
real dependency" pattern used elsewhere -- so the agent's ranking/cost
logic is verified without any network call.
"""

import agents.spots_weather_agent as spots_weather_agent_module
from agents.spots_weather_agent import spots_weather_agent_node
from tests.fake_llm import FakeLLM, RecordingFakeLLM

FAKE_RESULTS = [
    {"Destination Name": "Far Museum", "Type": "Museum", "EstimatedCostUSD": 15.0,
     "DistanceFromCenterKm": 5.0, "season_match": False},
    {"Destination Name": "Close Park", "Type": "Attraction", "EstimatedCostUSD": 0.0,
     "DistanceFromCenterKm": 0.5, "season_match": True},
    {"Destination Name": "Mid Gallery", "Type": "Gallery", "EstimatedCostUSD": 10.0,
     "DistanceFromCenterKm": 2.0, "season_match": True},
]


def test_zero_result_short_circuits_without_calling_llm(monkeypatch):
    monkeypatch.setattr(spots_weather_agent_module, "search_destinations", lambda *a, **k: [])
    llm = RecordingFakeLLM()

    state = {"destination_city": "Nowhereland", "duration_days": 5}
    result = spots_weather_agent_node(state, llm=llm)

    assert result["spot_results"] == []
    assert result["activities_cost_estimate"] == 0.0
    assert llm.prompts == []


def test_results_ranked_season_match_first_then_closest(monkeypatch):
    monkeypatch.setattr(spots_weather_agent_module, "search_destinations", lambda *a, **k: list(FAKE_RESULTS))

    state = {"destination_city": "Paris", "travel_month": "April", "duration_days": 5}
    result = spots_weather_agent_node(state, llm=FakeLLM())

    names = [s["Destination Name"] for s in result["spot_results"]]
    # Season-matched first (Close Park, Mid Gallery), then by distance;
    # Far Museum (not season-matched) goes last despite being in the list.
    assert names == ["Close Park", "Mid Gallery", "Far Museum"]


def test_activities_cost_is_avg_of_top_three_times_duration(monkeypatch):
    monkeypatch.setattr(spots_weather_agent_module, "search_destinations", lambda *a, **k: list(FAKE_RESULTS))

    state = {"destination_city": "Paris", "travel_month": "April", "duration_days": 3}
    result = spots_weather_agent_node(state, llm=FakeLLM())

    # top3 after ranking: Close Park (0.0), Mid Gallery (10.0), Far Museum (15.0)
    expected_avg = (0.0 + 10.0 + 15.0) / 3
    assert result["activities_cost_estimate"] == round(expected_avg * 3, 2)


def test_recommendation_prompt_receives_ranked_list(monkeypatch):
    monkeypatch.setattr(spots_weather_agent_module, "search_destinations", lambda *a, **k: list(FAKE_RESULTS))
    llm = RecordingFakeLLM()

    state = {"destination_city": "Paris", "travel_month": "April", "duration_days": 5}
    spots_weather_agent_node(state, llm=llm)

    assert len(llm.prompts) == 1
    assert "Close Park" in llm.prompts[0]
