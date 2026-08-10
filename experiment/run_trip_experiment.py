"""
Test area for the combined flight+hotel tool-calling variant
(experiment/trip_tool_calling_agent.py).

Usage:
    python experiment/run_trip_experiment.py 'flight from BOS to San Diego with a hotel for $500'
    python experiment/run_trip_experiment.py 'just a flight from BOS to MIA, budget $200'
    python experiment/run_trip_experiment.py 'find me a hotel in LAX for $150'
    python experiment/run_trip_experiment.py   # uses the default below
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from experiment.trip_tool_calling_agent import plan_trip_via_tool_calling

DEFAULT_REQUEST = "Find me a flight from BOS to MIA with a hotel, budget $500."


def main() -> None:
    user_request = " ".join(sys.argv[1:]) or DEFAULT_REQUEST

    print("=" * 70)
    print("(1) user prompt -> model  (model has ONLY the prompt + both tool schemas, never the CSVs)")
    print(f'    "{user_request}"')
    print()

    outcome = plan_trip_via_tool_calling(user_request)

    if not outcome["tool_calls"]:
        print("(!) Model answered WITHOUT calling any tool -- not backed by real data:")
        print(f"    {outcome['final_answer']}")
        return

    print(f"(2) model -> tool call(s): {[c['name'] + '(' + str(c['args']) + ')' for c in outcome['tool_calls']]}")
    print()
    print("(3) tool owner executes each for real against the CSVs (no model involved)")
    if outcome["flight_result"] is not None:
        print(f"    search_flights raw result: {outcome['flight_result']}")
    if outcome["hotel_result"] is not None:
        print(f"    search_hotels raw result:  {outcome['hotel_result']}")
    print()

    if outcome["budget_analysis"] is not None:
        print("(4) both tools ran -> code computes the VERIFIED combined budget analysis")
        print(f"    {outcome['budget_analysis']}")
        print()

    print("(5) tool result(s) [+ verified analysis] -> model -> final answer")
    print("=" * 70)
    print(outcome["final_answer"])


if __name__ == "__main__":
    main()
