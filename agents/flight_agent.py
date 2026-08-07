"""Flight Agent: LangGraph node wrapping tools/flight_tool.py (v3, fast-flights)."""

from agents.date_utils import next_occurrence_of_month
from agents.llm_client import get_llm
from agents.state import TripState
from tools.flight_tool import (
    get_baseline_price,
    resolve_city_to_iata_candidates,
    search_flights,
    search_flights_via_hub,
)

# Bounds how many (origin, destination) candidate pairs we'll try when the
# best-guess airport on either side turns up zero flights -- e.g. Jakarta
# has two "International"-named airports (CGK, HLP) and the offline
# resolver can't always tell which is the real hub. Capped so a genuinely
# unserved route still fails in a bounded number of live searches.
MAX_ROUTE_ATTEMPTS = 4


def flight_agent_node(state: TripState, llm=None) -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided.

    Airport resolution (tools.flight_tool.resolve_city_to_iata_candidates)
    is fully offline -- no network call, no quota -- so any real
    origin/destination city works, not a fixed airport list on either
    side.
    """
    seat_class = state.get("seat_class", "Economy")

    origin_candidates = resolve_city_to_iata_candidates(state["origin_city"], state.get("origin_country"))
    destination_candidates = resolve_city_to_iata_candidates(
        state["destination_city"], state.get("destination_country")
    )

    if not origin_candidates or not destination_candidates:
        unresolved = state["origin_city"] if not origin_candidates else state["destination_city"]
        return {
            "flight_results": [],
            "flight_recommendation": f"Couldn't find an airport for {unresolved}.",
            "flight_cost_estimate": 0.0,
        }

    try:
        departure_date = next_occurrence_of_month(state.get("travel_month", "April"))
    except ValueError:
        departure_date = next_occurrence_of_month("April")

    route_pairs = []
    for o in origin_candidates:
        for d in destination_candidates:
            if (o, d) not in route_pairs:
                route_pairs.append((o, d))
    route_pairs = route_pairs[:MAX_ROUTE_ATTEMPTS]

    results = []
    origin_code, destination_code = route_pairs[0]
    for o, d in route_pairs:
        results = search_flights(
            origin=o,
            destination=d,
            departure_date=departure_date,
            seat_class=seat_class,
            limit=10,
        )
        if results:
            origin_code, destination_code = o, d
            break

    if not results:
        # Every direct candidate pair came back empty -- not necessarily a
        # scrape failure, sometimes Google's own engine just can't build
        # any itinerary that far off the beaten path (seen live: Boise ->
        # Jakarta finds nothing even as a round-trip). Try self-assembling
        # a connection through a major hub before giving up entirely.
        #
        # Try each distinct destination candidate, not just route_pairs[0]
        # -- a secondary/domestic-leaning airport (e.g. Jakarta's HLP) can
        # have poor hub connectivity even when the metro's real primary
        # hub (CGK) connects fine.
        tried_destinations = set()
        for o, d in route_pairs:
            if d in tried_destinations:
                continue
            tried_destinations.add(d)
            hub_results = search_flights_via_hub(o, d, departure_date, seat_class=seat_class, limit=10)
            if hub_results:
                results, origin_code, destination_code = hub_results, o, d
                break

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

    # Don't rely on the LLM to notice and mention this on its own -- a
    # self-assembled connection is materially different (two separate
    # tickets, real misconnection risk) and that caveat must always show,
    # not just when the model happens to surface it.
    if top_flight.get("SelfConnectedVia"):
        recommendation = (
            f"⚠️ No single itinerary was found for this route, so this is a "
            f"self-assembled connection via {top_flight['SelfConnectedVia']} -- "
            "book as two separate tickets, which carries real misconnection risk. "
            f"{recommendation}"
        )

    cheapest_one_way = top_flight["Price_USD"]

    return {
        "flight_results": results,
        "flight_recommendation": recommendation,
        # Round-trip estimate: cheapest one-way fare, doubled for the return leg.
        "flight_cost_estimate": round(cheapest_one_way * 2, 2),
    }
