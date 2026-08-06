"""Hotel Agent: LangGraph node wrapping tools/hotel_tool.py."""

from agents.llm_client import get_llm
from agents.state import TripState
from tools.hotel_tool import search_hotels


def hotel_agent_node(state: TripState, llm=None) -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided."""
    results = search_hotels(
        city=state["destination_city"],
        max_price=state.get("max_nightly_hotel_price"),
        limit=10,
    )

    if not results:
        return {
            "hotel_results": [],
            "hotel_recommendation": (
                f"No hotels found in {state['destination_city']} "
                f"within the given budget."
            ),
            "lodging_cost_estimate": 0.0,
        }

    # `results` is already sorted cheapest-first by the tool. Pin the
    # recommendation to that exact hotel (results[0]) instead of letting the
    # LLM pick freely -- otherwise its narrative pick and the itinerary's
    # "check into X" line (which uses results[0]) can name different hotels.
    top_hotel = results[0]

    llm = llm or get_llm()
    prompt = (
        "You are a travel planning assistant. This hotel (JSON) is the "
        "cheapest option available for this trip. Write 1-2 sentences "
        "recommending it, mentioning its price and a couple of its "
        "amenities. Only use the data given, do not invent details, and do "
        "not suggest a different hotel.\n\n"
        f"{top_hotel}"
    )
    recommendation = llm.invoke(prompt).content

    duration_days = state.get("duration_days", 5)
    cheapest_nightly = top_hotel["EstimatedPriceUSD"]

    return {
        "hotel_results": results,
        "hotel_recommendation": recommendation,
        "lodging_cost_estimate": round(cheapest_nightly * duration_days, 2),
    }
