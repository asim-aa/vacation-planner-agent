"""Flight Agent: LangGraph node wrapping tools/flight_tool.py."""

from agents.llm_client import get_llm
from agents.state import TripState
from tools.flight_tool import get_baseline_price, search_flights


def flight_agent_node(state: TripState, llm=None) -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided."""
    seat_class = state.get("seat_class", "Economy")

    if not state.get("destination_airport"):
        return {
            "flight_results": [],
            "flight_recommendation": (
                f"No flight data available -- {state['destination_city']} isn't "
                "served by any of the 8 US airports this dataset covers."
            ),
            "flight_cost_estimate": 0.0,
        }

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
            "flight_cost_estimate": 0.0,
        }

    # `results` is already sorted cheapest-first by the tool. Pin the
    # recommendation to that exact flight instead of letting the LLM pick
    # freely -- otherwise its narrative pick and the cost estimate (which
    # uses results[0]) can disagree.
    top_flight = results[0]

    llm = llm or get_llm()
    prompt = (
        "You are a travel planning assistant. This flight (JSON) is the "
        f"cheapest option available, against a baseline average price of "
        f"${baseline}. Write 1-2 sentences recommending it. Only use the "
        "data given, do not invent details, and do not suggest a different "
        f"flight.\n\n{top_flight}"
    )
    recommendation = llm.invoke(prompt).content

    cheapest_one_way = top_flight["Price_USD"]

    return {
        "flight_results": results,
        "flight_recommendation": recommendation,
        # Round-trip estimate: cheapest one-way fare, doubled for the return leg.
        "flight_cost_estimate": round(cheapest_one_way * 2, 2),
    }
