"""Final node: assembles all sub-agent output into one Markdown itinerary."""

from agents.state import TripState


def _budget_row(label: str, amount: float) -> str:
    return f"| {label} | ${amount:,.2f} |"


def compile_itinerary_node(state: TripState) -> dict:
    duration_days = state.get("duration_days", 5)
    flight_cost = state.get("flight_cost_estimate", 0.0)
    lodging_cost = state.get("lodging_cost_estimate", 0.0)
    activities_cost = state.get("activities_cost_estimate", 0.0)
    total = round(flight_cost + lodging_cost + activities_cost, 2)
    budget_total = state["budget_total"]
    over_by = round(total - budget_total, 2)

    hotels = state.get("hotel_results", [])
    spots = state.get("spot_results", [])
    top_hotel = hotels[0]["HotelName"] if hotels else "TBD (no hotel found in budget)"

    if duration_days <= 1:
        day_lines = [
            f"- **Day 1:** Arrive in {state['destination_city']}, check into "
            f"{top_hotel}, and depart same-day."
        ]
    else:
        day_lines = [f"- **Day 1:** Arrive in {state['destination_city']}, check into {top_hotel}."]
        num_middle_days = duration_days - 2
        spot_names = [s["Destination Name"] for s in spots]
        for i in range(num_middle_days):
            day_number = i + 2
            spot = spot_names[i] if i < len(spot_names) else "Free day to explore"
            day_lines.append(f"- **Day {day_number}:** Visit {spot}.")
        day_lines.append(f"- **Day {duration_days}:** Departure from {state['destination_city']}.")

    budget_status = (
        f"✅ Within budget (${budget_total:,.2f})"
        if total <= budget_total
        else f"⚠️ Over budget by ${over_by:,.2f}"
    )

    markdown = f"""# Vacation Itinerary: {state['destination_city']}, {state['destination_country']}

**Travel month:** {state.get('travel_month', 'N/A')} | **Duration:** {duration_days} days | **Budget:** ${budget_total:,.2f}

## Flights
{state.get('flight_recommendation', 'No flight data.')}

## Lodging
{state.get('hotel_recommendation', 'No hotel data.')}

## Activities & Weather Fit
{state.get('spot_recommendation', 'No activity data.')}

## Chronological Itinerary
{chr(10).join(day_lines)}

## Itemized Budget Breakdown

| Category | Cost |
|---|---|
{_budget_row('Flights (round-trip)', flight_cost)}
{_budget_row(f'Lodging ({duration_days} nights)', lodging_cost)}
{_budget_row(f'Activities ({duration_days} days)', activities_cost)}
| **Total** | **${total:,.2f}** |

**Budget status:** {budget_status}
"""

    return {
        "total_cost_estimate": total,
        "itinerary_markdown": markdown,
    }
