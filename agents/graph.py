"""
Vacation Planner Orchestrator: the LangGraph StateGraph wiring all sub-agent
nodes together.

Flow:
    parse_request
        -> [flight_agent, spots_weather_agent] (parallel)
        -> compute_hotel_budget  (waits for both branches)
        -> hotel_agent           (uses the remaining-budget ceiling)
        -> compile_itinerary
"""

from langgraph.graph import END, START, StateGraph

from agents.budget import compute_hotel_budget_node
from agents.compile_itinerary import compile_itinerary_node
from agents.flight_agent import flight_agent_node
from agents.hotel_agent import hotel_agent_node
from agents.parse_request import parse_request_node
from agents.spots_weather_agent import spots_weather_agent_node
from agents.state import TripState


def build_graph():
    graph = StateGraph(TripState)

    graph.add_node("parse_request", parse_request_node)
    graph.add_node("flight_agent", flight_agent_node)
    graph.add_node("spots_weather_agent", spots_weather_agent_node)
    graph.add_node("compute_hotel_budget", compute_hotel_budget_node)
    graph.add_node("hotel_agent", hotel_agent_node)
    graph.add_node("compile_itinerary", compile_itinerary_node)

    graph.add_edge(START, "parse_request")

    # Fan out: flights and spots/weather don't depend on each other.
    graph.add_edge("parse_request", "flight_agent")
    graph.add_edge("parse_request", "spots_weather_agent")

    # Fan in: hotel budget needs both branches' cost estimates.
    graph.add_edge("flight_agent", "compute_hotel_budget")
    graph.add_edge("spots_weather_agent", "compute_hotel_budget")

    graph.add_edge("compute_hotel_budget", "hotel_agent")
    graph.add_edge("hotel_agent", "compile_itinerary")
    graph.add_edge("compile_itinerary", END)

    return graph.compile()


app = build_graph()


def plan_trip(user_request: str) -> dict:
    """Run the full orchestrator for one natural-language trip request."""
    return app.invoke({"user_request": user_request})
