"""Hotel Agent: LangGraph node wrapping tools/hotel_tool.py (v2, fast-hotels)."""

from agents.date_utils import add_days, next_occurrence_of_month
from agents.llm_client import get_llm
from agents.narrative_guard import mentions_unexpected_city
from agents.state import TripState
from tools.hotel_tool import search_hotels, select_hotel


def _template_hotel_recommendation(hotel: dict) -> str:
    return f"{hotel['HotelName']} in {hotel['cityName']}, ${hotel['EstimatedPriceUSD']:,.0f}/night."


def build_hotel_output(results: list[dict], duration_days: int, optimize_for: str = "cheapest", llm=None) -> dict:
    """Select + narrate a hotel from already-fetched `results` -- no
    network call. Split out from hotel_agent_node so a budget-
    reallocation follow-up (e.g. "spend the rest of my budget on a
    better hotel") can re-pick from the SAME candidates instead of
    re-scraping Google Hotels, which is both wasteful and non-
    deterministic (a fresh scrape can return a different set of hotels
    entirely, since live availability/pricing shifts between calls).
    """
    if not results:
        return {
            "hotel_results": [],
            "hotel_recommendation": "No hotels found within the given budget.",
            "lodging_cost_estimate": 0.0,
        }

    # Pin the recommendation (and the itinerary's "check into X" line,
    # which reads hotel_results[0]) to this exact pick, whichever mode
    # chose it -- otherwise the LLM's narrative pick could disagree.
    top_hotel = select_hotel(results, optimize_for=optimize_for)
    ordered_results = [top_hotel] + [h for h in results if h is not top_hotel]

    llm = llm or get_llm()
    pick_description = (
        "the best-rated option that still fits the trip's budget"
        if optimize_for == "quality"
        else "the cheapest option available for this trip"
    )
    prompt = (
        f"You are a travel planning assistant. This hotel (JSON) is {pick_description}. "
        "Write 1-2 sentences recommending it, mentioning its price and a couple of its "
        "amenities. Only use the data given, do not invent details, and do "
        "not suggest a different hotel or mention any other city.\n\n"
        f"{top_hotel}"
    )
    recommendation = llm.invoke(prompt).content

    # Same defensive check as the flight agent -- don't trust the LLM's
    # prose with place names any more than we trust it with the price.
    allowed_names = {top_hotel.get("cityName"), *str(top_hotel.get("HotelName", "")).split()}
    if mentions_unexpected_city(recommendation, allowed_names):
        recommendation = _template_hotel_recommendation(top_hotel)

    nightly_price = top_hotel["EstimatedPriceUSD"]

    return {
        "hotel_results": ordered_results,
        "hotel_recommendation": recommendation,
        "lodging_cost_estimate": round(nightly_price * duration_days, 2),
    }


def hotel_agent_node(state: TripState, llm=None, optimize_for: str = "cheapest") -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided."""
    duration_days = state.get("duration_days", 5)

    try:
        checkin_date = next_occurrence_of_month(state.get("travel_month", "April"))
    except ValueError:
        checkin_date = next_occurrence_of_month("April")
    checkout_date = add_days(checkin_date, duration_days)

    results = search_hotels(
        city=state["destination_city"],
        checkin_date=checkin_date,
        checkout_date=checkout_date,
        max_price=state.get("max_nightly_hotel_price"),
        limit=10,
    )

    output = build_hotel_output(results, duration_days, optimize_for=optimize_for, llm=llm)
    if not results:
        output["hotel_recommendation"] = f"No hotels found in {state['destination_city']} within the given budget."
    return output
