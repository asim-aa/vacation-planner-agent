from agents.hotel_agent import hotel_agent_node
from tests.fake_llm import FakeLLM, RecordingFakeLLM


def test_zero_result_short_circuits_without_calling_llm():
    llm = RecordingFakeLLM()
    state = {"destination_city": "Nonexistentville", "duration_days": 5}

    result = hotel_agent_node(state, llm=llm)

    assert result["hotel_results"] == []
    assert result["lodging_cost_estimate"] == 0.0
    assert llm.prompts == []  # never called


def test_lodging_cost_uses_cheapest_result_times_duration():
    llm = FakeLLM("Great pick!")
    state = {"destination_city": "Paris", "duration_days": 4}

    result = hotel_agent_node(state, llm=llm)

    assert result["hotel_results"]
    cheapest = min(r["EstimatedPriceUSD"] for r in result["hotel_results"])
    assert result["lodging_cost_estimate"] == round(cheapest * 4, 2)


def test_recommendation_prompt_only_describes_the_cheapest_hotel():
    llm = RecordingFakeLLM("Great pick!")
    state = {"destination_city": "Paris", "duration_days": 4}

    result = hotel_agent_node(state, llm=llm)

    cheapest_name = result["hotel_results"][0]["HotelName"]
    assert len(llm.prompts) == 1
    assert cheapest_name in llm.prompts[0]
    # No other hotel name from the results should appear in the prompt --
    # the LLM should only ever see the one hotel it's allowed to recommend.
    other_names = [r["HotelName"] for r in result["hotel_results"][1:]]
    assert not any(name in llm.prompts[0] for name in other_names)


def test_respects_max_nightly_hotel_price():
    llm = FakeLLM()
    state = {"destination_city": "Paris", "duration_days": 4, "max_nightly_hotel_price": 50}

    result = hotel_agent_node(state, llm=llm)

    assert all(r["EstimatedPriceUSD"] <= 50 for r in result["hotel_results"])
