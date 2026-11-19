"""Deterministic checks on a planned-trip state JSON. Exit 0 = pass."""
import json
import re
import sys

REQUIRED = ["## Flights", "## Lodging", "## Activities & Weather Fit",
            "## Chronological Itinerary", "## Itemized Budget Breakdown"]


def verify(state: dict) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    md = state.get("itinerary_markdown", "")
    if not md:
        return ["no itinerary_markdown in state"], warnings

    for h in REQUIRED:
        if h not in md:
            errors.append(f"missing section: {h}")

    parts = [state.get(k, 0.0) for k in
             ("flight_cost_estimate", "lodging_cost_estimate", "activities_cost_estimate")]
    expected = round(sum(parts), 2)
    total = state.get("total_cost_estimate")
    if total is None or abs(total - expected) > 0.01:
        errors.append(f"total {total} != sum of parts {expected}")

    budget = state.get("budget_total")
    if budget is not None and total is not None:
        over = total > budget
        if over and "Within budget" in md:
            errors.append("says within budget but total exceeds budget")
        if not over and "Over budget" in md:
            errors.append("says over budget but total is within budget")

    days = state.get("duration_days")
    if days:
        found = [int(n) for n in re.findall(r"\*\*Day (\d+):\*\*", md)]
        if sorted(found) != list(range(1, days + 1)):
            errors.append(f"days in itinerary {sorted(found)} != 1..{days}")

    for key, label in [("flight_results", "flights"), ("hotel_results", "hotels"),
                       ("spot_results", "activities")]:
        if not state.get(key):
            warnings.append(f"no {label} found -- tell the user, do not fill the gap")
    return errors, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_itinerary.py trip.json", file=sys.stderr)
        return 2
    with open(sys.argv[1]) as f:
        state = json.load(f)
    errors, warnings = verify(state)
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")
    print("PASS" if not errors else f"{len(errors)} check(s) failed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
