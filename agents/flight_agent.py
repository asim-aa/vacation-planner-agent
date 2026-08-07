"""Flight Agent: LangGraph node wrapping tools/flight_tool.py (v2, live API)."""

from calendar import monthrange
from datetime import date

from agents.llm_client import get_llm
from agents.state import TripState
from tools.flight_tool import (
    get_baseline_price,
    resolve_airport,
    resolve_city_to_airport,
    search_flights_by_ids,
)

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

    Resolves origin/destination exactly once and makes exactly one search
    request -- the baseline price is computed from that same response, not
    a second live call -- since the free API tier is quota-limited.
    """
    seat_class = state.get("seat_class", "Economy")

    origin_ids = resolve_airport(state["origin_airport"])

    # A known IATA code (from parse_request's fixed airport list) resolves
    # for free; anything else -- any real city -- resolves via free-text
    # lookup, which is what removes the old 8-airport limit.
    destination_airport = state.get("destination_airport")
    if destination_airport:
        destination_ids = resolve_airport(destination_airport)
        destination_code = destination_airport
    else:
        destination_ids = resolve_city_to_airport(state["destination_city"])
        destination_code = destination_ids["displayCode"] if destination_ids else None

    if not origin_ids or not destination_ids:
        return {
            "flight_results": [],
            "flight_recommendation": (
                f"Couldn't resolve an airport for "
                f"{state['origin_airport'] if not origin_ids else state['destination_city']}."
            ),
            "flight_cost_estimate": 0.0,
        }

    try:
        departure_date = _next_occurrence_of_month(state.get("travel_month", "April"))
    except ValueError:
        departure_date = _next_occurrence_of_month("April")

    results = search_flights_by_ids(
        origin_ids, destination_ids, departure_date, seat_class=seat_class, limit=10
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
