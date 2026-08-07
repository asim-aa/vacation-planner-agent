"""Flight Agent: LangGraph node wrapping tools/flight_tool.py (v3, fast-flights)."""

from agents.date_utils import next_occurrence_of_month
from agents.llm_client import get_llm
from agents.state import TripState
from tools.flight_tool import get_baseline_price, resolve_city_to_iata, search_flights


def flight_agent_node(state: TripState, llm=None) -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided.

    Airport resolution (tools.flight_tool.resolve_city_to_iata) is fully
    offline -- no network call, no quota -- so any real origin/destination
    city works, not a fixed airport list on either side.
    """
    seat_class = state.get("seat_class", "Economy")

    origin_code = resolve_city_to_iata(state["origin_city"], state.get("origin_country"))
    destination_code = resolve_city_to_iata(state["destination_city"], state.get("destination_country"))

    if not origin_code or not destination_code:
        unresolved = state["origin_city"] if not origin_code else state["destination_city"]
        return {
            "flight_results": [],
            "flight_recommendation": f"Couldn't find an airport for {unresolved}.",
            "flight_cost_estimate": 0.0,
        }

    try:
        departure_date = next_occurrence_of_month(state.get("travel_month", "April"))
    except ValueError:
        departure_date = next_occurrence_of_month("April")

    results = search_flights(
        origin=origin_code,
        destination=destination_code,
        departure_date=departure_date,
        seat_class=seat_class,
        limit=10,
    )

    if not results:
        return {
            "flight_results": [],
            "flight_recommendation": (
                f"No {seat_class} flights found from {origin_code} "
                f"to {destination_code} on {departure_date}."
            ),
            "flight_cost_estimate": 0.0,
        }

    baseline = get_baseline_price(results)

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
