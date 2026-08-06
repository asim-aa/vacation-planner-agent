"""
Streamlit front end for the vacation planner orchestrator.

Usage:
    streamlit run app.py
"""

import streamlit as st

from agents.graph import plan_trip

st.set_page_config(page_title="Vacation Planner", page_icon="🧳")

st.title("🧳 Vacation Planner")
st.caption(
    "Describe your trip in one sentence -- destination, budget, duration, "
    "and travel month. The Hotel, Flight, and Spots & Weather agents "
    "will do the rest."
)

with st.expander("Coverage notes (mock data, not live APIs)"):
    st.markdown(
        "- **Flights** only cover 8 US airports: JFK, ORD, SEA, LAX, SFO, "
        "ATL, DFW, DEN. Non-US or unlisted destinations will show no "
        "flight data.\n"
        "- **Hotel prices** are synthetic (derived from star rating), "
        "not real rates.\n"
        "- **Destinations/activities** dataset covers 22 countries."
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

if st.button("Plan my trip", type="primary"):
    if not user_request.strip():
        st.warning("Enter a trip request first.")
    else:
        with st.spinner("Running the Hotel, Flight, and Spots & Weather agents..."):
            try:
                final_state = plan_trip(user_request)
                st.markdown(final_state["itinerary_markdown"])
            except Exception as e:
                st.error(f"Something went wrong: {e}")
