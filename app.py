"""
Streamlit front end for the vacation planner orchestrator.

Renders each sub-agent's real output (flights, lodging, activities,
budget) as native Streamlit widgets -- cards, tabs, metrics -- instead of
dumping the raw itinerary Markdown, while still offering that Markdown as
a download for anyone who wants the plain-text version.

Usage:
    streamlit run app.py
"""

import pandas as pd
import streamlit as st

from agents.compile_itinerary import compile_itinerary_node
from agents.flight_agent import build_flight_output
from agents.graph import plan_trip
from agents.hotel_agent import build_hotel_output
from tools.flight_tool import select_flight

st.set_page_config(page_title="Vacation Planner", page_icon="🧳", layout="wide")

st.title("🧳 Vacation Planner")
st.caption(
    "Describe your trip in one sentence -- destination, budget, duration, "
    "and travel month. The Hotel, Flight, and Spots & Weather agents "
    "will do the rest."
)

with st.expander("ℹ️ Coverage notes"):
    st.markdown(
        "- ✈️ **Flights** are live (Google Flights via `fast-flights`) -- any "
        "real origin/destination city works, no fixed airport list. Routes "
        "with no direct itinerary fall back to a self-assembled connection "
        "through a major hub.\n"
        "- 🏨 **Hotels** are live (Google Hotels via `fast-hotels`) -- any "
        "real city works, with real nightly prices.\n"
        "- 🎡 **Activity spots** are real, named places (OpenStreetMap via "
        "Nominatim + Overpass) -- any real city works. Prices are a "
        "coarse fee-tag heuristic, not real cost data; there are no star "
        "ratings, so spots are ranked by distance from the city center.\n"
        "- 🌤️ **Weather/season fit** is live real historical climate data "
        "(Open-Meteo), checked at the actual destination city's real "
        "coordinates."
    )

default_example = (
    "Plan me a 6 day trip to Paris, France in April. My budget is $2500 "
    "and I'm flying out of New York."
)

user_request = st.text_area(
    "Your trip request",
    value=default_example,
    height=100,
)

go = st.button("✈️ Plan my trip", type="primary")

if go:
    if not user_request.strip():
        st.warning("Enter a trip request first.")
    else:
        with st.spinner("Running the Hotel, Flight, and Spots & Weather agents..."):
            try:
                st.session_state["trip_state"] = plan_trip(user_request)
                st.session_state["trip_error"] = None
            except Exception as e:
                st.session_state["trip_error"] = str(e)
                st.session_state["trip_state"] = None


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _flight_row(flight: dict) -> dict:
    return {
        "Airline": flight.get("Airline", "Unknown"),
        "Price ($)": flight.get("Price_USD", 0.0),
        "Stops": flight.get("Stops", 0),
        "Departs": flight.get("Departure_Time", ""),
        "Arrives": flight.get("Arrival_Time", ""),
    }


def refine_flight_for_comfort(state: dict) -> dict:
    """Re-pick a flight in comfort mode (fewest stops that still fits the
    trip's overall budget) from the SAME candidates already fetched this
    run -- no new search, same reasoning as refine_hotel_for_quality."""
    max_one_way = (
        state.get("budget_total", 0.0)
        - state.get("lodging_cost_estimate", 0.0)
        - state.get("activities_cost_estimate", 0.0)
    ) / 2
    flight_output = build_flight_output(
        state.get("flight_results", []),
        state.get("seat_class", "Economy"),
        optimize_for="comfort",
        max_price=max_one_way,
    )
    updated_state = {**state, **flight_output}
    updated_state.update(compile_itinerary_node(updated_state))
    return updated_state


def render_flights(state: dict) -> None:
    flights = state.get("flight_results", [])
    if not flights:
        st.info(state.get("flight_recommendation", "No flight data."))
        return

    top = flights[0]
    with st.container(border=True):
        cols = st.columns([3, 1, 1])
        cols[0].markdown(f"#### {top['Airline']}")
        cols[1].metric("Price", _money(top["Price_USD"]))
        cols[2].metric("Stops", top["Stops"])

        if top.get("SelfConnectedVia"):
            st.badge(f"Self-connect via {top['SelfConnectedVia']}", icon="⚠️", color="orange")

        st.write(f"**{top['Departure_Airport']} → {top['Arrival_Airport']}**  ·  {top['Seat_Class']}")
        st.caption(f"Departs {top['Departure_Time']}  →  Arrives {top['Arrival_Time']}")

    st.markdown("**Why this flight**")
    st.write(state.get("flight_recommendation", ""))

    max_one_way = (
        state.get("budget_total", 0.0)
        - state.get("lodging_cost_estimate", 0.0)
        - state.get("activities_cost_estimate", 0.0)
    ) / 2
    comfort_pick = select_flight(flights, optimize_for="comfort", max_price=max_one_way)
    if comfort_pick["Stops"] < top["Stops"]:
        headroom = max_one_way - top["Price_USD"]
        st.caption(f"💡 You have up to {_money(headroom)} more per one-way ticket to spend on fewer stops.")
        if st.button("💎 Spend it on a more direct flight instead"):
            with st.spinner("Re-picking your flight for comfort..."):
                st.session_state["trip_state"] = refine_flight_for_comfort(state)
            st.rerun()

    if len(flights) > 1:
        with st.expander(f"See {len(flights) - 1} more option(s)"):
            df = pd.DataFrame([_flight_row(f) for f in flights[1:]])
            st.dataframe(df, hide_index=True, width="stretch")


def refine_hotel_for_quality(state: dict) -> dict:
    """Re-pick a hotel in quality mode from the SAME candidates already
    fetched this run (no new search -- a fresh Google Hotels scrape can
    return a different set of hotels entirely, since live availability
    shifts between calls) and refresh the compiled itinerary to match.
    Flights and activities are untouched."""
    hotel_output = build_hotel_output(
        state.get("hotel_results", []), state.get("duration_days", 5), optimize_for="quality"
    )
    updated_state = {**state, **hotel_output}
    updated_state.update(compile_itinerary_node(updated_state))
    return updated_state


def render_lodging(state: dict) -> None:
    hotels = state.get("hotel_results", [])
    if not hotels:
        st.info(state.get("hotel_recommendation", "No hotel data."))
        return

    top = hotels[0]
    with st.container(border=True):
        cols = st.columns([3, 1])
        cols[0].markdown(f"#### {top['HotelName']}")
        cols[1].metric("Per night", _money(top["EstimatedPriceUSD"]))

        if top.get("GuestRating"):
            st.write(f"⭐ {top['GuestRating']} guest rating")

        amenities = top.get("Amenities") or []
        if amenities:
            st.write(" · ".join(f"`{a}`" for a in amenities[:6]))

        if top.get("URL"):
            st.markdown(f"[View on Google Hotels]({top['URL']})")

    st.markdown("**Why this hotel**")
    st.write(state.get("hotel_recommendation", ""))

    max_nightly = state.get("max_nightly_hotel_price")
    headroom = max_nightly - top["EstimatedPriceUSD"] if max_nightly else 0
    if headroom > 1:
        st.caption(f"💡 You have up to {_money(headroom)}/night of budget headroom left unused.")
        if st.button("💎 Spend it on a better-rated hotel instead"):
            with st.spinner("Re-picking your hotel for quality..."):
                st.session_state["trip_state"] = refine_hotel_for_quality(state)
            st.rerun()

    if len(hotels) > 1:
        with st.expander(f"See {len(hotels) - 1} more option(s)"):
            df = pd.DataFrame([
                {
                    "Hotel": h["HotelName"],
                    "Price/night ($)": h["EstimatedPriceUSD"],
                    "Rating": h.get("GuestRating") or "—",
                }
                for h in hotels[1:]
            ])
            st.dataframe(df, hide_index=True, width="stretch")


def render_activities(state: dict) -> None:
    spots = state.get("spot_results", [])
    if not spots:
        st.info(state.get("spot_recommendation", "No activity data."))
        return

    st.markdown("**Why these picks**")
    st.write(state.get("spot_recommendation", ""))

    climate = next((s.get("climate") for s in spots if s.get("climate")), None)
    if climate:
        c1, c2, c3 = st.columns(3)
        c1.metric("🌡️ Avg high", f"{climate['avg_max_temp_c']}°C")
        c2.metric("🌧️ Avg daily rain", f"{climate['avg_daily_precip_mm']} mm")
        c3.metric("Season fit", "✅ Good" if climate.get("suitable") else "⚠️ Mixed")

    st.markdown("#### Top picks")
    top = spots[:3]
    cols = st.columns(len(top))
    for col, spot in zip(cols, top):
        with col:
            with st.container(border=True):
                st.markdown(f"**{spot['Destination Name']}**")
                st.caption(spot.get("Type", ""))
                cost = spot.get("EstimatedCostUSD", 0.0)
                st.write(f"💵 {'Free' if cost == 0 else _money(cost)}")
                dist = spot.get("DistanceFromCenterKm")
                if dist is not None:
                    st.write(f"📍 {dist} km from center")
                if spot.get("season_match") is True:
                    st.badge("Great season fit", icon="🌤️", color="green")
                elif spot.get("season_match") is False:
                    st.badge("Off-season", icon="🌧️", color="gray")

    if len(spots) > 3:
        with st.expander(f"See {len(spots) - 3} more nearby attractions"):
            df = pd.DataFrame([
                {
                    "Name": s["Destination Name"],
                    "Type": s.get("Type", ""),
                    "Est. cost ($)": s.get("EstimatedCostUSD", 0.0),
                    "Distance (km)": s.get("DistanceFromCenterKm"),
                }
                for s in spots[3:]
            ])
            st.dataframe(df, hide_index=True, width="stretch")


def render_days(state: dict) -> None:
    duration_days = state.get("duration_days", 5)
    hotels = state.get("hotel_results", [])
    spots = state.get("spot_results", [])
    destination = state.get("destination_city", "")
    top_hotel = hotels[0]["HotelName"] if hotels else "TBD (no hotel found in budget)"
    spot_names = [s["Destination Name"] for s in spots]

    if duration_days <= 1:
        with st.container(border=True):
            st.markdown(f"**🛬 Day 1** — Arrive in {destination}, check into **{top_hotel}**, and depart same-day.")
        return

    with st.container(border=True):
        st.markdown(f"**🛬 Day 1** — Arrive in {destination}, check into **{top_hotel}**.")

    num_middle_days = duration_days - 2
    for i in range(num_middle_days):
        day_number = i + 2
        spot = spot_names[i] if i < len(spot_names) else "Free day to explore"
        with st.container(border=True):
            st.markdown(f"**🎯 Day {day_number}** — Visit **{spot}**.")

    with st.container(border=True):
        st.markdown(f"**🛫 Day {duration_days}** — Departure from {destination}.")


def render_budget(flight_cost: float, lodging_cost: float, activities_cost: float, total: float, budget: float) -> None:
    df = pd.DataFrame({
        "Category": ["Flights", "Lodging", "Activities"],
        "Cost": [flight_cost, lodging_cost, activities_cost],
    }).set_index("Category")
    st.bar_chart(df, y="Cost")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✈️ Flights", _money(flight_cost))
    c2.metric("🏨 Lodging", _money(lodging_cost))
    c3.metric("🎡 Activities", _money(activities_cost))
    c4.metric("🧾 Total", _money(total))

    if total <= budget:
        st.success(f"✅ Within budget — {_money(budget - total)} to spare")
    else:
        st.error(f"⚠️ Over budget by {_money(total - budget)}")


def render_itinerary(state: dict) -> None:
    destination = f"{state.get('destination_city', '')}, {state.get('destination_country', '')}"
    duration_days = state.get("duration_days", 0)
    travel_month = state.get("travel_month", "N/A")
    budget = state.get("budget_total", 0.0)
    total = state.get("total_cost_estimate", 0.0)
    flight_cost = state.get("flight_cost_estimate", 0.0)
    lodging_cost = state.get("lodging_cost_estimate", 0.0)
    activities_cost = state.get("activities_cost_estimate", 0.0)
    within_budget = total <= budget

    st.divider()
    st.header(f"🗺️ {destination}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 Duration", f"{duration_days} days")
    c2.metric("🗓️ Month", travel_month)
    c3.metric("💰 Budget", _money(budget))
    c4.metric(
        "🧾 Estimated total",
        _money(total),
        delta=_money(total - budget) if not within_budget else f"-{_money(budget - total)}",
        delta_color="inverse",
    )

    budget_fraction = min(total / budget, 1.0) if budget else 0.0
    st.progress(
        budget_fraction,
        text=("✅ Within budget" if within_budget else "⚠️ Over budget")
        + f" — {_money(total)} of {_money(budget)}",
    )

    tab_flights, tab_lodging, tab_activities, tab_days, tab_budget = st.tabs(
        ["✈️ Flights", "🏨 Lodging", "🎡 Activities", "📅 Day-by-Day", "💵 Budget"]
    )
    with tab_flights:
        render_flights(state)
    with tab_lodging:
        render_lodging(state)
    with tab_activities:
        render_activities(state)
    with tab_days:
        render_days(state)
    with tab_budget:
        render_budget(flight_cost, lodging_cost, activities_cost, total, budget)

    st.download_button(
        "⬇️ Download full itinerary (Markdown)",
        state.get("itinerary_markdown", ""),
        file_name="itinerary.md",
        mime="text/markdown",
    )


if st.session_state.get("trip_error"):
    st.error(f"Something went wrong: {st.session_state['trip_error']}")
elif st.session_state.get("trip_state"):
    render_itinerary(st.session_state["trip_state"])
