"""
Full Phase 4 orchestrator demo: give it one natural-language trip request,
get back a single Markdown itinerary.

Usage:
    python demo_orchestrator.py "Plan me a 5 day trip to Paris in April, budget $2000"
"""

import sys

from agents.graph import plan_trip

DEFAULT_REQUEST = (
    "Plan me a 6 day trip to Paris, France in April. My budget is $2500 "
    "and I'm flying out of New York."
)


def main() -> None:
    user_request = " ".join(sys.argv[1:]) or DEFAULT_REQUEST
    print(f"Request: {user_request}\n")
    print("Running orchestrator...\n")

    final_state = plan_trip(user_request)
    print(final_state["itinerary_markdown"])


if __name__ == "__main__":
    main()
