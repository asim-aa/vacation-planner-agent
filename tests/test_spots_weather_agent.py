"""
spots_weather_agent_node calls tools.spots_weather_tool.search_destinations,
which hits real network services (Nominatim + Overpass). These tests
monkeypatch search_destinations -- the same "inject a fake instead of the
real dependency" pattern used elsewhere -- so the agent's ranking/cost
logic is verified without any network call.
"""

import agents.spots_weather_agent as spots_weather_agent_module
from agents.spots_weather_agent import build_spot_output, rank_spots, spots_weather_agent_node
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


NOTABLE_FAKE_RESULTS = [
    {"Destination Name": "Obscure Plaza", "Type": "Attraction", "EstimatedCostUSD": 0.0,
     "DistanceFromCenterKm": 0.2, "season_match": True, "Notable": False},
    {"Destination Name": "Famous Landmark", "Type": "Museum", "EstimatedCostUSD": 15.0,
     "DistanceFromCenterKm": 1.5, "season_match": True, "Notable": True},
    {"Destination Name": "Off-Season Icon", "Type": "Museum", "EstimatedCostUSD": 15.0,
     "DistanceFromCenterKm": 0.1, "season_match": False, "Notable": True},
]


def test_build_spot_output_discards_hallucinated_city_for_template(monkeypatch):
    monkeypatch.setattr(spots_weather_agent_module, "search_destinations", lambda *a, **k: list(FAKE_RESULTS))
    llm = FakeLLM("These spots are a short walk from the beaches of Miami.")

    result = build_spot_output(FAKE_RESULTS, duration_days=3, llm=llm)

    assert "Miami" not in result["spot_recommendation"]
    assert "Close Park" in result["spot_recommendation"]


def test_build_spot_output_keeps_recommendation_without_hallucination(monkeypatch):
    monkeypatch.setattr(spots_weather_agent_module, "search_destinations", lambda *a, **k: list(FAKE_RESULTS))
    llm = FakeLLM("Close Park and Mid Gallery are both close to the center and free or cheap.")

    result = build_spot_output(FAKE_RESULTS, duration_days=3, llm=llm)

    assert result["spot_recommendation"] == "Close Park and Mid Gallery are both close to the center and free or cheap."


def test_rank_spots_notable_mode_is_pure_no_llm_needed():
    # app.py uses this directly (no build_spot_output/LLM call) to preview
    # whether a "notable" re-rank would actually change anything.
    ranked = rank_spots(NOTABLE_FAKE_RESULTS, optimize_for="notable")
    assert [s["Destination Name"] for s in ranked] == ["Famous Landmark", "Obscure Plaza", "Off-Season Icon"]


def test_build_spot_output_notable_mode_prefers_wikipedia_tagged_spots_within_season_tier():
    result = build_spot_output(NOTABLE_FAKE_RESULTS, duration_days=5, optimize_for="notable", llm=FakeLLM())

    names = [s["Destination Name"] for s in result["spot_results"]]
    # Famous Landmark (notable, season-matched) beats Obscure Plaza (not
    # notable, season-matched) despite being farther from the center --
    # but Off-Season Icon still loses to both since season-match still
    # outranks notability, it's just the tie-break within a tier.
    assert names == ["Famous Landmark", "Obscure Plaza", "Off-Season Icon"]


def test_build_spot_output_does_not_search_again(monkeypatch):
    def fail_if_called(*a, **k):
        raise AssertionError("build_spot_output must not search again")

    monkeypatch.setattr(spots_weather_agent_module, "search_destinations", fail_if_called)

    result = build_spot_output(list(FAKE_RESULTS), duration_days=3, optimize_for="notable", llm=FakeLLM())

    assert result["spot_results"]
