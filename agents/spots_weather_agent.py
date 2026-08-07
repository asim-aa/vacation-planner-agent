"""Spots & Weather Agent: LangGraph node wrapping tools/spots_weather_tool.py (v2, real places)."""

from agents.llm_client import get_llm
from agents.state import TripState
from tools.spots_weather_tool import search_destinations


def rank_spots(results: list[dict], optimize_for: str = "default") -> list[dict]:
    """Pure ranking, no LLM/network call -- callers that just need to know
    the order (e.g. app.py previewing whether a "notable" re-rank would
    actually change anything) can call this directly instead of paying
    for an LLM call via build_spot_output.

    "default": season-matched spots first, then closest to city center.
    "notable": same season-match priority, but within that, spots with a
    real Wikipedia/Wikidata entry (see tools/places_tool.py's "Notable"
    field) rank above untagged ones -- OSM has no popularity/rating data
    at all, so this is a real, if imperfect, stand-in for "well-known",
    not a fabricated score. Distance from center is still the final
    tie-break either way.
    """
    if optimize_for == "notable":
        return sorted(
            results,
            key=lambda r: (
                not r.get("season_match", False),
                not r.get("Notable", False),
                r.get("DistanceFromCenterKm") or 0,
            ),
        )
    return sorted(
        results,
        key=lambda r: (not r.get("season_match", False), r.get("DistanceFromCenterKm") or 0),
    )


def build_spot_output(results: list[dict], duration_days: int, optimize_for: str = "default", llm=None) -> dict:
    """Rank + narrate from already-fetched `results` -- no network call.
    Split out from spots_weather_agent_node so a follow-up (e.g. "show me
    more well-known spots") can re-rank the SAME candidates instead of
    re-querying Overpass (same reasoning as the identical fix already made
    for hotels and flights).
    """
    if not results:
        return {
            "spot_results": [],
            "spot_recommendation": "No activity data found.",
            "activities_cost_estimate": 0.0,
        }

    ranked = rank_spots(results, optimize_for=optimize_for)

    llm = llm or get_llm()
    pick_framing = (
        "prioritizing well-known spots (a real Wikipedia/Wikidata entry) within each "
        "season-matched tier"
        if optimize_for == "notable"
        else "already ranked with the best season-matched, closest-to-center options first"
    )
    prompt = (
        f"You are a travel planning assistant. Given this list of real "
        f"tourist attractions (JSON), {pick_framing}, recommend the "
        "top 2-3 spots -- prefer the first few in the list -- and explain "
        "why in a few sentences. Only use the data given, do not invent "
        f"details.\n\n{ranked}"
    )
    recommendation = llm.invoke(prompt).content

    top = ranked[:3]
    avg_daily_cost = sum(r["EstimatedCostUSD"] for r in top) / len(top)

    return {
        "spot_results": ranked,
        "spot_recommendation": recommendation,
        "activities_cost_estimate": round(avg_daily_cost * duration_days, 2),
    }


def spots_weather_agent_node(state: TripState, llm=None) -> dict:
    """`llm` is injectable so tests can pass a fake instead of hitting the
    real endpoint; defaults to the real client when not provided."""
    results = search_destinations(
        city=state["destination_city"],
        country=state.get("destination_country"),
        travel_month=state.get("travel_month"),
        limit=10,
    )

    output = build_spot_output(results, state.get("duration_days", 5), llm=llm)
    if not results:
        output["spot_recommendation"] = f"No activity data found for {state['destination_city']}."
    return output
