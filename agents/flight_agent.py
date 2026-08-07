"""Flight Agent: LangGraph node wrapping tools/flight_tool.py (v3, fast-flights)."""

from calendar import monthrange
from datetime import date

from agents.llm_client import get_llm
from agents.state import TripState
from tools.flight_tool import get_baseline_price, resolve_city_to_iata, search_flights

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def _next_occurrence_of_month(month_name: str, day: int = 15) -> str:
    """Return YYYY-MM-DD for the next future occurrence of `month_name`
    (e.g. "April"), clamping `day` to that month's length."""
    today = date.today()
    month_num = MONTH_NAMES.index(month_name.strip().lower()) + 1
    year = today.year if month_num >= today.month else today.year + 1
    day = min(day, monthrange(year, month_num)[1])
    return date(year, month_num, day).isoformat()


def flight_agent_node(state: TripState, llm=None) -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided.

    Airport resolution (tools.flight_tool.resolve_city_to_iata) is fully
    offline -- no network call, no quota -- so any real destination city
    works, not just a fixed airport list.
    """
    seat_class = state.get("seat_class", "Economy")

    destination_code = state.get("destination_airport") or resolve_city_to_iata(
        state["destination_city"], state.get("destination_country")
    )
    if not destination_code:
        return {
            "flight_results": [],
            "flight_recommendation": (
                f"Couldn't find an airport for {state['destination_city']}."
            ),
            "flight_cost_estimate": 0.0,
        }

    try:
        departure_date = _next_occurrence_of_month(state.get("travel_month", "April"))
    except ValueError:
        departure_date = _next_occurrence_of_month("April")

    results = search_flights(
        origin=state["origin_airport"],
        destination=destination_code,
        departure_date=departure_date,
        seat_class=seat_class,
        limit=10,
    )

    if not results:
        return {
            "flight_results": [],
            "flight_recommendation": (
                f"No {seat_class} flights found from {state['origin_airport']} "
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
