"""
Small test area for the CSV flight-search experiment.

Matches the sketch: (1) user prompt -> orchestrator, (2) orchestrator ->
model to extract structured criteria -- then the orchestrator (this
script) runs a deterministic search against the CSV, no model involved
in step 3.

Usage:
    python experiment/run_experiment.py "I'm flying from Chicago to Boston, budget $300"
    python experiment/run_experiment.py   # uses the default example below
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from experiment.csv_flight_search import AIRPORT_NAMES, plan_flight

DEFAULT_REQUEST = "I need to fly from Chicago to Boston, and I don't want to spend more than $300."


def _print_flight(flight: dict) -> None:
    print(
        f"    {flight['Flight_ID']}  {flight['Airline']:<10}  "
        f"{flight['Departure_Airport']} -> {flight['Arrival_Airport']}  "
        f"${flight['Price_USD']:>7.2f}  "
        f"{flight['Flight_Duration_Minutes']} min  "
        f"({flight['Flight_Status']})"
    )


def main() -> None:
    user_request = " ".join(sys.argv[1:]) or DEFAULT_REQUEST

    print("=" * 70)
    print("(1) user prompt -> orchestrator")
    print(f"    \"{user_request}\"")
    print()
    print("(2) orchestrator -> model  (extracting structured criteria)")

    outcome = plan_flight(user_request)
    criteria = outcome["criteria"]
    result = outcome["result"]

    origin_name = AIRPORT_NAMES[criteria["origin_airport"]]
    dest_name = AIRPORT_NAMES[criteria["destination_airport"]]
    print(f"    origin={criteria['origin_airport']} ({origin_name})")
    print(f"    destination={criteria['destination_airport']} ({dest_name})")
    print(f"    max_budget={'$' + format(criteria['max_budget'], '.2f') if criteria['max_budget'] is not None else '(none stated)'}")
    print()
    print("(3) orchestrator -> CSV search  (deterministic, no model)")
    print("=" * 70)

    if result["status"] == "no_budget_stated":
        print(
            "⚠️  No budget found in your request -- refusing to search rather than "
            "guess one. Include a dollar amount (e.g. \"budget $200\"), and if you're "
            "using double quotes in the shell, make sure the \"$\" isn't getting "
            "swallowed (use single quotes instead)."
        )
    elif result["status"] == "no_route":
        print(f"No flights exist from {criteria['origin_airport']} to {criteria['destination_airport']} in this dataset.")
    elif result["status"] == "over_budget":
        print(
            f"❌ Not possible within your ${result['budget']:.2f} budget.\n"
            f"   Cheapest real option: ${result['cheapest_price']:.2f} "
            f"(you're ${result['shortfall']:.2f} short)."
        )
        print("   Closest flight:")
        _print_flight(result["cheapest_flight"])
    else:
        print(f"✅ {len(result['flights'])} flight(s) found within budget, cheapest first:")
        for flight in result["flights"]:
            _print_flight(flight)


if __name__ == "__main__":
    main()
