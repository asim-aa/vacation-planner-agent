"""Hotel Agent: LangGraph node wrapping tools/hotel_tool.py."""

from agents.llm_client import get_llm
from agents.state import TripState
from tools.hotel_tool import search_hotels


def hotel_agent_node(state: TripState) -> dict:
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
        }

    llm = get_llm()
    prompt = (
        "You are a travel planning assistant. Given this list of hotel "
        "options (JSON), pick the single best value option and explain why "
        "in 1-2 sentences. Only use the data given, do not invent details.\n\n"
        f"{results}"
    )
    recommendation = llm.invoke(prompt).content

    return {"hotel_results": results, "hotel_recommendation": recommendation}
