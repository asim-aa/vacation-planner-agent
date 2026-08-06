"""Spots & Weather Agent: LangGraph node wrapping tools/spots_weather_tool.py."""

from agents.llm_client import get_llm
from agents.state import TripState
from tools.spots_weather_tool import search_destinations


def spots_weather_agent_node(state: TripState) -> dict:
    results = search_destinations(
        country=state["destination_country"],
        travel_month=state.get("travel_month"),
        limit=10,
    )

    if not results:
        return {
            "spot_results": [],
            "spot_recommendation": (
                f"No activity data found for {state['destination_country']}."
            ),
            "activities_cost_estimate": 0.0,
        }

    # Rank season-matched spots first (then by rating) so both the LLM's
    # narrative recommendation and the day-by-day itinerary downstream draw
    # from the same ordered list -- otherwise they can pick different spots.
    ranked = sorted(
        results,
        key=lambda r: (not r.get("season_match", False), -r["Avg Rating"]),
    )

    llm = get_llm()
    prompt = (
        "You are a travel planning assistant. Given this list of activity "
        "spots (JSON), already ranked with the best season-matched, "
        "highest-rated options first, recommend the top 2-3 spots -- "
        "prefer the first few in the list -- and explain why in a few "
        "sentences. Only use the data given, do not invent details.\n\n"
        f"{ranked}"
    )
    recommendation = llm.invoke(prompt).content

    duration_days = state.get("duration_days", 5)
    top = ranked[:3]
    avg_daily_cost = sum(r["Avg Cost (USD/day)"] for r in top) / len(top)

    return {
        "spot_results": ranked,
        "spot_recommendation": recommendation,
        "activities_cost_estimate": round(avg_daily_cost * duration_days, 2),
    }
