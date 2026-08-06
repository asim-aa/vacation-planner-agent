from agents.flight_agent import flight_agent_node
from tests.fake_llm import FakeLLM, RecordingFakeLLM


def test_no_destination_airport_short_circuits_without_calling_llm():
    llm = RecordingFakeLLM()
    state = {
        "destination_city": "Paris",
        "origin_airport": "JFK",
        "destination_airport": None,
    }

    result = flight_agent_node(state, llm=llm)

    assert result["flight_results"] == []
    assert result["flight_cost_estimate"] == 0.0
    assert llm.prompts == []


def test_unknown_route_short_circuits_without_calling_llm():
    llm = RecordingFakeLLM()
    state = {
        "destination_city": "Nowhere",
        "origin_airport": "JFK",
        "destination_airport": "ATL",
        "seat_class": "First",  # route+class combo that may not exist
    }

    result = flight_agent_node(state, llm=llm)

    if not result["flight_results"]:
        assert result["flight_cost_estimate"] == 0.0
        assert llm.prompts == []


def test_flight_cost_is_cheapest_one_way_doubled():
    llm = FakeLLM()
    state = {
        "destination_city": "Atlanta",
        "origin_airport": "JFK",
        "destination_airport": "ATL",
        "seat_class": "Economy",
    }

    result = flight_agent_node(state, llm=llm)

    assert result["flight_results"]
    cheapest = min(r["Price_USD"] for r in result["flight_results"])
    assert result["flight_cost_estimate"] == round(cheapest * 2, 2)


def test_recommendation_prompt_only_describes_the_cheapest_flight():
    llm = RecordingFakeLLM()
    state = {
        "destination_city": "Atlanta",
        "origin_airport": "JFK",
        "destination_airport": "ATL",
        "seat_class": "Economy",
    }

    result = flight_agent_node(state, llm=llm)

    cheapest_airline = result["flight_results"][0]["Airline"]
    cheapest_price = str(result["flight_results"][0]["Price_USD"])
    assert len(llm.prompts) == 1
    assert cheapest_airline in llm.prompts[0]
    assert cheapest_price in llm.prompts[0]
