"""
Test area for the tool-calling variant (experiment/tool_calling_flight_agent.py).

Usage:
    python experiment/run_tool_calling_experiment.py 'flying from Boston to Miami, budget $200'
    python experiment/run_tool_calling_experiment.py   # uses the default below
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from experiment.tool_calling_flight_agent import plan_flight_via_tool_calling

DEFAULT_REQUEST = "I need to fly from Boston to Phoenix, budget $200."


def main() -> None:
    user_request = " ".join(sys.argv[1:]) or DEFAULT_REQUEST

    print("=" * 70)
    print("(1) user prompt -> model  (model has ONLY the prompt + the tool's schema, never the CSV)")
    print(f"    \"{user_request}\"")
    print()

    outcome = plan_flight_via_tool_calling(user_request)

    if outcome["tool_call"] is None:
        print("(!) Model answered WITHOUT calling the tool -- not backed by real data:")
        print(f"    {outcome['final_answer']}")
        return

    print(f"(2) model -> tool call: search_flights({outcome['tool_call']['args']})")
    print()
    print("(3) tool owner executes it for real against the CSV (no model involved)")
    print(f"    raw result: {outcome['tool_result']}")
    print()
    print("(4) tool result -> model -> final answer")
    print("=" * 70)
    print(outcome["final_answer"])


if __name__ == "__main__":
    main()
