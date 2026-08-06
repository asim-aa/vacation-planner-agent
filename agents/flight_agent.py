"""Flight Agent: LangGraph node wrapping tools/flight_tool.py."""

from agents.llm_client import get_llm
from agents.state import TripState
from tools.flight_tool import get_baseline_price, search_flights


def flight_agent_node(state: TripState) -> dict:
    seat_class = state.get("seat_class", "Economy")
    results = search_flights(
        origin=state["origin_airport"],
        destination=state["destination_airport"],
        seat_class=seat_class,
        limit=10,
    )
    baseline = get_baseline_price(
        origin=state["origin_airport"],
        destination=state["destination_airport"],
        seat_class=seat_class,
    )

    if not results:
        return {
            "flight_results": [],
            "flight_recommendation": (
                f"No {seat_class} flights found from {state['origin_airport']} "
                f"to {state['destination_airport']}."
            ),
        }

    llm = get_llm()
    prompt = (
        "You are a travel planning assistant. Given this list of flight "
        f"options (JSON) and a baseline average price of ${baseline}, pick "
        "the single best value option and explain why in 1-2 sentences. "
        f"Only use the data given, do not invent details.\n\n{results}"
    )
    recommendation = llm.invoke(prompt).content

    return {
        "flight_results": results,
        "flight_recommendation": recommendation,
    }
