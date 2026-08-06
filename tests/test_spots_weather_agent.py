from agents.spots_weather_agent import spots_weather_agent_node
from tests.fake_llm import FakeLLM, RecordingFakeLLM


def test_zero_result_short_circuits_without_calling_llm():
    llm = RecordingFakeLLM()
    state = {"destination_country": "Nowhereland", "duration_days": 5}

    result = spots_weather_agent_node(state, llm=llm)

    assert result["spot_results"] == []
    assert result["activities_cost_estimate"] == 0.0
    assert llm.prompts == []


def test_results_ranked_season_match_first_then_rating():
    llm = FakeLLM()
    state = {
        "destination_country": "Japan",
        "travel_month": "April",
        "duration_days": 5,
    }

    result = spots_weather_agent_node(state, llm=llm)

    spots = result["spot_results"]
    assert spots
    keys = [(not s.get("season_match", False), -s["Avg Rating"]) for s in spots]
    assert keys == sorted(keys)


def test_activities_cost_is_avg_of_top_three_times_duration():
    llm = FakeLLM()
    state = {
        "destination_country": "Japan",
        "travel_month": "April",
        "duration_days": 3,
    }

    result = spots_weather_agent_node(state, llm=llm)

    top3 = result["spot_results"][:3]
    expected_avg = sum(s["Avg Cost (USD/day)"] for s in top3) / len(top3)
    assert result["activities_cost_estimate"] == round(expected_avg * 3, 2)
