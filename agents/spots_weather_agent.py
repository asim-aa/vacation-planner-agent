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
        }

    llm = get_llm()
    prompt = (
        "You are a travel planning assistant. Given this list of activity "
        "spots (JSON), each with a season_match flag indicating whether it "
        "suits the traveler's month, recommend the top 2-3 spots and "
        "explain why in a few sentences. Prefer season_match=true when "
        "possible. Only use the data given, do not invent details.\n\n"
        f"{results}"
    )
    recommendation = llm.invoke(prompt).content

    return {"spot_results": results, "spot_recommendation": recommendation}
